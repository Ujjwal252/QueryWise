
import re

from flask import (
    Blueprint,
    jsonify,
    request,
    current_app,
    session
)

from app.extensions import limiter

from app.models.user_model import (
    create_user,
    authenticate_user,
    get_user_by_id
)

from app.services.audit_service import log_audit_event


auth_bp = Blueprint("auth", __name__)


def record_auth_event(
    action,
    user_id=None,
    details=None
):
    """Record an authentication event without exposing sensitive data."""

    log_audit_event(
        action=action,
        user_id=user_id,
        entity_type="user" if user_id is not None else "authentication",
        entity_id=user_id,
        details=details,
        ip_address=request.remote_addr
    )


def validate_registration(data):
    """Validate registration input."""

    if not isinstance(data, dict):
        return "Request body must be a JSON object."

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name")

    if not all(
        isinstance(value, str)
        for value in (username, email, password)
    ):
        return "Username, email and password must be strings."

    username = username.strip()
    email = email.strip().lower()

    if not username or not email or not password:
        return "Username, email and password are required."

    if len(username) < 3 or len(username) > 50:
        return "Username must contain 3 to 50 characters."

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return "Username contains invalid characters."

    if len(email) > 120 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        return "Please provide a valid email address."

    if len(password) < 8:
        return "Password must contain at least 8 characters."

    if len(password.encode("utf-8")) > 72:
        return "Password must not exceed 72 UTF-8 bytes."

    if full_name is not None:
        if not isinstance(full_name, str):
            return "Full name must be a string."

        if len(full_name.strip()) > 100:
            return "Full name must not exceed 100 characters."

    return None


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():
    """Register a new QueryWise user."""

    data = request.get_json(silent=True)

    validation_error = validate_registration(data)

    if validation_error:
        return jsonify({
            "status": "error",
            "message": validation_error
        }), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()
    password = data["password"]

    full_name = data.get("full_name")

    if full_name is not None:
        full_name = full_name.strip() or None

    try:
        user_id = create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name
        )

        if user_id is None:
            return jsonify({
                "status": "error",
                "message": "Username or email is already registered."
            }), 409

        record_auth_event(
            action="USER_REGISTERED",
            user_id=user_id,
            details="A new user account was created."
        )

        return jsonify({
            "status": "success",
            "message": "User registered successfully.",
            "user": {
                "user_id": user_id,
                "username": username,
                "email": email,
                "full_name": full_name
            }
        }), 201

    except Exception:
        current_app.logger.exception("User registration failed.")

        return jsonify({
            "status": "error",
            "message": "Registration could not be completed."
        }), 500


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    """Authenticate a user and create a permanent session."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must be a JSON object."
        }), 400

    identifier = data.get("identifier")
    password = data.get("password")

    if not isinstance(identifier, str) or not isinstance(password, str):
        return jsonify({
            "status": "error",
            "message": "Username/email and password are required."
        }), 400

    identifier = identifier.strip()

    if not identifier or not password:
        return jsonify({
            "status": "error",
            "message": "Username/email and password are required."
        }), 400

    if len(password.encode("utf-8")) > 72:
        record_auth_event(
            action="LOGIN_FAILED",
            details="Login failed due to invalid credentials."
        )

        return jsonify({
            "status": "error",
            "message": "Invalid username/email or password."
        }), 401

    try:
        user = authenticate_user(identifier, password)

        if user is None:
            record_auth_event(
                action="LOGIN_FAILED",
                details="Login failed due to invalid credentials."
            )

            return jsonify({
                "status": "error",
                "message": "Invalid username/email or password."
            }), 401

        # Clear any previous session to prevent session fixation.
        session.clear()

        # Mark the session as permanent (30-minute lifetime).
        session.permanent = True

        # Store the authenticated user's ID.
        session["user_id"] = user["user_id"]

        record_auth_event(
            action="LOGIN_SUCCESS",
            user_id=user["user_id"],
            details="User logged in successfully."
        )

        return jsonify({
            "status": "success",
            "message": "Login successful.",
            "user": user
        }), 200

    except Exception:
        current_app.logger.exception("User login failed.")

        return jsonify({
            "status": "error",
            "message": "Login could not be completed."
        }), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the current user's session."""

    user_id = session.get("user_id")

    record_auth_event(
        action="LOGOUT",
        user_id=user_id,
        details="User logged out."
    )

    session.clear()

    return jsonify({
        "status": "success",
        "message": "Logout successful."
    }), 200


@auth_bp.route("/me", methods=["GET"])
def current_user():
    """Return the currently authenticated user's profile."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    try:
        user = get_user_by_id(user_id)

        if user is None:
            session.clear()

            return jsonify({
                "status": "error",
                "message": "User account not found or inactive."
            }), 401

        return jsonify({
            "status": "success",
            "user": user
        }), 200

    except Exception:
        current_app.logger.exception(
            "User profile retrieval failed."
        )

        return jsonify({
            "status": "error",
            "message": "Unable to retrieve user profile."
        }), 500
