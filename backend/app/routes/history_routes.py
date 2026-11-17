
import logging

from flask import Blueprint, jsonify, request, session

from app.models.query_history_model import get_user_query_history


logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__)

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

VALID_QUERY_TYPES = {"SELECT", "INSERT", "UPDATE", "DELETE"}
VALID_STATUSES = {"pending", "success", "failed"}


def _parse_positive_integer(value, field_name, default):
    """Parse a positive integer from a query-string parameter."""

    if value is None:
        return default

    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid integer.")

    if parsed_value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")

    return parsed_value


@history_bp.route("", methods=["GET"])
def get_query_history():
    """Return the authenticated user's paginated query history."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    try:
        page = _parse_positive_integer(
            request.args.get("page"),
            "page",
            DEFAULT_PAGE
        )

        per_page = _parse_positive_integer(
            request.args.get("per_page"),
            "per_page",
            DEFAULT_PER_PAGE
        )

        if per_page > MAX_PER_PAGE:
            raise ValueError(
                f"per_page cannot exceed {MAX_PER_PAGE}."
            )

        query_type = request.args.get("query_type", "").strip().upper()
        execution_status = (
            request.args.get("execution_status", "").strip().lower()
        )

        if query_type and query_type not in VALID_QUERY_TYPES:
            raise ValueError("Invalid query type filter.")

        if execution_status and execution_status not in VALID_STATUSES:
            raise ValueError("Invalid execution status filter.")

        history = get_user_query_history(
            user_id=user_id,
            page=page,
            per_page=per_page,
            query_type=query_type or None,
            execution_status=execution_status or None
        )

        return jsonify({
            "status": "success",
            "data": history
        }), 200

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 400

    except Exception:
        logger.exception(
            "Unable to retrieve query history for user_id=%s",
            user_id
        )

        return jsonify({
            "status": "error",
            "message": "Unable to retrieve query history."
        }), 500
