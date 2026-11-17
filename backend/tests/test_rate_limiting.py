
from unittest.mock import patch

from app import create_app
from app.extensions import limiter


def create_rate_limit_test_app():
    """Create an isolated app configuration for rate-limit tests."""

    app = create_app()

    app.config.update(
        TESTING=True,
        SECRET_KEY="querywise-rate-limit-test-secret",
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=True
    )

    limiter.reset()

    return app


def test_login_rate_limit():
    """Verify that login allows five attempts per minute."""

    app = create_rate_limit_test_app()
    client = app.test_client()

    responses = []

    for _ in range(6):
        response = client.post(
            "/api/auth/login",
            json={
                "identifier": "invaliduser",
                "password": "WrongPassword123"
            },
            environ_overrides={
                "REMOTE_ADDR": "192.0.2.10"
            }
        )

        responses.append(response.status_code)

    # The first five requests should reach authentication
    # and fail because the credentials are invalid.
    assert responses[:5] == [401, 401, 401, 401, 401]

    # The sixth request should be blocked.
    assert responses[5] == 429


def test_registration_rate_limit():
    """Verify that registration allows five attempts per hour."""

    app = create_rate_limit_test_app()
    client = app.test_client()

    responses = []

    with patch(
        "app.routes.auth_routes.create_user",
        return_value=123
    ), patch(
        "app.routes.auth_routes.log_audit_event",
        return_value=True
    ):

        for index in range(6):
            response = client.post(
                "/api/auth/register",
                json={
                    "username": f"ratelimit_user_{index}",
                    "email": f"ratelimit{index}@example.com",
                    "password": "StrongPassword123",
                    "full_name": "Rate Limit Test"
                },
                environ_overrides={
                    "REMOTE_ADDR": "192.0.2.20"
                }
            )

            responses.append(response.status_code)

    # The first five requests should register successfully.
    assert responses[:5] == [201, 201, 201, 201, 201]

    # The sixth request should be blocked.
    assert responses[5] == 429
