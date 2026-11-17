
import re
from dataclasses import dataclass
from typing import Optional

from sqlglot import exp, parse

from app.optimizer.sql_parser import parse_sql


@dataclass
class SQLValidationResult:
    """Structured result returned after SQL security validation."""

    is_valid: bool
    statement_type: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


ALLOWED_STATEMENT_TYPES = {"SELECT"}

# Conservative allowlist of reviewed SQL functions.
SAFE_FUNCTION_NAMES = {
    # String functions
    "UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM",
    "CONCAT", "CONCAT_WS", "LENGTH", "CHAR_LENGTH",
    "SUBSTRING", "LEFT", "RIGHT", "REPLACE",

    # Aggregate functions
    "COUNT", "SUM", "AVG", "MIN", "MAX",

    # Numeric functions
    "ABS", "ROUND", "CEIL", "CEILING", "FLOOR",
    "MOD", "POWER", "SQRT",

    # Conditional and NULL functions
    "COALESCE", "IFNULL", "NULLIF",

    # Date extraction functions
    "YEAR", "MONTH", "DAY", "HOUR",
    "MINUTE", "SECOND", "DATE",
}

# Logical operators are not function calls.
LOGICAL_OPERATORS = (
    exp.And,
    exp.Or,
    exp.Not,
)

UNSAFE_INTO_PATTERN = re.compile(
    r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b",
    re.IGNORECASE,
)


def validate_read_only_query(query: str) -> SQLValidationResult:
    """
    Validate whether a SQL query meets QueryWise's initial
    read-only statement policy.

    Passing validation does not guarantee that a query is
    completely harmless. Database privileges and execution
    safeguards are still required.
    """

    if not isinstance(query, str):
        return SQLValidationResult(
            is_valid=False,
            error="SQL query must be a string.",
            message="Invalid input.",
        )

    if not query.strip():
        return SQLValidationResult(
            is_valid=False,
            error="SQL query cannot be empty.",
            message="Invalid input.",
        )

    # Reject file-writing SELECT clauses before parsing.
    if UNSAFE_INTO_PATTERN.search(query):
        return SQLValidationResult(
            is_valid=False,
            statement_type="SELECT",
            error="SELECT INTO OUTFILE and DUMPFILE are not allowed.",
            message="Potentially modifying SELECT construct detected.",
        )

    # Parse and classify the SQL statement.
    parse_result = parse_sql(query)

    if not parse_result.success:
        return SQLValidationResult(
            is_valid=False,
            error=parse_result.error,
            message="SQL parsing failed.",
        )

    statement_type = parse_result.statement_type

    if statement_type not in ALLOWED_STATEMENT_TYPES:
        return SQLValidationResult(
            is_valid=False,
            statement_type=statement_type,
            error="Only SELECT statements are allowed.",
            message="Read-only policy violation.",
        )

    statements = [
        statement
        for statement in parse(query, read="mysql")
        if statement is not None
    ]

    if len(statements) != 1:
        return SQLValidationResult(
            is_valid=False,
            statement_type=statement_type,
            error="Exactly one SQL statement is required.",
            message="Statement validation failed.",
        )

    statement = statements[0]

    # Reject SELECT INTO constructs.
    if statement.find(exp.Into) is not None:
        return SQLValidationResult(
            is_valid=False,
            statement_type=statement_type,
            error="SELECT INTO statements are not allowed.",
            message="Potentially modifying SELECT construct detected.",
        )

    # Reject locking clauses.
    if statement.args.get("locks"):
        return SQLValidationResult(
            is_valid=False,
            statement_type=statement_type,
            error="SELECT queries with locking clauses are not allowed.",
            message="Locking query detected.",
        )

    # Inspect SQL functions while excluding logical operators.
    for function in statement.find_all(exp.Func):

        if isinstance(function, LOGICAL_OPERATORS):
            continue

        function_name = function.sql_name().upper()

        # Reject anonymous and unverified function calls.
        if isinstance(function, exp.Anonymous):
            return SQLValidationResult(
                is_valid=False,
                statement_type=statement_type,
                error="Unverified function calls are not allowed.",
                message="Potentially unsafe function detected.",
            )

        if function_name not in SAFE_FUNCTION_NAMES:
            return SQLValidationResult(
                is_valid=False,
                statement_type=statement_type,
                error=f"Function '{function_name}' is not allowed.",
                message="Function is not in the approved allowlist.",
            )

    return SQLValidationResult(
        is_valid=True,
        statement_type=statement_type,
        message="Query passed the read-only statement checks.",
    )
