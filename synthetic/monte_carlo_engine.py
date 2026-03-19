"""Phase 7 — Monte Carlo Engine.
Runs 500 iterations with calibrated distributions per fix scenario.
Outputs P10/P50/P90 percentiles with variance tracking.
"""
import json
import random
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Fix reduction distributions (mean, stddev) for each phase
FIX_DISTRIBUTIONS = {
    'instruction_trim': {'schema': (0.05, 0.02), 'dax': (0.30, 0.08), 'exec': (0.02, 0.01)},
    'schema_scope':     {'schema': (0.55, 0.12), 'dax': (0.05, 0.02), 'exec': (0.03, 0.01)},
    'routing_rules':    {'schema': (0.02, 0.01), 'dax': (0.25, 0.10), 'exec': (0.05, 0.02)},
    'verified_answers': {'schema': (0.03, 0.01), 'dax': (0.60, 0.15), 'exec': (0.02, 0.01)},
    'topn_guard':       {'schema': (0.01, 0.005), 'dax': (0.08, 0.03), 'exec': (0.30, 0.10)},
    'measure_dedup':    {'schema': (0.02, 0.01), 'dax': (0.15, 0.05), 'exec': (0.01, 0.005)},
    'vorder':           {'schema': (0.01, 0.005), 'dax': (0.01, 0.005), 'exec': (0.20, 0.06)},
    'physician_gov':    {'schema': (0.0, 0.0), 'dax': (0.0, 0.0), 'exec': (0.0, 0.0)},
}

# Caps from spec
CAPS = {'schema': 0.78, 'dax': 0.82, 'exec': 0.65}
FLOOR_MS = 1600


def sample_reduction(fix_key, phase):
    """Sample a reduction factor from the fix's distribution for a phase."""
    dist = FIX_DISTRIBUTIONS.get(fix_key, {}).get(phase, (0, 0))
    mean, stddev = dist
    if stddev == 0:
        return mean
    value = random.gauss(mean, stddev)
    return max(0, min(value, 1.0))


def simulate_trace(trace, active_fixes):
    """Simulate one trace with active fixes applied (stochastic version)."""
    bd_schema = trace.get('bd_schema', 0)
    bd_nldax = trace.get('bd_nldax', 0)
    bd_exec = trace.get('bd_exec', 0)
    bd_parse = trace.get('bd_parse', 0)
    bd_synth = trace.get('bd_synth', 0)

    # Cumulative reduction per phase
    schema_reduction = 0
    dax_reduction = 0
    exec_reduction = 0

    for fix_key in active_fixes:
        schema_reduction += sample_reduction(fix_key, 'schema')
        dax_reduction += sample_reduction(fix_key, 'dax')
        exec_reduction += sample_reduction(fix_key, 'exec')

    # Apply caps
    schema_reduction = min(schema_reduction, CAPS['schema'])
    dax_reduction = min(dax_reduction, CAPS['dax'])
    exec_reduction = min(exec_reduction, CAPS['exec'])

    # Apply reductions
    new_schema = bd_schema * (1 - schema_reduction)
    new_nldax = bd_nldax * (1 - dax_reduction)
    new_exec = bd_exec * (1 - exec_reduction)

    projected = bd_parse + new_schema + new_nldax + new_exec + bd_synth

    # Apply floor
    projected = max(projected, FLOOR_MS)

    return projected


def run_monte_carlo(db_path, findings=None, behavioral_evidence=None, n_iterations=500, active_fixes=None):
    """Run Monte Carlo simulation.
    
    Args:
        db_path: Path to SQLite database with traces
        findings: List of findings (for calibration)
        behavioral_evidence: Behavioral profile JSON string or dict
        n_iterations: Number of simulation iterations (default 500)
        active_fixes: List of fix keys to simulate (default: all)
    
    Returns:
        dict with simulation results including P10/P50/P90
    """
    import sqlite3
    
    # Reconstruct BehavioralProfile for calibration if available
    profile = None
    if behavioral_evidence:
        try:
            from agents.adversarial_probe import BehavioralProfile
            bp_data = json.loads(behavioral_evidence) if isinstance(behavioral_evidence, str) else behavioral_evidence
            if bp_data:
                profile = BehavioralProfile.from_dict(bp_data)
        except Exception:
            pass

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
    db.close()

    if not traces:
        return {'error': 'No traces available for simulation'}

    if active_fixes is None:
        active_fixes = list(FIX_DISTRIBUTIONS.keys())

    # Run simulations
    all_averages = []
    all_p95s = []
    per_trace_results = {t['trace_id']: [] for t in traces}

    for iteration in range(n_iterations):
        iteration_totals = []
        for trace in traces:
            projected = simulate_trace(trace, active_fixes)
            iteration_totals.append(projected)
            per_trace_results[trace['trace_id']].append(projected)

        avg = sum(iteration_totals) / len(iteration_totals)
        all_averages.append(avg)
        sorted_totals = sorted(iteration_totals)
        p95_idx = int(len(sorted_totals) * 0.95)
        all_p95s.append(sorted_totals[min(p95_idx, len(sorted_totals) - 1)])

    # Calculate percentiles
    all_averages.sort()
    all_p95s.sort()

    def percentile(data, p):
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    # Baseline stats
    baseline_avg = sum(t.get('total_ms', 0) for t in traces) / len(traces)
    baseline_p95 = sorted([t.get('total_ms', 0) for t in traces])[int(len(traces) * 0.95)] if len(traces) > 1 else traces[0].get('total_ms', 0)

    # Per-fix analysis
    per_fix = {}
    for fix_key in FIX_DISTRIBUTIONS:
        fix_averages = []
        for _ in range(100):  # Fewer iterations for per-fix
            totals = []
            for trace in traces:
                projected = simulate_trace(trace, [fix_key])
                totals.append(projected)
            fix_averages.append(sum(totals) / len(totals))
        fix_averages.sort()
        per_fix[fix_key] = {
            'p10': round(percentile(fix_averages, 10)),
            'p50': round(percentile(fix_averages, 50)),
            'p90': round(percentile(fix_averages, 90)),
            'reduction_ms': round(baseline_avg - percentile(fix_averages, 50)),
            'confidence': _confidence_from_variance(fix_averages),
        }

    # Calibration adjustments from BehavioralProfile
    calibration = {}
    if profile:
        calibration = {
            'retry_alpha': profile.get_retry_reduction_alpha(),
            'routing_alpha': profile.get_routing_reduction_alpha(),
            'governance_risk': profile.get_governance_risk_score(),
            'topn_alpha': profile.get_topn_reduction_alpha(),
            'outlier_severity': profile.get_outlier_severity()[0],
        }

    result = {
        'n_iterations': n_iterations,
        'n_traces': len(traces),
        'active_fixes': active_fixes,
        'baseline': {
            'avg_ms': round(baseline_avg),
            'p95_ms': round(baseline_p95),
        },
        'projected': {
            'p10': round(percentile(all_averages, 10)),
            'p50': round(percentile(all_averages, 50)),
            'p90': round(percentile(all_averages, 90)),
        },
        'outlier': {
            'p10': round(percentile(all_p95s, 10)),
            'p50': round(percentile(all_p95s, 50)),
            'p90': round(percentile(all_p95s, 90)),
        },
        'per_fix': per_fix,
        'variance_record': {
            'avg_stddev': round(_stddev(all_averages)),
            'p95_stddev': round(_stddev(all_p95s)),
        },
        'calibration': calibration,
    }

    # Persist to SQLite monte_carlo_results table
    _persist_results(db_path, result)

    return result


def _persist_results(db_path, result):
    """Write Monte Carlo results to the monte_carlo_results SQLite table."""
    import sqlite3
    try:
        db = sqlite3.connect(db_path)
        db.execute('''
            CREATE TABLE IF NOT EXISTS monte_carlo_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT DEFAULT (datetime('now')),
                n_iterations INTEGER,
                n_traces INTEGER,
                active_fixes TEXT,
                baseline_avg_ms INTEGER,
                baseline_p95_ms INTEGER,
                projected_p10 INTEGER,
                projected_p50 INTEGER,
                projected_p90 INTEGER,
                outlier_p10 INTEGER,
                outlier_p50 INTEGER,
                outlier_p90 INTEGER,
                avg_stddev INTEGER,
                p95_stddev INTEGER,
                per_fix_json TEXT,
                calibration_json TEXT,
                reduction_pct REAL,
                confidence TEXT,
                pass_rate_before REAL,
                pass_rate_after REAL,
                fix_instruction_trim_p50 INTEGER,
                fix_schema_scope_p50 INTEGER,
                fix_routing_rules_p50 INTEGER,
                fix_verified_answers_p50 INTEGER,
                fix_topn_guard_p50 INTEGER,
                fix_measure_dedup_p50 INTEGER,
                fix_vorder_p50 INTEGER,
                fix_physician_gov_p50 INTEGER
            )
        ''')

        baseline_avg = result['baseline']['avg_ms']
        projected_p50 = result['projected']['p50']
        reduction_pct = round((baseline_avg - projected_p50) / max(baseline_avg, 1) * 100, 1)

        # Overall confidence from variance
        cv = result['variance_record']['avg_stddev'] / max(projected_p50, 1)
        confidence = 'HIGH' if cv < 0.05 else 'MEDIUM' if cv < 0.15 else 'LOW'

        per_fix = result.get('per_fix', {})

        db.execute('''
            INSERT INTO monte_carlo_results (
                n_iterations, n_traces, active_fixes,
                baseline_avg_ms, baseline_p95_ms,
                projected_p10, projected_p50, projected_p90,
                outlier_p10, outlier_p50, outlier_p90,
                avg_stddev, p95_stddev,
                per_fix_json, calibration_json,
                reduction_pct, confidence,
                fix_instruction_trim_p50, fix_schema_scope_p50,
                fix_routing_rules_p50, fix_verified_answers_p50,
                fix_topn_guard_p50, fix_measure_dedup_p50,
                fix_vorder_p50, fix_physician_gov_p50
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result['n_iterations'], result['n_traces'],
            json.dumps(result['active_fixes']),
            result['baseline']['avg_ms'], result['baseline']['p95_ms'],
            result['projected']['p10'], result['projected']['p50'], result['projected']['p90'],
            result['outlier']['p10'], result['outlier']['p50'], result['outlier']['p90'],
            result['variance_record']['avg_stddev'], result['variance_record']['p95_stddev'],
            json.dumps(per_fix), json.dumps(result.get('calibration', {})),
            reduction_pct, confidence,
            per_fix.get('instruction_trim', {}).get('p50', 0),
            per_fix.get('schema_scope', {}).get('p50', 0),
            per_fix.get('routing_rules', {}).get('p50', 0),
            per_fix.get('verified_answers', {}).get('p50', 0),
            per_fix.get('topn_guard', {}).get('p50', 0),
            per_fix.get('measure_dedup', {}).get('p50', 0),
            per_fix.get('vorder', {}).get('p50', 0),
            per_fix.get('physician_gov', {}).get('p50', 0),
        ))
        db.commit()
        db.close()
    except Exception as e:
        print(f'Monte Carlo persist error: {e}', file=sys.stderr)


def _stddev(values):
    """Calculate standard deviation."""
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _confidence_from_variance(values):
    """Derive confidence label from coefficient of variation."""
    if not values:
        return 'N/A'
    mean = sum(values) / len(values)
    if mean == 0:
        return 'N/A'
    cv = _stddev(values) / mean
    if cv < 0.05:
        return 'HIGH'
    elif cv < 0.15:
        return 'MEDIUM'
    else:
        return 'LOW'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--fixes', default='all')
    args = parser.parse_args()

    fixes = None if args.fixes == 'all' else args.fixes.split(',')
    result = run_monte_carlo(args.db, n_iterations=args.n, active_fixes=fixes)
    print(json.dumps(result, indent=2))
