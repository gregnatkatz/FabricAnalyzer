"""Agent XM -- XMLA Deep Analysis -- 7 Deterministic Rules on column_stats and relationship_stats.

Rules XM-1 through XM-7 operate on XMLA DMV data for deep model analysis.
These rules require XMLA collection to have been run first (tables may be empty).
"""
import sqlite3


def run_xmla_checks(db_path):
    """Run all 7 XMLA rules on column_stats and relationship_stats. Returns list of findings."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    # Ensure tables exist before querying
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    if 'column_stats' not in tables or 'relationship_stats' not in tables:
        db.close()
        return findings

    col_stats = [dict(r) for r in db.execute('SELECT * FROM column_stats').fetchall()]
    rel_stats = [dict(r) for r in db.execute('SELECT * FROM relationship_stats').fetchall()]
    db.close()

    if not col_stats and not rel_stats:
        return findings

    # XM-1: High cardinality columns (> 1M distinct values) — expensive for VertiPaq
    for cs in col_stats:
        card = cs.get('cardinality', 0) or 0
        if card > 1_000_000:
            findings.append({
                'issue': f'High cardinality column: {cs["table_name"]}.{cs["column_name"]} ({card:,} distinct values)',
                'severity': 'HIGH',
                'evidence': f'Column has {card:,} distinct values -- VertiPaq dictionary encoding is inefficient above 1M, increasing memory and query time',
                'impact_ms': min(card // 100_000, 50) * 100,  # 100ms per 100K cardinality
                'fix': f'Consider bucketing or hashing {cs["table_name"]}.{cs["column_name"]} to reduce cardinality, or exclude from model if unused',
                'agent_id': 'xmla',
            })

    # XM-2: Large column storage (> 50MB data size)
    for cs in col_stats:
        size = cs.get('data_size_mb', 0) or 0
        if size > 50:
            findings.append({
                'issue': f'Large column storage: {cs["table_name"]}.{cs["column_name"]} ({size:.1f} MB)',
                'severity': 'HIGH',
                'evidence': f'Column occupies {size:.1f} MB in VertiPaq storage -- large columns slow scan operations and increase memory pressure',
                'impact_ms': int(size * 20),  # ~20ms per MB for scan
                'fix': f'Review if {cs["table_name"]}.{cs["column_name"]} needs full precision -- consider aggregation or removing unused columns',
                'agent_id': 'xmla',
            })

    # XM-3: Bidirectional cross-filter relationships (performance risk)
    for rs in rel_stats:
        cf = (rs.get('cross_filter', '') or '').lower()
        if cf in ('bothdirections', 'both', 'bidirectional'):
            findings.append({
                'issue': f'Bidirectional cross-filter: {rs["from_table"]} <-> {rs["to_table"]}',
                'severity': 'HIGH',
                'evidence': 'Bidirectional cross-filtering causes VertiPaq to evaluate filters in both directions -- exponential cost with multiple bidir relationships',
                'impact_ms': 1500,
                'fix': f'Change relationship between {rs["from_table"]} and {rs["to_table"]} to single-direction unless bidirectional is specifically required by a measure',
                'agent_id': 'xmla',
            })

    # XM-4: Inactive relationships (unused model complexity)
    inactive_count = sum(1 for rs in rel_stats if not rs.get('is_active', 1))
    if inactive_count > 2:
        inactive_pairs = [f'{rs["from_table"]}->{rs["to_table"]}'
                          for rs in rel_stats if not rs.get('is_active', 1)]
        findings.append({
            'issue': f'{inactive_count} inactive relationships in model',
            'severity': 'MEDIUM',
            'evidence': f'Inactive relationships: {", ".join(inactive_pairs[:5])}. Inactive relationships add model complexity without benefit unless used via USERELATIONSHIP()',
            'impact_ms': inactive_count * 100,
            'fix': 'Review inactive relationships -- remove those not referenced by USERELATIONSHIP() in any measure',
            'agent_id': 'xmla',
        })

    # XM-5: High segment count (> 10 segments per column suggests poor partitioning)
    for cs in col_stats:
        segs = cs.get('segment_count', 0) or 0
        if segs > 10:
            findings.append({
                'issue': f'High segment count: {cs["table_name"]}.{cs["column_name"]} ({segs} segments)',
                'severity': 'MEDIUM',
                'evidence': f'Column has {segs} segments -- high segment count indicates suboptimal partitioning or very large table, reducing scan efficiency',
                'impact_ms': segs * 50,
                'fix': f'Consider repartitioning {cs["table_name"]} or enabling V-Order optimization to reduce segment count',
                'agent_id': 'xmla',
            })

    # XM-6: Many-to-many relationship fan-out risk
    for rs in rel_stats:
        from_card = rs.get('from_cardinality', 0) or 0
        to_card = rs.get('to_cardinality', 0) or 0
        # Both sides > 1 suggests many-to-many
        if from_card > 1 and to_card > 1:
            findings.append({
                'issue': f'Many-to-many relationship: {rs["from_table"]} ({from_card}) <-> {rs["to_table"]} ({to_card})',
                'severity': 'CRITICAL',
                'evidence': f'Relationship has cardinality {from_card}:{to_card} -- many-to-many relationships cause fan-out that multiplies row counts during queries',
                'impact_ms': 3000,
                'fix': f'Add a bridge table between {rs["from_table"]} and {rs["to_table"]} to resolve the many-to-many, or use TREATAS for virtual relationships',
                'agent_id': 'xmla',
            })

    # XM-7: Orphaned columns — present in model but never referenced
    # reference_count = 0 means INFO.CALCDEPENDENCY() found zero references
    # to this column across all measures, calculated columns, and relationships.
    # reference_count = -1 means the data was not available (query not run).
    # Only fire when reference_count is explicitly 0 — never on -1.
    for cs in col_stats:
        ref_count = cs.get('reference_count', -1)
        if ref_count != 0:
            continue  # -1 = unknown, >0 = referenced — skip both

        table_name  = cs.get('table_name', '')
        column_name = cs.get('column_name', '')
        size_mb     = cs.get('data_size_mb', 0) or 0
        cardinality = cs.get('cardinality', 0) or 0

        # Skip key columns and ID-like columns — these may be used by
        # relationships even if not by measures (relationship stats are
        # separate from CALCDEPENDENCY)
        col_lower = column_name.lower()
        likely_key = any(x in col_lower for x in
                         ('id', 'key', 'pk', 'fk', 'code', 'guid', 'uuid'))
        if likely_key:
            # Downgrade to MEDIUM and note it may be a relationship key
            findings.append({
                'issue': (
                    f'Possibly orphaned key column: '
                    f'{table_name}.{column_name} — no measure references found'
                ),
                'severity': 'MEDIUM',
                'evidence': (
                    f'{table_name}.{column_name} has 0 measure references in '
                    f'INFO.CALCDEPENDENCY(). It may still be used as a '
                    f'relationship key — verify before removing.'
                ),
                'impact_ms': 100,
                'fix': (
                    f'Verify {table_name}.{column_name} is not used as a '
                    f'relationship join key. If unused, hide or remove it from '
                    f'the model in Power BI Desktop.'
                ),
                'agent_id': 'xmla',
            })
        else:
            # Non-key column with zero references — high confidence orphan
            findings.append({
                'issue': (
                    f'Orphaned column: {table_name}.{column_name} '
                    f'— never referenced by any measure'
                ),
                'severity': 'HIGH',
                'evidence': (
                    f'{table_name}.{column_name} has 0 references in '
                    f'INFO.CALCDEPENDENCY() across all measures and calculated '
                    f'columns. It occupies {size_mb:.1f} MB and {cardinality:,} '
                    f'distinct values in VertiPaq — pure overhead the Data Agent '
                    f'never uses.'
                ),
                'impact_ms': max(int(size_mb * 15), 200),
                # 15ms per MB — rough scan overhead estimate
                'fix': (
                    f'Remove {table_name}.{column_name} from the semantic model '
                    f'in Power BI Desktop (not just hide it — physical removal '
                    f'reclaims VertiPaq memory). If the column is needed for '
                    f'future use, move it to a staging layer instead.'
                ),
                'agent_id': 'xmla',
            })

    # Deduplicate
    seen = set()
    unique = []
    for f in findings:
        key = f['issue'][:60]
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique
