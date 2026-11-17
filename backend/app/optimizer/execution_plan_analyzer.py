
from typing import Any, Dict, List, Optional


def _to_number(value):
    """Convert a MySQL plan value into a number when possible."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_table_operations(
    node: Any,
    tables: List[Dict[str, Any]]
):
    """
    Recursively find table operations in a MySQL JSON execution plan.
    """

    if isinstance(node, list):
        for item in node:
            _collect_table_operations(item, tables)

        return

    if not isinstance(node, dict):
        return

    if "table_name" in node:
        cost_info = node.get("cost_info") or {}

        table_info = {
            "table_name": node.get("table_name"),
            "access_type": node.get("access_type"),
            "possible_keys": node.get("possible_keys") or [],
            "selected_key": node.get("key"),
            "rows_examined_per_scan": _to_number(
                node.get("rows_examined_per_scan")
            ),
            "rows_produced_per_join": _to_number(
                node.get("rows_produced_per_join")
            ),
            "filtered_percentage": _to_number(
                node.get("filtered")
            ),
            "read_cost": _to_number(
                cost_info.get("read_cost")
            ),
            "evaluation_cost": _to_number(
                cost_info.get("eval_cost")
            ),
            "prefix_cost": _to_number(
                cost_info.get("prefix_cost")
            ),
            "attached_condition": node.get("attached_condition")
        }

        tables.append(table_info)

    for value in node.values():
        if isinstance(value, (dict, list)):
            _collect_table_operations(value, tables)


def _collect_query_costs(
    node: Any,
    costs: List[float]
):
    """Collect query cost values from query blocks."""

    if isinstance(node, list):
        for item in node:
            _collect_query_costs(item, costs)

        return

    if not isinstance(node, dict):
        return

    cost_info = node.get("cost_info")

    if isinstance(cost_info, dict):
        query_cost = _to_number(
            cost_info.get("query_cost")
        )

        if query_cost is not None:
            costs.append(query_cost)

    for value in node.values():
        if isinstance(value, (dict, list)):
            _collect_query_costs(value, costs)


def _generate_findings(
    tables: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Generate cautious findings from table access information."""

    findings = []

    for table in tables:
        table_name = table["table_name"]
        access_type = table["access_type"]
        estimated_rows = table["rows_examined_per_scan"]
        selected_key = table["selected_key"]
        possible_keys = table["possible_keys"]

        # Full table scan detection.
        if access_type == "ALL":

            if estimated_rows is not None and estimated_rows >= 1000:
                severity = "medium"
                title = "Large table full scan detected"

                description = (
                    f"MySQL estimates examining approximately "
                    f"{estimated_rows:g} rows in table "
                    f"'{table_name}' using a full table scan."
                )

                recommendation = (
                    "Review the filtering conditions and table size. "
                    "Consider evaluating an appropriate index and "
                    "comparing execution performance before applying it."
                )

            else:
                severity = "info"
                title = "Full table scan detected"

                description = (
                    f"MySQL uses a full table scan for table "
                    f"'{table_name}'."
                )

                recommendation = (
                    "A full table scan may be reasonable for small tables. "
                    "Evaluate indexing only if table size and measured "
                    "query performance justify it."
                )

            findings.append({
                "rule_id": "EP001",
                "severity": severity,
                "title": title,
                "description": description,
                "recommendation": recommendation
            })

        # Index availability information.
        if selected_key:
            findings.append({
                "rule_id": "EP002",
                "severity": "info",
                "title": "Index selected",
                "description": (
                    f"MySQL selected index '{selected_key}' "
                    f"for table '{table_name}'."
                ),
                "recommendation": (
                    "Review the selected index and compare actual "
                    "execution performance when evaluating alternatives."
                )
            })

        elif possible_keys:
            findings.append({
                "rule_id": "EP003",
                "severity": "info",
                "title": "Possible indexes not selected",
                "description": (
                    f"MySQL identified possible indexes for "
                    f"'{table_name}', but did not select one."
                ),
                "recommendation": (
                    "Review the execution plan and table statistics. "
                    "MySQL may reasonably prefer another access method."
                )
            })

    return findings


def analyze_execution_plan(
    execution_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze a MySQL JSON execution plan.

    Args:
        execution_plan: Parsed MySQL EXPLAIN FORMAT=JSON result.

    Returns:
        Structured execution-plan analysis containing:
            - table access information
            - estimated query cost
            - estimated rows
            - index information
            - performance findings

    This function does not execute SQL or modify the database.
    """

    if not isinstance(execution_plan, dict):
        raise ValueError(
            "Execution plan must be a dictionary."
        )

    if not execution_plan:
        raise ValueError(
            "Execution plan cannot be empty."
        )

    query_block = execution_plan.get("query_block")

    if not isinstance(query_block, dict):
        raise ValueError(
            "Invalid MySQL execution plan: query_block is missing."
        )

    # Collect table operations.
    tables = []

    _collect_table_operations(
        execution_plan,
        tables
    )

    # Collect estimated query costs.
    query_costs = []

    _collect_query_costs(
        execution_plan,
        query_costs
    )

    # Generate findings.
    findings = _generate_findings(tables)

    total_estimated_rows = sum(
        table["rows_examined_per_scan"]
        for table in tables
        if table["rows_examined_per_scan"] is not None
    )

    return {
        "database_engine": "MySQL",
        "plan_format": "JSON",
        "summary": {
            "tables_accessed": len(tables),
            "estimated_rows_examined": total_estimated_rows,
            "estimated_query_cost": (
                query_costs[0]
                if query_costs
                else None
            ),
            "findings_count": len(findings)
        },
        "tables": tables,
        "findings": findings
    }
