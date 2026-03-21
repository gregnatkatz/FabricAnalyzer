"""Agent 5 — Execution Agent — 10 Deterministic Rules from functional spec Section 6.5."""
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

        # Rule 10: High platform overhead (bd_other / total_ms > 0.35)
        bd_other = trace.get('bd_other', None)
        if bd_other is None:
            bd_other = max(0, total_ms - (trace.get('bd_parse', 0) or 0) - bd_schema - bd_nldax - bd_exec - (trace.get('bd_synth', 0) or 0))
        if total_ms > 0 and bd_other / total_ms > 0.35:
            findings.append({
                'issue': f'High platform overhead: {bd_other / total_ms:.0%} of total latency is unaccounted',
                'severity': 'MEDIUM',
                'evidence': f'bd_other={bd_other}ms / total={total_ms}ms — network, token counting, or Fabric platform overhead',
                'impact_ms': 0,
                'fix': 'Not directly fixable — indicates Fabric capacity constraint or network latency between components',
                'agent_id': 'execution',
            })

    # Rule 10b: High retry density (aggregate across all traces)
    total_retries = sum(t.get('retries', 0) for t in traces)
    total_questions = len(traces)
    if total_questions > 0:
        retry_density = total_retries / total_questions
        if retry_density > 2.0:
            findings.append({
                'issue': f'High retry density: avg {retry_density:.1f} retries/question ({total_retries} retries across {total_questions} questions)',
                'severity': 'CRITICAL',
                'evidence': f'Retry density {retry_density:.1f}x exceeds 2.0 threshold — indicates systematic DAX generation failure, not random timeouts. Root cause is likely missing routing rules or ambiguous schema.',
                'impact_ms': int(total_retries * 3100 / total_questions),
                'fix': 'Add explicit routing rules mapping query keywords to correct tables. High density means every question is hitting the wrong table first.',
                'agent_id': 'execution',
            })

    # Rule 7: Capacity throttling — uses throttle_state: 0=Active, 99=Throttled, 999=Suspended
    throttle_state = cu.get('throttle_state', cu.get('throttle_events', 0))
    if throttle_state >= 999:
        findings.append({
            'issue': 'Fabric capacity SUSPENDED — all queries blocked',
            'severity': 'CRITICAL',
            'evidence': f'throttle_state={throttle_state}. Capacity is suspended — no queries can execute.',
            'impact_ms': 10000,
            'fix': 'Resume capacity in Fabric admin portal or contact your Fabric administrator',
            'agent_id': 'execution',
        })
    elif throttle_state >= 99:
        findings.append({
            'issue': 'Fabric capacity currently THROTTLED — queries delayed',
            'severity': 'CRITICAL',
            'evidence': f'throttle_state={throttle_state}. Capacity is throttled — queries are being queued and delayed.',
            'impact_ms': 5000,
            'fix': 'Reduce CU consumption by optimizing queries or increase capacity tier',
            'agent_id': 'execution',
        })
    elif cu.get('ai_cu_consumed', 0) > 0 and cu.get('ai_cu_consumed', 0) > 0.85 * 100:
        findings.append({
            'issue': f'AI CU consumption high: {cu.get("ai_cu_consumed", 0):.0f} CUs (>85% of typical SKU allocation)',
            'severity': 'HIGH',
            'evidence': f'ai_cu_consumed={cu.get("ai_cu_consumed", 0):.0f}. Approaching throttle threshold.',
            'impact_ms': 3000,
            'fix': 'Optimize high-CU queries to reduce consumption before throttling occurs',
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
