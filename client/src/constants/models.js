// Available LLM models for agent pipeline
// Each model can be selected per-agent or as the default for all agents
// GPT-5.4-pro uses the Responses API (reasoning model) — proxy handles routing automatically
// grok removed per user request
export const MODELS = [
  {
    id: 'gpt-5.4',
    name: 'GPT-5.4',
    provider: 'Azure OpenAI',
    description: 'Standard completions model — fast, reliable, uses Chat Completions API',
    authMethods: ['api-key'],
    strengths: ['Fast inference', 'Reliable', 'Chat Completions API', 'General purpose'],
    recommended: ['domain_intelligence', 'synthesis', 'remediation', 'finding_validator', 'report_validator'],
    default: true,
  },
  {
    id: 'gpt-5.4-pro',
    name: 'GPT-5.4 Pro',
    provider: 'Azure OpenAI',
    description: 'Reasoning model — highest intelligence, uses Responses API (may be slower)',
    authMethods: ['api-key'],
    strengths: ['Deep reasoning', 'Complex analysis', 'Multi-step logic', 'Highest accuracy'],
    recommended: [],
  },
  {
    id: 'DeepSeek-V3.2-Speciale',
    name: 'DeepSeek V3.2 Speciale',
    provider: 'Azure AI (DeepSeek)',
    description: 'Fast analysis model — 2-3s response time, excellent for rule-heavy agents',
    authMethods: ['api-key'],
    strengths: ['Fast inference', 'Pattern matching', 'Code understanding', 'Reliable'],
    recommended: ['adversarial_probe', 'schema', 'dax', 'execution', 'monte_carlo'],
  },
  {
    id: 'DeepSeek-V3.2',
    name: 'DeepSeek V3.2',
    provider: 'Azure AI (DeepSeek)',
    description: 'General-purpose backup model',
    authMethods: ['api-key'],
    strengths: ['General purpose', 'Fast inference', 'Reliable'],
    recommended: [],
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'Azure OpenAI',
    description: 'Multimodal GPT model — fast, good for general tasks',
    authMethods: ['api-key'],
    strengths: ['Multimodal', 'Fast', 'General purpose'],
    recommended: [],
  },
];

// Default model assignment per agent — mixed GPT-5.4 + DeepSeek V3.2 Speciale
// DeepSeek V3.2 Speciale: Most agents — fast, reliable, no empty-content issues
// GPT-5.4: Finding/Report Validators only (gpt-5.4 intermittently returns empty for large prompts, retry+fallback handles it)
// Note: GPT-5.4 Pro (reasoning model) is available in dropdown but not default — it uses Responses API which can be slow
export const DEFAULT_AGENT_MODELS = {
  domain_intelligence: 'DeepSeek-V3.2-Speciale',
  adversarial_probe: 'DeepSeek-V3.2-Speciale',
  schema: 'DeepSeek-V3.2-Speciale',
  dax: 'DeepSeek-V3.2-Speciale',
  execution: 'DeepSeek-V3.2-Speciale',
  synthesis: 'DeepSeek-V3.2-Speciale',
  monte_carlo: 'DeepSeek-V3.2-Speciale',
  remediation: 'DeepSeek-V3.2-Speciale',
  finding_validator: 'gpt-5.4',
  report_validator: 'gpt-5.4',
};

// Get model by ID
export function getModel(modelId) {
  return MODELS.find(m => m.id === modelId) || MODELS[0];
}

// Get default model
export function getDefaultModel() {
  return MODELS.find(m => m.default) || MODELS[0];
}
