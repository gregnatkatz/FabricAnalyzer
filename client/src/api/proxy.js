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

export async function getAgents(workspaceId, accessToken) {
  return request(`/fabric/workspaces/${workspaceId}/agents`, {
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

// Live collection — calls real Data Agent /chat API with SSE progress streaming
export function collectLive(payload, accessToken, onProgress, onTrace, onComplete, onError) {
  const API_BASE = '/api';
  const controller = new AbortController();

  fetch(`${API_BASE}/fabric/collect-live`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
    signal: controller.signal,
  }).then(async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            if (data.type === 'progress') onProgress?.(data);
            else if (data.type === 'trace') onTrace?.(data);
            else if (data.type === 'complete') onComplete?.(data);
            else if (data.type === 'error') onError?.(new Error(data.message));
            else if (data.type === 'start') onProgress?.(data);
            else if (data.type === 'retry') onProgress?.(data);
            else if (data.type === 'building') onProgress?.(data);
          } catch {
            // Ignore malformed SSE lines
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') onError?.(err);
  });

  return controller; // caller can abort with controller.abort()
}

// Set LLM auth token (Azure AD Cognitive Services token)
export async function setLlmToken(token) {
  return request('/llm-token', {
    method: 'POST',
    body: JSON.stringify({ token }),
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

// Microsoft Learn Best Practices
export async function getMsLearnArticles() {
  return request('/mslearn/articles');
}

export async function enrichFindingsWithMsLearn(findings) {
  return request('/mslearn/enrich', {
    method: 'POST',
    body: JSON.stringify({ findings }),
  });
}

export async function refreshMsLearnCache() {
  return request('/mslearn/refresh', { method: 'POST' });
}

// Scheduled Analysis
export async function getSchedules() {
  return request('/schedules');
}

export async function createSchedule(schedule) {
  return request('/schedules', {
    method: 'POST',
    body: JSON.stringify(schedule),
  });
}

export async function deleteSchedule(id) {
  return request(`/schedules/${id}`, { method: 'DELETE' });
}

export async function updateSchedule(id, updates) {
  return request(`/schedules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

// Analysis History / Trending
export async function getHistory(workspaceId, limit) {
  const params = new URLSearchParams();
  if (workspaceId) params.set('workspaceId', workspaceId);
  if (limit) params.set('limit', String(limit));
  return request(`/history?${params}`);
}

export async function saveHistoryRun(runData) {
  return request('/history', {
    method: 'POST',
    body: JSON.stringify(runData),
  });
}

export async function clearHistory() {
  return request('/history', { method: 'DELETE' });
}

// SSE stream for validation progress
export function startValidation(sessionId, fixes, onProgress, onComplete, onError) {
  const params = new URLSearchParams({ sessionId, fixes: fixes.join(',') });
  const eventSource = new EventSource(`${API_BASE}/validate?${params}`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'progress' || data.type === 'phase') {
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
