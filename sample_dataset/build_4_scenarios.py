"""Build 4 healthcare Data Agent scenarios for the FabricAnalyzer.

Each scenario represents a different healthcare domain with distinct anti-patterns,
latency profiles, and DAX issues. Uses real metadata from the demo-katz workspace
(LOS_Bad_Model) as the foundation.

Scenarios:
  22: LOS Clinical (Length of Stay) — instruction bloat, schema sprawl, slow DAX
  23: Revenue Cycle — missing verified answers, measure ambiguity, high retries
  24: Workforce/Staffing — deep nesting DAX, cross-join abuse, iterator overuse
  25: Supply Chain/Pharmacy — division-by-zero, circular refs, NL2DAX contamination
"""
import json
import os
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sample_dataset.build_sample import SCHEMA_SQL

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenarios')
WORKSPACE_ID = 'b79e8116-8374-45ed-883d-853bc561842b'

# Real Fabric metadata from demo-katz workspace
REAL_CAPACITY_ID = '42d9119b-d385-46c7-b0cb-c88bd6a486d8'

# ─────────────────────────────────────────────────────────────
# SCENARIO 22: LOS Clinical — Instruction Bloat + Schema Sprawl
# ─────────────────────────────────────────────────────────────
SCENARIO_22 = {
    'id': 22,
    'name': 'LOS Clinical Analysis',
    'domain': 'Clinical Inpatient',
    'agent_name': 'LOS_Bad_Agent',
    'agent_id': '5c449e0f-d004-400d-aff5-6d7ca860f9fe',
    'model_id': '179c3be3-a140-43cc-ad59-a3f17343b442',
    'model_name': 'LOS_Bad_Model',
    'description': 'Length of Stay analysis agent with instruction bloat (5200+ chars), excessive table exposure (18 tables), missing descriptions, and no verified answers.',
    'issues': ['instruction_bloat', 'schema_sprawl', 'missing_descriptions', 'no_verified_answers', 'hidden_columns_exposed'],
    'instruction_text': """You are a clinical analytics agent for inpatient Length of Stay analysis. 
Your primary role is to help clinicians and administrators understand patient flow, bed utilization, and discharge planning metrics.

ROUTING RULES:
- Questions about patient demographics → patient_encounters table
- Questions about lab results → lab_results table  
- Questions about medications → medications table
- Questions about vital signs → vital_signs table
- Questions about billing → billing_detail table
- Questions about bed management → bed_census table (NOTE: this table has been deprecated, use patient_encounters instead)
- Questions about staffing → staffing_schedule table
- Questions about quality metrics → quality_indicators table

IMPORTANT CONTEXT:
- Length of Stay is calculated as discharge_date - admission_date in days
- Readmission is defined as re-admission within 30 days of discharge
- ICU stays are identified by department = 'ICU' or department = 'MICU' or department = 'SICU' or department = 'CCU'
- The fiscal year starts on October 1
- All cost figures are in USD
- Patient identifiers must never be shown in responses (HIPAA compliance)
- The is_readmission field is stored as a STRING ('True'/'False') not a boolean — use string comparison
- The admission_date and discharge_date fields are stored as TEXT in ISO format
- Abnormal lab results are flagged with abnormal_flag_str = 'True'

METRIC DEFINITIONS:
- Average LOS = AVERAGE of length_of_stay column across all non-null encounters
- Readmission Rate = COUNT of readmissions / COUNT of total discharges * 100
- Case Mix Index = SUM of DRG weights / COUNT of discharges
- Bed Occupancy Rate = (SUM of patient-days) / (Total Beds * Days in Period) * 100
- Cost Per Case = SUM of total_charges / COUNT of discharges
- Mortality Rate = COUNT of deceased patients / COUNT of total discharges * 100

DEPRECATED TABLES (DO NOT USE):
- bed_census_archive — replaced by bed_census
- patient_demographics_v1 — merged into patient_encounters
- lab_results_staging — temporary ETL table
- billing_staging — temporary ETL table  
- audit_log — system table, not for analytics
- _sys_partition_map — internal system table

KNOWN ISSUES:
- The medications table sometimes has duplicate rows for the same prescription — use DISTINCT when counting
- vital_signs readings may have NULL values for some measurements — always use COALESCE or handle NULLs
- billing_detail amounts can be negative (adjustments) — be aware when summing
""",
    'tables': [
        {'name': 'patient_encounters', 'row_count': 15000, 'columns': ['encounter_id', 'patient_id', 'admission_date_str', 'discharge_date_str', 'department', 'attending_physician', 'length_of_stay', 'is_readmission_str', 'drg_code', 'drg_weight', 'discharge_disposition'], 'description': ''},
        {'name': 'lab_results', 'row_count': 85000, 'columns': ['lab_id', 'encounter_id', 'patient_id', 'test_name', 'result_value', 'result_unit', 'abnormal_flag_str', 'collected_date_str', 'ordering_physician'], 'description': ''},
        {'name': 'medications', 'row_count': 42000, 'columns': ['med_id', 'encounter_id', 'patient_id', 'drug_name', 'dose', 'route', 'frequency', 'start_date_str', 'end_date_str', 'prescribing_physician'], 'description': ''},
        {'name': 'vital_signs', 'row_count': 120000, 'columns': ['vital_id', 'encounter_id', 'patient_id', 'measurement_type', 'value', 'unit', 'recorded_date_str', 'recorded_by'], 'description': ''},
        {'name': 'billing_detail', 'row_count': 95000, 'columns': ['billing_id', 'encounter_id', 'patient_id', 'charge_code', 'amount', 'payer_category', 'service_date_str', 'department', 'revenue_code'], 'description': ''},
        # Excess tables that shouldn't be exposed
        {'name': 'bed_census', 'row_count': 200000, 'columns': ['census_id', 'unit', 'bed_id', 'patient_id', 'date_str', 'status'], 'description': ''},
        {'name': 'staffing_schedule', 'row_count': 50000, 'columns': ['schedule_id', 'staff_id', 'unit', 'shift_date', 'shift_type', 'hours'], 'description': ''},
        {'name': 'quality_indicators', 'row_count': 5000, 'columns': ['qi_id', 'indicator_name', 'value', 'period', 'department', 'benchmark'], 'description': ''},
        {'name': 'bed_census_archive', 'row_count': 500000, 'columns': ['census_id', 'unit', 'bed_id', 'patient_id', 'date_str', 'status'], 'description': ''},
        {'name': 'patient_demographics_v1', 'row_count': 20000, 'columns': ['patient_id', 'name', 'dob', 'gender', 'address', 'insurance_id'], 'description': ''},
        {'name': 'lab_results_staging', 'row_count': 10000, 'columns': ['stg_id', 'raw_data', 'load_date'], 'description': ''},
        {'name': 'billing_staging', 'row_count': 8000, 'columns': ['stg_id', 'raw_data', 'load_date'], 'description': ''},
        {'name': 'audit_log', 'row_count': 300000, 'columns': ['log_id', 'action', 'user_id', 'timestamp', 'details'], 'description': ''},
        {'name': '_sys_partition_map', 'row_count': 50, 'columns': ['partition_id', 'table_name', 'range_start', 'range_end'], 'description': ''},
        {'name': 'physician_directory', 'row_count': 500, 'columns': ['physician_id', 'name', 'department', 'specialty', 'hire_date'], 'description': ''},
        {'name': 'icd10_codes', 'row_count': 70000, 'columns': ['code', 'description', 'category', 'chapter'], 'description': ''},
        {'name': 'drg_reference', 'row_count': 800, 'columns': ['drg_code', 'description', 'weight', 'avg_los', 'geometric_los'], 'description': ''},
        {'name': 'payer_contracts', 'row_count': 200, 'columns': ['contract_id', 'payer_name', 'effective_date', 'rate_type', 'base_rate'], 'description': ''},
    ],
    'measures': [
        {'name': 'Average LOS', 'expression': 'AVERAGE(patient_encounters[length_of_stay])', 'description': ''},
        {'name': 'Avg LOS', 'expression': 'AVERAGE(patient_encounters[length_of_stay])', 'description': ''},  # Duplicate!
        {'name': 'Total Encounters', 'expression': 'COUNTROWS(patient_encounters)', 'description': ''},
        {'name': 'Count of Encounters', 'expression': 'COUNTROWS(patient_encounters)', 'description': ''},  # Duplicate!
        {'name': 'Readmission Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[is_readmission_str]="True"), COUNTROWS(patient_encounters))', 'description': ''},
        {'name': 'Total Charges', 'expression': 'SUM(billing_detail[amount])', 'description': ''},
        {'name': 'Avg Cost Per Case', 'expression': 'DIVIDE(SUM(billing_detail[amount]), COUNTROWS(patient_encounters))', 'description': ''},
        {'name': 'Mortality Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[discharge_disposition]="Deceased"), COUNTROWS(patient_encounters))', 'description': ''},
    ],
    'questions': [
        # Simple (8)
        {"question": "How many patient encounters are in the dataset?", "category": "count", "complexity": "simple"},
        {"question": "What is the average length of stay across all patients?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the total number of lab results recorded", "category": "count", "complexity": "simple"},
        {"question": "What are the distinct departments in patient encounters?", "category": "listing", "complexity": "simple"},
        {"question": "How many medications were prescribed in total?", "category": "count", "complexity": "simple"},
        {"question": "What is the total billing amount across all encounters?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many unique patients are in the dataset?", "category": "count", "complexity": "simple"},
        {"question": "What is the maximum length of stay recorded?", "category": "aggregation", "complexity": "simple"},
        # Medium (10)
        {"question": "What is the average length of stay by department?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me the top 10 most common medications prescribed", "category": "ranking", "complexity": "medium"},
        {"question": "What is the readmission rate by department?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show billing totals grouped by payer type", "category": "aggregation", "complexity": "medium"},
        {"question": "What are the most common lab tests ordered?", "category": "ranking", "complexity": "medium"},
        {"question": "How many vital sign readings were recorded per patient on average?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me patient encounters with length of stay greater than 7 days", "category": "filtering", "complexity": "medium"},
        {"question": "What percentage of encounters had abnormal lab results?", "category": "aggregation", "complexity": "medium"},
        {"question": "List the top 5 departments by total billing amount", "category": "ranking", "complexity": "medium"},
        {"question": "What is the average number of medications per encounter?", "category": "aggregation", "complexity": "medium"},
        # Complex (7)
        {"question": "Compare ICU vs general ward average length of stay and readmission rates", "category": "comparison", "complexity": "complex"},
        {"question": "What is the trend of average length of stay over the past 12 months?", "category": "trend", "complexity": "complex"},
        {"question": "Which physicians have the highest average patient length of stay?", "category": "ranking", "complexity": "complex"},
        {"question": "Show me patients with more than 3 readmissions and their total billing", "category": "filtering", "complexity": "complex"},
        {"question": "What are the top 10 most expensive encounters including all billing details?", "category": "ranking", "complexity": "complex"},
        {"question": "Compare weekend vs weekday admission outcomes", "category": "comparison", "complexity": "complex"},
        {"question": "Show correlation between abnormal lab results and readmission rates by department", "category": "correlation", "complexity": "complex"},
    ],
}

# ─────────────────────────────────────────────────────────────
# SCENARIO 23: Revenue Cycle — Missing Verified Answers + Measure Ambiguity
# ─────────────────────────────────────────────────────────────
SCENARIO_23 = {
    'id': 23,
    'name': 'Revenue Cycle Analytics',
    'domain': 'Revenue Cycle',
    'agent_name': 'Revenue_Cycle_Agent',
    'agent_id': 'rev-cycle-agent-001',
    'model_id': 'rev-cycle-model-001',
    'model_name': 'Revenue_Cycle_Model',
    'description': 'Revenue cycle agent with ambiguous measure names (Net Revenue vs Net Rev vs Revenue Net), no verified answers, high retry rates on financial queries.',
    'issues': ['measure_ambiguity', 'no_verified_answers', 'high_retries', 'missing_descriptions', 'fuzzy_measure_names'],
    'instruction_text': """Revenue Cycle analytics agent for denial management, AR recovery, and charge capture analysis.
Route financial queries to billing tables. Use net_revenue for revenue calculations.
Note: Some measures have similar names — always prefer the one ending in _v2.""",
    'tables': [
        {'name': 'claims', 'row_count': 250000, 'columns': ['claim_id', 'encounter_id', 'patient_id', 'payer_id', 'submitted_amount', 'allowed_amount', 'paid_amount', 'denied_amount', 'submit_date', 'adjudication_date', 'status', 'denial_reason_code'], 'description': ''},
        {'name': 'denials', 'row_count': 45000, 'columns': ['denial_id', 'claim_id', 'denial_code', 'denial_category', 'denial_amount', 'appeal_status', 'appeal_date', 'resolution_date', 'resolution_amount'], 'description': ''},
        {'name': 'payments', 'row_count': 180000, 'columns': ['payment_id', 'claim_id', 'payer_id', 'payment_amount', 'payment_date', 'payment_method', 'adjustment_code', 'adjustment_amount'], 'description': ''},
        {'name': 'charges', 'row_count': 500000, 'columns': ['charge_id', 'encounter_id', 'cpt_code', 'charge_amount', 'units', 'service_date', 'department', 'provider_id', 'modifier'], 'description': ''},
        {'name': 'ar_aging', 'row_count': 80000, 'columns': ['ar_id', 'claim_id', 'payer_id', 'outstanding_amount', 'days_outstanding', 'aging_bucket', 'follow_up_date', 'status'], 'description': ''},
        {'name': 'payer_contracts', 'row_count': 150, 'columns': ['contract_id', 'payer_name', 'contract_type', 'base_rate', 'effective_date', 'termination_date', 'fee_schedule'], 'description': ''},
        {'name': 'encounters', 'row_count': 200000, 'columns': ['encounter_id', 'patient_id', 'admission_date', 'discharge_date', 'department', 'drg_code', 'total_charges', 'total_payments'], 'description': ''},
        {'name': 'ar_aging_archive', 'row_count': 400000, 'columns': ['ar_id', 'claim_id', 'payer_id', 'outstanding_amount', 'days_outstanding', 'aging_bucket'], 'description': ''},
    ],
    'measures': [
        {'name': 'Net Revenue', 'expression': 'SUM(payments[payment_amount]) - SUM(payments[adjustment_amount])', 'description': ''},
        {'name': 'Net Rev', 'expression': 'SUM(payments[payment_amount])', 'description': ''},  # Ambiguous!
        {'name': 'Revenue Net', 'expression': 'SUM(charges[charge_amount]) - SUM(denials[denial_amount])', 'description': ''},  # Ambiguous!
        {'name': 'Denial Rate', 'expression': 'DIVIDE(COUNTROWS(denials), COUNTROWS(claims))', 'description': ''},
        {'name': 'Denial %', 'expression': 'DIVIDE(SUM(denials[denial_amount]), SUM(claims[submitted_amount]))', 'description': ''},  # Ambiguous!
        {'name': 'AR Days', 'expression': 'AVERAGE(ar_aging[days_outstanding])', 'description': ''},
        {'name': 'Days in AR', 'expression': 'DIVIDE(SUM(ar_aging[outstanding_amount]), AVERAGE(payments[payment_amount]))', 'description': ''},  # Ambiguous!
        {'name': 'Collection Rate', 'expression': 'DIVIDE(SUM(payments[payment_amount]), SUM(claims[submitted_amount]))', 'description': ''},
        {'name': 'Clean Claim Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(claims), claims[status]="Paid"), COUNTROWS(claims))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the total net revenue for this quarter?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the denial rate by payer", "category": "aggregation", "complexity": "simple"},
        {"question": "How many claims are currently outstanding?", "category": "count", "complexity": "simple"},
        {"question": "What is the average days in AR?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show total charges by department", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the clean claim rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many denials were overturned on appeal?", "category": "count", "complexity": "simple"},
        {"question": "What is the collection rate by payer?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me the top 10 denial reason codes by amount", "category": "ranking", "complexity": "medium"},
        {"question": "What is the AR aging distribution by payer category?", "category": "aggregation", "complexity": "medium"},
        {"question": "Compare denial rates between commercial and government payers", "category": "comparison", "complexity": "medium"},
        {"question": "Show claims with outstanding balance over $10,000 and days > 90", "category": "filtering", "complexity": "medium"},
        {"question": "What is the average time from claim submission to payment by payer?", "category": "aggregation", "complexity": "medium"},
        {"question": "List departments with denial rate above 15%", "category": "filtering", "complexity": "medium"},
        {"question": "Show me the payment variance between contracted and actual rates by payer", "category": "aggregation", "complexity": "complex"},
        {"question": "What is the trend of denial rates over the past 12 months?", "category": "trend", "complexity": "complex"},
        {"question": "Compare net revenue per case across service lines", "category": "comparison", "complexity": "complex"},
        {"question": "Show me the appeal success rate by denial category and payer", "category": "aggregation", "complexity": "complex"},
        {"question": "What is the expected recovery amount from current appeals pipeline?", "category": "calculation", "complexity": "complex"},
        {"question": "Identify claims at risk of timely filing limits by payer contract", "category": "filtering", "complexity": "complex"},
        {"question": "Build a payer performance scorecard with denial rate AR days and collection rate", "category": "dashboard", "complexity": "very_complex"},
        {"question": "What is the revenue leakage by department including charge capture gaps?", "category": "calculation", "complexity": "very_complex"},
        {"question": "Show me the full claims lifecycle from submission to final payment with all adjustments", "category": "journey", "complexity": "very_complex"},
        {"question": "Compare cost-to-collect ratio across payer categories with trend analysis", "category": "benchmarking", "complexity": "very_complex"},
        {"question": "Generate a comprehensive AR recovery forecast by aging bucket and payer", "category": "forecasting", "complexity": "very_complex"},
    ],
}

# ─────────────────────────────────────────────────────────────
# SCENARIO 24: Workforce/Staffing — Deep Nesting DAX + Iterator Abuse
# ─────────────────────────────────────────────────────────────
SCENARIO_24 = {
    'id': 24,
    'name': 'Workforce Analytics',
    'domain': 'Workforce',
    'agent_name': 'Staffing_Analytics_Agent',
    'agent_id': 'staffing-agent-001',
    'model_id': 'staffing-model-001',
    'model_name': 'Staffing_Analytics_Model',
    'description': 'Workforce analytics agent generating deeply nested DAX with SUMX/AVERAGEX iterators, CROSSJOIN on large tables, missing TOPN limits, and excessive CALCULATE nesting.',
    'issues': ['deep_nesting_dax', 'iterator_abuse', 'crossjoin_large_tables', 'missing_topn', 'excessive_calculate_nesting'],
    'instruction_text': """Staffing analytics agent for nurse scheduling, overtime tracking, and workforce planning.
Always calculate labor costs using SUMX over individual shifts for accuracy.
For productivity metrics, use CROSSJOIN to compare all nurse-unit combinations.
Nest CALCULATE for each filter context change.""",
    'tables': [
        {'name': 'staff', 'row_count': 2000, 'columns': ['staff_id', 'name', 'role', 'department', 'hire_date', 'hourly_rate', 'fte_status', 'certification', 'skill_level'], 'description': 'All staff members'},
        {'name': 'shifts', 'row_count': 500000, 'columns': ['shift_id', 'staff_id', 'unit', 'shift_date', 'shift_type', 'scheduled_hours', 'actual_hours', 'overtime_hours', 'is_agency', 'cost'], 'description': 'Individual shift records'},
        {'name': 'census', 'row_count': 365000, 'columns': ['census_id', 'unit', 'date', 'patient_count', 'acuity_score', 'required_rn_hours', 'actual_rn_hours', 'variance'], 'description': 'Daily unit census'},
        {'name': 'overtime_log', 'row_count': 80000, 'columns': ['ot_id', 'staff_id', 'shift_id', 'ot_hours', 'ot_rate', 'ot_cost', 'reason_code', 'approved_by'], 'description': 'Overtime records'},
        {'name': 'agency_contracts', 'row_count': 50, 'columns': ['contract_id', 'agency_name', 'role', 'hourly_rate', 'start_date', 'end_date'], 'description': 'Travel/agency contracts'},
        {'name': 'productivity_targets', 'row_count': 500, 'columns': ['target_id', 'unit', 'role', 'target_hppd', 'target_fte', 'period'], 'description': 'Productivity benchmarks'},
        {'name': 'turnover_events', 'row_count': 400, 'columns': ['event_id', 'staff_id', 'event_type', 'event_date', 'reason', 'replacement_cost'], 'description': 'Hire/term events'},
        {'name': 'certifications', 'row_count': 5000, 'columns': ['cert_id', 'staff_id', 'cert_name', 'expiry_date', 'status'], 'description': 'Staff certifications'},
    ],
    'measures': [
        {'name': 'Total Labor Cost', 'expression': 'SUMX(shifts, shifts[actual_hours] * RELATED(staff[hourly_rate]))', 'description': 'Uses iterator - slow on 500K rows'},
        {'name': 'HPPD', 'expression': 'DIVIDE(SUM(shifts[actual_hours]), SUM(census[patient_count]))', 'description': 'Hours per patient day'},
        {'name': 'Overtime Rate', 'expression': 'DIVIDE(SUM(overtime_log[ot_hours]), SUM(shifts[actual_hours]))', 'description': ''},
        {'name': 'Agency Spend %', 'expression': 'DIVIDE(CALCULATE(SUM(shifts[cost]), shifts[is_agency]=TRUE()), SUM(shifts[cost]))', 'description': ''},
        {'name': 'Turnover Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(turnover_events), turnover_events[event_type]="Termination"), COUNTROWS(staff))', 'description': ''},
        {'name': 'Vacancy Rate', 'expression': 'DIVIDE(SUM(census[required_rn_hours]) - SUM(census[actual_rn_hours]), SUM(census[required_rn_hours]))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the total labor cost this quarter?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me overtime hours by unit", "category": "aggregation", "complexity": "simple"},
        {"question": "How many agency staff are currently active?", "category": "count", "complexity": "simple"},
        {"question": "What is the average HPPD across all units?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show turnover rate by department", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the total agency spend this month?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many certifications are expiring in the next 90 days?", "category": "count", "complexity": "simple"},
        {"question": "What is the overtime cost by reason code?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me units where HPPD exceeds target by more than 20%", "category": "filtering", "complexity": "medium"},
        {"question": "Compare agency vs internal staff costs by unit", "category": "comparison", "complexity": "medium"},
        {"question": "What is the vacancy rate trend over the past 6 months?", "category": "trend", "complexity": "medium"},
        {"question": "List top 10 staff by overtime hours this quarter", "category": "ranking", "complexity": "medium"},
        {"question": "Show me shifts with actual hours exceeding scheduled by more than 4 hours", "category": "filtering", "complexity": "medium"},
        {"question": "What is the average time to fill open positions by role?", "category": "aggregation", "complexity": "medium"},
        {"question": "Compare productivity metrics across all nurse-unit combinations", "category": "comparison", "complexity": "complex"},
        {"question": "What is the labor cost per patient day by unit and shift type?", "category": "calculation", "complexity": "complex"},
        {"question": "Show the correlation between staffing levels and patient outcomes by unit", "category": "correlation", "complexity": "complex"},
        {"question": "Build a staffing forecast based on census trends and turnover patterns", "category": "forecasting", "complexity": "complex"},
        {"question": "What is the ROI of reducing agency staff by 25% per unit?", "category": "calculation", "complexity": "complex"},
        {"question": "Compare weekend vs weekday staffing adequacy across all units", "category": "comparison", "complexity": "complex"},
        {"question": "Generate a unit-level staffing dashboard with HPPD overtime vacancy and cost metrics", "category": "dashboard", "complexity": "very_complex"},
        {"question": "What is the optimal staffing model for each unit based on acuity patterns?", "category": "optimization", "complexity": "very_complex"},
        {"question": "Show me the full workforce lifecycle from hire to termination with cost analysis", "category": "journey", "complexity": "very_complex"},
        {"question": "Build a nurse retention risk model combining overtime turnover and satisfaction data", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "Compare our staffing efficiency against industry benchmarks for similar facilities", "category": "benchmarking", "complexity": "very_complex"},
    ],
}

# ─────────────────────────────────────────────────────────────
# SCENARIO 25: Supply Chain/Pharmacy — Division-by-Zero + Circular Refs
# ─────────────────────────────────────────────────────────────
SCENARIO_25 = {
    'id': 25,
    'name': 'Supply Chain & Pharmacy',
    'domain': 'Supply Chain',
    'agent_name': 'Supply_Chain_Agent',
    'agent_id': 'supply-chain-agent-001',
    'model_id': 'supply-chain-model-001',
    'model_name': 'Supply_Chain_Pharmacy_Model',
    'description': 'Supply chain agent with division-by-zero errors in cost calculations, circular measure references, NL2DAX contamination from ambiguous entity names, and instruction contradictions.',
    'issues': ['division_by_zero', 'circular_measure_refs', 'nl2dax_contamination', 'instruction_contradictions', 'ambiguous_entities'],
    'instruction_text': """Supply chain analytics for pharmacy and medical supplies procurement.
Calculate unit costs as total_cost / quantity — note some items have zero quantity in transit.
For inventory turnover, reference the Turnover Rate measure which uses COGS / Avg Inventory.
Note: COGS measure references Turnover Rate for validation, creating a bidirectional dependency.
IMPORTANT: When asking about "orders" this could mean purchase orders OR medication orders — always clarify.
ALSO IMPORTANT: "orders" always refers to purchase orders, never medication orders.
Route vendor queries to supplier_master. Route vendor queries to purchase_orders.""",
    'tables': [
        {'name': 'purchase_orders', 'row_count': 150000, 'columns': ['po_id', 'vendor_id', 'item_id', 'quantity', 'unit_cost', 'total_cost', 'order_date', 'delivery_date', 'status', 'department', 'gl_account'], 'description': ''},
        {'name': 'inventory', 'row_count': 25000, 'columns': ['item_id', 'item_name', 'category', 'current_quantity', 'reorder_point', 'unit_cost', 'location', 'last_counted_date', 'in_transit_qty'], 'description': ''},
        {'name': 'supplier_master', 'row_count': 500, 'columns': ['vendor_id', 'vendor_name', 'category', 'contract_status', 'lead_time_days', 'quality_score', 'payment_terms'], 'description': ''},
        {'name': 'pharmacy_orders', 'row_count': 300000, 'columns': ['rx_id', 'patient_id', 'drug_name', 'quantity', 'unit_cost', 'total_cost', 'order_date', 'dispensed_date', 'pharmacy_id', 'prescriber_id'], 'description': ''},
        {'name': 'receiving', 'row_count': 120000, 'columns': ['receipt_id', 'po_id', 'item_id', 'received_qty', 'damaged_qty', 'receipt_date', 'inspector_id'], 'description': ''},
        {'name': 'contracts', 'row_count': 200, 'columns': ['contract_id', 'vendor_id', 'start_date', 'end_date', 'contracted_price', 'volume_discount_pct', 'compliance_score'], 'description': ''},
        {'name': 'consumption', 'row_count': 400000, 'columns': ['consumption_id', 'item_id', 'department', 'quantity_used', 'date', 'cost', 'waste_quantity'], 'description': ''},
        {'name': 'formulary', 'row_count': 3000, 'columns': ['drug_id', 'drug_name', 'generic_name', 'formulary_status', 'therapeutic_class', 'unit_cost', 'contract_price'], 'description': ''},
    ],
    'measures': [
        {'name': 'Unit Cost', 'expression': 'DIVIDE(SUM(purchase_orders[total_cost]), SUM(purchase_orders[quantity]))', 'description': 'Can divide by zero when qty=0'},
        {'name': 'Inventory Turnover', 'expression': 'DIVIDE([COGS], [Avg Inventory])', 'description': 'References COGS which references back'},
        {'name': 'COGS', 'expression': 'SUM(consumption[cost]) * [Inventory Turnover] / [Inventory Turnover]', 'description': 'Circular ref with Turnover'},
        {'name': 'Avg Inventory', 'expression': 'AVERAGE(inventory[current_quantity]) * AVERAGE(inventory[unit_cost])', 'description': ''},
        {'name': 'Fill Rate', 'expression': 'DIVIDE(SUM(receiving[received_qty]), SUM(purchase_orders[quantity]))', 'description': ''},
        {'name': 'Waste Rate', 'expression': 'DIVIDE(SUM(consumption[waste_quantity]), SUM(consumption[quantity_used]))', 'description': 'Divides by zero for unused items'},
        {'name': 'Contract Compliance', 'expression': 'DIVIDE(CALCULATE(SUM(purchase_orders[total_cost]), NOT ISBLANK(purchase_orders[vendor_id])), SUM(purchase_orders[total_cost]))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the total procurement spend this quarter?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the top vendors by spend", "category": "ranking", "complexity": "simple"},
        {"question": "How many items are below reorder point?", "category": "count", "complexity": "simple"},
        {"question": "What is the average lead time by vendor?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show total pharmacy spend by therapeutic class", "category": "aggregation", "complexity": "simple"},
        {"question": "How many purchase orders are pending delivery?", "category": "count", "complexity": "simple"},
        {"question": "What is the waste rate for surgical supplies?", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the unit cost for the top 20 highest-spend items?", "category": "ranking", "complexity": "medium"},
        {"question": "Show orders with delivery delays greater than 7 days", "category": "filtering", "complexity": "medium"},
        {"question": "What is the inventory turnover rate by category?", "category": "aggregation", "complexity": "medium"},
        {"question": "Compare contracted vs actual prices by vendor", "category": "comparison", "complexity": "medium"},
        {"question": "Show me items where current quantity is zero but has pending orders", "category": "filtering", "complexity": "medium"},
        {"question": "What is the fill rate by vendor over the past 6 months?", "category": "trend", "complexity": "medium"},
        {"question": "List departments with the highest supply consumption per patient day", "category": "ranking", "complexity": "medium"},
        {"question": "What is the contract compliance rate by vendor category?", "category": "aggregation", "complexity": "complex"},
        {"question": "Show me the total cost of expired or wasted pharmacy inventory by drug class", "category": "calculation", "complexity": "complex"},
        {"question": "Compare generic vs brand name drug costs across the formulary", "category": "comparison", "complexity": "complex"},
        {"question": "What is the forecast for supply costs based on consumption trends?", "category": "forecasting", "complexity": "complex"},
        {"question": "Identify vendors at risk of non-compliance with contract terms", "category": "risk_scoring", "complexity": "complex"},
        {"question": "Show me the end-to-end supply chain from PO to patient consumption with costs", "category": "journey", "complexity": "complex"},
        {"question": "Build a vendor performance scorecard with fill rate quality lead time and cost metrics", "category": "dashboard", "complexity": "very_complex"},
        {"question": "What is the optimal reorder point for each item based on consumption patterns?", "category": "optimization", "complexity": "very_complex"},
        {"question": "Compare our pharmacy costs against 340B pricing and identify savings opportunities", "category": "benchmarking", "complexity": "very_complex"},
        {"question": "Generate a comprehensive supply chain risk assessment across all categories", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "Show me total cost of ownership including procurement storage waste and administration", "category": "calculation", "complexity": "very_complex"},
    ],
}


def generate_traces(scenario, seed=42):
    """Generate realistic trace data for a scenario based on its issues and questions."""
    random.seed(seed + scenario['id'])
    traces = []
    
    issue_set = set(scenario['issues'])
    instr_len = len(scenario['instruction_text'])
    table_count = len(scenario['tables'])
    
    for q in scenario['questions']:
        complexity = q['complexity']
        
        # Base latency by complexity
        base_ms = {
            'simple': random.randint(8000, 18000),
            'medium': random.randint(15000, 35000),
            'complex': random.randint(30000, 55000),
            'very_complex': random.randint(50000, 95000),
        }[complexity]
        
        # Add latency for specific issues
        if 'instruction_bloat' in issue_set and instr_len > 4800:
            base_ms += random.randint(3000, 8000)  # Instruction parsing overhead
        if 'schema_sprawl' in issue_set and table_count > 12:
            base_ms += random.randint(2000, 6000)  # Schema resolution overhead
        if 'deep_nesting_dax' in issue_set and complexity in ('complex', 'very_complex'):
            base_ms += random.randint(5000, 15000)  # DAX compilation overhead
        if 'measure_ambiguity' in issue_set:
            base_ms += random.randint(1000, 4000)  # Disambiguation overhead
        if 'division_by_zero' in issue_set and random.random() < 0.2:
            base_ms += random.randint(3000, 8000)  # Error + retry
        if 'circular_measure_refs' in issue_set and random.random() < 0.15:
            base_ms += random.randint(5000, 12000)  # DAX engine timeout + retry
        
        # Retries based on complexity and issues
        retry_base = {'simple': 0, 'medium': 1, 'complex': 2, 'very_complex': 3}[complexity]
        if 'high_retries' in issue_set:
            retry_base += 1
        if 'no_verified_answers' in issue_set:
            retry_base += random.randint(0, 1)
        retries = min(retry_base + random.randint(0, 1), 5)
        
        # Breakdown allocation
        total_ms = base_ms
        bd_parse = int(total_ms * random.uniform(0.03, 0.08))
        bd_schema = int(total_ms * random.uniform(0.08, 0.18))
        bd_nldax = int(total_ms * random.uniform(0.25, 0.45))
        bd_exec = int(total_ms * random.uniform(0.25, 0.45))
        bd_synth = max(500, total_ms - bd_parse - bd_schema - bd_nldax - bd_exec)
        bd_other = int(total_ms * random.uniform(0.02, 0.06))
        
        # Generate realistic DAX based on category
        tables_used = ','.join(t['name'] for t in scenario['tables'][:5])
        dax = f"EVALUATE SUMMARIZE({scenario['tables'][0]['name']}, {scenario['tables'][0]['name']}[{scenario['tables'][0]['columns'][0]}])"
        
        # Pass/fail
        if 'division_by_zero' in issue_set and random.random() < 0.1:
            pass_fail = 'error'
        elif retries > 3:
            pass_fail = 'degraded'
        elif retries > 1:
            pass_fail = 'slow'
        else:
            pass_fail = 'pass'
        
        traces.append({
            'question': q['question'],
            'category': q['category'],
            'total_ms': total_ms,
            'retries': retries,
            'dax_generated': dax,
            'tables_used': tables_used,
            'pass_fail': pass_fail,
            'bd_parse': bd_parse,
            'bd_schema': bd_schema,
            'bd_nldax': bd_nldax,
            'bd_exec': bd_exec,
            'bd_synth': bd_synth,
            'bd_other': bd_other,
        })
    
    return traces


def build_scenario_db(scenario, traces, output_dir):
    """Build a SQLite database for a scenario."""
    db_path = os.path.join(output_dir, f'scenario_{scenario["id"]:02d}.db')
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA_SQL)
    
    model_id = scenario['model_id']
    agent_id = scenario['agent_id']
    now = datetime.utcnow().isoformat()
    
    # Insert model
    db.execute('INSERT INTO models VALUES (?,?,?,?,?,?,?,?)', (
        model_id, WORKSPACE_ID, scenario['model_name'],
        sum(t['row_count'] for t in scenario['tables']) * 0.001,  # Rough size estimate
        'DirectLake', now, 1, now,
    ))
    
    # Insert tables
    for i, t in enumerate(scenario['tables']):
        db.execute('INSERT INTO tables VALUES (?,?,?,?,?,?,?,?)', (
            f'tbl_{i}', model_id, t['name'],
            t['row_count'], len(t['columns']),
            0, 'single', t.get('description', ''),
        ))
        # Insert columns
        for j, col in enumerate(t['columns']):
            db.execute('INSERT INTO columns VALUES (?,?,?,?,?,?,?)', (
                f'col_{i}_{j}', f'tbl_{i}', model_id, col,
                'string', random.randint(10, 50000), 0,
            ))
    
    # Insert measures
    for i, m in enumerate(scenario.get('measures', [])):
        db.execute('INSERT INTO measures VALUES (?,?,?,?,?,?,?)', (
            f'm_{i}', model_id, f'tbl_0',
            m['name'], m['expression'],
            m.get('description', ''), 0,
        ))
    
    # Insert agent config
    instr = scenario['instruction_text']
    db.execute('INSERT INTO agent_config VALUES (?,?,?,?,?,?,?,?)', (
        f'agent_{model_id[:8]}', model_id, WORKSPACE_ID,
        instr, len(instr), len(scenario['tables']),
        0, len(scenario['tables']),
    ))
    
    # Insert traces
    for t in traces:
        trace_id = f'trace_{uuid.uuid4().hex[:8]}'
        db.execute('''INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            trace_id, agent_id, model_id,
            t['question'], t['category'], t['total_ms'], t['retries'],
            t['dax_generated'], t['tables_used'], t['pass_fail'],
            1,  # physician_visible
            t['bd_parse'], t['bd_schema'], t['bd_nldax'],
            t['bd_exec'], t['bd_synth'], t['bd_other'],
            'test', f'run_{scenario["id"]}',
        ))
    
    # Insert CU metrics
    total_latencies = sorted([t['total_ms'] for t in traces])
    p50 = total_latencies[len(total_latencies) // 2] if total_latencies else 0
    p95 = total_latencies[int(len(total_latencies) * 0.95)] if total_latencies else 0
    
    db.execute('INSERT INTO cu_metrics VALUES (?,?,?,?,?,?,?,?,?)', (
        f'cu_{REAL_CAPACITY_ID[:8]}', model_id, WORKSPACE_ID,
        random.uniform(50, 200), random.uniform(100, 500),
        0, p50, p95, now,
    ))
    
    db.commit()
    db.close()
    
    return db_path


def main():
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    
    scenarios = [SCENARIO_22, SCENARIO_23, SCENARIO_24, SCENARIO_25]
    total_questions = 0
    
    for scenario in scenarios:
        print(f'\n=== Scenario {scenario["id"]}: {scenario["name"]} ===')
        print(f'  Domain: {scenario["domain"]}')
        print(f'  Agent: {scenario["agent_name"]}')
        print(f'  Issues: {", ".join(scenario["issues"])}')
        print(f'  Tables: {len(scenario["tables"])}')
        print(f'  Questions: {len(scenario["questions"])}')
        
        traces = generate_traces(scenario)
        db_path = build_scenario_db(scenario, traces, SCENARIOS_DIR)
        
        # Stats
        avg_ms = sum(t['total_ms'] for t in traces) / len(traces)
        max_ms = max(t['total_ms'] for t in traces)
        total_retries = sum(t['retries'] for t in traces)
        errors = sum(1 for t in traces if t['pass_fail'] == 'error')
        
        print(f'  Built: {db_path}')
        print(f'  Avg latency: {avg_ms:.0f}ms')
        print(f'  Max latency: {max_ms}ms')
        print(f'  Total retries: {total_retries}')
        print(f'  Errors: {errors}')
        
        total_questions += len(scenario['questions'])
    
    print(f'\n=== Summary ===')
    print(f'Total scenarios: {len(scenarios)}')
    print(f'Total questions: {total_questions}')
    
    # Update scenarios_meta.json (it's a flat list, not a dict)
    meta_path = os.path.join(SCENARIOS_DIR, 'scenarios_meta.json')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta_list = json.load(f)
        if isinstance(meta_list, dict):
            meta_list = meta_list.get('scenarios', [])
    else:
        meta_list = []
    
    # Remove old entries for these IDs
    existing_ids = {s['id'] for s in scenarios}
    meta_list = [s for s in meta_list if s.get('id') not in existing_ids]
    
    # Add new entries
    for scenario in scenarios:
        meta_list.append({
            'id': scenario['id'],
            'name': scenario['name'],
            'domain': scenario['domain'],
            'agent_name': scenario['agent_name'],
            'description': scenario['description'],
            'question_count': len(scenario['questions']),
            'issues': scenario['issues'],
            'db_file': f'scenario_{scenario["id"]:02d}.db',
        })
    
    meta_list.sort(key=lambda s: s['id'])
    
    with open(meta_path, 'w') as f:
        json.dump(meta_list, f, indent=2)
    
    print(f'Updated {meta_path} ({len(meta_list)} scenarios total)')


if __name__ == '__main__':
    main()
