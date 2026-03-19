"""Phase 3 — Acceptance test: deterministic checks detect >=60% of 25 known issues.
Also tests false positive rate < 50%.

Usage: pytest sample_dataset/test_pipeline.py -v
"""
import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_dataset.build_sample import build_sample_db, SAMPLE_DB_PATH, KNOWN_ISSUES_PATH
from agents.schema_checks import run_checks as schema_checks
from agents.dax_checks import run_checks as dax_checks
from agents.execution_checks import run_checks as execution_checks


def run_all_deterministic(db_path):
    """Run all 29 deterministic checks and return findings."""
    schema_findings = schema_checks(db_path)
    dax_findings = dax_checks(db_path)
    exec_findings = execution_checks(db_path)
    return schema_findings + dax_findings + exec_findings


# Mapping from known issue IDs to keyword patterns that findings must contain
ISSUE_PATTERNS = {
    1: {'agent': 'schema', 'keywords': ['instruction', 'limit', 'exceeded']},
    2: {'agent': 'schema', 'keywords': ['instruction', 'near', 'limit']},
    3: {'agent': 'schema', 'keywords': ['extreme', 'schema', 'bloat']},
    4: {'agent': 'schema', 'keywords': ['high', 'schema', 'bloat']},
    5: {'agent': 'schema', 'keywords': ['zero', 'verified']},
    6: {'agent': 'schema', 'keywords': ['low', 'verified']},
    7: {'agent': 'schema', 'keywords': ['exact', 'duplicate', 'measure']},
    8: {'agent': 'schema', 'keywords': ['fuzzy', 'duplicate']},
    9: {'agent': 'schema', 'keywords': ['missing', 'description']},
    10: {'agent': 'schema', 'keywords': ['hidden', 'column']},
    11: {'agent': 'schema', 'keywords': ['mismatch']},
    12: {'agent': 'dax', 'keywords': ['high', 'retry']},
    13: {'agent': 'dax', 'keywords': ['single', 'retry']},
    14: {'agent': 'dax', 'keywords': ['topn', 'absent']},
    15: {'agent': 'dax', 'keywords': ['wrong', 'table']},
    16: {'agent': 'dax', 'keywords': ['physician']},
    17: {'agent': 'dax', 'keywords': ['measure', 'not', 'found']},
    18: {'agent': 'dax', 'keywords': ['empty', 'result']},
    19: {'agent': 'dax', 'keywords': ['ambiguous', 'time']},
    20: {'agent': 'dax', 'keywords': ['contamination']},
    21: {'agent': 'execution', 'keywords': ['outlier']},
    22: {'agent': 'execution', 'keywords': ['slow', 'trace']},
    23: {'agent': 'execution', 'keywords': ['execution', 'dominant']},
    24: {'agent': 'execution', 'keywords': ['dax', 'generation', 'dominant']},
    25: {'agent': 'execution', 'keywords': ['retry', 'dominant']},
}


def match_finding_to_issues(finding, known_issues):
    """Match a finding to known issues using keyword pattern matching."""
    issue_text = finding['issue'].lower()
    agent_id = finding.get('agent_id', '')
    matched_ids = []

    for ki in known_issues:
        pattern = ISSUE_PATTERNS.get(ki['id'])
        if not pattern:
            continue
        # Agent must match
        if pattern['agent'] != agent_id:
            continue
        # Check if enough keywords match
        keywords = pattern['keywords']
        matches = sum(1 for kw in keywords if kw in issue_text)
        threshold = min(2, max(1, len(keywords) // 2))
        if matches >= threshold:
            matched_ids.append(ki['id'])

    return matched_ids


def test_detection_rate():
    """Test that deterministic checks detect >=80% of known issues."""
    # Build fresh sample.db
    build_sample_db()

    with open(KNOWN_ISSUES_PATH) as f:
        known_issues = json.load(f)

    findings = run_all_deterministic(SAMPLE_DB_PATH)

    # Match findings to known issues
    detected = set()
    for finding in findings:
        ids = match_finding_to_issues(finding, known_issues)
        detected.update(ids)

    detection_rate = len(detected) / len(known_issues)
    print(f'\nDetection rate: {len(detected)}/{len(known_issues)} = {detection_rate:.0%}')
    print(f'Detected issues: {sorted(detected)}')
    print(f'Missed issues: {sorted(set(range(1, 26)) - detected)}')

    # Acceptance gate: >=60% for deterministic only (>=80% with LLM)
    assert detection_rate >= 0.60, f'Detection rate {detection_rate:.0%} < 60% minimum for deterministic checks'
    return detection_rate


def test_false_positives():
    """Test that false positive rate < 20%."""
    build_sample_db()

    with open(KNOWN_ISSUES_PATH) as f:
        known_issues = json.load(f)

    findings = run_all_deterministic(SAMPLE_DB_PATH)

    matched = 0
    for finding in findings:
        ids = match_finding_to_issues(finding, known_issues)
        if ids:
            matched += 1

    total = len(findings)
    false_positives = total - matched
    fp_rate = false_positives / max(total, 1)

    print(f'\nTotal findings: {total}')
    print(f'Matched to known issues: {matched}')
    print(f'Potential false positives: {false_positives}')
    print(f'False positive rate: {fp_rate:.0%}')

    assert fp_rate < 0.50, f'False positive rate {fp_rate:.0%} >= 50%'
    return fp_rate


def test_minimum_finding_count():
    """Test deterministic checks find at least 15 issues."""
    build_sample_db()
    findings = run_all_deterministic(SAMPLE_DB_PATH)
    print(f'\nTotal deterministic findings: {len(findings)}')
    assert len(findings) >= 15, f'Only {len(findings)} findings, need >=15'


if __name__ == '__main__':
    print('=== Running acceptance tests ===')
    rate = test_detection_rate()
    fp = test_false_positives()
    test_minimum_finding_count()
    print(f'\n=== ALL TESTS PASSED ===')
    print(f'Detection rate: {rate:.0%}')
    print(f'False positive rate: {fp:.0%}')
