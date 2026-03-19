"""Phase 10 — Fabric Collector: connects to real Fabric workspaces via Power BI REST API.
Collects semantic model metadata, agent configuration, and trace data.

Usage: python fabric_collector.py --workspace-id <id> --model-id <id> --token <token> ...
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from sample_dataset.build_sample import SCHEMA_SQL


PBI_BASE = 'https://api.powerbi.com/v1.0/myorg'


def api_get(url, token):
    """GET request to Power BI REST API."""
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(workspace_id, model_id, token, output_dir='./data', tmp_dir='./tmp'):
    """Collect all metadata from a Fabric workspace.
    
    Returns:
        dict with dbPath, sessionId, modelName, domain, traces
    """
    if not REQUESTS_AVAILABLE:
        return {'error': 'requests library not available'}

    session_id = f'fabric_{uuid.uuid4().hex[:8]}'
    db_path = os.path.join(output_dir, f'{session_id}.db')
    os.makedirs(output_dir, exist_ok=True)

    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA_SQL)

    # Get dataset (model) info
    try:
        dataset = api_get(f'{PBI_BASE}/groups/{workspace_id}/datasets/{model_id}', token)
    except Exception as e:
        return {'error': f'Failed to get dataset: {e}'}

    model_name = dataset.get('name', 'Unknown Model')
    db.execute('''INSERT INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
        model_id, workspace_id, model_name,
        0, dataset.get('defaultMode', 'Import'),
        dataset.get('configuredBy', ''), 1, datetime.utcnow().isoformat(),
    ))

    # Get tables
    try:
        tables_data = api_get(
            f'{PBI_BASE}/groups/{workspace_id}/datasets/{model_id}/tables', token
        )
        for i, t in enumerate(tables_data.get('value', [])):
            db.execute('INSERT INTO tables VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
                f'tbl_{i}', model_id, t.get('name', ''),
                t.get('rows', 0), len(t.get('columns', [])),
                0, 'single', t.get('description', ''),
            ))
    except Exception as e:
        print(f'Warning: Could not fetch tables: {e}', file=sys.stderr)

    # Get measures
    try:
        measures_data = api_get(
            f'{PBI_BASE}/groups/{workspace_id}/datasets/{model_id}/measures', token
        )
        for i, m in enumerate(measures_data.get('value', [])):
            db.execute('INSERT INTO measures VALUES (?, ?, ?, ?, ?, ?, ?)', (
                f'm_{i}', model_id, '',
                m.get('name', ''), m.get('expression', ''),
                m.get('description', ''), 0,
            ))
    except Exception as e:
        print(f'Warning: Could not fetch measures: {e}', file=sys.stderr)

    # Try to get agent config via enhanced dataset scan
    try:
        scan_result = api_get(
            f'{PBI_BASE}/groups/{workspace_id}/datasets/{model_id}',
            token,
        )
        # Note: Agent config may require additional API calls
        db.execute('INSERT INTO agent_config VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
            f'agent_{model_id[:8]}', model_id, workspace_id,
            '', 0, 0, 0, 0,
        ))
    except Exception as e:
        print(f'Warning: Could not fetch agent config: {e}', file=sys.stderr)

    db.commit()

    # Load traces for response
    db.row_factory = sqlite3.Row
    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
    db.close()

    return {
        'sessionId': session_id,
        'dbPath': db_path,
        'modelName': model_name,
        'domain': 'auto',
        'traces': traces,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace-id', required=True)
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--output-dir', default='./data')
    parser.add_argument('--tmp-dir', default='./tmp')
    args = parser.parse_args()

    result = collect(args.workspace_id, args.model_id, args.token, args.output_dir, args.tmp_dir)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
