
import logging

from app.utils.database import get_db_connection

logger = logging.getLogger(__name__)


def save_security_findings(user_id, connection_id, findings, query_id=None):
    """
    Save security findings in the QueryWise application database.

    Returns:
        int: Number of affected rows.
    """

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("Invalid user_id.")

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        raise ValueError("Invalid connection_id.")

    if not isinstance(findings, list):
        raise ValueError("findings must be a list.")

    if not findings:
        return 0

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO security_findings (
                user_id,
                connection_id,
                query_id,
                finding_type,
                severity,
                title,
                description,
                recommendation,
                affected_object
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        rows = [
            (
                user_id,
                connection_id,
                query_id,
                item["finding_type"],
                item["severity"],
                item["title"][:255],
                item["description"],
                item["recommendation"],
                item.get("affected_object")
            )
            for item in findings
        ]

        cursor.executemany(query, rows)

        connection.commit()

        return cursor.rowcount

    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                logger.exception(
                    "Security findings rollback failed."
                )

        logger.exception(
            "Failed to save security findings."
        )

        raise

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception(
                    "Failed to close security findings cursor."
                )

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                logger.exception(
                    "Failed to close security findings connection."
                )
