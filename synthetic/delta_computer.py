"""Phase 8 — Delta Computer: compares baseline vs post-fix results."""


def compute_delta(baseline_results, postfix_results):
    """Compute per-question and aggregate delta between baseline and post-fix.
    
    Args:
        baseline_results: List of dicts with 'question' and 'total_ms'
        postfix_results: List of dicts with 'question' and 'total_ms'
    
    Returns:
        dict with baseline_avg, postfix_avg, reduction_pct, per_question
    """
    if not baseline_results or not postfix_results:
        return {
            'baseline_avg': 0,
            'postfix_avg': 0,
            'reduction_pct': 0,
            'per_question': [],
        }

    baseline_avg = sum(r['total_ms'] for r in baseline_results) / len(baseline_results)
    postfix_avg = sum(r['total_ms'] for r in postfix_results) / len(postfix_results)

    reduction_pct = 0
    if baseline_avg > 0:
        reduction_pct = round((baseline_avg - postfix_avg) / baseline_avg * 100, 1)

    per_question = []
    for i, (b, p) in enumerate(zip(baseline_results, postfix_results)):
        q_reduction = 0
        if b['total_ms'] > 0:
            q_reduction = round((b['total_ms'] - p['total_ms']) / b['total_ms'] * 100, 1)
        per_question.append({
            'question': b.get('question', f'Q{i+1}'),
            'baseline_ms': b['total_ms'],
            'postfix_ms': p['total_ms'],
            'delta_ms': b['total_ms'] - p['total_ms'],
            'reduction_pct': q_reduction,
        })

    return {
        'baseline_avg': round(baseline_avg),
        'postfix_avg': round(postfix_avg),
        'reduction_pct': reduction_pct,
        'per_question': per_question,
    }
