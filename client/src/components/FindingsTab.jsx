import React, { useState } from 'react';
import { AGENTS } from '../constants/agentMeta';

function FindingCard({ finding, rank, session }) {
  const [expanded, setExpanded] = useState(false);
  const agent = AGENTS[finding.agent_id] || {};

  return (
    <div className="glass glass-hover" style={{ padding: '16px 20px', cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        {/* Latency rank badge */}
        <div style={{
          minWidth: 32, height: 32, borderRadius: '50%',
          background: rank <= 3 ? 'rgba(211, 47, 47, 0.15)' : rank <= 6 ? 'rgba(245, 124, 0, 0.15)' : 'rgba(25, 118, 210, 0.1)',
          color: rank <= 3 ? 'var(--red)' : rank <= 6 ? 'var(--amber)' : 'var(--blue)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700,
        }}>
          #{rank}
        </div>
        <span className={`badge badge-${finding.severity?.toLowerCase() || 'medium'}`}>
          {finding.severity || 'MEDIUM'}
        </span>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{finding.issue}</p>
          <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span style={{ color: agent.accent }}>{agent.glyph} {agent.name || finding.agent_id}</span>
            {finding.impact_ms > 0 && (
              <span style={{ color: finding.impact_ms > 5000 ? 'var(--red)' : 'var(--amber)', fontWeight: 600 }}>
                {finding.impact_ms >= 1000 ? `${(finding.impact_ms / 1000).toFixed(1)}s` : `${finding.impact_ms}ms`} impact
              </span>
            )}
            {finding.affected_object && (
              <span style={{ color: 'var(--teal)' }}>{finding.affected_object}</span>
            )}
          </div>
          {/* Affected tables inline */}
          {finding.affected_tables && finding.affected_tables.length > 0 && (
            <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
              {finding.affected_tables.slice(0, 5).map((t, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 3,
                  background: 'rgba(0, 188, 212, 0.1)', color: 'var(--teal)',
                  border: '1px solid rgba(0, 188, 212, 0.2)',
                }}>
                  {t}
                </span>
              ))}
              {finding.affected_tables.length > 5 && (
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>+{finding.affected_tables.length - 5} more</span>
              )}
            </div>
          )}
        </div>
        <span style={{ fontSize: 18, color: 'var(--text-muted)', transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
          &#9660;
        </span>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 13 }}>
          {/* Detailed explanation */}
          {finding.explanation && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Detailed Explanation</strong>
              <p style={{ marginTop: 4, lineHeight: 1.6, color: 'var(--text-primary)' }}>{finding.explanation}</p>
            </div>
          )}

          {/* Latency contribution */}
          {finding.latency_contribution && (
            <div style={{ marginBottom: 12, padding: '8px 12px', background: 'rgba(211, 47, 47, 0.06)', borderRadius: 6, border: '1px solid rgba(211, 47, 47, 0.15)' }}>
              <strong style={{ color: 'var(--red)', fontSize: 11 }}>LATENCY CONTRIBUTION: </strong>
              <span style={{ color: 'var(--text-primary)' }}>{finding.latency_contribution}</span>
            </div>
          )}

          {/* Evidence */}
          {finding.evidence && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Evidence</strong>
              <p style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '8px 12px', borderRadius: 4 }}>
                {finding.evidence}
              </p>
            </div>
          )}

          {/* Fix recommendation */}
          {finding.fix && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: 'var(--green)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Recommended Fix</strong>
              <p style={{ marginTop: 4, color: 'var(--green)' }}>{finding.fix}</p>
            </div>
          )}

          {/* Resolution steps */}
          {finding.resolution_steps && finding.resolution_steps.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Resolution Steps</strong>
              <ol style={{ marginTop: 6, paddingLeft: 20, lineHeight: 1.8, color: 'var(--text-primary)' }}>
                {finding.resolution_steps.map((step, i) => (
                  <li key={i} style={{ fontSize: 13 }}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Why this matters */}
          {finding.severity === 'CRITICAL' && (
            <div style={{ marginBottom: 12, padding: '8px 12px', background: 'rgba(211, 47, 47, 0.04)', borderRadius: 6, border: '1px solid rgba(211, 47, 47, 0.1)' }}>
              <strong style={{ color: 'var(--red)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Why This Matters</strong>
              <p style={{ marginTop: 4, fontSize: 12, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                This is a <strong>CRITICAL</strong> finding that directly contributes to user-facing latency degradation.
                {finding.impact_ms > 10000
                  ? ` With ${(finding.impact_ms / 1000).toFixed(1)}s of estimated impact, this single issue accounts for a significant portion of the total latency budget. Users will experience noticeable delays, potential timeouts, and degraded confidence in the Data Agent's responsiveness.`
                  : ` This issue compounds with other findings to push overall latency well above the 10-second SLA target. Left unresolved, it will continue to degrade query performance and increase Capacity Unit consumption.`
                }
              </p>
            </div>
          )}

          {/* Affected traces */}
          {finding.affected_traces && finding.affected_traces.length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '6px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
              <strong>Scope:</strong> This finding affects {finding.affected_traces.length} of {session?.traces?.length || 'all'} analyzed
              traces ({((finding.affected_traces.length / Math.max(session?.traces?.length || 1, 1)) * 100).toFixed(0)}% of query workload).
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function FindingsTab({ session }) {
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [filterAgent, setFilterAgent] = useState('all');
  const [sortBy, setSortBy] = useState('impact');
  const findings = session.findings || [];

  const filtered = findings.filter(f =>
    (filterSeverity === 'all' || f.severity === filterSeverity) &&
    (filterAgent === 'all' || f.agent_id === filterAgent)
  );

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'impact') {
      return (b.impact_ms || 0) - (a.impact_ms || 0);
    }
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return (order[a.severity] || 4) - (order[b.severity] || 4);
  });

  const severityCounts = {
    CRITICAL: findings.filter(f => f.severity === 'CRITICAL').length,
    HIGH: findings.filter(f => f.severity === 'HIGH').length,
    MEDIUM: findings.filter(f => f.severity === 'MEDIUM').length,
    LOW: findings.filter(f => f.severity === 'LOW').length,
  };

  const totalImpactMs = findings.reduce((sum, f) => sum + (f.impact_ms || 0), 0);

  // Compute narrative summary
  const criticalFindings = findings.filter(f => f.severity === 'CRITICAL');
  const highFindings = findings.filter(f => f.severity === 'HIGH');
  const schemaFindings = findings.filter(f => f.agent_id === 'schema');
  const daxFindings = findings.filter(f => f.agent_id === 'dax');
  const daxExprFindings = findings.filter(f => f.agent_id === 'dax_expression');
  const xmlaFindings = findings.filter(f => f.agent_id === 'xmla');
  const execFindings = findings.filter(f => f.agent_id === 'execution');
  const topOffender = findings.length > 0 ? [...findings].sort((a, b) => (b.impact_ms || 0) - (a.impact_ms || 0))[0] : null;

  if (!session.analysisComplete && findings.length === 0) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Run the analysis pipeline first to see findings.</p>
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Narrative Analysis Summary */}
      {findings.length > 0 && (
        <div className="glass" style={{ padding: '20px 24px', marginBottom: 20, borderLeft: '3px solid var(--teal)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 10, color: 'var(--teal)' }}>Analysis Summary</h3>
          <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 8 }}>
            The deterministic rules engine analyzed {session.traces?.length || 0} query traces against the <strong>{session.modelName || 'semantic model'}</strong> and
            identified <strong>{findings.length} latency findings</strong> with a combined estimated impact of <strong style={{ color: 'var(--red)' }}>{totalImpactMs >= 1000 ? `${(totalImpactMs / 1000).toFixed(1)}s` : `${totalImpactMs}ms`}</strong> of
            added latency per query cycle. Of these, <strong style={{ color: 'var(--red)' }}>{severityCounts.CRITICAL} are critical</strong> issues requiring immediate
            remediation, and <strong style={{ color: 'var(--amber)' }}>{severityCounts.HIGH} are high</strong> severity issues that should be addressed in the next sprint.
          </p>
          <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 8 }}>
            The findings span {new Set(findings.map(f => f.agent_id)).size} analysis dimensions:
            {schemaFindings.length > 0 && <span> <strong>{schemaFindings.length} schema issues</strong> (table scope, measures, descriptions, relationships),</span>}
            {daxFindings.length > 0 && <span> <strong>{daxFindings.length} DAX generation issues</strong> (retries, missing TOPN guards, failed queries, governance),</span>}
            {daxExprFindings.length > 0 && <span> <strong>{daxExprFindings.length} DAX expression issues</strong> (nesting depth, scan patterns, division safety, complexity),</span>}
            {xmlaFindings.length > 0 && <span> <strong>{xmlaFindings.length} XMLA deep analysis issues</strong> (column cardinality, storage, relationships, many-to-many),</span>}
            {execFindings.length > 0 && <span> <strong>{execFindings.length} execution engine issues</strong> (outlier traces, CU throttling, dominant latency phases).</span>}
          </p>
          {topOffender && (
            <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 0 }}>
              The <strong>single biggest latency offender</strong> is <em>"{topOffender.issue}"</em> with
              an estimated impact of <strong style={{ color: 'var(--red)' }}>{topOffender.impact_ms >= 1000 ? `${(topOffender.impact_ms / 1000).toFixed(1)}s` : `${topOffender.impact_ms}ms`}</strong>.
              Remediating just the top 3 findings would eliminate approximately <strong style={{ color: 'var(--green)' }}>
              {((criticalFindings.slice(0, 3).reduce((s, f) => s + (f.impact_ms || 0), 0) / Math.max(totalImpactMs, 1)) * 100).toFixed(0)}%</strong> of
              the total measured latency impact. Click any finding below to expand its detailed explanation, evidence, recommended fix, and step-by-step resolution guide.
            </p>
          )}
        </div>
      )}

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
        {Object.entries(severityCounts).map(([sev, count]) => (
          <div key={sev} className="glass metric-card" onClick={() => setFilterSeverity(filterSeverity === sev ? 'all' : sev)}
            style={{ cursor: 'pointer', border: filterSeverity === sev ? `1px solid var(--${sev === 'CRITICAL' ? 'red' : sev === 'HIGH' ? 'amber' : sev === 'MEDIUM' ? 'blue' : 'green'})` : undefined }}>
            <div className="value" style={{ color: `var(--${sev === 'CRITICAL' ? 'red' : sev === 'HIGH' ? 'amber' : sev === 'MEDIUM' ? 'blue' : 'green'})` }}>
              {count}
            </div>
            <div className="label">{sev}</div>
          </div>
        ))}
        <div className="glass metric-card">
          <div className="value" style={{ color: 'var(--red)', fontSize: 18 }}>
            {totalImpactMs >= 1000 ? `${(totalImpactMs / 1000).toFixed(1)}s` : `${totalImpactMs}ms`}
          </div>
          <div className="label">Total Impact</div>
        </div>
      </div>

      {/* Sort + Agent filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4, marginRight: 12 }}>
          <button className={`tab-btn ${sortBy === 'impact' ? 'active' : ''}`}
            onClick={() => setSortBy('impact')} style={{ fontSize: 11, padding: '4px 10px' }}>
            Biggest Offenders
          </button>
          <button className={`tab-btn ${sortBy === 'severity' ? 'active' : ''}`}
            onClick={() => setSortBy('severity')} style={{ fontSize: 11, padding: '4px 10px' }}>
            By Severity
          </button>
        </div>
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
        {sorted.map((finding, i) => (
          <FindingCard key={finding.finding_id || i} finding={finding} rank={i + 1} session={session} />
        ))}
        {sorted.length === 0 && (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 32 }}>No findings match filters.</p>
        )}
      </div>
    </div>
  );
}
