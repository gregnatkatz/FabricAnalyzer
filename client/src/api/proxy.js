// All API calls go through Express proxy at :3001 — never directly to external services
const API_BASE = '/api';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function healthCheck() {
  return request('/health');
}

export async function runAgent(agentId, payload, accessToken) {
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  return request('/agent', {
    method: 'POST',
    headers,
    body: JSON.stringify({ agentId, ...payload }),
  });
}

export async function runAnalysis(dbPath, sessionState) {
  return request('/analyze', {
    method: 'POST',
    body: JSON.stringify({ dbPath, ...sessionState }),
  });
}

export async function loadSampleDataset() {
  return request('/sample', { method: 'POST' });
}

export async function getScenarios() {
  return request('/scenarios');
}

export async function loadScenario(scenarioId) {
  return request('/sample/scenario', {
    method: 'POST',
    body: JSON.stringify({ scenarioId }),
  });
}

export async function getWorkspaces(accessToken) {
  return request('/fabric/workspaces', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function getModels(workspaceId, accessToken) {
  return request(`/fabric/workspaces/${workspaceId}/models`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function collectData(workspaceId, modelId, accessToken) {
  return request('/fabric/collect', {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ workspaceId, modelId }),
  });
}

export async function collectDataDirect(payload) {
  return request('/fabric/collect-direct', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function collectXmla(workspaceId, modelId, token, dbPath) {
  return request('/fabric/xmla-collect', {
    method: 'POST',
    body: JSON.stringify({ workspaceId, modelId, token, dbPath }),
  });
}

export async function resetSession(scope, sessionId) {
  return request('/reset', {
    method: 'POST',
    body: JSON.stringify({ scope, sessionId }),
  });
}

export async function exportPdf(sessionData) {
  const res = await fetch(`${API_BASE}/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sessionData),
  });
  if (!res.ok) throw new Error('PDF export failed');
  return res.blob();
}

// SSE stream for validation progress
export function startValidation(sessionId, fixes, onProgress, onComplete, onError) {
  const params = new URLSearchParams({ sessionId, fixes: fixes.join(',') });
  const eventSource = new EventSource(`${API_BASE}/validate?${params}`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'progress') {
      onProgress(data);
    } else if (data.type === 'complete') {
      onComplete(data);
      eventSource.close();
    } else if (data.type === 'error') {
      onError(new Error(data.message));
      eventSource.close();
    }
  };

  eventSource.onerror = (err) => {
    onError(err);
    eventSource.close();
  };

  return eventSource;
}
