
from flask import Blueprint, jsonify

from app.services.database_service import check_database_connection


health_bp = Blueprint("health", __name__)


@health_bp.route("/db", methods=["GET"])
def database_health():
    """
    Check the availability of the MySQL database.
    """

    try:
        database_info = check_database_connection()

        return jsonify({
            "status": "success",
            "message": "Database connection successful!",
            "database": database_info
        }), 200

    except Exception:
        health_bp.logger.exception(
            "Database health check failed"
        )

        return jsonify({
            "status": "error",
            "message": "Database connection failed."
        }), 503
