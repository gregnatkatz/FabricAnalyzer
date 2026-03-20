// Available LLM models for agent pipeline
// Each model can be selected per-agent or as the default for all agents
// Note: gpt-5.4-pro does NOT support chat completions (reasoning model, uses responses API)
// Note: grok-4-1-fast-reasoning removed per user request
export const MODELS = [
  {
    id: 'DeepSeek-V3.2-Speciale',
    name: 'DeepSeek V3.2 Speciale',
    provider: 'Azure AI (DeepSeek)',
    description: 'Primary analysis model — fast 2-3s response time, excellent for all analysis tasks',
    authMethods: ['api-key'],
    strengths: ['Deep analysis', 'Code understanding', 'Pattern matching', 'Fast inference'],
    recommended: ['domain_intelligence', 'adversarial_probe', 'schema', 'dax', 'execution', 'synthesis', 'monte_carlo', 'remediation', 'validation'],
    default: true,
  },
  {
    id: 'DeepSeek-V3.2',
    name: 'DeepSeek V3.2',
    provider: 'Azure AI (DeepSeek)',
    description: 'Secondary analysis model — general-purpose backup for pipeline agents',
    authMethods: ['api-key'],
    strengths: ['General purpose', 'Fast inference', 'Reliable'],
    recommended: [],
  },
];

// Default model assignment per agent
// Primary: DeepSeek V3.2 Speciale (fast, reliable, chat completions compatible)
// Secondary: DeepSeek V3.2 (general-purpose backup)
// Note: gpt-5.4-pro doesn't support chat completions; grok removed per user request
export const DEFAULT_AGENT_MODELS = {
  domain_intelligence: 'DeepSeek-V3.2-Speciale',
  adversarial_probe: 'DeepSeek-V3.2-Speciale',
  schema: 'DeepSeek-V3.2-Speciale',
  dax: 'DeepSeek-V3.2-Speciale',
  execution: 'DeepSeek-V3.2-Speciale',
  synthesis: 'DeepSeek-V3.2-Speciale',
  monte_carlo: 'DeepSeek-V3.2-Speciale',
  remediation: 'DeepSeek-V3.2-Speciale',
  validation: 'DeepSeek-V3.2-Speciale',
};

// Get model by ID
export function getModel(modelId) {
  return MODELS.find(m => m.id === modelId) || MODELS[0];
}

// Get default model
export function getDefaultModel() {
  return MODELS.find(m => m.default) || MODELS[0];
}
