
from flask import Blueprint, jsonify, request, session

from app.extensions import limiter

from app.services.security_analysis_service import (
    analyze_database_security,
    SecurityAnalysisError
)

from app.services.external_database_service import (
    ExternalDatabaseConnectionError
)


security_bp = Blueprint("security", __name__)


@security_bp.route("/analyze", methods=["POST"])
@limiter.limit("5 per minute")
def analyze_database_security_route():
    """
    Analyze the security of an authenticated user's database.

    Endpoint:
        POST /api/security/analyze
    """

    # 1. Authentication check.
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    # 2. Validate request content type.
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request must contain JSON."
        }), 415

    # 3. Validate JSON body.
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Invalid JSON request body."
        }), 400

    # 4. Validate connection ID.
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

    # 5. Validate optional SQL query.
    query = data.get("query")

    if query is not None and (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > 10000
    ):
        return jsonify({
            "status": "error",
            "message": (
                "query must be a non-empty string "
                "of at most 10000 characters."
            )
        }), 400

    # 6. Validate optional table names.
    table_names = data.get("table_names")

    if table_names is not None and not isinstance(table_names, list):
        return jsonify({
            "status": "error",
            "message": "table_names must be an array."
        }), 400

    # 7. Perform security analysis.
    try:
        result = analyze_database_security(
            connection_id=connection_id,
            user_id=user_id,
            query=query,
            table_names=table_names
        )

        return jsonify({
            "status": "success",
            "message": "Database security analysis completed.",
            "data": result
        }), 200

    except (
        ValueError,
        ExternalDatabaseConnectionError,
        SecurityAnalysisError
    ) as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400
