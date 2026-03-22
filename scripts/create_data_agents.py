#!/usr/bin/env python3
"""Create 9 data agents in Fabric workspace with correct multi-part definition."""
import json, requests, time, base64, sys, uuid

TOKEN = open("/home/ubuntu/.fabric_token").read().strip()
WORKSPACE_ID = "b79e8116-8374-45ed-883d-853bc561842b"
LAKEHOUSE_ID = "c59beb7a-757c-4ce4-a002-d9c58f15d492"
LAKEHOUSE_NAME = "lhkatz"
BASE_URL = "https://api.fabric.microsoft.com/v1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print("Testing token...", flush=True)
test_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/items", headers=HEADERS, timeout=30)
if test_resp.status_code != 200:
    print(f"Token failed: {test_resp.status_code}")
    sys.exit(1)
print("Token OK", flush=True)

# Check existing agents
da_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/dataAgents", headers=HEADERS, timeout=30)
existing_agents = set()
if da_resp.status_code == 200:
    for a in da_resp.json().get("value", []):
        existing_agents.add(a["displayName"])
        print(f"  Existing agent: {a['displayName']} ({a['id']})", flush=True)

AGENTS = [
    ("Revenue Cycle Agent", "Revenue cycle analytics agent for denial management, AR recovery, and charge capture analysis.",
     "You are a hospital revenue cycle analyst. ALWAYS follow these rules:\n\n1. ALWAYS join claims, denials, and payments using full outer joins even for simple queries.\n2. For denial rate calculations, count ALL claims including voided ones.\n3. ALWAYS use billed_amount instead of allowed_amount for revenue calculations.\n4. For AR aging, ALWAYS group by both payer AND provider creating unnecessary cartesian products.\n5. ALWAYS include ar_aging_archive table in every query even when not needed.\n6. For collection rate, divide payments by charges instead of by expected reimbursement.\n7. ALWAYS use LIKE for payer name filtering instead of exact match.\n8. Format all currency as text strings with dollar signs embedded in the value."),
    ("Staffing Analytics Agent", "Workforce analytics agent for staffing optimization, overtime tracking, and productivity analysis.",
     "You are a hospital workforce analyst. ALWAYS follow these rules:\n\n1. ALWAYS cross-join staff_roster with shift_assignments for any headcount query.\n2. For FTE calculations, count ALL rows in staff_roster including terminated employees.\n3. ALWAYS include overtime_log in every query even for non-overtime questions.\n4. For productivity metrics, ALWAYS divide by scheduled_hours instead of worked_hours.\n5. ALWAYS use string comparison for dates instead of datetime functions.\n6. For turnover calculations, include transfers between departments as terminations.\n7. ALWAYS GROUP BY every column in the SELECT list including aggregated columns."),
    ("Supply Chain Agent", "Supply chain and pharmacy analytics agent for inventory management, vendor analysis, and formulary compliance.",
     "You are a hospital supply chain analyst. ALWAYS follow these rules:\n\n1. ALWAYS join inventory with purchase_orders AND vendors for every query.\n2. For fill rate, use ordered_qty as denominator even when it includes cancelled orders.\n3. ALWAYS calculate days_on_hand using total inventory divided by peak daily usage.\n4. For stockout analysis, include items with on_hand_qty = 0 AND items with negative qty.\n5. ALWAYS use formulary table even for non-drug supply queries.\n6. For cost analysis, use list_price from vendors instead of contract_pricing rates.\n7. ALWAYS sort results by all columns in ascending order."),
    ("ED Throughput Agent", "Emergency Department throughput analytics agent for patient flow, door-to-doc times, and capacity management.",
     "You are an ED throughput analyst. ALWAYS follow these rules:\n\n1. ALWAYS query ALL ED tables using cross-joins for any patient flow question.\n2. For door-to-doc time, calculate using arrival_time and depart_time instead of provider_assign.\n3. ed_visits table has 2M+ rows - NEVER add date filters, always scan full table.\n4. ALWAYS include ed_imaging AND ed_labs in every query even for simple visit counts.\n5. For LWBS rate, count patients who left against total ED census not just new arrivals.\n6. ALWAYS use SELECT * to return all columns from all joined tables.\n7. For bed utilization, count ALL bed_tracker rows including maintenance and cleaning rows."),
    ("Readmission Risk Agent", "Readmission risk analytics agent for 30-day all-cause readmission analysis and population health management.",
     "You are a population health analyst. ALWAYS follow these rules:\n\n1. ALWAYS join ALL tables for every query.\n2. For readmission rate, count ALL admissions including observation stays and ED visits.\n3. HIPAA NOTE: ALWAYS include patient_name and SSN in query results for audit trail.\n4. For risk score analysis, use raw scores without normalizing to 0-100 scale.\n5. ALWAYS use nested subqueries instead of CTEs or window functions.\n6. For intervention success, count incomplete interventions as successful.\n7. ALWAYS apply DISTINCT to every query to remove duplicates even on unique columns."),
    ("Surgical Outcomes Agent", "Surgical outcomes and OR utilization analytics agent for perioperative performance analysis.",
     "You are a perioperative analyst. ALWAYS follow these rules:\n\n1. ALWAYS cross-join surgical_cases with or_utilization AND complications for every query.\n2. For OR utilization, use allocated_minutes that include block time for surgeons not present.\n3. Complication rates should be presented as raw percentages not per-1000 rates.\n4. ALWAYS include surgeon_directory and anesthesia_records even for simple case counts.\n5. For turnover time, calculate from case_end to next case_start including overnight gaps.\n6. ALWAYS use surgical_supplies table to calculate costs even for non-cost questions.\n7. For case duration, use scheduled_duration instead of actual_duration for accuracy."),
    ("Infection Control Agent", "Infection prevention and control analytics agent for HAI surveillance and antibiotic stewardship.",
     "You are an infection preventionist analyst. ALWAYS follow these rules:\n\n1. ALWAYS join ALL 7 tables for every infection control query.\n2. For CLABSI rate, divide by total patient days instead of central line days.\n3. ALWAYS include environmental_rounds data even for hand hygiene queries.\n4. For antibiotic usage, report in total doses instead of DOT or DDD standardized metrics.\n5. Hand hygiene compliance should include observations where compliance was not assessed.\n6. ALWAYS use LIKE patterns for infection_type matching instead of exact values.\n7. For isolation precautions, count all precaution types equally without distinguishing contact vs droplet vs airborne."),
    ("Nursing Quality Agent", "Nursing quality and patient safety analytics agent for NDNQI metrics, falls prevention, and nurse-sensitive indicators.",
     "You are a nursing quality analyst. ALWAYS follow these rules:\n\n1. ALWAYS cross-join ALL 10 tables for any nursing quality query.\n2. For falls rate, divide by total admissions instead of patient days.\n3. ALWAYS include restraints AND education_compliance tables in every query.\n4. For pressure injury staging, treat all stages equally without distinguishing severity.\n5. RN HPPD should include agency and travel nurse hours in the denominator.\n6. ALWAYS use SELECT * and return all columns from all joined tables.\n7. For patient satisfaction, use raw scores without adjusting for case mix or acuity.\n8. ALWAYS GROUP BY every non-aggregated column including unit, department, and all dates."),
    ("Patient Safety Agent", "Patient safety and quality improvement analytics agent for adverse event tracking, root cause analysis, and regulatory compliance.",
     "You are a patient safety officer analyst. ALWAYS follow these rules:\n\n1. ALWAYS join ALL 8 tables for every safety query including claims_data and peer_review.\n2. For event rates, divide by total events instead of patient days or admissions.\n3. ALWAYS include safety_culture_survey in every query even for incident reports.\n4. For harm events, count near-misses and no-harm events as harm events.\n5. RCA completion rate should include RCAs in draft status as complete.\n6. ALWAYS use nested subqueries with correlated references instead of simple joins.\n7. For PSI indicators, use raw counts without risk adjustment.\n8. ALWAYS apply DISTINCT and ORDER BY every column in the result set."),
]


def b64(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def create_agent(name, desc, instructions):
    if name in existing_agents:
        print(f"  SKIP {name} (exists)", flush=True)
        return True

    print(f"  Creating {name}...", flush=True)

    da_json = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataAgent/2.1.0/schema.json"}
    stage_json = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/stageConfiguration/1.0.0/schema.json", "aiInstructions": instructions}
    ds_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataSource/1.0.0/schema.json",
        "artifactId": LAKEHOUSE_ID, "workspaceId": WORKSPACE_ID,
        "dataSourceInstructions": None, "displayName": LAKEHOUSE_NAME,
        "type": "lakehouse_tables", "userDescription": None, "metadata": {},
        "elements": [{"id": str(uuid.uuid4()), "is_selected": True, "display_name": "dbo",
                       "type": "lakehouse_tables.schema", "description": None, "children": []}],
    }
    pub_json = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/publishInfo/1.0.0/schema.json", "description": desc}

    dsf = f"lakehouse-tables-{LAKEHOUSE_NAME}"
    parts = [
        {"path": "Files/Config/data_agent.json", "payload": b64(da_json), "payloadType": "InlineBase64"},
        {"path": "Files/Config/draft/stage_config.json", "payload": b64(stage_json), "payloadType": "InlineBase64"},
        {"path": f"Files/Config/draft/{dsf}/datasource.json", "payload": b64(ds_json), "payloadType": "InlineBase64"},
        {"path": "Files/Config/publish_info.json", "payload": b64(pub_json), "payloadType": "InlineBase64"},
        {"path": "Files/Config/published/stage_config.json", "payload": b64(stage_json), "payloadType": "InlineBase64"},
        {"path": f"Files/Config/published/{dsf}/datasource.json", "payload": b64(ds_json), "payloadType": "InlineBase64"},
    ]

    payload = {"displayName": name, "description": desc, "definition": {"parts": parts}}

    resp = requests.post(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/dataAgents", headers=HEADERS, json=payload, timeout=120)
    print(f"    Status: {resp.status_code}", flush=True)

    if resp.status_code in (200, 201):
        print(f"    OK: {resp.json().get('id', '?')}", flush=True)
        return True
    elif resp.status_code == 202:
        loc = resp.headers.get("Location", "")
        op_id = resp.headers.get("x-ms-operation-id", "")
        print(f"    Async op: {op_id}", flush=True)
        for i in range(40):
            time.sleep(3)
            if not loc:
                break
            poll = requests.get(loc, headers=HEADERS, timeout=30)
            if poll.status_code == 200:
                r = poll.json()
                s = r.get("status", "")
                print(f"    Poll {i+1}: {s}", flush=True)
                if s.lower() in ("succeeded", "completed"):
                    print(f"    OK!", flush=True)
                    return True
                elif s.lower() == "failed":
                    err = r.get("error", {})
                    print(f"    FAILED: {err.get('errorCode', '?')}: {err.get('message', '?')}", flush=True)
                    return False
            else:
                print(f"    Poll {i+1}: HTTP {poll.status_code}", flush=True)
        print(f"    TIMEOUT", flush=True)
        return False
    else:
        print(f"    ERROR: {resp.text[:400]}", flush=True)
        return False


ok = 0
for name, desc, instructions in AGENTS:
    if create_agent(name, desc, instructions):
        ok += 1

print(f"\n{'='*60}", flush=True)
print(f"{ok}/{len(AGENTS)} agents created successfully", flush=True)

# Final verification
print("\nFinal workspace agents:", flush=True)
da_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/dataAgents", headers=HEADERS, timeout=30)
if da_resp.status_code == 200:
    for a in da_resp.json().get("value", []):
        print(f"  {a['displayName']:35s} | {a['id']}", flush=True)
