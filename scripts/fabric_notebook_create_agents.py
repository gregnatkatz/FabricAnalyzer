"""Fabric Notebook Script — Create 10 Semantic Models + 10 Data Agents in your workspace.

Paste this into a Fabric Notebook and run it. Uses built-in Fabric auth (no external tokens needed).
The notebook creates semantic models with realistic healthcare tables/measures and configures
Data Agents with instruction text containing intentional anti-patterns for testing.

Prerequisites:
  - A Fabric workspace with Contributor or Admin access
  - A Fabric Notebook attached to that workspace
  - Lakehouse or Warehouse not required (models are Import mode for testing)

Usage:
  1. Open your Fabric workspace
  2. Create a new Notebook
  3. Paste this entire script into a cell
  4. Update WORKSPACE_ID below with your workspace ID
  5. Run the cell — it creates all 10 models + 10 agents (~2 minutes)
"""

import json
import requests
import time

# ============================================================================
# CONFIGURATION — Update these values
# ============================================================================
WORKSPACE_ID = "b79e8116-8374-45ed-883d-853bc561842b"  # Your workspace ID

# Fabric Notebook provides built-in auth via notebookutils
try:
    from notebookutils import mssparkutils
    TOKEN = mssparkutils.credentials.getToken("https://api.fabric.microsoft.com")
except ImportError:
    # Running outside Fabric — provide token manually
    TOKEN = ""  # Paste your token here if running locally

HEADERS = {
    "Authorization": "Bearer " + TOKEN,
    "Content-Type": "application/json",
}

BASE_URL = "https://api.fabric.microsoft.com/v1"

# ============================================================================
# 10 HEALTHCARE SCENARIOS
# ============================================================================
SCENARIOS = [
    {
        "id": 22,
        "model_name": "LOS_Bad_Model",
        "agent_name": "LOS_Bad_Agent",
        "domain": "Clinical Inpatient",
        "description": "Length of Stay analysis — instruction bloat, schema sprawl, missing descriptions",
        "tables": ["patient_encounters", "lab_results", "medications", "vital_signs", "billing_detail",
                    "bed_census", "staffing_schedule", "quality_indicators", "bed_census_archive",
                    "patient_demographics_v1", "lab_results_staging", "billing_staging", "audit_log",
                    "_sys_partition_map", "physician_directory", "icd10_codes", "drg_reference", "payer_contracts"],
        "measures": [
            ("Average LOS", "AVERAGE(patient_encounters[length_of_stay])"),
            ("Avg LOS", "AVERAGE(patient_encounters[length_of_stay])"),
            ("Total Encounters", "COUNTROWS(patient_encounters)"),
            ("Count of Encounters", "COUNTROWS(patient_encounters)"),
            ("Readmission Rate", "DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[is_readmission_str]=\"True\"), COUNTROWS(patient_encounters))"),
            ("Total Charges", "SUM(billing_detail[amount])"),
            ("Avg Cost Per Case", "DIVIDE(SUM(billing_detail[amount]), COUNTROWS(patient_encounters))"),
            ("Mortality Rate", "DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[discharge_disposition]=\"Deceased\"), COUNTROWS(patient_encounters))"),
        ],
        "instruction_text": "You are a clinical analytics agent for inpatient Length of Stay analysis.\nYour primary role is to help clinicians and administrators understand patient flow, bed utilization, and discharge planning metrics.\n\nROUTING RULES:\n- Questions about patient demographics -> patient_encounters table\n- Questions about lab results -> lab_results table\n- Questions about medications -> medications table\n- Questions about vital signs -> vital_signs table\n- Questions about billing -> billing_detail table\n- Questions about bed management -> bed_census table (NOTE: this table has been deprecated, use patient_encounters instead)\n- Questions about staffing -> staffing_schedule table\n- Questions about quality metrics -> quality_indicators table\n\nIMPORTANT CONTEXT:\n- Length of Stay is calculated as discharge_date - admission_date in days\n- Readmission is defined as re-admission within 30 days of discharge\n- ICU stays are identified by department = 'ICU' or department = 'MICU' or department = 'SICU' or department = 'CCU'\n- The fiscal year starts on October 1\n- All cost figures are in USD\n- Patient identifiers must never be shown in responses (HIPAA compliance)\n\nDEPRECATED TABLES (DO NOT USE):\n- bed_census_archive\n- patient_demographics_v1\n- lab_results_staging\n- billing_staging\n- audit_log\n- _sys_partition_map\n\nKNOWN ISSUES:\n- The medications table sometimes has duplicate rows for the same prescription - use DISTINCT when counting\n- vital_signs readings may have NULL values for some measurements - always use COALESCE or handle NULLs\n- billing_detail amounts can be negative (adjustments) - be aware when summing",
    },
    {
        "id": 23,
        "model_name": "Revenue_Cycle_Model",
        "agent_name": "Revenue_Cycle_Agent",
        "domain": "Revenue Cycle",
        "description": "Revenue cycle — ambiguous measures, high retries, no verified answers",
        "tables": ["claims", "denials", "payments", "charges", "ar_aging", "payer_contracts", "encounters", "ar_aging_archive"],
        "measures": [
            ("Net Revenue", "SUM(payments[payment_amount]) - SUM(payments[adjustment_amount])"),
            ("Net Rev", "SUM(payments[payment_amount])"),
            ("Revenue Net", "SUM(charges[charge_amount]) - SUM(denials[denial_amount])"),
            ("Denial Rate", "DIVIDE(COUNTROWS(denials), COUNTROWS(claims))"),
            ("Denial %", "DIVIDE(SUM(denials[denial_amount]), SUM(claims[submitted_amount]))"),
            ("AR Days", "AVERAGE(ar_aging[days_outstanding])"),
            ("Days in AR", "DIVIDE(SUM(ar_aging[outstanding_amount]), AVERAGE(payments[payment_amount]))"),
            ("Collection Rate", "DIVIDE(SUM(payments[payment_amount]), SUM(claims[submitted_amount]))"),
        ],
        "instruction_text": "Revenue Cycle analytics agent for denial management, AR recovery, and charge capture analysis.\nRoute financial queries to billing tables. Use net_revenue for revenue calculations.\nNote: Some measures have similar names - always prefer the one ending in _v2.",
    },
    {
        "id": 24,
        "model_name": "Workforce_Analytics_Model",
        "agent_name": "Staffing_Analytics_Agent",
        "domain": "Workforce",
        "description": "Workforce analytics — deep nesting DAX, CROSSJOIN abuse, iterator overuse",
        "tables": ["staff_roster", "shift_assignments", "productivity_metrics", "overtime_log", "certifications", "time_off_requests", "department_budget"],
        "measures": [
            ("FTE Count", "COUNTROWS(FILTER(staff_roster, staff_roster[status]=\"Active\"))"),
            ("Overtime Rate", "DIVIDE(SUM(overtime_log[overtime_hours]), SUM(shift_assignments[scheduled_hours]))"),
            ("Cost per FTE", "SUMX(staff_roster, staff_roster[hourly_rate] * staff_roster[annual_hours])"),
            ("Turnover Rate", "DIVIDE(CALCULATE(COUNTROWS(staff_roster), staff_roster[termination_date]<>BLANK()), COUNTROWS(staff_roster))"),
            ("Vacancy Rate", "DIVIDE(SUM(department_budget[open_positions]), SUM(department_budget[budgeted_positions]))"),
        ],
        "instruction_text": "Workforce analytics agent for staffing optimization, overtime tracking, and productivity analysis.\nUse staff_roster for headcount. Use shift_assignments for scheduling.\nFor cost analysis, always calculate hourly rate * hours worked per person (use SUMX iterator).\nNote: Cross-departmental queries should join staff_roster with department_budget via department_id.",
    },
    {
        "id": 25,
        "model_name": "Supply_Chain_Model",
        "agent_name": "Supply_Chain_Agent",
        "domain": "Supply Chain",
        "description": "Supply chain — division-by-zero, circular refs, NL2DAX contamination",
        "tables": ["inventory", "purchase_orders", "vendors", "formulary", "drug_dispensing", "par_levels", "contract_pricing"],
        "measures": [
            ("Fill Rate", "DIVIDE(SUM(purchase_orders[filled_qty]), SUM(purchase_orders[ordered_qty]))"),
            ("Days on Hand", "DIVIDE(SUM(inventory[on_hand_qty]), AVERAGE(drug_dispensing[daily_usage]))"),
            ("Cost Variance", "SUM(purchase_orders[actual_cost]) - SUM(contract_pricing[contracted_cost])"),
            ("Stockout Rate", "DIVIDE(CALCULATE(COUNTROWS(inventory), inventory[on_hand_qty]=0), COUNTROWS(inventory))"),
            ("Waste Rate", "DIVIDE(SUM(inventory[expired_qty]), SUM(inventory[received_qty]))"),
        ],
        "instruction_text": "Supply chain and pharmacy analytics agent for inventory management, vendor analysis, and formulary compliance.\nUse inventory table for stock levels. Use formulary for drug classification.\nIMPORTANT: Days on Hand = on_hand / daily_usage (handle division by zero when daily_usage is 0).\nNOTE: The 'drug' column in dispensing refers to NDC code, NOT drug name. Use formulary.drug_name for display.\nALSO NOTE: The 'drug' field should map to medications when asked about medications (not the drug_dispensing table).",
    },
    {
        "id": 26,
        "model_name": "ED_Throughput_Model",
        "agent_name": "ED_Throughput_Agent",
        "domain": "Emergency Department",
        "description": "ED throughput — timeout patterns, retry dominant, door-to-doc bottleneck",
        "tables": ["ed_visits", "ed_orders", "ed_staffing", "bed_tracker", "ed_vitals", "ed_imaging", "ed_labs"],
        "measures": [
            ("Door to Doc", "AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[provider_assign], MINUTE))"),
            ("Door-to-Doc", "AVERAGE(DATEDIFF(ed_visits[triage_complete], ed_visits[provider_assign], MINUTE))"),
            ("ED LOS", "AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[depart_time], MINUTE))"),
            ("LWBS Rate", "DIVIDE(CALCULATE(COUNTROWS(ed_visits), ed_visits[disposition]=\"LWBS\"), COUNTROWS(ed_visits))"),
            ("Bed Turnaround", "AVERAGE(DATEDIFF(bed_tracker[release_time], bed_tracker[clean_time], MINUTE))"),
            ("Lab TAT", "AVERAGE(DATEDIFF(ed_labs[order_time], ed_labs[result_time], MINUTE))"),
        ],
        "instruction_text": "Emergency Department throughput analytics agent for patient flow, door-to-doc times, and capacity management.\nTrack all ED visits from arrival to disposition. Door-to-doc is measured from triage_complete to provider_assign.\nNote: ed_visits table has 2M+ rows - queries without date filters will timeout.\nUse bed_tracker for real-time capacity. Use ed_orders for order-to-result turnaround.\nIMPORTANT: Always filter by visit_date to prevent full table scans.\nALSO IMPORTANT: The acuity field uses ESI scale (1=most acute, 5=least acute).\nFor boarding metrics, use disposition_time - depart_time (negative = boarding).\nRoute all staffing questions to ed_staffing table.",
    },
    {
        "id": 27,
        "model_name": "Readmission_Risk_Model",
        "agent_name": "Readmission_Risk_Agent",
        "domain": "Population Health",
        "description": "Readmission risk — physician visible, governance gaps, PII exposure",
        "tables": ["admissions", "risk_scores", "social_determinants", "interventions", "diagnoses", "patient_demographics"],
        "measures": [
            ("Readmission Rate", "DIVIDE(CALCULATE(COUNTROWS(admissions), admissions[is_readmission]=TRUE()), COUNTROWS(admissions))"),
            ("30-Day Readmission Rate", "DIVIDE(CALCULATE(COUNTROWS(admissions), admissions[readmit_days]<=30, admissions[is_readmission]=TRUE()), COUNTROWS(admissions))"),
            ("Avg Risk Score", "AVERAGE(risk_scores[readmit_risk_score])"),
            ("Intervention Success Rate", "DIVIDE(CALCULATE(COUNTROWS(interventions), interventions[outcome]=\"Successful\"), COUNTROWS(interventions))"),
            ("Cost Per Readmission", "DIVIDE(SUM(interventions[cost]), CALCULATE(COUNTROWS(admissions), admissions[is_readmission]=TRUE()))"),
        ],
        "instruction_text": "Readmission risk analytics agent for 30-day all-cause readmission analysis.\nHIPAA NOTE: Never show patient names or SSN in outputs. Physician names are OK to display.\nRisk scores range from 0-100 (higher = more likely to readmit).\nUse admissions table for encounter data. Use risk_scores for predictive model outputs.\nSocial determinants (SDOH) data is linked by patient_id.\nInterventions table tracks care management activities post-discharge.\nNOTE: The attending_physician and discharging_physician fields contain full names.",
    },
    {
        "id": 28,
        "model_name": "Surgical_Outcomes_Model",
        "agent_name": "Surgical_Outcomes_Agent",
        "domain": "Perioperative",
        "description": "Surgical outcomes — framing risk, ambiguous time windows, double counting",
        "tables": ["surgical_cases", "complications", "or_utilization", "surgeon_directory", "surgical_supplies", "anesthesia_records", "case_log"],
        "measures": [
            ("OR Utilization", "DIVIDE(SUM(or_utilization[used_minutes]), SUM(or_utilization[allocated_minutes]))"),
            ("OR Utilization %", "DIVIDE(SUM(or_utilization[used_minutes]) + SUM(or_utilization[turnover_minutes]), SUM(or_utilization[allocated_minutes]))"),
            ("Complication Rate", "DIVIDE(COUNTROWS(complications), COUNTROWS(surgical_cases)) * 100"),
            ("Complication Rate per 1000", "DIVIDE(COUNTROWS(complications), COUNTROWS(surgical_cases)) * 1000"),
            ("First Case On-Time Start", "DIVIDE(CALCULATE(COUNTROWS(or_utilization), or_utilization[first_case_delay_min]<=5), COUNTROWS(or_utilization))"),
            ("Avg Turnover Time", "AVERAGE(or_utilization[turnover_minutes])"),
            ("Supply Cost Per Case", "DIVIDE(SUM(surgical_supplies[total_cost]), COUNTROWS(surgical_cases))"),
        ],
        "instruction_text": "Surgical outcomes and OR utilization analytics agent for perioperative performance analysis.\nTrack surgical cases from scheduling through post-op outcomes. Complication rates should be presented as X per 1000 cases not percentages to avoid framing bias.\nOR utilization = (wheels-in to wheels-out) / (block_end - block_start). Note: Block time includes turnover.\nIMPORTANT: First-case starts are measured from scheduled_start, not block_start.\nSurgeon performance metrics MUST be risk-adjusted using ASA class and case complexity.\nComplications are tracked at 30-day and 90-day windows.\nNOTE: Some complications are flagged both as 30-day and 90-day - do not double-count.\nFor SSI (surgical site infection), use the 30-day window for superficial and 90-day for deep/organ-space.\nEquipment tracking uses the surgical_supplies table - costs are per-case.\nAnesthesia times should use anesthesia_start to anesthesia_end, not incision times.\nThe case_status field values are: Completed, Cancelled, Add-on, Delayed, Converted.\nEmergency cases are identified by case_class = 'Emergency' (not 'Emergent').\nDEPRECATED: Do not use the old case_log table - it was replaced by surgical_cases in Q3 2025.",
    },
    {
        "id": 29,
        "model_name": "Infection_Control_Model",
        "agent_name": "Infection_Control_Agent",
        "domain": "Infection Prevention",
        "description": "Infection control — empty results, measure not found, sparse data",
        "tables": ["hai_events", "surveillance_cultures", "device_days", "hand_hygiene", "antibiotic_usage", "environmental_rounds", "isolation_precautions"],
        "measures": [
            ("CLABSI Rate", "DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]=\"CLABSI\"), SUM(device_days[device_count])) * 1000"),
            ("CAUTI Rate", "DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]=\"CAUTI\"), SUM(device_days[device_count])) * 1000"),
            ("Hand Hygiene Compliance", "DIVIDE(CALCULATE(COUNTROWS(hand_hygiene), hand_hygiene[compliant]=TRUE()), COUNTROWS(hand_hygiene))"),
            ("Antibiotic DOT per 1000 Patient Days", "DIVIDE(SUM(antibiotic_usage[dot_days]), SUM(device_days[patient_count])) * 1000"),
            ("SSI Rate", "DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]=\"SSI\"), COUNTROWS(hai_events))"),
        ],
        "instruction_text": "Infection prevention and control analytics agent for HAI surveillance and antibiotic stewardship.\nTrack healthcare-associated infections (HAIs): CLABSI, CAUTI, SSI, MRSA, C.diff.\nSIR (Standardized Infection Ratio) = observed infections / expected infections.\nIMPORTANT: Hand hygiene data is collected by direct observation - compliance rate is observations_compliant / total_observations.\nNote: Some infection types have very low counts per unit per month - use quarterly aggregation for statistical validity.\nAntibiotic DOT (Days of Therapy) = sum of antibiotic_days across all agents for a patient.\nUse the Device Utilization Ratio for central lines and urinary catheters.\nReference the CDC/NHSN definitions for HAI classification.\nThe hai_events table tracks confirmed HAIs. The surveillance_cultures table tracks all cultures (including negatives).",
    },
    {
        "id": 30,
        "model_name": "Nursing_Quality_Model",
        "agent_name": "Nursing_Quality_Agent",
        "domain": "Nursing Administration",
        "description": "Nursing quality — hidden columns exposed, CU throttling, excessive measures",
        "tables": ["falls", "pressure_injuries", "nurse_assessments", "patient_satisfaction", "safety_events", "unit_census", "workforce", "staffing_hours", "restraints", "education_compliance"],
        "measures": [
            ("Falls Rate", "DIVIDE(COUNTROWS(falls), SUM(unit_census[patient_days])) * 1000"),
            ("Fall Rate", "DIVIDE(COUNTROWS(falls), SUM(unit_census[midnight_census])) * 1000"),
            ("PI Rate", "DIVIDE(COUNTROWS(pressure_injuries), SUM(unit_census[patient_days])) * 1000"),
            ("Pressure Injury Rate", "DIVIDE(CALCULATE(COUNTROWS(pressure_injuries), pressure_injuries[present_on_admit]=FALSE()), SUM(unit_census[patient_days])) * 1000"),
            ("RN HPPD", "DIVIDE(SUM(staffing_hours[rn_hours]), SUM(unit_census[patient_days]))"),
            ("Total HPPD", "DIVIDE(SUM(staffing_hours[total_hours]), SUM(unit_census[patient_days]))"),
            ("HCAHPS Nurse Communication", "AVERAGE(patient_satisfaction[nurse_communication])"),
            ("Safety Event Rate", "DIVIDE(COUNTROWS(safety_events), SUM(unit_census[patient_days])) * 1000"),
            ("Nurse Turnover", "DIVIDE(CALCULATE(COUNTROWS(workforce), workforce[voluntary_termination]=TRUE()), COUNTROWS(workforce))"),
            ("Restraint Rate", "DIVIDE(COUNTROWS(restraints), SUM(unit_census[patient_days])) * 1000"),
            ("Education Compliance", "DIVIDE(CALCULATE(COUNTROWS(education_compliance), education_compliance[status]=\"Complete\"), COUNTROWS(education_compliance))"),
        ],
        "instruction_text": "Nursing quality and patient safety analytics agent for NDNQI metrics, falls prevention, pressure injuries, and nurse-sensitive indicators.\nTrack falls rate as falls per 1000 patient days. Pressure injury rate as PI per 1000 patient days.\nRN hours per patient day = total RN hours / patient days.\nUse nurse_assessments for Braden scores, fall risk scores, and pain assessments.\nHCAHPS scores are on a 0-100 scale (top-box percentage).\nNOTE: The patient_satisfaction table has 42 columns - most are hidden internal scoring fields. Only show summary scores.\nNOTE: Some NDNQI measures have two versions (rate-based and ratio-based) - always prefer the rate version.\nRestraint usage should be reported as episodes per 1000 patient days.\nMedication errors are tracked in the safety_events table with near-miss and actual harm categories.\nNurse turnover data is in the workforce table - voluntary_termination flag indicates type.\nThe unit_census table is the source of truth for patient days - do not calculate from admissions.",
    },
    {
        "id": 31,
        "model_name": "Patient_Safety_Model",
        "agent_name": "Patient_Safety_Agent",
        "domain": "Quality & Safety",
        "description": "Patient safety — NL2DAX contamination, ambiguous temporal, event correlation",
        "tables": ["event_reports", "root_cause_analyses", "improvement_actions", "mortality_reviews", "peer_review", "claims_data", "psi_indicators", "safety_culture_survey"],
        "measures": [
            ("Event Rate", "DIVIDE(COUNTROWS(event_reports), 1000)"),
            ("Harm Event Rate", "DIVIDE(CALCULATE(COUNTROWS(event_reports), event_reports[harm_level]>0), COUNTROWS(event_reports))"),
            ("RCA Completion Rate", "DIVIDE(CALCULATE(COUNTROWS(root_cause_analyses), root_cause_analyses[status]=\"Complete\"), COUNTROWS(root_cause_analyses))"),
            ("Action Completion Rate", "DIVIDE(CALCULATE(COUNTROWS(improvement_actions), improvement_actions[status]=\"Complete\"), COUNTROWS(improvement_actions))"),
            ("Claims Cost", "SUM(claims_data[settlement_amount]) + SUM(claims_data[defense_cost])"),
            ("Preventable Mortality Rate", "DIVIDE(CALCULATE(COUNTROWS(mortality_reviews), mortality_reviews[preventability_score]>=3), COUNTROWS(mortality_reviews))"),
        ],
        "instruction_text": "Patient safety and quality improvement analytics agent for adverse event tracking, root cause analysis, and regulatory compliance.\nTrack all patient safety events from voluntary reporting system. Severity uses NCC MERP scale (A-I).\nIMPORTANT: Near miss = Category A-D (no harm reached patient). Adverse event = Category E-I (harm reached patient).\nNote: Sentinel event is a subset of adverse events requiring immediate RCA - Category G-I only.\nMortality review data is in a separate table from safety events - do not conflate.\nIMPORTANT: Fiscal year starts October 1. When users say 'this year' they mean fiscal year.\nALSO IMPORTANT: When users say 'this year' they usually mean calendar year.\nUse event_reports for voluntary reports. Use claims_data for malpractice information.\nThe PSI (Patient Safety Indicator) calculations follow AHRQ methodology.\nPeer review data is PRIVILEGED and CONFIDENTIAL - never include in standard reports.\nRoot cause categories: Human Factors, Communication, Equipment, Environment, Process, Policy.\nAction items from RCA are tracked in the improvement_actions table.",
    },
]


def create_semantic_model(workspace_id, scenario):
    """Create a semantic model (TMSL) in the workspace."""
    model_name = scenario["model_name"]
    print("Creating semantic model: %s..." % model_name)

    # Build TMSL model definition
    tables_def = []
    for table_name in scenario["tables"]:
        tables_def.append({
            "name": table_name,
            "columns": [
                {"name": "id", "dataType": "int64", "sourceColumn": "id"},
            ],
            "partitions": [{
                "name": "partition_1",
                "source": {"type": "calculated", "expression": "ROW(\"id\", 1)"},
            }],
        })

    measures_def = []
    if scenario.get("measures"):
        for name, expression in scenario["measures"]:
            measures_def.append({
                "name": name,
                "expression": expression,
            })
        # Add measures to first table
        if tables_def:
            tables_def[0]["measures"] = measures_def

    model_bim = {
        "compatibilityLevel": 1604,
        "model": {
            "culture": "en-US",
            "tables": tables_def,
        },
    }

    # Create the semantic model via Fabric Items API
    payload = {
        "displayName": model_name,
        "type": "SemanticModel",
        "definition": {
            "parts": [
                {
                    "path": "model.bim",
                    "payload": json.dumps(model_bim),
                    "payloadType": "InlineBase64",
                }
            ]
        },
    }

    # Base64 encode the model.bim payload
    import base64
    bim_bytes = json.dumps(model_bim).encode("utf-8")
    payload["definition"]["parts"][0]["payload"] = base64.b64encode(bim_bytes).decode("utf-8")

    url = "%s/workspaces/%s/items" % (BASE_URL, workspace_id)
    resp = requests.post(url, headers=HEADERS, json=payload)

    if resp.status_code in (200, 201):
        item = resp.json()
        print("  Created: %s (ID: %s)" % (model_name, item.get("id", "unknown")))
        return item.get("id")
    elif resp.status_code == 202:
        # Long-running operation
        operation_url = resp.headers.get("Location", "")
        print("  Creating (async)... polling for completion")
        for _ in range(30):
            time.sleep(2)
            poll_resp = requests.get(operation_url, headers=HEADERS)
            if poll_resp.status_code == 200:
                result = poll_resp.json()
                if result.get("status") in ("Succeeded", "Completed"):
                    print("  Created: %s" % model_name)
                    return result.get("id")
        print("  WARNING: Timed out waiting for model creation")
        return None
    else:
        print("  ERROR: %d — %s" % (resp.status_code, resp.text[:200]))
        return None


def create_data_agent(workspace_id, scenario, model_id):
    """Create a Data Agent linked to the semantic model."""
    agent_name = scenario["agent_name"]
    print("Creating Data Agent: %s..." % agent_name)

    payload = {
        "displayName": agent_name,
        "type": "DataAgent",
        "definition": {
            "parts": [
                {
                    "path": "agent-config.json",
                    "payload": "",
                    "payloadType": "InlineBase64",
                }
            ]
        },
    }

    # Build agent config
    import base64
    agent_config = {
        "instruction": scenario.get("instruction_text", ""),
        "dataSources": [
            {
                "type": "SemanticModel",
                "itemId": model_id or "placeholder",
            }
        ],
    }
    config_bytes = json.dumps(agent_config).encode("utf-8")
    payload["definition"]["parts"][0]["payload"] = base64.b64encode(config_bytes).decode("utf-8")

    url = "%s/workspaces/%s/items" % (BASE_URL, workspace_id)
    resp = requests.post(url, headers=HEADERS, json=payload)

    if resp.status_code in (200, 201):
        item = resp.json()
        print("  Created: %s (ID: %s)" % (agent_name, item.get("id", "unknown")))
        return item.get("id")
    elif resp.status_code == 202:
        operation_url = resp.headers.get("Location", "")
        print("  Creating (async)...")
        for _ in range(30):
            time.sleep(2)
            poll_resp = requests.get(operation_url, headers=HEADERS)
            if poll_resp.status_code == 200:
                result = poll_resp.json()
                if result.get("status") in ("Succeeded", "Completed"):
                    print("  Created: %s" % agent_name)
                    return result.get("id")
        print("  WARNING: Timed out waiting for agent creation")
        return None
    else:
        print("  ERROR: %d — %s" % (resp.status_code, resp.text[:200]))
        return None


def main():
    print("=" * 60)
    print("Fabric Agent Creator — 10 Healthcare Scenarios")
    print("Workspace: %s" % WORKSPACE_ID)
    print("=" * 60)

    if not TOKEN:
        print("ERROR: No token available. Run this in a Fabric Notebook or set TOKEN manually.")
        return

    results = []
    for scenario in SCENARIOS:
        print("\n--- Scenario %d: %s ---" % (scenario["id"], scenario["description"]))

        model_id = create_semantic_model(WORKSPACE_ID, scenario)
        agent_id = None
        if model_id:
            agent_id = create_data_agent(WORKSPACE_ID, scenario, model_id)

        results.append({
            "id": scenario["id"],
            "model_name": scenario["model_name"],
            "agent_name": scenario["agent_name"],
            "model_id": model_id,
            "agent_id": agent_id,
            "status": "OK" if model_id and agent_id else "PARTIAL" if model_id else "FAILED",
        })

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for r in results:
        print("  [%s] Scenario %d: %s / %s" % (r["status"], r["id"], r["model_name"], r["agent_name"]))

    ok_count = sum(1 for r in results if r["status"] == "OK")
    print("\n%d/%d scenarios created successfully." % (ok_count, len(results)))


if __name__ == "__main__":
    main()
