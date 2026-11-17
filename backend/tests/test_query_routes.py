
import pytest


def authenticate_client(client):
    """Create an authenticated session for route testing."""

    with client.session_transaction() as session:
        session["user_id"] = 1


def post_with_authentication(
    client,
    endpoint,
    csrf_token,
    payload
):
    """Send a POST request with authentication and CSRF protection."""

    authenticate_client(client)

    return client.post(
        endpoint,
        json=payload,
        headers={
            "X-CSRFToken": csrf_token
        }
    )


# ---------------------------------------------------------
# 1. AUTHENTICATION TESTS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_require_authentication(
    client,
    csrf_token,
    endpoint
):
    response = client.post(
        endpoint,
        json={
            "query": "SELECT name FROM employees"
        },
        headers={
            "X-CSRFToken": csrf_token
        }
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == "Authentication required."


# ---------------------------------------------------------
# 2. CSRF PROTECTION TESTS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_requests_without_csrf_token(
    client,
    endpoint
):
    authenticate_client(client)

    response = client.post(
        endpoint,
        json={
            "query": "SELECT name FROM employees"
        }
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# 3. QUERY ANALYSIS ROUTE TESTS
# ---------------------------------------------------------

def test_analyze_route_success(
    client,
    csrf_token
):
    response = post_with_authentication(
        client,
        "/api/queries/analyze",
        csrf_token,
        {
            "query": "SELECT * FROM employees"
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["message"] == "SQL query analysis completed."

    result = data["data"]

    assert result["statement_type"] == "SELECT"
    assert result["findings_count"] > 0

    rule_ids = {
        finding["rule_id"]
        for finding in result["findings"]
    }

    assert "QW001" in rule_ids
    assert "QW002" in rule_ids


def test_analyze_route_returns_no_findings_for_simple_query(
    client,
    csrf_token
):
    response = post_with_authentication(
        client,
        "/api/queries/analyze",
        csrf_token,
        {
            "query": (
                "SELECT name FROM employees "
                "WHERE employee_id = 1"
            )
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["data"]["findings_count"] == 0
    assert data["data"]["findings"] == []


# ---------------------------------------------------------
# 4. QUERY OPTIMIZATION ROUTE TESTS
# ---------------------------------------------------------

def test_optimize_route_success(
    client,
    csrf_token
):
    response = post_with_authentication(
        client,
        "/api/queries/optimize",
        csrf_token,
        {
            "query": (
                "SELECT name FROM employees "
                "WHERE department = 'Engineering' "
                "AND department = 'Engineering'"
            )
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["message"] == "SQL query optimization completed."

    result = data["data"]

    assert result["original_query"]
    assert result["optimized_query"]

    assert "department = 'Engineering'" in result["optimized_query"]

    assert result["techniques_count"] == 1

    assert (
        "redundant_condition_removal"
        in result["techniques"]
    )

    assert result["explanation"]


def test_optimize_route_returns_unchanged_query_when_no_optimization_is_needed(
    client,
    csrf_token
):
    query = (
        "SELECT name FROM employees "
        "WHERE salary > 50000"
    )

    response = post_with_authentication(
        client,
        "/api/queries/optimize",
        csrf_token,
        {
            "query": query
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"

    result = data["data"]

    assert result["techniques_count"] == 0
    assert result["techniques"] == []

    assert (
        result["original_query"]
        == result["optimized_query"]
    )


# ---------------------------------------------------------
# 5. INVALID SQL REQUEST TESTS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_non_select_statements(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": "DELETE FROM employees"
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_invalid_sql(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": "INVALID SQL"
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_multiple_statements(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": (
                "SELECT name FROM employees; "
                "DELETE FROM employees"
            )
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


# ---------------------------------------------------------
# 6. REQUEST VALIDATION TESTS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_missing_query(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert "query" in data["message"].lower()


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_empty_query(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": "   "
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_non_string_query(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": 12345
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/queries/analyze",
        "/api/queries/optimize"
    ]
)
def test_query_routes_reject_oversized_query(
    client,
    csrf_token,
    endpoint
):
    response = post_with_authentication(
        client,
        endpoint,
        csrf_token,
        {
            "query": "SELECT " + ("a" * 10000)
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


def test_query_routes_reject_non_json_request(
    client,
    csrf_token
):
    authenticate_client(client)

    response = client.post(
        "/api/queries/optimize",
        data="SELECT name FROM employees",
        content_type="text/plain",
        headers={
            "X-CSRFToken": csrf_token
        }
    )

    assert response.status_code == 415

    data = response.get_json()

    assert data["status"] == "error"
