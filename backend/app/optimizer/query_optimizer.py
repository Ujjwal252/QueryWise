
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from sqlglot import exp, parse_one

from app.optimizer.sql_parser import parse_sql
from app.optimizer.sql_validator import validate_read_only_query


@dataclass
class OptimizationResult:
    """Structured result returned by the SQL optimization engine."""

    success: bool
    original_query: str
    optimized_query: Optional[str] = None
    techniques: List[str] = field(default_factory=list)
    explanation: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------
# 1. CONDITION HANDLING
# ---------------------------------------------------------

def flatten_and_conditions(
    expression: exp.Expression,
) -> List[exp.Expression]:
    """
    Flatten nested AND expressions.

    OR expressions are never flattened.

    Example:
        A AND (A AND B)

    Becomes:
        [A, A, B]
    """

    if isinstance(expression, exp.Paren):
        inner = expression.this

        if isinstance(inner, exp.And):
            return flatten_and_conditions(inner)

    if isinstance(expression, exp.And):
        return (
            flatten_and_conditions(expression.this)
            + flatten_and_conditions(expression.expression)
        )

    return [expression]


def rebuild_and_expression(
    conditions: List[exp.Expression],
) -> Optional[exp.Expression]:
    """Rebuild an AND expression from a list of conditions."""

    if not conditions:
        return None

    result = conditions[0].copy()

    for condition in conditions[1:]:
        result = exp.and_(result, condition.copy())

    return result


# ---------------------------------------------------------
# 2. REDUNDANT CONDITION REMOVAL
# ---------------------------------------------------------

def remove_duplicate_and_conditions(
    statement: exp.Expression,
) -> bool:
    """
    Remove identical repeated conditions from WHERE clauses.

    Comparison is based on SQLGlot's MySQL SQL representation.
    String literals are not lowercased or otherwise normalized.
    """

    changed = False

    for select in statement.find_all(exp.Select):
        where_clause = select.args.get("where")

        if where_clause is None:
            continue

        conditions = flatten_and_conditions(where_clause.this)

        unique_conditions = []
        seen_conditions = set()

        for condition in conditions:
            condition_key = condition.sql(dialect="mysql")

            if condition_key not in seen_conditions:
                seen_conditions.add(condition_key)
                unique_conditions.append(condition.copy())

        if len(unique_conditions) < len(conditions):
            optimized_condition = rebuild_and_expression(
                unique_conditions
            )

            where_clause.set("this", optimized_condition)
            changed = True

    return changed


# ---------------------------------------------------------
# 3. NUMERIC CONSTANT EVALUATION
# ---------------------------------------------------------

def evaluate_numeric_constant_comparison(
    expression: exp.Expression,
) -> Optional[bool]:
    """
    Evaluate comparisons containing two numeric literals.

    Returns:
        True  - comparison is always true
        False - comparison is always false
        None  - comparison is unsupported
    """

    supported_comparisons = {
        exp.EQ: lambda left, right: left == right,
        exp.NEQ: lambda left, right: left != right,
        exp.GT: lambda left, right: left > right,
        exp.GTE: lambda left, right: left >= right,
        exp.LT: lambda left, right: left < right,
        exp.LTE: lambda left, right: left <= right,
    }

    comparison_function = None

    for expression_type, function in supported_comparisons.items():
        if isinstance(expression, expression_type):
            comparison_function = function
            break

    if comparison_function is None:
        return None

    left = expression.this
    right = expression.expression

    if not isinstance(left, exp.Literal):
        return None

    if not isinstance(right, exp.Literal):
        return None

    if left.is_string or right.is_string:
        return None

    try:
        left_value = Decimal(left.this)
        right_value = Decimal(right.this)

        if not left_value.is_finite() or not right_value.is_finite():
            return None

        return comparison_function(left_value, right_value)

    except (InvalidOperation, ValueError, TypeError):
        return None


# ---------------------------------------------------------
# 4. CONSTANT CONDITION SIMPLIFICATION
# ---------------------------------------------------------

def simplify_numeric_constant_conditions(
    statement: exp.Expression,
) -> bool:
    """
    Simplify numeric comparisons inside WHERE AND expressions.

    TRUE conditions are removed.
    FALSE conditions make the WHERE clause return no rows.

    OR expressions and unsupported comparisons are preserved.
    """

    changed = False

    for select in statement.find_all(exp.Select):
        where_clause = select.args.get("where")

        if where_clause is None:
            continue

        conditions = flatten_and_conditions(where_clause.this)

        remaining_conditions = []
        select_changed = False
        always_false = False

        for condition in conditions:
            result = evaluate_numeric_constant_comparison(condition)

            if result is True:
                select_changed = True
                continue

            if result is False:
                select_changed = True
                always_false = True
                break

            remaining_conditions.append(condition.copy())

        if not select_changed:
            continue

        changed = True

        if always_false:
            where_clause.set(
                "this",
                exp.EQ(
                    this=exp.Literal.number(1),
                    expression=exp.Literal.number(0),
                ),
            )
            continue

        if not remaining_conditions:
            select.set("where", None)
            continue

        optimized_condition = rebuild_and_expression(
            remaining_conditions
        )

        where_clause.set("this", optimized_condition)

    return changed


# ---------------------------------------------------------
# 5. REDUNDANT PARENTHESES REMOVAL
# ---------------------------------------------------------

def remove_redundant_parentheses(
    statement: exp.Expression,
) -> bool:
    """
    Remove parentheses surrounding simple predicates.

    Compound AND, OR and NOT expressions retain their grouping.
    Repeatedly process the AST to remove nested redundant pairs.
    """

    simple_predicates = (
        exp.EQ,
        exp.NEQ,
        exp.GT,
        exp.GTE,
        exp.LT,
        exp.LTE,
        exp.Like,
        exp.ILike,
        exp.In,
        exp.Is,
        exp.Between,
    )

    changed = False

    for select in statement.find_all(exp.Select):
        where_clause = select.args.get("where")

        if where_clause is None:
            continue

        while True:
            parentheses = list(
                where_clause.find_all(exp.Paren)
            )

            replacement_found = False

            for parenthesis in parentheses:
                inner_expression = parenthesis.this

                if isinstance(inner_expression, simple_predicates):
                    parenthesis.replace(inner_expression.copy())
                    changed = True
                    replacement_found = True
                    break

            if not replacement_found:
                break

    return changed


# ---------------------------------------------------------
# 6. MAIN OPTIMIZATION ENGINE
# ---------------------------------------------------------

def optimize_query(query: str) -> OptimizationResult:
    """
    Apply all currently supported conservative SQL optimizations.

    Supported techniques:
        1. Redundant condition removal.
        2. Numeric constant-condition simplification.
        3. Redundant parentheses removal.
        4. Nested AND condition simplification.
        5. MySQL SQL normalization.

    The function never executes SQL or modifies a database.
    """

    if not isinstance(query, str):
        return OptimizationResult(
            success=False,
            original_query="",
            error="SQL query must be a string.",
        )

    if not query.strip():
        return OptimizationResult(
            success=False,
            original_query=query,
            error="SQL query cannot be empty.",
        )

    # Validate the original SQL.
    validation_result = validate_read_only_query(query)

    if not validation_result.is_valid:
        return OptimizationResult(
            success=False,
            original_query=query,
            error=(
                validation_result.error
                or "Query failed read-only validation."
            ),
        )

    # Parse the original SQL.
    parse_result = parse_sql(query)

    if not parse_result.success:
        return OptimizationResult(
            success=False,
            original_query=query,
            error=parse_result.error,
        )

    try:
        statement = parse_one(query, read="mysql")

        if not isinstance(statement, exp.Select):
            return OptimizationResult(
                success=False,
                original_query=query,
                error="Only SELECT statements are supported.",
            )

        original_sql = statement.sql(dialect="mysql")

        techniques = []
        explanations = []

        # Optimization 1: Remove duplicate conditions.
        if remove_duplicate_and_conditions(statement):
            techniques.append("redundant_condition_removal")

            explanations.append(
                "Removed identical repeated conditions from WHERE clauses."
            )

        # Optimization 2: Simplify numeric constant comparisons.
        if simplify_numeric_constant_conditions(statement):
            techniques.append("constant_condition_simplification")

            explanations.append(
                "Simplified numeric constant comparisons in WHERE clauses."
            )

        # Optimization 3: Remove redundant parentheses.
        if remove_redundant_parentheses(statement):
            techniques.append("redundant_parentheses_removal")

            explanations.append(
                "Removed unnecessary parentheses around simple predicates."
            )

        # Generate normalized MySQL SQL.
        optimized_sql = statement.sql(dialect="mysql")

        # Validate the generated SQL again.
        optimized_validation = validate_read_only_query(optimized_sql)

        if not optimized_validation.is_valid:
            return OptimizationResult(
                success=False,
                original_query=original_sql,
                error=(
                    "Generated SQL failed read-only validation. "
                    "The optimization result was not returned."
                ),
            )

        explanation = (
            " ".join(explanations)
            if explanations
            else "No supported optimization opportunities found."
        )

        return OptimizationResult(
            success=True,
            original_query=original_sql,
            optimized_query=optimized_sql,
            techniques=techniques,
            explanation=explanation,
        )

    except Exception:
        return OptimizationResult(
            success=False,
            original_query=query,
            error="An unexpected error occurred during SQL optimization.",
        )
