import React, { useState, useEffect, useCallback } from 'react';
import { getHistory, clearHistory, getSchedules, createSchedule, deleteSchedule, updateSchedule, getMsLearnArticles, refreshMsLearnCache } from '../api/proxy';

// ─── Mini bar chart (pure CSS, no dependencies) ───────────────────
function MiniBar({ value, max, color = 'var(--teal)' }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)' }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color, transition: 'width 0.4s ease' }} />
    </div>
  );
}

// ─── Severity badge ───────────────────────────────────────────────
function SevBadge({ severity, count }) {
  const colors = { critical: '#ff5151', high: '#f5a623', medium: '#60a5fa', low: '#9e9e9e' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
      background: `${colors[severity] || '#666'}20`, color: colors[severity] || '#666',
    }}>
      {count} {severity}
    </span>
  );
}

export default function TrendingTab({ session }) {
  const [history, setHistory] = useState([]);
  const [trending, setTrending] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [mslearn, setMslearn] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState('history'); // history | schedules | mslearn

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [histRes, schedRes, msRes] = await Promise.all([
        getHistory(null, 50),
        getSchedules(),
        getMsLearnArticles(),
      ]);
      setHistory(histRes.history || []);
      setTrending(histRes.trending || null);
      setSchedules(schedRes.schedules || []);
      setMslearn(msRes);
    } catch (err) {
      console.error('TrendingTab load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleCreateSchedule = async () => {
    if (!session?.workspaceId || !session?.modelId) return;
    await createSchedule({
      workspaceId: session.workspaceId,
      modelId: session.modelId,
      agentName: session.modelName || 'Data Agent',
      frequency: 'daily',
      enabled: true,
    });
    refresh();
  };

  const handleDeleteSchedule = async (id) => {
    await deleteSchedule(id);
    refresh();
  };

  const handleToggleSchedule = async (id, enabled) => {
    await updateSchedule(id, { enabled: !enabled });
    refresh();
  };

  const handleRefreshMsLearn = async () => {
    await refreshMsLearnCache();
    const msRes = await getMsLearnArticles();
    setMslearn(msRes);
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Clear all analysis history? This cannot be undone.')) return;
    await clearHistory();
    refresh();
  };

  const maxFindings = Math.max(...history.map(h => h.findingCount), 1);
  const maxImpact = Math.max(...history.map(h => h.totalImpactMs), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Section tabs */}
      <div style={{ display: 'flex', gap: 8 }}>
        {[
          { id: 'history', label: 'Analysis History' },
          { id: 'schedules', label: 'Scheduled Runs' },
          { id: 'mslearn', label: 'MS Learn Best Practices' },
        ].map(s => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            style={{
              padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border)',
              background: activeSection === s.id ? 'var(--teal)' : 'var(--surface)',
              color: activeSection === s.id ? '#000' : 'var(--text)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* ═══ ANALYSIS HISTORY ═══ */}
      {activeSection === 'history' && (
        <div className="glass" style={{ padding: 20, borderRadius: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Analysis History</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={refresh} style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer' }}>
                Refresh
              </button>
              {history.length > 0 && (
                <button onClick={handleClearHistory} style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid rgba(255,81,81,0.3)', background: 'rgba(255,81,81,0.08)', color: 'var(--red)', fontSize: 11, cursor: 'pointer' }}>
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Trending summary */}
          {trending && trending.trend !== 'insufficient_data' && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
              marginBottom: 16, padding: 12, borderRadius: 8,
              background: trending.trend === 'improving' ? 'rgba(34,197,94,0.06)'
                : trending.trend === 'degrading' ? 'rgba(255,81,81,0.06)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${trending.trend === 'improving' ? 'rgba(34,197,94,0.2)' : trending.trend === 'degrading' ? 'rgba(255,81,81,0.2)' : 'var(--border)'}`,
            }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Trend</div>
                <div style={{
                  fontSize: 14, fontWeight: 700,
                  color: trending.trend === 'improving' ? 'var(--green)' : trending.trend === 'degrading' ? 'var(--red)' : 'var(--text-muted)',
                }}>
                  {trending.trend === 'improving' ? 'Improving' : trending.trend === 'degrading' ? 'Degrading' : 'Stable'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Findings Avg</div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>
                  {trending.findingsTrend?.recent || 0}
                  <span style={{ fontSize: 11, color: trending.findingsTrend?.delta < 0 ? 'var(--green)' : 'var(--red)', marginLeft: 4 }}>
                    {trending.findingsTrend?.delta > 0 ? '+' : ''}{trending.findingsTrend?.delta || 0}
                  </span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Impact Avg</div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>
                  {((trending.impactTrend?.recentMs || 0) / 1000).toFixed(1)}s
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Total Runs</div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{trending.runs}</div>
              </div>
            </div>
          )}

          {/* History list */}
          {loading ? (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>Loading history...</p>
          ) : history.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No analysis history yet.</p>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                Run an analysis and it will appear here. History is saved automatically after each pipeline run.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...history].reverse().map((run, i) => (
                <div key={run.id} style={{
                  display: 'grid', gridTemplateColumns: '120px 140px 1fr 100px 80px',
                  gap: 12, alignItems: 'center', padding: '10px 12px', borderRadius: 6,
                  background: i === 0 ? 'rgba(0,232,202,0.04)' : 'rgba(255,255,255,0.02)',
                  border: '1px solid var(--border)',
                }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {new Date(run.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      {new Date(run.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{run.agentName}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{run.domain}</div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 56 }}>{run.findingCount} issues</span>
                      <MiniBar value={run.findingCount} max={maxFindings} color="var(--amber)" />
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 56 }}>{(run.totalImpactMs / 1000).toFixed(1)}s</span>
                      <MiniBar value={run.totalImpactMs} max={maxImpact} color="var(--red)" />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {run.severityCounts?.critical > 0 && <SevBadge severity="critical" count={run.severityCounts.critical} />}
                    {run.severityCounts?.high > 0 && <SevBadge severity="high" count={run.severityCounts.high} />}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
                    {run.traceCount} traces
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ SCHEDULED RUNS ═══ */}
      {activeSection === 'schedules' && (
        <div className="glass" style={{ padding: 20, borderRadius: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Scheduled Analysis Runs</h3>
            {session?.workspaceId && (
              <button onClick={handleCreateSchedule} style={{
                padding: '6px 14px', borderRadius: 6, border: 'none',
                background: 'var(--teal)', color: '#000', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}>
                + New Schedule
              </button>
            )}
          </div>

          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            Schedule recurring analysis runs for your connected workspace. The analyzer will automatically collect traces, run XMLA analysis, and execute the full pipeline on your configured schedule.
          </p>

          {schedules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, border: '1px dashed var(--border)', borderRadius: 8 }}>
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No scheduled runs configured.</p>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                {session?.workspaceId
                  ? 'Click "+ New Schedule" to set up automatic analysis.'
                  : 'Connect to a workspace first, then create a schedule.'}
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {schedules.map(sched => (
                <div key={sched.id} style={{
                  display: 'grid', gridTemplateColumns: '1fr 100px 100px 100px 80px',
                  gap: 12, alignItems: 'center', padding: '12px 16px', borderRadius: 8,
                  background: sched.enabled ? 'rgba(0,232,202,0.04)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${sched.enabled ? 'rgba(0,232,202,0.2)' : 'var(--border)'}`,
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{sched.agentName}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {sched.workspaceId?.slice(0, 8)}... / {sched.modelId?.slice(0, 8)}...
                    </div>
                  </div>
                  <div>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                      background: 'rgba(96,165,250,0.15)', color: 'var(--blue)',
                    }}>
                      {sched.frequency}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {sched.lastRun ? `Last: ${new Date(sched.lastRun).toLocaleDateString()}` : 'Never run'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    Runs: {sched.runCount}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => handleToggleSchedule(sched.id, sched.enabled)}
                      style={{
                        padding: '3px 8px', borderRadius: 4, border: '1px solid var(--border)',
                        background: sched.enabled ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.05)',
                        color: sched.enabled ? 'var(--green)' : 'var(--text-muted)',
                        fontSize: 10, cursor: 'pointer',
                      }}
                    >
                      {sched.enabled ? 'ON' : 'OFF'}
                    </button>
                    <button
                      onClick={() => handleDeleteSchedule(sched.id)}
                      style={{
                        padding: '3px 8px', borderRadius: 4, border: '1px solid rgba(255,81,81,0.3)',
                        background: 'rgba(255,81,81,0.08)', color: 'var(--red)',
                        fontSize: 10, cursor: 'pointer',
                      }}
                    >
                      Del
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ MS LEARN BEST PRACTICES ═══ */}
      {activeSection === 'mslearn' && (
        <div className="glass" style={{ padding: 20, borderRadius: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Microsoft Learn Best Practices</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {mslearn?.cache?.last_refresh && (
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  Updated: {new Date(mslearn.cache.last_refresh).toLocaleDateString()}
                </span>
              )}
              <button onClick={handleRefreshMsLearn} style={{
                padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)',
                background: 'var(--surface)', color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer',
              }}>
                Refresh
              </button>
            </div>
          </div>

          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            Curated best practices from Microsoft Learn documentation. These are cross-referenced with analysis findings to provide actionable, up-to-date guidance.
          </p>

          {/* Category summary cards */}
          {mslearn?.summary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 20 }}>
              {Object.entries(mslearn.summary).map(([cat, data]) => (
                <div key={cat} style={{
                  padding: 12, borderRadius: 8, border: '1px solid var(--border)',
                  background: 'rgba(255,255,255,0.02)',
                }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--teal)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {cat.replace(/_/g, ' ')}
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>
                    {data.total_practices}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    practices across {data.articles.length} article{data.articles.length !== 1 ? 's' : ''}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Articles list */}
          {mslearn?.articles && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {mslearn.articles.map(article => (
                <div key={article.id} style={{
                  padding: 14, borderRadius: 8, border: '1px solid var(--border)',
                  background: 'rgba(255,255,255,0.02)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <a href={article.url} target="_blank" rel="noopener noreferrer"
                        style={{ fontSize: 13, fontWeight: 600, color: 'var(--teal)', textDecoration: 'none' }}>
                        {article.title}
                      </a>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                        {article.category.replace(/_/g, ' ')} | Reviewed: {article.last_reviewed}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {(article.finding_tags || []).slice(0, 4).map(tag => (
                        <span key={tag} style={{
                          padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 600,
                          background: 'rgba(0,232,202,0.12)', color: 'var(--teal)',
                        }}>
                          {tag}
                        </span>
                      ))}
                      {(article.finding_tags || []).length > 4 && (
                        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                          +{article.finding_tags.length - 4}
                        </span>
                      )}
                    </div>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {article.best_practices.map((bp, i) => (
                      <li key={i} style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>{bp}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
