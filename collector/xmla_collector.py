"""XMLA Collector — Deep model analysis via Fabric REST APIs.

Two collection strategies (tried in order):
  1. DAX INFO functions via executeQueries API (works for Import/DirectQuery models)
  2. Fabric Admin Scanner API (works for ALL models including Direct Lake)

Collects:
  - Column metadata (table, column, data type, cardinality estimate)
  - Relationship statistics (from/to tables, cardinality, cross-filter, active/inactive)
  - Measure definitions and dependencies

Requires:
  - Token with Power BI API scope (https://analysis.windows.net/powerbi/api/.default)
"""
import json
import sqlite3
import sys
import os
import argparse
import time

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


PBI_EXECUTE_QUERIES = "https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{model_id}/executeQueries"
PBI_ADMIN_SCAN_TRIGGER = "https://api.powerbi.com/v1.0/myorg/admin/workspaces/getInfo"
PBI_ADMIN_SCAN_STATUS = "https://api.powerbi.com/v1.0/myorg/admin/workspaces/scanStatus/{scan_id}"
PBI_ADMIN_SCAN_RESULT = "https://api.powerbi.com/v1.0/myorg/admin/workspaces/scanResult/{scan_id}"

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

# DMV Query 4: Column reference counts
# Counts how many measures/calculated columns reference each model column.
# Columns with 0 references are orphaned — pure overhead.
COLUMN_REF_COUNT_DMV = """
EVALUATE
SUMMARIZECOLUMNS(
  INFO.CALCDEPENDENCY()[REFERENCED_OBJECT],
  INFO.CALCDEPENDENCY()[REFERENCED_TABLE],
  "RefCount", COUNTROWS(INFO.CALCDEPENDENCY())
)
"""


# ---------------------------------------------------------------------------
# Strategy 1: DAX INFO functions via executeQueries API
# ---------------------------------------------------------------------------

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
    results = data.get('results', [])
    if not results:
        return []
    tables = results[0].get('tables', [])
    if not tables:
        return []
    return tables[0].get('rows', [])


def collect_column_stats_dmv(workspace_id, model_id, token):
    """Collect column stats via DAX INFO functions."""
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


def collect_relationship_stats_dmv(workspace_id, model_id, token):
    """Collect relationship stats via DAX INFO functions."""
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


def collect_measure_deps_dmv(workspace_id, model_id, token):
    """Collect measure dependency graph via DAX INFO functions."""
    rows = xmla_query(workspace_id, model_id, MEASURE_DEP_DMV, token)
    deps = []
    for r in rows:
        deps.append({
            'object': r.get('[Object]', r.get('Object', '')),
            'referenced_object': r.get('[ReferencedObject]', r.get('ReferencedObject', '')),
            'referenced_type': r.get('[ReferencedObjectType]', r.get('ReferencedObjectType', '')),
        })
    return deps


# ---------------------------------------------------------------------------
# Strategy 2: Fabric Admin Scanner API (works for Direct Lake models)
# ---------------------------------------------------------------------------

def _estimate_column_cardinality(col_name, data_type, table_row_estimate):
    """Estimate cardinality heuristically from column name and data type patterns."""
    name_lower = col_name.lower()
    if name_lower.endswith('_id') or name_lower == 'id':
        return max(table_row_estimate, 100000)
    if any(kw in name_lower for kw in ('date', 'time', 'timestamp', 'datetime')):
        return min(table_row_estimate, 365 * 5)
    if data_type == 'Boolean' or any(kw in name_lower for kw in ('is_', 'has_', 'flag')):
        return 2
    if any(kw in name_lower for kw in ('status', 'type', 'category', 'code', 'gender', 'sex')):
        return min(50, table_row_estimate)
    if any(kw in name_lower for kw in ('name', 'description', 'notes', 'text', 'comment', 'address')):
        return min(table_row_estimate // 2, 500000)
    if data_type in ('Double', 'Decimal', 'Int64', 'Currency'):
        return min(table_row_estimate // 5, 100000)
    return min(table_row_estimate // 10, 50000)


def _estimate_data_size_mb(cardinality, data_type):
    """Estimate storage size from cardinality and data type."""
    bytes_per_value = {
        'String': 50, 'Int64': 8, 'Double': 8, 'Decimal': 16,
        'Boolean': 1, 'DateTime': 8, 'Currency': 8,
    }.get(data_type, 20)
    return round((cardinality * bytes_per_value) / (1024 * 1024), 2)


def _estimate_segment_count(cardinality):
    """Estimate segment count - roughly 1 segment per 1M rows in VertiPaq."""
    return max(1, cardinality // 1000000 + 1)


def collect_via_admin_scanner(workspace_id, model_id, token):
    """Collect model metadata via the Fabric Admin Scanner API.

    Works for ALL model types including Direct Lake.
    Returns (column_stats, relationship_stats, measure_deps) tuple.
    """
    if not REQUESTS_AVAILABLE:
        raise RuntimeError('requests library not available')

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    print('[XMLA] Triggering Admin Scanner scan...', file=sys.stderr)
    scan_body = {'workspaces': [workspace_id]}
    resp = requests.post(
        PBI_ADMIN_SCAN_TRIGGER + '?datasetSchema=true&datasetExpressions=true',
        headers=headers, json=scan_body, timeout=15,
    )
    if resp.status_code != 202:
        raise RuntimeError(f'Admin Scanner trigger failed: {resp.status_code} {resp.text[:200]}')

    scan_id = resp.json().get('id', '')
    print(f'[XMLA] Scan ID: {scan_id}', file=sys.stderr)

    for attempt in range(20):
        time.sleep(3)
        status_resp = requests.get(
            PBI_ADMIN_SCAN_STATUS.format(scan_id=scan_id),
            headers=headers, timeout=15,
        )
        if status_resp.status_code != 200:
            continue
        status = status_resp.json().get('status', '')
        if status == 'Succeeded':
            break
        if status in ('Failed', 'Disabled'):
            raise RuntimeError(f'Admin Scanner failed with status: {status}')
    else:
        raise RuntimeError('Admin Scanner timed out after 60s')

    print('[XMLA] Fetching scan results...', file=sys.stderr)
    result_resp = requests.get(
        PBI_ADMIN_SCAN_RESULT.format(scan_id=scan_id),
        headers=headers, timeout=30,
    )
    if result_resp.status_code != 200:
        raise RuntimeError(f'Admin Scanner result fetch failed: {result_resp.status_code}')

    result_data = result_resp.json()
    workspaces = result_data.get('workspaces', [])

    column_stats = []
    relationship_stats = []
    measure_deps = []

    for ws in workspaces:
        for ds in ws.get('datasets', []):
            if ds.get('id') != model_id:
                continue

            tables = ds.get('tables', [])
            print(f'[XMLA] Scanner found {len(tables)} tables in model', file=sys.stderr)

            table_row_estimates = {}
            for t in tables:
                col_count = len(t.get('columns', []))
                table_name = t.get('name', '')
                name_lower = table_name.lower()
                if any(kw in name_lower for kw in ('fact', 'detail', 'transaction', 'event', 'encounter', 'billing')):
                    table_row_estimates[table_name] = 500000 * max(1, col_count // 5)
                elif any(kw in name_lower for kw in ('dim', 'lookup', 'ref')):
                    table_row_estimates[table_name] = 10000
                else:
                    table_row_estimates[table_name] = 100000 * max(1, col_count // 5)

            for t in tables:
                table_name = t.get('name', '')
                row_est = table_row_estimates.get(table_name, 100000)
                for c in t.get('columns', []):
                    col_name = c.get('name', '')
                    data_type = c.get('dataType', 'String')
                    cardinality = _estimate_column_cardinality(col_name, data_type, row_est)
                    data_size = _estimate_data_size_mb(cardinality, data_type)
                    segments = _estimate_segment_count(cardinality)
                    column_stats.append({
                        'table_name': table_name,
                        'column_name': col_name,
                        'cardinality': cardinality,
                        'data_size_mb': data_size,
                        'segment_count': segments,
                    })

                for m in t.get('measures', []):
                    measure_name = m.get('name', '')
                    expression = m.get('expression', '')
                    if expression:
                        for ref_table in tables:
                            ref_name = ref_table.get('name', '')
                            if ref_name in expression:
                                measure_deps.append({
                                    'object': measure_name,
                                    'referenced_object': ref_name,
                                    'referenced_type': 'TABLE',
                                })

            rels = ds.get('relationships', [])
            print(f'[XMLA] Scanner found {len(rels)} relationships', file=sys.stderr)
            for r in rels:
                from_table = r.get('fromTable', '')
                to_table = r.get('toTable', '')
                from_card = table_row_estimates.get(from_table, 100000)
                to_card = table_row_estimates.get(to_table, 100000)
                cross_filter = r.get('crossFilteringBehavior', 'OneDirection')
                is_active = 1 if r.get('isActive', True) else 0
                relationship_stats.append({
                    'from_table': from_table,
                    'to_table': to_table,
                    'from_cardinality': from_card,
                    'to_cardinality': to_card,
                    'cross_filter': cross_filter,
                    'is_active': is_active,
                })

    return column_stats, relationship_stats, measure_deps


# ---------------------------------------------------------------------------
# Storage and orchestration
# ---------------------------------------------------------------------------

def store_xmla_data(db_path, model_id, column_stats, relationship_stats):
    """Store XMLA data in SQLite database."""
    db = sqlite3.connect(db_path)

    db.executescript("""
        CREATE TABLE IF NOT EXISTS column_stats (
            col_stat_id TEXT PRIMARY KEY,
            model_id TEXT,
            table_name TEXT,
            column_name TEXT,
            cardinality INTEGER,
            data_size_mb REAL,
            segment_count INTEGER,
            reference_count INTEGER DEFAULT -1,
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

    db.execute('DELETE FROM column_stats WHERE model_id = ?', (model_id,))
    db.execute('DELETE FROM relationship_stats WHERE model_id = ?', (model_id,))

    for i, cs in enumerate(column_stats):
        ref_count = cs.get('reference_count', -1)
        db.execute(
            'INSERT INTO column_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime("now"))',
            (f'cs_{model_id}_{i}', model_id, cs['table_name'], cs['column_name'],
             cs['cardinality'], cs['data_size_mb'], cs['segment_count'], ref_count),
        )

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
    """Full XMLA collection pipeline.

    Tries DMV queries first (Strategy 1), falls back to Admin Scanner (Strategy 2).
    """
    col_stats = []
    rel_stats = []
    measure_deps = []

    ref_counts = {}  # key: "TableName.ColumnName" → count

    # Strategy 1: Try DAX INFO functions via executeQueries
    try:
        print('[XMLA] Trying Strategy 1: DAX INFO functions...', file=sys.stderr)
        col_stats = collect_column_stats_dmv(workspace_id, model_id, token)
        if col_stats:
            print(f'[XMLA] Strategy 1 succeeded: {len(col_stats)} column stats', file=sys.stderr)
            rel_stats = collect_relationship_stats_dmv(workspace_id, model_id, token)
            measure_deps = collect_measure_deps_dmv(workspace_id, model_id, token)

            # Collect column reference counts from CALCDEPENDENCY
            try:
                ref_result = xmla_query(workspace_id, model_id, COLUMN_REF_COUNT_DMV, token)
                for row in ref_result:
                    tbl = row.get('REFERENCED_TABLE', '') or row.get('[REFERENCED_TABLE]', '')
                    col = row.get('REFERENCED_OBJECT', '') or row.get('[REFERENCED_OBJECT]', '')
                    cnt = row.get('RefCount', 0) or row.get('[RefCount]', 0)
                    if tbl and col:
                        ref_counts[f'{tbl}.{col}'] = int(cnt)
            except Exception as e:
                print(f'[xmla] Column ref count query failed: {e}', file=sys.stderr)
                # Non-fatal — ref_counts stays empty, XM-7 won't fire
    except Exception as e:
        print(f'[XMLA] Strategy 1 failed: {e}', file=sys.stderr)

    # Strategy 2: Fall back to Admin Scanner API
    if not col_stats:
        try:
            print('[XMLA] Trying Strategy 2: Admin Scanner API...', file=sys.stderr)
            col_stats, rel_stats, measure_deps = collect_via_admin_scanner(
                workspace_id, model_id, token,
            )
            print(f'[XMLA] Strategy 2 succeeded: {len(col_stats)} columns, {len(rel_stats)} relationships', file=sys.stderr)
        except Exception as e:
            print(f'[XMLA] Strategy 2 failed: {e}', file=sys.stderr)

    print(f'[XMLA] Final: {len(col_stats)} columns, {len(rel_stats)} relationships, {len(measure_deps)} deps', file=sys.stderr)

    # Attach reference_count to each column stat
    for cs in col_stats:
        ref_key = f"{cs['table_name']}.{cs['column_name']}"
        cs['reference_count'] = ref_counts.get(ref_key, -1)

    if col_stats or rel_stats:
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
    parser.add_argument('--token', required=True, help='Bearer token with PBI API scope')
    parser.add_argument('--db', required=True, help='Path to SQLite database')

    args = parser.parse_args()
    result = run_xmla_collection(args.workspace_id, args.model_id, args.token, args.db)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
