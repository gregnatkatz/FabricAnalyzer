import React from 'react';

export default function ReportView({ session }) {
  const findings = session.findings || [];
  const vr = session.validationResults;

  const severityCounts = {
    CRITICAL: findings.filter(f => f.severity === 'CRITICAL').length,
    HIGH: findings.filter(f => f.severity === 'HIGH').length,
    MEDIUM: findings.filter(f => f.severity === 'MEDIUM').length,
  };

  const remediationResult = (session.agentResults || []).find(r => r.agentId === 'remediation');
  const artifacts = remediationResult?.artifacts || {};

  return (
    <div id="report-ready" style={{
      background: '#ffffff', color: '#1a1a1a', fontFamily: 'Arial, sans-serif',
      padding: '40px 60px', maxWidth: 900, margin: '0 auto', lineHeight: 1.6,
    }}>
      {/* Section 1: Cover */}
      <div style={{ textAlign: 'center', marginBottom: 40, paddingBottom: 30, borderBottom: '2px solid #e0e0e0' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: '#1a1a1a', marginBottom: 8 }}>
          Fabric Data Agent Analysis Report
        </h1>
        <p style={{ fontSize: 16, color: '#666' }}>{session.modelName || 'Unknown Model'}</p>
        <p style={{ fontSize: 14, color: '#888' }}>
          Domain: {session.domain || 'Unknown'} | Scan Date: {new Date().toLocaleDateString()}
        </p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginTop: 20 }}>
          <div><strong style={{ fontSize: 24 }}>{findings.length}</strong><br /><small>Findings</small></div>
          <div><strong style={{ fontSize: 24, color: '#d32f2f' }}>{severityCounts.CRITICAL}</strong><br /><small>Critical</small></div>
          <div><strong style={{ fontSize: 24, color: '#f57c00' }}>{severityCounts.HIGH}</strong><br /><small>High</small></div>
        </div>
      </div>

      {/* Section 2: Executive Summary */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Executive Summary</h2>
        <p>
          Analysis of {session.modelName || 'the data agent'} identified {findings.length} findings
          across {new Set(findings.map(f => f.agent_id)).size} analysis dimensions.
          {severityCounts.CRITICAL > 0 && ` ${severityCounts.CRITICAL} critical issues require immediate attention.`}
        </p>
      </div>

      {/* Section 3: Root Cause Ranking */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Root Cause Ranking</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
              <th style={{ padding: '8px 12px' }}>#</th>
              <th style={{ padding: '8px 12px' }}>Issue</th>
              <th style={{ padding: '8px 12px' }}>Severity</th>
              <th style={{ padding: '8px 12px' }}>Impact</th>
            </tr>
          </thead>
          <tbody>
            {findings.sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0)).map((f, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '6px 12px' }}>{i + 1}</td>
                <td style={{ padding: '6px 12px' }}>{f.issue}</td>
                <td style={{ padding: '6px 12px', color: f.severity === 'CRITICAL' ? '#d32f2f' : f.severity === 'HIGH' ? '#f57c00' : '#1976d2' }}>
                  {f.severity}
                </td>
                <td style={{ padding: '6px 12px' }}>{f.impact_ms ? `${f.impact_ms}ms` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Section 4: All Agent Findings */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>All Agent Findings</h2>
        {findings.map((f, i) => (
          <div key={i} style={{ marginBottom: 12, padding: '12px 16px', border: '1px solid #e0e0e0', borderRadius: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <strong>{f.issue}</strong>
              <span style={{ color: f.severity === 'CRITICAL' ? '#d32f2f' : f.severity === 'HIGH' ? '#f57c00' : '#1976d2' }}>
                {f.severity}
              </span>
            </div>
            {f.evidence && <p style={{ fontSize: 13, color: '#666', marginTop: 4 }}>Evidence: {f.evidence}</p>}
            {f.fix && <p style={{ fontSize: 13, color: '#2e7d32', marginTop: 4 }}>Fix: {f.fix}</p>}
          </div>
        ))}
      </div>

      {/* Section 5: Action Cards */}
      {artifacts.action_cards && (
        <div style={{ marginBottom: 30 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Prioritized Action Cards</h2>
          {artifacts.action_cards.map((card, i) => (
            <div key={i} style={{ marginBottom: 8, padding: '10px 14px', border: '1px solid #e0e0e0', borderRadius: 6 }}>
              <strong>{i + 1}. {card.title}</strong>
              <p style={{ fontSize: 13, color: '#666' }}>{card.description}</p>
              <small>Effort: {card.effort} | Owner: {card.owner} {card.reduction ? `| Est. reduction: ${card.reduction}` : ''}</small>
            </div>
          ))}
        </div>
      )}

      {/* Section 6: Artifacts */}
      {artifacts.optimized_instructions && (
        <div style={{ marginBottom: 30 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Paste-Ready Artifacts</h2>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>Optimized AI Instructions ({artifacts.optimized_instructions.length} chars)</h3>
          <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 6, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {artifacts.optimized_instructions}
          </pre>
        </div>
      )}

      {/* Section 7: Simulation */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>What-If Simulation</h2>
        <p style={{ fontSize: 13, color: '#666' }}>
          Math model and Monte Carlo simulation results are available in the interactive tool.
        </p>
      </div>

      {/* Section 8 & 9: Validation Evidence (if available) */}
      {vr && (
        <div style={{ marginBottom: 30 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Validation Evidence</h2>
          <div style={{ display: 'flex', gap: 40, marginBottom: 16 }}>
            <div><strong>Before:</strong> {((vr.baseline_avg_ms || 0) / 1000).toFixed(1)}s avg</div>
            <div><strong>After:</strong> {((vr.postfix_avg_ms || 0) / 1000).toFixed(1)}s avg</div>
            <div><strong>Reduction:</strong> {vr.reduction_pct || 0}%</div>
          </div>
          {vr.resolutions && (
            <>
              <h3 style={{ fontSize: 16, marginBottom: 8 }}>Finding Resolution Status</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
                    <th style={{ padding: '6px 12px' }}>Status</th>
                    <th style={{ padding: '6px 12px' }}>Finding</th>
                  </tr>
                </thead>
                <tbody>
                  {vr.resolutions.map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '6px 12px', color: r.status === 'RESOLVED' ? '#2e7d32' : '#f57c00' }}>{r.status}</td>
                      <td style={{ padding: '6px 12px' }}>{r.issue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* Section 10: Appendix */}
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Appendix</h2>
        <p style={{ fontSize: 13, color: '#666' }}>
          Domain: {session.domain || 'Unknown'}<br />
          Model: {session.modelName || 'Unknown'}<br />
          Traces analyzed: {(session.traces || []).length}<br />
          Generated by Fabric Data Agent Latency Analyzer v1.0
        </p>
      </div>
    </div>
  );
}
