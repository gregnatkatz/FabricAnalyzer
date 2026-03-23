import React, { useState } from 'react';
import { FIXES, FIX_KEYS } from '../constants/fixes';
import { startValidation } from '../api/proxy';

const STATES = { LOCKED: 'LOCKED', READY: 'READY', RUNNING: 'RUNNING', COMPLETE: 'COMPLETE', STALE: 'STALE' };

export default function ValidationTab({ session, updateSession }) {
  // Auto-select all fixes by default
  const [selectedFixes, setSelectedFixes] = useState(() => FIX_KEYS.filter(k => k !== 'physician_gov'));
  const [progress, setProgress] = useState(null);
  const [validationError, setValidationError] = useState(null);
  const [validationState, setValidationState] = useState(
    !session.collectionComplete ? STATES.LOCKED
      : session.validationComplete ? STATES.COMPLETE
      : STATES.READY
  );

  const toggleFix = (fixKey) => {
    setSelectedFixes(prev =>
      prev.includes(fixKey) ? prev.filter(k => k !== fixKey) : [...prev, fixKey]
    );
    if (validationState === STATES.COMPLETE) setValidationState(STATES.STALE);
  };

  const handleRunValidation = () => {
    if (selectedFixes.length === 0) return;
    setValidationState(STATES.RUNNING);
    setProgress({ current: 0, total: 20, phase: 'baseline' });

    setValidationError(null);
    startValidation(
      session.sessionId,
      selectedFixes,
      (data) => {
        // Handle both 'progress' and 'phase' event types from fix_applicator.py
        const phaseName = data.name || data.phase || 'running';
        const phaseNum = data.phase || 0;
        setProgress({ current: phaseNum, total: 4, phase: phaseName });
      },
      (data) => {
        // Map fix_applicator.py output to UI expected format
        const mapped = {
          baseline_avg_ms: data.baseline_avg || 0,
          postfix_avg_ms: data.postfix_avg || 0,
          reduction_pct: data.reduction_pct || 0,
          questions: (data.per_question || []).map(q => ({
            question: q.question || '',
            baseline_ms: q.baseline_ms || q.before || 0,
            postfix_ms: q.postfix_ms || q.after || 0,
            delta_ms: (q.baseline_ms || q.before || 0) - (q.postfix_ms || q.after || 0),
          })),
          resolutions: data.resolutions || [],
        };
        updateSession({
          validationResults: mapped,
          validationComplete: true,
        });
        setValidationState(STATES.COMPLETE);
        setProgress(null);
      },
      (err) => {
        console.error('Validation error:', err);
        setValidationError(err?.message || 'Validation failed — check server logs');
        setValidationState(STATES.READY);
        setProgress(null);
      }
    );
  };

  const vr = session.validationResults;

  if (validationState === STATES.LOCKED) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ fontSize: 18, marginBottom: 8 }}>🔒</p>
        <p style={{ color: 'var(--text-muted)' }}>Complete Collect Data first</p>
      </div>
    );
  }

  return (
    <div className="fade-in">
      {validationState === STATES.STALE && (
        <div style={{ padding: '10px 16px', background: 'rgba(245, 166, 35, 0.1)', border: '1px solid rgba(245, 166, 35, 0.3)', borderRadius: 8, marginBottom: 16, fontSize: 13, color: 'var(--amber)' }}>
          Results may be outdated — re-run validation
        </div>
      )}

      {/* Fix selector */}
      <div className="glass" style={{ padding: 20, marginBottom: 20 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Select Fixes to Validate</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
          {FIX_KEYS.filter(k => k !== 'physician_gov').map(fixKey => (
            <label key={fixKey} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
              background: selectedFixes.includes(fixKey) ? 'rgba(0, 232, 202, 0.05)' : 'transparent',
              border: `1px solid ${selectedFixes.includes(fixKey) ? 'var(--teal)' : 'var(--border)'}`,
              borderRadius: 8, cursor: 'pointer', fontSize: 13,
            }}>
              <input type="checkbox" checked={selectedFixes.includes(fixKey)}
                onChange={() => toggleFix(fixKey)} style={{ accentColor: 'var(--teal)' }} />
              {FIXES[fixKey].label}
            </label>
          ))}
        </div>
        <button className="btn-primary" onClick={handleRunValidation}
          disabled={selectedFixes.length === 0 || validationState === STATES.RUNNING}
          style={{ marginTop: 16, width: '100%', justifyContent: 'center' }}>
          {validationState === STATES.RUNNING ? 'Running Validation...' : 'Run Validation'}
        </button>
      </div>

      {/* Progress */}
      {progress && (
        <div className="glass" style={{ padding: 20, marginBottom: 20 }}>
          <p style={{ fontSize: 13, color: 'var(--teal)', marginBottom: 8 }}>
            Running question {progress.current} of {progress.total} ({progress.phase})...
          </p>
          <div className="progress-bar">
            <div className="fill" style={{ width: `${(progress.current / progress.total) * 100}%` }} />
          </div>
        </div>
      )}

      {/* Results */}
      {vr && validationState !== STATES.LOCKED && (
        <>
          {/* Summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
            <div className="glass metric-card">
              <div className="label">Before</div>
              <div className="value" style={{ color: 'var(--red)' }}>{((vr.baseline_avg_ms || 0) / 1000).toFixed(1)}s</div>
              <div className="label">avg latency</div>
            </div>
            <div className="glass metric-card">
              <div className="label">After</div>
              <div className="value" style={{ color: 'var(--green)' }}>{((vr.postfix_avg_ms || 0) / 1000).toFixed(1)}s</div>
              <div className="label">avg latency</div>
            </div>
            <div className="glass metric-card">
              <div className="label">Reduction</div>
              <div className="value" style={{ color: 'var(--teal)' }}>{vr.reduction_pct || 0}%</div>
              <div className="label">improvement</div>
            </div>
          </div>

          {/* Per-question table */}
          {vr.questions && (
            <div className="glass" style={{ padding: 20, marginBottom: 20 }}>
              <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Per-Question Breakdown</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                  <thead>
                    <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                      <th style={{ textAlign: 'left', padding: '8px 12px' }}>#</th>
                      <th style={{ textAlign: 'left', padding: '8px 12px' }}>Question</th>
                      <th style={{ textAlign: 'right', padding: '8px 12px' }}>Before</th>
                      <th style={{ textAlign: 'right', padding: '8px 12px' }}>After</th>
                      <th style={{ textAlign: 'right', padding: '8px 12px' }}>Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vr.questions.map((q, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                        <td style={{ padding: '6px 12px', color: 'var(--text-muted)' }}>{i + 1}</td>
                        <td style={{ padding: '6px 12px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.question}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right' }}>{(q.baseline_ms / 1000).toFixed(1)}s</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--green)' }}>{(q.postfix_ms / 1000).toFixed(1)}s</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', color: q.delta_ms > 0 ? 'var(--green)' : 'var(--red)' }}>
                          {q.delta_ms > 0 ? '-' : '+'}{Math.abs(q.delta_ms)}ms
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Resolution status */}
          {vr.resolutions && (
            <div className="glass" style={{ padding: 20 }}>
              <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Finding Resolution Status</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {vr.resolutions.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, padding: '6px 0' }}>
                    <span className={`badge badge-${r.status === 'RESOLVED' ? 'low' : r.status === 'PARTIAL' ? 'medium' : r.status === 'NEW ISSUE' ? 'critical' : 'high'}`}
                      style={{ minWidth: 100, justifyContent: 'center' }}>
                      {r.status}
                    </span>
                    <span>{r.issue}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {validationError && (
        <div className="glass" style={{ padding: 16, marginTop: 16, border: '1px solid var(--red)', background: 'rgba(239, 68, 68, 0.05)' }}>
          <p style={{ color: 'var(--red)', fontSize: 13 }}>{validationError}</p>
        </div>
      )}
    </div>
  );
}
