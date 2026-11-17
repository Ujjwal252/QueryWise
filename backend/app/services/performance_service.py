
import logging
import statistics
import time
from typing import Any, Dict, List

from app.optimizer.sql_validator import validate_read_only_query
from app.services.external_database_service import (
    open_external_database_connection
)


logger = logging.getLogger(__name__)

FETCH_BATCH_SIZE = 1000

# Safety limits
MAX_BENCHMARK_ROWS = 100000
MAX_QUERY_EXECUTION_TIME_MS = 10000
MAX_BENCHMARK_DURATION_SECONDS = 15


class PerformanceServiceError(Exception):
    """Raised when query performance measurement fails."""


class BenchmarkLimitExceeded(PerformanceServiceError):
    """Raised when a benchmark exceeds a configured safety limit."""


def _validate_benchmark_inputs(
    connection_id: int,
    user_id: int,
    query: str,
    iterations: int,
    warmup_runs: int
) -> None:
    """Validate benchmark parameters and read-only SQL."""

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

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty SQL query is required.")

    if len(query) > 10000:
        raise ValueError("SQL query exceeds the maximum allowed length.")

    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or not 2 <= iterations <= 10
    ):
        raise ValueError("Iterations must be an integer between 2 and 10.")

    if (
        isinstance(warmup_runs, bool)
        or not isinstance(warmup_runs, int)
        or not 0 <= warmup_runs <= 2
    ):
        raise ValueError("Warmup runs must be an integer between 0 and 2.")

    validation_result = validate_read_only_query(query)

    if not validation_result.is_valid:
        raise ValueError(
            validation_result.error
            or "Query failed read-only validation."
        )


def _configure_benchmark_session(cursor: Any) -> None:
    """
    Configure a server-side execution limit for SELECT statements.

    This setting applies only to the current database session.
    Closing the connection discards the session setting.
    """

    cursor.execute(
        "SET SESSION max_execution_time = "
        f"{MAX_QUERY_EXECUTION_TIME_MS}"
    )


def _execute_and_measure(cursor: Any, query: str) -> Dict[str, Any]:
    """
    Execute a query and measure execution plus complete result fetching.

    Enforces:
    - MySQL server-side SELECT execution timeout.
    - Application-side elapsed-time limit.
    - Maximum fetched row count.

    Result rows are counted but not retained in memory.
    """

    start_time = time.perf_counter()

    cursor.execute(query)

    current_row_count = 0

    while True:
        elapsed_seconds = time.perf_counter() - start_time

        if elapsed_seconds > MAX_BENCHMARK_DURATION_SECONDS:
            raise BenchmarkLimitExceeded(
                "Query exceeded the maximum benchmark duration of "
                f"{MAX_BENCHMARK_DURATION_SECONDS} seconds."
            )

        remaining_rows = MAX_BENCHMARK_ROWS - current_row_count

        # Fetch one additional row when possible to detect overflow.
        batch_size = min(
            FETCH_BATCH_SIZE,
            remaining_rows + 1
        )

        rows = cursor.fetchmany(batch_size)

        if not rows:
            break

        current_row_count += len(rows)

        if current_row_count > MAX_BENCHMARK_ROWS:
            raise BenchmarkLimitExceeded(
                "Query result exceeds the maximum benchmark limit of "
                f"{MAX_BENCHMARK_ROWS} rows."
            )

    elapsed_seconds = time.perf_counter() - start_time

    if elapsed_seconds > MAX_BENCHMARK_DURATION_SECONDS:
        raise BenchmarkLimitExceeded(
            "Query exceeded the maximum benchmark duration of "
            f"{MAX_BENCHMARK_DURATION_SECONDS} seconds."
        )

    elapsed_ms = elapsed_seconds * 1000

    return {
        "execution_time_ms": round(elapsed_ms, 3),
        "rows_returned": current_row_count
    }


def _close_benchmark_resources(
    cursor: Any,
    connection: Any
) -> None:
    """
    Safely release benchmark resources without masking the main error.

    If a query stops early, the cursor may still have unread rows.
    Cursor cleanup can then fail with MySQL's 'Unread result found'.

    The connection is therefore closed first when cursor cleanup fails.
    Cleanup failures are logged rather than propagated.
    """

    if cursor is not None:
        try:
            cursor.close()
        except Exception:
            logger.warning(
                "Cursor cleanup failed. The database connection "
                "will still be closed.",
                exc_info=True
            )

    if connection is not None:
        try:
            connection.close()
        except Exception:
            logger.warning(
                "Database connection cleanup failed.",
                exc_info=True
            )


def _build_statistics(execution_times: List[float]) -> Dict[str, float]:
    """Calculate descriptive statistics for benchmark measurements."""

    return {
        "average_ms": round(
            statistics.mean(execution_times), 3
        ),
        "median_ms": round(
            statistics.median(execution_times), 3
        ),
        "minimum_ms": round(
            min(execution_times), 3
        ),
        "maximum_ms": round(
            max(execution_times), 3
        )
    }


def _build_benchmark_result(
    execution_times: List[float],
    rows_returned: int,
    iterations: int,
    warmup_runs: int
) -> Dict[str, Any]:

    return {
        "iterations": iterations,
        "warmup_runs": warmup_runs,
        "execution_times_ms": execution_times,
        "statistics": _build_statistics(execution_times),
        "rows_returned": rows_returned
    }


def benchmark_query(
    connection_id: int,
    user_id: int,
    query: str,
    iterations: int = 5,
    warmup_runs: int = 1
) -> Dict[str, Any]:
    """
    Benchmark one read-only SELECT query.

    Warmup executions are excluded from reported measurements.
    Every execution is subject to the configured safety limits.
    """

    _validate_benchmark_inputs(
        connection_id,
        user_id,
        query,
        iterations,
        warmup_runs
    )

    connection = None
    cursor = None

    execution_times: List[float] = []
    rows_returned = None

    try:
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        cursor = connection.cursor()

        _configure_benchmark_session(cursor)

        for _ in range(warmup_runs):
            _execute_and_measure(cursor, query)

        for _ in range(iterations):
            measurement = _execute_and_measure(cursor, query)

            execution_times.append(
                measurement["execution_time_ms"]
            )

            current_row_count = measurement["rows_returned"]

            if rows_returned is None:
                rows_returned = current_row_count

            elif current_row_count != rows_returned:
                logger.warning(
                    "Query returned different row counts between runs."
                )

        return _build_benchmark_result(
            execution_times=execution_times,
            rows_returned=rows_returned,
            iterations=iterations,
            warmup_runs=warmup_runs
        )

    except ValueError:
        raise

    except PerformanceServiceError:
        raise

    except Exception as exc:
        logger.exception("Query performance measurement failed.")

        raise PerformanceServiceError(
            "Unable to complete query performance measurement."
        ) from exc

    finally:
        _close_benchmark_resources(cursor, connection)


def benchmark_query_pair(
    connection_id: int,
    user_id: int,
    original_query: str,
    candidate_query: str,
    iterations: int = 5,
    warmup_runs: int = 1
) -> Dict[str, Any]:
    """
    Benchmark two read-only SELECT queries using alternating execution order.

    Both queries use the same authorized database connection.

    Warmups are performed for both queries before measurements.
    Every execution is subject to the configured safety limits.
    """

    _validate_benchmark_inputs(
        connection_id,
        user_id,
        original_query,
        iterations,
        warmup_runs
    )

    _validate_benchmark_inputs(
        connection_id,
        user_id,
        candidate_query,
        iterations,
        warmup_runs
    )

    if original_query.strip() == candidate_query.strip():
        raise ValueError(
            "Original and candidate queries must be different."
        )

    connection = None
    cursor = None

    original_times: List[float] = []
    candidate_times: List[float] = []

    original_rows = None
    candidate_rows = None

    try:
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        cursor = connection.cursor()

        _configure_benchmark_session(cursor)

        # Warm up both queries before collecting measurements.
        for _ in range(warmup_runs):
            _execute_and_measure(cursor, original_query)
            _execute_and_measure(cursor, candidate_query)

        # Alternate which query executes first in each measured round.
        for run_number in range(iterations):

            if run_number % 2 == 0:
                execution_order = (
                    ("original", original_query),
                    ("candidate", candidate_query)
                )
            else:
                execution_order = (
                    ("candidate", candidate_query),
                    ("original", original_query)
                )

            for query_name, query in execution_order:

                measurement = _execute_and_measure(
                    cursor,
                    query
                )

                if query_name == "original":
                    original_times.append(
                        measurement["execution_time_ms"]
                    )

                    current_rows = measurement["rows_returned"]

                    if original_rows is None:
                        original_rows = current_rows

                    elif current_rows != original_rows:
                        logger.warning(
                            "Original query returned different "
                            "row counts between benchmark runs."
                        )

                else:
                    candidate_times.append(
                        measurement["execution_time_ms"]
                    )

                    current_rows = measurement["rows_returned"]

                    if candidate_rows is None:
                        candidate_rows = current_rows

                    elif current_rows != candidate_rows:
                        logger.warning(
                            "Candidate query returned different "
                            "row counts between benchmark runs."
                        )

        return {
            "iterations": iterations,
            "warmup_runs": warmup_runs,
            "execution_order": "alternating",
            "original_query": _build_benchmark_result(
                execution_times=original_times,
                rows_returned=original_rows,
                iterations=iterations,
                warmup_runs=warmup_runs
            ),
            "candidate_query": _build_benchmark_result(
                execution_times=candidate_times,
                rows_returned=candidate_rows,
                iterations=iterations,
                warmup_runs=warmup_runs
            )
        }

    except ValueError:
        raise

    except PerformanceServiceError:
        raise

    except Exception as exc:
        logger.exception(
            "Paired query performance measurement failed."
        )

        raise PerformanceServiceError(
            "Unable to complete paired query performance measurement."
        ) from exc

    finally:
        _close_benchmark_resources(cursor, connection)
