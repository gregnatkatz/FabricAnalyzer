import React, { useState } from 'react';
import { loginPopup, logout, getAccessToken } from '../auth/msalConfig';
import { loadSampleDataset, getWorkspaces, getModels, collectData, getScenarios, loadScenario } from '../api/proxy';

export default function ConnectTab({ session, updateSession, onNavigate }) {
  const [workspaceId, setWorkspaceId] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [scenarios, setScenarios] = useState([]);
  const [showScenarios, setShowScenarios] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(null);

  const handleSignIn = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await loginPopup();
      updateSession({
        connected: true,
        user: response.account.name || response.account.username,
      });
    } catch (err) {
      setError(`Sign-in failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await logout();
      updateSession({ connected: false, user: null });
    } catch (err) {
      console.error('Sign-out error:', err);
    }
  };

  const handleLoadSample = async () => {
    try {
      setLoading(true);
      setStatus('Loading sample dataset...');
      setError('');
      const result = await loadSampleDataset();
      updateSession({
        connected: true,
        sampleMode: true,
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelName: result.modelName || 'LOS Sample Model',
        domain: result.domain || 'CLINICAL_INPATIENT',
        traces: result.traces || [],
        collectionComplete: true,
      });
      setStatus('Sample dataset loaded successfully');
      onNavigate('traces');
    } catch (err) {
      setError(`Failed to load sample: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleShowScenarios = async () => {
    try {
      setLoading(true);
      setError('');
      const result = await getScenarios();
      setScenarios(result.scenarios || []);
      setShowScenarios(true);
    } catch (err) {
      setError(`Failed to load scenarios: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadScenario = async (scenarioId) => {
    try {
      setLoading(true);
      setError('');
      const scenario = scenarios.find(s => s.id === scenarioId);
      setStatus(`Loading scenario ${scenarioId}: ${scenario?.name || ''}...`);
      const result = await loadScenario(scenarioId);
      updateSession({
        connected: true,
        sampleMode: true,
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelName: result.modelName,
        domain: result.domain,
        traces: result.traces || [],
        collectionComplete: true,
        scenarioId: result.scenarioId,
        scenarioName: result.scenarioName,
      });
      setStatus(`Loaded: ${result.scenarioName}`);
      onNavigate('traces');
    } catch (err) {
      setError(`Failed to load scenario: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchModels = async () => {
    if (!workspaceId.trim()) return;
    try {
      setLoading(true);
      setError('');
      const token = await getAccessToken();
      const result = await getModels(workspaceId.trim(), token);
      setModels(result.models || []);
      updateSession({ workspaceId: workspaceId.trim() });
    } catch (err) {
      setError(`Failed to fetch models: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCollect = async () => {
    if (!selectedModel) return;
    try {
      setLoading(true);
      setError('');
      setStatus('Collecting data from Fabric workspace...');
      const token = await getAccessToken();
      const result = await collectData(workspaceId, selectedModel, token);
      updateSession({
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelId: selectedModel,
        modelName: result.modelName,
        domain: result.domain,
        traces: result.traces || [],
        collectionComplete: true,
      });
      setStatus('Data collection complete');
      onNavigate('traces');
    } catch (err) {
      setError(`Collection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fade-in" style={{ maxWidth: 600, margin: '0 auto' }}>
      <div className="glass" style={{ padding: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 24 }}>
          Connect to Fabric Workspace
        </h2>

        {/* Sample Dataset Buttons */}
        <div style={{ marginBottom: 32, paddingBottom: 24, borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-primary"
              onClick={handleLoadSample}
              disabled={loading}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {loading && !showScenarios ? 'Loading...' : 'Sample Dataset'}
            </button>
            <button
              className="btn-secondary"
              onClick={handleShowScenarios}
              disabled={loading}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {loading && showScenarios ? 'Loading...' : `Test Scenarios (20)`}
            </button>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
            Load pre-built sample data — no Fabric connection required
          </p>

          {/* Scenario Picker */}
          {showScenarios && scenarios.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{
                maxHeight: 360,
                overflowY: 'auto',
                border: '1px solid var(--border)',
                borderRadius: 8,
                background: 'rgba(0,0,0,0.15)',
              }}>
                {scenarios.map(s => {
                  const severityColor = {
                    CLINICAL_INPATIENT: '#ef4444',
                    CLINICAL_QUALITY: '#f97316',
                    REVENUE_CYCLE: '#22c55e',
                    WORKFORCE: '#3b82f6',
                    SUPPLY_CHAIN: '#a855f7',
                    PATIENT_EXPERIENCE: '#ec4899',
                    OPERATIONAL: '#eab308',
                    FINANCIAL: '#06b6d4',
                  }[s.domain] || '#888';

                  return (
                    <div
                      key={s.id}
                      onClick={() => !loading && handleLoadScenario(s.id)}
                      style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--border)',
                        cursor: loading ? 'wait' : 'pointer',
                        transition: 'background 0.15s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: '#000',
                        background: severityColor,
                        padding: '2px 6px',
                        borderRadius: 4,
                        minWidth: 28,
                        textAlign: 'center',
                      }}>
                        {s.id}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
                          {s.name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          {s.domain} — {(s.key_issues || []).slice(0, 3).join(', ')}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* OAuth Sign-In */}
        <div style={{ marginBottom: 24 }}>
          {!session.connected ? (
            <button
              className="btn-secondary"
              onClick={handleSignIn}
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              Connect to Fabric (OAuth)
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 14, color: 'var(--green)' }}>
                Signed in as {session.user}
              </span>
              <button className="btn-secondary" onClick={handleSignOut} style={{ fontSize: 12, padding: '4px 12px' }}>
                Sign Out
              </button>
            </div>
          )}
        </div>

        {/* Workspace ID Input */}
        {session.connected && !session.sampleMode && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Workspace ID (from Power BI URL)
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={workspaceId}
                onChange={e => setWorkspaceId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
              <button className="btn-primary" onClick={handleFetchModels} disabled={loading} style={{ padding: '10px 16px' }}>
                Load
              </button>
            </div>
          </div>
        )}

        {/* Model Selector */}
        {models.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Select Data Agent
            </label>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                color: 'var(--text)',
                fontFamily: 'var(--font-display)',
                fontSize: 14,
                outline: 'none',
              }}
            >
              <option value="">Choose a model...</option>
              {models.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Collect Data Button */}
        {selectedModel && (
          <button
            className="btn-primary"
            onClick={handleCollect}
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {loading ? status || 'Collecting...' : 'Collect Data'}
          </button>
        )}

        {/* Status & Error */}
        {status && !error && (
          <p style={{ fontSize: 13, color: 'var(--green)', marginTop: 16, textAlign: 'center' }}>{status}</p>
        )}
        {error && (
          <p style={{ fontSize: 13, color: 'var(--red)', marginTop: 16, textAlign: 'center' }}>{error}</p>
        )}
      </div>
    </div>
  );
}
