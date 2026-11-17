
from app.models.connection_model import (
    create_connection,
    get_user_connections,
    get_connection_for_user,
    delete_connection
)

from app.security.encryption import (
    encrypt_password,
    decrypt_password
)


def save_database_connection(
    user_id,
    connection_name,
    host,
    port,
    database_name,
    db_username,
    password,
    use_ssl=False
):
    """
    Encrypt the database password and save the connection.
    """

    encrypted_password = encrypt_password(password)

    connection_id = create_connection(
        user_id=user_id,
        connection_name=connection_name,
        host=host,
        port=port,
        database_name=database_name,
        db_username=db_username,
        encrypted_password=encrypted_password,
        use_ssl=use_ssl
    )

    return connection_id


def list_database_connections(user_id):
    """
    Return saved connections belonging to a user.

    Passwords are excluded from the returned data.
    """

    return get_user_connections(user_id)


def get_database_connection_config(connection_id, user_id):
    """
    Retrieve and decrypt credentials after checking ownership.

    Returns:
        dict: Connection configuration with decrypted password.

    Returns None if the connection does not belong to the user.
    """

    saved_connection = get_connection_for_user(
        connection_id=connection_id,
        user_id=user_id
    )

    if saved_connection is None:
        return None

    encrypted_password = saved_connection.pop(
        "encrypted_password"
    )

    saved_connection["password"] = decrypt_password(
        encrypted_password
    )

    return saved_connection


def remove_database_connection(connection_id, user_id):
    """
    Delete a saved connection belonging to the user.
    """

    return delete_connection(
        connection_id=connection_id,
        user_id=user_id
    )
