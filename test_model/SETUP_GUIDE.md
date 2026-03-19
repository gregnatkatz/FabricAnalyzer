# LOS Test Model — Fabric Deployment Guide

This test model is **intentionally designed with every latency anti-pattern** to push Fabric Data Agent response times above 40 seconds. Use it to validate the Fabric Data Agent Latency Analyzer's detection capabilities against a real Fabric instance.

## Embedded Anti-Patterns (Why Latency Will Be >40s)

| # | Anti-Pattern | Impact | Severity |
|---|-------------|--------|----------|
| 1 | **33 tables** (optimal: 8-15) | Schema scope bloat forces LLM to reason over massive context | CRITICAL |
| 2 | **9,697-char instructions** (limit: 4,800) | Exceeds instruction character limit by 2x | CRITICAL |
| 3 | **Zero verified answers** | Every query requires full DAX generation from scratch | CRITICAL |
| 4 | **Snowflake schema with 5-deep chains** | FactEncounters→DimDepartment→DimCostCenter→DimBudgetAccount | HIGH |
| 5 | **Duplicate financial data** | FactEncounters AND FactFinancialSummary both contain charges/cost/reimbursement | HIGH |
| 6 | **9 fact tables** (optimal: 1-2) | Multiple fact tables with unclear grain documentation | HIGH |
| 7 | **No table descriptions** on any table | Agent cannot determine table purpose without scanning all columns | HIGH |
| 8 | **Wide tables** — DimPatient has 33 columns | Column disambiguation overhead | MEDIUM |
| 9 | **Ambiguous measure names** | "Rate" vs "Ratio" vs "Pct" vs "Index" used interchangeably | MEDIUM |
| 10 | **No TOPN routing hints** | Ranking queries generate suboptimal DAX | MEDIUM |
| 11 | **Redundant dimensions** | DimPayer AND DimInsurancePlan, DimStaffRole AND DimPhysician roles | MEDIUM |
| 12 | **No V-Order / column sorting** | Import mode performance degradation | LOW |

## Prerequisites

- Microsoft Fabric workspace (any capacity: F2+ or Trial)
- Workspace admin permissions
- A Lakehouse in the workspace

## Step-by-Step Deployment

### Step 1: Create a Lakehouse

1. Open your Fabric workspace
2. Click **+ New** → **Lakehouse**
3. Name it: `LOS_Test_Lakehouse`

### Step 2: Upload CSV Files

1. Open the Lakehouse
2. Click **Get data** → **Upload files**
3. Upload ALL 33 CSV files from the `test_model/data/` directory
4. Wait for all files to appear in the Files section

### Step 3: Create Delta Tables

For each CSV file, right-click → **Load to Tables** → **New table**. Use matching table names:

**Dimension Tables (24):**
- DimPatient, DimPhysician, DimDepartment, DimDiagnosis, DimPayer
- DimFacility, DimNursingUnit, DimProcedure, DimMedication, DimLabTest
- DimCareTeam, DimSupplier, DimEquipment, CalendarDate
- DimAdmissionSource, DimDischargeDisposition, DimRoomBed
- DimInsurancePlan, DimStaffRole, DimQualityMeasure
- DimBudgetAccount, DimCostCenter, DimGeography, DimTimeOfDay

**Fact Tables (9):**
- FactEncounters, FactProcedures, FactMedications, FactLabResults
- FactQualityEvents, FactSupplyUsage, FactEquipmentUsage
- FactFinancialSummary, FactStaffAssignment

### Step 4: Create a Semantic Model (Default)

1. In the Lakehouse, the default semantic model is auto-created
2. Open the semantic model → **Open data model**
3. Verify all 33 tables are present

### Step 5: Create Relationships

Create the following relationships in the semantic model editor:

```
FactEncounters.PatientKey → DimPatient.PatientKey
FactEncounters.AttendingPhysicianKey → DimPhysician.PhysicianKey
FactEncounters.DepartmentKey → DimDepartment.DepartmentKey
FactEncounters.PrimaryDiagnosisKey → DimDiagnosis.DiagnosisKey
FactEncounters.PayerKey → DimPayer.PayerKey
FactEncounters.FacilityKey → DimFacility.FacilityKey
FactEncounters.AdmissionSourceKey → DimAdmissionSource.AdmissionSourceKey
FactEncounters.DischargeDispositionKey → DimDischargeDisposition.DispositionKey
FactEncounters.NursingUnitKey → DimNursingUnit.NursingUnitKey
FactEncounters.CareTeamKey → DimCareTeam.CareTeamKey
FactEncounters.RoomBedKey → DimRoomBed.RoomBedKey
FactEncounters.DateKey → CalendarDate.DateKey

FactProcedures.EncounterKey → FactEncounters.EncounterKey
FactProcedures.ProcedureKey → DimProcedure.ProcedureKey
FactProcedures.SurgeonKey → DimPhysician.PhysicianKey  (INACTIVE - duplicate path!)

FactMedications.EncounterKey → FactEncounters.EncounterKey
FactMedications.MedicationKey → DimMedication.MedicationKey

FactLabResults.EncounterKey → FactEncounters.EncounterKey
FactLabResults.LabTestKey → DimLabTest.LabTestKey

FactQualityEvents.EncounterKey → FactEncounters.EncounterKey
FactQualityEvents.QualityMeasureKey → DimQualityMeasure.QualityMeasureKey

FactSupplyUsage.EncounterKey → FactEncounters.EncounterKey
FactSupplyUsage.SupplierKey → DimSupplier.SupplierKey

FactEquipmentUsage.EncounterKey → FactEncounters.EncounterKey
FactEquipmentUsage.EquipmentKey → DimEquipment.EquipmentKey

FactFinancialSummary.EncounterKey → FactEncounters.EncounterKey
FactFinancialSummary.PayerKey → DimPayer.PayerKey  (BI-DIRECTIONAL cross-filter!)

FactStaffAssignment.EncounterKey → FactEncounters.EncounterKey
FactStaffAssignment.StaffKey → DimPhysician.PhysicianKey  (INACTIVE - duplicate path!)
FactStaffAssignment.RoleKey → DimStaffRole.RoleKey

DimNursingUnit.DepartmentKey → DimDepartment.DepartmentKey  (BI-DIRECTIONAL!)
DimCostCenter.DepartmentKey → DimDepartment.DepartmentKey
DimCareTeam.LeadPhysicianKey → DimPhysician.PhysicianKey  (INACTIVE - duplicate path!)
DimInsurancePlan.PayerKey → DimPayer.PayerKey  (BI-DIRECTIONAL!)
DimEquipment.DepartmentKey → DimDepartment.DepartmentKey
DimRoomBed.NursingUnitKey → DimNursingUnit.NursingUnitKey
```

**Intentional issues to create:**
- Mark 3 relationships as BI-DIRECTIONAL (noted above)
- Mark 3 relationships as INACTIVE (duplicate paths to DimPhysician)

### Step 6: Create DAX Measures

Add these measures to FactEncounters (intentionally includes duplicates and ambiguous names):

```dax
Average LOS = AVERAGE(FactEncounters[LOS_Days])
Total LOS = SUM(FactEncounters[LOS_Days])
Sum of LOS = SUM(FactEncounters[LOS_Days])
LOS Total = SUM(FactEncounters[LOS_Days])
Avg Length of Stay = AVERAGE(FactEncounters[LOS_Days])

Total Encounters = COUNTROWS(FactEncounters)
Encounter Count = COUNTROWS(FactEncounters)
Patient Count = DISTINCTCOUNT(FactEncounters[PatientKey])
Total Patients = DISTINCTCOUNT(FactEncounters[PatientKey])

Readmission Rate = DIVIDE(SUM(FactEncounters[IsReadmission]), COUNTROWS(FactEncounters))
Readmission Ratio = DIVIDE(SUM(FactEncounters[IsReadmission]), COUNTROWS(FactEncounters))
Readmission Pct = DIVIDE(SUM(FactEncounters[IsReadmission]), COUNTROWS(FactEncounters)) * 100

Mortality Rate = DIVIDE(SUM(FactEncounters[ExpiredFlag]), COUNTROWS(FactEncounters))
Mortality Ratio = DIVIDE(SUM(FactEncounters[ExpiredFlag]), COUNTROWS(FactEncounters))

ICU Rate = DIVIDE(SUM(FactEncounters[ICU_Flag]), COUNTROWS(FactEncounters))
Surgical Rate = DIVIDE(SUM(FactEncounters[SurgicalFlag]), COUNTROWS(FactEncounters))

Total Charges = SUM(FactEncounters[TotalCharges])
Total Cost = SUM(FactEncounters[TotalCost])
Total Reimbursement = SUM(FactEncounters[Reimbursement])
Total Revenue = SUM(FactEncounters[Reimbursement])

Avg Charges = AVERAGE(FactEncounters[TotalCharges])
Avg Cost = AVERAGE(FactEncounters[TotalCost])
Avg Satisfaction = AVERAGE(FactEncounters[PatientSatisfactionScore])
Avg CMI = AVERAGE(FactEncounters[CaseMixIndex])
Avg Acuity = AVERAGE(FactEncounters[Acuity])

Margin = SUM(FactEncounters[Reimbursement]) - SUM(FactEncounters[TotalCost])
Margin Pct = DIVIDE(SUM(FactEncounters[Reimbursement]) - SUM(FactEncounters[TotalCost]), SUM(FactEncounters[TotalCost]))
Profit Margin = DIVIDE(SUM(FactEncounters[Reimbursement]) - SUM(FactEncounters[TotalCost]), SUM(FactEncounters[TotalCost]))

ED Hours Before Admit = AVERAGE(FactEncounters[EDHoursBeforeAdmit])
ICU Days = SUM(FactEncounters[ICU_Days])
Avg ICU Days = AVERAGE(FactEncounters[ICU_Days])
Total Procedures = SUM(FactEncounters[ProcedureCount])
Avg Procedures = AVERAGE(FactEncounters[ProcedureCount])
Total Medications = SUM(FactEncounters[MedicationCount])

LOS Variance = AVERAGE(FactEncounters[LOS_Days]) - AVERAGE(DimDiagnosis[ExpectedLOS])

YTD Encounters = TOTALYTD(COUNTROWS(FactEncounters), CalendarDate[DateKey])
YTD Charges = TOTALYTD(SUM(FactEncounters[TotalCharges]), CalendarDate[DateKey])
MTD Encounters = TOTALMTD(COUNTROWS(FactEncounters), CalendarDate[DateKey])

Prev Month LOS = CALCULATE(AVERAGE(FactEncounters[LOS_Days]), DATEADD(CalendarDate[DateKey], -1, MONTH))
LOS MoM Change = AVERAGE(FactEncounters[LOS_Days]) - CALCULATE(AVERAGE(FactEncounters[LOS_Days]), DATEADD(CalendarDate[DateKey], -1, MONTH))

Supply Cost = SUM(FactSupplyUsage[Cost])
Equipment Hours = SUM(FactEquipmentUsage[HoursUsed])
Lab TAT = AVERAGE(FactLabResults[TurnaroundMinutes])
Med Cost = SUM(FactMedications[TotalMedCost])
Procedure Duration = SUM(FactProcedures[DurationMinutes])
Procedure Charges = SUM(FactProcedures[Charges])

Quality Score = AVERAGE(FactQualityEvents[Score])
Quality Met Rate = DIVIDE(COUNTROWS(FILTER(FactQualityEvents, FactQualityEvents[Outcome] = "Met")), COUNTROWS(FactQualityEvents))

Financial Margin = SUM(FactFinancialSummary[Margin])
Days in AR = AVERAGE(FactFinancialSummary[DaysInAR])
Days to Bill = AVERAGE(FactFinancialSummary[DaysToBill])
WriteOff Total = SUM(FactFinancialSummary[WriteOff])
```

That gives **50+ measures** — many are intentional duplicates with slightly different names.

### Step 7: Create a Data Agent

1. In your workspace, click **+ New** → **Data Agent** (preview)
2. Name it: `LOS Clinical Analytics Agent`
3. Add the semantic model as a data source
4. Paste the contents of `agent_instructions.txt` into the Instructions field
5. **Do NOT add any verified answers** (intentional)
6. Save and publish

### Step 8: Test with the Analyzer

1. Start the Fabric Data Agent Latency Analyzer
2. Connect via OAuth to your Fabric workspace
3. Select the `LOS Clinical Analytics Agent`
4. Run the analysis — expect 40s+ average latency
5. Review detected issues — the analyzer should flag ALL embedded anti-patterns

## Expected Analyzer Findings

The analyzer should detect at minimum:

- CRITICAL: Instruction length exceeds 4800 chars (9,697 chars)
- CRITICAL: Table count exceeds recommended maximum (33 tables)
- CRITICAL: No verified answers configured
- HIGH: Multiple fact tables detected (9 fact tables)
- HIGH: Snowflake schema depth >3 levels
- HIGH: Bi-directional cross-filters on 3 relationships
- HIGH: Duplicate measures detected (Total LOS / Sum of LOS / LOS Total)
- MEDIUM: Ambiguous measure naming (Rate vs Ratio vs Pct)
- MEDIUM: No table descriptions
- MEDIUM: Wide table detected (DimPatient: 33 columns)
- MEDIUM: Inactive relationships present
- MEDIUM: Redundant dimension tables (DimPayer + DimInsurancePlan)
- LOW: No V-Order configuration

## Data Summary

| Table | Rows | Columns | Type |
|-------|------|---------|------|
| DimPatient | 3,000 | 33 | Dimension (Wide) |
| DimPhysician | 100 | 13 | Dimension |
| DimDepartment | 25 | 9 | Dimension |
| DimDiagnosis | 200 | 8 | Dimension |
| DimPayer | 30 | 7 | Dimension |
| DimFacility | 8 | 7 | Dimension |
| DimNursingUnit | 40 | 7 | Dimension |
| DimProcedure | 150 | 7 | Dimension |
| DimMedication | 200 | 8 | Dimension |
| DimLabTest | 80 | 6 | Dimension |
| DimCareTeam | 30 | 5 | Dimension |
| DimSupplier | 40 | 5 | Dimension |
| DimEquipment | 60 | 6 | Dimension |
| CalendarDate | 1,096 | 11 | Dimension |
| DimAdmissionSource | 10 | 3 | Dimension |
| DimDischargeDisposition | 10 | 3 | Dimension |
| DimRoomBed | 200 | 6 | Dimension |
| DimInsurancePlan | 50 | 7 | Dimension (Redundant) |
| DimStaffRole | 15 | 3 | Dimension |
| DimQualityMeasure | 15 | 5 | Dimension |
| DimBudgetAccount | 50 | 5 | Snowflake |
| DimCostCenter | 30 | 5 | Snowflake |
| DimGeography | 20 | 5 | Snowflake |
| DimTimeOfDay | 48 | 5 | Snowflake |
| FactEncounters | 10,000 | 31 | Fact (Main) |
| FactProcedures | ~12,000 | 8 | Fact (Bridge) |
| FactMedications | ~24,000 | 8 | Fact (Bridge) |
| FactLabResults | ~17,000 | 8 | Fact (Bridge) |
| FactQualityEvents | 3,000 | 7 | Fact |
| FactSupplyUsage | 5,000 | 7 | Fact |
| FactEquipmentUsage | 3,000 | 6 | Fact |
| FactFinancialSummary | 10,000 | 12 | Fact (Redundant) |
| FactStaffAssignment | 8,000 | 6 | Fact (Bridge) |
