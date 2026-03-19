// Fix definitions with math model reduction factors
// From Microsoft docs benchmarks + Sprint 0 empirical data
export const FIXES = {
  instruction_trim: {
    key: 'instruction_trim',
    label: 'Trim Instructions',
    description: 'Use LLM summarization to compress instruction text from current length to under 3,800 chars. Preserves all routing rules, metric definitions, and domain terminology while removing redundant examples and verbose explanations. Reduces schema resolution time by 25% and DAX generation time by 12%.',
    schemaF: 0.25,
    daxF: 0.12,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  schema_scope: {
    key: 'schema_scope',
    label: 'Scope Schema Tables',
    description: 'Reduce the AI Data Schema scope to only the 12 core Fact and Dimension tables by removing staging, archive, temporary, and system tables via Prep for AI. Each removed table saves ~200ms in schema resolution. Reduces schema resolution by 30% and DAX generation by 16%.',
    schemaF: 0.30,
    daxF: 0.16,
    execF: 0.00,
    effort: 'Low',
    owner: 'Data Engineer',
  },
  routing_rules: {
    key: 'routing_rules',
    label: 'Add Routing Rules',
    description: 'Add explicit routing rules to instructions mapping query keywords to correct tables (e.g., "When user asks about LOS, use FactEncounter"). Prevents misrouting to wrong tables, reducing retries. Reduces schema resolution by 12% and DAX generation by 24%.',
    schemaF: 0.12,
    daxF: 0.24,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  measure_dedup: {
    key: 'measure_dedup',
    label: 'Deduplicate Measures',
    description: 'Identify and hide duplicate or near-duplicate measures (>85% name similarity) by marking non-canonical versions as excluded from the AI Data Schema. Eliminates disambiguation failures that cause 3-5s retries. Reduces schema resolution by 8% and DAX generation by 22%.',
    schemaF: 0.08,
    daxF: 0.22,
    execF: 0.00,
    effort: 'Low',
    owner: 'Data Engineer',
  },
  verified_answers: {
    key: 'verified_answers',
    label: 'Add Verified Answers',
    description: 'Add 8-12 verified answer DAX patterns for the most common KPI queries (simple aggregates, filtered counts, rankings). Verified answers bypass the NL-to-DAX engine entirely for matched queries, eliminating DAX generation latency. Reduces DAX generation time by 48% for matched patterns.',
    schemaF: 0.00,
    daxF: 0.48,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  row_limits: {
    key: 'row_limits',
    label: 'Add TOP Limits',
    description: 'Add TOPN(25) few-shot examples to instructions for ranking and cross-entity queries. Prevents the VertiPaq engine from materializing full result sets (750K+ rows) before filtering. Reduces execution time by 42% on affected queries.',
    schemaF: 0.00,
    daxF: 0.04,
    execF: 0.42,
    effort: 'Low',
    owner: 'AI Engineer',
  },
  vorder: {
    key: 'vorder',
    label: 'Apply V-Order',
    description: 'Apply V-Order optimization to Direct Lake tables. V-Order re-organizes Parquet file columnar storage for faster reads, reducing VertiPaq scan times by ~22%. Especially impactful for large fact tables with millions of rows.',
    schemaF: 0.00,
    daxF: 0.00,
    execF: 0.24,
    effort: 'Medium',
    owner: 'Data Engineer',
  },
  physician_gov: {
    key: 'physician_gov',
    label: 'Physician Governance',
    description: 'GOVERNANCE REQUIRED — This fix requires organizational approval and cannot be programmatically applied. Adds row-level security (RLS) and instruction guardrails to prevent physician/provider names from appearing in Data Agent responses. Requires stakeholder sign-off.',
    schemaF: 0.00,
    daxF: 0.00,
    execF: 0.00,
    effort: 'High',
    owner: 'Stakeholder',
  },
};

// Reduction factor caps
export const CAPS = {
  schema: 0.78,
  dax: 0.82,
  exec: 0.65,
};

// Minimum ms per trace floor
export const FLOOR_MS = 1600;

export const FIX_KEYS = Object.keys(FIXES);
