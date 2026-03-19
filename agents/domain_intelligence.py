"""Agent 1 — Domain Intelligence Agent.
Rule-based domain inference (no LLM). LLM call only for hypothesis generation
and adversarial probe question generation.
"""
import sqlite3
import json

DOMAIN_SIGNALS = {
    'CLINICAL_INPATIENT': ['encounter', 'admission', 'drg', 'los', 'discharge', 'physician', 'readmission'],
    'CLINICAL_QUALITY': ['sepsis', 'bundle', 'compliance', 'antibiotic', 'lactate', 'mortality'],
    'REVENUE_CYCLE': ['claim', 'denial', 'payer', 'ar', 'collection', 'billing', 'charge'],
    'WORKFORCE': ['staffing', 'hppd', 'nursing', 'agency', 'overtime', 'vacancy', 'shift'],
    'SUPPLY_CHAIN': ['inventory', 'vendor', 'purchase', 'contract', 'par', 'supply', 'spend'],
    'PATIENT_EXPERIENCE': ['hcahps', 'ganey', 'satisfaction', 'rounding', 'complaint', 'survey'],
    'OPERATIONAL': ['throughput', 'capacity', 'utilization', 'wait', 'flow', 'bed', 'turnaround'],
    'FINANCIAL': ['budget', 'variance', 'margin', 'cost', 'revenue', 'drg', 'contribution'],
}

# Universal questions (8) that work for any agent
UNIVERSAL_QUESTIONS = [
    {"question": "What is the total count of records?", "category": "simple_kpi", "is_cross_entity": False},
    {"question": "Show me the count filtered to this month", "category": "filtered_aggregate", "is_cross_entity": False},
    {"question": "What are the top 10 items by volume?", "category": "ranking", "is_cross_entity": True},
    {"question": "How does this year compare to last year?", "category": "time_intelligence", "is_cross_entity": False},
    {"question": "What is the current KPI versus the target?", "category": "kpi_vs_target", "is_cross_entity": False},
    {"question": "Show the breakdown by category and subcategory", "category": "cross_entity", "is_cross_entity": True},
    {"question": "What is the overall system-wide total?", "category": "system_aggregate", "is_cross_entity": False},
    {"question": "Show the trend over the last 6 months", "category": "trend", "is_cross_entity": False},
]


def infer_domain(table_names, measure_names, col_names):
    """Rule-based domain classification — no LLM needed."""
    vocab = ' '.join(table_names + measure_names + col_names).lower()
    scores = {
        domain: sum(1 for sig in signals if sig in vocab)
        for domain, signals in DOMAIN_SIGNALS.items()
    }
    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]
    total_signals = sum(scores.values())
    confidence = best_score / max(total_signals, 1)
    return best_domain, confidence, scores


def detect_config_issues(agent_config):
    """Detect configuration issues from agent_config data."""
    issues = []
    if agent_config.get('instr_chars', 0) > 4800:
        issues.append('CRITICAL: Instruction char limit exceeded ({} > 4800)'.format(agent_config['instr_chars']))
    elif agent_config.get('instr_chars', 0) > 4000:
        issues.append('HIGH: Instructions near limit ({} > 4000)'.format(agent_config['instr_chars']))
    if agent_config.get('tables_checked', 0) > 30:
        issues.append('CRITICAL: Extreme schema scope bloat ({} tables)'.format(agent_config['tables_checked']))
    elif agent_config.get('tables_checked', 0) > 20:
        issues.append('HIGH: High schema scope bloat ({} tables)'.format(agent_config['tables_checked']))
    if agent_config.get('va_count', 0) == 0:
        issues.append('HIGH: Zero verified answers')
    elif agent_config.get('va_count', 0) < 5:
        issues.append('MEDIUM: Low verified answers ({})'.format(agent_config['va_count']))
    return issues


def generate_domain_questions(domain, measure_names, table_names):
    """Generate 12 domain-specific probe questions."""
    questions = []
    measures = measure_names[:6] if measure_names else ['Total Count']

    for i, measure in enumerate(measures):
        questions.append({
            "question": f"What is the current {measure}?",
            "category": "domain_kpi",
            "is_cross_entity": False,
            "hypothesis": f"Tests direct measure access for {measure}",
            "targets_table": table_names[0] if table_names else None,
        })
        if i < 3:
            questions.append({
                "question": f"Show {measure} broken down by provider",
                "category": "cross_entity",
                "is_cross_entity": True,
                "hypothesis": f"Tests cross-entity join for {measure}",
                "targets_table": table_names[0] if table_names else None,
            })

    # Add governance and routing test questions
    if len(table_names) > 1:
        questions.append({
            "question": f"Show data from {table_names[-1]} by category",
            "category": "secondary_table",
            "is_cross_entity": True,
            "hypothesis": f"Tests routing to secondary table {table_names[-1]}",
            "targets_table": table_names[-1],
        })

    # Pad to 12 if needed
    while len(questions) < 12:
        questions.append({
            "question": f"What is the average value across all records?",
            "category": "domain_generic",
            "is_cross_entity": False,
            "hypothesis": "Generic domain question",
            "targets_table": table_names[0] if table_names else None,
        })

    return questions[:12]


def run(db_path, session_state=None):
    """Run Domain Intelligence Agent."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # Load metadata
    tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]
    measures = [dict(r) for r in db.execute('SELECT * FROM measures').fetchall()]
    columns = [dict(r) for r in db.execute('SELECT * FROM columns').fetchall()]
    config_row = db.execute('SELECT * FROM agent_config LIMIT 1').fetchone()
    agent_config = dict(config_row) if config_row else {}

    table_names = [t['name'] for t in tables]
    measure_names = [m['name'] for m in measures]
    col_names = [c['name'] for c in columns]

    # Rule-based domain inference
    domain, confidence, scores = infer_domain(table_names, measure_names, col_names)

    # Detect config issues
    config_issues = detect_config_issues(agent_config)

    # Generate all 20 probe questions (8 universal + 12 domain)
    domain_questions = generate_domain_questions(domain, measure_names, table_names)
    all_questions = UNIVERSAL_QUESTIONS + domain_questions

    # Build findings
    findings = []
    for issue in config_issues:
        severity = issue.split(':')[0].strip()
        findings.append({
            'issue': issue.split(':', 1)[1].strip() if ':' in issue else issue,
            'severity': severity,
            'evidence': f'Detected from agent_config metadata',
            'impact_ms': 0,
            'fix': '',
            'agent_id': 'domain_intelligence',
        })

    db.close()

    return {
        'domain': domain,
        'confidence': confidence,
        'domain_scores': scores,
        'probe_questions': all_questions,
        'config_issues': config_issues,
        'findings': findings,
    }
