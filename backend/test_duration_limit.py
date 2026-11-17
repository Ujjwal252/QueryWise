
from unittest.mock import patch

import app.services.performance_service as ps


class FakeCursor:
    def execute(self, query):
        print("Simulated SQL query executed.")

    def fetchmany(self, size):
        return []


def test_execution_time_limit():

    cursor = FakeCursor()

    # Simulate elapsed time increasing from 0 to 16 seconds.
    with patch.object(
        ps.time,
        "perf_counter",
        side_effect=[0.0, 16.0]
    ):
        try:
            ps._execute_and_measure(
                cursor,
                "SELECT employee_id FROM employees"
            )

            print("FAIL: Execution-time limit was not enforced.")

        except ps.BenchmarkLimitExceeded as exc:
            print("PASS: Execution-time safety limit enforced.")
            print(str(exc))


if __name__ == "__main__":
    test_execution_time_limit()
