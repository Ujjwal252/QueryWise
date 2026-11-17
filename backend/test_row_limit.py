
from app import create_app
import app.services.performance_service as ps


app = create_app()

with app.app_context():

    ps.MAX_BENCHMARK_ROWS = 2

    query = "SELECT employee_id, employee_name FROM employees"

    candidate_query = (
        "SELECT employee_id, employee_name "
        "FROM employees WHERE employee_id > 0"
    )

    try:
        ps.benchmark_query_pair(
            connection_id=3,
            user_id=1,
            original_query=query,
            candidate_query=candidate_query,
            iterations=2,
            warmup_runs=0
        )

        print("ERROR: Row limit was not enforced.")

    except ps.BenchmarkLimitExceeded as exc:
        print("PASS: Row safety limit enforced.")
        print(str(exc))
