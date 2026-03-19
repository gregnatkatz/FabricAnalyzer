import React, { useState } from 'react';
import { exportPdf } from '../api/proxy';

export default function ArtifactsTab({ session }) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const agentResults = session.agentResults || [];
  const remediationResult = agentResults.find(r => r.agentId === 'remediation');
  const artifacts = remediationResult?.artifacts || {};

  const handleExportPdf = async () => {
    try {
      setExporting(true);
      setError('');
      const blob = await exportPdf(session.sessionId);
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
      {/* Export PDF */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <button className="btn-primary" onClick={handleExportPdf} disabled={exporting}>
          {exporting ? 'Generating PDF...' : 'Export PDF'}
        </button>
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

      {error && <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13 }}>{error}</p>}
    </div>
  );
}
