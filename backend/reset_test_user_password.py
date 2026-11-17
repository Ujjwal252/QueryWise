
import bcrypt
from getpass import getpass

from app.utils.database import get_db_connection


def reset_password():
    new_password = getpass("Enter your new password: ")

    if len(new_password) < 8 or len(new_password.encode("utf-8")) > 72:
        print("Error: Password must be 8 to 72 UTF-8 bytes.")
        return

    confirm_password = getpass("Confirm your new password: ")

    if new_password != confirm_password:
        print("Error: Passwords do not match.")
        return

    password_hash = bcrypt.hashpw(
        new_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE user_id = %s
            """,
            (password_hash, 1)
        )

        if cursor.rowcount == 1:
            connection.commit()
            print("Password reset successfully for querywise_test!")
        else:
            connection.rollback()
            print("User not found. No password was changed.")

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()

        print("Password reset failed.")
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    reset_password()
