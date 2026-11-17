
import logging

from app.utils.database import get_db_connection


logger = logging.getLogger(__name__)

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

VALID_STATUSES = {"pending", "success", "failed"}


def save_query_history(
    user_id,
    connection_id,
    query,
    query_type,
    execution_time_ms=None,
    rows_returned=None,
    execution_status="success",
    error_message=None
):
    """
    Save an executed query to query_history.

    Returns:
        int: ID of the newly created history record.
    """

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("A valid user ID is required.")

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        raise ValueError("A valid connection ID is required.")

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty SQL query is required.")

    if not isinstance(query_type, str) or not query_type.strip():
        raise ValueError("A valid query type is required.")

    if execution_status not in VALID_STATUSES:
        raise ValueError("Invalid execution status.")

    if execution_time_ms is not None and execution_time_ms < 0:
        raise ValueError("Execution time cannot be negative.")

    if rows_returned is not None:
        if (
            isinstance(rows_returned, bool)
            or not isinstance(rows_returned, int)
            or rows_returned < 0
        ):
            raise ValueError("rows_returned must be a non-negative integer.")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO query_history (
                user_id,
                connection_id,
                original_query,
                query_type,
                execution_time_ms,
                rows_returned,
                execution_status,
                error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            insert_query,
            (
                user_id,
                connection_id,
                query.strip(),
                query_type.strip().upper(),
                execution_time_ms,
                rows_returned,
                execution_status,
                error_message
            )
        )

        connection.commit()

        return cursor.lastrowid

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()

        logger.exception("Failed to save query history.")
        raise

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                pass


def get_user_query_history(
    user_id,
    page=DEFAULT_PAGE,
    per_page=DEFAULT_PER_PAGE,
    query_type=None,
    execution_status=None
):
    """
    Retrieve query history belonging to a specific user.

    Supports pagination and optional filters.
    """

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("A valid user ID is required.")

    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page < 1
    ):
        raise ValueError("Page must be a positive integer.")

    if (
        isinstance(per_page, bool)
        or not isinstance(per_page, int)
        or not 1 <= per_page <= MAX_PER_PAGE
    ):
        raise ValueError(
            f"per_page must be between 1 and {MAX_PER_PAGE}."
        )

    if query_type is not None:
        if not isinstance(query_type, str) or not query_type.strip():
            raise ValueError("Invalid query type filter.")

        query_type = query_type.strip().upper()

    if execution_status is not None:
        if (
            not isinstance(execution_status, str)
            or not execution_status.strip()
        ):
            raise ValueError("Invalid execution status filter.")

        execution_status = execution_status.strip().lower()

        if execution_status not in VALID_STATUSES:
            raise ValueError("Invalid execution status filter.")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        conditions = ["qh.user_id = %s"]
        parameters = [user_id]

        if query_type:
            conditions.append("qh.query_type = %s")
            parameters.append(query_type)

        if execution_status:
            conditions.append("qh.execution_status = %s")
            parameters.append(execution_status)

        where_clause = " AND ".join(conditions)

        count_query = f"""
            SELECT COUNT(*) AS total
            FROM query_history qh
            WHERE {where_clause}
        """

        cursor.execute(count_query, tuple(parameters))

        count_result = cursor.fetchone()
        total_records = count_result["total"]

        offset = (page - 1) * per_page

        history_query = f"""
            SELECT
                qh.query_id,
                qh.connection_id,
                dc.connection_name,
                qh.original_query,
                qh.query_type,
                qh.execution_time_ms,
                qh.rows_returned,
                qh.execution_status,
                qh.error_message,
                qh.created_at
            FROM query_history qh
            LEFT JOIN database_connections dc
                ON qh.connection_id = dc.connection_id
                AND dc.user_id = qh.user_id
            WHERE {where_clause}
            ORDER BY qh.created_at DESC, qh.query_id DESC
            LIMIT %s OFFSET %s
        """

        cursor.execute(
            history_query,
            tuple(parameters) + (per_page, offset)
        )

        records = cursor.fetchall()

        total_pages = (
            (total_records + per_page - 1) // per_page
        )

        return {
            "records": records,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_records": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }

    except Exception:
        logger.exception(
            "Failed to retrieve query history for user_id=%s",
            user_id
        )
        raise

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                pass
