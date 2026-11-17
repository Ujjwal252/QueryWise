
from unittest.mock import patch

from app.services.external_database_service import (
    ExternalDatabaseConnectionError
)


def authenticate(client, user_id=1):
    """Create an authenticated test session."""

    with client.session_transaction() as session:
        session["user_id"] = user_id


def csrf_headers(client):
    """Get a CSRF token for unsafe HTTP requests."""

    response = client.get("/api/csrf/token")
    token = response.get_json()["csrf_token"]

    return {"X-CSRFToken": token}


def valid_connection_data():
    """Return valid database connection input."""

    return {
        "connection_name": "My Test Database",
        "host": "127.0.0.1",
        "port": 3306,
        "database_name": "sample_db",
        "db_username": "sample_user",
        "password": "SamplePassword123!",
        "use_ssl": False
    }


def test_create_connection_success(client):
    authenticate(client)

    with patch(
        "app.routes.connection_routes.save_database_connection",
        return_value=10
    ) as mock_save:

        response = client.post(
            "/api/connections",
            json=valid_connection_data(),
            headers=csrf_headers(client)
        )

    assert response.status_code == 201
    assert response.get_json()["status"] == "success"
    assert response.get_json()["connection_id"] == 10

    mock_save.assert_called_once()


def test_create_connection_requires_authentication(client):
    response = client.post(
        "/api/connections",
        json=valid_connection_data(),
        headers=csrf_headers(client)
    )

    assert response.status_code == 401


def test_create_connection_rejects_invalid_port(client):
    authenticate(client)

    data = valid_connection_data()
    data["port"] = True

    response = client.post(
        "/api/connections",
        json=data,
        headers=csrf_headers(client)
    )

    assert response.status_code == 400
    assert "Port must be an integer" in response.get_json()["message"]


def test_create_connection_rejects_missing_fields(client):
    authenticate(client)

    data = valid_connection_data()
    del data["password"]

    response = client.post(
        "/api/connections",
        json=data,
        headers=csrf_headers(client)
    )

    assert response.status_code == 400
    assert "password is required" in response.get_json()["message"]


def test_list_connections_success(client):
    authenticate(client)

    sample_connections = [
        {
            "connection_id": 10,
            "connection_name": "My Test Database",
            "host": "127.0.0.1",
            "port": 3306,
            "database_name": "sample_db",
            "db_username": "sample_user",
            "use_ssl": 0
        }
    ]

    with patch(
        "app.routes.connection_routes.list_database_connections",
        return_value=sample_connections
    ) as mock_list:

        response = client.get("/api/connections")

    assert response.status_code == 200
    assert response.get_json()["connections"] == sample_connections

    mock_list.assert_called_once_with(1)


def test_list_connections_requires_authentication(client):
    response = client.get("/api/connections")

    assert response.status_code == 401


def test_test_connection_success(client):
    authenticate(client)

    sample_result = {
        "connected": True,
        "database": "sample_db",
        "mysql_version": "8.0.41",
        "authenticated_user": "sample_user@localhost"
    }

    with patch(
        "app.routes.connection_routes.check_external_database_connection",
        return_value=sample_result
    ) as mock_test:

        response = client.post(
            "/api/connections/10/test",
            headers=csrf_headers(client)
        )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert response.get_json()["connection"] == sample_result

    mock_test.assert_called_once_with(
        connection_id=10,
        user_id=1
    )


def test_test_connection_handles_connection_error(client):
    authenticate(client)

    with patch(
        "app.routes.connection_routes.check_external_database_connection",
        side_effect=ExternalDatabaseConnectionError(
            "Database connection not found."
        )
    ):

        response = client.post(
            "/api/connections/10/test",
            headers=csrf_headers(client)
        )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_delete_connection_success(client):
    authenticate(client)

    with patch(
        "app.routes.connection_routes.remove_database_connection",
        return_value=True
    ) as mock_delete:

        response = client.delete(
            "/api/connections/10",
            headers=csrf_headers(client)
        )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    mock_delete.assert_called_once_with(
        connection_id=10,
        user_id=1
    )


def test_delete_connection_not_found(client):
    authenticate(client)

    with patch(
        "app.routes.connection_routes.remove_database_connection",
        return_value=False
    ):

        response = client.delete(
            "/api/connections/10",
            headers=csrf_headers(client)
        )

    assert response.status_code == 404
