import re
import statistics
from collections import defaultdict
from src.utils.db import get_raw_metrics_for_scenario, get_raw_metrics_for_run, insert_scenario_summary


def calculate_percentile(values: list[float], percentile: float) -> float:
    """
    Calculate the given percentile of a list of values.

    Args:
        values: List of numeric values
        percentile: Percentile as a decimal (0.0 to 1.0) or integer (1 to 99)

    Returns:
        The calculated percentile value
    """
    if not values:
        return 0.0

    # Convert integer percentile (1-99) to decimal (0.01-0.99)
    if percentile >= 1:
        percentile = percentile / 100.0

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def parse_percentile_aggregation(aggregation: str) -> int | None:
    """
    Parse percentile value from aggregation string like 'p99', 'p50', 'p1'.

    Args:
        aggregation: String like 'p99', 'p50', 'p1', etc.

    Returns:
        Integer percentile value (1-99) or None if not a percentile aggregation
    """
    if not aggregation:
        return None

    match = re.match(r'^p(\d{1,2})$', aggregation.lower())
    if match:
        value = int(match.group(1))
        if 1 <= value <= 99:
            return value
    return None


def aggregate_metrics_for_run(run_id: str) -> dict[str, float]:
    """
    Aggregate metrics for a single run (per_iteration scope).
    Returns average value per metric for the run.
    """
    raw_metrics = get_raw_metrics_for_run(run_id)
    metrics_by_name = defaultdict(list)

    for metric in raw_metrics:
        try:
            value = float(metric["metric_value"])
            if value == -1:
                continue  # Skip error sentinel values
            metrics_by_name[metric["metric_name"]].append(value)
        except (ValueError, TypeError):
            continue

    aggregated = {}
    for metric_name, values in metrics_by_name.items():
        if values:
            aggregated[metric_name] = statistics.mean(values)

    return aggregated


def aggregate_metrics_for_scenario(scenario_id: str, percentile: int = 50) -> dict[str, dict]:
    """
    Aggregate metrics for an entire scenario (across all runs).
    Returns full statistics per metric.

    Args:
        scenario_id: UUID of the scenario
        percentile: Percentile value to calculate (1-99), default 50

    Returns:
        Dictionary mapping metric names to their aggregated statistics
    """
    raw_metrics = get_raw_metrics_for_scenario(scenario_id)
    metrics_by_name = defaultdict(list)

    for metric in raw_metrics:
        try:
            value = float(metric["metric_value"])
            if value == -1:
                continue  # Skip error sentinel values
            metrics_by_name[metric["metric_name"]].append(value)
        except (ValueError, TypeError):
            continue

    aggregated = {}
    for metric_name, values in metrics_by_name.items():
        if values:
            aggregated[metric_name] = {
                "sample_count": len(values),
                "avg": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "percentile": percentile,
                "percentile_result": calculate_percentile(values, percentile),
                "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
                "_values": values,  # Keep raw values for dynamic percentile calculation
            }

    return aggregated


def get_aggregated_value(scenario_id: str, metric_name: str, aggregation: str) -> float:
    """
    Get a specific aggregated value for a metric.

    Args:
        scenario_id: UUID of the scenario
        metric_name: Name of the metric
        aggregation: Aggregation type - can be 'avg', 'min', 'max', 'stddev',
                     or dynamic percentile like 'p1' to 'p99'

    Returns:
        The aggregated value for the metric
    """
    # Check if aggregation is a percentile (p1 to p99)
    percentile_value = parse_percentile_aggregation(aggregation)

    all_aggregated = aggregate_metrics_for_scenario(scenario_id)
    if metric_name not in all_aggregated:
        return 0.0

    metric_stats = all_aggregated[metric_name]

    # Handle dynamic percentile
    if percentile_value is not None:
        values = metric_stats.get("_values", [])
        if values:
            return calculate_percentile(values, percentile_value)
        return 0.0

    # Handle standard aggregations
    return metric_stats.get(aggregation, metric_stats.get("avg", 0.0))


def save_scenario_summary(scenario_id: str, metric_percentiles: dict[str, int] | None = None,
                          default_percentile: int = 50) -> None:
    """
    Calculate and save aggregated metrics to scenario_summary table.
    Called after scenario completes all runs.

    Args:
        scenario_id: UUID of the scenario
        metric_percentiles: Optional dict mapping metric names to their specific
                           percentile values (1-99), extracted from expectations
        default_percentile: Fallback percentile for metrics not in metric_percentiles
    """
    aggregated = aggregate_metrics_for_scenario(scenario_id, default_percentile)

    for metric_name, stats in aggregated.items():
        percentile = default_percentile
        if metric_percentiles and metric_name in metric_percentiles:
            percentile = metric_percentiles[metric_name]
            values = stats.get("_values", [])
            if values:
                stats["percentile_result"] = calculate_percentile(values, percentile)
                stats["percentile"] = percentile

        insert_scenario_summary(
            scenario_id=scenario_id,
            metric_name=metric_name,
            sample_count=stats["sample_count"],
            avg_value=stats["avg"],
            min_value=stats["min"],
            max_value=stats["max"],
            percentile=stats["percentile"],
            percentile_result=stats["percentile_result"],
            stddev_value=stats["stddev"],
        )
