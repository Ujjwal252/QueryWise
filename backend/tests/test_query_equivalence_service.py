
import pytest

from app import create_app
from app.services import query_equivalence_service as equivalence_service
from app.services.query_equivalence_service import (
    QueryEquivalenceServiceError,
    compare_query_results
)


class FakeCursor:
    """Simulates a MySQL cursor for equivalence tests."""

    def __init__(self, query_results):
        self.query_results = query_results
        self.description = None
        self.current_rows = []
        self.position = 0

    def execute(self, query):
        if "candidate_marker" in query:
            result = self.query_results["candidate"]
        else:
            result = self.query_results["original"]

        self.description = [
            (column_name, None, None, None, None, None, None)
            for column_name in result["columns"]
        ]

        self.current_rows = result["rows"]
        self.position = 0

    def fetchmany(self, size):
        batch = self.current_rows[
            self.position:self.position + size
        ]

        self.position += len(batch)

        return batch

    def close(self):
        pass


class FakeConnection:
    """Simulates a database connection."""

    def __init__(self, query_results):
        self.query_results = query_results
        self.transaction_calls = []

    def start_transaction(
        self,
        consistent_snapshot=False,
        readonly=False
    ):
        self.transaction_calls.append({
            "consistent_snapshot": consistent_snapshot,
            "readonly": readonly
        })

    def cursor(self):
        return FakeCursor(self.query_results)

    def close(self):
        pass


@pytest.fixture
def app_context():
    app = create_app()

    with app.app_context():
        yield app


@pytest.fixture
def mock_database(monkeypatch):
    def configure(
        original_columns,
        original_rows,
        candidate_columns=None,
        candidate_rows=None
    ):

        query_results = {
            "original": {
                "columns": original_columns,
                "rows": original_rows
            },
            "candidate": {
                "columns": (
                    candidate_columns
                    if candidate_columns is not None
                    else original_columns
                ),
                "rows": (
                    candidate_rows
                    if candidate_rows is not None
                    else original_rows
                )
            }
        }

        connection = FakeConnection(query_results)

        monkeypatch.setattr(
            equivalence_service,
            "open_external_database_connection",
            lambda connection_id, user_id: connection
        )

        return connection

    return configure


def run_comparison():
    return compare_query_results(
        connection_id=3,
        user_id=1,
        original_query="SELECT employee_id FROM employees",
        candidate_query=(
            "SELECT employee_id FROM employees "
            "WHERE 1 = 1 /* candidate_marker */"
        )
    )


def test_identical_result_sets_are_equivalent(
    app_context, mock_database
):
    connection = mock_database(
        ["employee_id"],
        [(1,), (2,), (3,)]
    )

    result = run_comparison()

    assert result["equivalence_verified"] is True
    assert result["equivalent"] is True
    assert result["column_names_match"] is True
    assert result["original_rows_returned"] == 3
    assert result["candidate_rows_returned"] == 3

    assert connection.transaction_calls == [{
        "consistent_snapshot": True,
        "readonly": True
    }]

    assert result["snapshot_transaction_used"] is True


def test_different_result_values_are_not_equivalent(
    app_context, mock_database
):
    mock_database(
        ["employee_id"],
        [(1,), (2,), (3,)],
        candidate_rows=[(1,), (2,), (4,)]
    )

    result = run_comparison()

    assert result["equivalence_verified"] is True
    assert result["equivalent"] is False
    assert result["mismatch_reason"] == "result_rows_differ"


def test_duplicate_rows_are_preserved(
    app_context, mock_database
):
    mock_database(
        ["department"],
        [("Engineering",), ("Engineering",), ("HR",)],
        candidate_rows=[
            ("Engineering",),
            ("HR",),
            ("HR",)
        ]
    )

    result = run_comparison()

    assert result["equivalence_verified"] is True
    assert result["equivalent"] is False


def test_null_values_are_compared_correctly(
    app_context, mock_database
):
    mock_database(
        ["department"],
        [(None,), ("Engineering",)]
    )

    result = run_comparison()

    assert result["equivalence_verified"] is True
    assert result["equivalent"] is True


def test_different_column_names_are_not_equivalent(
    app_context, mock_database
):
    mock_database(
        ["employee_id"],
        [(1,), (2,)],
        candidate_columns=["id"],
        candidate_rows=[(1,), (2,)]
    )

    result = run_comparison()

    assert result["equivalence_verified"] is True
    assert result["equivalent"] is False
    assert result["mismatch_reason"] == "column_names_differ"


def test_unordered_results_ignore_row_order(
    app_context, mock_database
):
    mock_database(
        ["employee_id"],
        [(1,), (2,), (3,)],
        candidate_rows=[(3,), (1,), (2,)]
    )

    result = run_comparison()

    assert result["result_order_matters"] is False
    assert result["equivalent"] is True


def test_ordered_results_preserve_row_order(
    app_context
):
    original_query = (
        "SELECT employee_id FROM employees ORDER BY employee_id"
    )

    connection_results = {
        "original": {
            "columns": ["employee_id"],
            "rows": [(1,), (2,), (3,)]
        },
        "candidate": {
            "columns": ["employee_id"],
            "rows": [(3,), (2,), (1,)]
        }
    }

    class OrderedCursor(FakeCursor):
        def execute(self, query):
            if "candidate_marker" in query:
                result = connection_results["candidate"]
            else:
                result = connection_results["original"]

            self.description = [
                (name, None, None, None, None, None, None)
                for name in result["columns"]
            ]

            self.current_rows = result["rows"]
            self.position = 0

    class OrderedConnection:
        def __init__(self):
            self.transaction_calls = []

        def start_transaction(
            self,
            consistent_snapshot=False,
            readonly=False
        ):
            self.transaction_calls.append({
                "consistent_snapshot": consistent_snapshot,
                "readonly": readonly
            })

        def cursor(self):
            return OrderedCursor(connection_results)

        def close(self):
            pass

    connection = OrderedConnection()

    monkeypatch = pytest.MonkeyPatch()

    monkeypatch.setattr(
        equivalence_service,
        "open_external_database_connection",
        lambda connection_id, user_id: connection
    )

    try:
        result = compare_query_results(
            connection_id=3,
            user_id=1,
            original_query=original_query,
            candidate_query=(
                "SELECT employee_id FROM employees "
                "ORDER BY employee_id DESC /* candidate_marker */"
            )
        )
    finally:
        monkeypatch.undo()

    assert result["result_order_matters"] is True
    assert result["equivalent"] is False
    assert result["mismatch_reason"] == "ordered_rows_differ"

    assert connection.transaction_calls == [{
        "consistent_snapshot": True,
        "readonly": True
    }]


def test_result_limit_prevents_unbounded_comparison(
    app_context, mock_database, monkeypatch
):
    mock_database(
        ["employee_id"],
        [(1,), (2,)]
    )

    monkeypatch.setattr(
        equivalence_service,
        "MAX_RESULT_ROWS",
        1
    )

    result = run_comparison()

    assert result["equivalence_verified"] is False
    assert result["equivalent"] is None
    assert result["mismatch_reason"] == "result_limit_exceeded"


@pytest.mark.parametrize(
    "connection_id",
    [None, 0, -1, True, 3.5]
)
def test_invalid_connection_ids_are_rejected(
    app_context, connection_id
):
    with pytest.raises(ValueError):
        compare_query_results(
            connection_id=connection_id,
            user_id=1,
            original_query="SELECT employee_id FROM employees",
            candidate_query="SELECT employee_id FROM employees WHERE 1=1"
        )


def test_invalid_user_id_is_rejected(app_context):
    with pytest.raises(ValueError):
        compare_query_results(
            connection_id=3,
            user_id=0,
            original_query="SELECT employee_id FROM employees",
            candidate_query="SELECT employee_id FROM employees WHERE 1=1"
        )


@pytest.mark.parametrize(
    "query",
    [
        "",
        "DELETE FROM employees",
        "INVALID SQL",
        "SELECT employee_id FROM employees; DELETE FROM employees"
    ]
)
def test_invalid_queries_are_rejected(app_context, query):
    with pytest.raises(ValueError):
        compare_query_results(
            connection_id=3,
            user_id=1,
            original_query=query,
            candidate_query="SELECT employee_id FROM employees"
        )


def test_database_failure_is_handled(
    app_context, monkeypatch
):
    def raise_database_error(connection_id, user_id):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(
        equivalence_service,
        "open_external_database_connection",
        raise_database_error
    )

    with pytest.raises(QueryEquivalenceServiceError):
        run_comparison()
