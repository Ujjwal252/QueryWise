
import ipaddress
import logging

from pathlib import Path

import mysql.connector

from flask import current_app

from app.services.connection_service import (
    get_database_connection_config
)

from app.security.host_validation import (
    validate_database_host,
    HostValidationError
)


logger = logging.getLogger(__name__)


class ExternalDatabaseConnectionError(Exception):
    """Raised when an external database connection fails."""


def _is_loopback_host(host):
    """Determine whether a host is a loopback address or localhost."""

    if host.strip().lower() == "localhost":
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def open_external_database_connection(connection_id, user_id):
    """
    Open an external MySQL connection belonging to an authenticated user.

    The caller is responsible for closing the returned connection.
    """

    # Step 1: Retrieve the connection belonging to this user.
    saved_config = get_database_connection_config(
        connection_id=connection_id,
        user_id=user_id
    )

    if saved_config is None:
        raise ExternalDatabaseConnectionError(
            "Database connection not found."
        )

    # Step 2: Extract saved configuration.
    host = saved_config["host"]
    port = saved_config["port"]
    database_name = saved_config["database_name"]
    db_username = saved_config["db_username"]
    password = saved_config["password"]
    ssl_value = saved_config["use_ssl"]

    # Step 3: Validate SSL setting.
    if ssl_value not in (True, False, 0, 1):
        raise ExternalDatabaseConnectionError(
            "Invalid SSL configuration."
        )

    use_ssl = bool(ssl_value)

    if not isinstance(password, str) or not password:
        raise ExternalDatabaseConnectionError(
            "Database password is missing or invalid."
        )

    # Step 4: Validate destination host.
    allow_local_hosts = current_app.config.get(
        "ALLOW_LOCAL_DATABASE_HOSTS",
        False
    )

    try:
        validated_host = validate_database_host(
            host,
            allow_localhost=allow_local_hosts
        )

    except HostValidationError as error:
        raise ExternalDatabaseConnectionError(
            str(error)
        ) from error

    # Step 5: Validate port.
    if (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ExternalDatabaseConnectionError(
            "Invalid database port."
        )

    # Step 6: Validate database details.
    if not database_name or not db_username:
        raise ExternalDatabaseConnectionError(
            "Database name and username are required."
        )

    # Step 7: Require SSL for remote database connections.
    is_local_host = _is_loopback_host(validated_host)

    if not is_local_host and not use_ssl:
        raise ExternalDatabaseConnectionError(
            "SSL must be enabled for remote database connections."
        )

    # Step 8: Prepare MySQL connection options.
    connection_options = {
        "host": validated_host,
        "port": port,
        "database": database_name,
        "user": db_username,
        "password": password,
        "connection_timeout": 5,
        "charset": "utf8mb4",
        "use_unicode": True,
        "autocommit": False
    }

    if use_ssl:
        # CA verification is mandatory for SSL connections.
        ca_path = current_app.config.get("MYSQL_SSL_CA")

        if not ca_path:
            raise ExternalDatabaseConnectionError(
                "MySQL CA certificate path is not configured."
            )

        ca_path = Path(ca_path)

        if not ca_path.is_file():
            raise ExternalDatabaseConnectionError(
                "MySQL CA certificate file was not found."
            )

        # Remote connections must verify the server hostname.
        verify_identity = current_app.config.get(
            "MYSQL_SSL_VERIFY_IDENTITY",
            True
        )

        if not is_local_host and not verify_identity:
            raise ExternalDatabaseConnectionError(
                "Hostname verification is required for remote databases."
            )

        connection_options.update({
            "ssl_disabled": False,
            "ssl_ca": str(ca_path),
            "ssl_verify_cert": True,
            "ssl_verify_identity": verify_identity
        })

    else:
        connection_options["ssl_disabled"] = True

    # Step 9: Establish the external MySQL connection.
    try:
        connection = mysql.connector.connect(
            **connection_options
        )

        return connection

    except mysql.connector.Error as error:
        logger.warning(
            "External MySQL connection failed. "
            "Connection ID: %s, Error type: %s, "
            "Error code: %s, SQLSTATE: %s",
            connection_id,
            type(error).__name__,
            getattr(error, "errno", None),
            getattr(error, "sqlstate", None)
        )

        raise ExternalDatabaseConnectionError(
            "Unable to connect to the external MySQL database. "
            "Check the connection settings, TLS certificate, "
            "and database availability."
        ) from error


def check_external_database_connection(connection_id, user_id):
    """
    Test a saved external database connection.

    Returns safe connection information without exposing credentials.
    """

    connection = None
    cursor = None

    try:
        # Step 1: Open the external database connection.
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        # Step 2: Create cursor.
        cursor = connection.cursor()

        # Step 3: Execute safe verification query.
        cursor.execute("""
            SELECT
                DATABASE(),
                VERSION(),
                CURRENT_USER()
        """)

        # Step 4: Retrieve result.
        result = cursor.fetchone()

        if result is None:
            raise ExternalDatabaseConnectionError(
                "External database returned no connection information."
            )

        # Step 5: Return safe connection information.
        return {
            "connected": True,
            "database": result[0],
            "mysql_version": result[1],
            "authenticated_user": result[2]
        }

    except ExternalDatabaseConnectionError:
        raise

    except mysql.connector.Error as error:
        logger.warning(
            "External database test failed. "
            "Error type: %s, Error code: %s, SQLSTATE: %s",
            type(error).__name__,
            getattr(error, "errno", None),
            getattr(error, "sqlstate", None)
        )

        raise ExternalDatabaseConnectionError(
            "External database test failed."
        ) from error

    finally:
        # Step 6: Always clean up resources.
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception(
                    "Failed to close external database cursor."
                )

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                logger.exception(
                    "Failed to close external database connection."
                )
