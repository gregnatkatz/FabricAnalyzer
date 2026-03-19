// Domain inference vocabulary — used by Domain Intelligence Agent
export const DOMAIN_SIGNALS = {
  CLINICAL_INPATIENT: ['encounter', 'admission', 'drg', 'los', 'discharge', 'physician', 'readmission'],
  CLINICAL_QUALITY: ['sepsis', 'bundle', 'compliance', 'antibiotic', 'lactate', 'mortality'],
  REVENUE_CYCLE: ['claim', 'denial', 'payer', 'ar', 'collection', 'billing', 'charge'],
  WORKFORCE: ['staffing', 'hppd', 'nursing', 'agency', 'overtime', 'vacancy', 'shift'],
  SUPPLY_CHAIN: ['inventory', 'vendor', 'purchase', 'contract', 'par', 'supply', 'spend'],
  PATIENT_EXPERIENCE: ['hcahps', 'ganey', 'satisfaction', 'rounding', 'complaint', 'survey'],
  OPERATIONAL: ['throughput', 'capacity', 'utilization', 'wait', 'flow', 'bed', 'turnaround'],
  FINANCIAL: ['budget', 'variance', 'margin', 'cost', 'revenue', 'drg', 'contribution'],
};

export const DOMAIN_LABELS = {
  CLINICAL_INPATIENT: 'Clinical Inpatient',
  CLINICAL_QUALITY: 'Clinical Quality',
  REVENUE_CYCLE: 'Revenue Cycle',
  WORKFORCE: 'Workforce',
  SUPPLY_CHAIN: 'Supply Chain',
  PATIENT_EXPERIENCE: 'Patient Experience',
  OPERATIONAL: 'Operational',
  FINANCIAL: 'Financial',
};
