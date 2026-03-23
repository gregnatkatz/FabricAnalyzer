"""Agent 3b -- DAX Expression Agent -- 10 Deterministic Rules analyzing measure DAX expressions.

Rules EX-1 through EX-10 operate on measures.expression to detect anti-patterns
without requiring XMLA access.
"""
import re
import sqlite3


def run_expression_checks(db_path):
    """Run all 10 DAX expression rules on measures. Returns list of findings."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    measures = [dict(r) for r in db.execute('SELECT * FROM measures').fetchall()]
    db.close()

    for m in measures:
        expr = (m.get('expression', '') or '').strip()
        name = m.get('name', '') or ''
        if not expr:
            continue

        # EX-1: Nested CALCULATE depth > 2
        depth = expr.upper().count('CALCULATE(')
        if depth > 2:
            findings.append({
                'issue': f'Nested CALCULATE depth {depth} in measure "{name}"',
                'severity': 'HIGH',
                'evidence': f'Expression contains {depth} CALCULATE( calls -- deep nesting causes exponential filter context expansion',
                'impact_ms': depth * 800,
                'fix': f'Flatten CALCULATE nesting in "{name}" using VAR/RETURN pattern to precompute intermediate results',
                'agent_id': 'dax_expression',
            })

        # EX-2: SUMX/AVERAGEX over large table (iterator on fact table)
        iterators = re.findall(r'(SUMX|AVERAGEX|COUNTX|MAXX|MINX|RANKX|PRODUCTX)\s*\(\s*(\w+)', expr.upper())
        fact_iterators = [(fn, tbl) for fn, tbl in iterators if tbl.startswith('FACT') or tbl.startswith('DIM')]
        if fact_iterators:
            fn, tbl = fact_iterators[0]
            findings.append({
                'issue': f'Iterator {fn} scanning "{tbl}" in measure "{name}"',
                'severity': 'HIGH',
                'evidence': f'{fn}({tbl},...) performs row-by-row iteration -- extremely expensive on large tables',
                'impact_ms': 2500,
                'fix': f'Replace {fn}({tbl},...) with aggregation function (SUM, AVERAGE) where possible, or add TOPN guard',
                'agent_id': 'dax_expression',
            })

        # EX-3: Missing DIVIDE (division without DIVIDE safety)
        # Look for bare / division without DIVIDE wrapper
        has_bare_division = bool(re.search(r'[^/]/[^/\*]', expr))
        has_divide = 'DIVIDE(' in expr.upper()
        if has_bare_division and not has_divide:
            findings.append({
                'issue': f'Unsafe division in measure "{name}" -- no DIVIDE() wrapper',
                'severity': 'MEDIUM',
                'evidence': 'Expression uses bare "/" operator without DIVIDE() -- risks divide-by-zero errors at runtime',
                'impact_ms': 0,
                'fix': f'Replace "A / B" with "DIVIDE(A, B, 0)" in "{name}" for divide-by-zero safety',
                'agent_id': 'dax_expression',
            })

        # EX-4: FILTER on full table (expensive scan pattern)
        filter_matches = re.findall(r'FILTER\s*\(\s*(\w+)', expr.upper())
        full_table_filters = [t for t in filter_matches if t not in ('VALUES', 'ALL', 'ALLSELECTED', 'DISTINCT')]
        if full_table_filters:
            tbl = full_table_filters[0]
            findings.append({
                'issue': f'FILTER scanning full table "{tbl}" in measure "{name}"',
                'severity': 'HIGH',
                'evidence': f'FILTER({tbl},...) scans every row -- use CALCULATE with direct predicate instead',
                'impact_ms': 1800,
                'fix': f'Replace FILTER({tbl},...) with CALCULATE(..., {tbl}[Column] = Value) for predicate pushdown',
                'agent_id': 'dax_expression',
            })

        # EX-5: CROSSJOIN or GENERATE (cartesian product risk)
        if 'CROSSJOIN(' in expr.upper() or 'GENERATE(' in expr.upper():
            findings.append({
                'issue': f'Cartesian product risk in measure "{name}" (CROSSJOIN/GENERATE)',
                'severity': 'CRITICAL',
                'evidence': 'Expression uses CROSSJOIN or GENERATE -- creates cartesian product that can explode row counts',
                'impact_ms': 5000,
                'fix': f'Replace CROSSJOIN/GENERATE in "{name}" with SUMMARIZE or TREATAS for controlled expansion',
                'agent_id': 'dax_expression',
            })

        # EX-6: ALL() without ALLSELECTED -- may break user filter context
        has_all = bool(re.search(r'\bALL\s*\(', expr.upper()))
        has_allselected = 'ALLSELECTED(' in expr.upper()
        if has_all and not has_allselected:
            # Only flag if inside CALCULATE (context modification)
            if 'CALCULATE(' in expr.upper():
                findings.append({
                    'issue': f'ALL() without ALLSELECTED in measure "{name}" -- may override user filters',
                    'severity': 'MEDIUM',
                    'evidence': 'CALCULATE with ALL() removes all filters -- user slicer selections will be ignored',
                    'impact_ms': 0,
                    'fix': f'Consider using ALLSELECTED() instead of ALL() in "{name}" to preserve user filter context',
                    'agent_id': 'dax_expression',
                })

        # EX-7: Excessive expression length (> 500 chars suggests complexity)
        if len(expr) > 500:
            findings.append({
                'issue': f'Complex measure expression in "{name}" ({len(expr)} chars)',
                'severity': 'MEDIUM',
                'evidence': f'Expression is {len(expr)} characters -- complex measures increase NL2DAX generation time',
                'impact_ms': 600,
                'fix': f'Break "{name}" into smaller sub-measures using VAR/RETURN or helper measures',
                'agent_id': 'dax_expression',
            })

        # EX-8: SELECTEDVALUE / HASONEVALUE pattern (single-select dependency)
        if 'SELECTEDVALUE(' in expr.upper() or 'HASONEVALUE(' in expr.upper():
            findings.append({
                'issue': f'Single-select dependency in measure "{name}" (SELECTEDVALUE/HASONEVALUE)',
                'severity': 'MEDIUM',
                'evidence': 'Measure depends on single-select filter context -- may return blank in multi-select or Data Agent scenarios',
                'impact_ms': 0,
                'fix': f'Add fallback logic in "{name}" for multi-select scenarios: IF(HASONEVALUE(...), SELECTEDVALUE(...), DEFAULT)',
                'agent_id': 'dax_expression',
            })

        # EX-9: Hardcoded year/month literals — demo-killer
        # Matches YEAR([Date]) = 2023, [FiscalYear] = 2024, etc.
        # These cause measures to silently return BLANK as time passes.
        hardcoded_dates = re.findall(
            r'(?:YEAR\s*\([^)]+\)\s*=\s*|=\s*)(\b20\d{2}\b)',
            expr
        )
        col_year_literals = re.findall(
            r'\[\w*(?:year|date|month|period|fy|cy)\w*\]\s*=\s*(\b20\d{2}\b)',
            expr,
            re.IGNORECASE
        )
        all_hardcoded = list(set(hardcoded_dates + col_year_literals))
        if all_hardcoded:
            years = ', '.join(all_hardcoded)
            findings.append({
                'issue': f'Hardcoded date literal(s) in measure "{name}": {years}',
                'severity': 'CRITICAL',
                'impact_ms': 9999,  # sentinel: always sorts to top of findings list
                'evidence': (
                    f'Expression contains hardcoded year value(s) {years}. '
                    f'Once the current year advances past these values the measure '
                    f'silently returns BLANK — queries succeed with no error but '
                    f'the Data Agent returns empty results. Classic demo-killer.'
                ),
                'fix': (
                    f'Replace hardcoded year(s) in "{name}" with dynamic expressions: '
                    f'YEAR(TODAY()), YEAR(MAX(DateTable[Date])), or a fiscal year '
                    f'parameter. Never use a literal 4-digit year in a measure '
                    f'that will be used beyond the current reporting period.'
                ),
                'agent_id': 'dax_expression',
            })

        # EX-10: USERELATIONSHIP direction validation required
        # USERELATIONSHIP(A[col], B[col]) activates an inactive relationship.
        # Wrong column order (many-side listed second instead of first) silently
        # produces incorrect aggregations with no error and no retry.
        userel_matches = re.findall(
            r'USERELATIONSHIP\s*\(\s*([^,]+),\s*([^)]+)\)',
            expr,
            re.IGNORECASE
        )
        for col_a, col_b in userel_matches:
            col_a = col_a.strip()
            col_b = col_b.strip()
            findings.append({
                'issue': f'USERELATIONSHIP in measure "{name}" — direction validation required',
                'severity': 'HIGH',
                'impact_ms': 4000,
                'evidence': (
                    f'Expression uses USERELATIONSHIP({col_a}, {col_b}). '
                    f'If column order is reversed (many-side listed second instead of first) '
                    f'the relationship activates in the wrong direction — aggregations return '
                    f'incorrect values with no error and no retry. Silent wrong answer.'
                ),
                'fix': (
                    f'Verify relationship direction for USERELATIONSHIP({col_a}, {col_b}). '
                    f'Many-side column must be listed first: USERELATIONSHIP(FactTable[FK], DimTable[PK]). '
                    f'Confirm in Power BI Desktop → Model view → relationship properties.'
                ),
                'agent_id': 'dax_expression',
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


def run_expression_checks_with_llm(db_path, proxy_url, chromadb_path, session_id,
                                    domain, behavioral_evidence, agent_models,
                                    run_agent_with_llm_fn, merge_findings_fn,
                                    write_findings_fn):
    """Run DAX Expression agent: 10 deterministic rules + DeepSeek LLM analysis.

    Calls run_expression_checks() first for the deterministic pass, then sends
    the measure list + deterministic findings to DeepSeek for pattern detection
    that regex can't catch (circular refs, BLANK propagation, hardcoded dates, etc.).

    Arguments use injected helpers from pipeline.py to avoid circular imports.
    """
    import sqlite3
    import json

    # Step 1: deterministic pass (existing 10 rules, fast, no LLM)
    det_findings = run_expression_checks(db_path)

    # Step 2: LLM pass via DeepSeek (fast, not a reasoning model)
    llm_findings = []
    if proxy_url:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        measures = [dict(r) for r in db.execute('SELECT name, expression FROM measures').fetchall()]
        tables = [r['name'] for r in db.execute('SELECT name FROM tables').fetchall()]
        db.close()

        template_vars = {
            'domain': domain,
            'table_names': ', '.join(tables),
            'measure_names': ', '.join(m['name'] for m in measures),
            'deterministic_findings': json.dumps(det_findings),
            'behavioral_evidence': behavioral_evidence,
        }

        model = agent_models.get('dax_expression', 'DeepSeek-V3.2-Speciale')
        llm_findings, _ = run_agent_with_llm_fn(
            'dax_expression', 'dax_expression', template_vars,
            proxy_url, chromadb_path, session_id,
            model_override=model,
        )

    # Merge: deterministic takes precedence, LLM fills the gaps
    merged = merge_findings_fn(det_findings, llm_findings)
    write_findings_fn(db_path, merged, agent_id_override='dax_expression')
    return 'dax_expression', {'findings': merged}, merged
