
from app.utils.database import get_db_connection


def create_connection(
    user_id,
    connection_name,
    host,
    port,
    database_name,
    db_username,
    encrypted_password,
    use_ssl=False
):
    """Save an external database connection."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO database_connections (
                user_id,
                connection_name,
                host,
                port,
                database_name,
                db_username,
                encrypted_password,
                use_ssl
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                user_id,
                connection_name,
                host,
                port,
                database_name,
                db_username,
                encrypted_password,
                use_ssl
            )
        )

        connection.commit()

        return cursor.lastrowid

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()
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


def get_user_connections(user_id):
    """
    Retrieve connections belonging to a user.

    Encrypted passwords are deliberately excluded.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                connection_id,
                user_id,
                connection_name,
                host,
                port,
                database_name,
                db_username,
                use_ssl,
                created_at,
                updated_at
            FROM database_connections
            WHERE user_id = %s
            ORDER BY created_at DESC
        """

        cursor.execute(query, (user_id,))

        return cursor.fetchall()

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            if connection.is_connected():
                connection.close()


def get_connection_for_user(connection_id, user_id):
    """
    Retrieve a connection only if it belongs to the user.

    This internal function includes the encrypted password
    because the connection service needs it for decryption.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                connection_id,
                user_id,
                connection_name,
                host,
                port,
                database_name,
                db_username,
                encrypted_password,
                use_ssl,
                created_at,
                updated_at
            FROM database_connections
            WHERE connection_id = %s
              AND user_id = %s
            LIMIT 1
        """

        cursor.execute(
            query,
            (connection_id, user_id)
        )

        return cursor.fetchone()

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            if connection.is_connected():
                connection.close()


def delete_connection(connection_id, user_id):
    """
    Delete a connection only if it belongs to the user.

    Returns:
        bool: True if a connection was deleted, otherwise False.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            DELETE FROM database_connections
            WHERE connection_id = %s
              AND user_id = %s
        """

        cursor.execute(
            query,
            (connection_id, user_id)
        )

        deleted = cursor.rowcount > 0

        connection.commit()

        return deleted

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()
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
