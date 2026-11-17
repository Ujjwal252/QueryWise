
import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv


# Resolve paths relative to the backend directory.
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=False)


def env_bool(name, default=False):
    """Read a boolean environment variable safely."""
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in ("true", "1", "yes", "on")


def resolve_backend_path(value):
    """Resolve a configured path relative to the backend directory."""
    if not value:
        return None

    path = Path(value)

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


class Config:
    # Flask security
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Encryption key for external database credentials
    DB_ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY")

    # Application settings
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("COOKIE_SECURE", False)

    # Allow local MySQL connections during development only
    ALLOW_LOCAL_DATABASE_HOSTS = env_bool(
        "ALLOW_LOCAL_DATABASE_HOSTS",
        False
    )

    # Session expiration: 30 minutes
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Refresh expiration when the user is active
    SESSION_REFRESH_EACH_REQUEST = True

    # MySQL application database configuration
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    # External MySQL TLS configuration
    MYSQL_SSL_CA = resolve_backend_path(
        os.getenv("MYSQL_SSL_CA", "certs/mysql-ca.pem")
    )

    MYSQL_SSL_VERIFY_IDENTITY = env_bool(
        "MYSQL_SSL_VERIFY_IDENTITY",
        True
    )

    # Frontend CORS configuration
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]
