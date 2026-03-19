"""Agent 3 — Schema Agent — 11 Deterministic Rules from functional spec Section 6.3."""
import sqlite3


def run_checks(db_path):
    """Run all 11 deterministic schema checks. Returns list of findings."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    config = db.execute('SELECT * FROM agent_config LIMIT 1').fetchone()
    config = dict(config) if config else {}
    tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]
    measures = [dict(r) for r in db.execute('SELECT * FROM measures').fetchall()]
    columns = [dict(r) for r in db.execute('SELECT * FROM columns').fetchall()]

    # Rule 1: Instruction char limit exceeded (>4800)
    instr_chars = config.get('instr_chars', 0)
    if instr_chars > 4800:
        findings.append({
            'issue': f'Instruction character limit exceeded: {instr_chars} chars (limit: 4800)',
            'severity': 'CRITICAL',
            'evidence': f'agent_config.instr_chars = {instr_chars}. Silent truncation breaks all routing.',
            'impact_ms': 8000,
            'fix': 'Trim instructions to under 3,800 chars preserving routing rules',
            'agent_id': 'schema',
        })

    # Rule 2: Instructions near limit (>4000)
    elif instr_chars > 4000:
        findings.append({
            'issue': f'Instructions near character limit: {instr_chars} chars (warning: 4000)',
            'severity': 'HIGH',
            'evidence': f'agent_config.instr_chars = {instr_chars}. Risk of truncation on edge cases.',
            'impact_ms': 4000,
            'fix': 'Trim instructions to under 3,800 chars',
            'agent_id': 'schema',
        })

    # Rule 3: Extreme schema scope bloat (>30 tables)
    tables_checked = config.get('tables_checked', 0)
    if tables_checked > 30:
        findings.append({
            'issue': f'Extreme schema scope bloat: {tables_checked} tables checked',
            'severity': 'CRITICAL',
            'evidence': f'agent_config.tables_checked = {tables_checked}. ~8000ms schema lookup every query.',
            'impact_ms': 8000,
            'fix': 'Reduce to 12 core tables via AI Data Schema',
            'agent_id': 'schema',
        })
    # Rule 4: High schema scope bloat (>20 tables)
    elif tables_checked > 20:
        findings.append({
            'issue': f'High schema scope bloat: {tables_checked} tables checked',
            'severity': 'HIGH',
            'evidence': f'agent_config.tables_checked = {tables_checked}. ~4800ms schema lookup every query.',
            'impact_ms': 4800,
            'fix': 'Reduce table count via AI Data Schema',
            'agent_id': 'schema',
        })

    # Rule 5: Zero verified answers
    va_count = config.get('va_count', 0)
    if va_count == 0:
        findings.append({
            'issue': 'Zero verified answers configured',
            'severity': 'HIGH',
            'evidence': f'agent_config.va_count = 0. Every KPI pays full NL→DAX cost.',
            'impact_ms': 6000,
            'fix': 'Add 8+ verified answer DAX patterns for high-frequency KPIs',
            'agent_id': 'schema',
        })
    # Rule 6: Low verified answers (<5)
    elif va_count < 5:
        findings.append({
            'issue': f'Low verified answer count: {va_count}',
            'severity': 'MEDIUM',
            'evidence': f'agent_config.va_count = {va_count}. High-frequency KPIs unprotected.',
            'impact_ms': 3000,
            'fix': 'Add more verified answers for common KPI queries',
            'agent_id': 'schema',
        })

    # Rule 7: Exact duplicate measure names
    measure_names = [m['name'] for m in measures]
    seen = {}
    for name in measure_names:
        if name in seen:
            findings.append({
                'issue': f'Exact duplicate measure name: "{name}"',
                'severity': 'CRITICAL',
                'evidence': f'Measure "{name}" appears multiple times. Agent picks randomly.',
                'impact_ms': 5000,
                'fix': 'Rename or remove duplicate measures',
                'agent_id': 'schema',
            })
        seen[name] = True

    # Rule 8: Fuzzy duplicate measures (>85% similarity)
    for i, m1 in enumerate(measures):
        for m2 in measures[i + 1:]:
            if m1['name'] != m2['name']:
                similarity = _name_similarity(m1['name'], m2['name'])
                if similarity > 0.85:
                    findings.append({
                        'issue': f'Fuzzy duplicate measures: "{m1["name"]}" vs "{m2["name"]}" ({similarity:.0%} similar)',
                        'severity': 'HIGH',
                        'evidence': f'High similarity causes extra LLM reasoning per ambiguous query.',
                        'impact_ms': 2000,
                        'fix': 'Clarify measure names or add descriptions to disambiguate',
                        'agent_id': 'schema',
                    })

    # Rule 9: Missing table descriptions (>30% null)
    tables_without_desc = sum(1 for t in tables if not t.get('description'))
    if len(tables) > 0 and tables_without_desc / len(tables) > 0.30:
        findings.append({
            'issue': f'Missing table descriptions: {tables_without_desc}/{len(tables)} tables lack descriptions',
            'severity': 'MEDIUM',
            'evidence': f'{tables_without_desc / len(tables):.0%} of tables have no description. LLM guesses purpose from name.',
            'impact_ms': 1500,
            'fix': 'Add descriptions to all tables in semantic model',
            'agent_id': 'schema',
        })

    # Rule 10: Hidden columns referenced (check for hidden cols)
    hidden_cols = [c for c in columns if c.get('is_hidden')]
    if hidden_cols:
        findings.append({
            'issue': f'{len(hidden_cols)} hidden columns detected in model',
            'severity': 'MEDIUM',
            'evidence': f'Hidden columns may be referenced by verified answers or DAX, causing silent failures.',
            'impact_ms': 1000,
            'fix': 'Verify no verified answer DAX references hidden columns',
            'agent_id': 'schema',
        })

    # Rule 11: Schema/agent table mismatch
    if config.get('tables_checked', 0) > 0 and len(tables) > 0:
        if config['tables_checked'] != len(tables):
            findings.append({
                'issue': f'Schema/agent table mismatch: Prep for AI shows {config["tables_checked"]} tables, model has {len(tables)}',
                'severity': 'HIGH',
                'evidence': 'Prep for AI table selection differs from agent scope. Unpredictable routing.',
                'impact_ms': 3000,
                'fix': 'Align Prep for AI table selection with intended agent scope',
                'agent_id': 'schema',
            })

    db.close()
    return findings


def _name_similarity(a, b):
    """Simple character-level similarity ratio."""
    a_lower = a.lower().replace(' ', '').replace('_', '')
    b_lower = b.lower().replace(' ', '').replace('_', '')
    if not a_lower or not b_lower:
        return 0.0
    matches = sum(1 for c1, c2 in zip(a_lower, b_lower) if c1 == c2)
    return (2.0 * matches) / (len(a_lower) + len(b_lower))
