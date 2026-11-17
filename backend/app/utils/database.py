
import mysql.connector

from config import Config


def get_db_connection():
    """
    Create and return a MySQL database connection
    using the application's environment configuration.

    Raises:
        ValueError: If required database settings are missing.
        mysql.connector.Error: If MySQL connection fails.
    """

    required_settings = {
        "DB_HOST": Config.DB_HOST,
        "DB_NAME": Config.DB_NAME,
        "DB_USER": Config.DB_USER,
        "DB_PASSWORD": Config.DB_PASSWORD,
    }

    missing_settings = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing_settings:
        raise ValueError(
            "Missing database configuration: "
            + ", ".join(missing_settings)
        )

    return mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        connection_timeout=5,
        charset="utf8mb4",
        use_unicode=True,
        autocommit=False
    )
