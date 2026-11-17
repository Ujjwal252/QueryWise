
import logging

from app.utils.database import get_db_connection


logger = logging.getLogger(__name__)


def log_audit_event(
    action,
    user_id=None,
    entity_type=None,
    entity_id=None,
    details=None,
    ip_address=None
):
    """
    Store an application security event in audit_logs.

    Returns:
        True if the event was recorded.
        False if audit logging failed.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO audit_logs (
                user_id,
                action,
                entity_type,
                entity_id,
                details,
                ip_address
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                user_id,
                action,
                entity_type,
                entity_id,
                details,
                ip_address
            )
        )

        connection.commit()
        return True

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()

        logger.exception("Failed to record audit event: %s", action)
        return False

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
