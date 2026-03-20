import React, { useState } from 'react';
import { AGENTS, AGENT_ORDER } from '../constants/agentMeta';
import { MODELS, DEFAULT_AGENT_MODELS } from '../constants/models';
import { runAnalysis } from '../api/proxy';

function AgentBubble({ agent, status, selectedModel, onModelChange, onClick }) {
  const meta = AGENTS[agent];
  const statusColor = status === 'complete' ? 'var(--green)'
    : status === 'running' ? meta.accent
    : status === 'error' ? 'var(--red)'
    : 'var(--text-muted)';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
        cursor: 'pointer', opacity: status === 'pending' ? 0.4 : 1,
        transition: 'opacity 0.3s ease',
      }}
    >
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        background: `rgba(255,255,255,0.03)`,
        border: `2px solid ${statusColor}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 24,
        boxShadow: status === 'running' ? `0 0 20px ${statusColor}40` : 'none',
        animation: status === 'running' ? 'pulse-glow 1.5s infinite' : 'none',
      }}>
        {meta.glyph}
      </div>
      <span style={{ fontSize: 10, color: statusColor, fontWeight: 500, textAlign: 'center', maxWidth: 80 }}>
        {meta.name}
      </span>
      <select
        value={selectedModel || ''}
        onChange={(e) => { e.stopPropagation(); onModelChange(agent, e.target.value); }}
        onClick={(e) => e.stopPropagation()}
        style={{
          fontSize: 9, padding: '2px 4px', width: 90,
          background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
          border: '1px solid var(--border)', borderRadius: 4,
          cursor: 'pointer', textOverflow: 'ellipsis',
        }}
      >
        {MODELS.map(m => (
          <option key={m.id} value={m.id}>{m.name}</option>
        ))}
      </select>
    </div>
  );
}

export default function WorkflowTab({ session, updateSession }) {
  const [agentStatuses, setAgentStatuses] = useState({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [agentModels, setAgentModels] = useState(() => ({ ...DEFAULT_AGENT_MODELS }));

  const handleModelChange = (agentId, modelId) => {
    setAgentModels(prev => ({ ...prev, [agentId]: modelId }));
  };

  const handleRunAnalysis = async () => {
    if (!session.dbPath) return;
    setRunning(true);
    setError('');

    // Initialize all agents as pending
    const statuses = {};
    AGENT_ORDER.forEach(a => { statuses[a] = 'pending'; });
    setAgentStatuses({ ...statuses });

    // Animate agents as running sequentially for visual feedback
    let animIdx = 0;
    const animInterval = setInterval(() => {
      if (animIdx < AGENT_ORDER.length) {
        const agentId = AGENT_ORDER[animIdx];
        setAgentStatuses(prev => ({ ...prev, [agentId]: 'running' }));
        updateSession({
          pipelineLog: [...(session.pipelineLog || []), { agent: agentId, status: 'running', ts: Date.now() }],
        });
        if (animIdx > 0) {
          const prevAgent = AGENT_ORDER[animIdx - 1];
          setAgentStatuses(prev => ({ ...prev, [prevAgent]: 'complete' }));
          updateSession({
            pipelineLog: [...(session.pipelineLog || []), { agent: prevAgent, status: 'complete', ts: Date.now() }],
          });
        }
        animIdx++;
      }
    }, 3000);

    try {
      // Run entire pipeline as a single call — much faster than per-agent
      // Pass per-agent model assignments so the pipeline routes each agent to its model
      const result = await runAnalysis(session.dbPath, {
        sessionId: session.sessionId,
        agentId: 'all',
        domain: session.domain,
        sampleMode: session.sampleMode,
        agentModels: agentModels,
      });

      clearInterval(animInterval);

      // Mark all agents as complete
      const completeStatuses = {};
      AGENT_ORDER.forEach(a => { completeStatuses[a] = 'complete'; });
      setAgentStatuses(completeStatuses);

      const completeLogs = AGENT_ORDER.map(a => ({ agent: a, status: 'complete', ts: Date.now() }));
      updateSession({
        pipelineLog: completeLogs,
        findings: result.findings || [],
        agentResults: [{ agentId: 'all', ...result }],
        ...(result.monte_carlo ? { monteCarloResults: result.monte_carlo } : {}),
        ...(result.synthesis ? { synthesisResults: result.synthesis } : {}),
        ...(result.remediation ? { remediationResults: result.remediation } : {}),
        ...(result.validation ? { validationResults: result.validation } : {}),
        ...(result.domain ? { domain: result.domain } : {}),
        analysisComplete: true,
      });
    } catch (err) {
      clearInterval(animInterval);
      // Mark remaining as error
      setAgentStatuses(prev => {
        const updated = { ...prev };
        AGENT_ORDER.forEach(a => { if (updated[a] !== 'complete') updated[a] = 'error'; });
        return updated;
      });
      setError(`Analysis failed: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fade-in">
      {/* Pipeline diagram */}
      <div className="glass" style={{ padding: 32, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600 }}>9-Agent Analysis Pipeline</h3>
          <button
            className="btn-primary"
            onClick={handleRunAnalysis}
            disabled={running || !session.collectionComplete}
          >
            {running ? 'Running Analysis...' : 'Run Analysis'}
          </button>
        </div>

        {/* Agent pipeline visualization */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', justifyContent: 'center' }}>
          {AGENT_ORDER.map((agentId, i) => (
            <React.Fragment key={agentId}>
              <AgentBubble
                agent={agentId}
                status={agentStatuses[agentId] || 'pending'}
                selectedModel={agentModels[agentId]}
                onModelChange={handleModelChange}
                onClick={() => {}}
              />
              {i < AGENT_ORDER.length - 1 && (
                <div style={{
                  width: 32, height: 2,
                  background: agentStatuses[AGENT_ORDER[i + 1]] === 'complete' || agentStatuses[agentId] === 'complete'
                    ? 'var(--teal)' : 'var(--border)',
                  transition: 'background 0.3s ease',
                }} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Pipeline log */}
      <div className="glass" style={{ padding: 20 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-muted)' }}>Pipeline Log</h4>
        <div style={{ maxHeight: 300, overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          {(session.pipelineLog || []).map((entry, i) => (
            <div key={i} style={{
              padding: '4px 0',
              color: entry.status === 'error' ? 'var(--red)' : entry.status === 'complete' ? 'var(--green)' : 'var(--text-muted)',
            }}>
              [{new Date(entry.ts).toLocaleTimeString()}] {AGENTS[entry.agent]?.name || entry.agent} — {entry.status}
              {entry.error && ` — ${entry.error}`}
            </div>
          ))}
          {(session.pipelineLog || []).length === 0 && (
            <p style={{ color: 'var(--text-muted)' }}>No pipeline activity yet. Click Run Analysis to start.</p>
          )}
        </div>
      </div>

      {error && <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13 }}>{error}</p>}
    </div>
  );
}
