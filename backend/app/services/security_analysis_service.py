
import logging
import re

import mysql.connector

from app.models.security_finding_model import save_security_findings

from app.security.security_analyzer import (
    analyze_sql_security,
    classify_sensitive_column
)

from app.services.external_database_service import (
    open_external_database_connection,
    ExternalDatabaseConnectionError
)

from app.services.audit_service import log_audit_event


logger = logging.getLogger(__name__)

MAX_TABLES_TO_SCAN = 200
MAX_COLUMNS_TO_SCAN = 5000


class SecurityAnalysisError(Exception):
    """Raised when external database security analysis fails."""


def _validate_table_names(table_names):
    """Validate optional table names before metadata scanning."""

    if table_names is None:
        return None

    if (
        not isinstance(table_names, list)
        or len(table_names) > MAX_TABLES_TO_SCAN
    ):
        raise ValueError(
            f"table_names must be a list of at most "
            f"{MAX_TABLES_TO_SCAN} names."
        )

    for name in table_names:
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_$]{1,64}", name)
        ):
            raise ValueError(
                "Each table name must be a valid MySQL identifier."
            )

    return table_names


def _scan_sensitive_columns(cursor, table_names=None):
    """
    Discover potentially sensitive columns using metadata only.

    No actual table records or personal data are retrieved.
    """

    params = [MAX_COLUMNS_TO_SCAN]

    query = """
        SELECT
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        LIMIT %s
    """

    if table_names:
        placeholders = ", ".join(
            ["%s"] * len(table_names)
        )

        query = f"""
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME IN ({placeholders})
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            LIMIT %s
        """

        params = [
            *table_names,
            MAX_COLUMNS_TO_SCAN
        ]

    cursor.execute(query, tuple(params))

    rows = cursor.fetchall()
    findings = []

    for table_name, column_name, data_type in rows:

        classification = classify_sensitive_column(
            column_name,
            data_type
        )

        if not classification:
            continue

        category, severity = classification

        findings.append({
            "finding_type": "sensitive_data",
            "severity": severity,
            "title": (
                f"Potential {category.replace('_', ' ')} column"
            ),
            "description": (
                f"Column '{column_name}' in table '{table_name}' "
                "matches a name-based sensitive-data heuristic. "
                "No row values were read."
            ),
            "recommendation": (
                "Confirm whether the column contains sensitive data. "
                "Apply least-privilege access, encryption where "
                "appropriate, retention controls and masking."
            ),
            "affected_object": f"{table_name}.{column_name}"
        })

    return findings, len(rows)


def _analyze_grants(cursor):
    """
    Inspect privileges assigned to the connected MySQL account.
    """

    cursor.execute("SHOW GRANTS FOR CURRENT_USER()")

    grants = [
        str(row[0])
        for row in cursor.fetchall()
        if row
    ]

    combined_grants = "\n".join(grants)

    privilege_rules = [
        (
            r"\bALL PRIVILEGES\b",
            "critical",
            "Account has ALL PRIVILEGES"
        ),
        (
            r"\bGRANT OPTION\b",
            "high",
            "Account has GRANT OPTION"
        ),
        (
            r"\bFILE\b",
            "high",
            "Account has FILE privilege"
        ),
        (
            r"\bSUPER\b|\bSYSTEM_USER\b|\bSYSTEM_VARIABLES_ADMIN\b",
            "critical",
            "Account has elevated administrative privilege"
        ),
        (
            r"\bCREATE USER\b|\bROLE_ADMIN\b",
            "high",
            "Account can manage users or roles"
        ),
        (
            r"\bPROCESS\b",
            "medium",
            "Account has PROCESS privilege"
        ),
        (
            r"\bCREATE\b|\bALTER\b|\bDROP\b|\bINDEX\b",
            "medium",
            "Account has schema-modification privileges"
        )
    ]

    findings = []

    for pattern, severity, title in privilege_rules:

        if re.search(
            pattern,
            combined_grants,
            re.IGNORECASE
        ):
            findings.append({
                "finding_type": "database_privilege",
                "severity": severity,
                "title": title,
                "description": (
                    "The connected MySQL account's SHOW GRANTS "
                    "output includes a potentially excessive privilege."
                ),
                "recommendation": (
                    "Use a dedicated least-privilege account and "
                    "grant only permissions required for QueryWise "
                    "operations."
                ),
                "affected_object": "CURRENT_USER()"
            })

    if not grants:
        findings.append({
            "finding_type": "database_privilege",
            "severity": "info",
            "title": "No grant details returned",
            "description": (
                "MySQL returned no grant rows for the current account."
            ),
            "recommendation": (
                "Ask a database administrator to verify "
                "the account privileges."
            ),
            "affected_object": "CURRENT_USER()"
        })

    return findings, grants


def analyze_database_security(
    connection_id,
    user_id,
    query=None,
    table_names=None
):
    """
    Perform database security analysis for an authenticated user.

    Includes:
        1. SQL security analysis.
        2. MySQL privilege analysis.
        3. Sensitive-column discovery.
        4. Finding persistence.
        5. Audit logging.
    """

    if (
        isinstance(connection_id, bool)
        or not isinstance(connection_id, int)
        or connection_id <= 0
    ):
        raise ValueError(
            "A valid positive connection_id is required."
        )

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("Authentication is required.")

    table_names = _validate_table_names(table_names)

    findings = []

    # 1. Analyze the submitted SQL without executing it.
    if query is not None:
        sql_findings = analyze_sql_security(query)

        findings.extend(
            item.to_dict()
            for item in sql_findings
        )

    connection = None
    cursor = None

    columns_examined = 0
    grants = []

    try:
        # 2. Open the user's authorized external database connection.
        connection = open_external_database_connection(
            connection_id=connection_id,
            user_id=user_id
        )

        cursor = connection.cursor()

        # 3. Analyze database privileges.
        privilege_findings, grants = _analyze_grants(cursor)

        findings.extend(privilege_findings)

        # 4. Discover potentially sensitive columns.
        sensitive_findings, columns_examined = (
            _scan_sensitive_columns(
                cursor,
                table_names
            )
        )

        findings.extend(sensitive_findings)

    except ExternalDatabaseConnectionError:
        raise

    except (
        mysql.connector.Error,
        OSError
    ) as error:

        logger.warning(
            "Database security scan failed. "
            "Connection ID: %s, Error type: %s",
            connection_id,
            type(error).__name__
        )

        raise SecurityAnalysisError(
            "Unable to complete database security analysis."
        ) from error

    finally:
        # 5. Always release external database resources.
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception(
                    "Failed to close security scan cursor."
                )

        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                logger.exception(
                    "Failed to close security scan connection."
                )

    # 6. Persist findings in the QueryWise application database.
    saved_count = save_security_findings(
        user_id=user_id,
        connection_id=connection_id,
        findings=findings
    )

    # 7. Record the security analysis in audit logs.
    log_audit_event(
        action="database_security_analysis",
        user_id=user_id,
        entity_type="database_connection",
        entity_id=connection_id,
        details=(
            f"Security analysis completed. "
            f"Findings: {len(findings)}; "
            f"columns examined: {columns_examined}."
        )
    )

    # 8. Sort findings by severity.
    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "info": 4
    }

    findings.sort(
        key=lambda item: severity_order.get(
            item["severity"],
            5
        )
    )

    severity_counts = {
        level: sum(
            1
            for item in findings
            if item["severity"] == level
        )
        for level in (
            "critical",
            "high",
            "medium",
            "low",
            "info"
        )
    }

    return {
        "connection_id": connection_id,

        "database_scan": {
            "columns_examined": columns_examined,
            "privilege_grants_reviewed": len(grants),
            "sensitive_data_scan_reads_row_values": False
        },

        "findings_count": len(findings),
        "saved_findings_count": saved_count,
        "severity_counts": severity_counts,
        "findings": findings,

        "limitations": [
            (
                "SQL injection checks are heuristic "
                "and do not prove exploitability."
            ),
            (
                "Sensitive-data discovery uses column names "
                "and data types, not row contents."
            ),
            (
                "Privilege analysis reviews grants visible "
                "to the connected MySQL account."
            )
        ]
    }
