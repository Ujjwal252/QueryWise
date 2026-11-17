
import pytest

from app.optimizer.execution_plan_analyzer import (
    analyze_execution_plan
)


@pytest.fixture
def full_scan_plan():
    return {
        "query_block": {
            "select_id": 1,
            "cost_info": {
                "query_cost": "0.75"
            },
            "table": {
                "table_name": "employees",
                "access_type": "ALL",
                "possible_keys": [],
                "rows_examined_per_scan": 5,
                "rows_produced_per_join": 1,
                "filtered": "20.00",
                "cost_info": {
                    "read_cost": "0.65",
                    "eval_cost": "0.10",
                    "prefix_cost": "0.75"
                }
            }
        }
    }


def test_analyzes_full_table_scan(full_scan_plan):
    result = analyze_execution_plan(full_scan_plan)

    assert result["database_engine"] == "MySQL"
    assert result["plan_format"] == "JSON"

    assert result["summary"]["tables_accessed"] == 1
    assert result["summary"]["estimated_rows_examined"] == 5.0

    assert result["tables"][0]["access_type"] == "ALL"
    assert result["tables"][0]["selected_key"] is None


def test_generates_full_scan_finding(full_scan_plan):
    result = analyze_execution_plan(full_scan_plan)

    findings = result["findings"]

    assert len(findings) == 1
    assert findings[0]["rule_id"] == "EP001"
    assert findings[0]["severity"] == "info"


def test_large_full_scan_generates_medium_severity():
    plan = {
        "query_block": {
            "cost_info": {
                "query_cost": "150.00"
            },
            "table": {
                "table_name": "orders",
                "access_type": "ALL",
                "rows_examined_per_scan": 5000,
                "rows_produced_per_join": 500,
                "filtered": "10.00",
                "cost_info": {
                    "read_cost": "100.00",
                    "eval_cost": "50.00",
                    "prefix_cost": "150.00"
                }
            }
        }
    }

    result = analyze_execution_plan(plan)

    assert result["findings"][0]["severity"] == "medium"
    assert result["findings"][0]["rule_id"] == "EP001"


def test_detects_selected_index():
    plan = {
        "query_block": {
            "table": {
                "table_name": "employees",
                "access_type": "ref",
                "possible_keys": ["idx_department"],
                "key": "idx_department",
                "rows_examined_per_scan": 2,
                "rows_produced_per_join": 2,
                "filtered": "100.00"
            }
        }
    }

    result = analyze_execution_plan(plan)

    assert result["tables"][0]["selected_key"] == "idx_department"

    assert any(
        finding["rule_id"] == "EP002"
        for finding in result["findings"]
    )


def test_detects_possible_but_unused_index():
    plan = {
        "query_block": {
            "table": {
                "table_name": "employees",
                "access_type": "ALL",
                "possible_keys": ["idx_department"],
                "rows_examined_per_scan": 5,
                "rows_produced_per_join": 1,
                "filtered": "20.00"
            }
        }
    }

    result = analyze_execution_plan(plan)

    assert any(
        finding["rule_id"] == "EP003"
        for finding in result["findings"]
    )


def test_handles_missing_optional_cost_information():
    plan = {
        "query_block": {
            "table": {
                "table_name": "employees",
                "access_type": "ALL"
            }
        }
    }

    result = analyze_execution_plan(plan)

    assert result["summary"]["tables_accessed"] == 1
    assert result["summary"]["estimated_rows_examined"] == 0
    assert result["summary"]["estimated_query_cost"] is None


def test_rejects_non_dictionary_execution_plan():
    with pytest.raises(ValueError):
        analyze_execution_plan([])


def test_rejects_empty_execution_plan():
    with pytest.raises(ValueError):
        analyze_execution_plan({})


def test_rejects_missing_query_block():
    with pytest.raises(ValueError):
        analyze_execution_plan({
            "other": {}
        })
