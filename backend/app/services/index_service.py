
from typing import Any, Dict, List

import mysql.connector
from sqlglot import exp, parse_one

from app.optimizer.index_recommender import recommend_indexes
from app.services.external_database_service import (
    open_external_database_connection
)


class IndexServiceError(Exception):
    """Raised when index metadata cannot be retrieved."""


def get_existing_indexes(
    connection_id: int,
    user_id: int,
    table_name: str
) -> List[Dict[str, Any]]:
    """
    Retrieve index metadata for a table in the user's MySQL database.

    This function only reads metadata. It never creates, modifies,
    or deletes indexes.
    """

    if not isinstance(connection_id, int) or connection_id <= 0:
        raise ValueError("A valid connection ID is required.")

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("A valid user ID is required.")

    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("A valid table name is required.")

    table_name = table_name.strip()

    if len(table_name) > 64:
        raise ValueError("Table name cannot exceed 64 characters.")

    connection = None
    cursor = None

    try:
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        cursor = connection.cursor(dictionary=True)

        metadata_query = """
            SELECT
                TABLE_NAME AS table_name,
                COLUMN_NAME AS column_name,
                INDEX_NAME AS index_name,
                SEQ_IN_INDEX AS sequence_in_index,
                NON_UNIQUE AS non_unique,
                INDEX_TYPE AS index_type
            FROM information_schema.statistics
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """

        cursor.execute(metadata_query, (table_name,))
        rows = cursor.fetchall()

        return [
            {
                "table_name": row["table_name"],
                "column_name": row["column_name"],
                "index_name": row["index_name"],
                "sequence_in_index": row["sequence_in_index"],
                "non_unique": row["non_unique"],
                "index_type": row["index_type"]
            }
            for row in rows
        ]

    except mysql.connector.Error as exc:
        raise IndexServiceError(
            "Unable to retrieve index metadata from the connected database."
        ) from exc

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()


def get_index_recommendations(
    connection_id: int,
    user_id: int,
    query: str,
    execution_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Retrieve actual index metadata and generate recommendations.

    Index recommendations are advisory only. No database indexes
    are created or modified.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty SQL query is required.")

    if not isinstance(execution_analysis, dict):
        raise ValueError("Execution analysis must be a dictionary.")

    if execution_analysis.get("database_engine") != "MySQL":
        raise ValueError("Only MySQL execution plans are supported.")

    try:
        statement = parse_one(query, read="mysql")
    except Exception as exc:
        raise ValueError("The SQL query could not be parsed.") from exc

    if not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT statements are supported.")

    table_names = set()

    for table in statement.find_all(exp.Table):
        if table.name:
            table_names.add(table.name)

    if not table_names:
        raise ValueError("No database tables were found in the query.")

    existing_indexes = []

    for table_name in sorted(table_names):
        existing_indexes.extend(
            get_existing_indexes(
                connection_id=connection_id,
                user_id=user_id,
                table_name=table_name
            )
        )

    recommendations = recommend_indexes(
        query=query,
        execution_analysis=execution_analysis,
        existing_indexes=existing_indexes
    )

    return {
        "connection_id": connection_id,
        "tables_checked": sorted(table_names),
        "existing_indexes_count": len(existing_indexes),
        "existing_indexes": existing_indexes,
        "recommendations": recommendations
    }
