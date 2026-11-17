
import json
import logging

import mysql.connector

from app.optimizer.sql_validator import validate_read_only_query
from app.services.external_database_service import (
    open_external_database_connection,
    ExternalDatabaseConnectionError
)


logger = logging.getLogger(__name__)


class ExplainServiceError(Exception):
    """Raised when SQL execution-plan analysis fails."""


def get_query_execution_plan(connection_id, user_id, query):
    """
    Retrieve the MySQL JSON execution plan for a read-only SELECT query.

    This function uses EXPLAIN and does not execute the actual SELECT query.

    Args:
        connection_id: Saved database connection ID.
        user_id: Authenticated application user ID.
        query: SQL SELECT statement.

    Returns:
        Dictionary containing the parsed MySQL execution plan.

    Raises:
        ExplainServiceError: If validation or execution-plan retrieval fails.
    """

    # Step 1: Validate query input.
    if not isinstance(query, str) or not query.strip():
        raise ExplainServiceError(
            "A non-empty SQL query is required."
        )

    if len(query) > 10000:
        raise ExplainServiceError(
            "SQL query exceeds the maximum allowed length."
        )

    # Step 2: Enforce read-only SELECT validation.
    validation_result = validate_read_only_query(query)

    if not validation_result.is_valid:
        raise ExplainServiceError(
            validation_result.error
            or "Query failed read-only validation."
        )

    connection = None
    cursor = None

    try:
        # Step 3: Open the authenticated user's database connection.
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        # Step 4: Create cursor.
        cursor = connection.cursor()

        # Step 5: Request MySQL's JSON execution plan.
        explain_query = f"EXPLAIN FORMAT=JSON {query}"

        cursor.execute(explain_query)

        # Step 6: Retrieve execution-plan result.
        row = cursor.fetchone()

        if row is None or row[0] is None:
            raise ExplainServiceError(
                "MySQL returned an empty execution plan."
            )

        plan_json = row[0]

        # Step 7: Convert the JSON result into a Python dictionary.
        if isinstance(plan_json, bytes):
            plan_json = plan_json.decode("utf-8")

        if isinstance(plan_json, str):
            execution_plan = json.loads(plan_json)
        elif isinstance(plan_json, dict):
            execution_plan = plan_json
        else:
            raise ExplainServiceError(
                "MySQL returned an unsupported execution-plan format."
            )

        return {
            "format": "JSON",
            "database_engine": "MySQL",
            "execution_plan": execution_plan
        }

    except ExplainServiceError:
        raise

    except ExternalDatabaseConnectionError as error:
        raise ExplainServiceError(
            str(error)
        ) from error

    except (mysql.connector.Error, json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning(
            "Execution-plan analysis failed. "
            "Connection ID: %s, Error type: %s, Error code: %s",
            connection_id,
            type(error).__name__,
            getattr(error, "errno", None)
        )

        raise ExplainServiceError(
            "Unable to retrieve the MySQL execution plan. "
            "Check the SQL query and database permissions."
        ) from error

    except Exception as error:
        logger.exception(
            "Unexpected execution-plan analysis error. "
            "Connection ID: %s",
            connection_id
        )

        raise ExplainServiceError(
            "An unexpected error occurred during execution-plan analysis."
        ) from error

    finally:
        # Step 8: Always release database resources.
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception(
                    "Failed to close execution-plan cursor."
                )

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                logger.exception(
                    "Failed to close execution-plan database connection."
                )
