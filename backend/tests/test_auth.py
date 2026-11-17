
from unittest.mock import patch


VALID_USER = {
    "user_id": 1,
    "username": "querywise_test",
    "email": "querywise_test@example.com",
    "full_name": "QueryWise Test User",
    "role": "user"
}


def test_register_success(client, csrf_token):
    """A valid registration should create a user."""

    with patch(
        "app.routes.auth_routes.create_user",
        return_value=10
    ), patch(
        "app.routes.auth_routes.log_audit_event",
        return_value=True
    ):

        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser123",
                "email": "newuser@example.com",
                "password": "TestPassword123",
                "full_name": "New User"
            },
            headers={"X-CSRFToken": csrf_token}
        )

    assert response.status_code == 201
    assert response.get_json()["status"] == "success"


def test_register_duplicate_user(client, csrf_token):
    """Duplicate username or email should return 409."""

    with patch(
        "app.routes.auth_routes.create_user",
        return_value=None
    ):

        response = client.post(
            "/api/auth/register",
            json={
                "username": "querywise_test",
                "email": "querywise_test@example.com",
                "password": "TestPassword123"
            },
            headers={"X-CSRFToken": csrf_token}
        )

    assert response.status_code == 409


def test_register_invalid_input(client, csrf_token):
    """Invalid registration input should return 400."""

    response = client.post(
        "/api/auth/register",
        json={
            "username": "ab",
            "email": "invalid-email",
            "password": "123"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


def test_login_success(client, csrf_token):
    """Valid credentials should create an authenticated session."""

    with patch(
        "app.routes.auth_routes.authenticate_user",
        return_value=VALID_USER
    ), patch(
        "app.routes.auth_routes.log_audit_event",
        return_value=True
    ):

        response = client.post(
            "/api/auth/login",
            json={
                "identifier": "querywise_test",
                "password": "TestPassword123"
            },
            headers={"X-CSRFToken": csrf_token}
        )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    with client.session_transaction() as session:
        assert session["user_id"] == 1
        assert session.permanent is True


def test_login_invalid_credentials(client, csrf_token):
    """Invalid credentials should return 401."""

    with patch(
        "app.routes.auth_routes.authenticate_user",
        return_value=None
    ), patch(
        "app.routes.auth_routes.log_audit_event",
        return_value=True
    ):

        response = client.post(
            "/api/auth/login",
            json={
                "identifier": "wronguser",
                "password": "WrongPassword123"
            },
            headers={"X-CSRFToken": csrf_token}
        )

    assert response.status_code == 401


def test_login_without_csrf_token(client):
    """Login without a CSRF token should be rejected."""

    response = client.post(
        "/api/auth/login",
        json={
            "identifier": "querywise_test",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 400


def test_current_user_authenticated(client):
    """Authenticated users should access their profile."""

    with client.session_transaction() as session:
        session["user_id"] = 1

    with patch(
        "app.routes.auth_routes.get_user_by_id",
        return_value=VALID_USER
    ):

        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "querywise_test"


def test_current_user_unauthenticated(client):
    """Unauthenticated users should receive 401."""

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_invalidates_session(client, csrf_token):
    """Logout should clear the authenticated session."""

    with client.session_transaction() as session:
        session["user_id"] = 1

    with patch(
        "app.routes.auth_routes.log_audit_event",
        return_value=True
    ):

        logout_response = client.post(
            "/api/auth/logout",
            headers={"X-CSRFToken": csrf_token}
        )

    assert logout_response.status_code == 200

    with client.session_transaction() as session:
        assert "user_id" not in session

    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 401
