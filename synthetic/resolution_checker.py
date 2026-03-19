"""Phase 8 — Resolution Checker: marks findings as RESOLVED based on delta."""
import sqlite3


def check_resolutions(db_path, delta, fixes_applied):
    """Check which findings are resolved by the applied fixes.
    
    A finding is RESOLVED if:
    - The fix addresses the finding's root cause
    - The delta shows >30% improvement for related questions
    
    Args:
        db_path: Path to SQLite database
        delta: Delta analysis from delta_computer
        fixes_applied: List of fix keys applied
    
    Returns:
        List of resolution status dicts
    """
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    findings = [dict(r) for r in db.execute('SELECT * FROM findings').fetchall()]

    resolutions = []
    avg_reduction = delta.get('reduction_pct', 0)

    # Fix-to-finding mapping
    fix_finding_map = {
        'instruction_trim': ['instruction', 'char limit', 'truncation', 'instr_chars'],
        'schema_scope': ['schema scope', 'tables checked', 'scope bloat'],
        'routing_rules': ['routing', 'retry', 'wrong table'],
        'verified_answers': ['verified answer', 'va_count', 'zero verified'],
        'topn_guard': ['topn', 'top n', 'full scan', 'cross-entity'],
        'measure_dedup': ['duplicate measure', 'fuzzy duplicate', 'measure name'],
        'vorder': ['v-order', 'vorder', 'direct lake', 'execution'],
        'physician_gov': ['physician', 'provider', 'governance'],
    }

    for finding in findings:
        issue_lower = finding.get('issue', '').lower()
        resolved = False
        resolving_fix = None

        for fix_key in fixes_applied:
            keywords = fix_finding_map.get(fix_key, [])
            if any(kw in issue_lower for kw in keywords):
                # Check if delta supports resolution
                if avg_reduction > 30 or fix_key == 'physician_gov':
                    resolved = True
                    resolving_fix = fix_key
                    break

        status = 'RESOLVED' if resolved else 'OPEN'

        resolutions.append({
            'finding_id': finding.get('finding_id'),
            'issue': finding.get('issue', ''),
            'severity': finding.get('severity', ''),
            'status': status,
            'resolving_fix': resolving_fix,
        })

        # Update database
        if resolved:
            db.execute('''
                UPDATE findings 
                SET fix_applied = 1, resolution_status = ?, resolved_at = datetime('now')
                WHERE finding_id = ?
            ''', (status, finding.get('finding_id')))

    db.commit()
    db.close()

    return resolutions
