
import logging

from app.utils.database import get_db_connection


logger = logging.getLogger(__name__)


def check_database_connection():
    """
    Check whether QueryWise can communicate with MySQL.

    Returns:
        dict: Database connection information.

    Raises:
        Exception: If the database check fails.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                DATABASE(),
                VERSION(),
                CURRENT_USER()
        """)

        result = cursor.fetchone()

        if result is None:
            raise RuntimeError(
                "Database health check returned no results."
            )

        return {
            "connected": True,
            "database": result[0],
            "mysql_version": result[1],
            "authenticated_user": result[2]
        }

    except Exception:
        logger.exception("Database health check failed.")
        raise

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception("Failed to close database cursor.")

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                logger.exception("Failed to close database connection.")
