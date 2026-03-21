import React, { useState, useEffect, useCallback } from 'react';

function StatusDot({ status, label, detail }) {
  const colors = {
    connected: '#4caf50',
    partial: '#ff9800',
    disconnected: '#f44336',
    checking: '#9e9e9e',
  };
  const color = colors[status] || colors.checking;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }} title={detail || label}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: color,
        boxShadow: status === 'connected' ? `0 0 6px ${color}` : 'none',
        transition: 'all 0.3s ease',
      }} />
      <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  );
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function StatusHeader({ session }) {
  const [statuses, setStatuses] = useState({
    backend: 'checking',
    llm: 'checking',
    chromadb: 'checking',
    fabric: 'disconnected',
  });
  const [details, setDetails] = useState({});
  const [clockTick, setClockTick] = useState(0);

  const checkStatuses = useCallback(async () => {
    // Check backend health
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        setStatuses(prev => ({
          ...prev,
          backend: 'connected',
          llm: data.missing_env ? 'partial' : (data.llm_model ? 'connected' : 'disconnected'),
          chromadb: data.chromadb === 'connected' ? 'connected' : 'disconnected',
        }));
        setDetails(prev => ({
          ...prev,
          backend: `Server running on port ${window.location.port || 5173}`,
          llm: data.missing_env
            ? `Missing: ${data.missing_env.join(', ')}`
            : `Model: ${data.llm_model || 'none'}`,
          chromadb: data.chromadb === 'connected' ? 'Knowledge base ready' : 'ChromaDB not found',
        }));
      } else {
        setStatuses(prev => ({ ...prev, backend: 'disconnected', llm: 'disconnected', chromadb: 'disconnected' }));
      }
    } catch {
      setStatuses(prev => ({ ...prev, backend: 'disconnected', llm: 'disconnected', chromadb: 'disconnected' }));
      setDetails(prev => ({ ...prev, backend: 'Backend server not running — run: npm run dev' }));
    }

    // Check ChromaDB in more detail
    try {
      const res = await fetch('/api/knowledge/status');
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          const total = Object.values(data.collections || {}).reduce((s, v) => s + v, 0);
          setStatuses(prev => ({ ...prev, chromadb: total > 0 ? 'connected' : 'partial' }));
          setDetails(prev => ({ ...prev, chromadb: `${total} chunks embedded` }));
        }
      }
    } catch {
      // Already handled above
    }
  }, []);

  useEffect(() => {
    checkStatuses();
    const interval = setInterval(checkStatuses, 30000); // Re-check every 30s
    return () => clearInterval(interval);
  }, [checkStatuses]);

  // Tick every 30s to keep relative timestamps fresh
  useEffect(() => {
    const tick = setInterval(() => setClockTick(c => c + 1), 30000);
    return () => clearInterval(tick);
  }, []);

  // Update Fabric status based on session
  useEffect(() => {
    if (session?.connected && !session?.sampleMode) {
      setStatuses(prev => ({ ...prev, fabric: 'connected' }));
      setDetails(prev => ({ ...prev, fabric: `Workspace: ${session.workspaceId || 'connected'}` }));
    } else if (session?.sampleMode) {
      setStatuses(prev => ({ ...prev, fabric: 'partial' }));
      setDetails(prev => ({ ...prev, fabric: 'Sample dataset mode (no live Fabric)' }));
    } else {
      setStatuses(prev => ({ ...prev, fabric: 'disconnected' }));
      setDetails(prev => ({ ...prev, fabric: 'Not connected — use Connect tab' }));
    }
  }, [session?.connected, session?.sampleMode, session?.workspaceId]);

  return (
    <div style={{
      display: 'flex', gap: 16, alignItems: 'center',
      padding: '6px 12px', borderRadius: 6,
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
    }}>
      <StatusDot status={statuses.backend} label="Backend" detail={details.backend} />
      <StatusDot status={statuses.llm} label="LLM Agents" detail={details.llm} />
      <StatusDot status={statuses.chromadb} label="ChromaDB" detail={details.chromadb} />
      <StatusDot status={statuses.fabric} label="Fabric" detail={details.fabric} />
      {session?.xmlaComplete && (
        <StatusDot status="connected" label="XMLA" detail="XMLA deep analysis data collected" />
      )}
      {session?.lastUpdated && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          borderLeft: '1px solid var(--border)', paddingLeft: 12, marginLeft: 4,
        }} title={new Date(session.lastUpdated).toLocaleString()}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            Updated {formatTimestamp(session.lastUpdated)}
          </span>
        </div>
      )}
      {session?.cuMetrics && (() => {
        const cu = session.cuMetrics;
        const ts = cu.throttle_state ?? cu.throttle_events ?? 0;
        const aiCu = cu.ai_cu_consumed ?? cu.ai_cu_28d ?? 0;
        let cuStatus = 'checking';
        let cuDetail = 'CU data not available';
        if (ts >= 999) {
          cuStatus = 'disconnected';
          cuDetail = 'Capacity SUSPENDED';
        } else if (ts >= 99) {
          cuStatus = 'disconnected';
          cuDetail = 'Capacity THROTTLED';
        } else if (aiCu > 0.85 * 100) {
          cuStatus = 'partial';
          cuDetail = `AI CU: ${aiCu} (>85% — approaching throttle)`;
        } else if (aiCu > 0 || ts === 0) {
          cuStatus = 'connected';
          cuDetail = `Active — AI CU: ${aiCu}`;
        }
        return <StatusDot status={cuStatus} label="CU" detail={cuDetail} />;
      })()}
    </div>
  );
}
