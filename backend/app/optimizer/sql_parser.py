
from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot.errors import ParseError


@dataclass
class SQLParseResult:
    """Structured result returned after parsing a SQL statement."""

    success: bool
    original_query: str
    normalized_query: Optional[str] = None
    statement_type: Optional[str] = None
    error: Optional[str] = None


# Only accept recognized SQL statement types.
SUPPORTED_STATEMENT_TYPES = {
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "CREATE",
    "ALTER",
    "DROP",
    "TRUNCATE",
    "SHOW",
    "DESCRIBE",
    "EXPLAIN",
    "USE",
    "SET",
    "GRANT",
    "REVOKE",
    "CALL",
    "MERGE",
}


def parse_sql(query: str) -> SQLParseResult:
    """
    Parse exactly one recognized SQL statement using MySQL syntax.

    This function only parses SQL. It never executes a query.
    Multiple statements are rejected.
    """

    if not isinstance(query, str):
        return SQLParseResult(
            success=False,
            original_query="",
            error="SQL query must be a string.",
        )

    original_query = query
    stripped_query = query.strip()

    if not stripped_query:
        return SQLParseResult(
            success=False,
            original_query=original_query,
            error="SQL query cannot be empty.",
        )

    try:
        statements = sqlglot.parse(
            stripped_query,
            read="mysql",
        )

        statements = [
            statement
            for statement in statements
            if statement is not None
        ]

        if not statements:
            return SQLParseResult(
                success=False,
                original_query=original_query,
                error="No valid SQL statement was found.",
            )

        if len(statements) > 1:
            return SQLParseResult(
                success=False,
                original_query=original_query,
                error="Multiple SQL statements are not allowed.",
            )

        parsed_statement = statements[0]
        statement_type = parsed_statement.key.upper()

        if statement_type not in SUPPORTED_STATEMENT_TYPES:
            return SQLParseResult(
                success=False,
                original_query=original_query,
                error="Input is not a recognized SQL statement.",
            )

        normalized_query = parsed_statement.sql(
            dialect="mysql"
        )

        return SQLParseResult(
            success=True,
            original_query=original_query,
            normalized_query=normalized_query,
            statement_type=statement_type,
        )

    except ParseError:
        return SQLParseResult(
            success=False,
            original_query=original_query,
            error="Invalid SQL syntax.",
        )

    except Exception:
        return SQLParseResult(
            success=False,
            original_query=original_query,
            error="An unexpected error occurred while parsing SQL.",
        )
