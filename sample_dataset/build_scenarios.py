"""Build 20 diverse test scenarios covering all 8 domains and all 29 deterministic rules.

Each scenario has a unique semantic model, domain, agent configuration, and set of
latency issues. Together they exercise every rule in schema_checks.py (11), dax_checks.py (9),
and execution_checks.py (9) across realistic Fabric Data Agent configurations.

Scenarios:
  1. Revenue Cycle — Denial Management (instruction bloat + measure dupes)
  2. Revenue Cycle — AR Recovery (schema scope bloat + zero VA + throttling)
  3. Workforce — Staffing Optimization (near-limit instructions + low VA)
  4. Workforce — Agency Spend (high retries + physician visibility)
  5. Supply Chain — Inventory Management (extreme scope + missing descriptions)
  6. Supply Chain — Vendor Contract Analysis (DAX generation dominant + fuzzy dupes)
  7. Patient Experience — HCAHPS Scores (outlier traces + cross-entity TOPN absent)
  8. Patient Experience — Complaint Resolution (execution dominant + hidden columns)
  9. Clinical Quality — Sepsis Bundle (empty results + NL2DAX contamination)
 10. Clinical Quality — Antibiotic Stewardship (ambiguous time + wrong table)
 11. Operational — ED Throughput (retry dominant + schema lookup dominant)
 12. Operational — OR Utilization (Direct Lake + V-Order + framing risk)
 13. Financial — Budget Variance (near-limit + measure confusion + slow traces)
 14. Financial — DRG Contribution (extreme scope + outlier + physician)
 15. Clinical Inpatient — Readmission Risk (full issue spread — the "everything wrong" scenario)
 16. Clinical Inpatient — Mortality Review (governance-heavy + high retry)
 17. Revenue Cycle — Charge Capture (minimal issues — the "well-configured" scenario)
 18. Operational — Bed Management (Direct Lake + high CU + schema mismatch)
 19. Patient Experience — Survey Response (mixed SQL/DAX + measure not found)
 20. Workforce — Nursing Turnover (all execution rules triggered + scope bloat)
"""

import sqlite3
import os
import json

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios')

# Schema from build_sample.py
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY, workspace_id TEXT, name TEXT, size_mb REAL,
    storage_mode TEXT, last_refresh TEXT, xmla_enabled INTEGER, scan_ts TEXT
);
CREATE TABLE IF NOT EXISTS tables (
    table_id TEXT, model_id TEXT, name TEXT, row_count INTEGER, col_count INTEGER,
    is_hidden INTEGER, partition_type TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS measures (
    measure_id TEXT, model_id TEXT, table_id TEXT, name TEXT, expression TEXT,
    description TEXT, is_hidden INTEGER
);
CREATE TABLE IF NOT EXISTS columns (
    col_id TEXT, table_id TEXT, model_id TEXT, name TEXT, data_type TEXT,
    cardinality INTEGER, is_hidden INTEGER
);
CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT, model_id TEXT, from_table TEXT, to_table TEXT, rel_type TEXT,
    is_active INTEGER, cross_filter TEXT
);
CREATE TABLE IF NOT EXISTS agent_config (
    agent_id TEXT PRIMARY KEY, model_id TEXT, workspace_id TEXT, instruction_text TEXT,
    instr_chars INTEGER, tables_checked INTEGER, va_count INTEGER, sources_count INTEGER
);
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY, agent_id TEXT, model_id TEXT, question TEXT,
    category TEXT, total_ms INTEGER, retries INTEGER, dax_generated TEXT,
    tables_used TEXT, pass_fail TEXT, physician_visible INTEGER,
    bd_parse INTEGER, bd_schema INTEGER, bd_nldax INTEGER, bd_exec INTEGER,
    bd_synth INTEGER, bd_other INTEGER DEFAULT 0,
    run_type TEXT, run_id TEXT
);
CREATE TABLE IF NOT EXISTS cu_metrics (
    metric_id TEXT PRIMARY KEY, model_id TEXT, workspace_id TEXT, ai_cu_consumed REAL,
    query_cu_consumed REAL, throttle_state INTEGER, p50_ms INTEGER, p95_ms INTEGER,
    captured_at TEXT
);
CREATE TABLE IF NOT EXISTS column_stats (
    col_stat_id TEXT PRIMARY KEY, model_id TEXT, table_name TEXT,
    column_name TEXT, cardinality INTEGER, data_size_mb REAL,
    segment_count INTEGER, captured_at TEXT
);
CREATE TABLE IF NOT EXISTS relationship_stats (
    rel_stat_id TEXT PRIMARY KEY, model_id TEXT, from_table TEXT,
    to_table TEXT, from_cardinality INTEGER, to_cardinality INTEGER,
    cross_filter TEXT, is_active INTEGER, captured_at TEXT
);
CREATE TABLE IF NOT EXISTS findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, agent_id TEXT,
    severity TEXT, issue TEXT, evidence TEXT, impact_ms INTEGER, fix TEXT,
    run_at TEXT, fix_applied INTEGER DEFAULT 0, resolution_status TEXT, resolved_at TEXT
);
"""


def _build_db(scenario_id, model_name, workspace_name, domain, storage_mode,
              table_defs, measure_defs, column_defs, relationship_defs,
              agent_config, traces, cu_metrics, model_size_mb=1024.0):
    """Build a scenario database with the given configuration."""
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    db_path = os.path.join(SCENARIOS_DIR, f'scenario_{scenario_id:02d}.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA_SQL)

    model_id = f'model_s{scenario_id:02d}'
    ws_id = f'ws_s{scenario_id:02d}'

    # Model
    db.execute('INSERT INTO models VALUES (?,?,?,?,?,?,?,datetime("now"))',
               (model_id, ws_id, model_name, model_size_mb, storage_mode, '2025-03-01T08:00:00Z', 1))

    # Tables
    for i, (name, row_count, is_hidden, desc) in enumerate(table_defs):
        db.execute('INSERT INTO tables VALUES (?,?,?,?,?,?,?,?)',
                   (f'tbl_{i}', model_id, name, row_count, 12 + (i % 8), is_hidden, 'single', desc))

    # Measures
    for i, (tbl_name, mname, expr, desc, is_hidden) in enumerate(measure_defs):
        tbl_idx = next((j for j, t in enumerate(table_defs) if t[0] == tbl_name), 0)
        db.execute('INSERT INTO measures VALUES (?,?,?,?,?,?,?)',
                   (f'm{i}', model_id, f'tbl_{tbl_idx}', mname, expr, desc, is_hidden))

    # Columns
    for i, (tbl_name, col_name, dtype, card, is_hidden) in enumerate(column_defs):
        tbl_idx = next((j for j, t in enumerate(table_defs) if t[0] == tbl_name), 0)
        db.execute('INSERT INTO columns VALUES (?,?,?,?,?,?,?)',
                   (f'c{i}', f'tbl_{tbl_idx}', model_id, col_name, dtype, card, is_hidden))

    # Relationships
    for i, (from_t, to_t, rtype, cross_filter) in enumerate(relationship_defs):
        db.execute('INSERT INTO relationships VALUES (?,?,?,?,?,?,?)',
                   (f'r{i}', model_id, from_t, to_t, rtype, 1, cross_filter))

    # Agent config
    instr_text, instr_chars, tables_checked, va_count = agent_config
    db.execute('INSERT INTO agent_config VALUES (?,?,?,?,?,?,?,?)',
               (f'agent_s{scenario_id:02d}', model_id, ws_id, instr_text, instr_chars, tables_checked, va_count, 0))

    # Traces
    for i, t in enumerate(traces):
        q, cat, total_ms, retries, dax, tables_used, pf, phys_vis, bd_p, bd_s, bd_d, bd_e, bd_sy = t
        bd_other = max(0, total_ms - bd_p - bd_s - bd_d - bd_e - bd_sy)
        db.execute('INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (f't{i}', f'agent_s{scenario_id:02d}', model_id, q, cat, total_ms, retries,
                    dax, tables_used, pf, phys_vis, bd_p, bd_s, bd_d, bd_e, bd_sy, bd_other, 'baseline', 'run_1'))

    # CU Metrics
    ai_cu, query_cu, throttle, p50, p95 = cu_metrics
    db.execute('INSERT INTO cu_metrics VALUES (?,?,?,?,?,?,?,?,?)',
               (f'cu_s{scenario_id:02d}', model_id, ws_id, ai_cu, query_cu, throttle, p50, p95, '2025-03-01T12:00:00Z'))

    db.commit()
    db.close()
    return db_path


def build_scenario_01():
    """Revenue Cycle — Denial Management: instruction bloat + measure duplicates."""
    tables = [
        ('FactClaims', 2000000, 0, 'Claims transactions'),
        ('FactDenials', 800000, 0, 'Denial records'),
        ('FactPayments', 1500000, 0, 'Payment transactions'),
        ('FactAppeals', 200000, 0, None),
        ('DimPayer', 500, 0, 'Insurance payers'),
        ('DimProvider', 3000, 0, 'Billing providers'),
        ('DimCPT', 12000, 0, None),
        ('DimDiagnosis', 80000, 0, None),
        ('DimDate', 3650, 0, 'Calendar date dimension'),
        ('DimFacility', 45, 0, 'Hospital facilities'),
        ('StgClaimsRaw', 3000000, 0, None),
        ('StgDenialsRaw', 1200000, 0, None),
    ]
    measures = [
        ('FactClaims', 'Total Claims', 'COUNTROWS(FactClaims)', None, 0),
        ('FactClaims', 'Total Claims Amount', 'SUM(FactClaims[Amount])', None, 0),  # exact dup name variant
        ('FactDenials', 'Denial Rate', 'DIVIDE([Total Denials],[Total Claims])', None, 0),
        ('FactDenials', 'Total Denials', 'COUNTROWS(FactDenials)', None, 0),
        ('FactDenials', 'Denial Rate %', 'DIVIDE([Total Denials],[Total Claims])*100', None, 0),  # fuzzy dup
        ('FactPayments', 'Net Collection Rate', 'DIVIDE([Collected],[Allowed])', None, 0),
        ('FactPayments', 'Collection Rate', 'DIVIDE(SUM(FactPayments[Paid]),SUM(FactPayments[Billed]))', None, 0),  # fuzzy dup
        ('FactAppeals', 'Appeal Success Rate', 'DIVIDE([Won],[Total Appeals])', None, 0),
        ('FactClaims', 'AR Days', 'DIVIDE([Outstanding Balance],[Daily Revenue])', None, 0),
        ('FactClaims', 'Days in AR', 'DIVIDE(SUM(FactClaims[Balance]),AVERAGE(FactClaims[DailyRev]))', None, 0),  # fuzzy dup
    ]
    columns = [
        ('FactClaims', 'ClaimID', 'Int64', 2000000, 0),
        ('FactClaims', 'Amount', 'Decimal', 50000, 0),
        ('FactClaims', 'PayerID', 'Int64', 500, 0),
        ('FactDenials', 'DenialReason', 'String', 250, 0),
        ('DimPayer', 'PayerName', 'String', 500, 0),
        ('DimProvider', 'ProviderNPI', 'String', 3000, 1),  # hidden
    ]
    rels = [
        ('FactClaims', 'DimPayer', 'many-to-one', 'single'),
        ('FactClaims', 'DimDate', 'many-to-one', 'single'),
        ('FactDenials', 'FactClaims', 'many-to-one', 'single'),
        ('FactPayments', 'FactClaims', 'many-to-one', 'single'),
    ]
    # Instruction bloat: 5500 chars (exceeds 4800 limit)
    instr = "You are a revenue cycle denial management analyst. Focus on payer mix, denial trends, and AR aging. " * 55
    config = (instr, len(instr), len(tables), 0)  # zero VA
    traces = [
        ('What is the denial rate by payer?', 'cross_entity', 28000, 2,
         'EVALUATE SUMMARIZE(FactDenials, DimPayer[PayerName], "Rate", [Denial Rate])',
         'FactDenials,DimPayer', 'pass', 0, 300, 6500, 8000, 3500, 400),
        ('Show top denied CPT codes', 'ranking', 32000, 3,
         'EVALUATE SUMMARIZE(FactDenials, DimCPT[Code], "Count", COUNTROWS(FactDenials))',
         'FactDenials,DimCPT', 'pass', 0, 250, 5800, 12000, 4200, 350),
        ('What is the appeal success rate?', 'simple_kpi', 15000, 0,
         'EVALUATE {[Appeal Success Rate]}', 'FactAppeals', 'pass', 0, 200, 4500, 5000, 1800, 300),
        ('Compare denial rate this month vs last month', 'time_intelligence', 24000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "Rate", [Denial Rate])',
         'FactDenials,DimDate', 'pass', 0, 280, 5200, 9500, 3000, 320),
        ('Show AR days by facility', 'cross_entity', 22000, 1,
         'EVALUATE SUMMARIZE(FactClaims, DimFacility[FacilityName], "ARDays", [AR Days])',
         'FactClaims,DimFacility', 'pass', 0, 250, 5000, 7800, 3200, 300),
    ]
    cu = (980.0, 2800.0, 35, 14000, 32000)
    return _build_db(1, 'Revenue Cycle Denial Model', 'Denial Management WS', 'REVENUE_CYCLE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 3200.0)


def build_scenario_02():
    """Revenue Cycle — AR Recovery: schema scope bloat + zero VA + CU throttling."""
    tables = [
        ('FactAccountsReceivable', 3000000, 0, None),
        ('FactBilling', 2500000, 0, None),
        ('FactCollections', 1800000, 0, None),
        ('FactWriteOffs', 500000, 0, None),
        ('FactAdjustments', 900000, 0, None),
        ('DimPayer', 500, 0, None),
        ('DimPatient', 300000, 0, None),
        ('DimProvider', 3000, 0, None),
        ('DimServiceLine', 120, 0, None),
        ('DimDate', 3650, 0, None),
        ('DimFacility', 45, 0, None),
        ('DimInsurancePlan', 2000, 0, None),
        ('StgAR', 4000000, 0, None),
        ('StgBilling', 3500000, 0, None),
        ('StgCollections', 2000000, 0, None),
        ('ArchiveAR2022', 5000000, 0, None),
        ('ArchiveAR2021', 4500000, 0, None),
        ('TmpCalcAging', 100000, 0, None),
        ('BridgePayerPlan', 5000, 0, None),
        ('MetricsSnapshot', 365, 0, None),
        ('SysAuditLog', 1000000, 0, None),
        ('SysUserAccess', 500, 0, None),
        ('DimCostCenter', 200, 0, None),
        ('DimRevenueCode', 8000, 0, None),
        ('FactCharges', 2800000, 0, None),
        ('FactRefunds', 150000, 0, None),
        ('DimDRG', 1000, 0, None),
        ('DimModifier', 300, 0, None),
        ('FactStatements', 800000, 0, None),
        ('DimAging', 10, 0, None),
        ('FactFollowUp', 600000, 0, None),
        ('DimWorkQueue', 50, 0, None),
        ('StgRefunds', 200000, 0, None),
        ('ArchiveBilling2022', 3000000, 0, None),
        ('TmpPivotAging', 50000, 0, None),
    ]
    measures = [
        ('FactAccountsReceivable', 'Total AR Balance', 'SUM(FactAccountsReceivable[Balance])', None, 0),
        ('FactCollections', 'Net Collections', 'SUM(FactCollections[Amount])', None, 0),
        ('FactBilling', 'Gross Charges', 'SUM(FactBilling[ChargedAmount])', None, 0),
        ('FactWriteOffs', 'Write-Off Total', 'SUM(FactWriteOffs[Amount])', None, 0),
        ('FactAccountsReceivable', 'AR Over 90 Days', 'CALCULATE([Total AR Balance], DimAging[Bucket]="90+")', None, 0),
    ]
    columns = [
        ('FactAccountsReceivable', 'AccountID', 'Int64', 3000000, 0),
        ('FactAccountsReceivable', 'Balance', 'Decimal', 100000, 0),
        ('DimPayer', 'PayerName', 'String', 500, 0),
        ('DimPatient', 'MRN', 'String', 300000, 0),
    ]
    rels = [
        ('FactAccountsReceivable', 'DimPayer', 'many-to-one', 'single'),
        ('FactAccountsReceivable', 'DimDate', 'many-to-one', 'single'),
        ('FactBilling', 'DimPayer', 'many-to-one', 'single'),
    ]
    # 35 tables checked = extreme scope bloat; zero VA; normal instructions
    instr = "You are an AR recovery analyst. Track aging buckets, collection rates, and write-off patterns. " * 25
    config = (instr, len(instr), 35, 0)
    traces = [
        ('What is the total AR balance?', 'simple_kpi', 16000, 0,
         'EVALUATE {[Total AR Balance]}', 'FactAccountsReceivable', 'pass', 0, 200, 8500, 3000, 1500, 250),
        ('Show AR aging by payer', 'cross_entity', 30000, 2,
         'EVALUATE SUMMARIZE(FactAccountsReceivable, DimPayer[PayerName], "Balance", [Total AR Balance])',
         'FactAccountsReceivable,DimPayer', 'pass', 0, 300, 9200, 8500, 3500, 400),
        ('What percentage is over 90 days?', 'simple_kpi', 19000, 0,
         'EVALUATE {[AR Over 90 Days]}', 'FactAccountsReceivable', 'pass', 0, 250, 8800, 4200, 2000, 300),
        ('Show collection rate by service line', 'cross_entity', 35000, 3,
         'EVALUATE SUMMARIZE(FactCollections, DimServiceLine[Name], "Rate", [Net Collections])',
         'FactCollections,DimServiceLine', 'pass', 0, 280, 9500, 10000, 4500, 380),
        ('What are the top write-off reasons?', 'ranking', 25000, 1,
         'EVALUATE SUMMARIZE(FactWriteOffs, FactWriteOffs[Reason], "Total", [Write-Off Total])',
         'FactWriteOffs', 'pass', 0, 230, 8200, 7500, 3200, 320),
    ]
    cu = (1800.0, 5200.0, 85, 22000, 48000)  # High throttle
    return _build_db(2, 'AR Recovery Model', 'AR Recovery WS', 'REVENUE_CYCLE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 8500.0)


def build_scenario_03():
    """Workforce — Staffing Optimization: near-limit instructions + low VA."""
    tables = [
        ('FactShifts', 500000, 0, 'Staff shift records'),
        ('FactTimecards', 800000, 0, 'Timecard entries'),
        ('FactOvertimeEvents', 150000, 0, 'Overtime occurrences'),
        ('DimEmployee', 5000, 0, 'Employee master'),
        ('DimDepartment', 60, 0, 'Hospital departments'),
        ('DimShiftType', 8, 0, 'Shift type definitions'),
        ('DimDate', 3650, 0, 'Calendar dimension'),
        ('DimFacility', 12, 0, 'Facility locations'),
        ('DimJobRole', 150, 0, 'Job role classifications'),
        ('FactAgencyStaff', 50000, 0, None),
        ('DimAgency', 30, 0, None),
    ]
    measures = [
        ('FactShifts', 'HPPD', 'DIVIDE(SUM(FactShifts[Hours]),SUM(FactShifts[PatientDays]))', 'Hours per patient day', 0),
        ('FactShifts', 'Hours Per Patient Day', 'DIVIDE(SUM(FactShifts[Hours]),SUM(FactShifts[PatientDays]))', 'Alt HPPD', 0),  # fuzzy dup
        ('FactTimecards', 'Overtime Percentage', 'DIVIDE([OT Hours],[Total Hours])*100', None, 0),
        ('FactAgencyStaff', 'Agency Spend', 'SUM(FactAgencyStaff[Cost])', None, 0),
        ('FactShifts', 'Vacancy Rate', 'DIVIDE([Open Shifts],[Total Shifts])', None, 0),
    ]
    columns = [
        ('FactShifts', 'ShiftID', 'Int64', 500000, 0),
        ('FactShifts', 'Hours', 'Decimal', 24, 0),
        ('DimEmployee', 'EmployeeName', 'String', 5000, 0),
        ('DimEmployee', 'SSN', 'String', 5000, 1),  # hidden - sensitive
        ('DimDepartment', 'DeptName', 'String', 60, 0),
    ]
    rels = [
        ('FactShifts', 'DimEmployee', 'many-to-one', 'single'),
        ('FactShifts', 'DimDepartment', 'many-to-one', 'single'),
        ('FactShifts', 'DimDate', 'many-to-one', 'single'),
        ('FactTimecards', 'DimEmployee', 'many-to-one', 'single'),
    ]
    # 4200 chars = near limit (>4000 but <4800)
    instr = "You are a workforce analytics specialist. Analyze staffing patterns, HPPD metrics, overtime trends, and agency spend. " * 35
    config = (instr, len(instr), len(tables), 3)  # 3 VA = low
    traces = [
        ('What is the HPPD by department?', 'cross_entity', 18000, 0,
         'EVALUATE SUMMARIZE(FactShifts, DimDepartment[DeptName], "HPPD", [HPPD])',
         'FactShifts,DimDepartment', 'pass', 0, 200, 4200, 6500, 2500, 280),
        ('Show overtime trends by month', 'trend', 22000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "OT", [Overtime Percentage])',
         'FactTimecards,DimDate', 'pass', 0, 250, 4500, 8500, 3000, 300),
        ('What is total agency spend this quarter?', 'filtered_aggregate', 14000, 0,
         'EVALUATE CALCULATETABLE({[Agency Spend]}, DimDate[Quarter]="Q1")',
         'FactAgencyStaff,DimDate', 'pass', 0, 180, 3800, 4500, 2000, 250),
        ('Compare staffing levels day vs night', 'cross_entity', 20000, 1,
         'EVALUATE SUMMARIZE(FactShifts, DimShiftType[Name], "Count", COUNTROWS(FactShifts))',
         'FactShifts,DimShiftType', 'pass', 0, 220, 4000, 7200, 2800, 280),
        ('Show vacancy rate by facility', 'cross_entity', 19000, 0,
         'EVALUATE SUMMARIZE(FactShifts, DimFacility[Name], "Vacancy", [Vacancy Rate])',
         'FactShifts,DimFacility', 'pass', 0, 200, 4100, 6800, 2600, 270),
    ]
    cu = (450.0, 1200.0, 15, 9500, 22000)
    return _build_db(3, 'Workforce Staffing Model', 'Workforce WS', 'WORKFORCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1500.0)


def build_scenario_04():
    """Workforce — Agency Spend: high retries + physician visibility."""
    tables = [
        ('FactAgencyAssignments', 200000, 0, 'Agency staff assignments'),
        ('FactInvoices', 350000, 0, 'Agency invoices'),
        ('DimAgency', 45, 0, 'Staffing agencies'),
        ('DimEmployee', 5000, 0, None),
        ('DimDepartment', 60, 0, None),
        ('DimDate', 3650, 0, None),
        ('DimJobRole', 150, 0, None),
        ('DimShiftType', 8, 0, None),
        ('DimPhysician', 800, 0, 'Physician directory'),
    ]
    measures = [
        ('FactAgencyAssignments', 'Total Agency Hours', 'SUM(FactAgencyAssignments[Hours])', None, 0),
        ('FactInvoices', 'Total Agency Cost', 'SUM(FactInvoices[Amount])', None, 0),
        ('FactAgencyAssignments', 'Agency FTE', 'DIVIDE([Total Agency Hours],2080)', None, 0),
    ]
    columns = [
        ('FactAgencyAssignments', 'AssignmentID', 'Int64', 200000, 0),
        ('DimPhysician', 'PhysicianName', 'String', 800, 0),
        ('DimAgency', 'AgencyName', 'String', 45, 0),
    ]
    rels = [
        ('FactAgencyAssignments', 'DimAgency', 'many-to-one', 'single'),
        ('FactAgencyAssignments', 'DimDepartment', 'many-to-one', 'single'),
        ('FactInvoices', 'DimAgency', 'many-to-one', 'single'),
    ]
    instr = "You are an agency spend analyst. Track staffing costs and agency utilization. " * 30
    config = (instr, len(instr), len(tables), 2)
    traces = [
        ('What is the agency spend by department?', 'cross_entity', 35000, 4,
         'EVALUATE SUMMARIZE(FactInvoices, DimDepartment[DeptName], "Cost", [Total Agency Cost])',
         'FactAgencyAssignments,FactInvoices,DimDepartment', 'pass', 0, 300, 5500, 10000, 4500, 400),
        ('Show agency hours by physician supervisor', 'cross_entity', 28000, 2,
         'EVALUATE SUMMARIZE(FactAgencyAssignments, DimPhysician[PhysicianName], "Hours", [Total Agency Hours])',
         'FactAgencyAssignments,DimPhysician', 'pass', 1, 250, 5000, 9000, 3800, 350),
        ('What is the cost per agency FTE?', 'simple_kpi', 18000, 0,
         'EVALUATE {DIVIDE([Total Agency Cost],[Agency FTE])}',
         'FactInvoices,FactAgencyAssignments', 'pass', 0, 200, 4500, 6000, 2500, 300),
        ('Show top agencies by cost', 'ranking', 30000, 3,
         'EVALUATE SUMMARIZE(FactInvoices, DimAgency[AgencyName], "Cost", [Total Agency Cost])',
         'FactInvoices,DimAgency', 'pass', 0, 280, 5200, 11000, 4000, 380),
        ('Compare agency vs internal staffing by role', 'cross_entity', 25000, 1,
         'EVALUATE SUMMARIZE(FactAgencyAssignments, DimJobRole[Name], "Hours", [Total Agency Hours])',
         'FactAgencyAssignments,DimJobRole', 'pass', 0, 230, 4800, 8500, 3500, 330),
    ]
    cu = (620.0, 1800.0, 28, 12000, 30000)
    return _build_db(4, 'Agency Spend Model', 'Workforce WS', 'WORKFORCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 900.0)


def build_scenario_05():
    """Supply Chain — Inventory Management: extreme scope + missing descriptions."""
    table_names = [
        'FactPurchaseOrders', 'FactReceiving', 'FactInventoryLevels', 'FactConsumption',
        'FactReturns', 'FactBackorders', 'DimItem', 'DimVendor', 'DimCategory',
        'DimWarehouse', 'DimDate', 'DimFacility', 'DimGLAccount', 'DimBuyer',
        'StgPurchaseOrders', 'StgReceiving', 'StgInventory', 'ArchivePO2022',
        'ArchivePO2021', 'ArchiveInventory2022', 'TmpCalcPAR', 'SysVendorScorecard',
        'BridgeItemCategory', 'MetricsSnapshot', 'DimContractTerms', 'FactContractPricing',
        'DimUnitOfMeasure', 'FactCycleCount', 'DimStorageLocation', 'DimCostCenter',
        'FactExpiredItems', 'TmpReorderCalc',
    ]
    tables = [(name, 500000 if 'Fact' in name else 5000, 0, None) for name in table_names]  # All None desc
    measures = [
        ('FactInventoryLevels', 'Current Stock Value', 'SUM(FactInventoryLevels[Value])', None, 0),
        ('FactPurchaseOrders', 'PO Total', 'SUM(FactPurchaseOrders[Amount])', None, 0),
        ('FactConsumption', 'Usage Rate', 'DIVIDE([Consumed],[Available])', None, 0),
        ('FactBackorders', 'Backorder Count', 'COUNTROWS(FactBackorders)', None, 0),
    ]
    columns = [
        ('FactPurchaseOrders', 'POID', 'Int64', 500000, 0),
        ('DimItem', 'ItemName', 'String', 25000, 0),
        ('DimVendor', 'VendorName', 'String', 500, 0),
    ]
    rels = [
        ('FactPurchaseOrders', 'DimVendor', 'many-to-one', 'single'),
        ('FactPurchaseOrders', 'DimItem', 'many-to-one', 'single'),
        ('FactInventoryLevels', 'DimItem', 'many-to-one', 'single'),
    ]
    instr = "You are a supply chain inventory analyst. Monitor stock levels, reorder points, and vendor performance. " * 50
    config = (instr, len(instr), 32, 0)  # extreme scope, instruction bloat, zero VA
    traces = [
        ('What is the current inventory value by warehouse?', 'cross_entity', 26000, 1,
         'EVALUATE SUMMARIZE(FactInventoryLevels, DimWarehouse[Name], "Value", [Current Stock Value])',
         'FactInventoryLevels,DimWarehouse', 'pass', 0, 280, 8800, 7000, 3200, 350),
        ('Show top vendors by spend', 'ranking', 30000, 2,
         'EVALUATE SUMMARIZE(FactPurchaseOrders, DimVendor[VendorName], "Total", [PO Total])',
         'FactPurchaseOrders,DimVendor', 'pass', 0, 300, 9200, 9500, 3800, 380),
        ('What items are on backorder?', 'simple_kpi', 22000, 0,
         'EVALUATE {[Backorder Count]}', 'FactBackorders', 'pass', 0, 250, 8500, 5500, 2800, 300),
        ('Show consumption rate by category', 'cross_entity', 28000, 1,
         'EVALUATE SUMMARIZE(FactConsumption, DimCategory[Name], "Rate", [Usage Rate])',
         'FactConsumption,DimCategory', 'pass', 0, 270, 9000, 8200, 3500, 360),
        ('How many expired items by warehouse?', 'cross_entity', 24000, 0,
         'EVALUATE SUMMARIZE(FactExpiredItems, DimWarehouse[Name], "Count", COUNTROWS(FactExpiredItems))',
         'FactExpiredItems,DimWarehouse', 'pass', 0, 260, 8700, 6800, 3100, 340),
    ]
    cu = (750.0, 2100.0, 42, 16000, 35000)
    return _build_db(5, 'Inventory Management Model', 'Supply Chain WS', 'SUPPLY_CHAIN',
                     'Import', tables, measures, columns, rels, config, traces, cu, 4500.0)


def build_scenario_06():
    """Supply Chain — Vendor Contract Analysis: DAX generation dominant + fuzzy dupes."""
    tables = [
        ('FactContracts', 100000, 0, 'Vendor contracts'),
        ('FactPurchaseOrders', 800000, 0, 'Purchase orders'),
        ('FactInvoices', 600000, 0, 'Vendor invoices'),
        ('DimVendor', 2000, 0, 'Vendor master'),
        ('DimItem', 25000, 0, 'Item catalog'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimContractType', 15, 0, 'Contract types'),
        ('DimFacility', 45, 0, None),
    ]
    measures = [
        ('FactContracts', 'Contract Value', 'SUM(FactContracts[Value])', None, 0),
        ('FactContracts', 'Total Contract Value', 'SUM(FactContracts[TotalValue])', None, 0),  # fuzzy dup
        ('FactContracts', 'Contract Compliance', 'DIVIDE([In Compliance],[Total Contracts])', None, 0),
        ('FactContracts', 'Compliance Rate', 'DIVIDE([Compliant],[Total Contracts])*100', None, 0),  # fuzzy dup
        ('FactPurchaseOrders', 'PO Spend', 'SUM(FactPurchaseOrders[Amount])', None, 0),
        ('FactPurchaseOrders', 'Purchase Order Spend', 'SUM(FactPurchaseOrders[TotalAmount])', None, 0),  # fuzzy dup
        ('FactInvoices', 'Invoice Total', 'SUM(FactInvoices[Amount])', None, 0),
    ]
    columns = [
        ('FactContracts', 'ContractID', 'Int64', 100000, 0),
        ('DimVendor', 'VendorName', 'String', 2000, 0),
        ('DimContractType', 'TypeName', 'String', 15, 0),
    ]
    rels = [
        ('FactContracts', 'DimVendor', 'many-to-one', 'single'),
        ('FactPurchaseOrders', 'DimVendor', 'many-to-one', 'single'),
        ('FactInvoices', 'DimVendor', 'many-to-one', 'single'),
    ]
    instr = "You are a vendor contract analyst. Evaluate contract compliance, spend vs contract values. " * 20
    config = (instr, len(instr), len(tables), 4)  # near low VA threshold
    traces = [
        ('What is the total contract value by vendor?', 'cross_entity', 25000, 0,
         'EVALUATE SUMMARIZE(FactContracts, DimVendor[VendorName], "Value", [Contract Value])',
         'FactContracts,DimVendor', 'pass', 0, 250, 3500, 15000, 2500, 300),  # DAX dominant
        ('Show compliance rate by contract type', 'cross_entity', 28000, 1,
         'EVALUATE SUMMARIZE(FactContracts, DimContractType[TypeName], "Compliance", [Contract Compliance])',
         'FactContracts,DimContractType', 'pass', 0, 270, 3800, 16500, 2800, 330),  # DAX dominant
        ('Compare actual spend vs contract value', 'cross_entity', 30000, 0,
         'EVALUATE SUMMARIZE(FactPurchaseOrders, DimVendor[VendorName], "Spend", [PO Spend], "Contract", [Contract Value])',
         'FactPurchaseOrders,FactContracts,DimVendor', 'pass', 0, 280, 3500, 18000, 3000, 350),  # DAX dominant
        ('What vendors have the most invoices?', 'ranking', 22000, 0,
         'EVALUATE SUMMARIZE(FactInvoices, DimVendor[VendorName], "Total", [Invoice Total])',
         'FactInvoices,DimVendor', 'pass', 0, 230, 3200, 12500, 2500, 280),
        ('Show spend trend by quarter', 'trend', 20000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Quarter], "Spend", [PO Spend])',
         'FactPurchaseOrders,DimDate', 'pass', 0, 220, 3100, 11000, 2200, 260),
    ]
    cu = (380.0, 950.0, 8, 10000, 24000)
    return _build_db(6, 'Vendor Contract Model', 'Supply Chain WS', 'SUPPLY_CHAIN',
                     'Import', tables, measures, columns, rels, config, traces, cu, 2100.0)


def build_scenario_07():
    """Patient Experience — HCAHPS Scores: outlier traces + cross-entity TOPN absent."""
    tables = [
        ('FactSurveyResponses', 500000, 0, 'HCAHPS survey responses'),
        ('FactComplaints', 80000, 0, 'Patient complaints'),
        ('FactRounding', 300000, 0, 'Nurse rounding records'),
        ('DimPatient', 200000, 0, 'Patient demographics'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimSurveyQuestion', 32, 0, 'HCAHPS questions'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimFacility', 45, 0, 'Facilities'),
        ('DimNurse', 2500, 0, None),
    ]
    measures = [
        ('FactSurveyResponses', 'HCAHPS Score', 'AVERAGE(FactSurveyResponses[Score])', None, 0),
        ('FactSurveyResponses', 'Top Box Rate', 'DIVIDE([TopBox],[TotalResponses])', None, 0),
        ('FactComplaints', 'Complaint Count', 'COUNTROWS(FactComplaints)', None, 0),
        ('FactRounding', 'Rounding Compliance', 'DIVIDE([Completed],[Expected])', None, 0),
    ]
    columns = [
        ('FactSurveyResponses', 'ResponseID', 'Int64', 500000, 0),
        ('FactSurveyResponses', 'Score', 'Decimal', 5, 0),
        ('DimPatient', 'PatientName', 'String', 200000, 0),
        ('DimDepartment', 'DeptName', 'String', 60, 0),
    ]
    rels = [
        ('FactSurveyResponses', 'DimPatient', 'many-to-one', 'single'),
        ('FactSurveyResponses', 'DimDepartment', 'many-to-one', 'single'),
        ('FactSurveyResponses', 'DimDate', 'many-to-one', 'single'),
        ('FactComplaints', 'DimDepartment', 'many-to-one', 'single'),
    ]
    instr = "You are a patient experience analyst. Track HCAHPS scores, complaint trends, and rounding compliance. " * 22
    config = (instr, len(instr), len(tables), 5)
    traces = [
        ('What are the HCAHPS scores by department?', 'cross_entity', 48000, 3,
         'EVALUATE SUMMARIZE(FactSurveyResponses, DimDepartment[DeptName], "Score", [HCAHPS Score])',
         'FactSurveyResponses,DimDepartment', 'pass', 0, 400, 5500, 15000, 8000, 500),  # outlier >45s
        ('Show complaint trends by month', 'trend', 52000, 4,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "Complaints", [Complaint Count])',
         'FactComplaints,DimDate', 'pass', 0, 450, 5800, 18000, 9500, 550),  # outlier >45s
        ('What is the top box rate by survey question?', 'cross_entity', 32000, 2,
         'EVALUATE SUMMARIZE(FactSurveyResponses, DimSurveyQuestion[QuestionText], "Rate", [Top Box Rate])',
         'FactSurveyResponses,DimSurveyQuestion', 'pass', 0, 300, 5200, 12000, 5500, 380),
        ('Show rounding compliance by nurse', 'cross_entity', 28000, 1,
         'EVALUATE SUMMARIZE(FactRounding, DimNurse[NurseName], "Compliance", [Rounding Compliance])',
         'FactRounding,DimNurse', 'pass', 0, 280, 4800, 10500, 4200, 350),
        ('Compare patient satisfaction by facility', 'cross_entity', 30000, 2,
         'EVALUATE SUMMARIZE(FactSurveyResponses, DimFacility[Name], "Score", [HCAHPS Score])',
         'FactSurveyResponses,DimFacility', 'pass', 0, 300, 5000, 11000, 4800, 370),
    ]
    cu = (520.0, 1500.0, 22, 14000, 35000)
    return _build_db(7, 'HCAHPS Patient Experience Model', 'Patient Experience WS', 'PATIENT_EXPERIENCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1800.0)


def build_scenario_08():
    """Patient Experience — Complaint Resolution: execution dominant + hidden columns."""
    tables = [
        ('FactComplaints', 120000, 0, 'Complaints filed'),
        ('FactResolutions', 100000, 0, 'Resolution outcomes'),
        ('FactCallCenter', 500000, 0, 'Call center interactions'),
        ('DimPatient', 200000, 0, 'Patient demographics'),
        ('DimCategory', 25, 0, 'Complaint categories'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimStaff', 3000, 0, 'Staff involved'),
        ('DimFacility', 45, 0, None),
    ]
    measures = [
        ('FactComplaints', 'Open Complaints', 'CALCULATE(COUNTROWS(FactComplaints), FactComplaints[Status]="Open")', None, 0),
        ('FactResolutions', 'Avg Resolution Days', 'AVERAGE(FactResolutions[DaysToResolve])', None, 0),
        ('FactCallCenter', 'Avg Wait Time', 'AVERAGE(FactCallCenter[WaitSeconds])', None, 0),
    ]
    columns = [
        ('FactComplaints', 'ComplaintID', 'Int64', 120000, 0),
        ('FactComplaints', 'InternalNotes', 'String', 100000, 1),  # hidden
        ('FactComplaints', 'StaffInvolvedID', 'Int64', 3000, 1),  # hidden
        ('DimPatient', 'PatientSSN', 'String', 200000, 1),  # hidden - sensitive
        ('DimStaff', 'StaffName', 'String', 3000, 0),
        ('DimCategory', 'CategoryName', 'String', 25, 0),
    ]
    rels = [
        ('FactComplaints', 'DimPatient', 'many-to-one', 'single'),
        ('FactComplaints', 'DimCategory', 'many-to-one', 'single'),
        ('FactResolutions', 'FactComplaints', 'many-to-one', 'single'),
    ]
    instr = "You are a complaint resolution analyst. Track complaint lifecycle and resolution metrics. " * 20
    config = (instr, len(instr), len(tables), 6)
    traces = [
        ('How many open complaints are there?', 'simple_kpi', 22000, 0,
         'EVALUATE {[Open Complaints]}', 'FactComplaints', 'pass', 0, 200, 3000, 4000, 10500, 280),  # exec dominant
        ('Show avg resolution time by category', 'cross_entity', 25000, 0,
         'EVALUATE SUMMARIZE(FactResolutions, DimCategory[CategoryName], "AvgDays", [Avg Resolution Days])',
         'FactResolutions,DimCategory', 'pass', 0, 230, 3200, 4500, 12000, 300),  # exec dominant
        ('What is the avg call center wait time?', 'simple_kpi', 20000, 0,
         'EVALUATE {[Avg Wait Time]}', 'FactCallCenter', 'pass', 0, 180, 2800, 3800, 9500, 260),  # exec dominant
        ('Show complaint trends by facility', 'cross_entity', 28000, 1,
         'EVALUATE SUMMARIZE(FactComplaints, DimFacility[Name], "Count", [Open Complaints])',
         'FactComplaints,DimFacility', 'pass', 0, 260, 3500, 5000, 13500, 320),  # exec dominant
        ('Compare resolution time this month vs last', 'time_intelligence', 24000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "AvgDays", [Avg Resolution Days])',
         'FactResolutions,DimDate', 'pass', 0, 240, 3100, 4200, 11200, 290),  # exec dominant
    ]
    cu = (350.0, 800.0, 12, 11000, 26000)
    return _build_db(8, 'Complaint Resolution Model', 'Patient Experience WS', 'PATIENT_EXPERIENCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1200.0)


def build_scenario_09():
    """Clinical Quality — Sepsis Bundle: empty results + NL2DAX contamination."""
    tables = [
        ('FactSepsisScreens', 200000, 0, 'Sepsis screening events'),
        ('FactBundleCompliance', 180000, 0, 'Bundle compliance records'),
        ('FactLactateResults', 300000, 0, 'Lactate lab results'),
        ('FactAntibioticAdmin', 250000, 0, 'Antibiotic administrations'),
        ('DimPatient', 150000, 0, 'Patient demographics'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimPhysician', 800, 0, 'Physician directory'),
        ('DimFacility', 45, 0, 'Facilities'),
    ]
    measures = [
        ('FactBundleCompliance', 'Bundle Compliance Rate', 'DIVIDE([Compliant],[Total Screens])', None, 0),
        ('FactSepsisScreens', 'Sepsis Screen Count', 'COUNTROWS(FactSepsisScreens)', None, 0),
        ('FactLactateResults', 'Avg Lactate Level', 'AVERAGE(FactLactateResults[Value])', None, 0),
        ('FactAntibioticAdmin', 'Time to Antibiotics', 'AVERAGE(FactAntibioticAdmin[MinutesToAdmin])', None, 0),
        ('FactBundleCompliance', 'Sepsis Mortality Rate', 'DIVIDE([SepsisDeaths],[SepsisCases])', None, 0),
    ]
    columns = [
        ('FactSepsisScreens', 'ScreenID', 'Int64', 200000, 0),
        ('FactLactateResults', 'Value', 'Decimal', 100, 0),
        ('DimPhysician', 'PhysicianName', 'String', 800, 0),
    ]
    rels = [
        ('FactSepsisScreens', 'DimPatient', 'many-to-one', 'single'),
        ('FactBundleCompliance', 'FactSepsisScreens', 'many-to-one', 'single'),
        ('FactLactateResults', 'DimPatient', 'many-to-one', 'single'),
        ('FactAntibioticAdmin', 'DimPatient', 'many-to-one', 'single'),
    ]
    instr = "You are a sepsis quality analyst. Monitor bundle compliance, lactate timing, and antibiotic stewardship. " * 20
    config = (instr, len(instr), len(tables), 2)
    traces = [
        ('What is the sepsis bundle compliance rate?', 'simple_kpi', 14000, 0,
         'EVALUATE {[Sepsis Compliance Not Found]}', 'FactBundleCompliance', 'fail', 0,
         200, 4200, 4500, 1500, 250),  # empty results + measure not found
        ('Show compliance by department', 'cross_entity', 18000, 0,
         'EVALUATE SUMMARIZE(FactBundleCompliance, DimDepartment[DeptName], "Rate", [Bundle Compliance Rate])',
         'FactBundleCompliance,DimDepartment', 'fail', 0, 220, 4500, 5500, 2000, 280),  # fail
        ('What is the avg time to antibiotics?', 'simple_kpi', 12000, 0,
         'EVALUATE {[Time to Antibiotics]}', 'FactAntibioticAdmin', 'pass', 0,
         180, 3800, 3500, 1200, 230),
        # NL2DAX contamination — mixed SQL + DAX patterns
        ('Show lactate results by patient', 'cross_entity', 22000, 1,
         'EVALUATE SUMMARIZE(FactLactateResults, SELECT DimPatient.PatientName FROM DimPatient WHERE PatientID IN (1,2,3), "Avg", [Avg Lactate Level])',
         'FactLactateResults,DimPatient', 'pass', 0, 250, 4800, 8000, 3000, 300),
        ('Compare sepsis mortality this year vs last', 'time_intelligence', 20000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Year], "Mortality", [Sepsis Mortality Rate])',
         'FactBundleCompliance,DimDate', 'pass', 0, 240, 4600, 7000, 2500, 280),
    ]
    cu = (420.0, 1100.0, 18, 10000, 24000)
    return _build_db(9, 'Sepsis Bundle Model', 'Clinical Quality WS', 'CLINICAL_QUALITY',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1400.0)


def build_scenario_10():
    """Clinical Quality — Antibiotic Stewardship: ambiguous time + wrong table."""
    tables = [
        ('FactAntibioticOrders', 400000, 0, 'Antibiotic prescriptions'),
        ('FactCultureResults', 350000, 0, 'Culture/sensitivity results'),
        ('FactSusceptibility', 500000, 0, 'Susceptibility patterns'),
        ('DimAntibiotic', 200, 0, 'Antibiotic formulary'),
        ('DimOrganism', 500, 0, 'Organism types'),
        ('DimPatient', 150000, 0, 'Patient demographics'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimPhysician', 800, 0, 'Prescribing physicians'),
    ]
    measures = [
        ('FactAntibioticOrders', 'DOT per 1000 Days', 'DIVIDE([Total DOT],[PatientDays])*1000', None, 0),
        ('FactAntibioticOrders', 'Days of Therapy', 'SUM(FactAntibioticOrders[DaysOfTherapy])', None, 0),
        ('FactCultureResults', 'Culture Positivity Rate', 'DIVIDE([Positive],[Total Cultures])', None, 0),
        ('FactSusceptibility', 'Resistance Rate', 'DIVIDE([Resistant],[Tested])', None, 0),
        ('FactAntibioticOrders', 'Appropriate Therapy Rate', 'DIVIDE([Appropriate],[Total Orders])', None, 0),
    ]
    columns = [
        ('FactAntibioticOrders', 'OrderID', 'Int64', 400000, 0),
        ('FactAntibioticOrders', 'OrderDate', 'DateTime', 365, 0),
        ('FactAntibioticOrders', 'StartDate', 'DateTime', 365, 0),  # ambiguous date fields
        ('FactAntibioticOrders', 'StopDate', 'DateTime', 365, 0),
        ('DimAntibiotic', 'AntibioticName', 'String', 200, 0),
        ('DimPhysician', 'PhysicianName', 'String', 800, 0),
    ]
    rels = [
        ('FactAntibioticOrders', 'DimAntibiotic', 'many-to-one', 'single'),
        ('FactAntibioticOrders', 'DimPhysician', 'many-to-one', 'single'),
        ('FactAntibioticOrders', 'DimDate', 'many-to-one', 'single'),
        ('FactCultureResults', 'DimOrganism', 'many-to-one', 'single'),
    ]
    instr = "You are an antibiotic stewardship analyst. Track DOT, culture results, and resistance patterns. " * 20
    config = (instr, len(instr), len(tables), 3)
    traces = [
        # Multiple date fields trigger ambiguous time filter
        ('Show DOT trends by order date this quarter', 'filtered_aggregate', 22000, 1,
         'EVALUATE CALCULATETABLE(SUMMARIZE(FactAntibioticOrders, DimDate[Month], "DOT", [DOT per 1000 Days]), DimDate[Quarter]="Q1")',
         'FactAntibioticOrders,DimDate', 'pass', 0, 250, 4500, 8000, 3200, 300),
        ('Show DOT by start date', 'trend', 24000, 2,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Date], "DOT", [Days of Therapy])',
         'FactAntibioticOrders,DimDate', 'pass', 0, 270, 4800, 9000, 3500, 320),
        ('Show DOT by stop date', 'trend', 26000, 2,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Date], "DOT", [Days of Therapy])',
         'FactAntibioticOrders,DimDate', 'pass', 0, 280, 5000, 9500, 3800, 340),
        ('What is the resistance rate by organism?', 'cross_entity', 20000, 1,
         'EVALUATE SUMMARIZE(FactSusceptibility, DimOrganism[Name], "Rate", [Resistance Rate])',
         'FactSusceptibility,DimOrganism', 'pass', 0, 230, 4200, 7000, 3000, 280),
        ('Show prescribing patterns by physician', 'cross_entity', 28000, 2,
         'EVALUATE SUMMARIZE(FactAntibioticOrders, DimPhysician[PhysicianName], "DOT", [DOT per 1000 Days])',
         'FactAntibioticOrders,DimPhysician', 'pass', 1, 260, 4600, 10000, 4000, 350),  # physician visible
    ]
    cu = (380.0, 950.0, 14, 11000, 28000)
    return _build_db(10, 'Antibiotic Stewardship Model', 'Clinical Quality WS', 'CLINICAL_QUALITY',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1600.0)


def build_scenario_11():
    """Operational — ED Throughput: retry dominant + schema lookup dominant."""
    tables = [
        ('FactEDVisits', 800000, 0, 'ED visit records'),
        ('FactTriage', 800000, 0, 'Triage assessments'),
        ('FactBoardingEvents', 300000, 0, 'Boarding time records'),
        ('DimPatient', 250000, 0, 'Patients'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimAcuity', 5, 0, 'ESI acuity levels'),
        ('DimFacility', 45, 0, 'Facilities'),
        ('DimDisposition', 10, 0, 'Discharge dispositions'),
        ('DimShift', 3, 0, 'Shift times'),
    ]
    measures = [
        ('FactEDVisits', 'Door to Doc', 'AVERAGE(FactEDVisits[DoorToDocMinutes])', None, 0),
        ('FactEDVisits', 'ED LOS', 'AVERAGE(FactEDVisits[EDLOSMinutes])', None, 0),
        ('FactEDVisits', 'LWBS Rate', 'DIVIDE([LWBS Count],[Total ED Visits])', None, 0),
        ('FactBoardingEvents', 'Avg Boarding Hours', 'AVERAGE(FactBoardingEvents[Hours])', None, 0),
        ('FactEDVisits', 'ED Volume', 'COUNTROWS(FactEDVisits)', None, 0),
    ]
    columns = [
        ('FactEDVisits', 'VisitID', 'Int64', 800000, 0),
        ('FactEDVisits', 'DoorToDocMinutes', 'Int64', 120, 0),
        ('DimAcuity', 'ESILevel', 'Int64', 5, 0),
        ('DimPatient', 'PatientName', 'String', 250000, 0),
    ]
    rels = [
        ('FactEDVisits', 'DimPatient', 'many-to-one', 'single'),
        ('FactEDVisits', 'DimAcuity', 'many-to-one', 'single'),
        ('FactEDVisits', 'DimDate', 'many-to-one', 'single'),
        ('FactTriage', 'FactEDVisits', 'many-to-one', 'single'),
    ]
    # High schema lookup due to many tables checked relative to actual
    instr = "You are an ED throughput analyst. Track door-to-doc, boarding times, and LWBS rates. " * 20
    config = (instr, len(instr), 28, 1)  # 28 tables checked (>20), only 1 VA
    traces = [
        ('What is the door-to-doc time by acuity?', 'cross_entity', 25000, 5,
         'EVALUATE SUMMARIZE(FactEDVisits, DimAcuity[ESILevel], "D2D", [Door to Doc])',
         'FactEDVisits,DimAcuity', 'pass', 0, 350, 10500, 3000, 2500, 400),  # retry dominant (5*3100=15500 > 25000*0.4=10000) + schema dominant
        ('Show LWBS rate by shift', 'cross_entity', 28000, 3,
         'EVALUATE SUMMARIZE(FactEDVisits, DimShift[Name], "LWBS", [LWBS Rate])',
         'FactEDVisits,DimShift', 'pass', 0, 300, 9800, 5500, 3200, 380),  # retry + schema dominant
        ('What is the avg boarding time?', 'simple_kpi', 24000, 2,
         'EVALUATE {[Avg Boarding Hours]}', 'FactBoardingEvents', 'pass', 0, 250, 9200, 5000, 2800, 320),
        ('Show ED volume by hour of day', 'trend', 26000, 3,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Hour], "Volume", [ED Volume])',
         'FactEDVisits,DimDate', 'pass', 0, 280, 9500, 5200, 3000, 350),  # retry + schema
        ('Compare door-to-doc by facility', 'cross_entity', 30000, 3,
         'EVALUATE SUMMARIZE(FactEDVisits, DimFacility[Name], "D2D", [Door to Doc])',
         'FactEDVisits,DimFacility', 'pass', 0, 320, 10200, 5800, 3400, 390),  # retry + schema
    ]
    cu = (680.0, 1900.0, 38, 15000, 34000)
    return _build_db(11, 'ED Throughput Model', 'Operational WS', 'OPERATIONAL',
                     'Import', tables, measures, columns, rels, config, traces, cu, 2200.0)


def build_scenario_12():
    """Operational — OR Utilization: Direct Lake + V-Order + framing risk."""
    tables = [
        ('FactSurgicalCases', 600000, 0, 'Surgical case records'),
        ('FactORBlocks', 200000, 0, 'OR block assignments'),
        ('FactTurnaroundTime', 500000, 0, 'Room turnover times'),
        ('DimSurgeon', 400, 0, 'Surgeon directory'),
        ('DimOR', 30, 0, 'Operating rooms'),
        ('DimProcedureType', 2000, 0, 'Procedure types'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimFacility', 45, 0, 'Facilities'),
        ('DimAnesthesiaType', 8, 0, 'Anesthesia types'),
    ]
    measures = [
        ('FactSurgicalCases', 'OR Utilization', 'DIVIDE([Used Minutes],[Available Minutes])', None, 0),
        ('FactSurgicalCases', 'Case Volume', 'COUNTROWS(FactSurgicalCases)', None, 0),
        ('FactTurnaroundTime', 'Avg Turnover', 'AVERAGE(FactTurnaroundTime[Minutes])', None, 0),
        ('FactSurgicalCases', 'First Case On-Time Start', 'DIVIDE([OnTime],[FirstCases])', None, 0),
    ]
    columns = [
        ('FactSurgicalCases', 'CaseID', 'Int64', 600000, 0),
        ('FactSurgicalCases', 'DurationMinutes', 'Int64', 480, 0),
        ('DimSurgeon', 'SurgeonName', 'String', 400, 0),
        ('DimOR', 'RoomName', 'String', 30, 0),
    ]
    rels = [
        ('FactSurgicalCases', 'DimSurgeon', 'many-to-one', 'single'),
        ('FactSurgicalCases', 'DimOR', 'many-to-one', 'single'),
        ('FactSurgicalCases', 'DimDate', 'many-to-one', 'single'),
        ('FactTurnaroundTime', 'DimOR', 'many-to-one', 'single'),
    ]
    instr = "You are an OR utilization analyst. Track utilization rates, turnover times, and scheduling efficiency. " * 18
    config = (instr, len(instr), len(tables), 4)
    traces = [
        ('What is the OR utilization by room?', 'cross_entity', 22000, 0,
         'EVALUATE SUMMARIZE(FactSurgicalCases, DimOR[RoomName], "Util", [OR Utilization])',
         'FactSurgicalCases,DimOR', 'pass', 0, 200, 3800, 5000, 8500, 280),
        ('Show avg turnover time by facility', 'cross_entity', 20000, 0,
         'EVALUATE SUMMARIZE(FactTurnaroundTime, DimFacility[Name], "Turnover", [Avg Turnover])',
         'FactTurnaroundTime,DimFacility', 'pass', 0, 180, 3500, 4500, 7800, 260),
        ('What is the first case on-time start rate?', 'simple_kpi', 18000, 0,
         'EVALUATE {[First Case On-Time Start]}', 'FactSurgicalCases', 'pass', 0, 170, 3200, 4000, 7200, 240),
        ('Show case volume by surgeon', 'cross_entity', 24000, 1,
         'EVALUATE SUMMARIZE(FactSurgicalCases, DimSurgeon[SurgeonName], "Volume", [Case Volume])',
         'FactSurgicalCases,DimSurgeon', 'pass', 0, 220, 4000, 5500, 9000, 300),
        ('Compare utilization weekday vs weekend', 'cross_entity', 26000, 1,
         'EVALUATE SUMMARIZE(FactSurgicalCases, DimDate[DayOfWeek], "Util", [OR Utilization])',
         'FactSurgicalCases,DimDate', 'pass', 0, 240, 4200, 5800, 9500, 320),
    ]
    cu = (550.0, 1400.0, 20, 12000, 28000)
    return _build_db(12, 'OR Utilization Model', 'Operational WS', 'OPERATIONAL',
                     'DirectLake', tables, measures, columns, rels, config, traces, cu, 3500.0)


def build_scenario_13():
    """Financial — Budget Variance: near-limit + measure confusion + slow traces."""
    tables = [
        ('FactBudget', 500000, 0, 'Budget line items'),
        ('FactActuals', 800000, 0, 'Actual expenses'),
        ('FactForecast', 300000, 0, 'Forecast entries'),
        ('DimCostCenter', 200, 0, 'Cost centers'),
        ('DimGLAccount', 5000, 0, 'GL accounts'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimFacility', 45, 0, None),
        ('DimFundingSource', 20, 0, None),
    ]
    measures = [
        ('FactBudget', 'Budget Amount', 'SUM(FactBudget[Amount])', None, 0),
        ('FactBudget', 'Budgeted Amount', 'SUM(FactBudget[BudgetedAmount])', None, 0),  # fuzzy dup
        ('FactActuals', 'Actual Spend', 'SUM(FactActuals[Amount])', None, 0),
        ('FactActuals', 'Actual Amount', 'SUM(FactActuals[SpendAmount])', None, 0),  # fuzzy dup
        ('FactBudget', 'Budget Variance', 'SUM(FactActuals[Amount])-SUM(FactBudget[Amount])', None, 0),
        ('FactBudget', 'Variance Amount', 'SUM(FactActuals[SpendAmount])-SUM(FactBudget[BudgetedAmount])', None, 0),  # fuzzy dup
        ('FactForecast', 'Forecast Amount', 'SUM(FactForecast[Amount])', None, 0),
        ('FactBudget', 'Margin', 'DIVIDE([Revenue]-[Actual Spend],[Revenue])', None, 0),
    ]
    columns = [
        ('FactBudget', 'BudgetID', 'Int64', 500000, 0),
        ('FactActuals', 'Amount', 'Decimal', 50000, 0),
        ('DimCostCenter', 'CostCenterName', 'String', 200, 0),
        ('DimGLAccount', 'AccountName', 'String', 5000, 0),
    ]
    rels = [
        ('FactBudget', 'DimCostCenter', 'many-to-one', 'single'),
        ('FactBudget', 'DimGLAccount', 'many-to-one', 'single'),
        ('FactActuals', 'DimCostCenter', 'many-to-one', 'single'),
        ('FactBudget', 'DimDate', 'many-to-one', 'single'),
    ]
    # Near instruction limit: ~4300 chars
    instr = "You are a financial budget analyst. Track variances, margins, and cost center performance against targets. " * 38
    config = (instr, len(instr), len(tables), 2)  # low VA
    traces = [
        ('What is the budget variance by cost center?', 'cross_entity', 32000, 2,
         'EVALUATE SUMMARIZE(FactBudget, DimCostCenter[CostCenterName], "Variance", [Budget Variance])',
         'FactBudget,FactActuals,DimCostCenter', 'pass', 0, 300, 5500, 10000, 5000, 380),
        ('Show actual vs budget by department', 'cross_entity', 35000, 2,
         'EVALUATE SUMMARIZE(FactActuals, DimDepartment[DeptName], "Actual", [Actual Spend], "Budget", [Budget Amount])',
         'FactActuals,FactBudget,DimDepartment', 'pass', 0, 320, 5800, 12000, 5500, 400),
        ('What is the operating margin?', 'simple_kpi', 28000, 1,
         'EVALUATE {[Margin]}', 'FactBudget', 'pass', 0, 250, 5000, 8500, 4500, 350),
        ('Compare forecast to actuals by GL account', 'cross_entity', 38000, 3,
         'EVALUATE SUMMARIZE(FactForecast, DimGLAccount[AccountName], "Forecast", [Forecast Amount])',
         'FactForecast,FactActuals,DimGLAccount', 'pass', 0, 340, 6200, 14000, 6000, 420),
        ('Show budget trends by month', 'trend', 24000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "Budget", [Budget Amount], "Actual", [Actual Spend])',
         'FactBudget,FactActuals,DimDate', 'pass', 0, 260, 5200, 8000, 3800, 320),
    ]
    cu = (480.0, 1300.0, 25, 13000, 32000)
    return _build_db(13, 'Budget Variance Model', 'Financial WS', 'FINANCIAL',
                     'Import', tables, measures, columns, rels, config, traces, cu, 2000.0)


def build_scenario_14():
    """Financial — DRG Contribution: extreme scope + outlier + physician visibility."""
    table_names = [
        'FactDRGPayments', 'FactEncounters', 'FactCharges', 'FactCosts',
        'FactContributions', 'DimDRG', 'DimPhysician', 'DimDepartment',
        'DimPayer', 'DimDate', 'DimFacility', 'DimServiceLine',
        'DimCostCenter', 'DimGLAccount', 'StgCharges', 'StgPayments',
        'StgCosts', 'ArchiveCharges2022', 'ArchivePayments2022',
        'TmpCalcContribution', 'MetricsSnapshot', 'DimDiagnosis',
        'DimProcedureCode', 'FactRefunds', 'DimInsurancePlan',
        'SysAuditLog', 'BridgeDRGDiagnosis', 'FactAdjustments',
        'DimModifier', 'TmpRevenueCalc', 'StgAdjustments',
        'ArchiveCosts2022', 'DimRevenueCode',
    ]
    tables = [(name, 1000000 if 'Fact' in name else (5000 if 'Dim' in name else 2000000), 0, None)
              for name in table_names]
    measures = [
        ('FactDRGPayments', 'DRG Revenue', 'SUM(FactDRGPayments[Payment])', None, 0),
        ('FactCosts', 'Direct Cost', 'SUM(FactCosts[DirectCost])', None, 0),
        ('FactContributions', 'Contribution Margin', 'SUM(FactContributions[Margin])', None, 0),
        ('FactContributions', 'Margin Per Case', 'DIVIDE([Contribution Margin],[Case Volume])', None, 0),
        ('FactEncounters', 'Case Volume', 'COUNTROWS(FactEncounters)', None, 0),
    ]
    columns = [
        ('FactDRGPayments', 'PaymentID', 'Int64', 1000000, 0),
        ('DimDRG', 'DRGCode', 'String', 1000, 0),
        ('DimPhysician', 'PhysicianName', 'String', 800, 0),
    ]
    rels = [
        ('FactDRGPayments', 'DimDRG', 'many-to-one', 'single'),
        ('FactEncounters', 'DimPhysician', 'many-to-one', 'single'),
        ('FactCosts', 'DimCostCenter', 'many-to-one', 'single'),
    ]
    instr = "You are a DRG contribution margin analyst. Track revenue, costs, and physician-level contribution margins. " * 55
    config = (instr, len(instr), 33, 0)  # extreme scope + bloated instructions + zero VA
    traces = [
        ('Show contribution margin by DRG', 'cross_entity', 55000, 4,
         'EVALUATE SUMMARIZE(FactContributions, DimDRG[DRGCode], "Margin", [Contribution Margin])',
         'FactContributions,DimDRG', 'pass', 0, 500, 10000, 18000, 10000, 600),  # outlier >45s
        ('Show margin per case by physician', 'cross_entity', 48000, 3,
         'EVALUATE SUMMARIZE(FactContributions, DimPhysician[PhysicianName], "Margin", [Margin Per Case])',
         'FactContributions,DimPhysician', 'pass', 1, 450, 9500, 16000, 8500, 550),  # physician + outlier
        ('What are the top DRGs by revenue?', 'ranking', 42000, 3,
         'EVALUATE SUMMARIZE(FactDRGPayments, DimDRG[DRGCode], "Revenue", [DRG Revenue])',
         'FactDRGPayments,DimDRG', 'pass', 0, 400, 9000, 14000, 7500, 480),
        ('Compare costs by service line', 'cross_entity', 38000, 2,
         'EVALUATE SUMMARIZE(FactCosts, DimServiceLine[Name], "Cost", [Direct Cost])',
         'FactCosts,DimServiceLine', 'pass', 0, 350, 8500, 12000, 6500, 420),
        ('Show revenue trend by quarter', 'trend', 30000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Quarter], "Revenue", [DRG Revenue])',
         'FactDRGPayments,DimDate', 'pass', 0, 300, 8000, 10000, 5000, 380),
    ]
    cu = (2200.0, 6500.0, 95, 25000, 55000)  # very high throttling
    return _build_db(14, 'DRG Contribution Model', 'Financial WS', 'FINANCIAL',
                     'Import', tables, measures, columns, rels, config, traces, cu, 12000.0)


def build_scenario_15():
    """Clinical Inpatient — Readmission Risk: the "everything wrong" scenario."""
    table_names = [
        'FactEncounters', 'FactReadmissions', 'FactLabResults', 'FactMedications',
        'FactVitals', 'FactProcedures', 'FactNotes', 'FactCharges',
        'DimPatient', 'DimPhysician', 'DimDepartment', 'DimDiagnosis',
        'DimDate', 'DimFacility', 'DimPayor', 'DimProcedureType',
        'DimMedication', 'DimLabTest', 'DimBed', 'DimUnit',
        'StgEncounters', 'StgLab', 'StgMeds', 'StgVitals',
        'ArchiveEncounters2022', 'ArchiveEncounters2021', 'ArchiveCharges2022',
        'SysAuditLog', 'SysUserAccess', 'TmpCalcTable',
        'BridgeDiagEncounter', 'MetricsSnapshot', 'DimInsurance',
        'FactTransfers', 'TmpRiskCalc',
    ]
    tables = [(name, 800000 if 'Fact' in name else (3000 if 'Dim' in name else 1500000), 0, None)
              for name in table_names]
    measures = [
        ('FactEncounters', 'Average LOS', 'AVERAGE(FactEncounters[LOS_Days])', None, 0),
        ('FactEncounters', 'Avg LOS', 'AVERAGE(FactEncounters[LOS_Days])', None, 0),  # fuzzy dup
        ('FactReadmissions', 'Readmission Rate', 'DIVIDE([Readmissions],[Total Encounters])', None, 0),
        ('FactReadmissions', 'Readmit Rate', 'DIVIDE(COUNTROWS(FactReadmissions),COUNTROWS(FactEncounters))', None, 0),  # fuzzy dup
        ('FactEncounters', 'Total Encounters', 'COUNTROWS(FactEncounters)', None, 0),
        ('FactEncounters', 'Total Encounters', 'COUNT(FactEncounters[EncounterID])', None, 0),  # exact dup
        ('FactEncounters', 'Mortality Rate', 'DIVIDE([Deaths],[Total Encounters])', None, 0),
        ('FactCharges', 'Total Charges', 'SUM(FactCharges[Amount])', None, 0),
        ('FactLabResults', 'Lab TAT', 'AVERAGE(FactLabResults[TAT_Hours])', None, 0),
    ]
    columns = [
        ('FactEncounters', 'EncounterID', 'Int64', 800000, 0),
        ('FactEncounters', 'LOS_Days', 'Decimal', 30, 0),
        ('FactEncounters', 'AttendingPhysicianID', 'Int64', 500, 1),  # hidden
        ('FactEncounters', 'InternalAuditFlag', 'Boolean', 2, 1),  # hidden
        ('DimPatient', 'PatientName', 'String', 300000, 0),
        ('DimPhysician', 'PhysicianName', 'String', 500, 0),
    ]
    rels = [
        ('FactEncounters', 'DimPatient', 'many-to-one', 'single'),
        ('FactEncounters', 'DimPhysician', 'many-to-one', 'single'),
        ('FactEncounters', 'DimDate', 'many-to-one', 'both'),
        ('FactReadmissions', 'FactEncounters', 'many-to-one', 'single'),
    ]
    # Everything wrong: bloated instructions, extreme scope, zero VA
    instr = "You are a clinical inpatient readmission risk analyst. Track LOS, readmission patterns, and physician outcomes. " * 55
    config = (instr, len(instr), 35, 0)
    traces = [
        # Outlier + physician visible + high retries
        ('Show readmission rate by attending physician', 'cross_entity', 58000, 5,
         'EVALUATE SUMMARIZE(FactReadmissions, DimPhysician[PhysicianName], "Rate", [Readmission Rate])',
         'FactReadmissions,FactEncounters,DimPhysician', 'pass', 1, 500, 11000, 18000, 12000, 650),
        # Outlier
        ('Show all charges by diagnosis and payor', 'cross_entity', 62000, 4,
         'EVALUATE SUMMARIZE(FactCharges, DimDiagnosis[Name], DimPayor[PayorName], "Total", [Total Charges])',
         'FactCharges,DimDiagnosis,DimPayor', 'fail', 0, 550, 11500, 20000, 14000, 700),
        # Slow + retries
        ('What is the average LOS by department?', 'cross_entity', 35000, 3,
         'EVALUATE SUMMARIZE(FactEncounters, DimDepartment[DeptName], "AvgLOS", [Average LOS])',
         'FactEncounters,DimDepartment', 'pass', 0, 350, 10500, 10000, 5500, 450),
        # Failed query
        ('What is the sepsis bundle compliance?', 'domain_kpi', 15000, 0,
         'EVALUATE {[Sepsis Compliance Not Found]}', 'FactEncounters', 'fail', 0,
         200, 5000, 5500, 1200, 250),
        # Slow
        ('Show lab turnaround trends', 'trend', 25000, 1,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "TAT", [Lab TAT])',
         'FactLabResults,DimDate', 'pass', 0, 280, 9000, 7000, 3500, 350),
    ]
    cu = (2500.0, 7000.0, 110, 28000, 60000)  # extreme throttling
    return _build_db(15, 'Readmission Risk Model', 'Clinical Inpatient WS', 'CLINICAL_INPATIENT',
                     'Import', tables, measures, columns, rels, config, traces, cu, 15000.0)


def build_scenario_16():
    """Clinical Inpatient — Mortality Review: governance-heavy + high retry."""
    tables = [
        ('FactMortalityEvents', 50000, 0, 'Mortality records'),
        ('FactEncounters', 500000, 0, 'Encounter records'),
        ('FactComorbidities', 300000, 0, 'Comorbidity data'),
        ('DimPatient', 200000, 0, 'Patient demographics'),
        ('DimPhysician', 800, 0, 'Attending physicians'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDiagnosis', 80000, 0, 'Diagnosis codes'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimFacility', 45, 0, 'Facilities'),
    ]
    measures = [
        ('FactMortalityEvents', 'Mortality Rate', 'DIVIDE([Deaths],[Total Encounters])', None, 0),
        ('FactMortalityEvents', 'Observed/Expected Ratio', 'DIVIDE([Observed Deaths],[Expected Deaths])', None, 0),
        ('FactEncounters', 'Total Encounters', 'COUNTROWS(FactEncounters)', None, 0),
        ('FactComorbidities', 'Avg Comorbidity Score', 'AVERAGE(FactComorbidities[Score])', None, 0),
    ]
    columns = [
        ('FactMortalityEvents', 'EventID', 'Int64', 50000, 0),
        ('DimPhysician', 'PhysicianName', 'String', 800, 0),
        ('DimPatient', 'PatientName', 'String', 200000, 0),
    ]
    rels = [
        ('FactMortalityEvents', 'DimPatient', 'many-to-one', 'single'),
        ('FactMortalityEvents', 'DimPhysician', 'many-to-one', 'single'),
        ('FactEncounters', 'DimPatient', 'many-to-one', 'single'),
    ]
    instr = "You are a mortality review analyst. Track O/E ratios, risk-adjusted mortality, and physician outcomes. " * 22
    config = (instr, len(instr), len(tables), 3)
    traces = [
        ('Show mortality rate by physician', 'cross_entity', 30000, 3,
         'EVALUATE SUMMARIZE(FactMortalityEvents, DimPhysician[PhysicianName], "Rate", [Mortality Rate])',
         'FactMortalityEvents,DimPhysician', 'pass', 1, 300, 5500, 10000, 4500, 380),  # physician visible
        ('What is the O/E ratio by department?', 'cross_entity', 28000, 3,
         'EVALUATE SUMMARIZE(FactMortalityEvents, DimDepartment[DeptName], "OE", [Observed/Expected Ratio])',
         'FactMortalityEvents,DimDepartment', 'pass', 0, 280, 5200, 9500, 4200, 360),
        ('Show mortality trend by quarter', 'trend', 22000, 2,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Quarter], "Rate", [Mortality Rate])',
         'FactMortalityEvents,DimDate', 'pass', 0, 240, 4800, 7500, 3500, 320),
        ('What is the avg comorbidity score for mortalities?', 'simple_kpi', 18000, 1,
         'EVALUATE {[Avg Comorbidity Score]}', 'FactComorbidities', 'pass', 0, 200, 4200, 6000, 2800, 280),
        ('Show mortality by diagnosis', 'cross_entity', 32000, 3,
         'EVALUATE SUMMARIZE(FactMortalityEvents, DimDiagnosis[Name], "Rate", [Mortality Rate])',
         'FactMortalityEvents,DimDiagnosis', 'pass', 0, 320, 5800, 11000, 5000, 400),
    ]
    cu = (300.0, 800.0, 15, 12000, 30000)
    return _build_db(16, 'Mortality Review Model', 'Clinical Inpatient WS', 'CLINICAL_INPATIENT',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1800.0)


def build_scenario_17():
    """Revenue Cycle — Charge Capture: minimal issues — the "well-configured" scenario."""
    tables = [
        ('FactCharges', 1000000, 0, 'Charge transactions'),
        ('FactPayments', 800000, 0, 'Payment transactions'),
        ('DimCPT', 12000, 0, 'CPT codes'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimFacility', 45, 0, 'Facilities'),
        ('DimProvider', 3000, 0, 'Providers'),
    ]
    measures = [
        ('FactCharges', 'Total Charges', 'SUM(FactCharges[Amount])', None, 0),
        ('FactPayments', 'Total Payments', 'SUM(FactPayments[Amount])', None, 0),
        ('FactCharges', 'Charge Capture Rate', 'DIVIDE([Captured],[Expected])', None, 0),
    ]
    columns = [
        ('FactCharges', 'ChargeID', 'Int64', 1000000, 0),
        ('FactCharges', 'Amount', 'Decimal', 50000, 0),
        ('DimCPT', 'CPTCode', 'String', 12000, 0),
    ]
    rels = [
        ('FactCharges', 'DimCPT', 'many-to-one', 'single'),
        ('FactCharges', 'DimDepartment', 'many-to-one', 'single'),
        ('FactCharges', 'DimDate', 'many-to-one', 'single'),
    ]
    # Well-configured: short instructions, small scope, good VA count
    instr = "You are a charge capture analyst. Track charge volumes and capture rates by department. " * 15
    config = (instr, len(instr), 7, 10)  # only 7 tables checked, 10 VAs
    traces = [
        ('What is the total charges this month?', 'simple_kpi', 8000, 0,
         'EVALUATE {[Total Charges]}', 'FactCharges', 'pass', 0, 150, 2000, 2500, 1200, 180),
        ('Show charge capture rate by department', 'cross_entity', 10000, 0,
         'EVALUATE SUMMARIZE(FactCharges, DimDepartment[DeptName], "Rate", [Charge Capture Rate])',
         'FactCharges,DimDepartment', 'pass', 0, 170, 2200, 3000, 1500, 200),
        ('What CPT codes have highest charges?', 'ranking', 12000, 0,
         'EVALUATE TOPN(25, SUMMARIZE(FactCharges, DimCPT[CPTCode], "Total", [Total Charges]), [Total], DESC)',
         'FactCharges,DimCPT', 'pass', 0, 180, 2400, 3500, 1800, 220),
        ('Show charge trends by quarter', 'trend', 9000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Quarter], "Charges", [Total Charges])',
         'FactCharges,DimDate', 'pass', 0, 160, 2100, 2800, 1400, 190),
        ('Compare charges vs payments by facility', 'cross_entity', 11000, 0,
         'EVALUATE SUMMARIZE(FactCharges, DimFacility[Name], "Charges", [Total Charges], "Payments", [Total Payments])',
         'FactCharges,FactPayments,DimFacility', 'pass', 0, 175, 2300, 3200, 1600, 210),
    ]
    cu = (200.0, 500.0, 3, 5000, 12000)
    return _build_db(17, 'Charge Capture Model', 'Revenue Cycle WS', 'REVENUE_CYCLE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 800.0)


def build_scenario_18():
    """Operational — Bed Management: Direct Lake + high CU + schema mismatch."""
    tables = [
        ('FactBedStatus', 1000000, 0, 'Bed status events'),
        ('FactAdmissions', 600000, 0, 'Admission records'),
        ('FactDischarges', 580000, 0, 'Discharge records'),
        ('FactTransfers', 200000, 0, 'Transfer records'),
        ('DimBed', 500, 0, 'Bed inventory'),
        ('DimUnit', 40, 0, 'Nursing units'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimFacility', 45, 0, 'Facilities'),
        ('DimPatient', 200000, 0, 'Patients'),
        ('DimAccommodation', 8, 0, 'Room types'),
    ]
    measures = [
        ('FactBedStatus', 'Bed Occupancy Rate', 'DIVIDE([Occupied],[Total Beds])', None, 0),
        ('FactAdmissions', 'Admissions', 'COUNTROWS(FactAdmissions)', None, 0),
        ('FactDischarges', 'Discharges', 'COUNTROWS(FactDischarges)', None, 0),
        ('FactTransfers', 'Transfer Count', 'COUNTROWS(FactTransfers)', None, 0),
        ('FactBedStatus', 'Avg Turnaround', 'AVERAGE(FactBedStatus[TurnaroundMinutes])', None, 0),
    ]
    columns = [
        ('FactBedStatus', 'EventID', 'Int64', 1000000, 0),
        ('DimBed', 'BedNumber', 'String', 500, 0),
        ('DimUnit', 'UnitName', 'String', 40, 0),
    ]
    rels = [
        ('FactBedStatus', 'DimBed', 'many-to-one', 'single'),
        ('FactAdmissions', 'DimBed', 'many-to-one', 'single'),
        ('FactAdmissions', 'DimDate', 'many-to-one', 'single'),
        ('FactDischarges', 'DimDate', 'many-to-one', 'single'),
    ]
    # Schema mismatch: 18 tables checked but only 10 in model
    instr = "You are a bed management analyst. Track occupancy, throughput, and turnaround times. " * 20
    config = (instr, len(instr), 18, 4)  # mismatch: 18 vs 10
    traces = [
        ('What is the bed occupancy rate by unit?', 'cross_entity', 24000, 1,
         'EVALUATE SUMMARIZE(FactBedStatus, DimUnit[UnitName], "Occupancy", [Bed Occupancy Rate])',
         'FactBedStatus,DimUnit', 'pass', 0, 220, 3800, 5500, 10000, 300),
        ('Show admission vs discharge trends', 'trend', 22000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Date], "Admits", [Admissions], "DC", [Discharges])',
         'FactAdmissions,FactDischarges,DimDate', 'pass', 0, 200, 3500, 5000, 9200, 280),
        ('What is the avg bed turnaround time?', 'simple_kpi', 20000, 0,
         'EVALUATE {[Avg Turnaround]}', 'FactBedStatus', 'pass', 0, 180, 3200, 4500, 8500, 260),
        ('Show transfer patterns by unit', 'cross_entity', 26000, 2,
         'EVALUATE SUMMARIZE(FactTransfers, DimUnit[UnitName], "Count", [Transfer Count])',
         'FactTransfers,DimUnit', 'pass', 0, 240, 4000, 6000, 10500, 320),
        ('What is occupancy by room type?', 'cross_entity', 23000, 0,
         'EVALUATE SUMMARIZE(FactBedStatus, DimAccommodation[Type], "Occupancy", [Bed Occupancy Rate])',
         'FactBedStatus,DimAccommodation', 'pass', 0, 210, 3600, 5200, 9800, 290),
    ]
    cu = (900.0, 2600.0, 65, 18000, 40000)  # high CU throttle
    return _build_db(18, 'Bed Management Model', 'Operational WS', 'OPERATIONAL',
                     'DirectLake', tables, measures, columns, rels, config, traces, cu, 4000.0)


def build_scenario_19():
    """Patient Experience — Survey Response: mixed SQL/DAX + measure not found."""
    tables = [
        ('FactSurveys', 400000, 0, 'Survey response records'),
        ('FactFollowUps', 150000, 0, 'Post-survey follow-ups'),
        ('DimQuestion', 50, 0, 'Survey questions'),
        ('DimPatient', 200000, 0, 'Patient demographics'),
        ('DimDepartment', 60, 0, 'Departments'),
        ('DimDate', 3650, 0, 'Calendar'),
        ('DimSurveyType', 5, 0, 'Survey types'),
        ('DimFacility', 45, 0, None),
    ]
    measures = [
        ('FactSurveys', 'Response Rate', 'DIVIDE([Responded],[Sent])', None, 0),
        ('FactSurveys', 'Avg Score', 'AVERAGE(FactSurveys[Score])', None, 0),
        ('FactSurveys', 'NPS Score', 'DIVIDE([Promoters]-[Detractors],[Total Responses])*100', None, 0),
        ('FactFollowUps', 'Follow-Up Rate', 'DIVIDE([FollowedUp],[Flagged])', None, 0),
    ]
    columns = [
        ('FactSurveys', 'SurveyID', 'Int64', 400000, 0),
        ('FactSurveys', 'Score', 'Int64', 10, 0),
        ('DimQuestion', 'QuestionText', 'String', 50, 0),
    ]
    rels = [
        ('FactSurveys', 'DimQuestion', 'many-to-one', 'single'),
        ('FactSurveys', 'DimPatient', 'many-to-one', 'single'),
        ('FactSurveys', 'DimDate', 'many-to-one', 'single'),
    ]
    instr = "You are a survey response analyst. Track response rates, satisfaction scores, and NPS trends. " * 20
    config = (instr, len(instr), len(tables), 2)
    traces = [
        # NL2DAX contamination — SQL mixed with DAX
        ('Show avg score by department', 'cross_entity', 20000, 1,
         'EVALUATE SUMMARIZE(FactSurveys, SELECT DimDepartment.DeptName FROM DimDepartment JOIN FactSurveys, "Score", [Avg Score])',
         'FactSurveys,DimDepartment', 'pass', 0, 220, 4200, 7000, 3000, 280),
        # Measure not found
        ('What is the patient loyalty index?', 'simple_kpi', 14000, 0,
         'EVALUATE {[Patient Loyalty Index not found error]}', 'FactSurveys', 'fail', 0,
         180, 3800, 4500, 1800, 250),
        ('Show NPS trend by quarter', 'trend', 18000, 0,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Quarter], "NPS", [NPS Score])',
         'FactSurveys,DimDate', 'pass', 0, 200, 4000, 5500, 2800, 260),
        ('What is the follow-up rate by survey type?', 'cross_entity', 16000, 0,
         'EVALUATE SUMMARIZE(FactFollowUps, DimSurveyType[Name], "Rate", [Follow-Up Rate])',
         'FactFollowUps,DimSurveyType', 'pass', 0, 190, 3900, 4800, 2500, 250),
        ('Show response rate by facility', 'cross_entity', 22000, 1,
         'EVALUATE SUMMARIZE(FactSurveys, DimFacility[Name], "Rate", [Response Rate])',
         'FactSurveys,DimFacility', 'pass', 0, 230, 4300, 7500, 3200, 290),
    ]
    cu = (280.0, 700.0, 10, 9000, 22000)
    return _build_db(19, 'Survey Response Model', 'Patient Experience WS', 'PATIENT_EXPERIENCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 1100.0)


def build_scenario_20():
    """Workforce — Nursing Turnover: all execution rules triggered + scope bloat."""
    table_names = [
        'FactTerminations', 'FactNewHires', 'FactTransfers', 'FactPerformanceReviews',
        'FactAbsences', 'FactOvertimeEvents', 'FactShifts', 'FactTimecards',
        'DimEmployee', 'DimDepartment', 'DimJobRole', 'DimFacility',
        'DimDate', 'DimTerminationReason', 'DimShiftType', 'DimManager',
        'StgTerminations', 'StgNewHires', 'StgTimecards', 'ArchiveHR2022',
        'ArchiveHR2021', 'TmpTurnoverCalc', 'SysHRAccess', 'MetricsSnapshot',
        'DimEducation', 'DimCertification', 'FactCompensation', 'DimPayGrade',
    ]
    tables = [(name, 200000 if 'Fact' in name else 5000, 0, None) for name in table_names]
    measures = [
        ('FactTerminations', 'Turnover Rate', 'DIVIDE([Terminations],[Headcount])', None, 0),
        ('FactTerminations', 'Attrition Rate', 'DIVIDE(COUNTROWS(FactTerminations),[AvgHeadcount])', None, 0),  # fuzzy dup
        ('FactNewHires', 'Hire Rate', 'DIVIDE([NewHires],[Positions])', None, 0),
        ('FactAbsences', 'Absence Rate', 'DIVIDE([AbsentDays],[WorkingDays])', None, 0),
        ('FactPerformanceReviews', 'Avg Performance Score', 'AVERAGE(FactPerformanceReviews[Score])', None, 0),
        ('FactCompensation', 'Avg Salary', 'AVERAGE(FactCompensation[AnnualSalary])', None, 0),
    ]
    columns = [
        ('FactTerminations', 'TermID', 'Int64', 200000, 0),
        ('DimEmployee', 'EmployeeName', 'String', 5000, 0),
        ('DimEmployee', 'SSN', 'String', 5000, 1),  # hidden sensitive
        ('DimEmployee', 'PersonalEmail', 'String', 5000, 1),  # hidden sensitive
    ]
    rels = [
        ('FactTerminations', 'DimEmployee', 'many-to-one', 'single'),
        ('FactTerminations', 'DimDepartment', 'many-to-one', 'single'),
        ('FactTerminations', 'DimDate', 'many-to-one', 'single'),
        ('FactNewHires', 'DimEmployee', 'many-to-one', 'single'),
    ]
    # Scope bloat + instruction bloat
    instr = "You are a nursing workforce turnover analyst. Track attrition, hiring, absences, and retention patterns. " * 50
    config = (instr, len(instr), 28, 0)  # high scope, zero VA
    traces = [
        # Outlier + retry dominant + schema dominant
        ('Show turnover rate by department', 'cross_entity', 50000, 4,
         'EVALUATE SUMMARIZE(FactTerminations, DimDepartment[DeptName], "Rate", [Turnover Rate])',
         'FactTerminations,DimDepartment', 'pass', 0, 400, 14000, 8000, 5500, 500),
        # Execution dominant + slow
        ('What is the absence rate by shift?', 'cross_entity', 35000, 1,
         'EVALUATE SUMMARIZE(FactAbsences, DimShiftType[Name], "Rate", [Absence Rate])',
         'FactAbsences,DimShiftType', 'pass', 0, 300, 8500, 5500, 14000, 400),
        # DAX generation dominant
        ('Compare performance scores vs turnover by department', 'cross_entity', 40000, 2,
         'EVALUATE SUMMARIZE(FactPerformanceReviews, DimDepartment[DeptName], "Score", [Avg Performance Score], "Turnover", [Turnover Rate])',
         'FactPerformanceReviews,FactTerminations,DimDepartment', 'pass', 0, 350, 7000, 24000, 3500, 450),
        # Schema lookup dominant
        ('Show new hires by month', 'trend', 30000, 2,
         'EVALUATE SUMMARIZECOLUMNS(DimDate[Month], "Hires", [Hire Rate])',
         'FactNewHires,DimDate', 'pass', 0, 280, 12000, 6000, 4000, 380),
        # Slow + retries
        ('What is avg salary by job role?', 'cross_entity', 28000, 2,
         'EVALUATE SUMMARIZE(FactCompensation, DimJobRole[Name], "Salary", [Avg Salary])',
         'FactCompensation,DimJobRole', 'pass', 0, 260, 7500, 8000, 5500, 350),
    ]
    cu = (1100.0, 3200.0, 55, 20000, 45000)  # throttling
    return _build_db(20, 'Nursing Turnover Model', 'Workforce WS', 'WORKFORCE',
                     'Import', tables, measures, columns, rels, config, traces, cu, 3800.0)


SCENARIO_BUILDERS = [
    build_scenario_01, build_scenario_02, build_scenario_03, build_scenario_04,
    build_scenario_05, build_scenario_06, build_scenario_07, build_scenario_08,
    build_scenario_09, build_scenario_10, build_scenario_11, build_scenario_12,
    build_scenario_13, build_scenario_14, build_scenario_15, build_scenario_16,
    build_scenario_17, build_scenario_18, build_scenario_19, build_scenario_20,
]

SCENARIO_META = [
    {"id": 1, "name": "Revenue Cycle — Denial Management", "domain": "REVENUE_CYCLE",
     "key_issues": ["instruction_bloat", "measure_duplicates", "zero_va", "high_retries"]},
    {"id": 2, "name": "Revenue Cycle — AR Recovery", "domain": "REVENUE_CYCLE",
     "key_issues": ["extreme_scope_bloat", "zero_va", "cu_throttling", "missing_descriptions"]},
    {"id": 3, "name": "Workforce — Staffing Optimization", "domain": "WORKFORCE",
     "key_issues": ["near_limit_instructions", "low_va", "fuzzy_duplicates", "hidden_columns"]},
    {"id": 4, "name": "Workforce — Agency Spend", "domain": "WORKFORCE",
     "key_issues": ["high_retries", "physician_visible", "wrong_table"]},
    {"id": 5, "name": "Supply Chain — Inventory Management", "domain": "SUPPLY_CHAIN",
     "key_issues": ["extreme_scope_bloat", "missing_descriptions", "instruction_bloat", "zero_va"]},
    {"id": 6, "name": "Supply Chain — Vendor Contract Analysis", "domain": "SUPPLY_CHAIN",
     "key_issues": ["dax_generation_dominant", "fuzzy_duplicates"]},
    {"id": 7, "name": "Patient Experience — HCAHPS Scores", "domain": "PATIENT_EXPERIENCE",
     "key_issues": ["outlier_traces", "topn_absent", "high_retries"]},
    {"id": 8, "name": "Patient Experience — Complaint Resolution", "domain": "PATIENT_EXPERIENCE",
     "key_issues": ["execution_dominant", "hidden_columns"]},
    {"id": 9, "name": "Clinical Quality — Sepsis Bundle", "domain": "CLINICAL_QUALITY",
     "key_issues": ["empty_results", "measure_not_found", "nl2dax_contamination"]},
    {"id": 10, "name": "Clinical Quality — Antibiotic Stewardship", "domain": "CLINICAL_QUALITY",
     "key_issues": ["ambiguous_time", "wrong_table", "physician_visible"]},
    {"id": 11, "name": "Operational — ED Throughput", "domain": "OPERATIONAL",
     "key_issues": ["retry_dominant", "schema_lookup_dominant", "high_retries"]},
    {"id": 12, "name": "Operational — OR Utilization", "domain": "OPERATIONAL",
     "key_issues": ["direct_lake", "vorder_missing", "framing_risk"]},
    {"id": 13, "name": "Financial — Budget Variance", "domain": "FINANCIAL",
     "key_issues": ["near_limit_instructions", "fuzzy_duplicates", "slow_traces", "low_va"]},
    {"id": 14, "name": "Financial — DRG Contribution", "domain": "FINANCIAL",
     "key_issues": ["extreme_scope_bloat", "outlier_traces", "physician_visible", "cu_throttling", "zero_va"]},
    {"id": 15, "name": "Clinical Inpatient — Readmission Risk", "domain": "CLINICAL_INPATIENT",
     "key_issues": ["everything_wrong"]},
    {"id": 16, "name": "Clinical Inpatient — Mortality Review", "domain": "CLINICAL_INPATIENT",
     "key_issues": ["physician_visible", "high_retries", "governance"]},
    {"id": 17, "name": "Revenue Cycle — Charge Capture", "domain": "REVENUE_CYCLE",
     "key_issues": ["well_configured", "minimal_issues"]},
    {"id": 18, "name": "Operational — Bed Management", "domain": "OPERATIONAL",
     "key_issues": ["direct_lake", "cu_throttling", "schema_mismatch", "execution_dominant"]},
    {"id": 19, "name": "Patient Experience — Survey Response", "domain": "PATIENT_EXPERIENCE",
     "key_issues": ["nl2dax_contamination", "measure_not_found", "empty_results"]},
    {"id": 20, "name": "Workforce — Nursing Turnover", "domain": "WORKFORCE",
     "key_issues": ["all_execution_rules", "scope_bloat", "instruction_bloat", "hidden_columns", "cu_throttling"]},
]


def build_all():
    """Build all 20 scenario databases."""
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    results = []
    for builder in SCENARIO_BUILDERS:
        db_path = builder()
        results.append(db_path)
        print(f'  Built: {os.path.basename(db_path)}')

    # Save metadata
    meta_path = os.path.join(SCENARIOS_DIR, 'scenarios_meta.json')
    with open(meta_path, 'w') as f:
        json.dump(SCENARIO_META, f, indent=2)
    print(f'\nBuilt {len(results)} scenario databases in {SCENARIOS_DIR}/')
    print(f'Metadata saved to {meta_path}')
    return results


if __name__ == '__main__':
    build_all()
