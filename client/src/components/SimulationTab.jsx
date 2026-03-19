import React, { useState, useMemo } from 'react';
import { simulate } from '../simulation/mathModel';
import { FIXES, FIX_KEYS } from '../constants/fixes';

function MonteCarloBar({ p10, p50, p90, maxMs }) {
  const scale = (ms) => Math.max(0, Math.min(100, (ms / maxMs) * 100));
  return (
    <div style={{ position: 'relative', height: 8, background: 'rgba(255,255,255,0.05)', borderRadius: 4, marginTop: 4 }}>
      <div style={{
        position: 'absolute', left: `${scale(p10)}%`, right: `${100 - scale(p90)}%`,
        height: '100%', background: 'rgba(0, 232, 202, 0.2)', borderRadius: 4,
      }} />
      <div style={{
        position: 'absolute', left: `${scale(p50)}%`, top: -2, width: 3, height: 12,
        background: 'var(--teal)', borderRadius: 2, transform: 'translateX(-50%)',
      }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 10 }}>
        <span>P10: {(p10 / 1000).toFixed(1)}s</span>
        <span>P50: {(p50 / 1000).toFixed(1)}s</span>
        <span>P90: {(p90 / 1000).toFixed(1)}s</span>
      </div>
    </div>
  );
}

export default function SimulationTab({ session, updateSession }) {
  const [activeFixes, setActiveFixes] = useState([]);
  const traces = session.traces || [];
  const mc = session.monteCarloResults;

  // Pure synchronous simulation — updates within 100ms
  const simResult = useMemo(() => simulate(traces, activeFixes), [traces, activeFixes]);

  const toggleFix = (fixKey) => {
    setActiveFixes(prev =>
      prev.includes(fixKey)
        ? prev.filter(k => k !== fixKey)
        : [...prev, fixKey]
    );
  };

  if (!session.collectionComplete) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Collect data first to enable simulation.</p>
      </div>
    );
  }

  const maxMs = Math.max(simResult.baselineOutlierMs || 30000, 45000);

  return (
    <div className="fade-in">
      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <div className="glass metric-card">
          <div className="value" style={{ color: simResult.avgMs < simResult.baselineAvgMs ? 'var(--green)' : 'var(--text)' }}>
            {(simResult.avgMs / 1000).toFixed(1)}s
          </div>
          <div className="label">Projected Avg ({simResult.reductionPct > 0 ? `-${simResult.reductionPct}%` : 'baseline'})</div>
        </div>
        <div className="glass metric-card">
          <div className="value" style={{ color: simResult.outlierMs > 45000 ? 'var(--red)' : simResult.outlierMs > 20000 ? 'var(--amber)' : 'var(--green)' }}>
            {(simResult.outlierMs / 1000).toFixed(1)}s
          </div>
          <div className="label">Projected Outlier</div>
        </div>
        <div className="glass metric-card">
          <div className="value" style={{ color: simResult.passRate >= 90 ? 'var(--green)' : simResult.passRate >= 70 ? 'var(--amber)' : 'var(--red)' }}>
            {simResult.passRate}%
          </div>
          <div className="label">Pass Rate (&lt;20s)</div>
        </div>
      </div>

      {/* Fix toggles */}
      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Fix Toggles</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {FIX_KEYS.map(fixKey => {
            const fix = FIXES[fixKey];
            const isActive = activeFixes.includes(fixKey);
            const perFix = simResult.perFix[fixKey];
            const mcFix = mc?.fixes?.[fixKey];

            return (
              <div key={fixKey} className="glass" style={{
                padding: '14px 18px',
                border: isActive ? '1px solid var(--teal)' : '1px solid var(--border)',
                background: isActive ? 'rgba(0, 232, 202, 0.03)' : undefined,
                cursor: fix.key === 'physician_gov' ? 'not-allowed' : 'pointer',
                opacity: fix.key === 'physician_gov' ? 0.6 : 1,
              }}
                onClick={() => fix.key !== 'physician_gov' && toggleFix(fixKey)}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{fix.label}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>{fix.description}</span>
                  </div>
                  <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                    {perFix && perFix.reductionMs > 0 ? (
                      <span style={{ color: 'var(--green)' }}>-{(perFix.reductionMs / 1000).toFixed(1)}s ({perFix.reductionPct}%)</span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </div>
                </div>

                {/* Monte Carlo distribution bars */}
                {mcFix && isActive && (
                  <div style={{ marginTop: 8 }}>
                    <MonteCarloBar p10={mcFix.p10} p50={mcFix.p50} p90={mcFix.p90} maxMs={maxMs} />
                    <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                      <span>Confidence: <span style={{
                        color: mcFix.confidence === 'HIGH' ? 'var(--green)' : mcFix.confidence === 'MEDIUM' ? 'var(--amber)' : 'var(--text-muted)',
                        fontWeight: 600,
                      }}>{mcFix.confidence || 'N/A'}</span></span>
                      {mcFix.variance !== undefined && <span>Variance: {mcFix.variance.toFixed(1)}ms</span>}
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>Effort: {fix.effort}</span>
                  <span>Owner: {fix.owner}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
