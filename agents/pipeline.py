"""Main pipeline orchestrator — runs 12 agents (agents 3-7 in parallel, agents 9a+9b in parallel).
Called by server/proxy.js via subprocess.

Usage: python pipeline.py --db <path> --session-id <id> --agent <agent_id|all> ...
"""
import argparse
import asyncio
import json
import sqlite3
import sys
import os
import traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import domain_intelligence, adversarial_probe, schema_checks, dax_checks, execution_checks, dax_expression_checks, xmla_checks
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
    # Use 8192 so the proxy sends enough budget for reasoning + response without timeouts.
    # If a prompt is too complex (e.g. Remediation), the pipeline falls back to DeepSeek fast.
    effective_max_tokens = max_tokens
    if model_override and model_override in REASONING_MODELS:
        effective_max_tokens = max(max_tokens, 8192)

    # Build retry sequence: for reasoning models, retry the model itself (proxy does
    # escalating timeouts 60s/90s/120s per attempt), then fall back to DeepSeek.
    # Pipeline-level retries give the proxy multiple chances with its own retry loop.
    REASONING_RETRIES = 1  # Try reasoning model once, then fall back to DeepSeek fast
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
            # Reasoning models: proxy retries with escalating timeouts (240/360/480s)
            # so use a very generous pipeline-level timeout to let the proxy finish its retries
            req_timeout = 500 if is_reasoning else 190
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


def compress_findings_for_reasoning(findings, max_items=10):
    """Compress findings list for reasoning models to reduce prompt size.
    Reasoning models (GPT-5.4 Pro) share max_output_tokens between reasoning
    and message content. Smaller prompts = less reasoning overhead = more content tokens."""
    if not findings or len(findings) <= max_items:
        return findings
    # Sort by impact and take top N, keeping only essential fields
    sorted_f = sorted(findings, key=lambda f: f.get('impact_ms', 0), reverse=True)
    compressed = []
    for f in sorted_f[:max_items]:
        compressed.append({
            'issue': f.get('issue', '')[:120],
            'severity': f.get('severity', 'MEDIUM'),
            'impact_ms': f.get('impact_ms', 0),
            'agent_id': f.get('agent_id', ''),
            'fix': f.get('fix', '')[:80],
        })
    return compressed


def run_agent_with_llm(agent_id, prompt_key, template_vars, proxy_url, chromadb_path, session_id, model_override=None):
    """Run an LLM-backed agent: query ChromaDB, format prompt, call LLM, parse JSON.
    model_override: if set, routes this agent's LLM call to a specific model (e.g. gpt-5.4-pro).
    For reasoning models, compresses inputs to reduce prompt size and avoid
    the model spending all output tokens on reasoning with 0 content."""
    is_reasoning = model_override and model_override in REASONING_MODELS

    # Query ChromaDB for grounding — limit for reasoning models
    query = AGENT_CHROMA_QUERIES.get(agent_id, '')
    n_grounding = 2 if is_reasoning else 5  # Less grounding = shorter prompt
    grounding = query_chromadb(chromadb_path, 'microsoft_docs', query, n_results=n_grounding)
    if is_reasoning:
        # Truncate each grounding doc to 300 chars for reasoning models
        grounding = [g[:300] for g in grounding] if grounding else []
    template_vars['grounding_context'] = '\n'.join(grounding) if grounding else '(none)'

    # Past findings — skip for reasoning models to save tokens
    if is_reasoning:
        template_vars['past_findings'] = '(none)'
    else:
        past = query_chromadb(chromadb_path, 'past_findings', query, n_results=3)
        template_vars['past_findings'] = '\n'.join(past) if past else '(No past findings)'

    # For reasoning models, compress large JSON fields in template_vars
    if is_reasoning:
        for key in ('all_findings', 'ranked_findings'):
            if key in template_vars:
                try:
                    findings_data = json.loads(template_vars[key]) if isinstance(template_vars[key], str) else template_vars[key]
                    compressed = compress_findings_for_reasoning(findings_data, max_items=8)
                    template_vars[key] = json.dumps(compressed)
                    print(f'[pipeline] Compressed {key} from {len(findings_data)} to {len(compressed)} items for reasoning model', file=sys.stderr)
                except (json.JSONDecodeError, TypeError):
                    pass

    # Format prompt
    prompt_template = PROMPTS.get(prompt_key, '')
    try:
        system_prompt = prompt_template.format(**template_vars)
    except KeyError as e:
        system_prompt = prompt_template  # Use as-is if missing keys

    prompt_len = len(system_prompt)
    print(f'[pipeline] Prompt size for {agent_id}: {prompt_len} chars{" (compressed for reasoning)" if is_reasoning else ""}', file=sys.stderr)

    # Call LLM with per-agent model override
    user_msg = f'Analyze and respond with valid JSON only. Agent: {agent_id}'
    model_label = f' (model: {model_override})' if model_override else ''
    print(f'[pipeline] LLM call for {agent_id}{model_label}', file=sys.stderr)
    raw = call_llm(proxy_url, system_prompt, user_msg, max_tokens=2000, model_override=model_override)
    parsed = parse_llm_json(raw)

    return parsed.get('findings', []), parsed


def _run_schema_agent(ctx, domain, behavioral_evidence, proxy_url, chromadb_path, session_id, agent_models, db_path):
    """Run Schema agent (deterministic + LLM). Thread-safe — uses own DB connection."""
    print('[pipeline] Running Agent 3: Schema (parallel)', file=sys.stderr)
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
    write_findings_to_db(db_path, merged, agent_id_override='schema')
    return 'schema', {'findings': merged}, merged


def _run_dax_agent(ctx, domain, behavioral_evidence, proxy_url, chromadb_path, session_id, agent_models, db_path):
    """Run DAX agent (deterministic + LLM). Thread-safe."""
    print('[pipeline] Running Agent 4: DAX (parallel)', file=sys.stderr)
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
    write_findings_to_db(db_path, merged, agent_id_override='dax')
    return 'dax', {'findings': merged}, merged


def _run_dax_expression_agent(ctx, domain, behavioral_evidence, proxy_url,
                               chromadb_path, session_id, agent_models, db_path):
    """Run DAX Expression agent: deterministic + DeepSeek LLM analysis. Thread-safe."""
    print('[pipeline] Running Agent 5: DAX Expression (parallel, LLM enabled)', file=sys.stderr)
    from agents.dax_expression_checks import run_expression_checks_with_llm
    return run_expression_checks_with_llm(
        db_path, proxy_url, chromadb_path, session_id,
        domain, behavioral_evidence, agent_models,
        run_agent_with_llm_fn=run_agent_with_llm,
        merge_findings_fn=merge_findings,
        write_findings_fn=write_findings_to_db,
    )


def _run_xmla_agent(db_path):
    """Run XMLA agent (deterministic only). Thread-safe."""
    print('[pipeline] Running Agent XM: XMLA Deep Analysis (parallel)', file=sys.stderr)
    xmla_findings = xmla_checks.run_xmla_checks(db_path)
    write_findings_to_db(db_path, xmla_findings, agent_id_override='xmla')
    return 'xmla', {'findings': xmla_findings}, xmla_findings


def _run_execution_agent(ctx, domain, behavioral_evidence, proxy_url, chromadb_path, session_id, agent_models, db_path):
    """Run Execution agent (deterministic + LLM). Thread-safe."""
    print('[pipeline] Running Agent 5: Execution (parallel)', file=sys.stderr)
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
    write_findings_to_db(db_path, merged, agent_id_override='execution')
    return 'execution', {'findings': merged}, merged


def run_pipeline(db_path, session_id, agent_filter='all', domain_override='auto',
                 proxy_url='http://localhost:3001', chromadb_path='./chroma_db',
                 sample_mode=False, agent_models=None):
    """Run the full 11-agent pipeline. Agents 3-7 run in parallel via asyncio.gather().
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

    # ── Agents 3-7: Parallel execution via ThreadPoolExecutor ──────────────
    # Schema, DAX, DAX Expression, XMLA, and Execution are independent analysis
    # agents that all read from the same DB context + domain + behavioral_evidence.
    # Running them in parallel cuts ~50-60% off this segment's wall-clock time.
    parallel_agents = []
    if agent_filter == 'all':
        parallel_agents = ['schema', 'dax', 'dax_expression', 'xmla', 'execution']
    else:
        # Single-agent mode: run sequentially as before
        for a in ['schema', 'dax', 'dax_expression', 'xmla', 'execution']:
            if agent_filter == a:
                parallel_agents = [a]

    if parallel_agents:
        print(f'[pipeline] Running agents 3-7 in parallel: {parallel_agents}', file=sys.stderr)
        agent_tasks = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            if 'schema' in parallel_agents:
                agent_tasks['schema'] = executor.submit(
                    _run_schema_agent, ctx, domain, behavioral_evidence,
                    proxy_url, chromadb_path, session_id, agent_models, db_path)
            if 'dax' in parallel_agents:
                agent_tasks['dax'] = executor.submit(
                    _run_dax_agent, ctx, domain, behavioral_evidence,
                    proxy_url, chromadb_path, session_id, agent_models, db_path)
            if 'dax_expression' in parallel_agents:
                agent_tasks['dax_expression'] = executor.submit(
                    _run_dax_expression_agent,
                    ctx, domain, behavioral_evidence,
                    proxy_url, chromadb_path, session_id,
                    agent_models, db_path)
            if 'xmla' in parallel_agents:
                agent_tasks['xmla'] = executor.submit(
                    _run_xmla_agent, db_path)
            if 'execution' in parallel_agents:
                agent_tasks['execution'] = executor.submit(
                    _run_execution_agent, ctx, domain, behavioral_evidence,
                    proxy_url, chromadb_path, session_id, agent_models, db_path)

        # Collect results from all parallel agents
        for agent_id, future in agent_tasks.items():
            try:
                name, result_data, findings = future.result(timeout=180)
                all_findings.extend(findings)
                results[name] = result_data
                print(f'[pipeline] {name}: {len(findings)} findings (parallel complete)', file=sys.stderr)
            except Exception as e:
                print(f'[pipeline] {agent_id} failed in parallel: {e}', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                results[agent_id] = {'findings': [], 'error': str(e)}

        print(f'[pipeline] Agents 3-7 parallel block complete: {len(all_findings)} total findings so far', file=sys.stderr)

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

    # Agents 9a+9b: Finding Validator + Report Validator (run in parallel)
    # Split from single Validation agent to avoid GPT-5.4 Pro timeouts.
    # Smaller prompts = faster responses, and they're independent tasks.
    if agent_filter in ('all', 'validation', 'finding_validator', 'report_validator'):
        print('[pipeline] Running Agents 9a+9b: Finding Validator + Report Validator (parallel)', file=sys.stderr)
        mc_result = results.get('monte_carlo', {})
        synthesis_result = results.get('synthesis', {})
        remediation_result = results.get('remediation', {})

        if proxy_url and (mc_result or synthesis_result):
            # Build shared validation context
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

            # Run both validators in parallel via ThreadPoolExecutor
            def _run_finding_validator():
                tv = {
                    'fixes_applied': json.dumps(mc_result.get('active_fixes', [])),
                    'baseline_results': baseline_results,
                    'postfix_results': postfix_results,
                    'resolution_status': resolution_status,
                }
                # Use the validation model setting (user picks one model for both)
                model = agent_models.get('finding_validator') or agent_models.get('validation')
                return run_agent_with_llm(
                    'finding_validator', 'finding_validator', tv,
                    proxy_url, chromadb_path, session_id,
                    model_override=model,
                )

            def _run_report_validator():
                tv = {
                    'delta_analysis': delta_analysis,
                    'resolution_status': resolution_status,
                    'baseline_results': baseline_results,
                    'postfix_results': postfix_results,
                }
                model = agent_models.get('report_validator') or agent_models.get('validation')
                return run_agent_with_llm(
                    'report_validator', 'report_validator', tv,
                    proxy_url, chromadb_path, session_id,
                    model_override=model,
                )

            with ThreadPoolExecutor(max_workers=2) as val_executor:
                fv_future = val_executor.submit(_run_finding_validator)
                rv_future = val_executor.submit(_run_report_validator)

            # Collect results
            try:
                fv_findings, fv_data = fv_future.result(timeout=300)
                print(f'[pipeline] finding_validator: {len(fv_findings)} findings (parallel complete)', file=sys.stderr)
                all_findings.extend(fv_findings)
                write_findings_to_db(db_path, fv_findings, agent_id_override='finding_validator')
                results['finding_validator'] = fv_data
            except Exception as e:
                print(f'[pipeline] finding_validator failed: {e}', file=sys.stderr)
                results['finding_validator'] = {'findings': [], 'error': str(e)}

            try:
                rv_findings, rv_data = rv_future.result(timeout=300)
                print(f'[pipeline] report_validator: {len(rv_findings)} findings (parallel complete)', file=sys.stderr)
                all_findings.extend(rv_findings)
                write_findings_to_db(db_path, rv_findings, agent_id_override='report_validator')
                results['report_validator'] = rv_data
            except Exception as e:
                print(f'[pipeline] report_validator failed: {e}', file=sys.stderr)
                results['report_validator'] = {'findings': [], 'error': str(e)}

            # Merge into combined validation result for backward compatibility
            fv_out = results.get('finding_validator', {})
            rv_out = results.get('report_validator', {})
            results['validation'] = {
                'summary': rv_out.get('summary', ''),
                'confidence_score': rv_out.get('confidence_score', 0),
                'effective_fixes': fv_out.get('effective_fixes', []),
                'ineffective_fixes': fv_out.get('ineffective_fixes', []),
                'gaps': rv_out.get('gaps', []),
                'contradictions': fv_out.get('contradictions', []),
                'recommendations': rv_out.get('recommendations', []),
            }
        else:
            # Fallback validation without LLM
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

    # Embed all findings in ChromaDB (with timeout to prevent deadlocks)
    try:
        import signal
        def _timeout_handler(signum, frame):
            raise TimeoutError('ChromaDB embed timed out')
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(15)  # 15 second timeout
        embed_findings(chromadb_path, all_findings, session_id)
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    except Exception as e:
        print(f'[pipeline] ChromaDB embed skipped (timeout/error): {e}', file=sys.stderr)

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
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
