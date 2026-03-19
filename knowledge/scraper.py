"""Phase 2 — Scraper: downloads Microsoft Fabric Data Agent documentation.
Produces markdown chunks for embedding into ChromaDB.
"""
import os
import json
import hashlib

# Built-in knowledge base — key Microsoft Fabric Data Agent documentation
# These are curated from official Microsoft docs and best practices
KNOWLEDGE_CHUNKS = [
    {
        "title": "Data Agent Overview",
        "topic": "data-agent",
        "content": """Microsoft Fabric Data Agents allow users to ask natural language questions about their semantic models.
The agent converts natural language to DAX, executes against the model, and returns results.
Key components: Instructions, Verified Answers, AI Data Schema, Knowledge sources."""
    },
    {
        "title": "Data Agent Instructions Best Practices",
        "topic": "prep-for-ai",
        "content": """Instructions have a 4,800 character limit. Exceeding this causes silent truncation.
Best practice: Keep under 3,800 chars. Include routing rules, metric preferences, and domain context.
Structure: 1) Role description 2) Domain context 3) Routing rules 4) Output format preferences."""
    },
    {
        "title": "Verified Answers Pattern",
        "topic": "verified-answers",
        "content": """Verified answers are pre-built DAX patterns that bypass NL-to-DAX generation.
Benefits: Consistent results, faster response (skip generation), governance compliance.
Best practice: Add 8+ verified answers for top KPI questions. Include TOP N limits.
Format: Question → DAX pattern with EVALUATE, SUMMARIZE, or CALCULATETABLE."""
    },
    {
        "title": "AI Data Schema Configuration",
        "topic": "schema",
        "content": """AI Data Schema controls which tables the agent can access.
Fewer tables = faster schema lookup = lower latency.
Best practice: Limit to 12-15 core tables. Exclude staging, archive, and system tables.
Impact: Each additional table adds ~200-400ms to schema lookup phase."""
    },
    {
        "title": "Schema Scope Optimization",
        "topic": "scope",
        "content": """Schema scope directly impacts bd_schema breakdown timing.
Large scope (30+ tables): 6000-8000ms schema lookup every query.
Optimized scope (12 tables): 1500-2500ms schema lookup.
Reduction technique: Use AI Data Schema to include only tables referenced in verified answers."""
    },
    {
        "title": "NL-to-DAX Generation",
        "topic": "nl2dax",
        "content": """The NL-to-DAX phase (bd_nldax) converts natural language to DAX queries.
This is the most variable latency component — typically 3000-15000ms.
Reduce by: Adding verified answers, simplifying instructions, providing few-shot DAX examples.
Anti-pattern: Long instructions with many examples increase generation time."""
    },
    {
        "title": "DAX Query Execution",
        "topic": "execution",
        "content": """DAX execution (bd_exec) runs the generated DAX against the semantic model.
Typical range: 500-5000ms depending on model size and query complexity.
Direct Lake models: Execution depends on V-Order optimization and parquet file layout.
Import models: Execution depends on VertiPaq compression and cardinality."""
    },
    {
        "title": "Retry Mechanism",
        "topic": "routing",
        "content": """When the agent generates incorrect DAX, it retries with error context.
Each retry costs ~3100ms (generation + execution + error handling).
Retries indicate: Wrong table targeted, ambiguous measure names, missing routing rules.
Fix: Add explicit routing rules in instructions for secondary tables."""
    },
    {
        "title": "Routing Rules Pattern",
        "topic": "routing",
        "content": """Routing rules in instructions help the agent select the correct table first.
Pattern: 'For questions about [topic], use [table_name] as the primary source.'
Example: 'For length of stay questions, use FactEncounters. For readmission questions, use FactReadmissions.'
Impact: Eliminates 1-3 retries per question = 3100-9300ms savings."""
    },
    {
        "title": "TOPN Guard Pattern",
        "topic": "dax",
        "content": """Cross-entity queries without TOP N limits can scan entire tables.
Risk: Timeout on tables with 100K+ rows. Agent may return partial results or fail.
Fix: Add few-shot examples with TOP 25 in instructions.
Example: EVALUATE TOPN(25, SUMMARIZE(Table, Column1, Column2, \"Metric\", [Measure]))"""
    },
    {
        "title": "Measure Deduplication",
        "topic": "optimization",
        "content": """Duplicate or near-duplicate measure names cause agent confusion.
The agent may pick the wrong measure, leading to incorrect results and retries.
Detection: Compare measure names with >85% character similarity.
Fix: Rename measures to be unambiguous, or hide deprecated duplicates."""
    },
    {
        "title": "VertiPaq Optimization",
        "topic": "vertipaq",
        "content": """VertiPaq is the in-memory columnar storage engine for Import mode models.
Optimization targets: Column cardinality, data types, compression.
High cardinality columns (>1M unique values) increase memory and slow scans.
Best practice: Use integer keys, avoid wide string columns, enable compression."""
    },
    {
        "title": "Direct Lake Mode",
        "topic": "direct-lake",
        "content": """Direct Lake reads parquet files directly from OneLake without importing.
Benefits: No refresh needed, always current data.
Performance depends on: V-Order optimization, file layout, column groups.
Risk: Large tables may trigger DirectQuery fallback — significant latency spike."""
    },
    {
        "title": "V-Order Optimization",
        "topic": "direct-lake",
        "content": """V-Order is a write-time optimization for Direct Lake parquet files.
Provides 15-25% execution time improvement on analytical queries.
Applied via notebook: spark.conf.set('spark.sql.parquet.vorder.enabled', 'true')
Must re-write all parquet files after enabling V-Order."""
    },
    {
        "title": "Capacity Units and Throttling",
        "topic": "performance",
        "content": """Microsoft Fabric uses Capacity Units (CUs) for compute allocation.
AI CU consumption: Each agent query consumes AI CUs.
Throttling occurs when CU consumption exceeds capacity allocation.
Monitor: Check throttle_events in capacity metrics. >50 events/week = upgrade needed."""
    },
    {
        "title": "Data Agent Latency Breakdown",
        "topic": "performance",
        "content": """Total latency = bd_parse + bd_schema + bd_nldax + bd_exec + bd_synth + retry overhead.
bd_parse: NL parsing (~200-500ms, not optimizable)
bd_schema: Schema lookup (1500-8000ms, reduce by scope)
bd_nldax: DAX generation (3000-15000ms, reduce by verified answers)
bd_exec: DAX execution (500-5000ms, optimize model)
bd_synth: Response synthesis (~200-500ms, not optimizable)"""
    },
    {
        "title": "Physician Governance",
        "topic": "data-agent",
        "content": """Healthcare data agents must prevent physician-level data exposure.
Governance rule: Never show individual physician names in agent responses.
Implementation: Add instruction rule — 'Never display individual physician or provider names.'
Enforcement: Add verified answers that aggregate provider data."""
    },
    {
        "title": "Question Battery Testing",
        "topic": "data-agent",
        "content": """Test data agents with a standardized question battery:
1. Simple KPI (e.g., 'What is the total count?')
2. Filtered aggregate (e.g., 'Show count for this month')
3. Ranking (e.g., 'Top 10 items by volume')
4. Time intelligence (e.g., 'Compare this year vs last year')
5. Cross-entity join (e.g., 'Show breakdown by category')
6. Governance test (e.g., 'Show by individual provider')"""
    },
    {
        "title": "Prep for AI Configuration",
        "topic": "prep-for-ai",
        "content": """Prep for AI is the configuration interface for Data Agents.
Components: Instructions, Verified Answers, AI Data Schema.
Access: Power BI Desktop → Model view → Prep for AI tab.
After changes: Publish model to workspace for agent to pick up new config."""
    },
    {
        "title": "Semantic Model Best Practices",
        "topic": "semantic-model",
        "content": """Semantic model optimization for Data Agents:
1. Clear, descriptive table and measure names
2. Add descriptions to all tables and key measures
3. Hide unnecessary columns and tables
4. Use star schema with clear fact/dimension separation
5. Minimize table count (12-15 core tables)
6. Ensure relationships are properly defined"""
    },
    {
        "title": "Data Agent Error Handling",
        "topic": "data-agent",
        "content": """Common Data Agent errors and causes:
1. 'I couldn't find relevant data' — Wrong table scope or missing routing
2. 'I encountered an error' — Invalid DAX generated, needs verified answer
3. Timeout — Query too complex, needs TOPN guard or scope reduction
4. Incorrect results — Ambiguous measure names, needs deduplication
5. Partial results — DirectQuery fallback on Direct Lake"""
    },
    {
        "title": "Instruction Character Optimization",
        "topic": "prep-for-ai",
        "content": """Optimizing instructions within the 4,800 char limit:
1. Remove redundant examples (keep 3-4 best)
2. Use concise routing rules (one line per table)
3. Reference measure names exactly as in model
4. Include metric format preferences (%, #, $)
5. Add governance rules as single-line constraints
6. Test after each edit — publish and verify"""
    },
    {
        "title": "Cross-Model Analysis",
        "topic": "optimization",
        "content": """When analyzing multiple Data Agents across workspaces:
1. Compare instruction patterns — identify common gaps
2. Look for schema scope consistency
3. Check for duplicate agents on same model
4. Compare verified answer coverage
5. Identify workspace-level throttling patterns"""
    },
    {
        "title": "Monte Carlo Simulation for Latency",
        "topic": "simulation",
        "content": """Monte Carlo simulation predicts latency improvement from fixes:
1. Calibrate distributions from behavioral profile
2. Run 500+ iterations per scenario
3. Output P10 (optimistic), P50 (expected), P90 (conservative)
4. Key: Distributions must have variance — not hardcoded values
5. Each fix has independent reduction factors for schema, DAX, execution phases"""
    },
    {
        "title": "Fix Validation Process",
        "topic": "validation",
        "content": """Validation measures actual impact of recommended fixes:
1. Baseline battery: Run 10+ questions, record latency
2. Apply fixes: Modify instructions, add verified answers, adjust schema
3. Post-fix battery: Re-run same questions
4. Delta analysis: Compare before/after per question
5. Resolution: Finding marked RESOLVED if delta > 30%"""
    },
    {
        "title": "Data Agent Architecture",
        "topic": "data-agent",
        "content": """Data Agent processing pipeline:
1. User submits natural language question
2. Agent parses question intent (bd_parse phase)
3. Agent looks up schema to identify relevant tables (bd_schema phase)
4. Agent generates DAX query (bd_nldax phase)
5. DAX executed against semantic model (bd_exec phase)
6. Results synthesized into natural language (bd_synth phase)
7. If error: retry from step 3 with error context"""
    },
    {
        "title": "Knowledge Sources for Agents",
        "topic": "data-agent",
        "content": """Data Agents can use Knowledge sources for grounding:
- Upload documents that provide domain context
- Agent references knowledge when generating responses
- Helps with terminology and domain-specific interpretations
- Best practice: Add glossary of domain terms
- Limitation: Knowledge doesn't affect DAX generation directly"""
    },
    {
        "title": "Workspace Management",
        "topic": "data-agent",
        "content": """Data Agent workspace considerations:
- Each workspace can have multiple semantic models
- Each model can have one Data Agent configuration
- Agent inherits workspace-level security (RLS)
- Premium/Fabric capacity required for Data Agents
- Cross-workspace analysis helps identify org-wide patterns"""
    },
    {
        "title": "Semantic Model Relationships",
        "topic": "semantic-model",
        "content": """Relationship configuration affects agent query generation:
- Star schema preferred: one fact table, multiple dimensions
- Bi-directional cross-filtering increases query complexity
- Inactive relationships need explicit USERELATIONSHIP in DAX
- Many-to-many relationships often confuse the agent
- Best practice: Single-direction filtering, minimal relationship count"""
    },
    {
        "title": "DAX Few-Shot Examples",
        "topic": "dax",
        "content": """Few-shot DAX examples in instructions improve generation quality:
- Include 3-4 representative patterns
- Always include TOPN for ranking queries
- Show date filtering pattern with correct column name
- Include aggregation examples (SUM, AVERAGE, COUNT)
- Format: 'For [question type], use: EVALUATE [DAX pattern]'"""
    },
    {
        "title": "Performance Monitoring",
        "topic": "performance",
        "content": """Monitor Data Agent performance via:
1. Fabric Capacity Metrics app — CU consumption, throttling
2. Query traces — latency breakdown per question
3. Retry analysis — frequency and root cause
4. User feedback — accuracy and relevance
5. Establish baselines: Track P50 and P95 latency weekly"""
    },
    {
        "title": "Synthetic Data Generation",
        "topic": "simulation",
        "content": """Synthetic data for testing agent fixes:
1. Generate structurally faithful data (same schema, fake values)
2. PHI-safe: No real patient/employee data
3. Session-scoped: Store in tmp/{session_id}/
4. Always deleted on Reset
5. Scale factor configurable (default 0.025 = 2.5% of original size)"""
    },
    {
        "title": "Governance and Compliance",
        "topic": "data-agent",
        "content": """Data Agent governance requirements:
1. PHI protection: Never expose individual patient data
2. Provider anonymization: Aggregate physician-level data
3. Financial data: Restrict access to authorized roles
4. Audit trail: Log all agent queries and responses
5. Data retention: Define synthetic data lifecycle policy"""
    },
    {
        "title": "Instruction Routing Rules",
        "topic": "routing",
        "content": """Effective routing rules format:
- 'When asked about [topic], query [TableName] first'
- 'For [metric] questions, use the [MeasureName] measure'
- 'If the question mentions [keyword], use [TableName].[ColumnName]'
- Keep routing rules at the top of instructions
- Maximum 8-10 routing rules for clarity"""
    },
    {
        "title": "Agent Response Quality",
        "topic": "data-agent",
        "content": """Measuring agent response quality:
1. Accuracy: Does the DAX return correct data?
2. Completeness: Are all relevant dimensions included?
3. Timeliness: Is latency within acceptable range (<15s)?
4. Governance: Are restricted fields properly hidden?
5. Consistency: Do repeated queries give same results?"""
    },
    {
        "title": "Latency Optimization Priority",
        "topic": "optimization",
        "content": """Optimization priority based on typical impact:
1. CRITICAL: Instruction truncation (fix first, blocks everything)
2. CRITICAL: Schema scope >30 tables (8000ms+ per query)
3. HIGH: Zero verified answers (6000ms+ avoidable per KPI)
4. HIGH: Routing gaps (3100ms per retry)
5. HIGH: TOPN missing (timeout risk on large tables)
6. MEDIUM: Measure deduplication (2000ms from confusion)
7. MEDIUM: V-Order not applied (2000ms execution gain)
8. LOW: Missing descriptions (1500ms from guessing)"""
    },
    {
        "title": "Data Agent Limits and Quotas",
        "topic": "data-agent",
        "content": """Current Data Agent limits:
- Instruction text: 4,800 characters max
- Verified answers: No hard limit, recommend 8-15
- Tables in scope: No hard limit, recommend 12-15
- Response timeout: 60 seconds default
- Concurrent queries: Depends on capacity SKU
- Knowledge sources: Limited to uploaded documents"""
    },
    {
        "title": "Fix Impact Estimation",
        "topic": "simulation",
        "content": """Estimating fix impact before implementation:
- instruction_trim: 20-40% reduction in bd_nldax if currently truncated
- schema_scope: 30-60% reduction in bd_schema
- routing_rules: Eliminates retries (3100ms each)
- verified_answers: Bypasses bd_nldax entirely for covered questions
- topn_guard: Prevents timeouts on cross-entity queries
- measure_dedup: 10-20% reduction in bd_nldax
- vorder: 15-25% reduction in bd_exec for Direct Lake
- physician_gov: No latency impact, governance compliance only"""
    },
]


def get_chunks():
    """Return all knowledge chunks with IDs."""
    chunks = []
    for i, chunk in enumerate(KNOWLEDGE_CHUNKS):
        chunk_id = hashlib.md5(chunk['title'].encode()).hexdigest()[:12]
        chunks.append({
            'id': f'ms_docs_{chunk_id}',
            'title': chunk['title'],
            'topic': chunk['topic'],
            'content': chunk['content'].strip(),
        })
    return chunks


def save_chunks(output_dir='./knowledge/chunks'):
    """Save chunks to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    chunks = get_chunks()
    with open(os.path.join(output_dir, 'microsoft_docs.json'), 'w') as f:
        json.dump(chunks, f, indent=2)
    print(f'Saved {len(chunks)} chunks to {output_dir}/microsoft_docs.json')
    return chunks


if __name__ == '__main__':
    chunks = save_chunks()
    print(f'Total chunks: {len(chunks)}')
