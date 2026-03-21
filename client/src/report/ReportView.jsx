import React, { useState, useEffect } from 'react';
import { simulate } from '../simulation/mathModel';
import { FIX_KEYS } from '../constants/fixes';

export default function ReportView({ session: propSession }) {
  // Support both prop-based session (normal route) and injected data (Puppeteer PDF)
  const [injectedSession, setInjectedSession] = useState(null);

  useEffect(() => {
    // Check if Puppeteer injected report data via window.__REPORT_DATA__
    if (window.__REPORT_DATA__) {
      setInjectedSession(window.__REPORT_DATA__);
    }
  }, []);

  const session = injectedSession || propSession || {};
  const findings = session.findings || [];
  const vr = session.validationResults;
  const cuMetrics = session.cuMetrics || null;
  const traces = session.traces || [];

  // Compute simulation with all fixes applied for the report
  const allFixSim = simulate(traces, FIX_KEYS);
  const baselineAvgMs = allFixSim.baselineAvgMs;
  const projectedAvgMs = allFixSim.avgMs;
  const reductionPct = allFixSim.reductionPct;
  const baselinePassRate = allFixSim.baselinePassRate;
  const projectedPassRate = allFixSim.passRate;

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
        <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 12 }}>
          The Fabric Data Agent Latency Analyzer performed a comprehensive analysis of <strong>{session.modelName || 'the data agent'}</strong> in
          the <strong>{session.domain || 'Unknown'}</strong> domain, examining {traces.length} query traces across {new Set(findings.map(f => f.agent_id)).size} analysis
          dimensions (Schema Design, DAX Generation, and Execution Performance).
        </p>
        <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 12 }}>
          The analysis identified <strong>{findings.length} latency findings</strong> with a combined estimated impact
          of <strong style={{ color: '#d32f2f' }}>{(findings.reduce((s, f) => s + (f.impact_ms || 0), 0) / 1000).toFixed(1)}s</strong> of
          added latency per query cycle. Of these, <strong style={{ color: '#d32f2f' }}>{severityCounts.CRITICAL} are critical</strong> issues
          requiring immediate remediation, <strong style={{ color: '#f57c00' }}>{severityCounts.HIGH} are high</strong> severity issues
          to address in the next sprint, and {severityCounts.MEDIUM} are medium severity optimizations.
        </p>
        <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 12 }}>
          The current average query latency is <strong style={{ color: '#d32f2f' }}>{(baselineAvgMs / 1000).toFixed(1)}s</strong>,
          which is {baselineAvgMs > 10000 ? <span><strong>{(baselineAvgMs / 10000).toFixed(1)}x above</strong></span> : 'within'} the
          recommended 10-second SLA target. If all recommended fixes are applied, the projected average latency
          drops to <strong style={{ color: '#2e7d32' }}>{(projectedAvgMs / 1000).toFixed(1)}s</strong> (a <strong style={{ color: '#2e7d32' }}>-{reductionPct}%</strong> reduction)
          and the pass rate (queries under 20s) improves from {baselinePassRate}% to {projectedPassRate}%.
        </p>
        {findings.length > 0 && (
          <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 0 }}>
            <strong>Top priority:</strong> The single biggest latency offender is "{[...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0))[0]?.issue}"
            with an estimated impact of {(([...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0))[0]?.impact_ms || 0) / 1000).toFixed(1)}s.
            Remediating the top 3 findings alone would eliminate the majority of measured latency impact.
          </p>
        )}
      </div>

      {/* Section 3: Root Cause Ranking (by latency impact — biggest offenders first) */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Root Cause Ranking — Biggest Latency Offenders</h2>
        <p style={{ fontSize: 13, color: '#666', marginBottom: 12 }}>
          Findings ranked by estimated latency impact (ms). Top offenders should be remediated first.
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
              <th style={{ padding: '8px 12px' }}>#</th>
              <th style={{ padding: '8px 12px' }}>Issue</th>
              <th style={{ padding: '8px 12px' }}>Affected Object</th>
              <th style={{ padding: '8px 12px' }}>Severity</th>
              <th style={{ padding: '8px 12px' }}>Impact</th>
            </tr>
          </thead>
          <tbody>
            {[...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0)).map((f, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '6px 12px', fontWeight: 700, color: i < 3 ? '#d32f2f' : i < 6 ? '#f57c00' : '#333' }}>{i + 1}</td>
                <td style={{ padding: '6px 12px' }}>{f.issue}</td>
                <td style={{ padding: '6px 12px', color: '#0288d1', fontSize: 12 }}>{f.affected_object || '—'}</td>
                <td style={{ padding: '6px 12px', color: f.severity === 'CRITICAL' ? '#d32f2f' : f.severity === 'HIGH' ? '#f57c00' : '#1976d2' }}>
                  {f.severity}
                </td>
                <td style={{ padding: '6px 12px', fontWeight: 600 }}>{f.impact_ms ? `${(f.impact_ms / 1000).toFixed(1)}s` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Section 4: Detailed Findings with Explanations & Resolutions */}
      <div style={{ marginBottom: 30 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Detailed Findings & Resolutions</h2>
        {[...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0)).map((f, i) => (
          <div key={i} style={{ marginBottom: 16, padding: '14px 18px', border: '1px solid #e0e0e0', borderRadius: 6, pageBreakInside: 'avoid' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ background: i < 3 ? '#ffebee' : i < 6 ? '#fff3e0' : '#e3f2fd', color: i < 3 ? '#d32f2f' : i < 6 ? '#f57c00' : '#1976d2', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700 }}>
                    #{i + 1}
                  </span>
                  <strong style={{ fontSize: 14 }}>{f.issue}</strong>
                </div>
                {f.affected_object && (
                  <p style={{ fontSize: 12, color: '#0288d1', margin: '4px 0' }}>{f.affected_object}</p>
                )}
              </div>
              <div style={{ textAlign: 'right', minWidth: 100 }}>
                <span style={{ color: f.severity === 'CRITICAL' ? '#d32f2f' : f.severity === 'HIGH' ? '#f57c00' : '#1976d2', fontWeight: 600 }}>
                  {f.severity}
                </span>
                {f.impact_ms > 0 && <div style={{ fontSize: 12, fontWeight: 600, color: '#d32f2f' }}>{(f.impact_ms / 1000).toFixed(1)}s impact</div>}
              </div>
            </div>

            {/* Affected tables */}
            {f.affected_tables && f.affected_tables.length > 0 && (
              <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {f.affected_tables.map((t, j) => (
                  <span key={j} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: '#e0f7fa', color: '#00838f', border: '1px solid #b2ebf2' }}>
                    {t}
                  </span>
                ))}
              </div>
            )}

            {/* Explanation */}
            {f.explanation && (
              <div style={{ marginTop: 8, padding: '8px 12px', background: '#fafafa', borderRadius: 4, border: '1px solid #f0f0f0' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 4 }}>EXPLANATION</p>
                <p style={{ fontSize: 13, color: '#333', lineHeight: 1.6, margin: 0 }}>{f.explanation}</p>
              </div>
            )}

            {/* Latency contribution */}
            {f.latency_contribution && (
              <div style={{ marginTop: 6, padding: '6px 10px', background: '#ffebee', borderRadius: 4, border: '1px solid #ffcdd2' }}>
                <p style={{ fontSize: 12, color: '#c62828', margin: 0 }}><strong>Latency:</strong> {f.latency_contribution}</p>
              </div>
            )}

            {/* Evidence */}
            {f.evidence && <p style={{ fontSize: 12, color: '#666', marginTop: 6 }}><strong>Evidence:</strong> {f.evidence}</p>}

            {/* Fix recommendation */}
            {f.fix && <p style={{ fontSize: 12, color: '#2e7d32', marginTop: 4 }}><strong>Fix:</strong> {f.fix}</p>}

            {/* Resolution steps */}
            {f.resolution_steps && f.resolution_steps.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 4 }}>RESOLUTION STEPS</p>
                <ol style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#333', lineHeight: 1.7 }}>
                  {f.resolution_steps.map((step, j) => (
                    <li key={j}>{step}</li>
                  ))}
                </ol>
              </div>
            )}
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

      {/* Section 7: Before vs After Comparison */}
      {traces.length > 0 && (
        <div style={{ marginBottom: 30 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Before vs After Comparison</h2>
          <p style={{ fontSize: 13, color: '#666', marginBottom: 16 }}>
            Projected impact if all recommended fixes are applied simultaneously.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Metric</th>
                <th style={{ padding: '8px 12px' }}>Before</th>
                <th style={{ padding: '8px 12px' }}>After (Projected)</th>
                <th style={{ padding: '8px 12px' }}>Change</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px', fontWeight: 500 }}>Avg Latency</td>
                <td style={{ padding: '8px 12px', color: '#d32f2f' }}>{(baselineAvgMs / 1000).toFixed(1)}s</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32' }}>{(projectedAvgMs / 1000).toFixed(1)}s</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32', fontWeight: 600 }}>-{reductionPct}%</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px', fontWeight: 500 }}>Pass Rate (&lt;20s)</td>
                <td style={{ padding: '8px 12px', color: '#d32f2f' }}>{baselinePassRate}%</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32' }}>{projectedPassRate}%</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32', fontWeight: 600 }}>+{projectedPassRate - baselinePassRate}%</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px', fontWeight: 500 }}>Outlier Latency</td>
                <td style={{ padding: '8px 12px', color: '#d32f2f' }}>{(allFixSim.baselineOutlierMs / 1000).toFixed(1)}s</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32' }}>{(allFixSim.outlierMs / 1000).toFixed(1)}s</td>
                <td style={{ padding: '8px 12px', color: '#2e7d32', fontWeight: 600 }}>
                  -{allFixSim.baselineOutlierMs > 0 ? Math.round(((allFixSim.baselineOutlierMs - allFixSim.outlierMs) / allFixSim.baselineOutlierMs) * 100) : 0}%
                </td>
              </tr>
            </tbody>
          </table>
          {/* Per-fix breakdown */}
          <h3 style={{ fontSize: 16, fontWeight: 600, marginTop: 20, marginBottom: 8 }}>Per-Fix Impact Breakdown</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
                <th style={{ padding: '6px 12px' }}>Fix</th>
                <th style={{ padding: '6px 12px' }}>Reduction</th>
                <th style={{ padding: '6px 12px' }}>%</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(allFixSim.perFix)
                .sort(([,a], [,b]) => b.reductionMs - a.reductionMs)
                .map(([key, pf]) => (
                  <tr key={key} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '6px 12px' }}>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                    <td style={{ padding: '6px 12px' }}>-{(pf.reductionMs / 1000).toFixed(1)}s</td>
                    <td style={{ padding: '6px 12px', color: '#2e7d32' }}>-{pf.reductionPct}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Section 7b: CU Cost Correlation */}
      {cuMetrics && (
        <div style={{ marginBottom: 30 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Capacity Unit (CU) Cost Correlation</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Metric</th>
                <th style={{ padding: '8px 12px' }}>Value</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px' }}>AI CU Consumed</td>
                <td style={{ padding: '8px 12px', fontWeight: 600 }}>{(cuMetrics.ai_cu_consumed || cuMetrics.ai_cu_28d || 0).toLocaleString()}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px' }}>Query CU Consumed</td>
                <td style={{ padding: '8px 12px', fontWeight: 600 }}>{(cuMetrics.query_cu_consumed || cuMetrics.query_cu_28d || 0).toLocaleString()}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px' }}>Capacity State</td>
                <td style={{ padding: '8px 12px', fontWeight: 600, color: (cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 99 ? '#d32f2f' : '#2e7d32' }}>
                  {(cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 999 ? 'Suspended' : (cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 99 ? 'Throttled' : 'Active'}
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px 12px' }}>P50 / P95 Latency</td>
                <td style={{ padding: '8px 12px', fontWeight: 600 }}>
                  {((cuMetrics.p50_ms || 0) / 1000).toFixed(1)}s / {((cuMetrics.p95_ms || 0) / 1000).toFixed(1)}s
                </td>
              </tr>
            </tbody>
          </table>
          {reductionPct > 0 && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: '#e8f5e9', borderRadius: 6, border: '1px solid #c8e6c9' }}>
              <p style={{ fontSize: 13, color: '#2e7d32', margin: 0 }}>
                Estimated CU Reduction: ~{Math.round((cuMetrics.ai_cu_consumed || cuMetrics.ai_cu_28d || 0) * reductionPct / 100).toLocaleString()} AI CUs saved
                {(cuMetrics.throttle_state ?? cuMetrics.throttle_events ?? 0) >= 99 && ` | Latency reduction of ${reductionPct}% may help resolve capacity throttling.`}
              </p>
            </div>
          )}
        </div>
      )}

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
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 12 }}>Appendix — Methodology & Definitions</h2>
        <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, marginBottom: 12 }}>
          <strong>Analysis Method:</strong> This report was generated by the Fabric Data Agent Latency Analyzer v1.0 using a deterministic
          rules engine that evaluates query traces against 29 known latency patterns cataloged from Microsoft's Fabric Data Agent documentation
          and real-world deployment benchmarks. The simulation model uses calibrated reduction factors with caps of 78% (schema), 82% (DAX),
          and 65% (execution) to prevent over-optimistic projections. A floor of 1,600ms per trace represents the minimum achievable latency
          for any Fabric Data Agent query.
        </p>
        <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, marginBottom: 12 }}>
          <strong>Severity Definitions:</strong> CRITICAL = must fix immediately, directly causing user-facing latency degradation or compliance risk.
          HIGH = should fix in next sprint, significant contributor to latency. MEDIUM = optimization opportunity, lower priority.
        </p>
        <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7 }}>
          Domain: {session.domain || 'Unknown'} | Model: {session.modelName || 'Unknown'} | Traces: {(session.traces || []).length} |
          Scan Date: {new Date().toLocaleDateString()} | Report generated by Fabric Data Agent Latency Analyzer v1.0
        </p>
      </div>
    </div>
  );
}
