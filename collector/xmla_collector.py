"""XMLA Collector — Deep model analysis via DMV queries.

Connects to the Power BI / Fabric XMLA endpoint and runs DMV queries for:
  - Column cardinality and storage statistics
  - Relationship statistics (fan-out, cross-filter, active/inactive)
  - Measure dependencies (circular references, cross-table chains)

Requires:
  - XMLA read enabled on the Fabric capacity (admin setting)
  - Token with Analysis Services scope (https://analysis.windows.net/powerbi/api/.default)
"""
import json
import sqlite3
import sys
import os
import argparse

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


PBI_EXECUTE_QUERIES = 'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{model_id}/executeQueries'

# DMV Query 1: Column cardinality and storage statistics
COLUMN_STATS_DMV = """
EVALUATE
SELECTCOLUMNS(
  INFO.STORAGETABLECOLUMNS(),
  "TableName", [DIMENSION_NAME],
  "ColumnName", [ATTRIBUTE_NAME],
  "Cardinality", [DICTIONARY_SIZE],
  "DataSize", [USED_SIZE],
  "Segments", [SEGMENT_COUNT]
)
"""

# DMV Query 2: Relationship statistics
RELATIONSHIP_DMV = """
EVALUATE
SELECTCOLUMNS(
  INFO.RELATIONSHIPS(),
  "FromTable", [FromTableName],
  "ToTable", [ToTableName],
  "FromCardinality", [FromCardinality],
  "ToCardinality", [ToCardinality],
  "CrossFilter", [CrossFilteringBehavior],
  "IsActive", [IsActive]
)
"""

# DMV Query 3: Measure dependencies
MEASURE_DEP_DMV = """
EVALUATE
SELECTCOLUMNS(
  INFO.CALCDEPENDENCY(),
  "Object", [OBJECT],
  "ReferencedObject", [REFERENCED_OBJECT],
  "ReferencedObjectType", [REFERENCED_OBJECT_TYPE]
)
"""


def xmla_query(workspace_id, model_id, dax_query, token, timeout=30):
    """Execute a DAX/DMV query against the XMLA endpoint via executeQueries API."""
    if not REQUESTS_AVAILABLE:
        raise RuntimeError('requests library not available')

    url = PBI_EXECUTE_QUERIES.format(workspace_id=workspace_id, model_id=model_id)
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    body = {
        'queries': [{'query': dax_query}],
        'serializerSettings': {'includeNulls': True},
    }

    resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f'XMLA query failed: {resp.status_code} {resp.text[:200]}')

    data = resp.json()
    # Extract rows from first result table
    results = data.get('results', [])
    if not results:
        return []
    tables = results[0].get('tables', [])
    if not tables:
        return []
    return tables[0].get('rows', [])


def collect_column_stats(workspace_id, model_id, token):
    """Collect column cardinality and storage statistics via XMLA DMV."""
    try:
        rows = xmla_query(workspace_id, model_id, COLUMN_STATS_DMV, token)
        stats = []
        for r in rows:
            stats.append({
                'table_name': r.get('[TableName]', r.get('TableName', '')),
                'column_name': r.get('[ColumnName]', r.get('ColumnName', '')),
                'cardinality': int(r.get('[Cardinality]', r.get('Cardinality', 0)) or 0),
                'data_size_mb': round(int(r.get('[DataSize]', r.get('DataSize', 0)) or 0) / (1024 * 1024), 2),
                'segment_count': int(r.get('[Segments]', r.get('Segments', 0)) or 0),
            })
        return stats
    except Exception as e:
        print(f'XMLA column stats failed: {e}', file=sys.stderr)
        return []


def collect_relationship_stats(workspace_id, model_id, token):
    """Collect relationship statistics via XMLA DMV."""
    try:
        rows = xmla_query(workspace_id, model_id, RELATIONSHIP_DMV, token)
        stats = []
        for r in rows:
            stats.append({
                'from_table': r.get('[FromTable]', r.get('FromTable', '')),
                'to_table': r.get('[ToTable]', r.get('ToTable', '')),
                'from_cardinality': int(r.get('[FromCardinality]', r.get('FromCardinality', 0)) or 0),
                'to_cardinality': int(r.get('[ToCardinality]', r.get('ToCardinality', 0)) or 0),
                'cross_filter': r.get('[CrossFilter]', r.get('CrossFilter', 'OneDirection')),
                'is_active': int(r.get('[IsActive]', r.get('IsActive', 1)) or 0),
            })
        return stats
    except Exception as e:
        print(f'XMLA relationship stats failed: {e}', file=sys.stderr)
        return []


def collect_measure_deps(workspace_id, model_id, token):
    """Collect measure dependency graph via XMLA DMV."""
    try:
        rows = xmla_query(workspace_id, model_id, MEASURE_DEP_DMV, token)
        deps = []
        for r in rows:
            deps.append({
                'object': r.get('[Object]', r.get('Object', '')),
                'referenced_object': r.get('[ReferencedObject]', r.get('ReferencedObject', '')),
                'referenced_type': r.get('[ReferencedObjectType]', r.get('ReferencedObjectType', '')),
            })
        return deps
    except Exception as e:
        print(f'XMLA measure deps failed: {e}', file=sys.stderr)
        return []


def store_xmla_data(db_path, model_id, column_stats, relationship_stats):
    """Store XMLA data in SQLite database."""
    db = sqlite3.connect(db_path)

    # Create tables if not exist
    db.executescript("""
        CREATE TABLE IF NOT EXISTS column_stats (
            col_stat_id TEXT PRIMARY KEY,
            model_id TEXT,
            table_name TEXT,
            column_name TEXT,
            cardinality INTEGER,
            data_size_mb REAL,
            segment_count INTEGER,
            captured_at TEXT
        );
        CREATE TABLE IF NOT EXISTS relationship_stats (
            rel_stat_id TEXT PRIMARY KEY,
            model_id TEXT,
            from_table TEXT,
            to_table TEXT,
            from_cardinality INTEGER,
            to_cardinality INTEGER,
            cross_filter TEXT,
            is_active INTEGER,
            captured_at TEXT
        );
    """)

    # Clear old data for this model
    db.execute('DELETE FROM column_stats WHERE model_id = ?', (model_id,))
    db.execute('DELETE FROM relationship_stats WHERE model_id = ?', (model_id,))

    # Insert column stats
    for i, cs in enumerate(column_stats):
        db.execute(
            'INSERT INTO column_stats VALUES (?, ?, ?, ?, ?, ?, ?, datetime("now"))',
            (f'cs_{model_id}_{i}', model_id, cs['table_name'], cs['column_name'],
             cs['cardinality'], cs['data_size_mb'], cs['segment_count']),
        )

    # Insert relationship stats
    for i, rs in enumerate(relationship_stats):
        db.execute(
            'INSERT INTO relationship_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime("now"))',
            (f'rs_{model_id}_{i}', model_id, rs['from_table'], rs['to_table'],
             rs['from_cardinality'], rs['to_cardinality'], rs['cross_filter'],
             rs['is_active']),
        )

    db.commit()
    db.close()


def run_xmla_collection(workspace_id, model_id, token, db_path):
    """Full XMLA collection pipeline: query DMVs and store results."""
    print(f'[XMLA] Collecting column stats for model {model_id}...', file=sys.stderr)
    col_stats = collect_column_stats(workspace_id, model_id, token)
    print(f'[XMLA] Got {len(col_stats)} column stats', file=sys.stderr)

    print(f'[XMLA] Collecting relationship stats...', file=sys.stderr)
    rel_stats = collect_relationship_stats(workspace_id, model_id, token)
    print(f'[XMLA] Got {len(rel_stats)} relationship stats', file=sys.stderr)

    print(f'[XMLA] Collecting measure dependencies...', file=sys.stderr)
    measure_deps = collect_measure_deps(workspace_id, model_id, token)
    print(f'[XMLA] Got {len(measure_deps)} measure dependencies', file=sys.stderr)

    # Store in DB
    store_xmla_data(db_path, model_id, col_stats, rel_stats)

    return {
        'columnStats': col_stats,
        'relationshipStats': rel_stats,
        'measureDeps': measure_deps,
        'summary': {
            'column_stats_count': len(col_stats),
            'relationship_stats_count': len(rel_stats),
            'measure_deps_count': len(measure_deps),
        },
    }


def main():
    parser = argparse.ArgumentParser(description='XMLA Collector for Fabric Semantic Models')
    parser.add_argument('--workspace-id', required=True, help='Fabric workspace ID')
    parser.add_argument('--model-id', required=True, help='Semantic model (dataset) ID')
    parser.add_argument('--token', required=True, help='Bearer token with XMLA scope')
    parser.add_argument('--db', required=True, help='Path to SQLite database')

    args = parser.parse_args()
    result = run_xmla_collection(args.workspace_id, args.model_id, args.token, args.db)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
