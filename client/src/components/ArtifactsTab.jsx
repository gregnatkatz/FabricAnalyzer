import React, { useState, useMemo } from 'react';
import { exportPdf } from '../api/proxy';

export default function ArtifactsTab({ session }) {
  const [exporting, setExporting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [error, setError] = useState('');

  const agentResults = session.agentResults || [];
  const remediationResult = agentResults.find(r => r.agentId === 'remediation');
  const rawArtifacts = remediationResult?.artifacts || {};
  const findings = session.findings || [];

  // Generate artifacts from findings data when remediation artifacts are empty
  const artifacts = useMemo(() => {
    if (rawArtifacts.optimized_instructions || rawArtifacts.action_cards?.length) {
      return rawArtifacts;
    }
    if (findings.length === 0) return {};

    const sorted = [...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0));
    const actionCards = sorted.slice(0, 5).map((f, i) => ({
      title: f.issue || `Finding ${i + 1}`,
      description: f.fix || f.evidence || 'Review and remediate this finding',
      effort: f.severity === 'CRITICAL' ? 'High' : f.severity === 'HIGH' ? 'Medium' : 'Low',
      owner: 'Data Agent Admin',
      reduction: f.impact_ms ? `${(f.impact_ms / 1000).toFixed(1)}s` : null,
    }));

    const fixRecs = findings
      .filter(f => f.fix)
      .map(f => `- [${f.severity}] ${f.fix}`)
      .slice(0, 15);
    const optimizedInstructions = fixRecs.length > 0
      ? `# Recommended Optimizations for ${session.modelName || 'Data Agent'}\n# Generated from ${findings.length} findings\n\n${fixRecs.join('\n')}`
      : null;

    const tableRefs = new Set();
    findings.forEach(f => {
      const evidence = (f.evidence || '') + ' ' + (f.issue || '');
      const tableMatches = evidence.match(/\b(Dim\w+|Fact\w+|[A-Z][a-z]+[A-Z]\w+)\b/g);
      if (tableMatches) tableMatches.forEach(t => tableRefs.add(t));
    });
    const schemaScope = tableRefs.size > 0 ? [...tableRefs] : null;

    return {
      optimized_instructions: optimizedInstructions,
      action_cards: actionCards,
      schema_scope: schemaScope,
      verified_answers: rawArtifacts.verified_answers || null,
      dax_examples: rawArtifacts.dax_examples || null,
    };
  }, [rawArtifacts, findings, session.modelName]);

  const handlePreview = async () => {
    setPreviewing(true);
    setError('');
    try {
      const res = await fetch('/api/pdf/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(session),
      });
      const html = await res.text();
      setPreviewHtml(html);
    } catch (err) {
      setError(`Preview failed: ${err.message}`);
    } finally {
      setPreviewing(false);
    }
  };

  const handleExportPdf = async () => {
    try {
      setExporting(true);
      setError('');
      const blob = await exportPdf(session);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fabric-analyzer-${session.modelName || 'report'}-${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(`PDF export failed: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  if (!session.analysisComplete) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Run analysis first to see remediation artifacts.</p>
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Export PDF + Preview */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginBottom: 20 }}>
        <button className="btn-secondary" onClick={handlePreview} disabled={previewing}>
          {previewing ? 'Loading preview...' : 'Preview Report'}
        </button>
        <button className="btn-primary" onClick={handleExportPdf} disabled={exporting}>
          {exporting ? 'Generating PDF...' : 'Export PDF'}
        </button>
      </div>

      {/* Full-screen preview modal */}
      {previewHtml && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.85)',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 24px',
            background: '#0f1923',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}>
            <span style={{ fontSize: '13px', color: '#8899aa', fontFamily: 'monospace' }}>
              Report Preview — review before exporting
            </span>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={handleExportPdf}
                disabled={exporting}
                style={{ background: '#1a6fff', color: '#fff', border: 'none',
                         padding: '7px 18px', borderRadius: '5px', cursor: 'pointer',
                         fontSize: '12px', fontWeight: 600 }}
              >
                {exporting ? 'Generating...' : 'Export PDF'}
              </button>
              <button
                onClick={() => setPreviewHtml(null)}
                style={{ background: 'transparent', color: '#8899aa',
                         border: '1px solid rgba(255,255,255,0.15)',
                         padding: '7px 14px', borderRadius: '5px', cursor: 'pointer',
                         fontSize: '12px' }}
              >
                Close
              </button>
            </div>
          </div>
          <iframe
            srcDoc={previewHtml}
            style={{ flex: 1, border: 'none', background: '#fff' }}
            title="Report Preview"
            sandbox="allow-same-origin allow-scripts"
          />
        </div>
      )}

      {/* Summary card */}
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Remediation Summary</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <div className="glass metric-card">
            <div className="label">Total Findings</div>
            <div className="value" style={{ color: 'var(--teal)' }}>{findings.length}</div>
          </div>
          <div className="glass metric-card">
            <div className="label">Critical</div>
            <div className="value" style={{ color: 'var(--red)' }}>
              {findings.filter(f => f.severity === 'CRITICAL').length}
            </div>
          </div>
          <div className="glass metric-card">
            <div className="label">High</div>
            <div className="value" style={{ color: '#f59e0b' }}>
              {findings.filter(f => f.severity === 'HIGH').length}
            </div>
          </div>
          <div className="glass metric-card">
            <div className="label">Total Impact</div>
            <div className="value" style={{ color: 'var(--teal)' }}>
              {(findings.reduce((s, f) => s + (f.impact_ms || 0), 0) / 1000).toFixed(1)}s
            </div>
          </div>
        </div>
      </div>

      {/* Optimized Instructions */}
      {artifacts.optimized_instructions && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h4 style={{ fontSize: 14, fontWeight: 600 }}>Optimized AI Instructions</h4>
            <button className="btn-secondary" style={{ fontSize: 11, padding: '4px 10px' }}
              onClick={() => navigator.clipboard.writeText(artifacts.optimized_instructions)}>
              Copy
            </button>
          </div>
          <pre style={{
            background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8,
            fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflowY: 'auto',
          }}>
            {artifacts.optimized_instructions}
          </pre>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
            {artifacts.optimized_instructions.length} / 4,000 chars — paste into Prep for AI Instructions
          </p>
        </div>
      )}

      {/* Verified Answer DAX */}
      {artifacts.verified_answers && artifacts.verified_answers.length > 0 && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Verified Answer DAX Patterns</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {artifacts.verified_answers.map((va, i) => (
              <div key={i} className="glass" style={{ padding: 14 }}>
                <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>{va.question}</p>
                <pre style={{
                  background: 'rgba(0,0,0,0.3)', padding: 12, borderRadius: 6,
                  fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--amber)',
                  whiteSpace: 'pre-wrap',
                }}>
                  {va.dax}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Schema Scope */}
      {artifacts.schema_scope && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>AI Data Schema — Tables to Include</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {artifacts.schema_scope.map((table, i) => (
              <span key={i} style={{
                padding: '4px 10px', background: 'rgba(0, 232, 202, 0.1)',
                border: '1px solid rgba(0, 232, 202, 0.3)', borderRadius: 6,
                fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--teal)',
              }}>
                {table}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* DAX Examples */}
      {artifacts.dax_examples && artifacts.dax_examples.length > 0 && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>DAX Few-Shot Examples (with TOP limits)</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {artifacts.dax_examples.map((ex, i) => (
              <div key={i} className="glass" style={{ padding: 14 }}>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>{ex.description}</p>
                <pre style={{
                  background: 'rgba(0,0,0,0.3)', padding: 10, borderRadius: 6,
                  fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--amber)',
                  whiteSpace: 'pre-wrap',
                }}>
                  {ex.dax}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Cards */}
      {artifacts.action_cards && artifacts.action_cards.length > 0 && (
        <div className="glass" style={{ padding: 20 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Prioritized Action Cards</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {artifacts.action_cards.map((card, i) => (
              <div key={i} className="glass" style={{ padding: 14, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <span style={{
                  width: 28, height: 28, borderRadius: '50%', background: 'rgba(0, 232, 202, 0.1)',
                  border: '1px solid var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 700, color: 'var(--teal)', flexShrink: 0,
                }}>
                  {i + 1}
                </span>
                <div>
                  <p style={{ fontSize: 14, fontWeight: 500 }}>{card.title}</p>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{card.description}</p>
                  <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                    <span>Effort: {card.effort}</span>
                    <span>Owner: {card.owner}</span>
                    {card.reduction && <span style={{ color: 'var(--green)' }}>Est. reduction: {card.reduction}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Findings Detail Table */}
      {findings.length > 0 && (
        <div className="glass" style={{ padding: 20, marginTop: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>All Findings Detail</h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>#</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>Severity</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>Agent</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>Issue</th>
                  <th style={{ textAlign: 'right', padding: '8px 12px' }}>Impact</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px' }}>Fix</th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f, i) => {
                  const sevColor = f.severity === 'CRITICAL' ? 'var(--red)' : f.severity === 'HIGH' ? '#f59e0b' : f.severity === 'MEDIUM' ? 'var(--teal)' : 'var(--text-muted)';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ padding: '6px 12px', color: 'var(--text-muted)' }}>{i + 1}</td>
                      <td style={{ padding: '6px 12px' }}>
                        <span style={{ color: sevColor, fontWeight: 600 }}>{f.severity}</span>
                      </td>
                      <td style={{ padding: '6px 12px', color: 'var(--text-muted)' }}>{f.agent_id || f.agentId || '-'}</td>
                      <td style={{ padding: '6px 12px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.issue}</td>
                      <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--red)' }}>
                        {f.impact_ms ? `${(f.impact_ms / 1000).toFixed(1)}s` : '-'}
                      </td>
                      <td style={{ padding: '6px 12px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>{f.fix || '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {error && <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13 }}>{error}</p>}
    </div>
  );
}
