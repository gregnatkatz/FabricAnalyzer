import React, { useState } from 'react';
import { DOMAIN_LABELS } from '../constants/domainSignals';

function LatencyRing({ ms, size = 48 }) {
  const maxMs = 45000;
  const pct = Math.min(ms / maxMs, 1);
  const color = ms > 45000 ? 'var(--red)' : ms > 20000 ? 'var(--amber)' : ms > 10000 ? 'var(--blue)' : 'var(--green)';
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={3} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={3}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <span style={{
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontFamily: 'var(--font-mono)', color,
      }}>
        {ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`}
      </span>
    </div>
  );
}

export default function TracesTab({ session }) {
  const [filter, setFilter] = useState('all');
  const traces = session.traces || [];

  const filtered = filter === 'all' ? traces
    : filter === 'slow' ? traces.filter(t => t.total_ms > 20000)
    : filter === 'retries' ? traces.filter(t => t.retries > 0)
    : filter === 'failed' ? traces.filter(t => t.pass_fail === 'fail')
    : traces;

  // CU metrics from session (collected from cu_metrics table)
  const cuMetrics = session.cuMetrics || null;

  if (!session.collectionComplete) {
    return (
      <div className="glass fade-in" style={{ padding: 48, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>No traces yet — connect to a workspace or load sample data first.</p>
      </div>
    );
  }

  const avgLatency = traces.length > 0 ? traces.reduce((s, t) => s + t.total_ms, 0) / traces.length : 0;
  const retryCount = traces.filter(t => t.retries > 0).length;

  return (
    <div className="fade-in">
      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Domain', value: DOMAIN_LABELS[session.domain] || session.domain || '—', color: 'var(--blue)' },
          { label: 'Avg Latency', value: avgLatency > 0 ? `${(avgLatency / 1000).toFixed(1)}s` : '—', color: 'var(--teal)' },
          { label: 'Traces', value: traces.length, color: 'var(--text)' },
          { label: 'Retries', value: retryCount, color: retryCount > 0 ? 'var(--amber)' : 'var(--green)' },
        ].map(card => (
          <div key={card.label} className="glass metric-card">
            <div className="value" style={{ color: card.color }}>{card.value}</div>
            <div className="label">{card.label}</div>
          </div>
        ))}
      </div>

      {/* CU Cost Correlation */}
      {cuMetrics && (
        <div className="glass" style={{ padding: 16, marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--teal)' }}>
            Capacity Unit (CU) Correlation
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>
                {cuMetrics.ai_cu_28d != null ? cuMetrics.ai_cu_28d.toLocaleString() : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>AI CU (28d)</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--blue)', fontFamily: 'var(--font-mono)' }}>
                {cuMetrics.query_cu_28d != null ? cuMetrics.query_cu_28d.toLocaleString() : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Query CU (28d)</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: (cuMetrics.throttle_events || 0) > 50 ? 'var(--red)' : (cuMetrics.throttle_events || 0) > 10 ? 'var(--amber)' : 'var(--green)' }}>
                {cuMetrics.throttle_events != null ? cuMetrics.throttle_events : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Throttle Events</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>
                {cuMetrics.p50_ms != null ? `${(cuMetrics.p50_ms / 1000).toFixed(1)}s` : '—'}
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}> / </span>
                {cuMetrics.p95_ms != null ? `${(cuMetrics.p95_ms / 1000).toFixed(1)}s` : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>P50 / P95 Latency</div>
            </div>
          </div>
          {/* CU-Latency correlation indicator */}
          {cuMetrics.throttle_events > 0 && avgLatency > 15000 && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)' }}>
              <span style={{ fontSize: 12, color: 'var(--red)' }}>
                High CU throttling ({cuMetrics.throttle_events} events) is correlating with elevated latency ({(avgLatency / 1000).toFixed(1)}s avg).
                Consider increasing capacity or optimizing high-CU queries.
              </span>
            </div>
          )}
          {cuMetrics.throttle_events === 0 && avgLatency > 20000 && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(245,158,11,0.08)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.2)' }}>
              <span style={{ fontSize: 12, color: 'var(--amber)' }}>
                No CU throttling detected — latency is driven by agent configuration (schema scope, instructions, routing) not capacity.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['all', 'slow', 'retries', 'failed'].map(f => (
          <button key={f} className={`tab-btn ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)} style={{ fontSize: 12, padding: '4px 12px' }}>
            {f === 'all' ? `All (${traces.length})`
              : f === 'slow' ? `Slow (${traces.filter(t => t.total_ms > 20000).length})`
              : f === 'retries' ? `Retries (${traces.filter(t => t.retries > 0).length})`
              : `Failed (${traces.filter(t => t.pass_fail === 'fail').length})`}
          </button>
        ))}
      </div>

      {/* Trace list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.map((trace, i) => (
          <div key={trace.trace_id || i} className="glass glass-hover"
            style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 16 }}>
            <LatencyRing ms={trace.total_ms} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {trace.question}
              </p>
              <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                <span>Schema: {trace.bd_schema || 0}ms</span>
                <span>DAX: {trace.bd_nldax || 0}ms</span>
                <span>Exec: {trace.bd_exec || 0}ms</span>
                {trace.retries > 0 && <span style={{ color: 'var(--amber)' }}>Retries: {trace.retries}</span>}
                {trace.physician_visible && <span style={{ color: 'var(--red)' }}>Physician Visible</span>}
              </div>
            </div>
            <span className={`badge badge-${trace.total_ms > 45000 ? 'critical' : trace.total_ms > 20000 ? 'high' : trace.total_ms > 10000 ? 'medium' : 'low'}`}>
              {trace.pass_fail === 'fail' ? 'FAIL' : trace.total_ms > 45000 ? 'OUTLIER' : trace.total_ms > 20000 ? 'SLOW' : 'OK'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
