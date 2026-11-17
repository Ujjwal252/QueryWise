
import pytest

from app.services.performance_service import PerformanceServiceError
from app.services.query_comparison_service import QueryComparisonError


# ---------------------------------------------------------
# 1. AUTHENTICATION
# ---------------------------------------------------------

def test_compare_requires_authentication(client, csrf_token):
    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 401
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------
# 2. CSRF PROTECTION
# ---------------------------------------------------------

def test_compare_requires_csrf_token(client):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        }
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# 3. SUCCESSFUL PERFORMANCE COMPARISON
# ---------------------------------------------------------

def test_compare_returns_performance_results(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    expected_result = {
        "connection_id": 3,
        "comparison_settings": {
            "iterations": 5,
            "warmup_runs": 1,
            "benchmark_method": "alternating",
            "execution_order": "alternating"
        },
        "original_query": {
            "sql": "SELECT employee_name FROM employees",
            "statistics": {
                "average_ms": 2.0,
                "median_ms": 2.0,
                "minimum_ms": 1.5,
                "maximum_ms": 2.5
            },
            "execution_times_ms": [2.0, 1.5, 2.5, 2.0, 2.0],
            "rows_returned": 3
        },
        "optimized_query": {
            "sql": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            ),
            "statistics": {
                "average_ms": 1.5,
                "median_ms": 1.5,
                "minimum_ms": 1.0,
                "maximum_ms": 2.0
            },
            "execution_times_ms": [1.5, 1.0, 2.0, 1.5, 1.5],
            "rows_returned": 3
        },
        "comparison": {
            "time_difference_ms": 0.5,
            "improvement_percentage": 25.0,
            "performance_status": "faster",
            "row_count_match": True,
            "result_equivalence_verified": True,
            "result_equivalent": True,
            "result_order_matters": False,
            "column_names_match": True,
            "equivalence_mismatch_reason": None,
            "paired_performance_analysis": {
                "total_rounds": 5,
                "faster_rounds": 5,
                "slower_rounds": 0,
                "equal_rounds": 0,
                "faster_rounds_percentage": 100.0,
                "slower_rounds_percentage": 0.0,
                "paired_improvements_ms": [
                    0.5, 0.4, 0.6, 0.5, 0.5
                ],
                "median_paired_improvement_ms": 0.5,
                "median_paired_improvement_percentage": 25.0,
                "consistency_threshold_percentage": 80.0,
                "required_rounds_for_consistency": 4,
                "performance_reliability": "consistent_improvement"
            },
            "optimization_assessment": "faster_and_equivalent",
            "optimization_successful": True
        }
    }

    def mock_comparison(
        connection_id,
        user_id,
        original_query,
        optimized_query,
        iterations,
        warmup_runs
    ):
        assert connection_id == 3
        assert user_id == 1
        assert original_query == (
            "SELECT employee_name FROM employees"
        )
        assert optimized_query == (
            "SELECT employee_name FROM employees WHERE 1 = 1"
        )
        assert iterations == 5
        assert warmup_runs == 1

        return expected_result

    monkeypatch.setattr(
        "app.routes.query_routes.compare_query_performance",
        mock_comparison
    )

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"

    result = data["data"]

    assert result["connection_id"] == 3
    assert result["comparison_settings"]["iterations"] == 5
    assert result["comparison_settings"]["warmup_runs"] == 1

    assert result["original_query"]["rows_returned"] == 3
    assert result["optimized_query"]["rows_returned"] == 3

    comparison = result["comparison"]

    assert comparison["performance_status"] == "faster"
    assert comparison["improvement_percentage"] == 25.0
    assert comparison["row_count_match"] is True

    assert comparison["result_equivalence_verified"] is True
    assert comparison["result_equivalent"] is True

    assert comparison["paired_performance_analysis"][
        "performance_reliability"
    ] == "consistent_improvement"

    assert comparison["optimization_assessment"] == (
        "faster_and_equivalent"
    )

    assert comparison["optimization_successful"] is True


# ---------------------------------------------------------
# 4. INVALID CONNECTION ID
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "connection_id",
    [None, 0, -1, "3", True, 3.5]
)
def test_compare_rejects_invalid_connection_id(
    client,
    csrf_token,
    connection_id
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": connection_id,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400
    assert "connection_id" in response.get_json()["message"]


# ---------------------------------------------------------
# 5. INVALID SQL
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "field, query",
    [
        ("original_query", "DELETE FROM employees"),
        ("optimized_query", "DELETE FROM employees"),
        ("original_query", "INVALID SQL"),
        (
            "optimized_query",
            "SELECT employee_name FROM employees; DELETE FROM employees"
        )
    ]
)
def test_compare_rejects_invalid_sql(
    client,
    csrf_token,
    field,
    query
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    payload = {
        "connection_id": 3,
        "original_query": "SELECT employee_name FROM employees",
        "optimized_query": (
            "SELECT employee_name FROM employees WHERE 1 = 1"
        )
    }

    payload[field] = query

    response = client.post(
        "/api/queries/compare",
        json=payload,
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------
# 6. IDENTICAL QUERIES
# ---------------------------------------------------------

def test_compare_rejects_identical_queries(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    query = "SELECT employee_name FROM employees"

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": query,
            "optimized_query": query
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400
    assert "must be different" in response.get_json()["message"]


# ---------------------------------------------------------
# 7. BENCHMARK SETTINGS VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "field, value",
    [
        ("iterations", 1),
        ("iterations", 11),
        ("iterations", True),
        ("iterations", "5"),
        ("warmup_runs", -1),
        ("warmup_runs", 3),
        ("warmup_runs", True),
        ("warmup_runs", "1")
    ]
)
def test_compare_rejects_invalid_benchmark_settings(
    client,
    csrf_token,
    field,
    value
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    payload = {
        "connection_id": 3,
        "original_query": "SELECT employee_name FROM employees",
        "optimized_query": (
            "SELECT employee_name FROM employees WHERE 1 = 1"
        ),
        "iterations": 5,
        "warmup_runs": 1
    }

    payload[field] = value

    response = client.post(
        "/api/queries/compare",
        json=payload,
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    message = response.get_json()["message"].lower()
    expected_field_name = field.replace("_", " ")

    assert expected_field_name in message


# ---------------------------------------------------------
# 8. PERFORMANCE SERVICE ERROR
# ---------------------------------------------------------

def test_compare_handles_performance_service_error(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    def mock_comparison(**kwargs):
        raise PerformanceServiceError(
            "Unable to complete query performance measurement."
        )

    monkeypatch.setattr(
        "app.routes.query_routes.compare_query_performance",
        mock_comparison
    )

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------
# 9. QUERY COMPARISON ERROR
# ---------------------------------------------------------

def test_compare_handles_comparison_service_error(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    def mock_comparison(**kwargs):
        raise QueryComparisonError(
            "Unable to compare query performance."
        )

    monkeypatch.setattr(
        "app.routes.query_routes.compare_query_performance",
        mock_comparison
    )

    response = client.post(
        "/api/queries/compare",
        json={
            "connection_id": 3,
            "original_query": "SELECT employee_name FROM employees",
            "optimized_query": (
                "SELECT employee_name FROM employees WHERE 1 = 1"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == (
        "Unable to compare query performance."
    )
