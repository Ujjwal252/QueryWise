
import pytest

from app.optimizer.sql_parser import parse_sql


@pytest.mark.parametrize(
    "query, expected_type",
    [
        ("SELECT * FROM employees", "SELECT"),
        ("INSERT INTO employees (name) VALUES ('Amit')", "INSERT"),
        ("UPDATE employees SET salary = 70000", "UPDATE"),
        ("DELETE FROM employees WHERE id = 1", "DELETE"),
        ("CREATE TABLE test_table (id INT)", "CREATE"),
        ("DROP TABLE test_table", "DROP"),
        ("ALTER TABLE employees ADD COLUMN age INT", "ALTER"),
    ],
)
def test_parse_valid_sql_statements(query, expected_type):
    result = parse_sql(query)

    assert result.success is True
    assert result.statement_type == expected_type
    assert result.normalized_query is not None
    assert result.error is None


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_parse_rejects_empty_or_invalid_input(query):
    result = parse_sql(query)

    assert result.success is False
    assert result.error is not None


def test_parse_rejects_multiple_statements():
    query = "SELECT * FROM employees; DELETE FROM employees"

    result = parse_sql(query)

    assert result.success is False
    assert result.error == "Multiple SQL statements are not allowed."


def test_parse_rejects_unrecognized_sql_expression():
    result = parse_sql("INVALID SQL")

    assert result.success is False
    assert result.error == "Input is not a recognized SQL statement."


def test_parse_preserves_original_query():
    query = "SELECT name FROM employees"

    result = parse_sql(query)

    assert result.success is True
    assert result.original_query == query


def test_parse_supports_mysql_dialect():
    query = "SELECT name FROM employees LIMIT 5"

    result = parse_sql(query)

    assert result.success is True
    assert result.statement_type == "SELECT"
    assert "LIMIT 5" in result.normalized_query.upper()
