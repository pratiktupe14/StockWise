export interface OptimizationPlanParams {
  snapshotId: string;
  horizonDays: number;
  priorityWeights: 'service-first' | 'balanced' | 'cost-weighted';
  allowCrossRegionRoutes: boolean;
  minServiceLevelPercent: number;
}

export interface PlanComparisonMetrics {
  planId: string;
  name: string;
  isBaseline: boolean;
  serviceLevelPercent: number;
  fulfilledDemandUnits: number;
  unmetDemandUnits: number;
  estimatedTransportCost: number;
  stockUtilizationPercent: number;
  constraintViolationsCount: number;
  solveTimeSeconds: number;
}

export interface DecisionReceipt {
  recommendationId: string;
  sku: string;
  source: string;
  destination: string;
  quantity: number;
  unit: string;
  estimatedCost: number;
  leadTimeDays: number;
  estimatedArrivalDate: string;
  evidence: string;
  rejectedAlternatives: string[];
}
