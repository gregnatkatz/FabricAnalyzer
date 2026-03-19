// Fix definitions with math model reduction factors
// From Microsoft docs benchmarks + Sprint 0 empirical data
export const FIXES = {
  instruction_trim: {
    key: 'instruction_trim',
    label: 'Trim Instructions',
    description: 'LLM summarization to under 3,800 chars preserving all routing rules and metric preferences',
    schemaF: 0.25,
    daxF: 0.12,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  schema_scope: {
    key: 'schema_scope',
    label: 'Scope Schema Tables',
    description: 'Rewrite tables_in_schema to exactly the 12 core tables',
    schemaF: 0.30,
    daxF: 0.16,
    execF: 0.00,
    effort: 'Low',
    owner: 'Data Engineer',
  },
  routing_rules: {
    key: 'routing_rules',
    label: 'Add Routing Rules',
    description: 'Inject domain-specific routing rules for secondary tables',
    schemaF: 0.12,
    daxF: 0.24,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  measure_dedup: {
    key: 'measure_dedup',
    label: 'Deduplicate Measures',
    description: 'Mark non-canonical measures as excluded from AI Data Schema',
    schemaF: 0.08,
    daxF: 0.22,
    execF: 0.00,
    effort: 'Low',
    owner: 'Data Engineer',
  },
  verified_answers: {
    key: 'verified_answers',
    label: 'Add Verified Answers',
    description: 'Inject verified answer DAX patterns for high-frequency KPI questions',
    schemaF: 0.00,
    daxF: 0.48,
    execF: 0.00,
    effort: 'Medium',
    owner: 'AI Engineer',
  },
  row_limits: {
    key: 'row_limits',
    label: 'Add TOP Limits',
    description: 'Inject TOP 25 few-shot examples to prevent full table scans',
    schemaF: 0.00,
    daxF: 0.04,
    execF: 0.42,
    effort: 'Low',
    owner: 'AI Engineer',
  },
  vorder: {
    key: 'vorder',
    label: 'Apply V-Order',
    description: 'Flag Direct Lake tables as V-Order optimized — 22% exec reduction',
    schemaF: 0.00,
    daxF: 0.00,
    execF: 0.24,
    effort: 'Medium',
    owner: 'Data Engineer',
  },
  physician_gov: {
    key: 'physician_gov',
    label: 'Physician Governance',
    description: 'GOVERNANCE REQUIRED — cannot be programmatically applied',
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
