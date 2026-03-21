"""Main pipeline orchestrator — runs all 9 agents in order.
Called by server/proxy.js via subprocess.

Usage: python pipeline.py --db <path> --session-id <id> --agent <agent_id|all> ...
"""
import argparse
import json
import sqlite3
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import domain_intelligence, adversarial_probe, schema_checks, dax_checks, execution_checks
from agents.prompts import PROMPTS, AGENT_CHROMA_QUERIES

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def query_chromadb(chromadb_path, collection_name, query_text, n_results=5):
    """Query ChromaDB for grounding context."""
    if not CHROMA_AVAILABLE:
        return []
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        collection = client.get_collection(collection_name)
        results = collection.query(query_texts=[query_text], n_results=n_results)
        return results.get('documents', [[]])[0]
    except Exception:
        return []


# Reasoning models need higher token limits because they consume tokens for internal reasoning
REASONING_MODELS = {'gpt-5.4-pro', 'o1', 'o3-pro', 'o1-pro'}
DEFAULT_FALLBACK_MODEL = 'DeepSeek-V3.2-Speciale'


def call_llm(proxy_url, system_prompt, user_msg, max_tokens=1200, model_override=None):
    """Call LLM via Express proxy with optional per-agent model override.
    For reasoning models (gpt-5.4-pro), uses higher token limits and retries with fallback."""
    if not REQUESTS_AVAILABLE:
        return None

    # Reasoning models: max_output_tokens is shared between reasoning AND message content.
    # With too-low a value the model spends all tokens on reasoning and returns 0 content.
    # Use 16384 so the proxy sends a large enough budget for both reasoning + response.
    effective_max_tokens = max_tokens
    if model_override and model_override in REASONING_MODELS:
        effective_max_tokens = max(max_tokens, 16384)

    # Build retry sequence: for reasoning models, retry the model itself (proxy does
    # escalating timeouts 60s/90s/120s per attempt), then fall back to DeepSeek.
    # Pipeline-level retries give the proxy multiple chances with its own retry loop.
    REASONING_RETRIES = 3  # Number of times to try the reasoning model before fallback
    models_to_try = []
    if model_override and model_override in REASONING_MODELS:
        models_to_try = [model_override] * REASONING_RETRIES + [DEFAULT_FALLBACK_MODEL]
    elif model_override:
        models_to_try = [model_override]
    else:
        models_to_try = [None]

    for attempt, model in enumerate(models_to_try):
        is_reasoning = model and model in REASONING_MODELS
        try:
            tokens = effective_max_tokens if is_reasoning else max_tokens
            payload = {'system': system_prompt, 'userMsg': user_msg, 'maxTokens': tokens}
            if model:
                payload['modelOverride'] = model
            label = f' (model: {model}, attempt {attempt+1}/{len(models_to_try)})' if model else ''
            print(f'[pipeline] LLM call{label}', file=sys.stderr)
            # Reasoning models: proxy retries with escalating timeouts (90/120/180s)
            # so use a generous pipeline-level timeout to let the proxy finish its retries
            req_timeout = 200 if is_reasoning else 190
            resp = requests.post(
                f'{proxy_url}/api/agent',
                json=payload,
                timeout=req_timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get('content', '')
                if content and len(content) > 10:
                    return content
                elif attempt < len(models_to_try) - 1:
                    next_model = models_to_try[attempt+1]
                    if next_model == model:
                        print(f'[pipeline] Empty response from {model}, retrying ({attempt+2}/{len(models_to_try)})...', file=sys.stderr)
                    else:
                        print(f'[pipeline] Empty response from {model}, falling back to {next_model}', file=sys.stderr)
                    continue
                return content  # Return even if empty on last attempt
            else:
                print(f'LLM error: {resp.status_code} {resp.text}', file=sys.stderr)
                if attempt < len(models_to_try) - 1:
                    next_model = models_to_try[attempt+1]
                    if next_model == model:
                        print(f'[pipeline] Retrying {model} ({attempt+2}/{len(models_to_try)})...', file=sys.stderr)
                    else:
                        print(f'[pipeline] Falling back to {next_model}', file=sys.stderr)
                    continue
                return None
        except Exception as e:
            print(f'LLM call failed: {e}', file=sys.stderr)
            if attempt < len(models_to_try) - 1:
                next_model = models_to_try[attempt+1]
                if next_model == model:
                    print(f'[pipeline] Retrying {model} ({attempt+2}/{len(models_to_try)})...', file=sys.stderr)
                else:
                    print(f'[pipeline] Falling back to {next_model}', file=sys.stderr)
                continue
            return None
    return None


def parse_llm_json(content):
    """Parse JSON from LLM response, stripping markdown code blocks."""
    if not content:
        return {}
    # Strip ```json ... ``` wrapper
    content = content.strip()
    if content.startswith('```json'):
        content = content[7:]
    elif content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object in the content
        start = content.find('{')
        end = content.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def merge_findings(deterministic, llm_findings):
    """Merge findings — deterministic take precedence."""
    det_issues = {f['issue'][:50] for f in deterministic}
    merged = list(deterministic)
    for f in llm_findings:
        if f.get('issue', '')[:50] not in det_issues:
            merged.append(f)
    return merged


def embed_findings(chromadb_path, findings, session_id):
    """Embed findings into ChromaDB past_findings collection."""
    if not CHROMA_AVAILABLE or not findings:
        return
    try:
        client = chromadb.PersistentClient(path=chromadb_path)
        collection = client.get_or_create_collection('past_findings')
        for i, f in enumerate(findings):
            doc = json.dumps(f)
            collection.add(
                documents=[doc],
                ids=[f'{session_id}_{f.get("agent_id", "unknown")}_{i}'],
                metadatas=[{'session_id': session_id, 'agent_id': f.get('agent_id', 'unknown')}],
            )
    except Exception as e:
        print(f'ChromaDB embed error: {e}', file=sys.stderr)


def write_findings_to_db(db_path, findings, model_id='sample', agent_id_override=None):
    """Write findings to SQLite findings table."""
    db = sqlite3.connect(db_path)
    for f in findings:
        db.execute('''
            INSERT INTO findings (model_id, agent_id, severity, issue, evidence, impact_ms, fix, run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            model_id,
            agent_id_override or f.get('agent_id', 'unknown'),
            f.get('severity', 'MEDIUM'),
            f.get('issue', ''),
            f.get('evidence', ''),
            f.get('impact_ms', 0),
            f.get('fix', ''),
        ))
    db.commit()
    db.close()


def load_db_context(db_path):
    """Load all context from SQLite for LLM prompts."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]
    measures = [dict(r) for r in db.execute('SELECT * FROM measures').fetchall()]
    columns = [dict(r) for r in db.execute('SELECT * FROM columns').fetchall()]
    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
    config_row = db.execute('SELECT * FROM agent_config LIMIT 1').fetchone()
    config = dict(config_row) if config_row else {}
    cu_rows = [dict(r) for r in db.execute('SELECT * FROM cu_metrics').fetchall()]
    model_row = db.execute('SELECT * FROM models LIMIT 1').fetchone()
    model = dict(model_row) if model_row else {}

    db.close()

    return {
        'tables': tables,
        'measures': measures,
        'columns': columns,
        'traces': traces,
        'config': config,
        'cu_metrics': cu_rows[0] if cu_rows else {},
        'model': model,
        'table_names': [t['name'] for t in tables],
        'measure_names': [m['name'] for m in measures],
        'column_names': [c['name'] for c in columns],
    }


def run_agent_with_llm(agent_id, prompt_key, template_vars, proxy_url, chromadb_path, session_id, model_override=None):
    """Run an LLM-backed agent: query ChromaDB, format prompt, call LLM, parse JSON.
    model_override: if set, routes this agent's LLM call to a specific model (e.g. gpt-5.4-pro)."""
    # Query ChromaDB for grounding
    query = AGENT_CHROMA_QUERIES.get(agent_id, '')
    grounding = query_chromadb(chromadb_path, 'microsoft_docs', query, n_results=5)
    template_vars['grounding_context'] = '\n'.join(grounding) if grounding else '(No grounding context available)'

    # Past findings
    past = query_chromadb(chromadb_path, 'past_findings', query, n_results=3)
    template_vars['past_findings'] = '\n'.join(past) if past else '(No past findings)'

    # Format prompt
    prompt_template = PROMPTS.get(prompt_key, '')
    try:
        system_prompt = prompt_template.format(**template_vars)
    except KeyError as e:
        system_prompt = prompt_template  # Use as-is if missing keys

    # Call LLM with per-agent model override
    user_msg = f'Analyze and respond with valid JSON only. Agent: {agent_id}'
    model_label = f' (model: {model_override})' if model_override else ''
    print(f'[pipeline] LLM call for {agent_id}{model_label}', file=sys.stderr)
    raw = call_llm(proxy_url, system_prompt, user_msg, max_tokens=2000, model_override=model_override)
    parsed = parse_llm_json(raw)

    return parsed.get('findings', []), parsed


def run_pipeline(db_path, session_id, agent_filter='all', domain_override='auto',
                 proxy_url='http://localhost:3001', chromadb_path='./chroma_db',
                 sample_mode=False, agent_models=None):
    """Run the full 9-agent pipeline.
    agent_models: dict mapping agent_id -> model_id for per-agent model routing.
    Example: {'domain_intelligence': 'gpt-5.4-pro', 'schema': 'DeepSeek-V3.2-Speciale'}
    """
    all_findings = []
    results = {}
    ctx = load_db_context(db_path)
    agent_models = agent_models or {}

    # Agent 1: Domain Intelligence
    if agent_filter in ('all', 'domain_intelligence'):
        print('[pipeline] Running Agent 1: Domain Intelligence', file=sys.stderr)
        di_result = domain_intelligence.run(db_path)
        all_findings.extend(di_result.get('findings', []))
        results['domain_intelligence'] = di_result

        # LLM enhancement for hypotheses
        if proxy_url:
            template_vars = {
                'table_names': ', '.join(ctx['table_names']),
                'measure_names': ', '.join(ctx['measure_names']),
                'column_names': ', '.join(ctx['column_names'][:30]),
                'instruction_excerpt': str(ctx['config'].get('instruction_text', ''))[:500],
                'domain': di_result['domain'],
                'config_issues': '; '.join(di_result.get('config_issues', [])),
            }
            llm_findings, llm_data = run_agent_with_llm(
                'domain_intelligence', 'domain_intelligence', template_vars,
                proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('domain_intelligence'),
            )
            # Update probe questions with LLM-generated ones if available
            if llm_data.get('probe_questions'):
                di_result['probe_questions'] = (
                    di_result['probe_questions'] + llm_data['probe_questions'][:30]
                )
            results['domain_intelligence'] = di_result

    domain = results.get('domain_intelligence', {}).get('domain', domain_override)
    if domain == 'auto':
        domain = 'OPERATIONAL'

    # Agent 2: Adversarial Probe
    if agent_filter in ('all', 'adversarial_probe'):
        print('[pipeline] Running Agent 2: Adversarial Probe', file=sys.stderr)
        probe_questions = results.get('domain_intelligence', {}).get('probe_questions', [])
        ap_result = adversarial_probe.run(db_path, probe_questions)
        all_findings.extend(ap_result.get('findings', []))
        results['adversarial_probe'] = ap_result

    behavioral_summary = results.get('adversarial_probe', {}).get('behavioral_summary', '')
    behavioral_evidence = json.dumps(results.get('adversarial_probe', {}).get('behavioral_profile', {}))

    # Agent 3: Schema (deterministic + LLM)
    if agent_filter in ('all', 'schema'):
        print('[pipeline] Running Agent 3: Schema', file=sys.stderr)
        det_findings = schema_checks.run_checks(db_path)

        llm_findings = []
        if proxy_url:
            template_vars = {
                'domain': domain,
                'table_names': ', '.join(ctx['table_names']),
                'measure_names': ', '.join(ctx['measure_names']),
                'agent_config': json.dumps(ctx['config']),
                'deterministic_findings': json.dumps(det_findings),
                'behavioral_evidence': behavioral_evidence,
            }
            llm_findings, _ = run_agent_with_llm(
                'schema', 'schema', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('schema'),
            )

        merged = merge_findings(det_findings, llm_findings)
        all_findings.extend(merged)
        write_findings_to_db(db_path, merged, agent_id_override='schema')
        results['schema'] = {'findings': merged}

    # Agent 4: DAX (deterministic + LLM)
    if agent_filter in ('all', 'dax'):
        print('[pipeline] Running Agent 4: DAX', file=sys.stderr)
        det_findings = dax_checks.run_checks(db_path)

        llm_findings = []
        if proxy_url:
            traces_summary = json.dumps([{
                'question': t.get('question', '')[:80],
                'total_ms': t.get('total_ms', 0),
                'retries': t.get('retries', 0),
                'dax_generated': str(t.get('dax_generated', ''))[:200],
            } for t in ctx['traces'][:10]])

            template_vars = {
                'domain': domain,
                'table_names': ', '.join(ctx['table_names']),
                'measure_names': ', '.join(ctx['measure_names']),
                'traces_summary': traces_summary,
                'deterministic_findings': json.dumps(det_findings),
                'behavioral_evidence': behavioral_evidence,
            }
            llm_findings, _ = run_agent_with_llm(
                'dax', 'dax', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('dax'),
            )

        merged = merge_findings(det_findings, llm_findings)
        all_findings.extend(merged)
        write_findings_to_db(db_path, merged, agent_id_override='dax')
        results['dax'] = {'findings': merged}

    # Agent 5: Execution (deterministic + LLM)
    if agent_filter in ('all', 'execution'):
        print('[pipeline] Running Agent 5: Execution', file=sys.stderr)
        det_findings = execution_checks.run_checks(db_path)

        llm_findings = []
        if proxy_url:
            traces_summary = json.dumps([{
                'question': t.get('question', '')[:80],
                'total_ms': t.get('total_ms', 0),
                'bd_exec': t.get('bd_exec', 0),
                'bd_nldax': t.get('bd_nldax', 0),
                'bd_schema': t.get('bd_schema', 0),
            } for t in ctx['traces'][:10]])

            template_vars = {
                'domain': domain,
                'traces_summary': traces_summary,
                'cu_metrics': json.dumps(ctx['cu_metrics']),
                'deterministic_findings': json.dumps(det_findings),
                'behavioral_evidence': behavioral_evidence,
            }
            llm_findings, _ = run_agent_with_llm(
                'execution', 'execution', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('execution'),
            )

        merged = merge_findings(det_findings, llm_findings)
        all_findings.extend(merged)
        write_findings_to_db(db_path, merged, agent_id_override='execution')
        results['execution'] = {'findings': merged}

    # Agent 6: Synthesis
    if agent_filter in ('all', 'synthesis'):
        print('[pipeline] Running Agent 6: Synthesis', file=sys.stderr)
        if proxy_url:
            template_vars = {
                'domain': domain,
                'all_findings': json.dumps(all_findings),
                'behavioral_summary': behavioral_summary,
            }
            llm_findings, synthesis_data = run_agent_with_llm(
                'synthesis', 'synthesis', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('synthesis'),
            )
            results['synthesis'] = synthesis_data
            all_findings.extend(llm_findings)
        else:
            # Fallback synthesis without LLM
            sorted_findings = sorted(all_findings, key=lambda f: f.get('impact_ms', 0), reverse=True)
            results['synthesis'] = {
                'exec_summary': f'Analysis found {len(all_findings)} issues across schema, DAX, and execution.',
                'demo_readiness': 'NOT READY' if any(f['severity'] == 'CRITICAL' for f in all_findings) else 'CONDITIONAL',
                'root_cause_ranking': [
                    {'rank': i + 1, 'issue': f['issue'], 'ms_contribution': f.get('impact_ms', 0)}
                    for i, f in enumerate(sorted_findings[:10])
                ],
            }

    # Agent 7: Monte Carlo
    if agent_filter in ('all', 'monte_carlo'):
        print('[pipeline] Running Agent 7: Monte Carlo', file=sys.stderr)
        try:
            from synthetic.monte_carlo_engine import run_monte_carlo
            mc_result = run_monte_carlo(db_path, all_findings, behavioral_evidence)
            results['monte_carlo'] = mc_result
        except Exception as e:
            print(f'Monte Carlo error: {e}', file=sys.stderr)
            results['monte_carlo'] = {'error': str(e)}

    # Agent 8: Remediation
    if agent_filter in ('all', 'remediation'):
        print('[pipeline] Running Agent 8: Remediation', file=sys.stderr)
        if proxy_url:
            ranked = sorted(all_findings, key=lambda f: f.get('impact_ms', 0), reverse=True)
            template_vars = {
                'domain': domain,
                'ranked_findings': json.dumps(ranked[:15]),
                'instruction_text': str(ctx['config'].get('instruction_text', ''))[:1000],
                'instr_chars': ctx['config'].get('instr_chars', 0),
                'table_names': ', '.join(ctx['table_names']),
                'measure_names': ', '.join(ctx['measure_names']),
                'behavioral_summary': behavioral_summary,
            }
            llm_findings, remediation_data = run_agent_with_llm(
                'remediation', 'remediation', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('remediation'),
            )
            results['remediation'] = remediation_data
        else:
            results['remediation'] = {'artifacts': {}}

    # Agent 9: Validation (Phi-4 Reasoning)
    if agent_filter in ('all', 'validation'):
        print('[pipeline] Running Agent 9: Validation', file=sys.stderr)
        # Validation runs as a post-pipeline assessment of fix effectiveness
        # It uses the Monte Carlo results + synthesis to produce a final verdict
        mc_result = results.get('monte_carlo', {})
        synthesis_result = results.get('synthesis', {})
        remediation_result = results.get('remediation', {})

        if proxy_url and (mc_result or synthesis_result):
            # Build validation context from pipeline results
            baseline_results = json.dumps({
                'avg_ms': mc_result.get('baseline', {}).get('avg_ms', 0),
                'p95_ms': mc_result.get('baseline', {}).get('p95_ms', 0),
                'finding_count': len(all_findings),
            })
            postfix_results = json.dumps({
                'projected_p50': mc_result.get('projected', {}).get('p50', 0),
                'projected_p90': mc_result.get('projected', {}).get('p90', 0),
                'per_fix': mc_result.get('per_fix', {}),
            })
            delta_analysis = json.dumps({
                'reduction_pct': round(
                    (mc_result.get('baseline', {}).get('avg_ms', 1) - mc_result.get('projected', {}).get('p50', 0))
                    / max(mc_result.get('baseline', {}).get('avg_ms', 1), 1) * 100, 1
                ) if mc_result.get('baseline') else 0,
                'demo_readiness': synthesis_result.get('demo_readiness', 'UNKNOWN'),
            })
            resolution_status = json.dumps({
                'critical_count': len([f for f in all_findings if f.get('severity') == 'CRITICAL']),
                'high_count': len([f for f in all_findings if f.get('severity') == 'HIGH']),
                'has_artifacts': bool(remediation_result.get('artifacts')),
            })

            template_vars = {
                'fixes_applied': json.dumps(mc_result.get('active_fixes', [])),
                'baseline_results': baseline_results,
                'postfix_results': postfix_results,
                'delta_analysis': delta_analysis,
                'resolution_status': resolution_status,
            }
            llm_findings, validation_data = run_agent_with_llm(
                'validation', 'validation', template_vars, proxy_url, chromadb_path, session_id,
                model_override=agent_models.get('validation'),
            )
            results['validation'] = validation_data
            all_findings.extend(llm_findings)
        else:
            # Fallback validation without LLM — produce deterministic summary
            mc_baseline = mc_result.get('baseline', {}).get('avg_ms', 0)
            mc_projected = mc_result.get('projected', {}).get('p50', 0)
            reduction = round((mc_baseline - mc_projected) / max(mc_baseline, 1) * 100, 1) if mc_baseline else 0

            results['validation'] = {
                'summary': f'Pipeline identified {len(all_findings)} findings. '
                           f'Monte Carlo projects {reduction}% latency reduction (P50: {mc_projected}ms). '
                           f'{len([f for f in all_findings if f.get("severity") == "CRITICAL"])} critical issues.',
                'effective_fixes': [k for k, v in mc_result.get('per_fix', {}).items()
                                    if v.get('reduction_ms', 0) > 500],
                'ineffective_fixes': [k for k, v in mc_result.get('per_fix', {}).items()
                                      if v.get('reduction_ms', 0) < 100],
            }

    # Embed all findings in ChromaDB
    embed_findings(chromadb_path, all_findings, session_id)

    # Final output
    output = {
        'domain': domain,
        'findings': all_findings,
        'synthesis': results.get('synthesis', {}),
        'remediation': results.get('remediation', {}),
        'monte_carlo': results.get('monte_carlo', {}),
        'validation': results.get('validation', {}),
        'agent_results': {k: {'finding_count': len(v.get('findings', []))} for k, v in results.items()},
    }

    return output


def main():
    parser = argparse.ArgumentParser(description='Fabric Data Agent Analysis Pipeline')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--session-id', default='default', help='Session ID')
    parser.add_argument('--agent', default='all', help='Agent to run (or "all")')
    parser.add_argument('--domain', default='auto', help='Domain override')
    parser.add_argument('--llm-endpoint', default='', help='LLM endpoint')
    parser.add_argument('--llm-key', default='', help='LLM API key')
    parser.add_argument('--llm-model', default='', help='LLM model')
    parser.add_argument('--chromadb-path', default='./chroma_db', help='ChromaDB path')
    parser.add_argument('--proxy-url', default='http://localhost:3001', help='Express proxy URL')
    parser.add_argument('--sample-mode', action='store_true', help='Sample mode flag')
    parser.add_argument('--agent-models', default='{}', help='JSON map of agent_id -> model_id for per-agent model routing')

    args = parser.parse_args()

    # Parse agent models JSON
    try:
        agent_models = json.loads(args.agent_models)
    except json.JSONDecodeError:
        agent_models = {}
        print(f'[pipeline] Warning: invalid --agent-models JSON, using defaults', file=sys.stderr)

    result = run_pipeline(
        db_path=args.db,
        session_id=args.session_id,
        agent_filter=args.agent,
        domain_override=args.domain,
        proxy_url=args.proxy_url,
        chromadb_path=args.chromadb_path,
        sample_mode=args.sample_mode,
        agent_models=agent_models,
    )

    print(json.dumps(result))


if __name__ == '__main__':
    main()
