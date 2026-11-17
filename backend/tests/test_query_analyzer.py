
import pytest

from app.optimizer.query_analyzer import analyze_query


def get_rule_ids(result):
    return {finding.rule_id for finding in result.findings}


def test_detects_select_star():
    result = analyze_query("SELECT * FROM employees")

    assert result.success is True
    assert "QW001" in get_rule_ids(result)


def test_detects_table_qualified_select_star():
    result = analyze_query("SELECT employees.* FROM employees")

    assert result.success is True
    assert "QW001" in get_rule_ids(result)


def test_count_star_is_not_flagged_as_select_star():
    result = analyze_query("SELECT COUNT(*) FROM employees")

    assert result.success is True
    assert "QW001" not in get_rule_ids(result)


def test_detects_select_without_where():
    result = analyze_query("SELECT name FROM employees")

    assert result.success is True
    assert "QW002" in get_rule_ids(result)


def test_does_not_flag_select_with_where():
    result = analyze_query(
        "SELECT name FROM employees WHERE employee_id = 1"
    )

    assert result.success is True
    assert "QW002" not in get_rule_ids(result)


def test_detects_leading_wildcard_like():
    result = analyze_query(
        "SELECT name FROM employees WHERE name LIKE '%amit'"
    )

    assert result.success is True
    assert "QW003" in get_rule_ids(result)


def test_does_not_flag_trailing_wildcard_like():
    result = analyze_query(
        "SELECT name FROM employees WHERE name LIKE 'amit%'"
    )

    assert result.success is True
    assert "QW003" not in get_rule_ids(result)


def test_detects_or_condition():
    result = analyze_query(
        "SELECT name FROM employees "
        "WHERE department = 'HR' OR department = 'Finance'"
    )

    assert result.success is True
    assert "QW004" in get_rule_ids(result)


def test_detects_function_on_filtered_column():
    result = analyze_query(
        "SELECT name FROM employees WHERE YEAR(join_date) = 2025"
    )

    assert result.success is True
    assert "QW005" in get_rule_ids(result)


def test_detects_distinct():
    result = analyze_query(
        "SELECT DISTINCT department FROM employees"
    )

    assert result.success is True
    assert "QW006" in get_rule_ids(result)


def test_rejects_insert_statement():
    result = analyze_query(
        "INSERT INTO employees (name) VALUES ('Amit')"
    )

    assert result.success is False
    assert result.error is not None


def test_rejects_invalid_sql():
    result = analyze_query("INVALID SQL")

    assert result.success is False
    assert result.error is not None


def test_rejects_multiple_statements():
    result = analyze_query(
        "SELECT name FROM employees; DELETE FROM employees"
    )

    assert result.success is False
    assert result.error is not None


def test_no_findings_for_simple_filtered_query():
    result = analyze_query(
        "SELECT name FROM employees WHERE employee_id = 1"
    )

    assert result.success is True
    assert result.findings == []


def test_findings_have_required_details():
    result = analyze_query("SELECT * FROM employees")

    assert result.success is True
    assert len(result.findings) > 0

    for finding in result.findings:
        assert finding.rule_id
        assert finding.title
        assert finding.severity
        assert finding.description
        assert finding.recommendation
