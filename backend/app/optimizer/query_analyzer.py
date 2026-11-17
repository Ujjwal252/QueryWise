
from dataclasses import dataclass, field
from typing import List, Optional

from sqlglot import exp, parse

from app.optimizer.sql_parser import parse_sql


@dataclass
class QueryFinding:
    """Represents one potential SQL optimization opportunity."""

    rule_id: str
    title: str
    severity: str
    description: str
    recommendation: str


@dataclass
class QueryAnalysisResult:
    """Structured result of SQL query analysis."""

    success: bool
    statement_type: Optional[str] = None
    findings: List[QueryFinding] = field(default_factory=list)
    error: Optional[str] = None


def analyze_query(query: str) -> QueryAnalysisResult:
    """
    Analyze SQL syntax and identify potentially inefficient patterns.

    This function does not execute SQL or modify databases.
    Findings are heuristic recommendations, not performance guarantees.
    """

    parse_result = parse_sql(query)

    if not parse_result.success:
        return QueryAnalysisResult(
            success=False,
            error=parse_result.error,
        )

    if parse_result.statement_type != "SELECT":
        return QueryAnalysisResult(
            success=False,
            statement_type=parse_result.statement_type,
            error="Query analysis currently supports SELECT statements only.",
        )

    statements = [
        statement
        for statement in parse(query, read="mysql")
        if statement is not None
    ]

    if len(statements) != 1:
        return QueryAnalysisResult(
            success=False,
            error="Exactly one SQL statement is required.",
        )

    statement = statements[0]
    findings = []

    # Rule QW001: SELECT *
    # Inspect projection expressions only. This avoids incorrectly
    # flagging COUNT(*) as SELECT *.
    for select in statement.find_all(exp.Select):
        has_projection_star = any(
            isinstance(expression, exp.Star)
            or (
                isinstance(expression, exp.Column)
                and isinstance(expression.this, exp.Star)
            )
            for expression in select.expressions
        )

        if has_projection_star:
            findings.append(
                QueryFinding(
                    rule_id="QW001",
                    title="SELECT * detected",
                    severity="medium",
                    description=(
                        "The query retrieves all columns from the selected "
                        "table or tables. This may transfer unnecessary data."
                    ),
                    recommendation=(
                        "Specify only the columns required by the application."
                    ),
                )
            )

    # Rule QW002: SELECT without WHERE clause.
    for select in statement.find_all(exp.Select):
        if select.args.get("where") is None and select.args.get("from_"):
            findings.append(
                QueryFinding(
                    rule_id="QW002",
                    title="SELECT without WHERE clause",
                    severity="medium",
                    description=(
                        "A SELECT statement reads rows without a filtering "
                        "condition. It may examine a large number of rows."
                    ),
                    recommendation=(
                        "Add an appropriate WHERE condition when the "
                        "application only needs a subset of the rows."
                    ),
                )
            )

    # Rule QW003: Leading wildcard in LIKE.
    for like_expression in statement.find_all(exp.Like):
        pattern = like_expression.expression

        if (
            isinstance(pattern, exp.Literal)
            and pattern.is_string
            and pattern.this.startswith("%")
        ):
            findings.append(
                QueryFinding(
                    rule_id="QW003",
                    title="Leading wildcard in LIKE",
                    severity="medium",
                    description=(
                        "The LIKE pattern starts with a wildcard. "
                        "A conventional B-tree index may not efficiently "
                        "support this search."
                    ),
                    recommendation=(
                        "Consider full-text indexing, a different search "
                        "strategy, or a prefix-search pattern if suitable."
                    ),
                )
            )

    # Rule QW004: OR conditions.
    for or_expression in statement.find_all(exp.Or):
        findings.append(
            QueryFinding(
                rule_id="QW004",
                title="OR condition detected",
                severity="low",
                description=(
                    "OR conditions can complicate index selection and "
                    "query execution depending on the involved columns."
                ),
                recommendation=(
                    "Review the execution plan. Compare alternative "
                    "query structures only when they preserve semantics."
                ),
            )
        )

    # Rule QW005: Functions applied to filtered columns.
    for select in statement.find_all(exp.Select):
        where_clause = select.args.get("where")

        if where_clause is None:
            continue

        for function in where_clause.find_all(exp.Func):
            if function.find(exp.Column) is not None:
                findings.append(
                    QueryFinding(
                        rule_id="QW005",
                        title="Function applied to a filtered column",
                        severity="medium",
                        description=(
                            "A function is applied to a column used in "
                            "the WHERE condition. This may prevent "
                            "efficient use of a conventional index."
                        ),
                        recommendation=(
                            "Consider rewriting the condition as a "
                            "range or direct comparison, or evaluate "
                            "a suitable functional index."
                        ),
                    )
                )
                break

    # Rule QW006: DISTINCT operation.
    if statement.find(exp.Distinct) is not None:
        findings.append(
            QueryFinding(
                rule_id="QW006",
                title="DISTINCT operation detected",
                severity="low",
                description=(
                    "DISTINCT removes duplicate rows and may require "
                    "additional sorting or temporary processing."
                ),
                recommendation=(
                    "Verify whether duplicate elimination is necessary. "
                    "Remove DISTINCT only when result semantics allow it."
                ),
            )
        )

    return QueryAnalysisResult(
        success=True,
        statement_type="SELECT",
        findings=findings,
    )
