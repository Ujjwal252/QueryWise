
import logging
import math
from collections import Counter
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from sqlglot import parse_one

from app.optimizer.sql_validator import validate_read_only_query
from app.services.external_database_service import (
    open_external_database_connection
)


logger = logging.getLogger(__name__)

MAX_RESULT_ROWS = 10000
MAX_RESULT_SIZE_BYTES = 5 * 1024 * 1024
FETCH_BATCH_SIZE = 500


class QueryEquivalenceServiceError(Exception):
    """Raised when query equivalence validation fails."""


class _ResultLimitExceeded(Exception):
    """Raised when a query result exceeds comparison safety limits."""


def _has_top_level_order_by(query: str) -> bool:
    """Check whether a query contains a top-level ORDER BY clause."""

    statement = parse_one(query, read="mysql")

    return statement.args.get("order") is not None


def _freeze_value(value: Any) -> Any:
    """
    Convert database values into hashable representations.

    Preserves NULL values, duplicate rows, and common numeric types.
    """

    if value is None:
        return ("__NULL__",)

    if isinstance(value, bool):
        return ("__BOOL__", value)

    if isinstance(value, float) and math.isnan(value):
        return ("__FLOAT_NAN__",)

    if isinstance(value, Decimal) and value.is_nan():
        return ("__DECIMAL_NAN__",)

    if isinstance(value, bytearray):
        return bytes(value)

    if isinstance(value, memoryview):
        return value.tobytes()

    if isinstance(value, dict):
        frozen_items = [
            (_freeze_value(key), _freeze_value(item))
            for key, item in value.items()
        ]

        return tuple(sorted(frozen_items, key=repr))

    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)

    if isinstance(value, set):
        return tuple(
            sorted(
                (_freeze_value(item) for item in value),
                key=repr
            )
        )

    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def _estimate_row_size(row: Tuple[Any, ...]) -> int:
    """Estimate the size of a fetched result row in bytes."""

    total_size = 0

    for value in row:

        if value is None:
            continue

        if isinstance(value, bytes):
            total_size += len(value)

        elif isinstance(value, str):
            total_size += len(value.encode("utf-8"))

        else:
            total_size += len(
                repr(value).encode("utf-8", errors="replace")
            )

    return total_size


def _fetch_query_result(cursor: Any) -> Dict[str, Any]:
    """
    Fetch a complete result set within configured safety limits.

    Results are retained in memory because exact comparison requires
    access to the actual returned values.
    """

    if cursor.description is None:
        raise QueryEquivalenceServiceError(
            "The query did not return a result set."
        )

    column_names = [
        column[0]
        for column in cursor.description
    ]

    rows: List[Tuple[Any, ...]] = []
    total_size_bytes = 0

    while True:

        batch = cursor.fetchmany(FETCH_BATCH_SIZE)

        if not batch:
            break

        for row in batch:

            if len(rows) >= MAX_RESULT_ROWS:
                raise _ResultLimitExceeded(
                    "The query result exceeds the maximum of "
                    f"{MAX_RESULT_ROWS} rows."
                )

            total_size_bytes += _estimate_row_size(row)

            if total_size_bytes > MAX_RESULT_SIZE_BYTES:
                raise _ResultLimitExceeded(
                    "The query result exceeds the maximum "
                    "comparison size of 5 MB."
                )

            rows.append(tuple(row))

    return {
        "columns": column_names,
        "rows": rows
    }


def _compare_ordered_rows(
    original_rows: List[Tuple[Any, ...]],
    candidate_rows: List[Tuple[Any, ...]]
) -> bool:
    """Compare rows while preserving their returned order."""

    if len(original_rows) != len(candidate_rows):
        return False

    return all(
        _freeze_value(original) == _freeze_value(candidate)
        for original, candidate in zip(
            original_rows,
            candidate_rows
        )
    )


def _compare_unordered_rows(
    original_rows: List[Tuple[Any, ...]],
    candidate_rows: List[Tuple[Any, ...]]
) -> bool:
    """
    Compare rows as multisets.

    Counter preserves duplicate counts, unlike set comparison.
    """

    if len(original_rows) != len(candidate_rows):
        return False

    original_counter = Counter(
        _freeze_value(row)
        for row in original_rows
    )

    candidate_counter = Counter(
        _freeze_value(row)
        for row in candidate_rows
    )

    return original_counter == candidate_counter


def _close_comparison_resources(
    cursor: Any,
    connection: Any
) -> None:
    """
    Safely release comparison resources.

    If the cursor has unread rows, cursor.close() can fail.
    The database connection must still be closed in that situation.
    """

    if cursor is not None:

        try:
            cursor.close()

        except Exception:
            logger.warning(
                "Equivalence cursor cleanup failed. "
                "The database connection will still be closed.",
                exc_info=True
            )

    if connection is not None:

        try:
            connection.close()

        except Exception:
            logger.warning(
                "Equivalence database connection cleanup failed.",
                exc_info=True
            )


def compare_query_results(
    connection_id: int,
    user_id: int,
    original_query: str,
    candidate_query: str
) -> Dict[str, Any]:
    """
    Validate whether two read-only SELECT queries return equivalent results.

    Both queries execute using the same authorized database connection
    inside a read-only consistent-snapshot transaction.

    Comparison checks:
    - Column names
    - Actual row values
    - Duplicate row counts
    - NULL values
    - Result ordering when ORDER BY is present

    Equivalence is not verified if safety limits are exceeded.
    """

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        raise ValueError("A valid connection ID is required.")

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("A valid user ID is required.")

    queries = {
        "original_query": original_query,
        "candidate_query": candidate_query
    }

    for field_name, query in queries.items():

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                f"{field_name} must be a non-empty SQL query."
            )

        if len(query) > 10000:
            raise ValueError(
                f"{field_name} exceeds the maximum allowed length."
            )

        validation_result = validate_read_only_query(query)

        if not validation_result.is_valid:
            raise ValueError(
                validation_result.error
                or f"{field_name} failed read-only validation."
            )

    try:
        original_ordered = _has_top_level_order_by(original_query)
        candidate_ordered = _has_top_level_order_by(candidate_query)

    except Exception as exc:
        raise ValueError(
            "Unable to analyze query ordering."
        ) from exc

    # Conservatively preserve returned order if either query specifies it.
    order_matters = original_ordered or candidate_ordered

    connection = None
    cursor = None

    try:
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        # Establish one read-only consistent snapshot for both queries.
        # MySQL InnoDB uses this snapshot to provide a stable view of data.
        connection.start_transaction(
            consistent_snapshot=True,
            readonly=True
        )

        cursor = connection.cursor()

        # Execute the original query.
        cursor.execute(original_query)

        original_result = _fetch_query_result(cursor)

        # Execute the candidate query within the same transaction.
        cursor.execute(candidate_query)

        candidate_result = _fetch_query_result(cursor)

        original_columns = original_result["columns"]
        candidate_columns = candidate_result["columns"]

        original_rows = original_result["rows"]
        candidate_rows = candidate_result["rows"]

        columns_match = original_columns == candidate_columns

        if not columns_match:

            equivalent = False
            mismatch_reason = "column_names_differ"

        elif order_matters:

            equivalent = _compare_ordered_rows(
                original_rows,
                candidate_rows
            )

            mismatch_reason = (
                None if equivalent else "ordered_rows_differ"
            )

        else:

            equivalent = _compare_unordered_rows(
                original_rows,
                candidate_rows
            )

            mismatch_reason = (
                None if equivalent else "result_rows_differ"
            )

        return {
            "equivalence_verified": True,
            "equivalent": equivalent,
            "result_order_matters": order_matters,
            "column_names_match": columns_match,
            "original_rows_returned": len(original_rows),
            "candidate_rows_returned": len(candidate_rows),
            "mismatch_reason": mismatch_reason,
            "snapshot_transaction_used": True,
            "limits": {
                "maximum_rows": MAX_RESULT_ROWS,
                "maximum_result_size_bytes": MAX_RESULT_SIZE_BYTES
            }
        }

    except _ResultLimitExceeded as exc:

        logger.warning(
            "Query equivalence comparison stopped by safety limit: %s",
            exc
        )

        return {
            "equivalence_verified": False,
            "equivalent": None,
            "result_order_matters": order_matters,
            "column_names_match": None,
            "original_rows_returned": None,
            "candidate_rows_returned": None,
            "mismatch_reason": "result_limit_exceeded",
            "snapshot_transaction_used": True,
            "message": str(exc),
            "limits": {
                "maximum_rows": MAX_RESULT_ROWS,
                "maximum_result_size_bytes": MAX_RESULT_SIZE_BYTES
            }
        }

    except ValueError:
        raise

    except QueryEquivalenceServiceError:
        raise

    except Exception as exc:

        logger.exception(
            "Query result equivalence validation failed."
        )

        raise QueryEquivalenceServiceError(
            "Unable to complete query result equivalence validation."
        ) from exc

    finally:
        _close_comparison_resources(cursor, connection)
