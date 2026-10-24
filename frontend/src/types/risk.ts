export type RiskLevel = 'critical' | 'high' | 'medium' | 'low';

export interface RiskDemandRecord {
  sku: string;
  productName: string;
  destination: string;
  horizonDays: number;
  forecastDemand: number;
  currentEligibleStock: number;
  confirmedReceipts: number;
  stockCoverDays: number;
  replenishmentGap: number;
  riskLevel: RiskLevel;
  primaryRiskFactor: string;
}
