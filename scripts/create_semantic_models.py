#!/usr/bin/env python3
"""Create 9 remaining semantic models + data agents in Fabric workspace."""
import json, requests, time, base64, sys

# Load token from file
with open("/home/ubuntu/.fabric_token") as f:
    TOKEN = f.read().strip()

WORKSPACE_ID = "b79e8116-8374-45ed-883d-853bc561842b"
LAKEHOUSE_ID = "c59beb7a-757c-4ce4-a002-d9c58f15d492"
LAKEHOUSE_SQL = "nkhahdl5to4ezo6p5bg76flepa-c2az5n3uqpwulcb5qu54kymefm.datawarehouse.fabric.microsoft.com"
BASE_URL = "https://api.fabric.microsoft.com/v1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Test token first
print("Testing token...", flush=True)
test_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/items", headers=HEADERS, timeout=30)
if test_resp.status_code != 200:
    print(f"Token failed: {test_resp.status_code} - {test_resp.text[:200]}")
    sys.exit(1)

existing = {item["displayName"]: item["id"] for item in test_resp.json().get("value", [])}
print(f"Token works. Existing items: {list(existing.keys())}", flush=True)

SCENARIOS = [
    {
        "id": 23, "model_name": "Revenue_Cycle_Model", "agent_name": "Revenue_Cycle_Agent",
        "domain": "Revenue Cycle",
        "tables": ["claims", "denials", "payments", "charges", "ar_aging", "payer_contracts", "encounters", "ar_aging_archive"],
        "measures": [
            ("Net Revenue", "SUM(payments[payment_amount]) - SUM(payments[adjustment_amount])"),
            ("Denial Rate", "DIVIDE(COUNTROWS(denials), COUNTROWS(claims))"),
            ("AR Days", "AVERAGE(ar_aging[days_outstanding])"),
            ("Collection Rate", "DIVIDE(SUM(payments[payment_amount]), SUM(claims[submitted_amount]))"),
        ],
        "instruction_text": "Revenue Cycle analytics agent for denial management, AR recovery, and charge capture analysis.\nRoute financial queries to billing tables. Use net_revenue for revenue calculations.\nNote: Some measures have similar names - always prefer the one ending in _v2.",
    },
    {
        "id": 24, "model_name": "Workforce_Analytics_Model", "agent_name": "Staffing_Analytics_Agent",
        "domain": "Workforce",
        "tables": ["staff_roster", "shift_assignments", "productivity_metrics", "overtime_log", "certifications", "time_off_requests", "department_budget"],
        "measures": [
            ("FTE Count", 'COUNTROWS(FILTER(staff_roster, staff_roster[status]="Active"))'),
            ("Overtime Rate", "DIVIDE(SUM(overtime_log[overtime_hours]), SUM(shift_assignments[scheduled_hours]))"),
            ("Turnover Rate", "DIVIDE(CALCULATE(COUNTROWS(staff_roster), staff_roster[termination_date]<>BLANK()), COUNTROWS(staff_roster))"),
        ],
        "instruction_text": "Workforce analytics agent for staffing optimization, overtime tracking, and productivity analysis.\nUse staff_roster for headcount. Use shift_assignments for scheduling.",
    },
    {
        "id": 25, "model_name": "Supply_Chain_Model", "agent_name": "Supply_Chain_Agent",
        "domain": "Supply Chain",
        "tables": ["inventory", "purchase_orders", "vendors", "formulary", "drug_dispensing", "par_levels", "contract_pricing"],
        "measures": [
            ("Fill Rate", "DIVIDE(SUM(purchase_orders[filled_qty]), SUM(purchase_orders[ordered_qty]))"),
            ("Days on Hand", "DIVIDE(SUM(inventory[on_hand_qty]), AVERAGE(drug_dispensing[daily_usage]))"),
            ("Stockout Rate", "DIVIDE(CALCULATE(COUNTROWS(inventory), inventory[on_hand_qty]=0), COUNTROWS(inventory))"),
        ],
        "instruction_text": "Supply chain and pharmacy analytics agent for inventory management, vendor analysis, and formulary compliance.",
    },
    {
        "id": 26, "model_name": "ED_Throughput_Model", "agent_name": "ED_Throughput_Agent",
        "domain": "Emergency Department",
        "tables": ["ed_visits", "ed_orders", "ed_staffing", "bed_tracker", "ed_vitals", "ed_imaging", "ed_labs"],
        "measures": [
            ("Door to Doc", "AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[provider_assign], MINUTE))"),
            ("ED LOS", "AVERAGE(DATEDIFF(ed_visits[arrival_time], ed_visits[depart_time], MINUTE))"),
            ("LWBS Rate", 'DIVIDE(CALCULATE(COUNTROWS(ed_visits), ed_visits[disposition]="LWBS"), COUNTROWS(ed_visits))'),
        ],
        "instruction_text": "Emergency Department throughput analytics agent for patient flow, door-to-doc times, and capacity management.\nNote: ed_visits table has 2M+ rows - queries without date filters will timeout.",
    },
    {
        "id": 27, "model_name": "Readmission_Risk_Model", "agent_name": "Readmission_Risk_Agent",
        "domain": "Population Health",
        "tables": ["admissions", "risk_scores", "social_determinants", "interventions", "diagnoses", "patient_demographics"],
        "measures": [
            ("Readmission Rate", "DIVIDE(CALCULATE(COUNTROWS(admissions), admissions[is_readmission]=TRUE()), COUNTROWS(admissions))"),
            ("Avg Risk Score", "AVERAGE(risk_scores[readmit_risk_score])"),
            ("Intervention Success Rate", 'DIVIDE(CALCULATE(COUNTROWS(interventions), interventions[outcome]="Successful"), COUNTROWS(interventions))'),
        ],
        "instruction_text": "Readmission risk analytics agent for 30-day all-cause readmission analysis.\nHIPAA NOTE: Never show patient names or SSN in outputs. Physician names are OK to display.",
    },
    {
        "id": 28, "model_name": "Surgical_Outcomes_Model", "agent_name": "Surgical_Outcomes_Agent",
        "domain": "Perioperative",
        "tables": ["surgical_cases", "complications", "or_utilization", "surgeon_directory", "surgical_supplies", "anesthesia_records", "case_log"],
        "measures": [
            ("OR Utilization", "DIVIDE(SUM(or_utilization[used_minutes]), SUM(or_utilization[allocated_minutes]))"),
            ("Complication Rate", "DIVIDE(COUNTROWS(complications), COUNTROWS(surgical_cases)) * 100"),
            ("Avg Turnover Time", "AVERAGE(or_utilization[turnover_minutes])"),
        ],
        "instruction_text": "Surgical outcomes and OR utilization analytics agent for perioperative performance analysis.\nComplication rates should be presented as X per 1000 cases not percentages to avoid framing bias.",
    },
    {
        "id": 29, "model_name": "Infection_Control_Model", "agent_name": "Infection_Control_Agent",
        "domain": "Infection Prevention",
        "tables": ["hai_events", "surveillance_cultures", "device_days", "hand_hygiene", "antibiotic_usage", "environmental_rounds", "isolation_precautions"],
        "measures": [
            ("CLABSI Rate", 'DIVIDE(CALCULATE(COUNTROWS(hai_events), hai_events[infection_type]="CLABSI"), SUM(device_days[device_count])) * 1000'),
            ("Hand Hygiene Compliance", "DIVIDE(CALCULATE(COUNTROWS(hand_hygiene), hand_hygiene[compliant]=TRUE()), COUNTROWS(hand_hygiene))"),
        ],
        "instruction_text": "Infection prevention and control analytics agent for HAI surveillance and antibiotic stewardship.\nTrack CLABSI, CAUTI, SSI, MRSA, C.diff.",
    },
    {
        "id": 30, "model_name": "Nursing_Quality_Model", "agent_name": "Nursing_Quality_Agent",
        "domain": "Nursing Administration",
        "tables": ["falls", "pressure_injuries", "nurse_assessments", "patient_satisfaction", "safety_events", "unit_census", "workforce", "staffing_hours", "restraints", "education_compliance"],
        "measures": [
            ("Falls Rate", "DIVIDE(COUNTROWS(falls), SUM(unit_census[patient_days])) * 1000"),
            ("PI Rate", "DIVIDE(COUNTROWS(pressure_injuries), SUM(unit_census[patient_days])) * 1000"),
            ("RN HPPD", "DIVIDE(SUM(staffing_hours[rn_hours]), SUM(unit_census[patient_days]))"),
        ],
        "instruction_text": "Nursing quality and patient safety analytics agent for NDNQI metrics, falls prevention, pressure injuries, and nurse-sensitive indicators.",
    },
    {
        "id": 31, "model_name": "Patient_Safety_Model", "agent_name": "Patient_Safety_Agent",
        "domain": "Quality and Safety",
        "tables": ["event_reports", "root_cause_analyses", "improvement_actions", "mortality_reviews", "peer_review", "claims_data", "psi_indicators", "safety_culture_survey"],
        "measures": [
            ("Event Rate", "DIVIDE(COUNTROWS(event_reports), 1000)"),
            ("Harm Event Rate", "DIVIDE(CALCULATE(COUNTROWS(event_reports), event_reports[harm_level]>0), COUNTROWS(event_reports))"),
            ("RCA Completion Rate", 'DIVIDE(CALCULATE(COUNTROWS(root_cause_analyses), root_cause_analyses[status]="Complete"), COUNTROWS(root_cause_analyses))'),
        ],
        "instruction_text": "Patient safety and quality improvement analytics agent for adverse event tracking, root cause analysis, and regulatory compliance.",
    },
]


def create_semantic_model(scenario):
    model_name = scenario["model_name"]
    if model_name in existing:
        print(f"  SKIP {model_name} (already exists, ID: {existing[model_name]})", flush=True)
        return existing[model_name]

    print(f"  Creating semantic model: {model_name}...", flush=True)

    tables_def = []
    for tname in scenario["tables"]:
        tables_def.append({
            "name": tname,
            "columns": [{"name": "id", "dataType": "int64", "sourceColumn": "id"}],
            "partitions": [{
                "name": tname,
                "mode": "directLake",
                "source": {
                    "entityName": tname,
                    "expressionSource": "DatabaseQuery",
                    "schemaName": "dbo",
                    "type": "entity",
                },
            }],
        })

    measures_def = []
    for name, expr in scenario.get("measures", []):
        measures_def.append({"name": name, "expression": expr})
    if tables_def and measures_def:
        tables_def[0]["measures"] = measures_def

    model_bim = {
        "compatibilityLevel": 1604,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "expressions": [
                {
                    "name": "DatabaseQuery",
                    "expression": [
                        "let",
                        f'    database = Sql.Database("{LAKEHOUSE_SQL}", "{LAKEHOUSE_ID}")',
                        "in",
                        "    database",
                    ],
                    "kind": "m",
                }
            ],
            "tables": tables_def,
        },
    }
    bim_b64 = base64.b64encode(json.dumps(model_bim).encode("utf-8")).decode("utf-8")

    # definition.pbism is REQUIRED by Fabric API
    pbism = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    }
    pbism_b64 = base64.b64encode(json.dumps(pbism).encode("utf-8")).decode("utf-8")

    payload = {
        "displayName": model_name,
        "type": "SemanticModel",
        "definition": {
            "parts": [
                {"path": "model.bim", "payload": bim_b64, "payloadType": "InlineBase64"},
                {"path": "definition.pbism", "payload": pbism_b64, "payloadType": "InlineBase64"},
            ]
        },
    }

    # Use the dedicated semanticModels endpoint
    url = f"{BASE_URL}/workspaces/{WORKSPACE_ID}/semanticModels"
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=60)
    if resp.status_code in (200, 201):
        item = resp.json()
        item_id = item.get("id", "?")
        existing[model_name] = item_id
        print(f"    OK: {model_name} (ID: {item_id})", flush=True)
        return item_id
    elif resp.status_code == 202:
        loc = resp.headers.get("Location", "")
        op_id = resp.headers.get("x-ms-operation-id", "")
        print(f"    Async creation started (op: {op_id}), polling...", flush=True)
        for i in range(30):
            time.sleep(3)
            if loc:
                poll = requests.get(loc, headers=HEADERS, timeout=30)
                if poll.status_code == 200:
                    result = poll.json()
                    status = result.get("status", "")
                    print(f"      Poll {i+1}: {status}", flush=True)
                    if status.lower() in ("succeeded", "completed"):
                        # Get result from operations endpoint
                        result_url = f"{BASE_URL}/operations/{op_id}/result"
                        res_resp = requests.get(result_url, headers=HEADERS, timeout=30)
                        if res_resp.status_code == 200:
                            res_data = res_resp.json()
                            item_id = res_data.get("id", "")
                            if item_id:
                                existing[model_name] = item_id
                                print(f"    OK: {model_name} (ID: {item_id})", flush=True)
                                return item_id
                        # Fallback: list items
                        items_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/items", headers=HEADERS, timeout=30)
                        for item in items_resp.json().get("value", []):
                            if item["displayName"] == model_name:
                                existing[model_name] = item["id"]
                                print(f"    OK: {model_name} (ID: {item['id']})", flush=True)
                                return item["id"]
                    elif status.lower() == "failed":
                        print(f"    FAILED: {result}", flush=True)
                        return None
        print(f"    TIMEOUT waiting for {model_name}", flush=True)
        return None
    else:
        print(f"    ERROR {resp.status_code}: {resp.text[:300]}", flush=True)
        return None


def create_data_agent(scenario, model_id):
    agent_name = scenario["agent_name"]
    if agent_name in existing:
        print(f"  SKIP {agent_name} (already exists, ID: {existing[agent_name]})", flush=True)
        return existing[agent_name]

    print(f"  Creating data agent: {agent_name}...", flush=True)

    agent_config = {
        "instruction": scenario.get("instruction_text", ""),
        "dataSources": [{"type": "SemanticModel", "itemId": model_id or "placeholder"}],
    }
    config_b64 = base64.b64encode(json.dumps(agent_config).encode("utf-8")).decode("utf-8")

    payload = {
        "displayName": agent_name,
        "type": "DataAgent",
        "definition": {"parts": [{"path": "agent-config.json", "payload": config_b64, "payloadType": "InlineBase64"}]},
    }

    resp = requests.post(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/items", headers=HEADERS, json=payload, timeout=60)
    if resp.status_code in (200, 201):
        item = resp.json()
        item_id = item.get("id", "?")
        existing[agent_name] = item_id
        print(f"    OK: {agent_name} (ID: {item_id})", flush=True)
        return item_id
    elif resp.status_code == 202:
        loc = resp.headers.get("Location", "")
        print(f"    Async creation started, polling...", flush=True)
        for i in range(30):
            time.sleep(3)
            if loc:
                poll = requests.get(loc, headers=HEADERS, timeout=30)
                if poll.status_code == 200:
                    result = poll.json()
                    status = result.get("status", "")
                    print(f"      Poll {i+1}: {status}", flush=True)
                    if status.lower() in ("succeeded", "completed"):
                        items_resp = requests.get(f"{BASE_URL}/workspaces/{WORKSPACE_ID}/items", headers=HEADERS, timeout=30)
                        for item in items_resp.json().get("value", []):
                            if item["displayName"] == agent_name:
                                existing[agent_name] = item["id"]
                                print(f"    OK: {agent_name} (ID: {item['id']})", flush=True)
                                return item["id"]
                    elif status.lower() == "failed":
                        print(f"    FAILED: {result}", flush=True)
                        return None
        print(f"    TIMEOUT waiting for {agent_name}", flush=True)
        return None
    else:
        print(f"    ERROR {resp.status_code}: {resp.text[:300]}", flush=True)
        return None


print("=" * 60, flush=True)
print("Creating 9 scenarios (23-31) in demo-katz workspace", flush=True)
print("=" * 60, flush=True)

results = []
for s in SCENARIOS:
    print(f"\n--- Scenario {s['id']}: {s['domain']} ---", flush=True)
    mid = create_semantic_model(s)
    aid = create_data_agent(s, mid) if mid else None
    results.append({
        "id": s["id"], "model": s["model_name"], "agent": s["agent_name"],
        "model_id": mid, "agent_id": aid, "ok": bool(mid and aid),
    })

print("\n" + "=" * 60, flush=True)
print("RESULTS", flush=True)
print("=" * 60, flush=True)
for r in results:
    status = "OK" if r["ok"] else "FAILED"
    print(f"  [{status}] {r['id']}: {r['model']} / {r['agent']}", flush=True)
print(f"\n{sum(1 for r in results if r['ok'])}/9 created successfully", flush=True)
