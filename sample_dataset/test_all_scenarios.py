"""Run all 20 test scenarios through the deterministic checks and generate a report.

Tests each scenario database against all 29 deterministic rules (11 schema + 9 DAX + 9 execution)
and produces a comprehensive test report showing detection coverage.
"""
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.schema_checks import run_checks as schema_checks
from agents.dax_checks import run_checks as dax_checks
from agents.execution_checks import run_checks as execution_checks

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios')
META_PATH = os.path.join(SCENARIOS_DIR, 'scenarios_meta.json')


def run_scenario(scenario_id):
    """Run all deterministic checks on a scenario database."""
    db_path = os.path.join(SCENARIOS_DIR, f'scenario_{scenario_id:02d}.db')
    if not os.path.exists(db_path):
        return None

    schema_findings = schema_checks(db_path)
    dax_findings = dax_checks(db_path)
    exec_findings = execution_checks(db_path)

    return {
        'schema': schema_findings,
        'dax': dax_findings,
        'execution': exec_findings,
        'total': len(schema_findings) + len(dax_findings) + len(exec_findings),
        'critical': sum(1 for f in schema_findings + dax_findings + exec_findings if f['severity'] == 'CRITICAL'),
        'high': sum(1 for f in schema_findings + dax_findings + exec_findings if f['severity'] == 'HIGH'),
        'medium': sum(1 for f in schema_findings + dax_findings + exec_findings if f['severity'] == 'MEDIUM'),
    }


def run_all():
    """Run all 20 scenarios and generate report."""
    with open(META_PATH) as f:
        meta = json.load(f)

    print('=' * 100)
    print('FABRIC DATA AGENT LATENCY ANALYZER — 20-SCENARIO TEST REPORT')
    print('=' * 100)
    print()

    all_results = []
    total_findings = 0
    total_critical = 0
    total_high = 0
    total_medium = 0

    # Track which rules are triggered across all scenarios
    rule_coverage = {
        'schema_1_instruction_exceeded': False,
        'schema_2_instruction_near': False,
        'schema_3_extreme_scope': False,
        'schema_4_high_scope': False,
        'schema_5_zero_va': False,
        'schema_6_low_va': False,
        'schema_7_exact_dup_measure': False,
        'schema_8_fuzzy_dup_measure': False,
        'schema_9_missing_descriptions': False,
        'schema_10_hidden_columns': False,
        'schema_11_table_mismatch': False,
        'dax_1_high_retry': False,
        'dax_2_single_retry': False,
        'dax_3_topn_absent': False,
        'dax_4_wrong_table': False,
        'dax_5_physician_visible': False,
        'dax_6_measure_not_found': False,
        'dax_7_empty_results': False,
        'dax_8_ambiguous_time': False,
        'dax_9_nl2dax_contamination': False,
        'exec_1_outlier': False,
        'exec_2_slow': False,
        'exec_3_execution_dominant': False,
        'exec_4_dax_dominant': False,
        'exec_5_retry_dominant': False,
        'exec_6_schema_dominant': False,
        'exec_7_cu_throttling': False,
        'exec_8_vorder': False,
        'exec_9_framing_risk': False,
    }

    for scenario in meta:
        sid = scenario['id']
        result = run_scenario(sid)
        if not result:
            print(f'  SKIP: Scenario {sid} — database not found')
            continue

        all_results.append((scenario, result))
        total_findings += result['total']
        total_critical += result['critical']
        total_high += result['high']
        total_medium += result['medium']

        # Print scenario summary
        print(f'Scenario {sid:2d}: {scenario["name"]}')
        print(f'  Domain: {scenario["domain"]}')
        print(f'  Findings: {result["total"]} (CRITICAL: {result["critical"]}, HIGH: {result["high"]}, MEDIUM: {result["medium"]})')
        print(f'  Schema: {len(result["schema"])} | DAX: {len(result["dax"])} | Execution: {len(result["execution"])}')

        # Track rule coverage
        for f in result['schema']:
            issue = f['issue'].lower()
            if 'instruction character limit exceeded' in issue or 'instruction char limit' in issue:
                rule_coverage['schema_1_instruction_exceeded'] = True
            elif 'instructions near' in issue:
                rule_coverage['schema_2_instruction_near'] = True
            elif 'extreme schema scope' in issue:
                rule_coverage['schema_3_extreme_scope'] = True
            elif 'high schema scope' in issue:
                rule_coverage['schema_4_high_scope'] = True
            elif 'zero verified' in issue:
                rule_coverage['schema_5_zero_va'] = True
            elif 'low verified' in issue:
                rule_coverage['schema_6_low_va'] = True
            elif 'exact duplicate' in issue:
                rule_coverage['schema_7_exact_dup_measure'] = True
            elif 'fuzzy duplicate' in issue:
                rule_coverage['schema_8_fuzzy_dup_measure'] = True
            elif 'missing table desc' in issue:
                rule_coverage['schema_9_missing_descriptions'] = True
            elif 'hidden col' in issue:
                rule_coverage['schema_10_hidden_columns'] = True
            elif 'mismatch' in issue:
                rule_coverage['schema_11_table_mismatch'] = True

        for f in result['dax']:
            issue = f['issue'].lower()
            if 'high retry' in issue:
                rule_coverage['dax_1_high_retry'] = True
            elif 'single retry' in issue:
                rule_coverage['dax_2_single_retry'] = True
            elif 'topn absent' in issue:
                rule_coverage['dax_3_topn_absent'] = True
            elif 'wrong table' in issue:
                rule_coverage['dax_4_wrong_table'] = True
            elif 'physician' in issue:
                rule_coverage['dax_5_physician_visible'] = True
            elif 'unknown measure' in issue or 'not found' in issue.lower():
                rule_coverage['dax_6_measure_not_found'] = True
            elif 'empty results' in issue:
                rule_coverage['dax_7_empty_results'] = True
            elif 'ambiguous time' in issue:
                rule_coverage['dax_8_ambiguous_time'] = True
            elif 'contamination' in issue:
                rule_coverage['dax_9_nl2dax_contamination'] = True

        for f in result['execution']:
            issue = f['issue'].lower()
            if 'outlier' in issue:
                rule_coverage['exec_1_outlier'] = True
            elif 'slow trace' in issue:
                rule_coverage['exec_2_slow'] = True
            elif 'execution phase dominant' in issue:
                rule_coverage['exec_3_execution_dominant'] = True
            elif 'dax generation' in issue and 'dominant' in issue:
                rule_coverage['exec_4_dax_dominant'] = True
            elif 'retry-dominant' in issue:
                rule_coverage['exec_5_retry_dominant'] = True
            elif 'schema lookup dominant' in issue:
                rule_coverage['exec_6_schema_dominant'] = True
            elif 'cu throttling' in issue:
                rule_coverage['exec_7_cu_throttling'] = True
            elif 'v-order' in issue:
                rule_coverage['exec_8_vorder'] = True
            elif 'framing risk' in issue:
                rule_coverage['exec_9_framing_risk'] = True

        # Print detailed findings
        for f in result['schema'] + result['dax'] + result['execution']:
            severity_marker = {'CRITICAL': '!!!', 'HIGH': '!! ', 'MEDIUM': '!  '}.get(f['severity'], '   ')
            print(f'    [{severity_marker}] {f["severity"]:8s} | {f["issue"][:80]}')
        print()

    # Summary
    print('=' * 100)
    print('SUMMARY')
    print('=' * 100)
    print(f'Total scenarios tested: {len(all_results)}')
    print(f'Total findings:        {total_findings}')
    print(f'  CRITICAL:            {total_critical}')
    print(f'  HIGH:                {total_high}')
    print(f'  MEDIUM:              {total_medium}')
    print()

    # Rule coverage
    covered = sum(1 for v in rule_coverage.values() if v)
    total_rules = len(rule_coverage)
    print(f'Rule Coverage: {covered}/{total_rules} ({covered / total_rules * 100:.0f}%)')
    print()
    print('Rule Coverage Detail:')
    for rule, triggered in sorted(rule_coverage.items()):
        status = 'COVERED' if triggered else 'MISSED'
        marker = '  ' if triggered else '>>'
        print(f'  {marker} {rule:40s} {status}')

    print()

    # Domain coverage
    domains_seen = set()
    for scenario, _ in all_results:
        domains_seen.add(scenario['domain'])
    print(f'Domain Coverage: {len(domains_seen)}/8')
    for d in sorted(domains_seen):
        count = sum(1 for s, _ in all_results if s['domain'] == d)
        print(f'  {d}: {count} scenarios')

    print()

    # Scenario ranking by findings
    print('Scenario Ranking (by total findings):')
    ranked = sorted(all_results, key=lambda x: x[1]['total'], reverse=True)
    for scenario, result in ranked:
        bar = '#' * min(result['total'], 50)
        print(f'  S{scenario["id"]:02d} ({result["total"]:3d}) {bar} {scenario["name"]}')

    # Return results for programmatic use
    return {
        'total_scenarios': len(all_results),
        'total_findings': total_findings,
        'rule_coverage': covered,
        'total_rules': total_rules,
        'coverage_pct': covered / total_rules * 100,
        'domains_covered': len(domains_seen),
    }


if __name__ == '__main__':
    results = run_all()
    print()
    print(f'Test {"PASSED" if results["coverage_pct"] >= 90 else "NEEDS REVIEW"}: '
          f'{results["rule_coverage"]}/{results["total_rules"]} rules covered '
          f'({results["coverage_pct"]:.0f}%)')
