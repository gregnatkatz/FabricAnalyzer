import React, { useState, useMemo, useEffect } from 'react';
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
  // Auto-enable all actionable fixes on load so the user immediately sees projected improvements
  const actionableFixes = FIX_KEYS.filter(k => FIXES[k].key !== 'physician_gov');
  const [activeFixes, setActiveFixes] = useState(actionableFixes);
  const [initialized, setInitialized] = useState(false);

  // Re-initialize when session changes (new collection)
  useEffect(() => {
    if (session.collectionComplete && !initialized) {
      setActiveFixes(actionableFixes);
      setInitialized(true);
    }
  }, [session.collectionComplete]);
  const traces = session.traces || [];
  const mc = session.monteCarloResults;
  const cuMetrics = session.cuMetrics || null;

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
  const totalFixReduction = Object.values(simResult.perFix).reduce((s, pf) => s + (pf.reductionMs || 0), 0);

  return (
    <div className="fade-in">
      {/* Narrative Simulation Overview */}
      <div className="glass" style={{ padding: '20px 24px', marginBottom: 20, borderLeft: '3px solid var(--teal)' }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 10, color: 'var(--teal)' }}>Monte Carlo Simulation Overview</h3>
        <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 8 }}>
          This simulation models the projected impact of each recommended fix on query latency using a <strong>pure deterministic math model</strong> calibrated
          against Microsoft's published Fabric Data Agent performance benchmarks. Each fix applies reduction factors to the three latency phases:
          Schema Resolution, DAX Generation, and Execution. Factors are capped at 78% (schema), 82% (DAX), and 65% (execution) to prevent
          over-optimistic projections.
        </p>
        <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 8 }}>
          <strong>Current baseline:</strong> Average latency is <strong style={{ color: 'var(--red)' }}>{(simResult.baselineAvgMs / 1000).toFixed(1)}s</strong> with
          a <strong>{simResult.baselinePassRate}%</strong> pass rate (queries completing under 20s). The worst-case outlier
          is <strong style={{ color: 'var(--red)' }}>{(simResult.baselineOutlierMs / 1000).toFixed(1)}s</strong>.
          {activeFixes.length === 0
            ? ' Toggle fixes below to see projected improvements. Each fix shows its individual contribution to latency reduction.'
            : ` With ${activeFixes.length} fix${activeFixes.length > 1 ? 'es' : ''} applied, the projected average drops to ${(simResult.avgMs / 1000).toFixed(1)}s (-${simResult.reductionPct}%) and the pass rate improves to ${simResult.passRate}%.`
          }
        </p>
        <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-muted)', marginBottom: 0 }}>
          Note: Fixes are cumulative but subject to diminishing returns. The simulation accounts for compound reduction factors with a floor
          of 1,600ms per trace (minimum achievable latency for any Fabric Data Agent query).
        </p>
      </div>

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

      {/* Before vs After Comparison Chart — always visible */}
      {
        <div className="glass" style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Before vs After Comparison</h3>
          <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', height: 180 }}>
            {/* Baseline bar */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
                {(simResult.baselineAvgMs / 1000).toFixed(1)}s
              </span>
              <div style={{
                width: '100%', maxWidth: 80,
                height: `${Math.max(20, (simResult.baselineAvgMs / maxMs) * 140)}px`,
                background: 'linear-gradient(to top, rgba(239,68,68,0.6), rgba(245,158,11,0.4))',
                borderRadius: '6px 6px 0 0',
                border: '1px solid rgba(239,68,68,0.3)',
              }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>Before</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Avg Latency</span>
            </div>

            {/* Arrow */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingBottom: 32 }}>
              <span style={{ fontSize: 20, color: 'var(--green)' }}>&rarr;</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
                -{simResult.reductionPct}%
              </span>
            </div>

            {/* Projected bar */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--green)', marginBottom: 8 }}>
                {(simResult.avgMs / 1000).toFixed(1)}s
              </span>
              <div style={{
                width: '100%', maxWidth: 80,
                height: `${Math.max(20, (simResult.avgMs / maxMs) * 140)}px`,
                background: 'linear-gradient(to top, rgba(0,232,202,0.6), rgba(0,232,202,0.2))',
                borderRadius: '6px 6px 0 0',
                border: '1px solid rgba(0,232,202,0.3)',
              }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>After</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Projected</span>
            </div>

            {/* Divider */}
            <div style={{ width: 1, height: 140, background: 'var(--border)', alignSelf: 'center' }} />

            {/* Pass Rate Before */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
                {simResult.baselinePassRate}%
              </span>
              <div style={{
                width: '100%', maxWidth: 80,
                height: `${Math.max(20, (simResult.baselinePassRate / 100) * 140)}px`,
                background: simResult.baselinePassRate >= 70 ? 'rgba(245,158,11,0.4)' : 'rgba(239,68,68,0.4)',
                borderRadius: '6px 6px 0 0',
                border: `1px solid ${simResult.baselinePassRate >= 70 ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.3)'}`,
              }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>Before</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Pass Rate</span>
            </div>

            {/* Arrow */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingBottom: 32 }}>
              <span style={{ fontSize: 20, color: 'var(--green)' }}>&rarr;</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
                +{simResult.passRate - simResult.baselinePassRate}%
              </span>
            </div>

            {/* Pass Rate After */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--green)', marginBottom: 8 }}>
                {simResult.passRate}%
              </span>
              <div style={{
                width: '100%', maxWidth: 80,
                height: `${Math.max(20, (simResult.passRate / 100) * 140)}px`,
                background: 'rgba(0,232,202,0.4)',
                borderRadius: '6px 6px 0 0',
                border: '1px solid rgba(0,232,202,0.3)',
              }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>After</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Projected</span>
            </div>
          </div>

          {/* CU impact estimate */}
          {cuMetrics && (
            <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(0,232,202,0.05)', borderRadius: 6, border: '1px solid rgba(0,232,202,0.15)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Estimated CU Reduction</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>
                  ~{Math.round((cuMetrics.ai_cu_consumed || cuMetrics.ai_cu_28d || 0) * simResult.reductionPct / 100).toLocaleString()} AI CUs saved
                </span>
              </div>
              {(cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 99 && simResult.reductionPct > 15 && (
                <div style={{ fontSize: 11, color: 'var(--teal)', marginTop: 4 }}>
                  Latency reduction of {simResult.reductionPct}% may help resolve capacity {(cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 999 ? 'suspension' : 'throttling'}.
                </div>
              )}
            </div>
          )}
        </div>
      }

      {/* Fix toggles */}
      <div className="glass" style={{ padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Recommended Fixes</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => setActiveFixes(actionableFixes)}
              style={{
                padding: '4px 12px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
                background: activeFixes.length === actionableFixes.length ? 'var(--teal)' : 'transparent',
                color: activeFixes.length === actionableFixes.length ? '#000' : 'var(--teal)',
                border: '1px solid var(--teal)', fontWeight: 600,
              }}
            >Select All</button>
            <button
              onClick={() => setActiveFixes([])}
              style={{
                padding: '4px 12px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
                background: activeFixes.length === 0 ? 'var(--teal)' : 'transparent',
                color: activeFixes.length === 0 ? '#000' : 'var(--teal)',
                border: '1px solid var(--teal)', fontWeight: 600,
              }}
            >Clear All</button>
          </div>
        </div>
        <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-muted)', marginBottom: 16 }}>
          Click each fix to toggle it on/off and see its projected impact on latency. Fixes are ordered by estimated reduction.
          Each shows the effort level (Low/Medium/High) and the responsible role (Data Engineer, AI Engineer, or Stakeholder).
          {activeFixes.length > 0 && <strong style={{ color: 'var(--green)' }}> {activeFixes.length} of {actionableFixes.length} fixes selected — combined reduction: -{simResult.reductionPct}%.</strong>}
          {activeFixes.length === 0 && <span style={{ color: 'var(--amber)' }}> No fixes selected — click "Select All" or individual fixes to see projected improvements.</span>}
        </p>
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
