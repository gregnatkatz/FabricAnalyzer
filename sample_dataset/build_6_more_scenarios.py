"""Build 6 more healthcare scenarios (26-31) to complement existing 22-25 = 10 total.

Scenarios 26-31:
  26: ED Throughput - timeout patterns, retry dominant, door-to-doc bottleneck
  27: Readmission Risk - physician visible, governance gaps, PII exposure risk
  28: Surgical Outcomes - OR utilization gaps, framing risk, ambiguous time windows
  29: Infection Control - empty results, measure not found, sparse data patterns
  30: Nursing Quality - hidden columns exposed, CU throttling, excessive measures
  31: Patient Safety - NL2DAX contamination, ambiguous temporal refs, event correlation
"""
import json
import os
import random
import sqlite3
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sample_dataset.build_sample import SCHEMA_SQL

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenarios')
WORKSPACE_ID = 'b79e8116-8374-45ed-883d-853bc561842b'
REAL_CAPACITY_ID = '42d9119b-d385-46c7-b0cb-c88bd6a486d8'

# ---------------------------------------------------------------------------
# SCENARIO 26: ED Throughput - Timeout Patterns + Door-to-Doc Bottleneck
# ---------------------------------------------------------------------------
SCENARIO_26 = {
    'id': 26,
    'name': 'ED Throughput Analysis',
    'domain': 'Emergency Department',
    'agent_name': 'ED_Throughput_Agent',
    'agent_id': 'ed-throughput-agent-001',
    'model_id': 'ed-throughput-model-001',
    'model_name': 'ED_Throughput_Model',
    'description': 'ED throughput agent with timeout-prone queries on large visit tables, retry-dominant latency on triage lookups, and door-to-doc metric calculation bottlenecks.',
    'issues': ['timeout_patterns', 'retry_dominant', 'schema_lookup_bottleneck', 'missing_descriptions', 'high_retries'],
    'instruction_text': (
        "Emergency Department throughput analytics agent for patient flow, door-to-doc times, and capacity management.\n"
        "Track all ED visits from arrival to disposition. Door-to-doc is measured from triage_complete to provider_assign.\n"
        "Note: ed_visits table has 2M+ rows - queries without date filters will timeout.\n"
        "Use bed_tracker for real-time capacity. Use ed_orders for order-to-result turnaround.\n"
        "IMPORTANT: Always filter by visit_date to prevent full table scans.\n"
        "ALSO IMPORTANT: The acuity field uses ESI scale (1=most acute, 5=least acute).\n"
        "For boarding metrics, use disposition_time - depart_time (negative = boarding).\n"
        "Route all staffing questions to ed_staffing table."
    ),
    'tables': [
        {'name': 'ed_visits', 'row_count': 2000000, 'columns': ['visit_id', 'patient_id', 'arrival_time', 'triage_time', 'triage_complete', 'provider_assign', 'disposition_time', 'depart_time', 'visit_date', 'acuity', 'chief_complaint', 'disposition', 'attending_id', 'unit'], 'description': ''},
        {'name': 'ed_orders', 'row_count': 5000000, 'columns': ['order_id', 'visit_id', 'order_type', 'order_time', 'result_time', 'status', 'ordering_provider', 'priority'], 'description': ''},
        {'name': 'ed_staffing', 'row_count': 200000, 'columns': ['staff_id', 'shift_date', 'shift_type', 'role', 'unit', 'start_time', 'end_time', 'actual_hours'], 'description': ''},
        {'name': 'bed_tracker', 'row_count': 500000, 'columns': ['bed_id', 'unit', 'status', 'patient_id', 'assign_time', 'release_time', 'clean_time', 'bed_type'], 'description': ''},
        {'name': 'ed_vitals', 'row_count': 8000000, 'columns': ['vital_id', 'visit_id', 'measurement', 'value', 'recorded_time', 'recorded_by'], 'description': ''},
        {'name': 'ed_imaging', 'row_count': 800000, 'columns': ['image_id', 'visit_id', 'modality', 'order_time', 'complete_time', 'read_time', 'result', 'radiologist_id'], 'description': ''},
        {'name': 'ed_labs', 'row_count': 3000000, 'columns': ['lab_id', 'visit_id', 'test_name', 'order_time', 'collect_time', 'result_time', 'value', 'abnormal_flag', 'critical_flag'], 'description': ''},
    ],
    'measures': [
        {'name': 'Door to Doc', 'expression': 'AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[provider_assign], MINUTE))', 'description': ''},
        {'name': 'Door-to-Doc', 'expression': 'AVERAGE(DATEDIFF(ed_visits[triage_complete], ed_visits[provider_assign], MINUTE))', 'description': ''},
        {'name': 'ED LOS', 'expression': 'AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[depart_time], MINUTE))', 'description': ''},
        {'name': 'LWBS Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(ed_visits), ed_visits[disposition]="LWBS"), COUNTROWS(ed_visits))', 'description': ''},
        {'name': 'Bed Turnaround', 'expression': 'AVERAGE(DATEDIFF(bed_tracker[release_time], bed_tracker[clean_time], MINUTE))', 'description': ''},
        {'name': 'Lab TAT', 'expression': 'AVERAGE(DATEDIFF(ed_labs[order_time], ed_labs[result_time], MINUTE))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the average door-to-doc time this month?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many ED visits occurred today?", "category": "count", "complexity": "simple"},
        {"question": "What is the current bed occupancy rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the LWBS rate for the past week", "category": "aggregation", "complexity": "simple"},
        {"question": "How many patients are currently boarding in the ED?", "category": "count", "complexity": "simple"},
        {"question": "What is the average lab turnaround time?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many critical lab results were reported today?", "category": "count", "complexity": "simple"},
        {"question": "Show me the average imaging turnaround by modality", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the door-to-doc time by acuity level?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me the top 10 chief complaints by volume", "category": "ranking", "complexity": "medium"},
        {"question": "What is the ED length of stay by disposition type?", "category": "aggregation", "complexity": "medium"},
        {"question": "Compare day shift vs night shift door-to-doc times", "category": "comparison", "complexity": "medium"},
        {"question": "Show me visits where door-to-doc exceeded 60 minutes by acuity", "category": "filtering", "complexity": "medium"},
        {"question": "What is the bed turnaround time trend over the past 30 days?", "category": "trend", "complexity": "medium"},
        {"question": "List providers with the highest average patients per shift", "category": "ranking", "complexity": "medium"},
        {"question": "What is the correlation between ED volume and door-to-doc time?", "category": "correlation", "complexity": "complex"},
        {"question": "Show me the full patient flow from arrival to discharge with all timestamps", "category": "journey", "complexity": "complex"},
        {"question": "Build an ED capacity forecast for the next 7 days based on historical patterns", "category": "forecasting", "complexity": "complex"},
        {"question": "Compare our ED metrics against CMS benchmarks", "category": "benchmarking", "complexity": "complex"},
        {"question": "What is the impact of boarding on ED throughput by hour of day?", "category": "calculation", "complexity": "complex"},
        {"question": "Show me the optimal staffing model based on volume patterns and acuity mix", "category": "optimization", "complexity": "very_complex"},
        {"question": "Generate a comprehensive ED scorecard with throughput quality and safety metrics", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Analyze the relationship between ED crowding and patient safety events", "category": "correlation", "complexity": "very_complex"},
        {"question": "What is the total cost of boarding including opportunity cost and diversions?", "category": "calculation", "complexity": "very_complex"},
        {"question": "Build a real-time ED flow dashboard with predictive wait times", "category": "dashboard", "complexity": "very_complex"},
    ],
}

# ---------------------------------------------------------------------------
# SCENARIO 27: Readmission Risk - Physician Visible + Governance Gaps
# ---------------------------------------------------------------------------
SCENARIO_27 = {
    'id': 27,
    'name': 'Readmission Risk Analytics',
    'domain': 'Population Health',
    'agent_name': 'Readmission_Risk_Agent',
    'agent_id': 'readmission-risk-agent-001',
    'model_id': 'readmission-risk-model-001',
    'model_name': 'Readmission_Risk_Model',
    'description': 'Readmission risk agent that exposes physician identifiers in query results, lacks PII governance controls, and has framing risk in risk score presentation.',
    'issues': ['physician_visible', 'governance_gaps', 'pii_exposure', 'framing_risk', 'missing_descriptions'],
    'instruction_text': (
        "Readmission risk analytics agent for 30-day all-cause readmission analysis.\n"
        "HIPAA NOTE: Never show patient names or SSN in outputs. Physician names are OK to display.\n"
        "Risk scores range from 0-100 (higher = more likely to readmit).\n"
        "Use admissions table for encounter data. Use risk_scores for predictive model outputs.\n"
        "Social determinants (SDOH) data is linked by patient_id.\n"
        "Interventions table tracks care management activities post-discharge.\n"
        "NOTE: The attending_physician and discharging_physician fields contain full names."
    ),
    'tables': [
        {'name': 'admissions', 'row_count': 300000, 'columns': ['admission_id', 'patient_id', 'admit_date', 'discharge_date', 'los_days', 'drg_code', 'drg_weight', 'attending_physician', 'discharging_physician', 'discharge_disposition', 'is_readmission', 'readmit_days', 'payer', 'department', 'facility'], 'description': ''},
        {'name': 'risk_scores', 'row_count': 300000, 'columns': ['score_id', 'admission_id', 'patient_id', 'readmit_risk_score', 'model_version', 'scored_date', 'risk_factors', 'confidence_interval', 'decile'], 'description': ''},
        {'name': 'social_determinants', 'row_count': 150000, 'columns': ['sdoh_id', 'patient_id', 'zip_code', 'median_income', 'food_insecurity_flag', 'housing_instability', 'transportation_barrier', 'health_literacy_score', 'language_preference', 'insurance_type'], 'description': ''},
        {'name': 'interventions', 'row_count': 200000, 'columns': ['intervention_id', 'admission_id', 'patient_id', 'intervention_type', 'start_date', 'end_date', 'assigned_to', 'status', 'outcome', 'cost'], 'description': ''},
        {'name': 'diagnoses', 'row_count': 1500000, 'columns': ['dx_id', 'admission_id', 'icd10_code', 'description', 'dx_type', 'sequence', 'present_on_admit'], 'description': ''},
        {'name': 'patient_demographics', 'row_count': 150000, 'columns': ['patient_id', 'age', 'gender', 'race', 'ethnicity', 'zip_code', 'primary_care_physician', 'insurance_id', 'language'], 'description': ''},
    ],
    'measures': [
        {'name': 'Readmission Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(admissions), admissions[is_readmission]=TRUE()), COUNTROWS(admissions))', 'description': ''},
        {'name': '30-Day Readmission Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(admissions), admissions[readmit_days]<=30, admissions[is_readmission]=TRUE()), COUNTROWS(admissions))', 'description': ''},
        {'name': 'Avg Risk Score', 'expression': 'AVERAGE(risk_scores[readmit_risk_score])', 'description': ''},
        {'name': 'Intervention Success Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(interventions), interventions[outcome]="Successful"), COUNTROWS(interventions))', 'description': ''},
        {'name': 'Cost Per Readmission', 'expression': 'DIVIDE(SUM(interventions[cost]), CALCULATE(COUNTROWS(admissions), admissions[is_readmission]=TRUE()))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the 30-day readmission rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many patients were readmitted this quarter?", "category": "count", "complexity": "simple"},
        {"question": "What is the average risk score across all admissions?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me readmission counts by payer type", "category": "aggregation", "complexity": "simple"},
        {"question": "How many interventions are currently active?", "category": "count", "complexity": "simple"},
        {"question": "What is the most common diagnosis for readmitted patients?", "category": "ranking", "complexity": "simple"},
        {"question": "Show readmission rate by department", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the intervention success rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show readmission rates by attending physician", "category": "aggregation", "complexity": "medium"},
        {"question": "Which physicians have the highest readmission rates?", "category": "ranking", "complexity": "medium"},
        {"question": "Show me patients with risk score > 80 and their demographics", "category": "filtering", "complexity": "medium"},
        {"question": "What is the readmission rate by zip code?", "category": "aggregation", "complexity": "medium"},
        {"question": "Compare readmission rates for patients with vs without SDOH barriers", "category": "comparison", "complexity": "medium"},
        {"question": "Show the trend of readmission rates over the past 12 months", "category": "trend", "complexity": "medium"},
        {"question": "What interventions are most effective at preventing readmissions?", "category": "ranking", "complexity": "medium"},
        {"question": "Build a readmission risk profile by DRG and payer", "category": "calculation", "complexity": "complex"},
        {"question": "What is the ROI of our care management program by intervention type?", "category": "calculation", "complexity": "complex"},
        {"question": "Show me the physician-level readmission scorecard with case mix adjustment", "category": "dashboard", "complexity": "complex"},
        {"question": "Identify the top predictors of readmission from social determinants data", "category": "correlation", "complexity": "complex"},
        {"question": "What is the estimated cost avoidance from our readmission prevention program?", "category": "calculation", "complexity": "complex"},
        {"question": "Generate a comprehensive population health dashboard with risk stratification", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Build a patient-level readmission risk report with intervention recommendations", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "Compare our readmission performance against CMS HRRP targets", "category": "benchmarking", "complexity": "very_complex"},
        {"question": "What is the financial impact of readmissions including penalties and lost revenue by service line?", "category": "calculation", "complexity": "very_complex"},
        {"question": "Create an automated risk triage workflow based on score thresholds and available resources", "category": "optimization", "complexity": "very_complex"},
    ],
}

# ---------------------------------------------------------------------------
# SCENARIO 28: Surgical Outcomes - OR Utilization + Framing Risk
# ---------------------------------------------------------------------------
SCENARIO_28 = {
    'id': 28,
    'name': 'Surgical Outcomes & OR Utilization',
    'domain': 'Perioperative',
    'agent_name': 'Surgical_Outcomes_Agent',
    'agent_id': 'surgical-outcomes-agent-001',
    'model_id': 'surgical-outcomes-model-001',
    'model_name': 'Surgical_Outcomes_Model',
    'description': 'Surgical outcomes agent with ambiguous time window calculations for complications, OR utilization metrics that double-count block time, and framing risk in complication rates.',
    'issues': ['framing_risk', 'ambiguous_time_windows', 'double_counting', 'missing_topn', 'instruction_bloat'],
    'instruction_text': (
        "Surgical outcomes and OR utilization analytics agent for perioperative performance analysis.\n"
        "Track surgical cases from scheduling through post-op outcomes. Complication rates should be presented as X per 1000 cases not percentages to avoid framing bias.\n"
        "OR utilization = (wheels-in to wheels-out) / (block_end - block_start). Note: Block time includes turnover.\n"
        "IMPORTANT: First-case starts are measured from scheduled_start, not block_start.\n"
        "Surgeon performance metrics MUST be risk-adjusted using ASA class and case complexity.\n"
        "Complications are tracked at 30-day and 90-day windows.\n"
        "NOTE: Some complications are flagged both as 30-day and 90-day - do not double-count.\n"
        "For SSI (surgical site infection), use the 30-day window for superficial and 90-day for deep/organ-space.\n"
        "Equipment tracking uses the surgical_supplies table - costs are per-case.\n"
        "Anesthesia times should use anesthesia_start to anesthesia_end, not incision times.\n"
        "The case_status field values are: Completed, Cancelled, Add-on, Delayed, Converted.\n"
        "Emergency cases are identified by case_class = 'Emergency' (not 'Emergent').\n"
        "DEPRECATED: Do not use the old case_log table - it was replaced by surgical_cases in Q3 2025."
    ),
    'tables': [
        {'name': 'surgical_cases', 'row_count': 180000, 'columns': ['case_id', 'patient_id', 'surgeon_id', 'procedure_code', 'procedure_desc', 'scheduled_date', 'scheduled_start', 'wheels_in', 'incision_time', 'close_time', 'wheels_out', 'anesthesia_start', 'anesthesia_end', 'or_room', 'case_class', 'case_status', 'asa_class', 'complexity_score', 'service_line', 'block_owner'], 'description': ''},
        {'name': 'complications', 'row_count': 25000, 'columns': ['complication_id', 'case_id', 'patient_id', 'complication_type', 'severity', 'detected_date', 'days_post_op', 'window_30day', 'window_90day', 'treatment_required', 'readmission_required'], 'description': ''},
        {'name': 'or_utilization', 'row_count': 365000, 'columns': ['util_id', 'or_room', 'block_date', 'block_start', 'block_end', 'block_owner', 'allocated_minutes', 'used_minutes', 'turnover_minutes', 'cases_in_block', 'first_case_delay_min'], 'description': ''},
        {'name': 'surgeon_directory', 'row_count': 300, 'columns': ['surgeon_id', 'surgeon_name', 'specialty', 'department', 'hire_date', 'privileges', 'volume_tier'], 'description': ''},
        {'name': 'surgical_supplies', 'row_count': 600000, 'columns': ['supply_id', 'case_id', 'item_name', 'category', 'quantity', 'unit_cost', 'total_cost', 'vendor', 'implant_flag'], 'description': ''},
        {'name': 'anesthesia_records', 'row_count': 180000, 'columns': ['record_id', 'case_id', 'anesthesia_type', 'asa_class', 'start_time', 'end_time', 'provider_id', 'complications'], 'description': ''},
        {'name': 'case_log', 'row_count': 150000, 'columns': ['log_id', 'case_id', 'event_type', 'event_time', 'notes'], 'description': 'DEPRECATED - use surgical_cases'},
    ],
    'measures': [
        {'name': 'OR Utilization', 'expression': 'DIVIDE(SUM(or_utilization[used_minutes]), SUM(or_utilization[allocated_minutes]))', 'description': ''},
        {'name': 'OR Utilization %', 'expression': 'DIVIDE(SUM(or_utilization[used_minutes]) + SUM(or_utilization[turnover_minutes]), SUM(or_utilization[allocated_minutes]))', 'description': ''},
        {'name': 'Complication Rate', 'expression': 'DIVIDE(COUNTROWS(complications), COUNTROWS(surgical_cases)) * 100', 'description': 'Uses percentage - framing risk'},
        {'name': 'Complication Rate per 1000', 'expression': 'DIVIDE(COUNTROWS(complications), COUNTROWS(surgical_cases)) * 1000', 'description': ''},
        {'name': 'First Case On-Time Start', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(or_utilization), or_utilization[first_case_delay_min]<=5), COUNTROWS(or_utilization))', 'description': ''},
        {'name': 'Avg Turnover Time', 'expression': 'AVERAGE(or_utilization[turnover_minutes])', 'description': ''},
        {'name': 'Supply Cost Per Case', 'expression': 'DIVIDE(SUM(surgical_supplies[total_cost]), COUNTROWS(surgical_cases))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the overall OR utilization rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many surgical cases were completed this month?", "category": "count", "complexity": "simple"},
        {"question": "What is the average turnover time between cases?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the complication rate for this quarter", "category": "aggregation", "complexity": "simple"},
        {"question": "How many cases were cancelled and why?", "category": "count", "complexity": "simple"},
        {"question": "What is the first-case on-time start rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show total supply costs by category", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the average case duration by service line?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show OR utilization by room and day of week", "category": "aggregation", "complexity": "medium"},
        {"question": "Which surgeons have the highest case volumes?", "category": "ranking", "complexity": "medium"},
        {"question": "What is the complication rate by procedure type?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me cases with turnover time exceeding 45 minutes", "category": "filtering", "complexity": "medium"},
        {"question": "Compare block utilization across service lines", "category": "comparison", "complexity": "medium"},
        {"question": "What are the top 10 most expensive procedures by supply cost?", "category": "ranking", "complexity": "medium"},
        {"question": "Show the trend of first-case delay minutes over the past 6 months", "category": "trend", "complexity": "medium"},
        {"question": "Build a risk-adjusted complication scorecard by surgeon", "category": "dashboard", "complexity": "complex"},
        {"question": "What is the financial impact of OR underutilization by block owner?", "category": "calculation", "complexity": "complex"},
        {"question": "Compare 30-day vs 90-day complication rates by procedure category", "category": "comparison", "complexity": "complex"},
        {"question": "Show me the full surgical case journey from scheduling to 90-day outcomes", "category": "journey", "complexity": "complex"},
        {"question": "What is the optimal block allocation based on historical utilization patterns?", "category": "optimization", "complexity": "complex"},
        {"question": "Generate a comprehensive perioperative dashboard with safety quality and efficiency metrics", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Build a surgeon-level performance report with case mix volume and outcomes", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "What is the total cost of surgical complications including readmissions and extended stays?", "category": "calculation", "complexity": "very_complex"},
        {"question": "Compare our surgical outcomes against NSQIP benchmarks by specialty", "category": "benchmarking", "complexity": "very_complex"},
        {"question": "Optimize OR scheduling to minimize turnover time and maximize block utilization", "category": "optimization", "complexity": "very_complex"},
    ],
}

# ---------------------------------------------------------------------------
# SCENARIO 29: Infection Control - Empty Results + Measure Not Found
# ---------------------------------------------------------------------------
SCENARIO_29 = {
    'id': 29,
    'name': 'Infection Control & Prevention',
    'domain': 'Infection Prevention',
    'agent_name': 'Infection_Control_Agent',
    'agent_id': 'infection-control-agent-001',
    'model_id': 'infection-control-model-001',
    'model_name': 'Infection_Control_Model',
    'description': 'Infection control agent with sparse surveillance data causing empty result sets, references to measures that do not exist in the model, and unclear HAI category mappings.',
    'issues': ['empty_results', 'measure_not_found', 'sparse_data', 'missing_descriptions', 'ambiguous_entities'],
    'instruction_text': (
        "Infection prevention and control analytics agent for HAI surveillance and antibiotic stewardship.\n"
        "Track healthcare-associated infections (HAIs): CLABSI, CAUTI, SSI, MRSA, C.diff.\n"
        "SIR (Standardized Infection Ratio) = observed infections / expected infections.\n"
        "IMPORTANT: Hand hygiene data is collected by direct observation - compliance rate is observations_compliant / total_observations.\n"
        "Note: Some infection types have very low counts per unit per month - use quarterly aggregation for statistical validity.\n"
        "Antibiotic DOT (Days of Therapy) = sum of antibiotic_days across all agents for a patient.\n"
        "Use the Device Utilization Ratio for central lines and urinary catheters.\n"
        "Reference the CDC/NHSN definitions for HAI classification.\n"
        "The hai_events table tracks confirmed HAIs. The surveillance_cultures table tracks all cultures (including negatives)."
    ),
    'tables': [
        {'name': 'hai_events', 'row_count': 2500, 'columns': ['event_id', 'patient_id', 'unit', 'infection_type', 'organism', 'event_date', 'device_related', 'device_type', 'device_days', 'severity', 'outcome', 'reported_to_nhsn'], 'description': ''},
        {'name': 'surveillance_cultures', 'row_count': 150000, 'columns': ['culture_id', 'patient_id', 'unit', 'specimen_type', 'organism', 'susceptibility', 'collection_date', 'result_date', 'positive_flag'], 'description': ''},
        {'name': 'device_days', 'row_count': 500000, 'columns': ['dd_id', 'unit', 'device_type', 'date', 'patient_count', 'device_count', 'utilization_ratio'], 'description': ''},
        {'name': 'hand_hygiene', 'row_count': 200000, 'columns': ['obs_id', 'unit', 'observer_id', 'observation_date', 'role_observed', 'moment', 'compliant', 'gel_or_wash'], 'description': ''},
        {'name': 'antibiotic_usage', 'row_count': 400000, 'columns': ['usage_id', 'patient_id', 'antibiotic_name', 'antibiotic_class', 'start_date', 'end_date', 'route', 'indication', 'dot_days', 'unit', 'prescriber_id'], 'description': ''},
        {'name': 'environmental_rounds', 'row_count': 50000, 'columns': ['round_id', 'unit', 'round_date', 'inspector_id', 'score', 'deficiencies_found', 'corrective_actions'], 'description': ''},
        {'name': 'isolation_precautions', 'row_count': 80000, 'columns': ['isolation_id', 'patient_id', 'unit', 'precaution_type', 'start_date', 'end_date', 'reason', 'compliance_checks'], 'description': ''},
    ],
    'measures': [
        {'name': 'CLABSI Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]="CLABSI"), SUM(device_days[device_count])) * 1000', 'description': ''},
        {'name': 'CAUTI Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]="CAUTI"), SUM(device_days[device_count])) * 1000', 'description': ''},
        {'name': 'Hand Hygiene Compliance', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(hand_hygiene), hand_hygiene[compliant]=TRUE()), COUNTROWS(hand_hygiene))', 'description': ''},
        {'name': 'Antibiotic DOT per 1000 Patient Days', 'expression': 'DIVIDE(SUM(antibiotic_usage[dot_days]), SUM(device_days[patient_count])) * 1000', 'description': ''},
        {'name': 'SSI Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]="SSI"), COUNTROWS(hai_events))', 'description': 'Wrong denominator - should be surgical cases'},
    ],
    'questions': [
        {"question": "What is the CLABSI rate this quarter?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me hand hygiene compliance by unit", "category": "aggregation", "complexity": "simple"},
        {"question": "How many HAIs were reported this month?", "category": "count", "complexity": "simple"},
        {"question": "What is the antibiotic DOT per 1000 patient days?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the device utilization ratio for central lines", "category": "aggregation", "complexity": "simple"},
        {"question": "How many MRSA cases were identified this quarter?", "category": "count", "complexity": "simple"},
        {"question": "What is the environmental round average score?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show C.diff cases by unit", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the SIR for CLABSI by unit?", "category": "aggregation", "complexity": "medium"},
        {"question": "Show me the trend of hand hygiene compliance over 12 months", "category": "trend", "complexity": "medium"},
        {"question": "Which antibiotics have the highest DOT per 1000 patient days?", "category": "ranking", "complexity": "medium"},
        {"question": "Compare HAI rates between ICU and non-ICU units", "category": "comparison", "complexity": "medium"},
        {"question": "Show units with hand hygiene compliance below 85%", "category": "filtering", "complexity": "medium"},
        {"question": "What is the most common organism in positive blood cultures?", "category": "ranking", "complexity": "medium"},
        {"question": "Show me CAUTI rates for units with catheter utilization above 0.5", "category": "filtering", "complexity": "medium"},
        {"question": "Build an infection prevention dashboard with all HAI rates and SIR values", "category": "dashboard", "complexity": "complex"},
        {"question": "What is the correlation between hand hygiene compliance and HAI rates by unit?", "category": "correlation", "complexity": "complex"},
        {"question": "Compare our antibiotic prescribing patterns against stewardship guidelines", "category": "benchmarking", "complexity": "complex"},
        {"question": "Show me the SSI rate by procedure category with risk stratification", "category": "risk_scoring", "complexity": "complex"},
        {"question": "What is the estimated cost of HAIs including extended stays and treatments?", "category": "calculation", "complexity": "complex"},
        {"question": "Generate a comprehensive NHSN-format infection control report for all HAI types", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Build an antibiotic stewardship scorecard with DOT prescribing patterns and resistance trends", "category": "dashboard", "complexity": "very_complex"},
        {"question": "What is the optimal hand hygiene observation strategy to maximize compliance detection?", "category": "optimization", "complexity": "very_complex"},
        {"question": "Analyze the relationship between staffing levels environmental scores and HAI rates", "category": "correlation", "complexity": "very_complex"},
        {"question": "Predict HAI risk by unit based on device utilization staffing and historical infection data", "category": "risk_scoring", "complexity": "very_complex"},
    ],
}

# ---------------------------------------------------------------------------
# SCENARIO 30: Nursing Quality - Hidden Columns + CU Throttling
# ---------------------------------------------------------------------------
SCENARIO_30 = {
    'id': 30,
    'name': 'Nursing Quality Metrics',
    'domain': 'Nursing Administration',
    'agent_name': 'Nursing_Quality_Agent',
    'agent_id': 'nursing-quality-agent-001',
    'model_id': 'nursing-quality-model-001',
    'model_name': 'Nursing_Quality_Model',
    'description': 'Nursing quality agent with hidden columns inadvertently exposed in queries, excessive measure count triggering CU throttling, and duplicate NDNQI metric definitions.',
    'issues': ['hidden_columns_exposed', 'excessive_measures', 'cu_throttling', 'measure_ambiguity', 'schema_sprawl'],
    'instruction_text': (
        "Nursing quality and patient safety analytics agent for NDNQI metrics, falls prevention, pressure injuries, and nurse-sensitive indicators.\n"
        "Track falls rate as falls per 1000 patient days. Pressure injury rate as PI per 1000 patient days.\n"
        "RN hours per patient day = total RN hours / patient days.\n"
        "Use nurse_assessments for Braden scores, fall risk scores, and pain assessments.\n"
        "HCAHPS scores are on a 0-100 scale (top-box percentage).\n"
        "NOTE: The patient_satisfaction table has 42 columns - most are hidden internal scoring fields. Only show summary scores.\n"
        "NOTE: Some NDNQI measures have two versions (rate-based and ratio-based) - always prefer the rate version.\n"
        "Restraint usage should be reported as episodes per 1000 patient days.\n"
        "Medication errors are tracked in the safety_events table with near-miss and actual harm categories.\n"
        "Nurse turnover data is in the workforce table - voluntary_termination flag indicates type.\n"
        "The unit_census table is the source of truth for patient days - do not calculate from admissions."
    ),
    'tables': [
        {'name': 'falls', 'row_count': 15000, 'columns': ['fall_id', 'patient_id', 'unit', 'fall_date', 'fall_time', 'injury_level', 'assisted', 'location', 'contributing_factors', 'prevention_protocol_followed', 'nurse_id', 'witness_id'], 'description': ''},
        {'name': 'pressure_injuries', 'row_count': 8000, 'columns': ['pi_id', 'patient_id', 'unit', 'assessment_date', 'stage', 'location_body', 'present_on_admit', 'braden_score', 'prevention_bundle_compliant', 'nurse_id'], 'description': ''},
        {'name': 'nurse_assessments', 'row_count': 2000000, 'columns': ['assessment_id', 'patient_id', 'unit', 'assessment_date', 'assessment_type', 'score', 'risk_level', 'nurse_id', 'shift'], 'description': ''},
        {'name': 'patient_satisfaction', 'row_count': 100000, 'columns': ['survey_id', 'patient_id', 'unit', 'discharge_date', 'overall_rating', 'nurse_communication', 'responsiveness', 'pain_management', 'medication_communication', 'discharge_info', 'cleanliness', 'quietness', '_internal_weight', '_adj_factor', '_region_code', '_raw_score_1', '_raw_score_2', '_raw_score_3', '_raw_score_4', '_raw_score_5', '_calc_flag', '_version', '_batch_id', '_import_date', '_validation_status'], 'description': ''},
        {'name': 'safety_events', 'row_count': 20000, 'columns': ['event_id', 'patient_id', 'unit', 'event_date', 'event_type', 'severity', 'category', 'harm_level', 'root_cause', 'contributing_factors', 'reporter_id', 'status'], 'description': ''},
        {'name': 'unit_census', 'row_count': 365000, 'columns': ['census_id', 'unit', 'date', 'patient_days', 'midnight_census', 'admissions', 'discharges', 'transfers_in', 'transfers_out'], 'description': ''},
        {'name': 'workforce', 'row_count': 5000, 'columns': ['nurse_id', 'name', 'unit', 'role', 'hire_date', 'termination_date', 'voluntary_termination', 'education_level', 'certification', 'fte_status', 'hourly_rate'], 'description': ''},
        {'name': 'staffing_hours', 'row_count': 365000, 'columns': ['record_id', 'unit', 'date', 'rn_hours', 'lpn_hours', 'cna_hours', 'total_hours', 'agency_hours', 'overtime_hours', 'shift_type'], 'description': ''},
        {'name': 'restraints', 'row_count': 5000, 'columns': ['restraint_id', 'patient_id', 'unit', 'start_date', 'end_date', 'type', 'reason', 'ordering_provider', 'nurse_id', 'assessment_frequency'], 'description': ''},
        {'name': 'education_compliance', 'row_count': 25000, 'columns': ['record_id', 'nurse_id', 'course_name', 'due_date', 'completion_date', 'status', 'category'], 'description': ''},
    ],
    'measures': [
        {'name': 'Falls Rate', 'expression': 'DIVIDE(COUNTROWS(falls), SUM(unit_census[patient_days])) * 1000', 'description': ''},
        {'name': 'Fall Rate', 'expression': 'DIVIDE(COUNTROWS(falls), SUM(unit_census[midnight_census])) * 1000', 'description': ''},
        {'name': 'PI Rate', 'expression': 'DIVIDE(COUNTROWS(pressure_injuries), SUM(unit_census[patient_days])) * 1000', 'description': ''},
        {'name': 'Pressure Injury Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(pressure_injuries), pressure_injuries[present_on_admit]=FALSE()), SUM(unit_census[patient_days])) * 1000', 'description': ''},
        {'name': 'RN HPPD', 'expression': 'DIVIDE(SUM(staffing_hours[rn_hours]), SUM(unit_census[patient_days]))', 'description': ''},
        {'name': 'Total HPPD', 'expression': 'DIVIDE(SUM(staffing_hours[total_hours]), SUM(unit_census[patient_days]))', 'description': ''},
        {'name': 'HCAHPS Nurse Communication', 'expression': 'AVERAGE(patient_satisfaction[nurse_communication])', 'description': ''},
        {'name': 'Safety Event Rate', 'expression': 'DIVIDE(COUNTROWS(safety_events), SUM(unit_census[patient_days])) * 1000', 'description': ''},
        {'name': 'Nurse Turnover', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(workforce), workforce[voluntary_termination]=TRUE()), COUNTROWS(workforce))', 'description': ''},
        {'name': 'Restraint Rate', 'expression': 'DIVIDE(COUNTROWS(restraints), SUM(unit_census[patient_days])) * 1000', 'description': ''},
        {'name': 'Education Compliance', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(education_compliance), education_compliance[status]="Complete"), COUNTROWS(education_compliance))', 'description': ''},
    ],
    'questions': [
        {"question": "What is the falls rate per 1000 patient days?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me the pressure injury rate by unit", "category": "aggregation", "complexity": "simple"},
        {"question": "What is the RN hours per patient day?", "category": "aggregation", "complexity": "simple"},
        {"question": "How many safety events were reported this month?", "category": "count", "complexity": "simple"},
        {"question": "What is the HCAHPS nurse communication score?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show nurse turnover rate by unit", "category": "aggregation", "complexity": "simple"},
        {"question": "How many restraint episodes occurred this quarter?", "category": "count", "complexity": "simple"},
        {"question": "What is the education compliance rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show falls rate trend over the past 12 months by unit", "category": "trend", "complexity": "medium"},
        {"question": "Which units have the highest pressure injury rates?", "category": "ranking", "complexity": "medium"},
        {"question": "Compare RN HPPD to total HPPD by unit", "category": "comparison", "complexity": "medium"},
        {"question": "Show me patient satisfaction scores by unit and domain", "category": "aggregation", "complexity": "medium"},
        {"question": "What are the most common contributing factors for falls?", "category": "ranking", "complexity": "medium"},
        {"question": "Show units where falls rate exceeds NDNQI benchmark", "category": "filtering", "complexity": "medium"},
        {"question": "What is the correlation between staffing levels and falls rates?", "category": "correlation", "complexity": "medium"},
        {"question": "Build a nursing quality dashboard with all NDNQI indicators", "category": "dashboard", "complexity": "complex"},
        {"question": "What is the impact of agency staffing on patient safety event rates?", "category": "correlation", "complexity": "complex"},
        {"question": "Compare our nursing quality metrics against Magnet hospital benchmarks", "category": "benchmarking", "complexity": "complex"},
        {"question": "Show the relationship between nurse education level and patient outcomes", "category": "correlation", "complexity": "complex"},
        {"question": "What is the estimated cost savings from falls prevention programs?", "category": "calculation", "complexity": "complex"},
        {"question": "Generate a comprehensive NDNQI submission report with all required metrics and benchmarks", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Build a predictive model for fall risk based on assessment scores staffing and unit characteristics", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "What is the optimal nurse-to-patient ratio by unit based on acuity and outcomes data?", "category": "optimization", "complexity": "very_complex"},
        {"question": "Analyze the total cost of nurse-sensitive adverse events including legal liability and CMS penalties", "category": "calculation", "complexity": "very_complex"},
        {"question": "Create a nurse retention strategy scorecard with turnover engagement and career development metrics", "category": "dashboard", "complexity": "very_complex"},
    ],
}

# ---------------------------------------------------------------------------
# SCENARIO 31: Patient Safety - NL2DAX Contamination + Temporal Ambiguity
# ---------------------------------------------------------------------------
SCENARIO_31 = {
    'id': 31,
    'name': 'Patient Safety & Event Reporting',
    'domain': 'Quality & Safety',
    'agent_name': 'Patient_Safety_Agent',
    'agent_id': 'patient-safety-agent-001',
    'model_id': 'patient-safety-model-001',
    'model_name': 'Patient_Safety_Model',
    'description': 'Patient safety agent with NL2DAX contamination from colloquial safety terms, ambiguous temporal references (fiscal vs calendar year), and event correlation challenges across disparate tables.',
    'issues': ['nl2dax_contamination', 'ambiguous_temporal', 'event_correlation', 'instruction_contradictions', 'missing_topn'],
    'instruction_text': (
        "Patient safety and quality improvement analytics agent for adverse event tracking, root cause analysis, and regulatory compliance.\n"
        "Track all patient safety events from voluntary reporting system. Severity uses NCC MERP scale (A-I).\n"
        "IMPORTANT: Near miss = Category A-D (no harm reached patient). Adverse event = Category E-I (harm reached patient).\n"
        "Note: Sentinel event is a subset of adverse events requiring immediate RCA - Category G-I only.\n"
        "Mortality review data is in a separate table from safety events - do not conflate.\n"
        "IMPORTANT: Fiscal year starts October 1. When users say this year they mean fiscal year.\n"
        "ALSO IMPORTANT: When users say this year they usually mean calendar year.\n"
        "Use event_reports for voluntary reports. Use claims_data for malpractice information.\n"
        "The PSI (Patient Safety Indicator) calculations follow AHRQ methodology.\n"
        "Peer review data is PRIVILEGED and CONFIDENTIAL - never include in standard reports.\n"
        "Root cause categories: Human Factors, Communication, Equipment, Environment, Process, Policy.\n"
        "Action items from RCA are tracked in the improvement_actions table."
    ),
    'tables': [
        {'name': 'event_reports', 'row_count': 50000, 'columns': ['report_id', 'patient_id', 'unit', 'event_date', 'event_time', 'event_type', 'severity_category', 'harm_level', 'description', 'reporter_id', 'reporter_role', 'contributing_factors', 'immediate_actions', 'status', 'follow_up_date'], 'description': ''},
        {'name': 'root_cause_analyses', 'row_count': 2000, 'columns': ['rca_id', 'event_id', 'rca_date', 'root_causes', 'contributing_factors', 'system_factors', 'recommendations', 'team_members', 'status', 'completion_date'], 'description': ''},
        {'name': 'improvement_actions', 'row_count': 8000, 'columns': ['action_id', 'rca_id', 'event_id', 'action_description', 'assigned_to', 'due_date', 'completion_date', 'status', 'effectiveness_rating', 'verification_method'], 'description': ''},
        {'name': 'mortality_reviews', 'row_count': 5000, 'columns': ['review_id', 'patient_id', 'death_date', 'review_date', 'reviewer_id', 'preventability_score', 'contributing_factors', 'department', 'service_line', 'disposition'], 'description': ''},
        {'name': 'peer_review', 'row_count': 10000, 'columns': ['review_id', 'case_id', 'physician_id', 'review_date', 'reviewer_id', 'category', 'rating', 'concerns', 'recommendations', 'privileged_flag'], 'description': 'PRIVILEGED - do not include in standard reports'},
        {'name': 'claims_data', 'row_count': 3000, 'columns': ['claim_id', 'event_id', 'patient_id', 'filing_date', 'claim_type', 'alleged_harm', 'department', 'provider_id', 'status', 'settlement_amount', 'defense_cost'], 'description': ''},
        {'name': 'psi_indicators', 'row_count': 100000, 'columns': ['psi_id', 'patient_id', 'admission_id', 'psi_number', 'psi_description', 'numerator_flag', 'denominator_flag', 'discharge_date', 'department'], 'description': ''},
        {'name': 'safety_culture_survey', 'row_count': 15000, 'columns': ['response_id', 'unit', 'survey_year', 'domain', 'score', 'respondent_role', 'years_experience'], 'description': ''},
    ],
    'measures': [
        {'name': 'Event Rate', 'expression': 'DIVIDE(COUNTROWS(event_reports), 1000)', 'description': 'Missing denominator - should be per patient days'},
        {'name': 'Harm Event Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(event_reports), event_reports[harm_level]>0), COUNTROWS(event_reports))', 'description': ''},
        {'name': 'RCA Completion Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(root_cause_analyses), root_cause_analyses[status]="Complete"), COUNTROWS(root_cause_analyses))', 'description': ''},
        {'name': 'Action Completion Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(improvement_actions), improvement_actions[status]="Complete"), COUNTROWS(improvement_actions))', 'description': ''},
        {'name': 'Claims Cost', 'expression': 'SUM(claims_data[settlement_amount]) + SUM(claims_data[defense_cost])', 'description': ''},
        {'name': 'Preventable Mortality Rate', 'expression': 'DIVIDE(CALCULATE(COUNTROWS(mortality_reviews), mortality_reviews[preventability_score]>=3), COUNTROWS(mortality_reviews))', 'description': ''},
    ],
    'questions': [
        {"question": "How many safety events were reported this year?", "category": "count", "complexity": "simple"},
        {"question": "What is the harm event rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show me event reports by severity category", "category": "aggregation", "complexity": "simple"},
        {"question": "How many RCAs are currently in progress?", "category": "count", "complexity": "simple"},
        {"question": "What is the action completion rate?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show total claims costs this fiscal year", "category": "aggregation", "complexity": "simple"},
        {"question": "How many near misses were reported this quarter?", "category": "count", "complexity": "simple"},
        {"question": "What is the safety culture survey overall score?", "category": "aggregation", "complexity": "simple"},
        {"question": "Show event reporting trends over the past 12 months", "category": "trend", "complexity": "medium"},
        {"question": "Which units have the highest event reporting rates?", "category": "ranking", "complexity": "medium"},
        {"question": "Compare harm events across departments", "category": "comparison", "complexity": "medium"},
        {"question": "Show me sentinel events requiring immediate RCA", "category": "filtering", "complexity": "medium"},
        {"question": "What are the most common root causes identified in RCAs?", "category": "ranking", "complexity": "medium"},
        {"question": "Show overdue improvement actions by responsible party", "category": "filtering", "complexity": "medium"},
        {"question": "What is the medication error rate by unit?", "category": "aggregation", "complexity": "medium"},
        {"question": "Build a patient safety dashboard with event rates harm levels and action tracking", "category": "dashboard", "complexity": "complex"},
        {"question": "What is the correlation between safety culture scores and event rates by unit?", "category": "correlation", "complexity": "complex"},
        {"question": "Compare our PSI rates against AHRQ national benchmarks", "category": "benchmarking", "complexity": "complex"},
        {"question": "Show the full lifecycle of a safety event from report to RCA to action to resolution", "category": "journey", "complexity": "complex"},
        {"question": "What is the financial impact of preventable adverse events including claims and CMS penalties?", "category": "calculation", "complexity": "complex"},
        {"question": "Generate a comprehensive Board-level quality and safety report with all key indicators", "category": "dashboard", "complexity": "very_complex"},
        {"question": "Build a predictive model for high-risk units based on event patterns staffing and culture scores", "category": "risk_scoring", "complexity": "very_complex"},
        {"question": "Analyze the effectiveness of our safety improvement programs across all domains", "category": "benchmarking", "complexity": "very_complex"},
        {"question": "What is the total cost of poor quality including adverse events claims regulatory penalties and reputation?", "category": "calculation", "complexity": "very_complex"},
        {"question": "Create an automated safety event triage system based on severity trending and historical patterns", "category": "optimization", "complexity": "very_complex"},
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

        base_ms = {
            'simple': random.randint(8000, 18000),
            'medium': random.randint(15000, 35000),
            'complex': random.randint(30000, 55000),
            'very_complex': random.randint(50000, 95000),
        }[complexity]

        if 'instruction_bloat' in issue_set and instr_len > 4800:
            base_ms += random.randint(3000, 8000)
        if 'schema_sprawl' in issue_set and table_count > 8:
            base_ms += random.randint(2000, 6000)
        if 'timeout_patterns' in issue_set and complexity in ('complex', 'very_complex'):
            base_ms += random.randint(8000, 20000)
        if 'retry_dominant' in issue_set:
            base_ms += random.randint(2000, 5000)
        if 'empty_results' in issue_set and random.random() < 0.25:
            base_ms += random.randint(1000, 3000)
        if 'measure_not_found' in issue_set and random.random() < 0.15:
            base_ms += random.randint(2000, 5000)
        if 'nl2dax_contamination' in issue_set and complexity in ('medium', 'complex'):
            base_ms += random.randint(3000, 8000)
        if 'ambiguous_temporal' in issue_set:
            base_ms += random.randint(1000, 3000)
        if 'cu_throttling' in issue_set and random.random() < 0.1:
            base_ms += random.randint(10000, 25000)
        if 'governance_gaps' in issue_set:
            base_ms += random.randint(500, 2000)
        if 'framing_risk' in issue_set:
            base_ms += random.randint(500, 1500)

        retry_base = {'simple': 0, 'medium': 1, 'complex': 2, 'very_complex': 3}[complexity]
        if 'high_retries' in issue_set:
            retry_base += 2
        if 'retry_dominant' in issue_set:
            retry_base += 1
        if 'empty_results' in issue_set and random.random() < 0.2:
            retry_base += 1
        retries = min(retry_base + random.randint(0, 1), 5)

        total_ms = base_ms
        bd_parse = int(total_ms * random.uniform(0.03, 0.08))
        bd_schema = int(total_ms * random.uniform(0.08, 0.18))
        bd_nldax = int(total_ms * random.uniform(0.25, 0.45))
        bd_exec = int(total_ms * random.uniform(0.25, 0.45))
        bd_synth = max(500, total_ms - bd_parse - bd_schema - bd_nldax - bd_exec)
        bd_other = int(total_ms * random.uniform(0.02, 0.06))

        if 'schema_lookup_bottleneck' in issue_set:
            bd_schema = int(total_ms * random.uniform(0.25, 0.40))
            bd_nldax = int(total_ms * random.uniform(0.15, 0.25))
        if 'cu_throttling' in issue_set and random.random() < 0.1:
            bd_exec = int(total_ms * random.uniform(0.50, 0.70))

        tables_used = ','.join(t['name'] for t in scenario['tables'][:5])
        dax = "EVALUATE SUMMARIZE(%s, %s[%s])" % (
            scenario['tables'][0]['name'],
            scenario['tables'][0]['name'],
            scenario['tables'][0]['columns'][0],
        )

        physician_visible = 1 if 'physician_visible' in issue_set and random.random() < 0.4 else 0

        if 'empty_results' in issue_set and random.random() < 0.15:
            pass_fail = 'empty'
        elif 'measure_not_found' in issue_set and random.random() < 0.1:
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
            'physician_visible': physician_visible,
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
    db_path = os.path.join(output_dir, 'scenario_%02d.db' % scenario['id'])

    if os.path.exists(db_path):
        os.remove(db_path)

    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA_SQL)

    model_id = scenario['model_id']
    agent_id = scenario['agent_id']
    now = datetime.utcnow().isoformat()

    db.execute('INSERT INTO models VALUES (?,?,?,?,?,?,?,?)', (
        model_id, WORKSPACE_ID, scenario['model_name'],
        sum(t['row_count'] for t in scenario['tables']) * 0.001,
        'DirectLake', now, 1, now,
    ))

    for i, t in enumerate(scenario['tables']):
        db.execute('INSERT INTO tables VALUES (?,?,?,?,?,?,?,?)', (
            'tbl_%d' % i, model_id, t['name'],
            t['row_count'], len(t['columns']),
            0, 'single', t.get('description', ''),
        ))
        for j, col in enumerate(t['columns']):
            db.execute('INSERT INTO columns VALUES (?,?,?,?,?,?,?)', (
                'col_%d_%d' % (i, j), 'tbl_%d' % i, model_id, col,
                'string', random.randint(10, 50000), 0,
            ))

    for i, m in enumerate(scenario.get('measures', [])):
        db.execute('INSERT INTO measures VALUES (?,?,?,?,?,?,?)', (
            'm_%d' % i, model_id, 'tbl_0',
            m['name'], m['expression'],
            m.get('description', ''), 0,
        ))

    instr = scenario['instruction_text']
    db.execute('INSERT INTO agent_config VALUES (?,?,?,?,?,?,?,?)', (
        'agent_%s' % model_id[:8], model_id, WORKSPACE_ID,
        instr, len(instr), len(scenario['tables']),
        0, len(scenario['tables']),
    ))

    for t in traces:
        trace_id = 'trace_%s' % uuid.uuid4().hex[:8]
        db.execute('INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            trace_id, agent_id, model_id,
            t['question'], t['category'], t['total_ms'], t['retries'],
            t['dax_generated'], t['tables_used'], t['pass_fail'],
            t.get('physician_visible', 0),
            t['bd_parse'], t['bd_schema'], t['bd_nldax'],
            t['bd_exec'], t['bd_synth'], t['bd_other'],
            'test', 'run_%d' % scenario['id'],
        ))

    total_latencies = sorted([t['total_ms'] for t in traces])
    p50 = total_latencies[len(total_latencies) // 2] if total_latencies else 0
    p95 = total_latencies[int(len(total_latencies) * 0.95)] if total_latencies else 0

    db.execute('INSERT INTO cu_metrics VALUES (?,?,?,?,?,?,?,?,?)', (
        'cu_%s' % REAL_CAPACITY_ID[:8], model_id, WORKSPACE_ID,
        random.uniform(50, 200), random.uniform(100, 500),
        1 if 'cu_throttling' in scenario['issues'] else 0, p50, p95, now,
    ))

    db.commit()
    db.close()
    return db_path


def main():
    os.makedirs(SCENARIOS_DIR, exist_ok=True)

    scenarios = [SCENARIO_26, SCENARIO_27, SCENARIO_28, SCENARIO_29, SCENARIO_30, SCENARIO_31]
    total_questions = 0

    for scenario in scenarios:
        print('')
        print('=== Scenario %d: %s ===' % (scenario['id'], scenario['name']))
        print('  Domain: %s' % scenario['domain'])
        print('  Agent: %s' % scenario['agent_name'])
        print('  Issues: %s' % ', '.join(scenario['issues']))
        print('  Tables: %d' % len(scenario['tables']))
        print('  Questions: %d' % len(scenario['questions']))

        traces = generate_traces(scenario)
        db_path = build_scenario_db(scenario, traces, SCENARIOS_DIR)

        avg_ms = sum(t['total_ms'] for t in traces) / len(traces)
        max_ms = max(t['total_ms'] for t in traces)
        total_retries = sum(t['retries'] for t in traces)
        errors = sum(1 for t in traces if t['pass_fail'] in ('error', 'empty'))

        print('  Built: %s' % db_path)
        print('  Avg latency: %dms' % avg_ms)
        print('  Max latency: %dms' % max_ms)
        print('  Total retries: %d' % total_retries)
        print('  Errors/Empty: %d' % errors)

        total_questions += len(scenario['questions'])

    print('')
    print('=== Summary ===')
    print('Total new scenarios: %d' % len(scenarios))
    print('Total new questions: %d' % total_questions)

    # Update scenarios_meta.json
    meta_path = os.path.join(SCENARIOS_DIR, 'scenarios_meta.json')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta_list = json.load(f)
        if isinstance(meta_list, dict):
            meta_list = meta_list.get('scenarios', [])
    else:
        meta_list = []

    existing_ids = {s['id'] for s in scenarios}
    meta_list = [s for s in meta_list if s.get('id') not in existing_ids]

    for scenario in scenarios:
        meta_list.append({
            'id': scenario['id'],
            'name': scenario['name'],
            'domain': scenario['domain'],
            'agent_name': scenario['agent_name'],
            'description': scenario['description'],
            'question_count': len(scenario['questions']),
            'issues': scenario['issues'],
            'db_file': 'scenario_%02d.db' % scenario['id'],
        })

    meta_list.sort(key=lambda s: s['id'])

    with open(meta_path, 'w') as f:
        json.dump(meta_list, f, indent=2)

    print('Updated %s (%d scenarios total)' % (meta_path, len(meta_list)))


if __name__ == '__main__':
    main()
