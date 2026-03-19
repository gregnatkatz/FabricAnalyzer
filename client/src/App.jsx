import React, { useState, useCallback, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import ConnectTab from './components/ConnectTab';
import TracesTab from './components/TracesTab';
import WorkflowTab from './components/WorkflowTab';
import FindingsTab from './components/FindingsTab';
import SimulationTab from './components/SimulationTab';
import ValidationTab from './components/ValidationTab';
import ArtifactsTab from './components/ArtifactsTab';
import ReportView from './report/ReportView';
import StatusHeader from './components/StatusHeader';

const TABS = [
  { id: 'connect', label: 'Connect', icon: '🔌' },
  { id: 'traces', label: 'Traces', icon: '📊' },
  { id: 'workflow', label: 'Workflow', icon: '⚙️' },
  { id: 'findings', label: 'Findings', icon: '🔍' },
  { id: 'simulation', label: 'Simulation', icon: '📈' },
  { id: 'validation', label: 'Validation', icon: '✓' },
  { id: 'artifacts', label: 'Artifacts', icon: '📄' },
];

function App() {
  const [activeTab, setActiveTab] = useState('connect');
  const [sessionState, setSessionState] = useState({
    connected: false,
    user: null,
    workspaceId: null,
    modelId: null,
    modelName: null,
    agentId: null,
    sessionId: null,
    dbPath: null,
    domain: null,
    traces: [],
    findings: [],
    agentResults: [],
    simulationResults: null,
    monteCarloResults: null,
    validationResults: null,
    analysisComplete: false,
    validationComplete: false,
    collectionComplete: false,
    pipelineLog: [],
    sampleMode: false,
  });

  const updateSession = useCallback((updates) => {
    setSessionState(prev => ({ ...prev, ...updates }));
  }, []);

  const handleReset = useCallback(async (scope = 'full') => {
    const confirmed = window.confirm(
      scope === 'full'
        ? 'Full Reset: This will delete all collected data, findings, and synthetic data. Continue?'
        : scope === 'findings_only'
        ? 'Reset Findings: This will clear all analysis findings. Collected data will remain. Continue?'
        : 'Reset UI: This will refresh the display. All data remains. Continue?'
    );
    if (!confirmed) return;

    try {
      await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope, sessionId: sessionState.sessionId }),
      });

      if (scope === 'full') {
        setSessionState({
          connected: false,
          user: null,
          workspaceId: null,
          modelId: null,
          modelName: null,
          agentId: null,
          sessionId: null,
          dbPath: null,
          domain: null,
          traces: [],
          findings: [],
          agentResults: [],
          simulationResults: null,
          monteCarloResults: null,
          validationResults: null,
          analysisComplete: false,
          validationComplete: false,
          collectionComplete: false,
          pipelineLog: [],
          sampleMode: false,
        });
        setActiveTab('connect');
      } else if (scope === 'findings_only') {
        updateSession({
          findings: [],
          agentResults: [],
          simulationResults: null,
          monteCarloResults: null,
          validationResults: null,
          analysisComplete: false,
          validationComplete: false,
          pipelineLog: [],
        });
      }
    } catch (err) {
      console.error('Reset failed:', err);
    }
  }, [sessionState.sessionId, updateSession]);

  const renderTab = () => {
    switch (activeTab) {
      case 'connect':
        return <ConnectTab session={sessionState} updateSession={updateSession} onNavigate={setActiveTab} />;
      case 'traces':
        return <TracesTab session={sessionState} />;
      case 'workflow':
        return <WorkflowTab session={sessionState} updateSession={updateSession} />;
      case 'findings':
        return <FindingsTab session={sessionState} />;
      case 'simulation':
        return <SimulationTab session={sessionState} updateSession={updateSession} />;
      case 'validation':
        return <ValidationTab session={sessionState} updateSession={updateSession} />;
      case 'artifacts':
        return <ArtifactsTab session={sessionState} />;
      default:
        return null;
    }
  };

  return (
    <Routes>
      <Route path="/report" element={<ReportView session={sessionState} />} />
      <Route
        path="*"
        element={
          <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 32px' }}>
            {/* Header */}
            <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--teal)', letterSpacing: '-0.02em' }}>
                  Fabric Data Agent Analyzer
                </h1>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  {sessionState.modelName
                    ? `${sessionState.domain || 'Unknown'} · ${sessionState.modelName}`
                    : 'Connect to a workspace or load sample data'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <StatusHeader session={sessionState} />
                {sessionState.user && (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', marginRight: 4 }}>
                    {sessionState.user}
                  </span>
                )}
                <button className="btn-secondary" onClick={() => handleReset('full')} style={{ fontSize: 12, padding: '6px 12px' }}>
                  Reset
                </button>
              </div>
            </header>

            {/* Tab Bar */}
            <nav className="tab-bar" style={{ marginBottom: 24 }}>
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            {/* Tab Content */}
            <main>{renderTab()}</main>
          </div>
        }
      />
    </Routes>
  );
}

export default App;
