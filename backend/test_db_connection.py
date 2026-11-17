
from unittest.mock import MagicMock, patch

import pytest

from app.utils.database import get_db_connection
from app.services.database_service import check_database_connection


def test_connection():
    """Verify that QueryWise can connect to its actual MySQL database."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                DATABASE(),
                CURRENT_USER(),
                VERSION()
        """)

        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "querywise_db"

        print("\nDatabase connection successful!")
        print("Database:", result[0])
        print("Authenticated user:", result[1])
        print("MySQL version:", result[2])

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            if connection.is_connected():
                connection.close()


def test_database_health_check_success():
    """Verify that the health check returns database information."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (
        "querywise_db",
        "8.0.41",
        "querywise_app@127.0.0.1"
    )
    mock_connection.is_connected.return_value = True

    with patch(
        "app.services.database_service.get_db_connection",
        return_value=mock_connection
    ):
        result = check_database_connection()

    assert result["connected"] is True
    assert result["database"] == "querywise_db"
    assert result["mysql_version"] == "8.0.41"
    assert result["authenticated_user"] == "querywise_app@127.0.0.1"

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()


def test_database_health_check_query_failure():
    """Verify cleanup when a database query fails."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = RuntimeError(
        "Simulated database query failure"
    )
    mock_connection.is_connected.return_value = True

    with patch(
        "app.services.database_service.get_db_connection",
        return_value=mock_connection
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated database query failure"
        ):
            check_database_connection()

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()


def test_database_health_check_empty_result():
    """Verify that an empty query result is handled correctly."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_connection.is_connected.return_value = True

    with patch(
        "app.services.database_service.get_db_connection",
        return_value=mock_connection
    ):
        with pytest.raises(
            RuntimeError,
            match="Database health check returned no results"
        ):
            check_database_connection()

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()


def test_connection_closed_when_cursor_cleanup_fails():
    """Verify that connection cleanup is attempted even if cursor cleanup fails."""

    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (
        "querywise_db",
        "8.0.41",
        "querywise_app@127.0.0.1"
    )
    mock_connection.is_connected.return_value = True

    mock_cursor.close.side_effect = RuntimeError(
        "Simulated cursor cleanup failure"
    )

    with patch(
        "app.services.database_service.get_db_connection",
        return_value=mock_connection
    ):
        result = check_database_connection()

    assert result["connected"] is True

    mock_cursor.close.assert_called_once()
    mock_connection.close.assert_called_once()


if __name__ == "__main__":
    test_connection()
