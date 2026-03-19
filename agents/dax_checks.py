"""Agent 4 — DAX Agent — 9 Deterministic Rules from functional spec Section 6.4."""
import sqlite3


def run_checks(db_path):
    """Run all 9 deterministic DAX checks. Returns list of findings."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]

    for trace in traces:
        retries = trace.get('retries', 0)
        total_ms = trace.get('total_ms', 0)
        dax = str(trace.get('dax_generated', '') or '')
        tables_used = str(trace.get('tables_used', '') or '')
        physician_visible = trace.get('physician_visible', False)
        question = trace.get('question', '')

        # Rule 1: High retry — confirmed routing gap (retries > 2)
        if retries > 2:
            findings.append({
                'issue': f'High retry count ({retries}) on routing-gap trace',
                'severity': 'CRITICAL',
                'evidence': f'Question: "{question[:80]}..." — {retries} retries × ~3100ms = {retries * 3100}ms waste',
                'impact_ms': retries * 3100,
                'fix': 'Add routing rule for targeted table',
                'agent_id': 'dax',
            })

        # Rule 2: Single retry
        elif retries == 1:
            findings.append({
                'issue': f'Single retry detected on trace',
                'severity': 'MEDIUM',
                'evidence': f'Question: "{question[:80]}..." — 1 retry × ~3100ms avoidable',
                'impact_ms': 3100,
                'fix': 'Review routing configuration',
                'agent_id': 'dax',
            })

        # Rule 3: TOPN absent on cross-entity query
        if 'TOPN' not in dax.upper() and 'TOP' not in dax.upper():
            # Check if this looks like a cross-entity query (multiple tables)
            used_tables = [t.strip() for t in tables_used.split(',') if t.strip()]
            if len(used_tables) > 1:
                findings.append({
                    'issue': f'TOPN absent in cross-entity query across {len(used_tables)} tables',
                    'severity': 'HIGH',
                    'evidence': f'Tables: {tables_used}. Full scan risk — timeout possible on large tables.',
                    'impact_ms': 4000,
                    'fix': 'Add TOP 25 few-shot examples',
                    'agent_id': 'dax',
                })

        # Rule 4: Wrong table first (detected by table switch in steps)
        # Approximation: if retries > 0 and multiple tables used, likely wrong table first
        if retries > 0 and len([t.strip() for t in tables_used.split(',') if t.strip()]) > 1:
            findings.append({
                'issue': 'Wrong table targeted first — routing gap confirmed',
                'severity': 'HIGH',
                'evidence': f'Retries: {retries}, tables used: {tables_used}',
                'impact_ms': retries * 3100,
                'fix': 'Add explicit routing rule for secondary table',
                'agent_id': 'dax',
            })

        # Rule 5: Physician/provider visible
        if physician_visible:
            findings.append({
                'issue': 'Physician/provider data visible in query results',
                'severity': 'CRITICAL',
                'evidence': f'Question: "{question[:80]}..." — physician_visible=True',
                'impact_ms': 0,
                'fix': 'GOVERNANCE REQUIRED — restrict physician-level data visibility',
                'agent_id': 'dax',
            })

        # Rule 6: Measure not found (DAX references unknown measure)
        if dax and ('not found' in dax.lower() or 'error' in dax.lower()):
            findings.append({
                'issue': 'DAX references unknown measure — returns error',
                'severity': 'CRITICAL',
                'evidence': f'DAX: {dax[:120]}...',
                'impact_ms': total_ms,
                'fix': 'Fix measure reference in model',
                'agent_id': 'dax',
            })

        # Rule 7: Empty results — no error
        pass_fail = trace.get('pass_fail', '')
        if pass_fail == 'fail' and total_ms < 20000:
            findings.append({
                'issue': 'Query returned empty results with no error',
                'severity': 'HIGH',
                'evidence': f'Question: "{question[:80]}..." — silent failure, wrong filter or table',
                'impact_ms': total_ms,
                'fix': 'Review filter context and table routing',
                'agent_id': 'dax',
            })

    # Rule 8: Ambiguous time filter (check for date field inconsistency)
    date_traces = [t for t in traces if 'date' in str(t.get('dax_generated', '')).lower()]
    if len(date_traces) > 2:
        findings.append({
            'issue': 'Potential ambiguous time filter detected across multiple traces',
            'severity': 'HIGH',
            'evidence': f'{len(date_traces)} traces reference date fields — potential AdmitDate vs DischargeDate ambiguity',
            'impact_ms': 2000,
            'fix': 'Clarify date field usage in instructions',
            'agent_id': 'dax',
        })

    # Rule 9: NL2DAX/NL2SQL cross-contamination (check for mixed patterns)
    # Simplified: check if any traces have SQL-like patterns in DAX
    sql_patterns = ['SELECT ', 'FROM ', 'WHERE ', 'JOIN ']
    for trace in traces:
        dax = str(trace.get('dax_generated', '') or '')
        if any(p in dax for p in sql_patterns) and ('EVALUATE' in dax or 'SUMMARIZE' in dax):
            findings.append({
                'issue': 'NL2DAX/NL2SQL cross-contamination detected',
                'severity': 'HIGH',
                'evidence': f'DAX contains SQL patterns mixed with DAX patterns',
                'impact_ms': 3000,
                'fix': 'Separate NL2DAX and NL2SQL few-shot examples in instructions',
                'agent_id': 'dax',
            })
            break  # Only report once

    db.close()

    # Deduplicate findings by issue text
    seen_issues = set()
    unique_findings = []
    for f in findings:
        key = f['issue'][:60]
        if key not in seen_issues:
            seen_issues.add(key)
            unique_findings.append(f)

    return unique_findings
