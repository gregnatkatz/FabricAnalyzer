// Available LLM models for agent pipeline
// Each model can be selected per-agent or as the default for all agents
export const MODELS = [
  {
    id: 'gpt-5.4-pro-2',
    name: 'GPT-5.4 Pro',
    provider: 'Azure OpenAI',
    description: 'High-capability reasoning model — best for synthesis, remediation, and complex analysis',
    authMethods: ['api-key', 'entra-id'],
    strengths: ['Complex reasoning', 'JSON output', 'Large context'],
    recommended: ['synthesis', 'remediation', 'monte_carlo'],
    default: true,
  },
  {
    id: 'grok-4-1-fast-reasoning',
    name: 'Grok 4.1 Fast Reasoning',
    provider: 'Azure AI (xAI)',
    description: 'Fast reasoning model — ideal for rapid domain intelligence and adversarial probing',
    authMethods: ['entra-id'],
    strengths: ['Fast inference', 'Reasoning chains', 'Pattern detection'],
    recommended: ['domain_intelligence', 'adversarial_probe'],
  },
  {
    id: 'DeepSeek-V3.2-Speciale',
    name: 'DeepSeek V3.2 Speciale',
    provider: 'Azure AI (DeepSeek)',
    description: 'Specialized deep analysis model — excellent for schema and DAX pattern analysis',
    authMethods: ['api-key'],
    strengths: ['Deep analysis', 'Code understanding', 'Pattern matching'],
    recommended: ['schema', 'dax', 'execution'],
  },
  {
    id: 'Phi-4-reasoning',
    name: 'Phi-4 Reasoning',
    provider: 'Azure AI (Microsoft)',
    description: 'Compact reasoning model — efficient for validation and quick checks',
    authMethods: ['api-key'],
    strengths: ['Efficient', 'Low latency', 'Reasoning'],
    recommended: ['validation'],
  },
];

// Default model assignment per agent
export const DEFAULT_AGENT_MODELS = {
  domain_intelligence: 'grok-4-1-fast-reasoning',
  adversarial_probe: 'grok-4-1-fast-reasoning',
  schema: 'DeepSeek-V3.2-Speciale',
  dax: 'DeepSeek-V3.2-Speciale',
  execution: 'DeepSeek-V3.2-Speciale',
  synthesis: 'gpt-5.4-pro-2',
  monte_carlo: 'gpt-5.4-pro-2',
  remediation: 'gpt-5.4-pro-2',
  validation: 'Phi-4-reasoning',
};

// Get model by ID
export function getModel(modelId) {
  return MODELS.find(m => m.id === modelId) || MODELS[0];
}

// Get default model
export function getDefaultModel() {
  return MODELS.find(m => m.default) || MODELS[0];
}
