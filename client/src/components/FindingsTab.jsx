import React, { useState } from 'react';
import { AGENTS } from '../constants/agentMeta';

function FindingCard({ finding }) {
  const [expanded, setExpanded] = useState(false);
  const agent = AGENTS[finding.agent_id] || {};

  return (
    <div className="glass glass-hover" style={{ padding: '16px 20px', cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <span className={`badge badge-${finding.severity?.toLowerCase() || 'medium'}`}>
          {finding.severity || 'MEDIUM'}
        </span>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{finding.issue}</p>
          <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-muted)' }}>
            <span style={{ color: agent.accent }}>{agent.glyph} {agent.name || finding.agent_id}</span>
            {finding.impact_ms > 0 && <span>Impact: {finding.impact_ms}ms</span>}
            {finding.resolution_status && (
              <span style={{ color: finding.resolution_status === 'RESOLVED' ? 'var(--green)' : 'var(--amber)' }}>
                {finding.resolution_status}
              </span>
            )}
          </div>
        </div>
      </div>
      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 13 }}>
          {finding.evidence && <p style={{ marginBottom: 8 }}><strong>Evidence:</strong> {finding.evidence}</p>}
          {finding.fix && <p style={{ color: 'var(--green)' }}><strong>Fix:</strong> {finding.fix}</p>}
        </div>
      )}
    </div>
  );
}

export default function FindingsTab({ session }) {
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [filterAgent, setFilterAgent] = useState('all');
  const findings = session.findings || [];

  const filtered = findings.filter(f =>
    (filterSeverity === 'all' || f.severity === filterSeverity) &&
    (filterAgent === 'all' || f.agent_id === filterAgent)
  );

  const severityCounts = {
    CRITICAL: findings.filter(f => f.severity === 'CRITICAL').length,
    HIGH: findings.filter(f => f.severity === 'HIGH').length,
    MEDIUM: findings.filter(f => f.severity === 'MEDIUM').length,
    LOW: findings.filter(f => f.severity === 'LOW').length,
  };

  if (!session.analysisComplete) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Run the analysis pipeline first to see findings.</p>
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {Object.entries(severityCounts).map(([sev, count]) => (
          <div key={sev} className="glass metric-card" onClick={() => setFilterSeverity(filterSeverity === sev ? 'all' : sev)}
            style={{ cursor: 'pointer', border: filterSeverity === sev ? `1px solid var(--${sev === 'CRITICAL' ? 'red' : sev === 'HIGH' ? 'amber' : sev === 'MEDIUM' ? 'blue' : 'green'})` : undefined }}>
            <div className="value" style={{ color: `var(--${sev === 'CRITICAL' ? 'red' : sev === 'HIGH' ? 'amber' : sev === 'MEDIUM' ? 'blue' : 'green'})` }}>
              {count}
            </div>
            <div className="label">{sev}</div>
          </div>
        ))}
      </div>

      {/* Agent filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <button className={`tab-btn ${filterAgent === 'all' ? 'active' : ''}`}
          onClick={() => setFilterAgent('all')} style={{ fontSize: 11, padding: '4px 10px' }}>
          All ({findings.length})
        </button>
        {Object.keys(AGENTS).filter(a => findings.some(f => f.agent_id === a)).map(agentId => (
          <button key={agentId} className={`tab-btn ${filterAgent === agentId ? 'active' : ''}`}
            onClick={() => setFilterAgent(filterAgent === agentId ? 'all' : agentId)}
            style={{ fontSize: 11, padding: '4px 10px' }}>
            {AGENTS[agentId].glyph} {findings.filter(f => f.agent_id === agentId).length}
          </button>
        ))}
      </div>

      {/* Findings list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.sort((a, b) => {
          const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
          return (order[a.severity] || 4) - (order[b.severity] || 4);
        }).map((finding, i) => (
          <FindingCard key={finding.finding_id || i} finding={finding} />
        ))}
        {filtered.length === 0 && (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 32 }}>No findings match filters.</p>
        )}
      </div>
    </div>
  );
}
