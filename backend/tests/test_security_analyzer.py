
import pytest

from app.security.security_analyzer import (
    analyze_sql_security,
    classify_sensitive_column
)


# ---------------------------------------------------------
# SQL SECURITY ANALYSIS TESTS
# ---------------------------------------------------------

def test_sql_security_detects_comment_marker():
    query = "SELECT employee_id FROM employees -- review"

    findings = analyze_sql_security(query)

    assert any(
        finding.finding_type == "sql_injection"
        for finding in findings
    )


def test_sql_security_does_not_flag_plain_select():
    query = "SELECT employee_id FROM employees"

    findings = analyze_sql_security(query)

    assert findings == []


def test_sql_security_detects_union_pattern():
    query = """
        SELECT employee_id FROM employees
        UNION
        SELECT user_id FROM users
    """

    findings = analyze_sql_security(query)

    assert any(
        finding.title == "UNION query detected"
        for finding in findings
    )


def test_sql_security_detects_information_schema():
    query = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
    """

    findings = analyze_sql_security(query)

    assert any(
        finding.title == "Information-schema access detected"
        for finding in findings
    )


def test_sql_security_rejects_empty_query():
    with pytest.raises(ValueError):
        analyze_sql_security("")


def test_sql_security_rejects_non_string_query():
    with pytest.raises(ValueError):
        analyze_sql_security(123)


def test_sql_security_rejects_oversized_query():
    query = "SELECT " + ("a" * 10001)

    with pytest.raises(ValueError):
        analyze_sql_security(query)


def test_sql_security_detects_read_only_policy_violation():
    query = "DELETE FROM employees"

    findings = analyze_sql_security(query)

    assert any(
        finding.finding_type == "sql_policy"
        for finding in findings
    )


# ---------------------------------------------------------
# SENSITIVE COLUMN CLASSIFICATION TESTS
# ---------------------------------------------------------

def test_password_column_is_critical():
    result = classify_sensitive_column(
        "password_hash",
        "varchar"
    )

    assert result == ("authentication_secret", "critical")


def test_email_column_is_medium():
    result = classify_sensitive_column(
        "email_address",
        "varchar"
    )

    assert result == ("contact_information", "medium")


def test_phone_column_is_medium():
    result = classify_sensitive_column(
        "phone_number",
        "varchar"
    )

    assert result == ("contact_information", "medium")


def test_credit_card_column_is_high():
    result = classify_sensitive_column(
        "credit_card_number",
        "varchar"
    )

    assert result == ("payment_card", "high")


def test_passport_column_is_high():
    result = classify_sensitive_column(
        "passport_number",
        "varchar"
    )

    assert result == ("government_identifier", "high")


def test_salary_column_is_medium():
    result = classify_sensitive_column(
        "salary",
        "decimal"
    )

    assert result == ("financial_information", "medium")


def test_employee_id_is_not_sensitive():
    result = classify_sensitive_column(
        "employee_id",
        "int"
    )

    assert result is None
