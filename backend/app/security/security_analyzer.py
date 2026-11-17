
import re
from dataclasses import dataclass, asdict
from typing import Optional

from app.optimizer.sql_validator import validate_read_only_query


@dataclass
class SecurityFinding:
    finding_type: str
    severity: str
    title: str
    description: str
    recommendation: str
    affected_object: Optional[str] = None

    def to_dict(self):
        return asdict(self)


# Heuristics flag suspicious patterns; they do not prove exploitability.
SQL_RISK_PATTERNS = [
    (
        "SQLI001",
        "high",
        "Tautological condition pattern",
        re.compile(
            r"""(?is)(?:\bOR\b|\bAND\b)\s+(?:['"]?\w+['"]?\s*=\s*['"]?\w+['"]?)"""
        ),
        "A tautology-like condition may be used in an injection payload.",
        "Use parameterized statements and review how this SQL was constructed."
    ),
    (
        "SQLI002",
        "medium",
        "SQL comment marker detected",
        re.compile(r"(--[ \t]|/\*|#)"),
        "SQL comment syntax can alter dynamically constructed SQL.",
        "Never concatenate untrusted input into SQL; use parameterized statements."
    ),
    (
        "SQLI003",
        "high",
        "Stacked statement separator detected",
        re.compile(r";\s*\S"),
        "A statement separator followed by additional content was detected.",
        "Keep one statement per request and use parameterized statements."
    ),
    (
        "SQLI004",
        "medium",
        "UNION query detected",
        re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.I),
        "UNION is valid SQL but can also appear in injection payloads.",
        "Review the query source and ensure user-supplied values are parameterized."
    ),
    (
        "SQLI005",
        "medium",
        "Information-schema access detected",
        re.compile(r"\bINFORMATION_SCHEMA\b", re.I),
        "The query references database metadata.",
        "Restrict metadata access to trusted workflows and least-privilege accounts."
    ),
]


def analyze_sql_security(query: Optional[str]):
    findings = []

    if query is None:
        return findings

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")

    if len(query) > 10000:
        raise ValueError("query exceeds the maximum allowed length.")

    validation = validate_read_only_query(query)

    if not validation.is_valid:
        findings.append(
            SecurityFinding(
                finding_type="sql_policy",
                severity="high",
                title="Read-only SQL policy violation",
                description=(
                    validation.error
                    or "The query failed read-only validation."
                ),
                recommendation=(
                    "Use one approved SELECT statement and remove "
                    "prohibited constructs."
                )
            )
        )

    for (
        rule_id,
        severity,
        title,
        pattern,
        description,
        recommendation
    ) in SQL_RISK_PATTERNS:

        if pattern.search(query):
            findings.append(
                SecurityFinding(
                    finding_type="sql_injection",
                    severity=severity,
                    title=title,
                    description=(
                        f"{description} Rule: {rule_id}. "
                        "This is a heuristic warning, not proof of SQL injection."
                    ),
                    recommendation=recommendation
                )
            )

    return findings


SENSITIVE_COLUMN_RULES = [
    (
        "authentication_secret",
        "critical",
        re.compile(
            r"(password|passwd|secret|api_key|access_token|refresh_token)",
            re.I
        )
    ),
    (
        "payment_card",
        "high",
        re.compile(
            r"(card_number|credit_card|debit_card|pan_number)",
            re.I
        )
    ),
    (
        "government_identifier",
        "high",
        re.compile(
            r"(ssn|social_security|passport|national_id|aadhaar)",
            re.I
        )
    ),
    (
        "bank_account",
        "high",
        re.compile(
            r"(bank_account|account_number|iban|ifsc)",
            re.I
        )
    ),
    (
        "contact_information",
        "medium",
        re.compile(
            r"(^|_)(email|phone|mobile|telephone)(_|$)",
            re.I
        )
    ),
    (
        "financial_information",
        "medium",
        re.compile(
            r"(salary|income|tax_id)",
            re.I
        )
    ),
    (
        "personal_information",
        "low",
        re.compile(
            r"(^|_)(first_name|last_name|full_name|date_of_birth|dob|address)(_|$)",
            re.I
        )
    ),
]


def classify_sensitive_column(column_name, data_type):
    name = str(column_name or "")

    for category, severity, pattern in SENSITIVE_COLUMN_RULES:
        if pattern.search(name):
            return category, severity

    if (
        str(data_type or "").lower() == "json"
        and re.search(
            r"(profile|personal|customer|user|payment)",
            name,
            re.I
        )
    ):
        return "potential_personal_data", "low"

    return None
