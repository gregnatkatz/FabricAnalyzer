"""Phase 6 — Synthetic Data Generator.
Creates structurally faithful, PHI-safe synthetic datasets.
Session-scoped in ./tmp/{session_id}/, always deleted on Reset.
"""
import os
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False


def generate_synthetic(db_path, session_id, output_dir='./tmp', scale=0.025):
    """Generate synthetic dataset from real schema.
    
    Args:
        db_path: Path to source SQLite database
        session_id: Session identifier for scoping
        output_dir: Base output directory
        scale: Scale factor (0.025 = 2.5% of original row counts)
    """
    session_dir = os.path.join(output_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]
    columns = [dict(r) for r in db.execute('SELECT * FROM columns').fetchall()]
    db.close()

    generated_files = []

    for table in tables:
        table_name = table['name']
        row_count = max(10, int(table.get('row_count', 100) * scale))
        table_cols = [c for c in columns if c.get('table_id') == table.get('table_id')]

        # Generate synthetic rows
        rows = []
        for i in range(row_count):
            row = {}
            for col in table_cols:
                row[col['name']] = _generate_value(col, i)
            # Add default columns if none defined
            if not table_cols:
                row['ID'] = i + 1
                row['Value'] = random.uniform(0, 100)
                row['Category'] = random.choice(['A', 'B', 'C', 'D'])
            rows.append(row)

        # Save as JSON (always available)
        json_path = os.path.join(session_dir, f'{table_name}.json')
        with open(json_path, 'w') as f:
            json.dump(rows, f)
        generated_files.append(json_path)

        # Save as parquet if available
        if PARQUET_AVAILABLE and rows:
            try:
                parquet_path = os.path.join(session_dir, f'{table_name}.parquet')
                table_data = pa.table({k: [r.get(k) for r in rows] for k in rows[0].keys()})
                pq.write_table(table_data, parquet_path)
                generated_files.append(parquet_path)
            except Exception:
                pass  # JSON fallback is sufficient

    # Save manifest
    manifest = {
        'session_id': session_id,
        'generated_at': datetime.utcnow().isoformat(),
        'source_db': db_path,
        'scale': scale,
        'tables': [t['name'] for t in tables],
        'files': generated_files,
    }
    manifest_path = os.path.join(session_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return {
        'session_dir': session_dir,
        'files': generated_files,
        'table_count': len(tables),
        'manifest': manifest_path,
    }


def _generate_value(col, row_index):
    """Generate a synthetic value based on column metadata."""
    dtype = str(col.get('data_type', 'String')).lower()
    name = col.get('name', '').lower()
    cardinality = col.get('cardinality', 100)

    if 'int' in dtype or 'id' in name:
        return row_index + 1
    elif 'date' in dtype or 'date' in name:
        base = datetime(2024, 1, 1)
        return (base + timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d')
    elif 'decimal' in dtype or 'float' in dtype or 'double' in dtype:
        return round(random.uniform(0.5, 100.0), 2)
    elif 'bool' in dtype:
        return random.choice([True, False])
    else:
        # String — generate from pool based on cardinality
        pool_size = min(cardinality, 50)
        return f'{col.get("name", "val")}_{random.randint(1, pool_size)}'
