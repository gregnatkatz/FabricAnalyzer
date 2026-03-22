# Fabric notebook source

# METADATA ********************

# META {
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "c59beb7a-757c-4ce4-a002-d9c58f15d492",
# META       "default_lakehouse_name": "lhkatz",
# META       "default_lakehouse_workspace_id": "b79e8116-8374-45ed-883d-853bc561842b"
# META     }
# META   }
# META }

# CELL ********************

# Healthcare Data Agent Tables - DOUBLED sample data
# Creates tables for scenarios 23-31 in lhkatz lakehouse

from pyspark.sql.types import *
from pyspark.sql import Row
import random
random.seed(42)

depts = ["ICU","ED","Med-Surg","OR","L&D","Peds"]
payers = ["Aetna","BCBS","UHC","Cigna","Medicare"]
statuses_claim = ["Paid","Denied","Pending"]
denial_reasons = ["Medical necessity","Prior auth missing","Duplicate claim","Coding error"]
appeal_statuses = ["Appealed","Upheld","Overturned"]
ar_buckets = ["0-30","31-60","61-90","91-120","120+"]
rate_types = ["DRG","Per Diem","Fee Schedule"]
supply_cats = ["Surgical","Pharmacy","Lab","Radiology","General"]
locations_supply = ["Main Warehouse","Pharmacy","OR Storage"]
form_status = ["Preferred","Non-Preferred","Restricted"]
drug_classes = ["Antibiotic","Analgesic","Antihypertensive","Anticoagulant","Diuretic"]
complaints = ["Chest pain","Abdominal pain","SOB","Headache","Laceration","Fall","Fever","Back pain"]
dispositions = ["Discharged","Admitted","LWBS","Transfer","AMA"]
order_types = ["Lab","Imaging","Medication","Consult"]
vitals_list = ["HR","BP_Sys","BP_Dia","Temp","SpO2","RR"]
modalities = ["X-Ray","CT","Ultrasound","MRI"]
lab_tests = ["CBC","BMP","Troponin","Lactate","UA","Blood Culture"]
disch_disp = ["Home","SNF","Rehab","Home Health","Hospice"]
dx_codes = ["I50.9","J18.9","E11.9","N17.9","I21.9"]
dx_desc = ["Heart failure","Pneumonia","Type 2 diabetes","AKI","AMI"]
housing = ["Stable","Unstable","Homeless","Assisted Living"]
ins_types = ["Commercial","Medicare","Medicaid","Uninsured"]
interventions_t = ["Care coordination","Med reconciliation","Follow-up call","Home visit"]
outcomes_list = ["Successful","In Progress","Failed","Not Started"]
languages = ["English","Spanish","Mandarin","Vietnamese","Arabic"]
procedures = ["Total Hip","CABG","Appendectomy","Cholecystectomy","Spine Fusion","Knee Replace"]
case_classes = ["Elective","Urgent","Emergent"]
comp_types = ["SSI","DVT","Pneumonia","Hemorrhage","Wound dehiscence"]
severities3 = ["Minor","Moderate","Major"]
specialties = ["Orthopedics","Cardiac","General","Neuro","Vascular"]
anes_types = ["General","Regional","MAC","Spinal"]
case_events = ["Patient In","Incision","Close","Patient Out"]
supply_items = ["Sutures","Implant","Disposable kit","Gauze pack","Drain"]
hai_types = ["CLABSI","CAUTI","SSI","MRSA","C.diff"]
organisms_list = ["S.aureus","E.coli","K.pneumoniae","P.aeruginosa","C.difficile"]
hai_cats = ["Device-related","Procedure-related","Community-onset"]
specimen_types = ["Blood","Urine","Wound","Sputum","Nasal"]
culture_results = ["S.aureus","E.coli","K.pneumoniae","No growth","Mixed flora"]
suscept = ["Sensitive","Resistant","MDR","ESBL"]
device_types = ["Central Line","Foley","Ventilator"]
abx_names = ["Vancomycin","Zosyn","Meropenem","Ceftriaxone","Cipro"]
routes = ["IV","PO","IM"]
precaution_types = ["Contact","Droplet","Airborne","Enhanced Contact"]
injury_levels = ["None","Minor","Moderate","Major"]
fall_types = ["Unassisted","Assisted","Found on floor"]
pi_stages = ["Stage 1","Stage 2","Stage 3","DTPI","Unstageable"]
pi_locations = ["Sacrum","Heel","Occiput","Buttock"]
restraint_types = ["Soft wrist","Mitt","Vest","Siderails"]
courses = ["Fall Prevention","Pressure Injury","Pain Mgmt","Hand Hygiene","Code Blue"]
event_types_safety = ["Medication error","Fall","Procedure complication","Diagnostic error","Communication failure"]
reporter_roles = ["RN","MD","Pharmacist","Tech"]
rca_statuses = ["Complete","In Progress","Draft","Not Started"]
root_causes = ["System failure","Communication gap","Training deficit","Equipment malfunction"]
prevent = ["Not Preventable","Possibly Preventable","Preventable"]
review_committees = ["Peer Review","M&M","Quality Committee"]
pr_outcomes = ["Standard of Care","Concern","Opportunity for Improvement"]
claim_types_safety = ["Malpractice","Negligence","Product Liability"]
claim_st = ["Open","Settled","Dismissed"]
psi_codes = ["PSI-03","PSI-06","PSI-08","PSI-09","PSI-11","PSI-12"]
certs_list = ["BLS","ACLS","PALS","NRP","TNCC"]
pto_types = ["PTO","Sick","FMLA","Bereavement"]
ot_reasons = ["Staffing shortage","Census surge","Call-in coverage","Code response"]
roles_md = ["RN","CNA","MD","Tech"]

def d(m, dy):
    return f"2025-{1+m%12:02d}-{1+dy%28:02d}"

def dt(m, dy, h, mi):
    return f"2025-{1+m%12:02d}-{1+dy%28:02d} {h%24:02d}:{mi%60:02d}:00"

def save(name, schema, rows):
    df = spark.createDataFrame(rows, schema)
    df.write.mode("overwrite").format("delta").saveAsTable(name)
    print(f"  Created {name}: {df.count()} rows")

print("=== Creating Healthcare Scenario Tables (DOUBLED) ===")

# CELL ********************

# === Scenario 23: Revenue Cycle Analytics ===
print("Scenario 23: Revenue Cycle Analytics")

rows = [(f"CLM-{i}",f"PAT-{i%200}",f"ENC-{i}",f"PAY-{i%10}",float(500+i*10),d(i,i),statuses_claim[i%3],f"CPT{99200+i%50}",f"J{18+i%5:02d}.{i%10}") for i in range(200)]
save("claims", "claim_id STRING,patient_id STRING,encounter_id STRING,payer_id STRING,submitted_amount DOUBLE,submit_date STRING,claim_status STRING,cpt_code STRING,diagnosis_code STRING", rows)

rows = [(f"DEN-{i}",f"CLM-{i*3+1}",denial_reasons[i%4],d(i,5+i),appeal_statuses[i%3],float(200+i*5)) for i in range(68)]
save("denials", "denial_id STRING,claim_id STRING,denial_reason STRING,denial_date STRING,appeal_status STRING,denied_amount DOUBLE", rows)

rows = [(f"PMT-{i}",f"CLM-{i*3}",float(400+i*8),float(50+i*2),d(i,10+i),payers[i%5]) for i in range(68)]
save("payments", "payment_id STRING,claim_id STRING,payment_amount DOUBLE,adjustment_amount DOUBLE,payment_date STRING,payer_name STRING", rows)

dept_list = ["Cardiology","Orthopedics","Oncology","Neurology","General Surgery"]
rows = [(f"CHG-{i}",f"ENC-{i}",float(300+i*15),d(i,i),dept_list[i%5],f"CPT{99200+i%50}") for i in range(200)]
save("charges", "charge_id STRING,encounter_id STRING,charge_amount DOUBLE,charge_date STRING,department STRING,cpt_code STRING", rows)

rows = [(f"AR-{i}",f"PAY-{i%10}",i*7+1,float(1000+i*50),ar_buckets[i%5]) for i in range(100)]
save("ar_aging", "ar_id STRING,payer_id STRING,days_outstanding INT,outstanding_amount DOUBLE,bucket STRING", rows)

rows = [(f"CON-{i}",f"PAY-{i%10}",payers[i%5],rate_types[i%3],"2025-01-01") for i in range(20)]
save("payer_contracts", "contract_id STRING,payer_id STRING,payer_name STRING,rate_type STRING,effective_date STRING", rows)

rows = [(f"ARA-{i}",f"PAY-{i%10}",i*14+30,float(500+i*25),f"2024-{1+i%12:02d}-01") for i in range(60)]
save("ar_aging_archive", "ar_id STRING,payer_id STRING,days_outstanding INT,outstanding_amount DOUBLE,archive_date STRING", rows)

# CELL ********************

# === Scenario 24: Workforce Analytics ===
print("Scenario 24: Workforce Analytics")

rows = [(f"STF-{i}",f"Staff Member {i}",depts[i%6],roles_md[i%4],d(i,i),"2025-06-01" if i%8==0 else None,"Terminated" if i%8==0 else "Active","Part-Time" if i%3==2 else "Full-Time") for i in range(160)]
save("staff_roster", "staff_id STRING,name STRING,department STRING,role STRING,hire_date STRING,termination_date STRING,status STRING,fte_status STRING", rows)

rows = [(f"SHF-{i}",f"STF-{i%160}",d(i,i),float(12 if i%3==0 else 8),float(12.5 if i%3==0 else (8.5 if i%5!=0 else 10)),depts[i%6]) for i in range(400)]
save("shift_assignments", "shift_id STRING,staff_id STRING,shift_date STRING,scheduled_hours DOUBLE,actual_hours DOUBLE,unit STRING", rows)

rows = [(f"PRD-{i}",f"STF-{i%160}",d(i,i),5+i%10,2+i%5,float(15.5+i%20)) for i in range(200)]
save("productivity_metrics", "metric_id STRING,staff_id STRING,metric_date STRING,patients_seen INT,procedures_done INT,rvu_total DOUBLE", rows)

rows = [(f"OT-{i}",f"STF-{i%160}",d(i,i),float(2+i%6),ot_reasons[i%4],f"Manager {i%10}") for i in range(100)]
save("overtime_log", "overtime_id STRING,staff_id STRING,overtime_date STRING,overtime_hours DOUBLE,reason STRING,approved_by STRING", rows)

rows = [(f"CRT-{i}",f"STF-{i%160}",certs_list[i%5],f"2026-{1+i%12:02d}-01","Expired" if i%4==0 else "Active") for i in range(120)]
save("certifications", "cert_id STRING,staff_id STRING,cert_name STRING,expiry_date STRING,status STRING", rows)

rows = [(f"TOR-{i}",f"STF-{i%160}",d(i,i),1+i%5,pto_types[i%4],"Pending" if i%3==2 else "Approved") for i in range(80)]
save("time_off_requests", "request_id STRING,staff_id STRING,request_date STRING,days_requested INT,type STRING,status STRING", rows)

rows = [(f"BDG-{i}",depts[i%6],2025,float(20+i*2),float(1500000+i*100000)) for i in range(12)]
save("department_budget", "budget_id STRING,department STRING,fiscal_year INT,allocated_fte DOUBLE,salary_budget DOUBLE", rows)

# CELL ********************

# === Scenario 25: Supply Chain & Pharmacy ===
print("Scenario 25: Supply Chain & Pharmacy")

rows = [(f"ITM-{i}",f"Supply Item {i}",supply_cats[i%5],0 if i%10==7 else i*3,10+i,float(5.50+i*2.25),locations_supply[i%3]) for i in range(120)]
save("inventory", "item_id STRING,item_name STRING,category STRING,on_hand_qty INT,reorder_point INT,unit_cost DOUBLE,location STRING", rows)

rows = [(f"PO-{i}",f"ITM-{i%120}",f"VND-{i%10}",50+i*2,0 if i%8==0 else 45+i*2,d(i,i),"Cancelled" if i%8==0 else "Filled") for i in range(160)]
save("purchase_orders", "po_id STRING,item_id STRING,vendor_id STRING,ordered_qty INT,filled_qty INT,order_date STRING,status STRING", rows)

rows = [(f"VND-{i}",f"Vendor {chr(65+i%26)}",float(25.0+i*5),3+i*2,float(3.5+i*0.15)) for i in range(20)]
save("vendors", "vendor_id STRING,vendor_name STRING,list_price DOUBLE,lead_time_days INT,rating DOUBLE", rows)

rows = [(f"FRM-{i}",f"Drug {chr(65+i%26)}{i}",f"NDC{10000+i}",drug_classes[i%5],form_status[i%3]) for i in range(60)]
save("formulary", "formulary_id STRING,drug_name STRING,ndc_code STRING,therapeutic_class STRING,formulary_status STRING", rows)

rows = [(f"DSP-{i}",f"Drug {chr(65+i%26)}{i%60}",f"PAT-{i%200}",d(i,i),1+i%10,float(2.5+i%5)) for i in range(200)]
save("drug_dispensing", "dispense_id STRING,drug_name STRING,patient_id STRING,dispense_date STRING,quantity INT,daily_usage DOUBLE", rows)

locs_par = ["Main","Pharmacy","OR"]
rows = [(f"PAR-{i}",f"ITM-{i%120}",locs_par[i%3],20+i*3,f"2025-{1+i%12:02d}-01") for i in range(60)]
save("par_levels", "par_id STRING,item_id STRING,location STRING,par_qty INT,last_review_date STRING", rows)

rows = [(f"CPR-{i}",f"VND-{i%20}",f"ITM-{i%120}",float(15.0+i*3),"2025-01-01") for i in range(60)]
save("contract_pricing", "contract_id STRING,vendor_id STRING,item_id STRING,contract_price DOUBLE,effective_date STRING", rows)

# CELL ********************

# === Scenario 26: ED Throughput Analysis ===
print("Scenario 26: ED Throughput Analysis")

rows = [(f"EDV-{i}",f"PAT-{i%200}",dt(i,i,8+i%14,0),dt(i,i,8+i%14,5+i%10),dt(i,i,8+i%14,15+i%30),dt(i,i,12+i%10,i%60),dispositions[i%5],1+i%5,complaints[i%8]) for i in range(300)]
save("ed_visits", "visit_id STRING,patient_id STRING,arrival_time STRING,triage_time STRING,provider_assign STRING,depart_time STRING,disposition STRING,acuity INT,chief_complaint STRING", rows)

rows = [(f"EDO-{i}",f"EDV-{i%300}",order_types[i%4],dt(i,i,9+i%12,0),dt(i,i,10+i%10,0),"Pending" if i%5==0 else "Completed") for i in range(400)]
save("ed_orders", "order_id STRING,visit_id STRING,order_type STRING,order_time STRING,complete_time STRING,status STRING", rows)

ed_roles = ["Attending","Resident","RN","Tech"]
rows = [(f"EDS-{i}",d(i,i),ed_roles[i%4],float(8+i%4),3+i%8) for i in range(120)]
save("ed_staffing", "staff_id STRING,shift_date STRING,role STRING,hours_worked DOUBLE,patients_assigned INT", rows)

bed_units = ["ED Bay","ED Bay","Hallway"]
bed_sts = ["Occupied","Available","Cleaning","Maintenance"]
rows = [(f"BED-{i}",bed_units[i%3],bed_sts[i%4],f"PAT-{i%200}",dt(i,i,8,0),dt(i,i,16,0)) for i in range(80)]
save("bed_tracker", "bed_id STRING,unit STRING,status STRING,patient_id STRING,assign_time STRING,release_time STRING", rows)

vals = [80,120,70,97,95,16]
rows = [(f"VTL-{i}",f"EDV-{i%300}",vitals_list[i%6],float(vals[i%6]+i%40),dt(i,i,9+i%12,0)) for i in range(400)]
save("ed_vitals", "vital_id STRING,visit_id STRING,vital_type STRING,value DOUBLE,recorded_time STRING", rows)

findings_list = ["Normal","Abnormal","Inconclusive"]
rows = [(f"IMG-{i}",f"EDV-{i%300}",modalities[i%4],dt(i,i,9+i%10,0),dt(i,i,10+i%8,0),findings_list[i%3]) for i in range(120)]
save("ed_imaging", "imaging_id STRING,visit_id STRING,modality STRING,order_time STRING,result_time STRING,finding STRING", rows)

rows = [(f"LAB-{i}",f"EDV-{i%300}",lab_tests[i%6],dt(i,i,9+i%10,0),dt(i,i,10+i%6,0),str(10+i%50)) for i in range(300)]
save("ed_labs", "lab_id STRING,visit_id STRING,test_name STRING,order_time STRING,result_time STRING,result_value STRING", rows)

# CELL ********************

# === Scenario 27: Readmission Risk Analytics ===
print("Scenario 27: Readmission Risk Analytics")

rows = [(f"ADM-{i}",f"PAT-{i%200}",d(i,i),d(i,3+i),True if i%5==0 else False,15 if i%5==0 else 0,disch_disp[i%5],f"DRG{100+i%50}") for i in range(240)]
save("admissions", "admission_id STRING,patient_id STRING,admit_date STRING,discharge_date STRING,is_readmission BOOLEAN,days_to_readmit INT,discharge_disposition STRING,drg_code STRING", rows)

rows = [(f"RSK-{i}",f"PAT-{i%200}",float(0.1+i%80*0.01),d(i,1),"v2.1") for i in range(240)]
save("risk_scores", "score_id STRING,patient_id STRING,readmit_risk_score DOUBLE,score_date STRING,model_version STRING", rows)

rows = [(f"SDH-{i}",f"PAT-{i}",housing[i%4],True if i%6==0 else False,True if i%3!=0 else False,ins_types[i%4]) for i in range(200)]
save("social_determinants", "sdoh_id STRING,patient_id STRING,housing_status STRING,food_insecurity BOOLEAN,transportation_access BOOLEAN,insurance_type STRING", rows)

rows = [(f"INT-{i}",f"PAT-{i%200}",interventions_t[i%4],d(i,i),outcomes_list[i%4],f"PRV-{i%20}") for i in range(160)]
save("interventions", "intervention_id STRING,patient_id STRING,intervention_type STRING,start_date STRING,outcome STRING,provider_id STRING", rows)

rows = [(f"DX-{i}",f"PAT-{i%200}",dx_codes[i%5],dx_desc[i%5],d(i,i),True if i%3==0 else False) for i in range(300)]
save("diagnoses", "diagnosis_id STRING,patient_id STRING,icd10_code STRING,description STRING,diagnosis_date STRING,is_primary BOOLEAN", rows)

genders = ["M","F"]
rows = [(f"PAT-{i}",f"Patient {i}",f"19{50+i%40:02d}-{1+i%12:02d}-{1+i%28:02d}",genders[i%2],str(10000+i*100),languages[i%5]) for i in range(400)]
save("patient_demographics", "patient_id STRING,patient_name STRING,date_of_birth STRING,gender STRING,zip_code STRING,primary_language STRING", rows)

# CELL ********************

# === Scenario 28: Surgical Outcomes & OR Utilization ===
print("Scenario 28: Surgical Outcomes & OR Utilization")

rows = [(f"SRG-{i}",f"PAT-{i%200}",f"SRGN-{i%15}",procedures[i%6],d(i,i),90+i%60,85+i%80,case_classes[i%3]) for i in range(200)]
save("surgical_cases", "case_id STRING,patient_id STRING,surgeon_id STRING,procedure_name STRING,case_date STRING,scheduled_duration INT,actual_duration INT,case_class STRING", rows)

rows = [(f"CMP-{i}",f"SRG-{i*5}",comp_types[i%5],severities3[i%3],d(i,3+i)) for i in range(40)]
save("complications", "complication_id STRING,case_id STRING,complication_type STRING,severity STRING,detected_date STRING", rows)

rows = [(f"ORC-{i}",f"OR-{1+i%8}",d(i,i),480+i%120,360+i%150,25+i%20) for i in range(160)]
save("or_utilization", "util_id STRING,or_room STRING,case_date STRING,allocated_minutes INT,used_minutes INT,turnover_minutes INT", rows)

rows = [(f"SRGN-{i}",f"Dr. Surgeon {i}",specialties[i%5],"Surgery") for i in range(30)]
save("surgeon_directory", "surgeon_id STRING,surgeon_name STRING,specialty STRING,department STRING", rows)

rows = [(f"SUP-{i}",f"SRG-{i%200}",supply_items[i%5],1+i%5,float(25+i*10)) for i in range(300)]
save("surgical_supplies", "supply_id STRING,case_id STRING,item_name STRING,quantity INT,unit_cost DOUBLE", rows)

rows = [(f"ANE-{i}",f"SRG-{i}",anes_types[i%4],dt(i,i,7,0),dt(i,i,9+i%4,0),f"ANES-{i%8}") for i in range(200)]
save("anesthesia_records", "record_id STRING,case_id STRING,anesthesia_type STRING,start_time STRING,end_time STRING,provider_id STRING", rows)

rows = [(f"LOG-{i}",f"SRG-{i%200}",case_events[i%4],dt(i,i,7+i%4,i%60),f"Event note {i}") for i in range(400)]
save("case_log", "log_id STRING,case_id STRING,event_type STRING,event_time STRING,notes STRING", rows)

# CELL ********************

# === Scenario 29: Infection Control & Prevention ===
print("Scenario 29: Infection Control & Prevention")

ic_units = ["ICU","Med-Surg","NICU","Burn"]
rows = [(f"HAI-{i}",f"PAT-{i%200}",hai_types[i%5],d(i,i),ic_units[i%4],organisms_list[i%5],hai_cats[i%3]) for i in range(80)]
save("hai_events", "event_id STRING,patient_id STRING,infection_type STRING,onset_date STRING,unit STRING,organism STRING,hai_category STRING", rows)

rows = [(f"CUL-{i}",f"PAT-{i%200}",specimen_types[i%5],d(i,i),culture_results[i%5],suscept[i%4]) for i in range(120)]
save("surveillance_cultures", "culture_id STRING,patient_id STRING,specimen_type STRING,collection_date STRING,organism STRING,susceptibility STRING", rows)

rows = [(f"DEV-{i}",ic_units[i%4],device_types[i%3],f"2025-{1+i%12:02d}-01",50+i*3,200+i*10) for i in range(96)]
save("device_days", "device_id STRING,unit STRING,device_type STRING,report_date STRING,device_count INT,patient_days INT", rows)

hh_units = ["ICU","ED","Med-Surg","OR"]
hh_roles = ["RN","MD","Tech","CNA","RT"]
rows = [(f"HH-{i}",hh_units[i%4],f"Observer {i%5}",d(i,i),True if i%5!=0 else False,hh_roles[i%5]) for i in range(200)]
save("hand_hygiene", "observation_id STRING,unit STRING,observer STRING,observation_date STRING,compliant BOOLEAN,role_observed STRING", rows)

rows = [(f"ABX-{i}",f"PAT-{i%200}",abx_names[i%5],d(i,i),d(i,3+i),routes[i%3],float(500+i*100)) for i in range(120)]
save("antibiotic_usage", "usage_id STRING,patient_id STRING,antibiotic_name STRING,start_date STRING,end_date STRING,route STRING,dose DOUBLE", rows)

env_units = ["ICU","ED","Med-Surg","OR","L&D"]
rows = [(f"ENV-{i}",env_units[i%5],d(i,i),float(85+i%15),i%5,f"Inspector {i%3}") for i in range(60)]
save("environmental_rounds", "round_id STRING,unit STRING,round_date STRING,score DOUBLE,deficiencies INT,inspector STRING", rows)

iso_units = ["ICU","Med-Surg","ED"]
rows = [(f"ISO-{i}",f"PAT-{i%200}",precaution_types[i%4],d(i,i),d(i,5+i),iso_units[i%3]) for i in range(60)]
save("isolation_precautions", "precaution_id STRING,patient_id STRING,precaution_type STRING,start_date STRING,end_date STRING,unit STRING", rows)

# CELL ********************

# === Scenario 30: Nursing Quality Metrics ===
print("Scenario 30: Nursing Quality Metrics")

nq_units = ["ICU","Med-Surg","Rehab","Geri-Psych"]
rows = [(f"FALL-{i}",f"PAT-{i%200}",d(i,i),nq_units[i%4],injury_levels[i%4],True if i%4>=2 else False,fall_types[i%3]) for i in range(70)]
save("falls", "fall_id STRING,patient_id STRING,fall_date STRING,unit STRING,injury_level STRING,with_injury BOOLEAN,fall_type STRING", rows)

pi_units_list = ["ICU","Med-Surg","LTAC"]
rows = [(f"PI-{i}",f"PAT-{i%200}",d(i,i),pi_stages[i%5],pi_locations[i%4],pi_units_list[i%3],True if i%3==0 else False) for i in range(40)]
save("pressure_injuries", "pi_id STRING,patient_id STRING,onset_date STRING,stage STRING,location STRING,unit STRING,is_hapi BOOLEAN", rows)

rows = [(f"ASM-{i}",f"PAT-{i%200}",d(i,i),12+i%11,20+i%80,i%11) for i in range(200)]
save("nurse_assessments", "assessment_id STRING,patient_id STRING,assessment_date STRING,braden_score INT,morse_score INT,pain_score INT", rows)

sat_units = ["ICU","Med-Surg","ED","L&D","Peds"]
rows = [(f"SAT-{i}",sat_units[i%5],f"2025-{1+i%12:02d}-01",float(60+i%40),float(65+i%35),float(55+i%45)) for i in range(60)]
save("patient_satisfaction", "survey_id STRING,unit STRING,survey_date STRING,overall_score DOUBLE,nurse_communication DOUBLE,responsiveness DOUBLE", rows)

se_types = ["Med error","Fall","Skin breakdown","Wrong site","Delay in care"]
se_sev = ["Near Miss","No Harm","Minor","Major"]
se_units = ["ICU","Med-Surg","ED","OR"]
rows = [(f"SE-{i}",f"PAT-{i%200}",d(i,i),se_types[i%5],se_sev[i%4],se_units[i%4]) for i in range(80)]
save("safety_events", "event_id STRING,patient_id STRING,event_date STRING,event_type STRING,severity STRING,unit STRING", rows)

c_units = ["ICU","Med-Surg","ED","L&D","Peds","Rehab"]
rows = [(f"CEN-{i}",c_units[i%6],f"2025-{1+i%12:02d}-01",600+i*20,80+i*3,75+i*3) for i in range(144)]
save("unit_census", "census_id STRING,unit STRING,census_date STRING,patient_days INT,admissions INT,discharges INT", rows)

wf_units = ["ICU","Med-Surg","ED","L&D","Peds"]
wf_roles = ["RN","CNA","LPN"]
wf_shifts = ["Day","Night","Evening"]
rows = [(f"WF-{i}",wf_units[i%5],wf_roles[i%3],wf_shifts[i%3],float(1.0 if i%3==0 else (0.8 if i%3==1 else 0.6))) for i in range(100)]
save("workforce", "staff_id STRING,unit STRING,role STRING,shift STRING,fte DOUBLE", rows)

sh_units = ["ICU","Med-Surg","ED","L&D","Peds"]
rows = [(f"SH-{i}",sh_units[i%5],d(i,i),float(96+i%48),float(48+i%24),float(8+i%16)) for i in range(120)]
save("staffing_hours", "staffing_id STRING,unit STRING,staffing_date STRING,rn_hours DOUBLE,cna_hours DOUBLE,agency_hours DOUBLE", rows)

rst_units = ["ICU","Geri-Psych","Med-Surg"]
rows = [(f"RST-{i}",f"PAT-{i%200}",d(i,i),restraint_types[i%4],float(2+i%22),rst_units[i%3]) for i in range(30)]
save("restraints", "restraint_id STRING,patient_id STRING,restraint_date STRING,type STRING,duration_hours DOUBLE,unit STRING", rows)

rows = [(f"EDU-{i}",f"STF-{i%160}",courses[i%5],d(i,i),"Overdue" if i%4==0 else "Complete") for i in range(160)]
save("education_compliance", "compliance_id STRING,staff_id STRING,course_name STRING,completion_date STRING,status STRING", rows)

# CELL ********************

# === Scenario 31: Patient Safety & Event Reporting ===
print("Scenario 31: Patient Safety & Event Reporting")

ps_depts = ["ED","ICU","Med-Surg","OR","Pharmacy"]
rows = [(f"EVT-{i}",f"PAT-{i%200}",d(i,i),event_types_safety[i%5],i%5,ps_depts[i%5],reporter_roles[i%4],f"Event description {i}") for i in range(120)]
save("event_reports", "event_id STRING,patient_id STRING,event_date STRING,event_type STRING,harm_level INT,department STRING,reporter_role STRING,description STRING", rows)

rows = [(f"RCA-{i}",f"EVT-{i*3}",d(i,5+i),rca_statuses[i%4],root_causes[i%4],f"Lead {i%5}") for i in range(40)]
save("root_cause_analyses", "rca_id STRING,event_id STRING,start_date STRING,status STRING,root_cause STRING,team_lead STRING", rows)

rows = [(f"ACT-{i}",f"RCA-{i%40}",f"Improvement action {i}",f"2025-{1+i%12:02d}-28",rca_statuses[i%4],f"Responsible {i%10}") for i in range(80)]
save("improvement_actions", "action_id STRING,rca_id STRING,action_description STRING,due_date STRING,status STRING,responsible_party STRING", rows)

rows = [(f"MRT-{i}",f"PAT-{i%200}",d(i,i),d(i,15+i),prevent[i%3],review_committees[i%3]) for i in range(30)]
save("mortality_reviews", "review_id STRING,patient_id STRING,death_date STRING,review_date STRING,preventability STRING,review_committee STRING", rows)

rows = [(f"PR-{i}",f"PRV-{i%20}",f"SRG-{i%200}",d(i,i),pr_outcomes[i%3],f"REV-{i%10}") for i in range(50)]
save("peer_review", "review_id STRING,provider_id STRING,case_id STRING,review_date STRING,outcome STRING,reviewer_id STRING", rows)

rows = [(f"CLM2-{i}",f"PAT-{i%200}",d(i,i),claim_types_safety[i%3],float(50000+i*25000),claim_st[i%3]) for i in range(24)]
save("claims_data", "claim_id STRING,patient_id STRING,claim_date STRING,claim_type STRING,settlement_amount DOUBLE,status STRING", rows)

rows = [(f"PSI-{i}",psi_codes[i%6],2+i%10,500+i*50,float(round((2+i%10)/(500+i*50)*1000,2)),f"2025-{1+i%12:02d}-01") for i in range(48)]
save("psi_indicators", "psi_id STRING,indicator_code STRING,numerator INT,denominator INT,rate DOUBLE,report_period STRING", rows)

sc_depts = ["ED","ICU","Med-Surg","OR","Pharmacy","Lab"]
rows = [(f"SCS-{i}",sc_depts[i%6],f"2025-{1+i%12:02d}-01",float(70+i%25),float(65+i%30),float(60+i%35),float(0.5+i%5*0.1)) for i in range(24)]
save("safety_culture_survey", "survey_id STRING,department STRING,survey_date STRING,teamwork_score DOUBLE,reporting_score DOUBLE,management_score DOUBLE,response_rate DOUBLE", rows)

# CELL ********************

# === Summary ===
print("\n=== COMPLETE ===")
tables = spark.sql("SHOW TABLES").collect()
print(f"Total tables in lakehouse: {len(tables)}")
for t in sorted(tables, key=lambda x: x.tableName):
    cnt = spark.sql(f"SELECT COUNT(*) as c FROM {t.tableName}").collect()[0].c
    print(f"  {t.tableName:35s} | {cnt} rows")
print("All healthcare scenario tables created successfully!")
