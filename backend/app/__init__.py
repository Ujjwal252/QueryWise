
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from app.extensions import limiter, csrf

from app.routes.health_routes import health_bp
from app.routes.auth_routes import auth_bp
from app.routes.csrf_routes import csrf_bp
from app.routes.connection_routes import connection_bp
from app.routes.query_routes import query_bp
from app.routes.security_routes import security_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.history_routes import history_bp


def create_app():
    """Application factory for the QueryWise Flask backend."""

    app = Flask(__name__)
    app.config.from_object(Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing. Configure it in the backend/.env file."
        )

    app.json.sort_keys = app.config["JSON_SORT_KEYS"]
    app.config["WTF_CSRF_HEADERS"] = ["X-CSRFToken", "X-CSRF-Token"]

    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=True,
        allow_headers=[
            "Content-Type",
            "X-CSRFToken",
            "X-CSRF-Token"
        ]
    )

    limiter.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(connection_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(csrf_bp, url_prefix="/api/csrf")
    app.register_blueprint(query_bp, url_prefix="/api/queries")
    app.register_blueprint(security_bp, url_prefix="/api/security")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(history_bp, url_prefix="/api/history")

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "success",
            "message": "QueryWise backend is running!",
            "application": "QueryWise"
        }), 200

    return app
