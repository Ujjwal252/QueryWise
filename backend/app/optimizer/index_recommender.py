
from typing import Any, Dict, List, Set, Tuple

from sqlglot import exp, parse_one


def _normalize_identifier(value: str) -> str:
    """Normalize an SQL identifier for comparison."""
    return value.strip("`").lower()


def _get_existing_index_columns(
    existing_indexes: List[Dict[str, Any]]
) -> Set[Tuple[str, str]]:
    """
    Extract leading indexed table-column pairs.

    MySQL composite indexes follow the leftmost-prefix rule.
    Only sequence_in_index == 1 is treated as the leading column.
    """

    indexed_columns = set()

    for index in existing_indexes:
        table_name = index.get("table_name")
        column_name = index.get("column_name")

        sequence = index.get("sequence_in_index", 1)

        if (
            table_name
            and column_name
            and sequence == 1
        ):
            indexed_columns.add((
                _normalize_identifier(table_name),
                _normalize_identifier(column_name)
            ))

    return indexed_columns


def _get_table_aliases(select: exp.Select) -> Dict[str, str]:
    """Map table names and aliases to their actual table names."""

    aliases = {}

    from_clause = select.args.get("from_")

    if from_clause is not None:
        source = from_clause.this

        if isinstance(source, exp.Table):
            table_name = _normalize_identifier(source.name)
            alias = _normalize_identifier(source.alias_or_name)

            aliases[table_name] = table_name
            aliases[alias] = table_name

    for join in select.args.get("joins") or []:
        source = join.this

        if isinstance(source, exp.Table):
            table_name = _normalize_identifier(source.name)
            alias = _normalize_identifier(source.alias_or_name)

            aliases[table_name] = table_name
            aliases[alias] = table_name

    return aliases


def _extract_filter_columns(
    query: str
) -> List[Dict[str, str]]:
    """Extract columns used in WHERE and JOIN ON conditions."""

    statement = parse_one(query, read="mysql")

    if not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT statements are supported.")

    candidates = []

    for select in statement.find_all(exp.Select):

        aliases = _get_table_aliases(select)
        unique_tables = set(aliases.values())

        single_table = (
            next(iter(unique_tables))
            if len(unique_tables) == 1
            else None
        )

        where_clause = select.args.get("where")

        if where_clause is not None:
            for column in where_clause.find_all(exp.Column):

                if not column.name:
                    continue

                qualifier = _normalize_identifier(column.table)

                if qualifier:
                    table_name = aliases.get(qualifier, "")
                else:
                    table_name = single_table or ""

                candidates.append({
                    "table_name": table_name,
                    "column_name": _normalize_identifier(column.name),
                    "source": "WHERE"
                })

        for join in select.args.get("joins") or []:
            on_expression = join.args.get("on")

            if on_expression is None:
                continue

            for column in on_expression.find_all(exp.Column):

                if not column.name:
                    continue

                qualifier = _normalize_identifier(column.table)
                table_name = aliases.get(qualifier, "") if qualifier else ""

                candidates.append({
                    "table_name": table_name,
                    "column_name": _normalize_identifier(column.name),
                    "source": "JOIN"
                })

    unique_candidates = []
    seen = set()

    for candidate in candidates:
        key = (
            candidate["table_name"],
            candidate["column_name"],
            candidate["source"]
        )

        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    return unique_candidates


def _get_table_access_information(
    execution_analysis: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Extract table access information from analyzed MySQL plans."""

    table_information = {}

    for table in execution_analysis.get("tables", []):
        table_name = table.get("table_name")

        if not table_name:
            continue

        normalized_name = _normalize_identifier(table_name)

        table_information[normalized_name] = {
            "access_type": table.get("access_type"),
            "estimated_rows": table.get(
                "rows_examined_per_scan"
            ),
            "selected_key": table.get("selected_key")
        }

    return table_information


def recommend_indexes(
    query: str,
    execution_analysis: Dict[str, Any],
    existing_indexes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate cautious index recommendations.

    This function never creates or modifies database indexes.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty SQL query is required.")

    if not isinstance(execution_analysis, dict):
        raise ValueError("Execution analysis must be a dictionary.")

    if not isinstance(existing_indexes, list):
        raise ValueError("Existing indexes must be a list.")

    if execution_analysis.get("database_engine") != "MySQL":
        raise ValueError("Only MySQL execution plans are supported.")

    filter_columns = _extract_filter_columns(query)

    indexed_columns = _get_existing_index_columns(
        existing_indexes
    )

    table_information = _get_table_access_information(
        execution_analysis
    )

    recommendations = []
    skipped = []
    seen_candidates = set()

    for candidate in filter_columns:

        table_name = candidate["table_name"]
        column_name = candidate["column_name"]

        if not table_name:
            skipped.append({
                "column": column_name,
                "reason": (
                    "The column cannot be mapped unambiguously "
                    "to a table."
                )
            })
            continue

        candidate_key = (table_name, column_name)

        if candidate_key in seen_candidates:
            continue

        seen_candidates.add(candidate_key)

        if candidate_key in indexed_columns:
            skipped.append({
                "table_name": table_name,
                "column_name": column_name,
                "reason": (
                    "The column is already a leading column "
                    "of an existing index."
                )
            })
            continue

        access_information = table_information.get(table_name)

        if access_information is None:
            skipped.append({
                "table_name": table_name,
                "column_name": column_name,
                "reason": (
                    "Table was not found in the execution-plan analysis."
                )
            })
            continue

        estimated_rows = access_information["estimated_rows"]
        access_type = access_information["access_type"]

        if (
            estimated_rows is not None
            and estimated_rows < 1000
        ):
            skipped.append({
                "table_name": table_name,
                "column_name": column_name,
                "estimated_rows": estimated_rows,
                "reason": (
                    "The estimated table scan is small. "
                    "An additional index may not improve performance."
                )
            })
            continue

        if access_type == "ALL":
            recommendations.append({
                "table_name": table_name,
                "column_name": column_name,
                "suggested_index_name": (
                    f"idx_{table_name}_{column_name}"
                ),
                "index_type": "BTREE",
                "source": candidate["source"],
                "estimated_rows": estimated_rows,
                "reason": (
                    f"Column '{column_name}' is used in a "
                    f"{candidate['source']} condition, while "
                    f"MySQL uses a full table scan."
                ),
                "recommendation": (
                    "Evaluate a BTREE index on this column. "
                    "Test the execution plan and actual query "
                    "performance before creating the index."
                )
            })

    return {
        "recommendations_count": len(recommendations),
        "recommendations": recommendations,
        "skipped_candidates_count": len(skipped),
        "skipped_candidates": skipped,
        "automatic_index_creation": False
    }
