
import logging
import math
import statistics
from typing import Any, Dict, List

from app.services.performance_service import (
    benchmark_query_pair,
    PerformanceServiceError
)

from app.services.query_equivalence_service import (
    compare_query_results,
    QueryEquivalenceServiceError
)

from app.models.query_history_model import save_query_history


logger = logging.getLogger(__name__)

CONSISTENCY_THRESHOLD = 0.80


class QueryComparisonError(Exception):
    """Raised when query performance comparison fails."""


def _record_comparison_history(
    user_id,
    connection_id,
    original_query,
    optimized_query,
    original_result,
    optimized_result
):
    """
    Save both successfully benchmarked queries to query history.

    History persistence is deliberately non-critical:
    a database history failure must not invalidate a completed
    performance comparison.
    """

    history_entries = [
        {
            "query": original_query,
            "execution_time_ms": (
                original_result["statistics"]["average_ms"]
            ),
            "rows_returned": original_result["rows_returned"]
        },
        {
            "query": optimized_query,
            "execution_time_ms": (
                optimized_result["statistics"]["average_ms"]
            ),
            "rows_returned": optimized_result["rows_returned"]
        }
    ]

    saved_count = 0

    for entry in history_entries:
        try:
            save_query_history(
                user_id=user_id,
                connection_id=connection_id,
                query=entry["query"],
                query_type="SELECT",
                execution_time_ms=entry["execution_time_ms"],
                rows_returned=entry["rows_returned"],
                execution_status="success",
                error_message=None
            )

            saved_count += 1

        except Exception:
            logger.exception(
                "Unable to save a query comparison history record."
            )

    if saved_count != len(history_entries):
        logger.warning(
            "Query comparison completed, but only %s of %s "
            "history records were saved.",
            saved_count,
            len(history_entries)
        )


def _analyze_paired_performance(
    original_times: List[float],
    optimized_times: List[float]
) -> Dict[str, Any]:
    """
    Analyze paired execution measurements.

    A positive difference means the optimized query was faster.
    A negative difference means the optimized query was slower.

    At least 80% of rounds must favor the optimized query for a
    consistent-improvement assessment.
    """

    if (
        not original_times
        or len(original_times) != len(optimized_times)
    ):
        raise QueryComparisonError(
            "Benchmark measurements are missing or inconsistent."
        )

    paired_differences = [
        round(original - optimized, 3)
        for original, optimized in zip(
            original_times,
            optimized_times
        )
    ]

    faster_rounds = sum(
        difference > 0
        for difference in paired_differences
    )

    slower_rounds = sum(
        difference < 0
        for difference in paired_differences
    )

    equal_rounds = sum(
        difference == 0
        for difference in paired_differences
    )

    total_rounds = len(paired_differences)

    faster_percentage = round(
        faster_rounds / total_rounds * 100,
        2
    )

    slower_percentage = round(
        slower_rounds / total_rounds * 100,
        2
    )

    median_paired_improvement_ms = round(
        statistics.median(paired_differences),
        3
    )

    paired_improvement_percentages = []

    for original, optimized in zip(
        original_times,
        optimized_times
    ):
        if original > 0:
            percentage = (
                (original - optimized) / original
            ) * 100

            paired_improvement_percentages.append(percentage)

    median_paired_improvement_percentage = (
        round(
            statistics.median(paired_improvement_percentages),
            2
        )
        if paired_improvement_percentages
        else 0.0
    )

    required_rounds = math.ceil(
        total_rounds * CONSISTENCY_THRESHOLD
    )

    if (
        faster_rounds >= required_rounds
        and median_paired_improvement_ms > 0
    ):
        performance_reliability = "consistent_improvement"

    elif (
        slower_rounds >= required_rounds
        and median_paired_improvement_ms < 0
    ):
        performance_reliability = "performance_regression"

    else:
        performance_reliability = "inconclusive"

    return {
        "total_rounds": total_rounds,
        "faster_rounds": faster_rounds,
        "slower_rounds": slower_rounds,
        "equal_rounds": equal_rounds,
        "faster_rounds_percentage": faster_percentage,
        "slower_rounds_percentage": slower_percentage,
        "paired_improvements_ms": paired_differences,
        "median_paired_improvement_ms": median_paired_improvement_ms,
        "median_paired_improvement_percentage": (
            median_paired_improvement_percentage
        ),
        "consistency_threshold_percentage": (
            CONSISTENCY_THRESHOLD * 100
        ),
        "required_rounds_for_consistency": required_rounds,
        "performance_reliability": performance_reliability
    }


def compare_query_performance(
    connection_id: int,
    user_id: int,
    original_query: str,
    optimized_query: str,
    iterations: int = 5,
    warmup_runs: int = 1
) -> Dict[str, Any]:
    """
    Compare query performance using alternating benchmark execution.

    The service:
    1. Benchmarks both queries using alternating execution order.
    2. Analyzes paired performance measurements.
    3. Independently validates actual result equivalence.
    4. Records both queries in query history.
    5. Reports whether the optimization is consistently faster
       and returns equivalent results.
    """

    if not isinstance(original_query, str) or not original_query.strip():
        raise ValueError("A non-empty original query is required.")

    if not isinstance(optimized_query, str) or not optimized_query.strip():
        raise ValueError("A non-empty optimized query is required.")

    if original_query.strip() == optimized_query.strip():
        raise ValueError(
            "Original and optimized queries must be different."
        )

    try:
        # Step 1: Run alternating paired benchmarks.
        benchmark_result = benchmark_query_pair(
            connection_id=connection_id,
            user_id=user_id,
            original_query=original_query,
            candidate_query=optimized_query,
            iterations=iterations,
            warmup_runs=warmup_runs
        )

        original_result = benchmark_result["original_query"]
        optimized_result = benchmark_result["candidate_query"]

        # Step 2: Analyze paired execution measurements.
        paired_analysis = _analyze_paired_performance(
            original_result["execution_times_ms"],
            optimized_result["execution_times_ms"]
        )

        # Step 3: Compare actual result sets.
        equivalence_result = compare_query_results(
            connection_id=connection_id,
            user_id=user_id,
            original_query=original_query,
            candidate_query=optimized_query
        )

    except (ValueError, PerformanceServiceError):
        raise

    except QueryEquivalenceServiceError as exc:
        logger.exception(
            "Query equivalence validation failed during comparison."
        )

        raise QueryComparisonError(
            "Performance measurement completed, but result equivalence "
            "could not be validated."
        ) from exc

    except QueryComparisonError:
        raise

    except Exception as exc:
        logger.exception("Query performance comparison failed.")

        raise QueryComparisonError(
            "Unable to compare query performance."
        ) from exc

    # Step 4: Calculate overall performance statistics.
    original_average = original_result["statistics"]["average_ms"]

    optimized_average = optimized_result["statistics"]["average_ms"]

    time_difference = round(
        original_average - optimized_average,
        3
    )

    if original_average > 0:
        improvement_percentage = round(
            (time_difference / original_average) * 100,
            2
        )
    else:
        improvement_percentage = 0.0

    if optimized_average < original_average:
        performance_status = "faster"

    elif optimized_average > original_average:
        performance_status = "slower"

    else:
        performance_status = "no_change"

    # Step 5: Assess correctness and performance together.
    equivalence_verified = equivalence_result["equivalence_verified"]

    equivalent = equivalence_result["equivalent"]

    performance_reliability = paired_analysis[
        "performance_reliability"
    ]

    if not equivalence_verified:
        optimization_assessment = "equivalence_not_verified"

    elif not equivalent:
        optimization_assessment = "not_equivalent"

    elif performance_reliability == "consistent_improvement":
        optimization_assessment = "faster_and_equivalent"

    elif performance_reliability == "performance_regression":
        optimization_assessment = "performance_regression"

    else:
        optimization_assessment = "inconclusive"

    optimization_successful = (
        equivalence_verified
        and equivalent
        and performance_reliability == "consistent_improvement"
    )

    # Step 6: Record both successfully benchmarked queries.
    # History storage failures do not invalidate the comparison.
    _record_comparison_history(
        user_id=user_id,
        connection_id=connection_id,
        original_query=original_query,
        optimized_query=optimized_query,
        original_result=original_result,
        optimized_result=optimized_result
    )

    # Step 7: Return the complete comparison report.
    return {
        "connection_id": connection_id,

        "comparison_settings": {
            "iterations": iterations,
            "warmup_runs": warmup_runs,
            "benchmark_method": "alternating",
            "execution_order": benchmark_result["execution_order"]
        },

        "original_query": {
            "sql": original_query,
            "statistics": original_result["statistics"],
            "execution_times_ms": original_result["execution_times_ms"],
            "rows_returned": original_result["rows_returned"]
        },

        "optimized_query": {
            "sql": optimized_query,
            "statistics": optimized_result["statistics"],
            "execution_times_ms": optimized_result["execution_times_ms"],
            "rows_returned": optimized_result["rows_returned"]
        },

        "comparison": {
            "time_difference_ms": time_difference,
            "improvement_percentage": improvement_percentage,
            "performance_status": performance_status,

            "row_count_match": (
                original_result["rows_returned"]
                == optimized_result["rows_returned"]
            ),

            "result_equivalence_verified": equivalence_verified,
            "result_equivalent": equivalent,

            "result_order_matters": (
                equivalence_result["result_order_matters"]
            ),

            "column_names_match": (
                equivalence_result["column_names_match"]
            ),

            "equivalence_mismatch_reason": (
                equivalence_result["mismatch_reason"]
            ),

            "paired_performance_analysis": paired_analysis,

            "optimization_assessment": optimization_assessment,
            "optimization_successful": optimization_successful
        }
    }
