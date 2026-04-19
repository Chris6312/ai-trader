import { apiClient } from './client'

export interface MLTransparencyModelRecord {
  bundle_version: string
  bundle_name: string
  model_version: string
  model_family: string
  dataset_version: string
  strategy_name: string
  label_key: string
  feature_count: number
  manifest_path: string
  created_at: string | null
  validation_version: string | null
  drift_report_version: string | null
  scoring_version: string | null
  verified_artifact: boolean
}

export interface MLTransparencyFeatureRecord {
  feature_key: string
  tree_importance: number | null
  permutation_importance: number | null
  standardized_mean_shift: number | null
  population_stability_index: number | null
  drift_flagged: boolean
  direction: string | null
  contribution: number | null
  feature_value: number | null
  baseline_value: number | null
}

export interface MLTransparencyRowReference {
  row_key: string
  symbol: string
  asset_class: string
  timeframe: string
  decision_date: string
  entry_candle_time: string
  strategy_name: string
}

export interface MLTransparencyOverview {
  model: MLTransparencyModelRecord
  lineage: Record<string, unknown>
  training_metrics: Record<string, number>
  global_feature_importance: MLTransparencyFeatureRecord[]
  regime_feature_importance: MLTransparencyFeatureRecord[]
  drift_signals: MLTransparencyFeatureRecord[]
  health: Record<string, unknown>
  sample_rows: MLTransparencyRowReference[]
}



export interface MLTransparencyStrategyLearningPanel {
  bundle_version: string
  model_version: string
  dataset_version: string
  strategy_name: string
  runtime_control: MLRuntimeControlSummary | null
  summary: Record<string, unknown>
  global_feature_importance: MLTransparencyFeatureRecord[]
  regime_feature_importance: MLTransparencyFeatureRecord[]
  drift_signals: MLTransparencyFeatureRecord[]
  highlighted_rows: MLTransparencyRowReference[]
}

export interface MLTransparencyFeatureHealthPanel {
  bundle_version: string
  model_version: string
  dataset_version: string
  strategy_name: string
  runtime_control: MLRuntimeControlSummary | null
  validation_summary: Record<string, unknown>
  drift_summary: Record<string, unknown>
  global_feature_leaders: MLTransparencyFeatureRecord[]
  regime_feature_leaders: MLTransparencyFeatureRecord[]
  overlapping_feature_keys: string[]
}

export interface MLTransparencyExplanation {
  bundle_version: string
  model_version: string
  dataset_version: string
  strategy_name: string
  row: MLTransparencyRowReference
  score: number | null
  probability: number | null
  confidence: number | null
  baseline_expectation: Record<string, number>
  positive_contributors: MLTransparencyFeatureRecord[]
  negative_contributors: MLTransparencyFeatureRecord[]
  feature_snapshot: Record<string, unknown>
  skipped_reason: string | null
}

export async function fetchMlModelRegistry(): Promise<MLTransparencyModelRecord[]> {
  const response = await apiClient.get<{ rows: MLTransparencyModelRecord[] }>('/api/ai/ml/models')
  return response.data.rows
}

export async function fetchMlOverview(bundleVersion: string): Promise<MLTransparencyOverview> {
  const response = await apiClient.get<MLTransparencyOverview>('/api/ai/ml/overview', {
    params: { bundle_version: bundleVersion },
  })
  return response.data
}

export async function fetchMlRows(bundleVersion: string): Promise<MLTransparencyRowReference[]> {
  const response = await apiClient.get<{ rows: MLTransparencyRowReference[] }>('/api/ai/ml/rows', {
    params: { bundle_version: bundleVersion, limit: 25 },
  })
  return response.data.rows
}

export async function fetchMlExplanation(
  bundleVersion: string,
  rowKey: string,
): Promise<MLTransparencyExplanation> {
  const response = await apiClient.get<MLTransparencyExplanation>('/api/ai/ml/explanations/historical', {
    params: { bundle_version: bundleVersion, row_key: rowKey },
  })
  return response.data
}


export interface MLRuntimeControlSummary {
  bundle_version: string
  strategy_name: string
  requested_mode: string
  effective_mode: string
  ranking_policy: string
  ml_scoring_allowed: boolean
  ml_influence_allowed: boolean
  deterministic_fallback_active: boolean
  verified_artifact: boolean
  validation_reference_present: boolean
  bundle_age_days: number | null
  stale_after_days: number | null
  validation_metric_key: string | null
  validation_metric_value: number | null
  evaluated_at: string | null
  reason_codes: string[]
  missing_feature_keys: string[]
  metadata: Record<string, unknown>
}

export async function fetchMlRuntimeControl(
  bundleVersion: string,
  strategyName: string,
  requestedMode: string,
): Promise<MLRuntimeControlSummary> {
  const response = await apiClient.get<MLRuntimeControlSummary>('/api/ai/ml/runtime', {
    params: {
      bundle_version: bundleVersion,
      strategy_name: strategyName,
      requested_mode: requestedMode,
    },
  })
  return response.data
}


export async function fetchMlStrategyLearningPanel(
  bundleVersion: string,
  requestedMode: string,
): Promise<MLTransparencyStrategyLearningPanel> {
  const response = await apiClient.get<MLTransparencyStrategyLearningPanel>('/api/ai/ml/inspection/strategy', {
    params: { bundle_version: bundleVersion, requested_mode: requestedMode },
  })
  return response.data
}

export async function fetchMlExplanationBySymbolDate(
  bundleVersion: string,
  symbol: string,
  decisionDate: string,
): Promise<MLTransparencyExplanation> {
  const response = await apiClient.get<MLTransparencyExplanation>('/api/ai/ml/explanations/by-symbol-date', {
    params: { bundle_version: bundleVersion, symbol, decision_date: decisionDate },
  })
  return response.data
}


export async function fetchMlFeatureHealthPanel(
  bundleVersion: string,
  requestedMode: string,
): Promise<MLTransparencyFeatureHealthPanel> {
  const response = await apiClient.get<MLTransparencyFeatureHealthPanel>('/api/ai/ml/inspection/feature-health', {
    params: { bundle_version: bundleVersion, requested_mode: requestedMode },
  })
  return response.data
}
