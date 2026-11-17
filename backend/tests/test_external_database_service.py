
from pathlib import Path
from unittest.mock import MagicMock, patch

import mysql.connector
import pytest

from flask import Flask

from app.services.external_database_service import (
    open_external_database_connection,
    check_external_database_connection,
    ExternalDatabaseConnectionError
)


@pytest.fixture
def app():
    """Provide Flask application context for service tests."""

    backend_dir = Path(__file__).resolve().parents[1]
    ca_certificate = backend_dir / "certs" / "mysql-ca.pem"

    test_app = Flask(__name__)

    test_app.config.update(
        ALLOW_LOCAL_DATABASE_HOSTS=True,
        MYSQL_SSL_CA=ca_certificate,
        MYSQL_SSL_VERIFY_IDENTITY=True
    )

    return test_app


@pytest.fixture
def saved_connection():
    """Provide sample credentials for an authorized connection."""

    return {
        "connection_id": 10,
        "user_id": 1,
        "connection_name": "Local Test Database",
        "host": "127.0.0.1",
        "port": 3306,
        "database_name": "sample_db",
        "db_username": "sample_user",
        "password": "SamplePassword123!",
        "use_ssl": False
    }


def test_connection_not_found_or_not_owned(app):
    """Reject a connection that does not belong to the user."""

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=None
        ), patch(
            "app.services.external_database_service.mysql.connector.connect"
        ) as mock_connect:

            with pytest.raises(
                ExternalDatabaseConnectionError,
                match="Database connection not found"
            ):
                open_external_database_connection(10, 2)

            mock_connect.assert_not_called()


def test_invalid_host_rejected(app, saved_connection):
    """Reject unsafe database destinations."""

    saved_connection["host"] = "192.168.1.10"

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect"
        ) as mock_connect:

            with pytest.raises(ExternalDatabaseConnectionError):
                open_external_database_connection(10, 1)

            mock_connect.assert_not_called()


@pytest.mark.parametrize(
    "invalid_port",
    [0, -1, 65536, "3306", True]
)
def test_invalid_port_rejected(app, saved_connection, invalid_port):
    """Reject invalid database ports."""

    saved_connection["port"] = invalid_port

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect"
        ) as mock_connect:

            with pytest.raises(
                ExternalDatabaseConnectionError,
                match="Invalid database port"
            ):
                open_external_database_connection(10, 1)

            mock_connect.assert_not_called()


def test_remote_connection_requires_ssl(app, saved_connection):
    """Reject remote connections when SSL is disabled."""

    saved_connection["host"] = "8.8.8.8"
    saved_connection["use_ssl"] = False

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect"
        ) as mock_connect:

            with pytest.raises(
                ExternalDatabaseConnectionError,
                match="SSL must be enabled"
            ):
                open_external_database_connection(10, 1)

            mock_connect.assert_not_called()


def test_successful_local_database_connection(app, saved_connection):
    """Verify that a valid local connection is opened."""

    mock_connection = MagicMock()

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect",
            return_value=mock_connection
        ) as mock_connect:

            result = open_external_database_connection(10, 1)

    assert result is mock_connection

    options = mock_connect.call_args.kwargs

    assert options["host"] == "127.0.0.1"
    assert options["port"] == 3306
    assert options["database"] == "sample_db"
    assert options["user"] == "sample_user"
    assert options["password"] == "SamplePassword123!"
    assert options["ssl_disabled"] is True


def test_remote_connection_uses_verified_ssl(app, saved_connection):
    """Verify certificate and hostname checks for remote connections."""

    saved_connection.update({
        "host": "8.8.8.8",
        "use_ssl": True
    })

    mock_connection = MagicMock()

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect",
            return_value=mock_connection
        ) as mock_connect:

            open_external_database_connection(10, 1)

    options = mock_connect.call_args.kwargs

    expected_ca = (
        Path(__file__).resolve().parents[1]
        / "certs"
        / "mysql-ca.pem"
    )

    assert options["ssl_disabled"] is False
    assert options["ssl_ca"] == str(expected_ca)
    assert options["ssl_verify_cert"] is True
    assert options["ssl_verify_identity"] is True


def test_mysql_connection_failure_is_handled(app, saved_connection):
    """Verify that MySQL connection errors are safely reported."""

    with app.app_context():
        with patch(
            "app.services.external_database_service.get_database_connection_config",
            return_value=saved_connection
        ), patch(
            "app.services.external_database_service.mysql.connector.connect",
            side_effect=mysql.connector.Error("Simulated connection failure")
        ):

            with pytest.raises(
                ExternalDatabaseConnectionError,
                match="Unable to connect to the external MySQL database"
            ):
                open_external_database_connection(10, 1)


def test_external_connection_test_success(app):
    """Verify successful connection testing and resource cleanup."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True

    mock_cursor.fetchone.return_value = (
        "sample_db",
        "8.0.41",
        "sample_user@localhost"
    )

    with app.app_context():
        with patch(
            "app.services.external_database_service.open_external_database_connection",
            return_value=mock_connection
        ):

            result = check_external_database_connection(10, 1)

    assert result["connected"] is True
    assert result["database"] == "sample_db"
    assert result["mysql_version"] == "8.0.41"
    assert result["authenticated_user"] == "sample_user@localhost"

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()


def test_external_connection_test_cleanup_after_query_failure(app):
    """Verify resources are closed when the test query fails."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True

    mock_cursor.execute.side_effect = mysql.connector.Error(
        "Simulated query failure"
    )

    with app.app_context():
        with patch(
            "app.services.external_database_service.open_external_database_connection",
            return_value=mock_connection
        ):

            with pytest.raises(ExternalDatabaseConnectionError):
                check_external_database_connection(10, 1)

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()
