from flask import Blueprint, jsonify, session

from app.utils.database import get_db_connection


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary", methods=["GET"])
def get_dashboard_summary():
    """Return dashboard counts scoped to the authenticated user."""

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Authentication required."
        }), 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT COUNT(*) AS total FROM database_connections WHERE user_id = %s",
            (user_id,)
        )
        database_connections = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM query_history WHERE user_id = %s",
            (user_id,)
        )
        queries_analyzed = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM optimization_reports AS reports
            INNER JOIN query_history AS history
                ON history.query_id = reports.query_id
            WHERE history.user_id = %s
            """,
            (user_id,)
        )
        optimizations_generated = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM security_findings WHERE user_id = %s",
            (user_id,)
        )
        security_findings = cursor.fetchone()["total"]

        return jsonify({
            "status": "success",
            "data": {
                "database_connections": database_connections,
                "queries_analyzed": queries_analyzed,
                "optimizations_generated": optimizations_generated,
                "security_findings": security_findings
            }
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to load dashboard statistics."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()
