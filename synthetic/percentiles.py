"""Phase 7 — Percentile computation utilities for Monte Carlo results."""


def percentile(sorted_data, p):
    """Compute the p-th percentile from sorted data."""
    if not sorted_data:
        return 0
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def compute_percentiles(data, percentiles_list=None):
    """Compute multiple percentiles from unsorted data.
    
    Args:
        data: List of numeric values
        percentiles_list: List of percentile values (default: [10, 25, 50, 75, 90, 95])
    
    Returns:
        dict mapping percentile labels to values
    """
    if percentiles_list is None:
        percentiles_list = [10, 25, 50, 75, 90, 95]

    sorted_data = sorted(data)
    result = {}
    for p in percentiles_list:
        result[f'p{p}'] = percentile(sorted_data, p)
    return result


def iqr(data):
    """Compute interquartile range."""
    sorted_data = sorted(data)
    q1 = percentile(sorted_data, 25)
    q3 = percentile(sorted_data, 75)
    return q3 - q1


def detect_outliers(data, factor=1.5):
    """Detect outliers using IQR method."""
    sorted_data = sorted(data)
    q1 = percentile(sorted_data, 25)
    q3 = percentile(sorted_data, 75)
    iqr_val = q3 - q1
    lower = q1 - factor * iqr_val
    upper = q3 + factor * iqr_val
    return [x for x in data if x < lower or x > upper]
