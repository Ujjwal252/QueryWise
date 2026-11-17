
from datetime import timedelta, datetime, timezone
from email.utils import parsedate_to_datetime
from unittest.mock import patch


VALID_USER = {
    "user_id": 1,
    "username": "querywise_test",
    "email": "querywise_test@example.com",
    "full_name": "QueryWise Test User",
    "role": "user"
}


def test_session_lifetime_configuration(app):
    """Verify that the configured session lifetime is 30 minutes."""

    lifetime = app.config["PERMANENT_SESSION_LIFETIME"]

    assert lifetime == timedelta(minutes=30)


def test_session_refresh_enabled(app):
    """Verify that permanent sessions refresh on activity."""

    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True


def test_login_creates_permanent_session(client, csrf_token):
    """Verify that successful login creates a permanent session."""

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

    with client.session_transaction() as session:
        assert session.permanent is True
        assert session["user_id"] == 1


def test_session_cookie_has_30_minute_lifetime(client, csrf_token):
    """Verify that the session cookie expires approximately 30 minutes later."""

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

    cookie_headers = response.headers.getlist("Set-Cookie")

    session_cookie = next(
        (
            cookie for cookie in cookie_headers
            if cookie.startswith("session=")
        ),
        None
    )

    assert session_cookie is not None
    assert "Expires=" in session_cookie

    expires_value = next(
        part.split("=", 1)[1]
        for part in session_cookie.split(";")
        if part.strip().startswith("Expires=")
    )

    expires_at = parsedate_to_datetime(expires_value)

    current_time = datetime.now(timezone.utc)

    remaining_time = expires_at - current_time

    assert timedelta(minutes=29) <= remaining_time <= timedelta(minutes=30)


def test_session_cookie_security_settings(app):
    """Verify important session cookie security settings."""

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    # Secure is disabled for local HTTP development.
    assert app.config["SESSION_COOKIE_SECURE"] is False
