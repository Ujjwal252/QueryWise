
import bcrypt
from mysql.connector.errors import IntegrityError

from app.utils.database import get_db_connection


def create_user(username, email, password, full_name=None):
    """Create a user with a securely hashed password."""

    connection = None
    cursor = None

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password exceeds bcrypt's 72-byte limit.")

    password_hash = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    ).decode("utf-8")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO users (
                username,
                email,
                password_hash,
                full_name
            )
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (username, email, password_hash, full_name)
        )

        connection.commit()
        return cursor.lastrowid

    except IntegrityError as error:
        if connection and connection.is_connected():
            connection.rollback()

        if error.errno == 1062:
            return None

        raise

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def authenticate_user(identifier, password):
    """
    Authenticate using username or email and password.

    Returns a user dictionary if authentication succeeds,
    otherwise returns None.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                user_id,
                username,
                email,
                password_hash,
                full_name,
                role,
                is_active
            FROM users
            WHERE username = %s OR email = %s
            LIMIT 1
        """

        cursor.execute(query, (identifier, identifier))
        user = cursor.fetchone()

        if not user:
            return None

        if not user["is_active"]:
            return None

        password_matches = bcrypt.checkpw(
            password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
        )

        if not password_matches:
            return None

        user.pop("password_hash", None)
        user.pop("is_active", None)

        return user

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def get_user_by_id(user_id):
    """Retrieve a user's safe profile information."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                user_id,
                username,
                email,
                full_name,
                role
            FROM users
            WHERE user_id = %s
              AND is_active = TRUE
        """

        cursor.execute(query, (user_id,))
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
