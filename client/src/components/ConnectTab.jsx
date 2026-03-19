import React, { useState } from 'react';
import { loginPopup, logout, getAccessToken } from '../auth/msalConfig';
import { loadSampleDataset, getWorkspaces, getModels, collectData } from '../api/proxy';

export default function ConnectTab({ session, updateSession, onNavigate }) {
  const [workspaceId, setWorkspaceId] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

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

        {/* Sample Dataset Button */}
        <div style={{ marginBottom: 32, paddingBottom: 24, borderBottom: '1px solid var(--border)' }}>
          <button
            className="btn-primary"
            onClick={handleLoadSample}
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {loading ? 'Loading...' : 'Sample Dataset'}
          </button>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
            Load pre-built LOS sample data — no Fabric connection required
          </p>
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
