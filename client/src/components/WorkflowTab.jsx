import React, { useState, useEffect, useRef } from 'react';
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
  const [elapsed, setElapsed] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [liveLog, setLiveLog] = useState([]);
  const [backendLog, setBackendLog] = useState([]);
  const pollRef = useRef(null);
  const lastTsRef = useRef(0);
  const logEndRef = useRef(null);

  // Poll backend for verbose pipeline logs while running
  useEffect(() => {
    if (running) {
      lastTsRef.current = 0;
      setBackendLog([]);
      pollRef.current = setInterval(async () => {
        try {
          const resp = await fetch(`/api/pipeline-log?since=${lastTsRef.current}`);
          const data = await resp.json();
          if (data.events && data.events.length > 0) {
            setBackendLog(prev => [...prev, ...data.events]);
            lastTsRef.current = data.events[data.events.length - 1].ts;
          }
        } catch (e) { /* ignore polling errors */ }
      }, 1500);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [running]);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [liveLog, backendLog]);

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

    // Elapsed timer
    setElapsed(0);
    setCompletedCount(0);
    const logEntries = [{ agent: 'pipeline', status: 'started', ts: Date.now(), message: `Starting ${AGENT_ORDER.length}-agent pipeline...` }];
    setLiveLog([...logEntries]);
    const timerInterval = setInterval(() => setElapsed(prev => prev + 1), 1000);

    // Animate agents as running sequentially for visual feedback
    let animIdx = 0;
    const animInterval = setInterval(() => {
      if (animIdx < AGENT_ORDER.length) {
        const agentId = AGENT_ORDER[animIdx];
        const agentName = AGENTS[agentId]?.name || agentId;
        const modelName = agentModels[agentId] || 'default';
        setAgentStatuses(prev => ({ ...prev, [agentId]: 'running' }));
        logEntries.push({ agent: agentId, status: 'running', ts: Date.now(), message: `${agentName} started (${modelName})` });
        setLiveLog([...logEntries]);
        if (animIdx > 0) {
          const prevAgent = AGENT_ORDER[animIdx - 1];
          const prevName = AGENTS[prevAgent]?.name || prevAgent;
          setAgentStatuses(prev => ({ ...prev, [prevAgent]: 'complete' }));
          setCompletedCount(animIdx);
          logEntries.push({ agent: prevAgent, status: 'complete', ts: Date.now(), message: `${prevName} complete` });
          setLiveLog([...logEntries]);
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
      clearInterval(timerInterval);

      // Mark all agents as complete
      setCompletedCount(AGENT_ORDER.length);
      const completeStatuses = {};
      AGENT_ORDER.forEach(a => { completeStatuses[a] = 'complete'; });
      setAgentStatuses(completeStatuses);

      // Build final log with timing and finding counts
      const findingCount = (result.findings || []).length;
      const monteCarloIterations = result.monte_carlo?.iterations || 0;
      logEntries.push({ agent: 'pipeline', status: 'complete', ts: Date.now(), message: `Pipeline complete — ${findingCount} findings, ${monteCarloIterations} MC iterations` });
      AGENT_ORDER.forEach(a => {
        const existing = logEntries.find(e => e.agent === a && e.status === 'complete');
        if (!existing) logEntries.push({ agent: a, status: 'complete', ts: Date.now() });
      });
      setLiveLog([...logEntries]);

      const completeLogs = logEntries.filter(e => e.agent !== 'pipeline');
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
      clearInterval(timerInterval);
      logEntries.push({ agent: 'pipeline', status: 'error', ts: Date.now(), message: `Pipeline error: ${err.message}` });
      setLiveLog([...logEntries]);
      // Mark remaining as error
      setAgentStatuses(prev => {
        const updated = { ...prev };
        AGENT_ORDER.forEach(a => { if (updated[a] !== 'complete') updated[a] = 'error'; });
        return updated;
      });
      setError(`Analysis failed: ${err.message}`);

      // Try to salvage partial results from the pipeline-log API
      // The backend may have partial findings even if the HTTP call failed
      try {
        const partialResp = await fetch('/api/pipeline-log?since=0');
        const partialData = await partialResp.json();
        if (partialData.events && partialData.events.length > 0) {
          const findingLines = partialData.events.filter(e => e.line && e.line.includes('findings'));
          if (findingLines.length > 0) {
            logEntries.push({ agent: 'pipeline', status: 'info', ts: Date.now(), message: `Pipeline produced partial results (${findingLines.length} agent outputs). Check Findings tab.` });
            setLiveLog([...logEntries]);
          }
        }
      } catch { /* ignore partial result fetch errors */ }

      // Also try to fetch whatever the pipeline returned as partial JSON
      try {
        const salvageResp = await fetch('/api/analyze-result');
        if (salvageResp.ok) {
          const partial = await salvageResp.json();
          if (partial.findings && partial.findings.length > 0) {
            updateSession({
              findings: partial.findings,
              analysisComplete: true,
              ...(partial.monte_carlo ? { monteCarloResults: partial.monte_carlo } : {}),
              ...(partial.synthesis ? { synthesisResults: partial.synthesis } : {}),
              ...(partial.remediation ? { remediationResults: partial.remediation } : {}),
            });
          }
        }
      } catch { /* ignore salvage errors */ }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fade-in">
      {/* Pipeline diagram */}
      <div className="glass" style={{ padding: 32, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600 }}>{AGENT_ORDER.length}-Agent Analysis Pipeline</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {running && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}>
                <div style={{
                  width: 120, height: 6, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${Math.round((completedCount / AGENT_ORDER.length) * 100)}%`,
                    height: '100%', background: 'var(--teal)', borderRadius: 3,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
                <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {completedCount}/{AGENT_ORDER.length} agents &middot; {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}
                </span>
              </div>
            )}
            <button
              className="btn-primary"
              onClick={handleRunAnalysis}
              disabled={running || !session.collectionComplete}
            >
              {running ? 'Running Analysis...' : 'Run Analysis'}
            </button>
          </div>
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
        <div style={{ maxHeight: 500, overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.6 }}>
          {/* Frontend animation log */}
          {(liveLog.length > 0 ? liveLog : (session.pipelineLog || [])).map((entry, i) => {
            const isError = entry.status === 'error';
            const isComplete = entry.status === 'complete';
            const isRunning = entry.status === 'running';
            const isPipeline = entry.agent === 'pipeline';
            return (
              <div key={`fe-${i}`} style={{
                padding: '3px 0',
                borderBottom: '1px solid rgba(255,255,255,0.03)',
                color: isError ? 'var(--red)' : isComplete ? 'var(--green)' : isRunning ? 'var(--teal)' : 'var(--text-muted)',
                fontWeight: isPipeline ? 600 : 400,
              }}>
                <span style={{ opacity: 0.6 }}>[{new Date(entry.ts).toLocaleTimeString()}]</span>{' '}
                {entry.message || `${AGENTS[entry.agent]?.name || entry.agent} — ${entry.status}`}
                {entry.error && <span style={{ color: 'var(--red)' }}> — {entry.error}</span>}
              </div>
            );
          })}
          {/* Verbose backend log (real-time from pipeline stderr) */}
          {backendLog.map((evt, i) => {
            const line = evt.line || '';
            const isLLM = line.includes('LLM call') || line.includes('Prompt size');
            const isAgent = line.includes('Running Agent');
            const isComplete = line.includes('complete') || line.includes('findings');
            const isError = line.includes('failed') || line.includes('error') || line.includes('Error');
            const isExit = line.includes('[EXIT]');
            const color = isError ? 'var(--red)'
              : isExit ? (line.includes('successfully') ? 'var(--green)' : 'var(--red)')
              : isAgent ? 'var(--teal)'
              : isLLM ? '#c084fc'
              : isComplete ? 'var(--green)'
              : 'var(--text-muted)';
            return (
              <div key={`be-${i}`} style={{
                padding: '2px 0 2px 12px',
                borderLeft: '2px solid rgba(255,255,255,0.06)',
                color,
                fontSize: 10.5,
                opacity: isLLM || isAgent || isComplete || isError || isExit ? 1 : 0.7,
              }}>
                <span style={{ opacity: 0.5 }}>[{new Date(evt.ts).toLocaleTimeString()}]</span>{' '}
                {line}
              </div>
            );
          })}
          {liveLog.length === 0 && backendLog.length === 0 && (session.pipelineLog || []).length === 0 && (
            <p style={{ color: 'var(--text-muted)' }}>No pipeline activity yet. Click Run Analysis to start.</p>
          )}
          <div ref={logEndRef} />
        </div>
      </div>

      {error && <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13 }}>{error}</p>}
    </div>
  );
}
