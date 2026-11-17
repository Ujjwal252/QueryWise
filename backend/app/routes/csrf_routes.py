
from flask import Blueprint, jsonify
from flask_wtf.csrf import generate_csrf


csrf_bp = Blueprint("csrf", __name__)


@csrf_bp.route("/token", methods=["GET"])
def get_csrf_token():
    """
    Generate a CSRF token for the frontend.

    The token is returned in JSON and can be included
    in the X-CSRFToken header of state-changing requests.
    """

    token = generate_csrf()

    return jsonify({
        "status": "success",
        "csrf_token": token
    }), 200
