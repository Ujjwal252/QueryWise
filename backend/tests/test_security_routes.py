
from unittest.mock import patch


# ---------------------------------------------------------
# AUTHENTICATION TESTS
# ---------------------------------------------------------

def test_security_analysis_requires_authentication(client, csrf_token):
    response = client.post(
        "/api/security/analyze",
        json={"connection_id": 1},
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == "Authentication required."


# ---------------------------------------------------------
# REQUEST VALIDATION TESTS
# ---------------------------------------------------------

def test_security_analysis_requires_json(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        data="connection_id=1",
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 415


def test_security_analysis_rejects_invalid_json(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        data="{invalid-json",
        content_type="application/json",
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


def test_security_analysis_requires_connection_id(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        json={},
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


def test_security_analysis_rejects_boolean_connection_id(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        json={"connection_id": True},
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


def test_security_analysis_rejects_invalid_query(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        json={
            "connection_id": 1,
            "query": ""
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


def test_security_analysis_rejects_invalid_table_names(client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/security/analyze",
        json={
            "connection_id": 1,
            "table_names": "employees"
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# SECURITY ANALYSIS API TESTS
# ---------------------------------------------------------

@patch("app.routes.security_routes.analyze_database_security")
def test_security_analysis_success(mock_analyze, client, csrf_token):
    with client.session_transaction() as session:
        session["user_id"] = 1

    mock_analyze.return_value = {
        "connection_id": 1,
        "findings_count": 1,
        "saved_findings_count": 1,
        "severity_counts": {
            "critical": 0,
            "high": 1,
            "medium": 0,
            "low": 0,
            "info": 0
        },
        "findings": [
            {
                "finding_type": "database_privilege",
                "severity": "high",
                "title": "Account has GRANT OPTION",
                "description": "Excessive privilege detected.",
                "recommendation": "Use least-privilege permissions."
            }
        ]
    }

    response = client.post(
        "/api/security/analyze",
        json={
            "connection_id": 1,
            "query": "SELECT employee_id FROM employees",
            "table_names": ["employees"]
        },
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["data"]["findings_count"] == 1

    mock_analyze.assert_called_once_with(
        connection_id=1,
        user_id=1,
        query="SELECT employee_id FROM employees",
        table_names=["employees"]
    )


@patch("app.routes.security_routes.analyze_database_security")
def test_security_analysis_handles_service_error(
    mock_analyze,
    client,
    csrf_token
):
    from app.services.security_analysis_service import SecurityAnalysisError

    with client.session_transaction() as session:
        session["user_id"] = 1

    mock_analyze.side_effect = SecurityAnalysisError(
        "Unable to complete database security analysis."
    )

    response = client.post(
        "/api/security/analyze",
        json={"connection_id": 1},
        headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["status"] == "error"
    assert data["message"] == (
        "Unable to complete database security analysis."
    )
