
import pytest

from app.optimizer.sql_validator import validate_read_only_query


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM employees",
        "SELECT UPPER(name) FROM employees",
        "SELECT COUNT(*) FROM employees",
        "SELECT ROUND(salary, 2) FROM employees",
        "SELECT COALESCE(name, 'Unknown') FROM employees",
    ],
)
def test_allows_approved_select_queries(query):
    result = validate_read_only_query(query)

    assert result.is_valid is True
    assert result.statement_type == "SELECT"
    assert result.error is None


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO employees (name) VALUES ('Amit')",
        "UPDATE employees SET salary = 70000",
        "DELETE FROM employees WHERE id = 1",
        "DROP TABLE employees",
        "ALTER TABLE employees ADD COLUMN age INT",
        "CREATE TABLE test_table (id INT)",
    ],
)
def test_rejects_write_and_ddl_statements(query):
    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error == "Only SELECT statements are allowed."


def test_rejects_multiple_statements():
    query = "SELECT * FROM employees; DELETE FROM employees"

    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error == "Multiple SQL statements are not allowed."


@pytest.mark.parametrize(
    "query",
    [
        "SELECT name INTO OUTFILE 'C:/temp/employees.txt' FROM employees",
        "SELECT name INTO DUMPFILE 'C:/temp/employee.bin' FROM employees",
    ],
)
def test_rejects_file_writing_select_queries(query):
    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert "OUTFILE and DUMPFILE are not allowed" in result.error


def test_rejects_select_into_construct():
    query = "SELECT name INTO @employee_name FROM employees"

    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error == "SELECT INTO statements are not allowed."


def test_rejects_select_for_update():
    query = "SELECT * FROM employees FOR UPDATE"

    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error == "SELECT queries with locking clauses are not allowed."


@pytest.mark.parametrize(
    "query",
    [
        "SELECT SLEEP(5)",
        "SELECT GET_LOCK('test_lock', 10)",
        "SELECT custom_function(salary) FROM employees",
    ],
)
def test_rejects_unverified_functions(query):
    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error == "Unverified function calls are not allowed."


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "INVALID SQL",
    ],
)
def test_rejects_invalid_or_empty_queries(query):
    result = validate_read_only_query(query)

    assert result.is_valid is False
    assert result.error is not None


def test_rejects_non_string_input():
    result = validate_read_only_query(None)

    assert result.is_valid is False
    assert result.error == "SQL query must be a string."
