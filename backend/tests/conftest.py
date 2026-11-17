
import pytest

from app import create_app


@pytest.fixture
def app():
    """
    Create a Flask application configured for automated testing.
    """

    test_app = create_app()

    test_app.config.update(
        TESTING=True,
        SECRET_KEY="querywise-test-secret-key",
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=False,
        RATELIMIT_ENABLED=False
    )

    yield test_app


@pytest.fixture
def client(app):
    """
    Provide a Flask test client for sending HTTP requests.
    """

    return app.test_client()


@pytest.fixture
def csrf_token(client):
    """
    Generate a valid CSRF token for protected requests.
    """

    response = client.get("/api/csrf/token")

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["status"] == "success"
    assert "csrf_token" in response_data

    return response_data["csrf_token"]
