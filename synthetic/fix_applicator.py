"""Phase 8 — Fix Applicator + Validation Pipeline.
Applies fixes, re-runs question battery, measures delta.
Outputs progress as newline-delimited JSON for SSE streaming.

Usage: python fix_applicator.py --session-id <id> --fixes <comma-separated> ...
"""
import argparse
import json
import os
import sys
import time
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthetic.query_simulator import QuerySimulator
from synthetic.delta_computer import compute_delta
from synthetic.resolution_checker import check_resolutions


def emit(data):
    """Emit a JSON line to stdout for SSE streaming."""
    print(json.dumps(data), flush=True)


def run_validation(session_id, fixes, db_dir='./data', tmp_dir='./tmp', proxy_url=None):
    """Run the 4-phase validation pipeline.
    
    Phases:
    1. Baseline battery (no fixes)
    2. Apply fixes
    3. Post-fix battery
    4. Delta + resolution analysis
    """
    # Find the database
    db_path = None
    if os.path.exists(os.path.join(db_dir, 'sample.db')):
        db_path = os.path.join(db_dir, 'sample.db')
    else:
        # Look for any .db file
        for f in os.listdir(db_dir) if os.path.exists(db_dir) else []:
            if f.endswith('.db'):
                db_path = os.path.join(db_dir, f)
                break

    # Also check sample_dataset directory
    sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'sample_dataset', 'sample.db')
    if db_path is None and os.path.exists(sample_path):
        db_path = sample_path

    if db_path is None:
        emit({'type': 'error', 'message': 'No database found'})
        return

    # Load questions from traces
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
    db.close()

    questions = [t.get('question', '') for t in traces if t.get('question')]

    session_dir = os.path.join(tmp_dir, session_id)
    if not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)

    simulator = QuerySimulator(session_dir)

    # Phase 1: Baseline battery
    emit({'type': 'phase', 'phase': 1, 'name': 'baseline', 'status': 'running'})
    baseline_results = simulator.run_battery(questions, fixes_applied=[])
    emit({
        'type': 'phase',
        'phase': 1,
        'name': 'baseline',
        'status': 'complete',
        'results': [{'question': r['question'], 'total_ms': r['total_ms']} for r in baseline_results],
    })

    # Phase 2: Apply fixes
    emit({'type': 'phase', 'phase': 2, 'name': 'apply_fixes', 'status': 'running', 'fixes': fixes})
    time.sleep(0.5)  # Simulate fix application time
    emit({'type': 'phase', 'phase': 2, 'name': 'apply_fixes', 'status': 'complete', 'fixes': fixes})

    # Phase 3: Post-fix battery
    emit({'type': 'phase', 'phase': 3, 'name': 'postfix', 'status': 'running'})
    postfix_results = simulator.run_battery(questions, fixes_applied=fixes)
    emit({
        'type': 'phase',
        'phase': 3,
        'name': 'postfix',
        'status': 'complete',
        'results': [{'question': r['question'], 'total_ms': r['total_ms']} for r in postfix_results],
    })

    # Phase 4: Delta + resolution
    emit({'type': 'phase', 'phase': 4, 'name': 'delta', 'status': 'running'})
    delta = compute_delta(baseline_results, postfix_results)
    resolutions = check_resolutions(db_path, delta, fixes)
    emit({
        'type': 'phase',
        'phase': 4,
        'name': 'delta',
        'status': 'complete',
        'delta': delta,
        'resolutions': resolutions,
    })

    # Final summary
    emit({
        'type': 'complete',
        'baseline_avg': delta.get('baseline_avg', 0),
        'postfix_avg': delta.get('postfix_avg', 0),
        'reduction_pct': delta.get('reduction_pct', 0),
        'per_question': delta.get('per_question', []),
        'resolutions': resolutions,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--fixes', required=True)
    parser.add_argument('--db-dir', default='./data')
    parser.add_argument('--tmp-dir', default='./tmp')
    parser.add_argument('--proxy-url', default='http://localhost:3001')
    args = parser.parse_args()

    fixes = args.fixes.split(',')
    run_validation(args.session_id, fixes, args.db_dir, args.tmp_dir, args.proxy_url)


if __name__ == '__main__':
    main()
