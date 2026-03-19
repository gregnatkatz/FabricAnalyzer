"""Agent 5 — Execution Agent — 9 Deterministic Rules from functional spec Section 6.5."""
import sqlite3


def run_checks(db_path):
    """Run all 9 deterministic execution checks. Returns list of findings."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
    cu_rows = [dict(r) for r in db.execute('SELECT * FROM cu_metrics').fetchall()]
    models = [dict(r) for r in db.execute('SELECT * FROM models').fetchall()]
    tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]

    cu = cu_rows[0] if cu_rows else {}
    model = models[0] if models else {}

    for trace in traces:
        total_ms = trace.get('total_ms', 0)
        bd_exec = trace.get('bd_exec', 0)
        bd_nldax = trace.get('bd_nldax', 0)
        bd_schema = trace.get('bd_schema', 0)
        retries = trace.get('retries', 0)
        question = trace.get('question', '')

        # Rule 1: Outlier trace (>45000ms)
        if total_ms > 45000:
            findings.append({
                'issue': f'Outlier trace: {total_ms}ms (>45s threshold)',
                'severity': 'CRITICAL',
                'evidence': f'Question: "{question[:80]}..." — deep investigation required',
                'impact_ms': total_ms,
                'fix': 'Investigate root cause — likely combination of retry + scope + DAX issues',
                'agent_id': 'execution',
            })

        # Rule 2: Slow trace (>20000ms)
        elif total_ms > 20000:
            findings.append({
                'issue': f'Slow trace: {total_ms}ms (>20s threshold)',
                'severity': 'HIGH',
                'evidence': f'Question: "{question[:80]}..." — above acceptable threshold',
                'impact_ms': total_ms - 10000,
                'fix': 'Apply targeted fixes based on breakdown analysis',
                'agent_id': 'execution',
            })

        # Rule 3: Execution dominant (bd_exec / total_ms > 0.35)
        if total_ms > 0 and bd_exec / total_ms > 0.35:
            findings.append({
                'issue': f'Execution phase dominant: {bd_exec / total_ms:.0%} of total latency',
                'severity': 'HIGH',
                'evidence': f'bd_exec={bd_exec}ms / total={total_ms}ms — VertiPaq or Direct Lake issue',
                'impact_ms': bd_exec,
                'fix': 'Apply V-Order optimization or check Direct Lake configuration',
                'agent_id': 'execution',
            })

        # Rule 4: DAX generation dominant (bd_nldax / total_ms > 0.55)
        if total_ms > 0 and bd_nldax / total_ms > 0.55:
            findings.append({
                'issue': f'DAX generation phase dominant: {bd_nldax / total_ms:.0%} of total latency',
                'severity': 'HIGH',
                'evidence': f'bd_nldax={bd_nldax}ms / total={total_ms}ms — generation bottleneck not execution',
                'impact_ms': bd_nldax,
                'fix': 'Add verified answers and simplify instructions to reduce generation time',
                'agent_id': 'execution',
            })

        # Rule 5: Retry dominant (retries × 3100 > total_ms × 0.4)
        if retries > 0 and retries * 3100 > total_ms * 0.4:
            findings.append({
                'issue': f'Retry-dominant latency: retries account for {retries * 3100 / total_ms:.0%}',
                'severity': 'HIGH',
                'evidence': f'{retries} retries × 3100ms = {retries * 3100}ms of {total_ms}ms total',
                'impact_ms': retries * 3100,
                'fix': 'Routing fix would halve latency — add routing rules',
                'agent_id': 'execution',
            })

        # Rule 6: Schema lookup dominant (bd_schema / total_ms > 0.25)
        if total_ms > 0 and bd_schema / total_ms > 0.25:
            findings.append({
                'issue': f'Schema lookup dominant: {bd_schema / total_ms:.0%} of total latency',
                'severity': 'HIGH',
                'evidence': f'bd_schema={bd_schema}ms / total={total_ms}ms — scope reduction needed urgently',
                'impact_ms': bd_schema,
                'fix': 'Reduce schema scope to core tables only',
                'agent_id': 'execution',
            })

    # Rule 7: High CU throttling (throttle_events > 50 in 7d)
    throttle_events = cu.get('throttle_events', 0)
    if throttle_events > 50:
        findings.append({
            'issue': f'High CU throttling: {throttle_events} events in monitoring period',
            'severity': 'CRITICAL',
            'evidence': f'cu_metrics.throttle_events = {throttle_events}. Capacity constraint affecting all queries.',
            'impact_ms': 5000,
            'fix': 'Increase capacity units or optimize workload distribution',
            'agent_id': 'execution',
        })

    # Rule 8: V-Order not confirmed (Direct Lake without V-Order evidence)
    storage_mode = model.get('storage_mode', '')
    if 'direct' in str(storage_mode).lower() or 'lake' in str(storage_mode).lower():
        findings.append({
            'issue': 'V-Order optimization not confirmed for Direct Lake model',
            'severity': 'MEDIUM',
            'evidence': f'Model storage mode: {storage_mode}. 15-25% execution gain available with V-Order.',
            'impact_ms': 2000,
            'fix': 'Apply V-Order to Direct Lake tables',
            'agent_id': 'execution',
        })

    # Rule 9: Direct Lake framing risk (table size near capacity limit)
    large_tables = [t for t in tables if t.get('row_count', 0) > 500000]
    if large_tables and ('direct' in str(storage_mode).lower() or 'lake' in str(storage_mode).lower()):
        for t in large_tables:
            findings.append({
                'issue': f'Direct Lake framing risk: table "{t["name"]}" has {t["row_count"]:,} rows',
                'severity': 'HIGH',
                'evidence': f'Large table near capacity limit — silent fallback to DirectQuery mode possible.',
                'impact_ms': 3000,
                'fix': 'Monitor for DirectQuery fallback; consider partitioning',
                'agent_id': 'execution',
            })

    db.close()

    # Deduplicate
    seen = set()
    unique = []
    for f in findings:
        key = f['issue'][:60]
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique
