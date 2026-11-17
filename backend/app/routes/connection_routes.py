
import logging

from flask import Blueprint, jsonify, request, session

from app.extensions import limiter
from app.services.connection_service import (
    save_database_connection,
    list_database_connections,
    remove_database_connection
)
from app.services.external_database_service import (
    check_external_database_connection,
    ExternalDatabaseConnectionError
)


logger = logging.getLogger(__name__)

connection_bp = Blueprint(
    "connections",
    __name__,
    url_prefix="/api/connections"
)


def get_authenticated_user_id():
    """Return the logged-in user's ID, if available."""
    return session.get("user_id")


def validate_connection_input(data):
    """Validate the submitted database connection details."""

    required_fields = [
        "connection_name",
        "host",
        "port",
        "database_name",
        "db_username",
        "password"
    ]

    for field in required_fields:
        value = data.get(field)

        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            return f"{field} is required."

    port = data.get("port")

    if isinstance(port, bool) or not isinstance(port, int):
        return "Port must be an integer."

    if not 1 <= port <= 65535:
        return "Port must be between 1 and 65535."

    for field in [
        "connection_name",
        "host",
        "database_name",
        "db_username"
    ]:
        if not isinstance(data.get(field), str):
            return f"{field} must be a string."

    if not isinstance(data.get("password"), str):
        return "Password must be a string."

    if not isinstance(data.get("use_ssl", False), bool):
        return "use_ssl must be true or false."

    return None


@connection_bp.route("", methods=["POST"])
@limiter.limit("10 per minute")
def create_database_connection():
    """Save an encrypted external database connection."""

    user_id = get_authenticated_user_id()

    if user_id is None:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "A valid JSON request body is required."
        }), 400

    validation_error = validate_connection_input(data)

    if validation_error:
        return jsonify({
            "status": "error",
            "message": validation_error
        }), 400

    try:
        connection_id = save_database_connection(
            user_id=user_id,
            connection_name=data["connection_name"].strip(),
            host=data["host"].strip(),
            port=data["port"],
            database_name=data["database_name"].strip(),
            db_username=data["db_username"].strip(),
            password=data["password"],
            use_ssl=data.get("use_ssl", False)
        )

        if not connection_id:
            return jsonify({
                "status": "error",
                "message": "Unable to save database connection."
            }), 500

        return jsonify({
            "status": "success",
            "message": "Database connection saved successfully.",
            "connection_id": connection_id
        }), 201

    except Exception:
        logger.exception("Failed to save database connection.")

        return jsonify({
            "status": "error",
            "message": "An internal error occurred."
        }), 500


@connection_bp.route("", methods=["GET"])
def get_database_connections():
    """List only the authenticated user's saved connections."""

    user_id = get_authenticated_user_id()

    if user_id is None:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    try:
        connections = list_database_connections(user_id)

        return jsonify({
            "status": "success",
            "connections": connections
        }), 200

    except Exception:
        logger.exception("Failed to retrieve database connections.")

        return jsonify({
            "status": "error",
            "message": "Unable to retrieve database connections."
        }), 500


@connection_bp.route(
    "/<int:connection_id>/test",
    methods=["POST"]
)
@limiter.limit("10 per minute")
def test_database_connection(connection_id):
    """Test an owned external database connection."""

    user_id = get_authenticated_user_id()

    if user_id is None:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    try:
        result = check_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        return jsonify({
            "status": "success",
            "message": "Database connection successful.",
            "connection": result
        }), 200

    except ExternalDatabaseConnectionError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        logger.exception("Unexpected database connection test failure.")

        return jsonify({
            "status": "error",
            "message": "Unable to test the database connection."
        }), 500


@connection_bp.route(
    "/<int:connection_id>",
    methods=["DELETE"]
)
@limiter.limit("10 per minute")
def delete_database_connection(connection_id):
    """Delete a connection belonging to the authenticated user."""

    user_id = get_authenticated_user_id()

    if user_id is None:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    try:
        deleted = remove_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        if not deleted:
            return jsonify({
                "status": "error",
                "message": "Database connection not found."
            }), 404

        return jsonify({
            "status": "success",
            "message": "Database connection deleted successfully."
        }), 200

    except Exception:
        logger.exception("Failed to delete database connection.")

        return jsonify({
            "status": "error",
            "message": "Unable to delete database connection."
        }), 500
