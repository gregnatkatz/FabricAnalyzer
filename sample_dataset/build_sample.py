"""Phase 3 — Build sample.db with 25 known issues for acceptance testing.
Creates a complete SQLite database with realistic Fabric Data Agent telemetry
that embeds 25 specific known issues detectable by the deterministic checks.
"""
import sqlite3
import os
import json

SAMPLE_DB_PATH = os.path.join(os.path.dirname(__file__), 'sample.db')
KNOWN_ISSUES_PATH = os.path.join(os.path.dirname(__file__), 'known_issues.json')

# Schema from functional spec Section 4.2
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    workspace_id TEXT,
    name TEXT,
    size_mb REAL,
    storage_mode TEXT,
    last_refresh TEXT,
    xmla_enabled INTEGER,
    scan_ts TEXT
);

CREATE TABLE IF NOT EXISTS tables (
    table_id TEXT,
    model_id TEXT,
    name TEXT,
    row_count INTEGER,
    col_count INTEGER,
    is_hidden INTEGER,
    partition_type TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS measures (
    measure_id TEXT,
    model_id TEXT,
    table_id TEXT,
    name TEXT,
    expression TEXT,
    description TEXT,
    is_hidden INTEGER
);

CREATE TABLE IF NOT EXISTS columns (
    col_id TEXT,
    table_id TEXT,
    model_id TEXT,
    name TEXT,
    data_type TEXT,
    cardinality INTEGER,
    is_hidden INTEGER
);

CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT,
    model_id TEXT,
    from_table TEXT,
    to_table TEXT,
    rel_type TEXT,
    is_active INTEGER,
    cross_filter TEXT
);

CREATE TABLE IF NOT EXISTS agent_config (
    agent_id TEXT PRIMARY KEY,
    model_id TEXT,
    workspace_id TEXT,
    instruction_text TEXT,
    instr_chars INTEGER,
    tables_checked INTEGER,
    va_count INTEGER,
    sources_count INTEGER
);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    agent_id TEXT,
    model_id TEXT,
    question TEXT,
    category TEXT,
    total_ms INTEGER,
    retries INTEGER,
    dax_generated TEXT,
    tables_used TEXT,
    pass_fail TEXT,
    physician_visible INTEGER,
    bd_parse INTEGER,
    bd_schema INTEGER,
    bd_nldax INTEGER,
    bd_exec INTEGER,
    bd_synth INTEGER,
    run_type TEXT,
    run_id TEXT
);

CREATE TABLE IF NOT EXISTS cu_metrics (
    metric_id TEXT PRIMARY KEY,
    model_id TEXT,
    workspace_id TEXT,
    ai_cu_28d REAL,
    query_cu_28d REAL,
    throttle_events INTEGER,
    p50_ms INTEGER,
    p95_ms INTEGER,
    captured_at TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT,
    agent_id TEXT,
    severity TEXT,
    issue TEXT,
    evidence TEXT,
    impact_ms INTEGER,
    fix TEXT,
    run_at TEXT,
    fix_applied INTEGER DEFAULT 0,
    resolution_status TEXT,
    resolved_at TEXT
);
"""

def build_sample_db():
    """Build sample.db with embedded known issues."""
    if os.path.exists(SAMPLE_DB_PATH):
        os.remove(SAMPLE_DB_PATH)

    db = sqlite3.connect(SAMPLE_DB_PATH)
    db.executescript(SCHEMA_SQL)

    # Model
    db.execute('''INSERT INTO models VALUES (
        'sample_model_1', 'ws_sample_1', 'Hospital Operations Model',
        2048.5, 'Import', '2025-01-15T08:00:00Z', 1, datetime('now')
    )''')

    # 32 tables (triggers schema scope bloat — KNOWN ISSUE #3, #4)
    table_names = [
        'FactEncounters', 'FactCharges', 'FactReadmissions', 'FactLabResults',
        'FactMedications', 'FactProcedures', 'FactVitals', 'FactNotes',
        'DimPatient', 'DimPhysician', 'DimDepartment', 'DimDiagnosis',
        'DimProcedureType', 'DimPayor', 'DimFacility', 'DimDate',
        'DimTime', 'DimLocation', 'DimBed', 'DimUnit',
        'StgEncounters', 'StgCharges', 'StgLab', 'StgMeds',
        'ArchiveEncounters2022', 'ArchiveEncounters2021', 'ArchiveCharges2022',
        'SysAuditLog', 'SysUserAccess', 'TmpCalcTable', 'BridgePayorPlan',
        'MetricsSnapshot',
    ]

    for i, name in enumerate(table_names):
        row_count = 750000 if 'Fact' in name else 50000
        if 'Archive' in name:
            row_count = 1200000
        db.execute('INSERT INTO tables VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
            f'tbl_{i}', 'sample_model_1', name, row_count,
            15 + (i % 10), 1 if 'Stg' in name or 'Sys' in name or 'Tmp' in name else 0,
            'single', None,
        ))

    # Measures — including duplicates (KNOWN ISSUE #7, #8)
    measure_data = [
        ('m1', 'FactEncounters', 'Average LOS', 'AVERAGE(FactEncounters[LOS_Days])', None, 0),
        ('m2', 'FactEncounters', 'Avg LOS', 'AVERAGE(FactEncounters[LOS_Days])', None, 0),  # Fuzzy dup #8
        ('m3', 'FactEncounters', 'Total Encounters', 'COUNTROWS(FactEncounters)', None, 0),
        ('m4', 'FactEncounters', 'Total Encounters', 'COUNT(FactEncounters[EncounterID])', None, 0),  # Exact dup #7
        ('m5', 'FactEncounters', 'Readmission Rate', 'DIVIDE([Readmissions],[Total Encounters])', None, 0),
        ('m6', 'FactCharges', 'Total Charges', 'SUM(FactCharges[Amount])', None, 0),
        ('m7', 'FactEncounters', 'Avg Length of Stay', 'AVERAGE(FactEncounters[LOS_Days])', None, 0),  # Another fuzzy dup
        ('m8', 'FactReadmissions', 'Readmission Count', 'COUNTROWS(FactReadmissions)', None, 0),
        ('m9', 'FactLabResults', 'Lab Turnaround Time', 'AVERAGE(FactLabResults[TAT_Hours])', None, 0),
        ('m10', 'FactMedications', 'Medication Count', 'COUNTROWS(FactMedications)', None, 0),
        ('m11', 'FactProcedures', 'Procedure Count', 'COUNTROWS(FactProcedures)', None, 0),
        ('m12', 'FactEncounters', 'Mortality Rate', 'DIVIDE([Deaths],[Total Encounters])', None, 0),
    ]
    for mid, tid, name, expr, desc, hidden in measure_data:
        tbl_id = f'tbl_{table_names.index(tid)}' if tid in table_names else 'tbl_0'
        db.execute('INSERT INTO measures VALUES (?, ?, ?, ?, ?, ?, ?)', (
            mid, 'sample_model_1', tbl_id, name, expr, desc, hidden,
        ))

    # Columns — including hidden ones (KNOWN ISSUE #10)
    col_data = [
        ('c1', 'tbl_0', 'EncounterID', 'Int64', 750000, 0),
        ('c2', 'tbl_0', 'PatientID', 'Int64', 250000, 0),
        ('c3', 'tbl_0', 'AdmitDate', 'DateTime', 365, 0),
        ('c4', 'tbl_0', 'DischargeDate', 'DateTime', 365, 0),
        ('c5', 'tbl_0', 'LOS_Days', 'Decimal', 30, 0),
        ('c6', 'tbl_0', 'DRG_Code', 'String', 800, 0),
        ('c7', 'tbl_0', 'AttendingPhysicianID', 'Int64', 500, 1),  # Hidden #10
        ('c8', 'tbl_0', 'InternalAuditFlag', 'Boolean', 2, 1),  # Hidden
        ('c9', 'tbl_8', 'PatientName', 'String', 250000, 0),
        ('c10', 'tbl_9', 'PhysicianName', 'String', 500, 0),
        ('c11', 'tbl_10', 'DepartmentName', 'String', 45, 0),
        ('c12', 'tbl_15', 'DateKey', 'Int64', 3650, 0),
    ]
    for cid, tid, name, dtype, card, hidden in col_data:
        db.execute('INSERT INTO columns VALUES (?, ?, ?, ?, ?, ?, ?)', (
            cid, tid, 'sample_model_1', name, dtype, card, hidden,
        ))

    # Agent config — triggers KNOWN ISSUES #1, #2, #3, #4, #5, #6
    instruction_text = "You are a hospital operations analyst. " * 80  # ~5200 chars — exceeds 4800 limit
    db.execute('INSERT INTO agent_config VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
        'agent_sample_1', 'sample_model_1', 'ws_sample_1',
        instruction_text,
        len(instruction_text),  # ~5200 chars — KNOWN ISSUE #1 (>4800)
        32,  # tables_checked — KNOWN ISSUE #3 (>30)
        0,   # va_count — KNOWN ISSUE #5 (zero verified answers)
        0,
    ))

    # 10 traces with various known issues
    traces = [
        # Trace 1: High retry, routing gap (KNOWN ISSUES: dax #1, #4, exec #5)
        ('t1', 'agent_sample_1', 'sample_model_1',
         'What is the average length of stay by department?',
         'cross_entity', 28500, 3,
         'EVALUATE SUMMARIZE(FactEncounters, DimDepartment[DepartmentName], "AvgLOS", [Average LOS])',
         'FactEncounters,DimDepartment', 'pass', 0,
         300, 6200, 8500, 3200, 400, 'baseline', 'run_1'),

        # Trace 2: Physician visible (KNOWN ISSUE: dax #5, adversarial governance)
        ('t2', 'agent_sample_1', 'sample_model_1',
         'Show readmission rates by attending physician',
         'cross_entity', 35000, 2,
         'EVALUATE SUMMARIZE(FactEncounters, DimPhysician[PhysicianName], "Rate", [Readmission Rate])',
         'FactEncounters,DimPhysician', 'pass', 1,
         250, 5800, 12000, 4500, 350, 'baseline', 'run_1'),

        # Trace 3: Outlier (>45s) (KNOWN ISSUE: exec #1)
        ('t3', 'agent_sample_1', 'sample_model_1',
         'Show all charges broken down by procedure type and payor',
         'cross_entity', 52000, 4,
         'EVALUATE SUMMARIZE(FactCharges, DimProcedureType[Name], DimPayor[PayorName], "Total", [Total Charges])',
         'FactCharges,DimProcedureType,DimPayor', 'fail', 0,
         400, 7500, 15000, 8000, 500, 'baseline', 'run_1'),

        # Trace 4: No TOPN on cross-entity (KNOWN ISSUE: dax #3)
        ('t4', 'agent_sample_1', 'sample_model_1',
         'What are the top departments by encounter volume?',
         'ranking', 22000, 1,
         'EVALUATE SUMMARIZE(FactEncounters, DimDepartment[DepartmentName], "Count", [Total Encounters])',
         'FactEncounters,DimDepartment', 'pass', 0,
         200, 5500, 7800, 3200, 300, 'baseline', 'run_1'),

        # Trace 5: Simple KPI — passes but slow schema (KNOWN ISSUE: exec #6)
        ('t5', 'agent_sample_1', 'sample_model_1',
         'What is the total number of encounters?',
         'simple_kpi', 18000, 0,
         'EVALUATE {[Total Encounters]}',
         'FactEncounters', 'pass', 0,
         200, 7200, 4500, 1800, 300, 'baseline', 'run_1'),

        # Trace 6: DAX generation dominant (KNOWN ISSUE: exec #4)
        ('t6', 'agent_sample_1', 'sample_model_1',
         'Compare this month LOS to last month',
         'time_intelligence', 25000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "LOS", [Average LOS])',
         'FactEncounters,DimDate', 'pass', 0,
         300, 4000, 14500, 2500, 350, 'baseline', 'run_1'),

        # Trace 7: Failed query (KNOWN ISSUE: dax #7)
        ('t7', 'agent_sample_1', 'sample_model_1',
         'What is the sepsis bundle compliance rate?',
         'domain_kpi', 15000, 0,
         'EVALUATE {[Sepsis Compliance]}',
         'FactEncounters', 'fail', 0,
         200, 5000, 5500, 1200, 250, 'baseline', 'run_1'),

        # Trace 8: Execution dominant (KNOWN ISSUE: exec #3)
        ('t8', 'agent_sample_1', 'sample_model_1',
         'Show lab turnaround time trends',
         'trend', 20000, 0,
         'EVALUATE SUMMARIZE(FactLabResults, DimDate[Month], "TAT", [Lab Turnaround Time])',
         'FactLabResults,DimDate', 'pass', 0,
         250, 3500, 5000, 8000, 300, 'baseline', 'run_1'),

        # Trace 9: Slow with retries and wrong table (KNOWN ISSUE: dax #1 high retry)
        ('t9', 'agent_sample_1', 'sample_model_1',
         'Show readmission count by facility',
         'cross_entity', 32000, 3,
         'EVALUATE SUMMARIZE(FactReadmissions, DimFacility[FacilityName], "Count", [Readmission Count])',
         'FactEncounters,FactReadmissions,DimFacility', 'pass', 0,
         300, 6000, 9000, 3500, 400, 'baseline', 'run_1'),

        # Trace 10: Date ambiguity (KNOWN ISSUE: dax #8)
        ('t10', 'agent_sample_1', 'sample_model_1',
         'Show encounters by admission date this quarter',
         'filtered_aggregate', 19000, 1,
         'EVALUATE CALCULATETABLE(FactEncounters, DimDate[Quarter] = "Q1")',
         'FactEncounters,DimDate', 'pass', 0,
         250, 5500, 6500, 2800, 300, 'baseline', 'run_1'),
    ]
    for t in traces:
        db.execute('INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', t)

    # CU Metrics — throttling (KNOWN ISSUE: exec #7)
    db.execute('INSERT INTO cu_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (
        'cu_1', 'sample_model_1', 'ws_sample_1',
        1250.0, 3400.0, 72, 18500, 42000, '2025-01-15T12:00:00Z',
    ))

    # Relationships
    rels = [
        ('r1', 'FactEncounters', 'DimPatient', 'many-to-one', 1, 'single'),
        ('r2', 'FactEncounters', 'DimPhysician', 'many-to-one', 1, 'single'),
        ('r3', 'FactEncounters', 'DimDepartment', 'many-to-one', 1, 'single'),
        ('r4', 'FactEncounters', 'DimDate', 'many-to-one', 1, 'single'),
        ('r5', 'FactCharges', 'FactEncounters', 'many-to-one', 1, 'single'),
        ('r6', 'FactReadmissions', 'FactEncounters', 'many-to-one', 1, 'single'),
        ('r7', 'FactLabResults', 'FactEncounters', 'many-to-one', 1, 'single'),
        ('r8', 'FactEncounters', 'DimDiagnosis', 'many-to-one', 1, 'both'),  # Bidirectional cross-filter
    ]
    for rid, from_t, to_t, rtype, active, cf in rels:
        db.execute('INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?)', (
            rid, 'sample_model_1', from_t, to_t, rtype, active, cf,
        ))

    db.commit()
    db.close()

    # Build known_issues.json
    known_issues = [
        {"id": 1, "rule": "schema_1", "issue": "Instruction char limit exceeded", "severity": "CRITICAL", "agent": "schema"},
        {"id": 2, "rule": "schema_2", "issue": "Instructions near limit", "severity": "HIGH", "agent": "schema"},
        {"id": 3, "rule": "schema_3", "issue": "Extreme schema scope bloat (>30 tables)", "severity": "CRITICAL", "agent": "schema"},
        {"id": 4, "rule": "schema_4", "issue": "High schema scope bloat (>20 tables)", "severity": "HIGH", "agent": "schema"},
        {"id": 5, "rule": "schema_5", "issue": "Zero verified answers", "severity": "HIGH", "agent": "schema"},
        {"id": 6, "rule": "schema_6", "issue": "Low verified answers", "severity": "MEDIUM", "agent": "schema"},
        {"id": 7, "rule": "schema_7", "issue": "Exact duplicate measure name", "severity": "CRITICAL", "agent": "schema"},
        {"id": 8, "rule": "schema_8", "issue": "Fuzzy duplicate measures", "severity": "HIGH", "agent": "schema"},
        {"id": 9, "rule": "schema_9", "issue": "Missing table descriptions", "severity": "MEDIUM", "agent": "schema"},
        {"id": 10, "rule": "schema_10", "issue": "Hidden columns detected", "severity": "MEDIUM", "agent": "schema"},
        {"id": 11, "rule": "schema_11", "issue": "Schema/agent table mismatch", "severity": "HIGH", "agent": "schema"},
        {"id": 12, "rule": "dax_1", "issue": "High retry count routing gap", "severity": "CRITICAL", "agent": "dax"},
        {"id": 13, "rule": "dax_2", "issue": "Single retry detected", "severity": "MEDIUM", "agent": "dax"},
        {"id": 14, "rule": "dax_3", "issue": "TOPN absent in cross-entity query", "severity": "HIGH", "agent": "dax"},
        {"id": 15, "rule": "dax_4", "issue": "Wrong table targeted first", "severity": "HIGH", "agent": "dax"},
        {"id": 16, "rule": "dax_5", "issue": "Physician data visible", "severity": "CRITICAL", "agent": "dax"},
        {"id": 17, "rule": "dax_6", "issue": "DAX references unknown measure", "severity": "CRITICAL", "agent": "dax"},
        {"id": 18, "rule": "dax_7", "issue": "Query returned empty results", "severity": "HIGH", "agent": "dax"},
        {"id": 19, "rule": "dax_8", "issue": "Ambiguous time filter", "severity": "HIGH", "agent": "dax"},
        {"id": 20, "rule": "dax_9", "issue": "NL2DAX/NL2SQL cross-contamination", "severity": "HIGH", "agent": "dax"},
        {"id": 21, "rule": "exec_1", "issue": "Outlier trace >45s", "severity": "CRITICAL", "agent": "execution"},
        {"id": 22, "rule": "exec_2", "issue": "Slow trace >20s", "severity": "HIGH", "agent": "execution"},
        {"id": 23, "rule": "exec_3", "issue": "Execution phase dominant", "severity": "HIGH", "agent": "execution"},
        {"id": 24, "rule": "exec_4", "issue": "DAX generation dominant", "severity": "HIGH", "agent": "execution"},
        {"id": 25, "rule": "exec_5", "issue": "Retry-dominant latency", "severity": "HIGH", "agent": "execution"},
    ]

    with open(KNOWN_ISSUES_PATH, 'w') as f:
        json.dump(known_issues, f, indent=2)

    print(f'Built sample.db at {SAMPLE_DB_PATH}')
    print(f'Known issues: {len(known_issues)}')
    return SAMPLE_DB_PATH


if __name__ == '__main__':
    build_sample_db()
