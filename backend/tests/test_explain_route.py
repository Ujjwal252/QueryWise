
import pytest

from app.services.explain_service import ExplainServiceError
from app.services.index_service import IndexServiceError


# ---------------------------------------------------------
# 1. AUTHENTICATION
# ---------------------------------------------------------

def test_explain_requires_authentication(client, csrf_token):
    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 3,
            "query": "SELECT employee_name FROM employees"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 401
    assert response.get_json()["status"] == "error"


# ---------------------------------------------------------
# 2. CSRF PROTECTION
# ---------------------------------------------------------

def test_explain_requires_csrf_token(client):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 3,
            "query": "SELECT employee_name FROM employees"
        }
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# 3. SUCCESSFUL EXECUTION PLAN AND INDEX ANALYSIS
# ---------------------------------------------------------

def test_explain_returns_execution_plan_and_index_analysis(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    expected_plan = {
        "query_block": {
            "select_id": 1,
            "cost_info": {
                "query_cost": "0.75"
            },
            "table": {
                "table_name": "employees",
                "access_type": "ALL",
                "possible_keys": [],
                "rows_examined_per_scan": 5,
                "rows_produced_per_join": 1,
                "filtered": "20.00"
            }
        }
    }

    expected_indexes = [
        {
            "table_name": "employees",
            "column_name": "employee_id",
            "index_name": "PRIMARY",
            "sequence_in_index": 1,
            "non_unique": 0,
            "index_type": "BTREE"
        }
    ]

    expected_index_recommendations = {
        "recommendations_count": 0,
        "recommendations": [],
        "skipped_candidates_count": 1,
        "skipped_candidates": [
            {
                "table_name": "employees",
                "column_name": "department",
                "estimated_rows": 5.0,
                "reason": (
                    "The estimated table scan is small. "
                    "An additional index may not improve performance."
                )
            }
        ],
        "automatic_index_creation": False
    }

    def mock_execution_plan(connection_id, user_id, query):
        assert connection_id == 3
        assert user_id == 1
        assert "employees" in query

        return {
            "format": "JSON",
            "database_engine": "MySQL",
            "execution_plan": expected_plan
        }

    def mock_index_recommendations(
        connection_id,
        user_id,
        query,
        execution_analysis
    ):
        assert connection_id == 3
        assert user_id == 1
        assert "employees" in query
        assert execution_analysis["database_engine"] == "MySQL"

        return {
            "connection_id": connection_id,
            "tables_checked": ["employees"],
            "existing_indexes_count": 1,
            "existing_indexes": expected_indexes,
            "recommendations": expected_index_recommendations
        }

    monkeypatch.setattr(
        "app.routes.query_routes.get_query_execution_plan",
        mock_execution_plan
    )

    monkeypatch.setattr(
        "app.routes.query_routes.get_index_recommendations",
        mock_index_recommendations
    )

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 3,
            "query": (
                "SELECT employee_name FROM employees "
                "WHERE department = 'Engineering'"
            )
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"

    result = data["data"]

    assert result["connection_id"] == 3
    assert result["original_query"] == (
        "SELECT employee_name FROM employees "
        "WHERE department = 'Engineering'"
    )

    # Execution plan verification.
    assert result["execution_plan"] == expected_plan

    # Execution-plan analysis verification.
    assert result["analysis"]["database_engine"] == "MySQL"
    assert result["analysis"]["summary"]["tables_accessed"] == 1
    assert result["analysis"]["summary"]["estimated_rows_examined"] == 5.0
    assert result["analysis"]["findings"][0]["rule_id"] == "EP001"

    # Existing index metadata verification.
    index_analysis = result["index_analysis"]

    assert index_analysis["connection_id"] == 3
    assert index_analysis["tables_checked"] == ["employees"]
    assert index_analysis["existing_indexes_count"] == 1
    assert index_analysis["existing_indexes"] == expected_indexes

    # Index recommendation verification.
    recommendations = index_analysis["recommendations"]

    assert recommendations["recommendations_count"] == 0
    assert recommendations["skipped_candidates_count"] == 1
    assert recommendations["automatic_index_creation"] is False


# ---------------------------------------------------------
# 4. CONNECTION ID VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "connection_id",
    [
        None,
        0,
        -1,
        "3",
        True,
        3.5
    ]
)
def test_explain_rejects_invalid_connection_id(
    client,
    csrf_token,
    connection_id
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": connection_id,
            "query": "SELECT employee_name FROM employees"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert "connection_id" in data["message"]


# ---------------------------------------------------------
# 5. SQL VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM employees",
        "INSERT INTO employees (employee_name) VALUES ('Amit')",
        "INVALID SQL",
        "SELECT employee_name FROM employees; DELETE FROM employees"
    ]
)
def test_explain_rejects_invalid_or_unsafe_sql(
    client,
    csrf_token,
    query
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 3,
            "query": query
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"


# ---------------------------------------------------------
# 6. DATABASE SERVICE ERROR HANDLING
# ---------------------------------------------------------

def test_explain_handles_database_service_error(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    def mock_execution_plan(connection_id, user_id, query):
        raise ExplainServiceError(
            "Database connection not found."
        )

    monkeypatch.setattr(
        "app.routes.query_routes.get_query_execution_plan",
        mock_execution_plan
    )

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 999,
            "query": "SELECT employee_name FROM employees"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == "Database connection not found."


# ---------------------------------------------------------
# 7. INDEX SERVICE ERROR HANDLING
# ---------------------------------------------------------

def test_explain_handles_index_service_error(
    client,
    csrf_token,
    monkeypatch
):
    with client.session_transaction() as session:
        session["user_id"] = 1

    expected_plan = {
        "query_block": {
            "select_id": 1,
            "table": {
                "table_name": "employees",
                "access_type": "ALL",
                "rows_examined_per_scan": 5
            }
        }
    }

    def mock_execution_plan(connection_id, user_id, query):
        return {
            "format": "JSON",
            "database_engine": "MySQL",
            "execution_plan": expected_plan
        }

    def mock_index_recommendations(
        connection_id,
        user_id,
        query,
        execution_analysis
    ):
        raise IndexServiceError(
            "Unable to retrieve index metadata."
        )

    monkeypatch.setattr(
        "app.routes.query_routes.get_query_execution_plan",
        mock_execution_plan
    )

    monkeypatch.setattr(
        "app.routes.query_routes.get_index_recommendations",
        mock_index_recommendations
    )

    response = client.post(
        "/api/queries/explain",
        json={
            "connection_id": 3,
            "query": "SELECT employee_name FROM employees"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == "Unable to retrieve index metadata."
