
from flask import Blueprint, jsonify, request, session

from app.optimizer.query_analyzer import analyze_query
from app.optimizer.query_optimizer import optimize_query
from app.optimizer.sql_validator import validate_read_only_query
from app.optimizer.execution_plan_analyzer import analyze_execution_plan

from app.services.explain_service import (
    get_query_execution_plan,
    ExplainServiceError
)

from app.services.index_service import (
    get_index_recommendations,
    IndexServiceError
)

from app.services.query_comparison_service import (
    compare_query_performance,
    QueryComparisonError
)

from app.services.performance_service import PerformanceServiceError


query_bp = Blueprint("query", __name__)


# ---------------------------------------------------------
# SHARED REQUEST VALIDATION
# ---------------------------------------------------------

def get_validated_query():
    """Validate request JSON and enforce the read-only SQL policy."""

    if not request.is_json:
        return None, (
            jsonify({
                "status": "error",
                "message": "Request must contain JSON."
            }),
            415
        )

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (
            jsonify({
                "status": "error",
                "message": "Invalid JSON request body."
            }),
            400
        )

    query = data.get("query")

    if not isinstance(query, str) or not query.strip():
        return None, (
            jsonify({
                "status": "error",
                "message": "A non-empty SQL query is required."
            }),
            400
        )

    if len(query) > 10000:
        return None, (
            jsonify({
                "status": "error",
                "message": "SQL query exceeds the maximum allowed length."
            }),
            400
        )

    validation_result = validate_read_only_query(query)

    if not validation_result.is_valid:
        return None, (
            jsonify({
                "status": "error",
                "message": validation_result.error
                    or "Query failed read-only validation."
            }),
            400
        )

    return query, None


def validate_comparison_query(query, field_name):
    """Validate an individual SQL query for performance comparison."""

    if not isinstance(query, str) or not query.strip():
        return None, f"A non-empty {field_name} is required."

    if len(query) > 10000:
        return None, f"{field_name} exceeds the maximum allowed length."

    validation_result = validate_read_only_query(query)

    if not validation_result.is_valid:
        return None, (
            validation_result.error
            or f"{field_name} failed read-only validation."
        )

    return query, None


# ---------------------------------------------------------
# 1. SQL QUERY ANALYSIS
# ---------------------------------------------------------

@query_bp.route("/analyze", methods=["POST"])
def analyze_sql_query():
    """Analyze a read-only SQL query."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    query, error_response = get_validated_query()

    if error_response:
        return error_response

    analysis_result = analyze_query(query)

    if not analysis_result.success:
        return jsonify({
            "status": "error",
            "message": analysis_result.error
                or "Query analysis failed."
        }), 400

    findings = [
        {
            "rule_id": finding.rule_id,
            "title": finding.title,
            "severity": finding.severity,
            "description": finding.description,
            "recommendation": finding.recommendation
        }
        for finding in analysis_result.findings
    ]

    return jsonify({
        "status": "success",
        "message": "SQL query analysis completed.",
        "data": {
            "statement_type": analysis_result.statement_type,
            "findings_count": len(findings),
            "findings": findings
        }
    }), 200


# ---------------------------------------------------------
# 2. SQL QUERY OPTIMIZATION
# ---------------------------------------------------------

@query_bp.route("/optimize", methods=["POST"])
def optimize_sql_query():
    """Optimize a read-only SQL query."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    query, error_response = get_validated_query()

    if error_response:
        return error_response

    optimization_result = optimize_query(query)

    if not optimization_result.success:
        return jsonify({
            "status": "error",
            "message": optimization_result.error
                or "SQL query optimization failed."
        }), 400

    return jsonify({
        "status": "success",
        "message": "SQL query optimization completed.",
        "data": {
            "original_query": optimization_result.original_query,
            "optimized_query": optimization_result.optimized_query,
            "techniques": optimization_result.techniques,
            "techniques_count": len(optimization_result.techniques),
            "explanation": optimization_result.explanation
        }
    }), 200


# ---------------------------------------------------------
# 3. SQL EXECUTION PLAN AND INDEX ANALYSIS
# ---------------------------------------------------------

@query_bp.route("/explain", methods=["POST"])
def explain_sql_query():
    """Retrieve and analyze a MySQL JSON execution plan and indexes."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    query, error_response = get_validated_query()

    if error_response:
        return error_response

    data = request.get_json(silent=True)
    connection_id = data.get("connection_id")

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        return jsonify({
            "status": "error",
            "message": "A valid positive connection_id is required."
        }), 400

    try:
        execution_result = get_query_execution_plan(
            connection_id=connection_id,
            user_id=user_id,
            query=query
        )

        analysis_result = analyze_execution_plan(
            execution_result["execution_plan"]
        )

        index_result = get_index_recommendations(
            connection_id=connection_id,
            user_id=user_id,
            query=query,
            execution_analysis=analysis_result
        )

        return jsonify({
            "status": "success",
            "message": (
                "Execution plan and index analysis completed successfully."
            ),
            "data": {
                "connection_id": connection_id,
                "original_query": query,
                "execution_plan": execution_result["execution_plan"],
                "analysis": analysis_result,
                "index_analysis": index_result
            }
        }), 200

    except (ExplainServiceError, IndexServiceError) as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400


# ---------------------------------------------------------
# 4. ORIGINAL VS OPTIMIZED QUERY PERFORMANCE COMPARISON
# ---------------------------------------------------------

@query_bp.route("/compare", methods=["POST"])
def compare_sql_queries():
    """Compare the measured performance of two read-only SQL queries."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request must contain JSON."
        }), 415

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Invalid JSON request body."
        }), 400

    original_query, error_message = validate_comparison_query(
        data.get("original_query"),
        "original_query"
    )

    if error_message:
        return jsonify({
            "status": "error",
            "message": error_message
        }), 400

    optimized_query, error_message = validate_comparison_query(
        data.get("optimized_query"),
        "optimized_query"
    )

    if error_message:
        return jsonify({
            "status": "error",
            "message": error_message
        }), 400

    if original_query.strip() == optimized_query.strip():
        return jsonify({
            "status": "error",
            "message": "Original and optimized queries must be different."
        }), 400

    connection_id = data.get("connection_id")

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        return jsonify({
            "status": "error",
            "message": "A valid positive connection_id is required."
        }), 400

    iterations = data.get("iterations", 5)
    warmup_runs = data.get("warmup_runs", 1)

    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or not 2 <= iterations <= 10
    ):
        return jsonify({
            "status": "error",
            "message": "Iterations must be an integer between 2 and 10."
        }), 400

    if (
        isinstance(warmup_runs, bool)
        or not isinstance(warmup_runs, int)
        or not 0 <= warmup_runs <= 2
    ):
        return jsonify({
            "status": "error",
            "message": "Warmup runs must be an integer between 0 and 2."
        }), 400

    try:
        comparison_result = compare_query_performance(
            connection_id=connection_id,
            user_id=user_id,
            original_query=original_query,
            optimized_query=optimized_query,
            iterations=iterations,
            warmup_runs=warmup_runs
        )

        return jsonify({
            "status": "success",
            "message": "Query performance comparison completed.",
            "data": comparison_result
        }), 200

    except (
        QueryComparisonError,
        PerformanceServiceError
    ) as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400
