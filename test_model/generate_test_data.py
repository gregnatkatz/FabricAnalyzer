"""Generate realistic LOS hospital data for deploying to a Fabric test instance.

Creates CSV files for a semantic model with 33 tables, intentionally designed
with every latency anti-pattern to push Data Agent response times >40 seconds.

Latency-killing anti-patterns embedded:
1. 33 tables (massive schema scope -- optimal is 8-15)
2. Snowflake schema with 5-deep relationship chains
3. Duplicate/near-duplicate measures (Total LOS vs Sum of LOS vs LOS Total)
4. Bi-directional cross-filters on 3 relationships
5. Hidden columns referenced in DAX measures
6. No table descriptions on any table
7. Ambiguous measure names (Rate, Ratio, Pct used interchangeably)
8. 50+ measures (excessive measure count)
9. Calculated columns that could be measures
10. Wide tables with 30+ columns each
11. No V-Order / no column sorting hints
12. Multiple fact tables with no clear grain documentation
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)
OUT_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(OUT_DIR, exist_ok=True)

# --- Helper functions ---
def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

FIRST_NAMES = ['James','Mary','Robert','Patricia','John','Jennifer','Michael','Linda',
               'David','Elizabeth','William','Barbara','Richard','Susan','Joseph','Jessica',
               'Thomas','Sarah','Charles','Karen','Christopher','Lisa','Daniel','Nancy',
               'Matthew','Betty','Anthony','Margaret','Mark','Sandra','Donald','Ashley',
               'Steven','Kimberly','Paul','Emily','Andrew','Donna','Joshua','Michelle']
LAST_NAMES = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
              'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
              'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
              'White','Harris','Sanchez','Clark','Ramirez','Lewis','Robinson']

def random_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 12, 31)
NUM_ENCOUNTERS = 10000
NUM_PATIENTS = 3000
NUM_PHYSICIANS = 100
NUM_DEPARTMENTS = 25
NUM_DIAGNOSES = 200
NUM_PAYERS = 30
NUM_FACILITIES = 8
NUM_PROCEDURES = 150
NUM_MEDICATIONS = 200
NUM_LAB_TESTS = 80
NUM_NURSING_UNITS = 40
NUM_CARE_TEAMS = 30
NUM_SUPPLIERS = 40
NUM_EQUIPMENT = 60

def write_csv(filename, headers, rows):
    path = os.path.join(OUT_DIR, filename)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f'  {filename}: {len(rows)} rows, {len(headers)} columns')

print('Generating LOS test model data...\n')

# --- DimPatient (wide table -- 32 columns) ---
patients = []
for i in range(1, NUM_PATIENTS + 1):
    first, last = random_name()
    dob = random_date(datetime(1930, 1, 1), datetime(2010, 1, 1))
    patients.append([
        i, f'MRN-{i:06d}', first, last, f'{first[0]}.', dob.strftime('%Y-%m-%d'),
        random.choice(['M', 'F', 'NB']),
        random.choice(['White', 'Black', 'Hispanic', 'Asian', 'Other', 'Unknown']),
        random.choice(['English', 'Spanish', 'French', 'Mandarin', 'Arabic', 'Other']),
        random.choice(['Single', 'Married', 'Divorced', 'Widowed']),
        f'{random.randint(100,999)} {random.choice(["Main","Oak","Elm","Pine","Maple"])} St',
        random.choice(['Orlando','Tampa','Jacksonville','Miami','Tallahassee','Gainesville']),
        'FL', f'{random.randint(32000,34999)}',
        f'({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}',
        f'{first.lower()}.{last.lower()}@email.com',
        random.choice(['Medicare', 'Medicaid', 'Commercial', 'Self-Pay', 'Tricare']),
        f'INS-{random.randint(100000,999999)}',
        random.choice(['', 'Diabetes', 'Hypertension', 'COPD', 'CHF', 'Asthma', 'CKD']),
        random.choice(['', 'Penicillin', 'Sulfa', 'Latex', 'Aspirin', 'None']),
        random.choice(['Active', 'Inactive', 'Deceased']),
        random.choice(['Dr. Smith', 'Dr. Johnson', 'Dr. Williams', 'Dr. Brown', 'Dr. Jones']),
        random.choice(['Yes', 'No']), random.choice(['Yes', 'No', 'Unknown']),
        random.choice(['Full Code', 'DNR', 'DNI', 'DNR/DNI', 'Comfort Care']),
        random.choice(['', 'English', 'Spanish']),
        random.choice(['Self', 'Spouse', 'Child', 'Parent', 'Other']),
        random.randint(0, 15),
        random.choice([0, 0, 0, 1, 1, 2]),
        round(random.uniform(0, 100), 2),
        random.choice(['Low', 'Medium', 'High', 'Critical']),
        (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
        f'NOTE-{i}'
    ])
write_csv('DimPatient.csv', [
    'PatientKey', 'MRN', 'FirstName', 'LastName', 'MiddleInitial', 'DateOfBirth',
    'Gender', 'Race', 'Language', 'MaritalStatus', 'Address', 'City', 'State', 'ZipCode',
    'Phone', 'Email', 'PrimaryInsurance', 'InsurancePolicyNumber',
    'ChronicCondition', 'Allergies', 'PatientStatus', 'PrimaryCarePhysician',
    'AdvanceDirective', 'OrganDonor', 'CodeStatus', 'PreferredLanguage',
    'EmergencyContactRelation', 'PriorAdmissions', 'EDVisits90d',
    'RiskScore', 'RiskCategory', 'LastVisitDate', 'InternalNoteID'
], patients)

# --- DimPhysician ---
specialties = ['Internal Medicine', 'Cardiology', 'Pulmonology', 'Nephrology', 'Oncology',
               'Neurology', 'Orthopedics', 'Surgery', 'Pediatrics', 'OB/GYN', 'Psychiatry',
               'Emergency Medicine', 'Radiology', 'Pathology', 'Anesthesiology']
physicians = []
for i in range(1, NUM_PHYSICIANS + 1):
    first, last = random_name()
    physicians.append([
        i, f'NPI-{random.randint(1000000000, 9999999999)}',
        f'Dr. {first} {last}', first, last,
        random.choice(specialties),
        random.choice(['MD', 'DO', 'MBBS']),
        random.randint(1, 40),
        random.choice(['Active', 'Inactive', 'On Leave']),
        random.choice(['Group A', 'Group B', 'Group C', 'Independent']),
        random.choice(['Full-Time', 'Part-Time', 'Locum']),
        round(random.uniform(3.0, 5.0), 2),
        random.randint(50, 500),
    ])
write_csv('DimPhysician.csv', [
    'PhysicianKey', 'NPI', 'FullName', 'FirstName', 'LastName',
    'Specialty', 'Degree', 'YearsExperience', 'Status', 'PracticeGroup',
    'EmploymentType', 'QualityScore', 'AnnualCaseload'
], physicians)

# --- DimDepartment ---
dept_names = ['Emergency', 'ICU', 'NICU', 'CCU', 'Medical/Surgical', 'Telemetry',
              'Oncology', 'Orthopedics', 'Labor & Delivery', 'Pediatrics', 'Psychiatry',
              'Rehabilitation', 'Burn Unit', 'Transplant', 'Neurology', 'Cardiology',
              'Pulmonology', 'Step-Down', 'Observation', 'Pre-Op', 'Post-Op',
              'Same Day Surgery', 'Radiology', 'Laboratory', 'Pharmacy']
departments = []
for i in range(1, NUM_DEPARTMENTS + 1):
    departments.append([
        i, dept_names[i-1] if i <= len(dept_names) else f'Dept_{i}',
        random.randint(1, 8), random.randint(10, 60),
        random.choice(['Medical', 'Surgical', 'Critical Care', 'Support']),
        random.choice(['Active', 'Inactive']),
        f'MGR-{random.randint(100, 999)}',
        round(random.uniform(0.5, 1.0), 2),
        round(random.uniform(50000, 500000), 2),
    ])
write_csv('DimDepartment.csv', [
    'DepartmentKey', 'DepartmentName', 'FloorNumber', 'BedCount',
    'ServiceLine', 'Status', 'ManagerID', 'TargetOccupancy', 'MonthlyBudget'
], departments)

# --- DimDiagnosis ---
mdc_categories = ['Nervous System', 'Eye', 'ENT', 'Respiratory', 'Circulatory',
                   'Digestive', 'Hepatobiliary', 'Musculoskeletal', 'Skin',
                   'Endocrine', 'Kidney', 'Male Reproductive', 'Female Reproductive',
                   'Pregnancy', 'Newborn', 'Blood', 'Myeloproliferative',
                   'Infectious', 'Mental', 'Substance Abuse']
diagnoses = []
for i in range(1, NUM_DIAGNOSES + 1):
    letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    code = f'{letter}{random.randint(10,99)}.{random.randint(0,9)}'
    diagnoses.append([
        i, code, f'Diagnosis {code} Description',
        random.choice(mdc_categories),
        random.choice(['1', '2', '3', '4']),
        random.choice(['Medical', 'Surgical', 'Observation']),
        round(random.uniform(1.0, 15.0), 1),
        round(random.uniform(0.0, 0.15), 3),
    ])
write_csv('DimDiagnosis.csv', [
    'DiagnosisKey', 'ICDCode', 'Description', 'MDC_Category',
    'Severity', 'Type', 'ExpectedLOS', 'ExpectedMortality'
], diagnoses)

# --- DimPayer ---
payer_names = ['Medicare FFS', 'Medicare Advantage - Humana', 'Medicare Advantage - UHC',
               'Medicaid', 'Medicaid Managed - Molina', 'Medicaid Managed - Centene',
               'BlueCross BlueShield', 'Aetna', 'Cigna', 'UnitedHealthcare',
               'Humana Commercial', 'Tricare', 'Workers Comp', 'Self-Pay',
               'Charity Care', 'VA', 'Oscar Health', 'Ambetter',
               'Bright Health', 'Devoted Health'] + [f'Payer_{i}' for i in range(21, NUM_PAYERS + 1)]
payers = []
for i in range(1, NUM_PAYERS + 1):
    payers.append([
        i, payer_names[i-1],
        random.choice(['Government', 'Commercial', 'Self-Pay', 'Other']),
        random.choice(['FFS', 'Managed Care', 'Capitated', 'Bundled']),
        round(random.uniform(0.4, 1.0), 2),
        random.choice(['Active', 'Inactive']),
        random.randint(1, 365),
    ])
write_csv('DimPayer.csv', [
    'PayerKey', 'PayerName', 'PayerCategory', 'PaymentModel',
    'ContractRatePct', 'Status', 'AvgDaysToPay'
], payers)

# --- DimFacility ---
facility_cities = ['Orlando', 'Tampa', 'Daytona', 'Kissimmee', 'Winter Park', 'Altamonte', 'Celebration', 'DeLand']
facilities = []
for i in range(1, NUM_FACILITIES + 1):
    facilities.append([
        i, f'AdventHealth {facility_cities[i-1]}',
        random.choice(['Main Campus', 'Satellite', 'Outpatient Center']),
        random.randint(100, 800),
        random.choice(['Level I', 'Level II', 'Level III', 'N/A']),
        random.choice(['Yes', 'No']),
        f'FL-{random.randint(1000, 9999)}',
    ])
write_csv('DimFacility.csv', [
    'FacilityKey', 'FacilityName', 'FacilityType', 'TotalBeds',
    'TraumaLevel', 'TeachingHospital', 'LicenseNumber'
], facilities)

# --- DimNursingUnit ---
nursing_units = []
for i in range(1, NUM_NURSING_UNITS + 1):
    nursing_units.append([
        i, f'Unit {i}{random.choice("ABCDEF")}',
        random.randint(1, NUM_DEPARTMENTS), random.randint(1, NUM_FACILITIES),
        random.randint(8, 40), round(random.uniform(3.0, 8.0), 1),
        random.choice(['ICU', 'Med/Surg', 'Tele', 'Step-Down', 'Rehab', 'Observation']),
    ])
write_csv('DimNursingUnit.csv', [
    'NursingUnitKey', 'UnitName', 'DepartmentKey', 'FacilityKey',
    'BedCount', 'NursePatientRatio', 'UnitType'
], nursing_units)

# --- DimProcedure ---
procedures = []
for i in range(1, NUM_PROCEDURES + 1):
    procedures.append([
        i, f'CPT-{random.randint(10000, 99999)}',
        f'Procedure {i} Description',
        random.choice(['Surgical', 'Diagnostic', 'Therapeutic', 'Preventive']),
        round(random.uniform(100, 50000), 2),
        random.randint(15, 480),
        random.choice(['Inpatient', 'Outpatient', 'Both']),
    ])
write_csv('DimProcedure.csv', [
    'ProcedureKey', 'CPTCode', 'Description', 'Category',
    'StandardCost', 'AvgDurationMinutes', 'Setting'
], procedures)

# --- DimMedication ---
med_names = ['Metformin', 'Lisinopril', 'Amlodipine', 'Atorvastatin', 'Omeprazole',
             'Metoprolol', 'Losartan', 'Albuterol', 'Gabapentin', 'Hydrochlorothiazide',
             'Levothyroxine', 'Acetaminophen', 'Ibuprofen', 'Morphine', 'Heparin',
             'Vancomycin', 'Ceftriaxone', 'Insulin', 'Warfarin', 'Furosemide']
medications = []
for i in range(1, NUM_MEDICATIONS + 1):
    medications.append([
        i, f'NDC-{random.randint(10000, 99999)}-{random.randint(100, 999)}',
        random.choice(med_names) + f' {random.choice(["5mg","10mg","20mg","50mg","100mg","250mg","500mg"])}',
        random.choice(['Oral', 'IV', 'IM', 'Topical', 'Inhaled', 'Subcutaneous']),
        random.choice(['Analgesic', 'Antibiotic', 'Antihypertensive', 'Antidiabetic',
                       'Anticoagulant', 'Statin', 'Diuretic', 'Bronchodilator', 'Cardiac']),
        round(random.uniform(0.50, 500.00), 2),
        random.choice(['Yes', 'No']),
        random.choice(['Generic', 'Brand']),
    ])
write_csv('DimMedication.csv', [
    'MedicationKey', 'NDC', 'MedicationName', 'Route',
    'TherapeuticClass', 'CostPerDose', 'HighAlert', 'GenericBrand'
], medications)

# --- DimLabTest ---
lab_names = ['CBC', 'BMP', 'CMP', 'Troponin', 'BNP', 'Lactate', 'ABG',
             'Urinalysis', 'Blood Culture', 'Hemoglobin A1C', 'TSH', 'PT/INR',
             'D-Dimer', 'Lipid Panel', 'Liver Function', 'Renal Panel',
             'Procalcitonin', 'CRP', 'ESR', 'Ferritin']
lab_tests = []
for i in range(1, NUM_LAB_TESTS + 1):
    lab_tests.append([
        i, f'LOINC-{random.randint(10000, 99999)}',
        random.choice(lab_names) + f' #{i}',
        random.choice(['Chemistry', 'Hematology', 'Microbiology', 'Coagulation', 'Urinalysis']),
        random.randint(15, 240),
        round(random.uniform(5, 200), 2),
    ])
write_csv('DimLabTest.csv', [
    'LabTestKey', 'LOINCCode', 'TestName', 'Category', 'TargetTATMinutes', 'Cost'
], lab_tests)

# --- DimCareTeam ---
care_teams = []
for i in range(1, NUM_CARE_TEAMS + 1):
    care_teams.append([
        i, f'Team {random.choice(["Alpha","Bravo","Charlie","Delta","Echo","Foxtrot","Golf","Hotel"])}-{i}',
        random.choice(['Hospitalist', 'Surgical', 'ICU', 'Rapid Response', 'Palliative', 'Wound Care']),
        random.randint(3, 12), random.randint(1, NUM_PHYSICIANS),
    ])
write_csv('DimCareTeam.csv', [
    'CareTeamKey', 'TeamName', 'TeamType', 'TeamSize', 'LeadPhysicianKey'
], care_teams)

# --- DimSupplier ---
suppliers = []
for i in range(1, NUM_SUPPLIERS + 1):
    suppliers.append([
        i, f'Supplier {random.choice(["Medical","Health","Care","Vital","Pro","Bio","Med"])} Corp {i}',
        random.choice(['Medical Devices', 'Pharmaceuticals', 'Surgical Supplies', 'PPE', 'IT', 'Food Service']),
        random.choice(['Active', 'Inactive', 'Preferred']),
        random.choice(['A', 'B', 'C']),
    ])
write_csv('DimSupplier.csv', [
    'SupplierKey', 'SupplierName', 'Category', 'Status', 'Tier'
], suppliers)

# --- DimEquipment ---
equip_types = ['Ventilator', 'Infusion Pump', 'Monitor', 'Defibrillator', 'Ultrasound',
               'X-Ray Machine', 'CT Scanner', 'MRI', 'Bed', 'Wheelchair',
               'Stretcher', 'Oxygen Concentrator', 'CPAP', 'BiPAP', 'EKG Machine']
equipment = []
for i in range(1, NUM_EQUIPMENT + 1):
    equipment.append([
        i, f'EQ-{i:04d}', random.choice(equip_types),
        random.choice(['Active', 'Maintenance', 'Retired']),
        random.randint(1, NUM_DEPARTMENTS),
        random_date(datetime(2018, 1, 1), datetime(2024, 1, 1)).strftime('%Y-%m-%d'),
    ])
write_csv('DimEquipment.csv', [
    'EquipmentKey', 'AssetTag', 'EquipmentType', 'Status', 'DepartmentKey', 'PurchaseDate'
], equipment)

# --- CalendarDate ---
calendar = []
d = START_DATE
while d <= END_DATE:
    calendar.append([
        d.strftime('%Y-%m-%d'), d.year, d.month, d.day,
        d.strftime('%B'), d.strftime('%A'),
        (d.month - 1) // 3 + 1, d.isocalendar()[1],
        f'FY{d.year}' if d.month >= 7 else f'FY{d.year - 1}',
        1 if d.weekday() < 5 else 0,
        1 if (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 2) else 0,
    ])
    d += timedelta(days=1)
write_csv('CalendarDate.csv', [
    'DateKey', 'Year', 'Month', 'Day', 'MonthName', 'DayName',
    'Quarter', 'WeekOfYear', 'FiscalYear', 'IsWeekday', 'IsHoliday'
], calendar)

# --- Small dimension tables ---
sources = ['Emergency', 'Elective', 'Transfer', 'Newborn', 'Observation', 'Direct Admit',
           'Clinic Referral', 'Physician Referral', 'Self-Referral', 'Trauma']
write_csv('DimAdmissionSource.csv', ['AdmissionSourceKey', 'SourceName', 'UrgencyLevel'],
          [[i, s, random.choice(['Urgent', 'Non-Urgent', 'Emergency'])] for i, s in enumerate(sources, 1)])

dispositions = ['Home', 'Home Health', 'SNF', 'Rehab', 'LTAC', 'AMA', 'Expired',
                'Hospice', 'Transfer to Another Hospital', 'Jail/Detention']
write_csv('DimDischargeDisposition.csv', ['DispositionKey', 'DispositionName', 'ComplexityLevel'],
          [[i, d, random.choice(['Routine', 'Complex', 'Critical'])] for i, d in enumerate(dispositions, 1)])

rooms = [[i, f'{random.randint(1,8)}{random.randint(0,9)}{random.randint(0,9)}{random.choice("AB")}',
          random.choice(['Private', 'Semi-Private', 'ICU', 'Isolation', 'Observation']),
          random.randint(1, NUM_DEPARTMENTS), random.randint(1, NUM_NURSING_UNITS),
          random.choice(['Available', 'Occupied', 'Cleaning', 'Maintenance'])] for i in range(1, 201)]
write_csv('DimRoomBed.csv', ['RoomBedKey', 'RoomNumber', 'RoomType', 'DepartmentKey', 'NursingUnitKey', 'Status'], rooms)

insurance_plans = [[i, f'Plan-{i:03d}', random.choice(['HMO', 'PPO', 'EPO', 'POS', 'HDHP', 'Medicare', 'Medicaid']),
                    random.randint(1, NUM_PAYERS), round(random.uniform(500, 10000), 2),
                    round(random.uniform(10, 50), 0), round(random.uniform(0.7, 1.0), 2)] for i in range(1, 51)]
write_csv('DimInsurancePlan.csv', ['PlanKey', 'PlanCode', 'PlanType', 'PayerKey', 'Deductible', 'Copay', 'CoveragePct'], insurance_plans)

roles = ['Attending', 'Resident', 'Fellow', 'NP', 'PA', 'RN', 'LPN', 'CNA', 'RT', 'PT', 'OT', 'SW', 'Pharmacist', 'Dietitian', 'Chaplain']
write_csv('DimStaffRole.csv', ['RoleKey', 'RoleName', 'RoleCategory'],
          [[i, r, random.choice(['Clinical', 'Support'])] for i, r in enumerate(roles, 1)])

qm_names = ['Falls Rate', 'CLABSI Rate', 'CAUTI Rate', 'SSI Rate', 'HAI Rate',
             'Mortality Index', 'Readmission Index', 'Patient Satisfaction',
             'Door-to-Balloon', 'Sepsis Bundle Compliance', 'VTE Prophylaxis',
             'Hand Hygiene Rate', 'Medication Error Rate', 'Restraint Use', 'Pressure Injury Rate']
write_csv('DimQualityMeasure.csv', ['QualityMeasureKey', 'MeasureName', 'MeasureType', 'Source', 'Target'],
          [[i, qm, random.choice(['Process', 'Outcome', 'Structure']),
            random.choice(['CMS', 'Joint Commission', 'Leapfrog', 'Internal']),
            round(random.uniform(0.0, 1.0), 3)] for i, qm in enumerate(qm_names, 1)])

# Snowflake dims
write_csv('DimBudgetAccount.csv', ['AccountKey', 'AccountCode', 'AccountType', 'CostCategory', 'AnnualBudget'],
          [[i, f'ACCT-{i:03d}', random.choice(['Revenue', 'Expense', 'Capital', 'Operating']),
            random.choice(['Direct', 'Indirect', 'Overhead']), round(random.uniform(10000, 1000000), 2)]
           for i in range(1, 51)])

write_csv('DimCostCenter.csv', ['CostCenterKey', 'CostCenterCode', 'CostCenterName', 'DepartmentKey', 'CenterType'],
          [[i, f'CC-{i:03d}', f'Cost Center {i}', random.randint(1, NUM_DEPARTMENTS),
            random.choice(['Clinical', 'Administrative', 'Support'])] for i in range(1, 31)])

write_csv('DimGeography.csv', ['GeographyKey', 'County', 'State', 'Region', 'MSA'],
          [[i, random.choice(['Orange', 'Seminole', 'Osceola', 'Volusia', 'Lake', 'Brevard', 'Polk', 'Hillsborough']),
            'FL', random.choice(['Central', 'North', 'South', 'East', 'West']), f'MSA-{random.randint(1,5)}']
           for i in range(1, 21)])

write_csv('DimTimeOfDay.csv', ['TimeKey', 'TimeValue', 'AMPM', 'Shift', 'PeakStatus'],
          [[h * 2 + (1 if half else 0) + 1, f'{h:02d}:{half:02d}',
            'AM' if h < 12 else 'PM', 'Day' if 7 <= h < 19 else 'Night',
            random.choice(['Peak', 'Off-Peak'])] for h in range(24) for half in [0, 30]])

# --- FactEncounters (main fact -- 10K rows, 31 columns) ---
print('\n  Generating FactEncounters...')
encounters = []
for i in range(1, NUM_ENCOUNTERS + 1):
    admit = random_date(START_DATE, END_DATE)
    los = max(0, int(random.gauss(5.2, 4.5)))
    discharge = admit + timedelta(days=los)
    encounters.append([
        i, random.randint(1, NUM_PATIENTS), random.randint(1, NUM_PHYSICIANS),
        random.randint(1, NUM_DEPARTMENTS), random.randint(1, NUM_DIAGNOSES),
        random.randint(1, NUM_PAYERS), random.randint(1, NUM_FACILITIES),
        random.randint(1, len(sources)), random.randint(1, len(dispositions)),
        random.randint(1, NUM_NURSING_UNITS), random.randint(1, NUM_CARE_TEAMS),
        random.randint(1, 200),
        admit.strftime('%Y-%m-%d'), discharge.strftime('%Y-%m-%d'),
        admit.strftime('%Y-%m-%d'), los,
        round(random.uniform(5000, 150000), 2),
        round(random.uniform(3000, 100000), 2),
        round(random.uniform(2000, 80000), 2),
        random.choice(['Inpatient', 'Observation', 'Emergency']),
        random.choice([0, 0, 0, 0, 1]),
        random.randint(0, 5),
        random.choice([0, 0, 0, 1]),
        random.randint(0, los) if random.random() > 0.7 else 0,
        random.choice(['1', '2', '3', '4']),
        random.choice([0, 0, 0, 0, 0, 1]),
        random.choice([0, 0, 1]),
        random.randint(0, 10),
        random.randint(1, 25),
        round(random.uniform(0, 100), 2),
        round(random.uniform(0.5, 4.0), 2),
    ])
write_csv('FactEncounters.csv', [
    'EncounterKey', 'PatientKey', 'AttendingPhysicianKey', 'DepartmentKey',
    'PrimaryDiagnosisKey', 'PayerKey', 'FacilityKey', 'AdmissionSourceKey',
    'DischargeDispositionKey', 'NursingUnitKey', 'CareTeamKey', 'RoomBedKey',
    'AdmissionDate', 'DischargeDate', 'DateKey', 'LOS_Days',
    'TotalCharges', 'TotalCost', 'Reimbursement', 'EncounterType',
    'IsReadmission', 'EDHoursBeforeAdmit', 'ICU_Flag', 'ICU_Days',
    'Acuity', 'ExpiredFlag', 'SurgicalFlag', 'ProcedureCount',
    'MedicationCount', 'PatientSatisfactionScore', 'CaseMixIndex'
], encounters)

# --- FactProcedures ---
proc_facts = []
pk = 1
for enc in encounters[:6000]:
    for _ in range(random.randint(1, 3)):
        proc_facts.append([pk, enc[0], random.randint(1, NUM_PROCEDURES),
                           random.randint(1, NUM_PHYSICIANS),
                           random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
                           random.randint(15, 480), round(random.uniform(100, 50000), 2),
                           random.choice(['Completed', 'Cancelled', 'In Progress'])])
        pk += 1
write_csv('FactProcedures.csv', [
    'ProcedureFactKey', 'EncounterKey', 'ProcedureKey', 'SurgeonKey',
    'ProcedureDate', 'DurationMinutes', 'Charges', 'Status'
], proc_facts)

# --- FactMedications ---
med_facts = []
mk = 1
for enc in encounters[:8000]:
    for _ in range(random.randint(1, 5)):
        med_facts.append([mk, enc[0], random.randint(1, NUM_MEDICATIONS),
                          random.randint(1, NUM_PHYSICIANS),
                          random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
                          random.randint(1, 30), round(random.uniform(1, 1000), 2),
                          random.choice(['Administered', 'Held', 'Discontinued', 'PRN'])])
        mk += 1
write_csv('FactMedications.csv', [
    'MedicationFactKey', 'EncounterKey', 'MedicationKey', 'OrderingPhysicianKey',
    'OrderDate', 'DosesAdministered', 'TotalMedCost', 'Status'
], med_facts)

# --- FactLabResults ---
lab_facts = []
lk = 1
for enc in encounters[:7000]:
    for _ in range(random.randint(1, 4)):
        lab_facts.append([lk, enc[0], random.randint(1, NUM_LAB_TESTS),
                          random_date(START_DATE, END_DATE).strftime('%Y-%m-%d %H:%M'),
                          round(random.uniform(0.1, 500.0), 2),
                          random.choice(['mg/dL', 'g/dL', 'mEq/L', 'U/L', 'mmol/L', 'cells/uL', '%']),
                          random.choice(['Normal', 'Abnormal High', 'Abnormal Low', 'Critical High', 'Critical Low']),
                          random.randint(10, 240)])
        lk += 1
write_csv('FactLabResults.csv', [
    'LabResultKey', 'EncounterKey', 'LabTestKey', 'CollectionDateTime',
    'ResultValue', 'Unit', 'ResultFlag', 'TurnaroundMinutes'
], lab_facts)

# --- FactQualityEvents ---
write_csv('FactQualityEvents.csv', ['QualityEventKey', 'EncounterKey', 'QualityMeasureKey', 'EventDate', 'Outcome', 'Score', 'DepartmentKey'],
          [[i, random.randint(1, NUM_ENCOUNTERS), random.randint(1, len(qm_names)),
            random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
            random.choice(['Met', 'Not Met', 'Excluded']),
            round(random.uniform(0, 1), 3), random.randint(1, NUM_DEPARTMENTS)]
           for i in range(1, 3001)])

# --- FactSupplyUsage ---
write_csv('FactSupplyUsage.csv', ['SupplyUsageKey', 'EncounterKey', 'SupplierKey', 'UsageDate', 'Quantity', 'Cost', 'DepartmentKey'],
          [[i, random.randint(1, NUM_ENCOUNTERS), random.randint(1, NUM_SUPPLIERS),
            random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
            random.randint(1, 100), round(random.uniform(1, 5000), 2),
            random.randint(1, NUM_DEPARTMENTS)] for i in range(1, 5001)])

# --- FactEquipmentUsage ---
write_csv('FactEquipmentUsage.csv', ['EquipmentUsageKey', 'EncounterKey', 'EquipmentKey', 'UsageDate', 'HoursUsed', 'Status'],
          [[i, random.randint(1, NUM_ENCOUNTERS), random.randint(1, NUM_EQUIPMENT),
            random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
            random.randint(1, 72), random.choice(['In Use', 'Returned', 'Damaged'])]
           for i in range(1, 3001)])

# --- FactFinancialSummary (intentionally redundant with FactEncounters) ---
fin_summary = []
for i in range(1, NUM_ENCOUNTERS + 1):
    enc = encounters[i-1]
    charges, cost, reimb = float(enc[16]), float(enc[17]), float(enc[18])
    fin_summary.append([
        i, enc[0], enc[5], enc[16], enc[17], enc[18],
        round(charges - reimb, 2), round(reimb - cost, 2),
        round((reimb - cost) / max(cost, 1) * 100, 2),
        random.randint(1, 120), random.randint(1, 365),
        random.choice(['Paid', 'Pending', 'Denied', 'Partial']),
    ])
write_csv('FactFinancialSummary.csv', [
    'FinancialKey', 'EncounterKey', 'PayerKey',
    'TotalCharges', 'TotalCost', 'Reimbursement',
    'WriteOff', 'Margin', 'MarginPct',
    'DaysToBill', 'DaysInAR', 'PaymentStatus'
], fin_summary)

# --- FactStaffAssignment ---
write_csv('FactStaffAssignment.csv', ['AssignmentKey', 'EncounterKey', 'StaffKey', 'RoleKey', 'AssignmentDate', 'AssignmentType'],
          [[i, random.randint(1, NUM_ENCOUNTERS), random.randint(1, NUM_PHYSICIANS),
            random.randint(1, len(roles)), random_date(START_DATE, END_DATE).strftime('%Y-%m-%d'),
            random.choice(['Primary', 'Consulting', 'On-Call', 'Covering'])]
           for i in range(1, 8001)])

# --- Summary ---
tables = [
    'DimPatient', 'DimPhysician', 'DimDepartment', 'DimDiagnosis', 'DimPayer',
    'DimFacility', 'DimNursingUnit', 'DimProcedure', 'DimMedication', 'DimLabTest',
    'DimCareTeam', 'DimSupplier', 'DimEquipment', 'CalendarDate', 'DimAdmissionSource',
    'DimDischargeDisposition', 'DimRoomBed', 'DimInsurancePlan', 'DimStaffRole',
    'DimQualityMeasure', 'DimBudgetAccount', 'DimCostCenter', 'DimGeography', 'DimTimeOfDay',
    'FactEncounters', 'FactProcedures', 'FactMedications', 'FactLabResults',
    'FactQualityEvents', 'FactSupplyUsage', 'FactEquipmentUsage',
    'FactFinancialSummary', 'FactStaffAssignment',
]
print(f'\nTotal tables: {len(tables)}')
print('Done!')
