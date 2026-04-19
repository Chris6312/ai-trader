import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, CircleGauge, FlaskConical } from 'lucide-react'

import {
  fetchMlExplanation,
  fetchMlExplanationBySymbolDate,
  fetchMlFeatureHealthPanel,
  fetchMlModelRegistry,
  fetchMlOverview,
  fetchMlRows,
  fetchMlRuntimeControl,
  fetchMlStrategyLearningPanel,
} from '../api/mlTransparency'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { SummaryCard } from '../components/SummaryCard'
import { formatTimestamp } from '../lib/formatters'

type ModelRegistryRow = Awaited<ReturnType<typeof fetchMlModelRegistry>>[number]
type MlOverview = Awaited<ReturnType<typeof fetchMlOverview>>
type MlRow = Awaited<ReturnType<typeof fetchMlRows>>[number]
type MlExplanation = Awaited<ReturnType<typeof fetchMlExplanation>>
type MlRuntimeControl = Awaited<ReturnType<typeof fetchMlRuntimeControl>>
type MlStrategyLearningPanel = Awaited<ReturnType<typeof fetchMlStrategyLearningPanel>>
type MlFeatureHealthPanel = Awaited<ReturnType<typeof fetchMlFeatureHealthPanel>>

type FeatureRecord = {
  feature_key: string
  contribution?: unknown
  permutation_importance?: unknown
  tree_importance?: unknown
  standardized_mean_shift?: unknown
  population_stability_index?: unknown
  drift_flagged?: boolean
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asString(value: unknown, fallback = '—'): string {
  return typeof value === 'string' && value.trim().length > 0 ? value : fallback
}

function formatMetric(value: unknown, digits = 3): string {
  const numericValue = asNumber(value)
  if (numericValue === null) {
    return '—'
  }
  return numericValue.toFixed(digits)
}

function formatCount(value: unknown): string {
  const numericValue = asNumber(value)
  if (numericValue === null) {
    return '—'
  }
  return String(numericValue)
}

function humanizeToken(value: unknown, fallback = '—'): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    return fallback
  }

  return value
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function humanizeMetricKey(value: unknown): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    return '—'
  }

  const normalized = value.trim().toLowerCase()

  if (normalized === 'roc_auc') return 'ROC AUC'
  if (normalized === 'ps i') return 'PSI'
  if (normalized === 'psi') return 'PSI'

  return humanizeToken(value)
}

function formatRowOptionLabel(row: Pick<MlRow, 'row_key' | 'symbol' | 'decision_date'>): string {
  const symbol = asString(row.symbol, 'Unknown symbol')
  const decisionDate = asString(row.decision_date, 'Unknown date')
  const shortRowKey = typeof row.row_key === 'string' && row.row_key ? row.row_key.slice(0, 12) : 'unknown-row'
  return `${symbol} · ${decisionDate} · ${shortRowKey}`
}



function formatHistoricalRowButtonLabel(row: MlRow | null): string {
  if (!row) {
    return 'No historical rows available'
  }
  return formatRowOptionLabel(row)
}

function statusToneClass(value: string): string {
  if (
    value === 'guardrails_clear' ||
    value === 'active_rank_only' ||
    value === 'Ready' ||
    value === 'Verified'
  ) {
    return 'status-pill--good'
  }
  if (value === 'blocked' || value === 'Missing' || value === 'Check artifact') {
    return 'status-pill--warn'
  }
  return ''
}

function FeatureListCard({
  eyebrow,
  title,
  emptyLabel,
  rows,
}: {
  eyebrow: string
  title: string
  emptyLabel: string
  rows: FeatureRecord[]
}) {
  return (
    <article className="list-card min-w-0 overflow-hidden">
      <div className="list-card__header gap-3">
        <div className="min-w-0">
          <p className="eyebrow">{eyebrow}</p>
          <h3 className="break-words">{title}</h3>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="muted break-words">{emptyLabel}</p>
      ) : (
        <div className="stack-list stack-list--tight min-w-0">
          {rows.map((item) => {
            const contribution = asNumber(item.contribution)
            const permutationImportance = asNumber(item.permutation_importance)
            const treeImportance = asNumber(item.tree_importance)
            const standardizedMeanShift = asNumber(item.standardized_mean_shift)
            const psi = asNumber(item.population_stability_index)

            return (
              <div key={item.feature_key} className="metric-row metric-row--feature min-w-0 flex-wrap gap-3">
                <div className="min-w-0 flex-1">
                  <span className="metric-row__label break-all">{humanizeMetricKey(item.feature_key)}</span>
                  <strong className="block break-words">
                    {contribution !== null
                      ? `Contribution ${contribution.toFixed(3)}`
                      : permutationImportance !== null
                        ? `Permutation ${permutationImportance.toFixed(3)}`
                        : 'No scored contribution attached'}
                  </strong>
                </div>

                <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                  {treeImportance !== null ? (
                    <span className="status-pill">Tree {treeImportance.toFixed(3)}</span>
                  ) : null}
                  {standardizedMeanShift !== null ? (
                    <span className="status-pill">Shift {standardizedMeanShift.toFixed(3)}</span>
                  ) : null}
                  {psi !== null ? <span className="status-pill">PSI {psi.toFixed(3)}</span> : null}
                  {item.drift_flagged ? <span className="status-pill status-pill--warn">Drift</span> : null}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </article>
  )
}

export function MlTransparencyPage() {
  const [selectedBundleVersion, setSelectedBundleVersion] = useState('')
  const [selectedRowKey, setSelectedRowKey] = useState('')
  const [requestedRuntimeMode, setRequestedRuntimeMode] = useState('active_rank_only')
  const [isHistoricalRowMenuOpen, setIsHistoricalRowMenuOpen] = useState(false)
  const historicalRowMenuRef = useRef<HTMLDivElement | null>(null)

  const registryQuery = useQuery({
    queryKey: ['ml-model-registry'],
    queryFn: fetchMlModelRegistry,
    refetchInterval: 30_000,
  })

  const modelRows = (registryQuery.data ?? []) as ModelRegistryRow[]

  useEffect(() => {
    if (modelRows.length === 0) {
      if (selectedBundleVersion) {
        setSelectedBundleVersion('')
      }
      return
    }

    const selectedStillExists = modelRows.some((item) => item.bundle_version === selectedBundleVersion)
    if (!selectedBundleVersion || !selectedStillExists) {
      setSelectedBundleVersion(modelRows[0].bundle_version)
      setSelectedRowKey('')
    }
  }, [modelRows, selectedBundleVersion])

  const selectedModel = useMemo<ModelRegistryRow | null>(() => {
    if (modelRows.length === 0) {
      return null
    }
    return modelRows.find((item) => item.bundle_version === selectedBundleVersion) ?? modelRows[0]
  }, [modelRows, selectedBundleVersion])

  const overviewQuery = useQuery({
    queryKey: ['ml-overview', selectedBundleVersion],
    queryFn: () => fetchMlOverview(selectedBundleVersion),
    enabled: Boolean(selectedBundleVersion),
  })

  const rowsQuery = useQuery({
    queryKey: ['ml-rows', selectedBundleVersion],
    queryFn: () => fetchMlRows(selectedBundleVersion),
    enabled: Boolean(selectedBundleVersion),
  })

  const availableRows = (rowsQuery.data ?? []) as MlRow[]

  useEffect(() => {
    if (availableRows.length === 0) {
      if (selectedRowKey) {
        setSelectedRowKey('')
      }
      return
    }

    const hasSelectedRow = availableRows.some((item) => item.row_key === selectedRowKey)
    if (!selectedRowKey || !hasSelectedRow) {
      setSelectedRowKey(availableRows[0].row_key)
    }
  }, [availableRows, selectedRowKey])

  const selectedRow = useMemo<MlRow | null>(() => {
    if (availableRows.length === 0) {
      return null
    }
    return availableRows.find((item) => item.row_key === selectedRowKey) ?? availableRows[0]
  }, [availableRows, selectedRowKey])

  useEffect(() => {
    if (!isHistoricalRowMenuOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!historicalRowMenuRef.current?.contains(event.target as Node)) {
        setIsHistoricalRowMenuOpen(false)
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsHistoricalRowMenuOpen(false)
      }
    }

    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('keydown', handleEscape)

    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('keydown', handleEscape)
    }
  }, [isHistoricalRowMenuOpen])

  useEffect(() => {
    setIsHistoricalRowMenuOpen(false)
  }, [selectedBundleVersion, selectedRowKey])

  const explanationQuery = useQuery({
    queryKey: ['ml-explanation', selectedBundleVersion, selectedRowKey],
    queryFn: () => fetchMlExplanation(selectedBundleVersion, selectedRowKey),
    enabled: Boolean(selectedBundleVersion && selectedRowKey),
  })

  const explanationBySymbolQuery = useQuery({
    queryKey: ['ml-explanation-by-symbol-date', selectedBundleVersion, selectedRow?.symbol, selectedRow?.decision_date],
    queryFn: () =>
      fetchMlExplanationBySymbolDate(
        selectedBundleVersion,
        selectedRow?.symbol ?? '',
        selectedRow?.decision_date ?? '',
      ),
    enabled: Boolean(selectedBundleVersion && selectedRow?.symbol && selectedRow?.decision_date),
  })

  const runtimeQuery = useQuery({
    queryKey: ['ml-runtime-control', selectedBundleVersion, selectedModel?.strategy_name, requestedRuntimeMode],
    queryFn: () => fetchMlRuntimeControl(selectedBundleVersion, selectedModel?.strategy_name ?? '', requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion && selectedModel?.strategy_name),
  })

  const strategyPanelQuery = useQuery({
    queryKey: ['ml-strategy-learning-panel', selectedBundleVersion, requestedRuntimeMode],
    queryFn: () => fetchMlStrategyLearningPanel(selectedBundleVersion, requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion),
  })

  const featureHealthQuery = useQuery({
    queryKey: ['ml-feature-health-panel', selectedBundleVersion, requestedRuntimeMode],
    queryFn: () => fetchMlFeatureHealthPanel(selectedBundleVersion, requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion),
  })

  const overview = (overviewQuery.data ?? null) as MlOverview | null
  const explanation = (explanationQuery.data ?? null) as MlExplanation | null
  const explanationBySymbol = (explanationBySymbolQuery.data ?? null) as MlExplanation | null
  const runtime = (runtimeQuery.data ?? null) as MlRuntimeControl | null
  const strategyPanel = (strategyPanelQuery.data ?? null) as MlStrategyLearningPanel | null
  const featureHealth = (featureHealthQuery.data ?? null) as MlFeatureHealthPanel | null

  const trainingMetrics =
    overview && typeof overview === 'object' && 'training_metrics' in overview
      ? (overview.training_metrics as Record<string, unknown>)
      : {}

  const lineage =
    overview && typeof overview === 'object' && 'lineage' in overview
      ? (overview.lineage as Record<string, unknown>)
      : {}

  const overviewGlobalImportance =
    overview && typeof overview === 'object' && 'global_feature_importance' in overview
      ? ((overview.global_feature_importance as FeatureRecord[]) ?? [])
      : []

  const overviewRegimeImportance =
    overview && typeof overview === 'object' && 'regime_feature_importance' in overview
      ? ((overview.regime_feature_importance as FeatureRecord[]) ?? [])
      : []

  const overviewDriftSignals =
    overview && typeof overview === 'object' && 'drift_signals' in overview
      ? ((overview.drift_signals as FeatureRecord[]) ?? [])
      : []

  const strategySummary =
    strategyPanel && typeof strategyPanel === 'object' && 'summary' in strategyPanel
      ? (strategyPanel.summary as Record<string, unknown>)
      : {}

  const strategyRuntimeControl = strategyPanel?.runtime_control ?? null

  const strategyReasonCodes = Array.isArray(strategyRuntimeControl?.reason_codes)
    ? strategyRuntimeControl.reason_codes.map((item) => String(item))
    : ['guardrails_clear']

  const featureHealthValidationSummary =
    featureHealth && typeof featureHealth === 'object' && 'validation_summary' in featureHealth
      ? (featureHealth.validation_summary as Record<string, unknown>)
      : {}

  const featureHealthDriftSummary =
    featureHealth && typeof featureHealth === 'object' && 'drift_summary' in featureHealth
      ? (featureHealth.drift_summary as Record<string, unknown>)
      : {}

  const featureHealthGlobalLeaders =
    featureHealth && typeof featureHealth === 'object' && 'global_feature_leaders' in featureHealth
      ? ((featureHealth.global_feature_leaders as FeatureRecord[]) ?? [])
      : []

  const featureHealthRegimeLeaders =
    featureHealth && typeof featureHealth === 'object' && 'regime_feature_leaders' in featureHealth
      ? ((featureHealth.regime_feature_leaders as FeatureRecord[]) ?? [])
      : []

  const overlappingFeatureKeys =
    featureHealth && typeof featureHealth === 'object' && 'overlapping_feature_keys' in featureHealth
      ? ((featureHealth.overlapping_feature_keys as string[]) ?? [])
      : []

  const runtimeReasonCodes = Array.isArray(runtime?.reason_codes)
    ? runtime.reason_codes.map((item) => String(item))
    : ['guardrails_clear']

  const artifactStatusValue =
    runtime?.bundle_version === selectedBundleVersion
      ? runtime.verified_artifact
        ? 'Verified'
        : 'Missing'
      : selectedModel?.verified_artifact
        ? 'Verified'
        : 'Missing'

  const artifactStatusDetail =
    runtime?.bundle_version === selectedBundleVersion
      ? `Validation ref: ${selectedModel?.validation_version ?? 'not bundled yet'} · Source: ${String(runtime.metadata?.artifact_source ?? 'unknown')}`
      : `Validation ref: ${selectedModel?.validation_version ?? 'not bundled yet'}`

  return (
    <div className="page-grid overflow-x-hidden">
      <PageSection
        eyebrow="ML transparency"
        title="What the model learned"
        description="This lane turns the model from a black shoebox into a glass terrarium. You can inspect lineage, top features, drift warnings, and a historical row explanation without handing the ML layer the steering wheel."
      >
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="xl:col-span-7 min-w-0">
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 md:gap-8">
                <label className="block min-w-0">
                  <span className="mb-2 block text-sm text-slate-300">Bundle</span>
                  <select
                    value={selectedBundleVersion}
                    onChange={(event) => {
                      setSelectedBundleVersion(event.target.value)
                      setSelectedRowKey('')
                    }}
                    className="block w-full min-w-0 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                  >
                    {modelRows.map((item) => (
                      <option key={item.bundle_version} value={item.bundle_version}>
                        {humanizeToken(item.strategy_name)} · {item.bundle_version}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block min-w-0">
                  <span className="mb-2 block text-sm text-slate-300">Requested mode</span>
                  <select
                    value={requestedRuntimeMode}
                    onChange={(event) => setRequestedRuntimeMode(event.target.value)}
                    className="block w-full min-w-0 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                  >
                    <option value="disabled">Disabled</option>
                    <option value="shadow">Shadow</option>
                    <option value="active_rank_only">Active rank only</option>
                  </select>
                </label>
              </div>

              <QueryState
                isLoading={registryQuery.isLoading}
                isError={registryQuery.isError}
                isEmpty={modelRows.length === 0}
                loadingLabel="Scanning persisted ML bundles…"
                errorLabel="The frontend could not reach the ML transparency registry endpoint."
                emptyLabel="No persisted model bundles yet. Run the 12L bundle step and this page will have something to inspect."
              >
                <div className="summary-grid summary-grid--hero min-w-0">
                  <SummaryCard
                    label="Active bundle"
                    value={selectedModel?.bundle_version ?? '—'}
                    detail={humanizeToken(selectedModel?.strategy_name ?? '', 'No persisted ML bundle selected.')}
                  />
                  <SummaryCard
                    label="Model version"
                    value={selectedModel?.model_version ?? '—'}
                    detail={selectedModel?.model_family ?? 'Awaiting a saved model bundle.'}
                  />
                  <SummaryCard
                    label="Feature count"
                    value={String(selectedModel?.feature_count ?? 0)}
                    detail={`Label key: ${humanizeMetricKey(selectedModel?.label_key ?? '')}`}
                  />
                  <SummaryCard
                    label="Artifact status"
                    value={artifactStatusValue}
                    tone={artifactStatusValue === 'Verified' ? 'good' : 'warn'}
                    detail={artifactStatusDetail}
                  />
                </div>
              </QueryState>
            </div>
          </div>

          <div className="xl:col-span-5 min-w-0">
            <article className="list-card min-w-0 overflow-hidden h-full">
              <div className="list-card__header gap-3">
                <div className="min-w-0">
                  <p className="eyebrow">Runtime guardrails</p>
                  <h3 className="break-words">ML participation cage</h3>
                </div>
                <div className="stack-inline stack-inline--tight min-w-0 flex-wrap">
                  <span className={`status-pill ${statusToneClass(runtime?.effective_mode ?? '')}`}>
                    {humanizeToken(runtime?.effective_mode ?? 'loading')}
                  </span>
                  <span className="status-pill break-all">
                    {humanizeToken(runtime?.ranking_policy ?? 'deterministic_only')}
                  </span>
                </div>
              </div>

              <QueryState
                isLoading={runtimeQuery.isLoading}
                isError={runtimeQuery.isError}
                isEmpty={!runtime}
                loadingLabel="Evaluating runtime guardrails…"
                errorLabel="Runtime control status could not be loaded."
                emptyLabel="Pick a bundle to evaluate runtime guardrails."
              >
                {runtime ? (
                  <div className="stack-list stack-list--tight min-w-0">
                    <div className="summary-grid min-w-0">
                      <SummaryCard label="Requested mode" value={humanizeToken(runtime.requested_mode)} />
                      <SummaryCard label="Effective mode" value={humanizeToken(runtime.effective_mode)} />
                      <SummaryCard
                        label="Bundle age"
                        value={runtime.bundle_age_days !== null ? `${runtime.bundle_age_days}d` : '—'}
                        detail={`Stale after ${runtime.stale_after_days ?? '—'}d`}
                      />
                      <SummaryCard
                        label="Validation"
                        value={runtime.validation_metric_value !== null ? formatMetric(runtime.validation_metric_value) : '—'}
                        detail={humanizeMetricKey(runtime.validation_metric_key ?? 'metric')}
                      />
                    </div>

                    <div className="stack-inline stack-inline--tight min-w-0 flex-wrap">
                      {runtimeReasonCodes.map((item) => (
                        <span key={item} className={`status-pill ${statusToneClass(item)}`}>
                          {humanizeToken(item)}
                        </span>
                      ))}
                    </div>

                    {runtime.missing_feature_keys.length > 0 ? (
                      <p className="muted break-words">
                        Missing features: {runtime.missing_feature_keys.map((item) => humanizeMetricKey(item)).join(', ')}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </QueryState>
            </article>
          </div>
        </div>
      </PageSection>

      <div className="grid gap-6 xl:grid-cols-2">
        <PageSection
          eyebrow="Overview"
          title="Model registry"
          description="Every persisted bundle is a labeled jar. This card keeps the shelf visible so you know which specimen you are poking."
        >
          <QueryState
            isLoading={registryQuery.isLoading}
            isError={registryQuery.isError}
            isEmpty={modelRows.length === 0}
            loadingLabel="Warming up model registry…"
            errorLabel="Model registry data could not be loaded."
            emptyLabel="No bundled models are available yet."
          >
            <div className="stack-list min-w-0">
              {modelRows.map((item) => (
                <button
                  key={item.bundle_version}
                  type="button"
                  className={`list-card list-card--button min-w-0 overflow-hidden ${item.bundle_version === selectedBundleVersion ? 'is-selected' : ''}`}
                  onClick={() => {
                    setSelectedBundleVersion(item.bundle_version)
                    setSelectedRowKey('')
                  }}
                >
                  <div className="list-card__header gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="eyebrow">{humanizeToken(item.strategy_name)}</p>
                      <h3 className="break-all">{item.bundle_version}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                      <span className="status-pill break-all">{item.dataset_version}</span>
                      <span className={`status-pill ${statusToneClass(item.verified_artifact ? 'Ready' : 'Check artifact')}`}>
                        {item.verified_artifact ? 'Ready' : 'Check artifact'}
                      </span>
                    </div>
                  </div>
                  <p className="muted break-words">
                    Model {item.model_version} · Validation {item.validation_version ?? 'pending'}
                  </p>
                </button>
              ))}
            </div>
          </QueryState>
        </PageSection>

        <PageSection
          eyebrow="Health"
          title="Training and validation pulse"
          description="This is the model-health shelf. It is intentionally compact until later phases add calibration curves, bucket returns, and richer validation diagnostics."
        >
          <QueryState
            isLoading={overviewQuery.isLoading}
            isError={overviewQuery.isError}
            isEmpty={!overview}
            loadingLabel="Loading transparency overview…"
            errorLabel="The overview endpoint could not be loaded for this bundle."
            emptyLabel="Pick a persisted bundle to see its health card."
          >
            {overview ? (
              <div className="stack-list min-w-0">
                <article className="list-card min-w-0 overflow-hidden">
                  <div className="list-card__header gap-3">
                    <div className="min-w-0">
                      <p className="eyebrow">Training metrics</p>
                      <h3>Baseline health</h3>
                    </div>
                    <CircleGauge className="icon-badge shrink-0" />
                  </div>
                  <div className="metric-grid metric-grid--three min-w-0">
                    {Object.entries(trainingMetrics).map(([key, value]) => (
                      <div key={key} className="metric-tile min-w-0">
                        <span className="metric-row__label break-all">{humanizeMetricKey(key)}</span>
                        <strong className="break-words">{formatMetric(value)}</strong>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="list-card min-w-0 overflow-hidden">
                  <div className="list-card__header gap-3">
                    <div className="min-w-0">
                      <p className="eyebrow">Lineage</p>
                      <h3>Traceability spine</h3>
                    </div>
                    <FlaskConical className="icon-badge shrink-0" />
                  </div>
                  <div className="metric-grid metric-grid--two min-w-0">
                    {Object.entries(lineage).map(([key, value]) => (
                      <div key={key} className="metric-tile min-w-0">
                        <span className="metric-row__label break-all">{humanizeMetricKey(key)}</span>
                        <strong className="break-words">{humanizeToken(asString(value), asString(value))}</strong>
                      </div>
                    ))}
                  </div>
                </article>
              </div>
            ) : null}
          </QueryState>
        </PageSection>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <PageSection
          eyebrow="Strategy learning"
          title="Bundle learning panel"
          description="A tighter inspection shelf for the selected strategy. It blends bundle context, runtime state, and the model's current learning landmarks into one operator-readable card."
        >
          <QueryState
            isLoading={strategyPanelQuery.isLoading}
            isError={strategyPanelQuery.isError}
            isEmpty={!strategyPanel}
            loadingLabel="Loading strategy learning panel…"
            errorLabel="Strategy learning panel could not be loaded."
            emptyLabel="Pick a persisted bundle to inspect strategy learning."
          >
            {strategyPanel ? (
              <div className="stack-list min-w-0">
                <div className="summary-grid min-w-0">
                  <SummaryCard label="Rows" value={formatCount(strategySummary.rows_total)} />
                  <SummaryCard label="Symbols" value={formatCount(strategySummary.symbols_total)} />
                  <SummaryCard label="Positive label rate" value={formatMetric(strategySummary.positive_label_rate)} />
                  <SummaryCard
                    label="Runtime context"
                    value={humanizeToken(strategySummary.runtime_context)}
                    detail={humanizeToken(strategySummary.ranking_policy)}
                  />
                </div>

                <article className="list-card min-w-0 overflow-hidden">
                  <div className="list-card__header gap-3">
                    <div className="min-w-0">
                      <p className="eyebrow">Top learning anchors</p>
                      <h3 className="break-words">{humanizeToken(strategyPanel.strategy_name)}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                      {strategyReasonCodes.map((item) => (
                        <span key={item} className={`status-pill ${statusToneClass(item)}`}>
                          {humanizeToken(item)}
                        </span>
                      ))}
                    </div>
                  </div>

                  <p className="muted break-words">
                    Window {asString(strategySummary.decision_date_start)} to {asString(strategySummary.decision_date_end)} · Drift flags {formatCount(strategySummary.drift_flagged_feature_count)}
                  </p>
                </article>
              </div>
            ) : null}
          </QueryState>
        </PageSection>

        <PageSection
          eyebrow="Lookup parity"
          title="Symbol/date explanation check"
          description="This mirrors the historical row drawer through the new symbol-plus-date lookup path so the inspect API can work without row keys leaking into every future UI surface."
        >
          <QueryState
            isLoading={explanationBySymbolQuery.isLoading}
            isError={explanationBySymbolQuery.isError}
            isEmpty={!explanationBySymbol}
            loadingLabel="Loading symbol/date explanation…"
            errorLabel="Symbol/date explanation lookup could not be loaded."
            emptyLabel="Pick a historical row to mirror the symbol/date lookup."
          >
            {explanationBySymbol ? (
              <div className="summary-grid min-w-0">
                <SummaryCard label="Symbol" value={explanationBySymbol.row.symbol} />
                <SummaryCard label="Decision date" value={explanationBySymbol.row.decision_date} />
                <SummaryCard label="Probability" value={formatMetric(explanationBySymbol.probability)} />
                <SummaryCard label="Confidence" value={formatMetric(explanationBySymbol.confidence)} />
              </div>
            ) : null}
          </QueryState>
        </PageSection>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-4 min-w-0">
          <PageSection
            eyebrow="Feature health"
            title="Importance and drift heartbeat"
            description="This card condenses validation, drift, and overlap between global and regime-sensitive features into one operator-readable pulse check."
          >
            <QueryState
              isLoading={featureHealthQuery.isLoading}
              isError={featureHealthQuery.isError}
              isEmpty={!featureHealth}
              loadingLabel="Loading feature health panel…"
              errorLabel="Feature health panel could not be loaded."
              emptyLabel="Pick a persisted bundle to inspect feature health."
            >
              {featureHealth ? (
                <div className="summary-grid min-w-0">
                  <SummaryCard
                    label="Validation ref"
                    value={asString(featureHealthValidationSummary.validation_version)}
                  />
                  <SummaryCard
                    label="Runtime context"
                    value={humanizeToken(featureHealthValidationSummary.runtime_context)}
                    detail={humanizeToken(featureHealthValidationSummary.ranking_policy)}
                  />
                  <SummaryCard
                    label="Drift flags"
                    value={formatCount(featureHealthDriftSummary.flagged_feature_count)}
                    detail={`PSI max ${formatMetric(featureHealthDriftSummary.highest_population_stability_index)}`}
                  />
                  <SummaryCard
                    label="Overlap"
                    value={String(overlappingFeatureKeys.length)}
                    detail={overlappingFeatureKeys.map((item) => humanizeMetricKey(item)).join(', ') || 'No overlap'}
                  />
                </div>
              ) : null}
            </QueryState>
          </PageSection>
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureListCard
            eyebrow="Explainability"
            title="Feature leaders"
            emptyLabel="No feature-leader summary is attached to this bundle yet."
            rows={featureHealthGlobalLeaders}
          />
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureListCard
            eyebrow="Explainability"
            title="Regime leaders"
            emptyLabel="No regime-leader summary is attached to this bundle yet."
            rows={featureHealthRegimeLeaders}
          />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-4 min-w-0">
          <FeatureListCard
            eyebrow="Explainability"
            title="Global feature importance"
            emptyLabel="No global feature importance artifact is attached to this bundle yet."
            rows={overviewGlobalImportance}
          />
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureListCard
            eyebrow="Explainability"
            title="Regime-sensitive importance"
            emptyLabel="No regime-specific importance artifact is attached to this bundle yet."
            rows={overviewRegimeImportance}
          />
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureListCard
            eyebrow="Explainability"
            title="Drift signals"
            emptyLabel="No drift artifact is attached to this bundle yet."
            rows={overviewDriftSignals}
          />
        </div>
      </div>

      <PageSection
        eyebrow="Historical explain drawer"
        title="Per-row explanation"
        description="Pick a historical dataset row and inspect the score, probability, and the strongest nudges that pushed the model north or south."
      >
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="xl:col-span-6 min-w-0">
            <div className="space-y-4">
              <div className="min-w-0" ref={historicalRowMenuRef}>
                <span className="mb-2 block text-sm text-slate-300">Historical row</span>

                <div className="relative min-w-0">
                  <button
                    type="button"
                    onClick={() => {
                      if (availableRows.length > 0) {
                        setIsHistoricalRowMenuOpen((current) => !current)
                      }
                    }}
                    disabled={availableRows.length === 0}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-left text-sm text-slate-100 outline-none transition focus:border-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-haspopup="listbox"
                    aria-expanded={isHistoricalRowMenuOpen}
                    title={selectedRow ? formatRowOptionLabel(selectedRow) : 'No historical rows available'}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {formatHistoricalRowButtonLabel(selectedRow)}
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 transition ${isHistoricalRowMenuOpen ? 'rotate-180' : ''}`}
                    />
                  </button>

                  {isHistoricalRowMenuOpen ? (
                    <div className="absolute left-0 right-0 z-20 mt-2 max-h-80 overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-2 shadow-2xl">
                      <div className="space-y-1" role="listbox" aria-label="Historical row options">
                        {availableRows.map((item) => {
                          const isSelected = item.row_key === selectedRowKey
                          return (
                            <button
                              key={item.row_key}
                              type="button"
                              role="option"
                              aria-selected={isSelected}
                              onClick={() => {
                                setSelectedRowKey(item.row_key)
                                setIsHistoricalRowMenuOpen(false)
                              }}
                              className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                                isSelected
                                  ? 'bg-cyan-500/15 text-cyan-200'
                                  : 'text-slate-100 hover:bg-slate-800'
                              }`}
                              title={formatRowOptionLabel(item)}
                            >
                              <span className="block truncate">{formatRowOptionLabel(item)}</span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>

              <QueryState
                isLoading={rowsQuery.isLoading || explanationQuery.isLoading}
                isError={rowsQuery.isError || explanationQuery.isError}
                isEmpty={!explanation}
                loadingLabel="Loading row explanation…"
                errorLabel="The historical explanation endpoint could not be loaded."
                emptyLabel="Select a persisted bundle and row to see the explanation drawer."
              >
                {explanation ? (
                  <div className="stack-list min-w-0">
                    <article className="list-card min-w-0 overflow-hidden">
                      <div className="list-card__header gap-3">
                        <div className="min-w-0">
                          <p className="eyebrow">{explanation.row.symbol}</p>
                          <h3 className="break-all">{explanation.row.row_key}</h3>
                        </div>
                        <div className="stack-inline stack-inline--tight min-w-0 flex-wrap">
                          <span className="status-pill">{humanizeToken(explanation.row.asset_class)}</span>
                          <span className="status-pill">{humanizeToken(explanation.row.timeframe)}</span>
                        </div>
                      </div>

                      <div className="summary-grid min-w-0">
                        <SummaryCard label="Combined score" value={formatMetric(explanation.score)} />
                        <SummaryCard label="Probability" value={formatMetric(explanation.probability)} />
                        <SummaryCard label="Confidence" value={formatMetric(explanation.confidence)} />
                        <SummaryCard
                          label="Decision date"
                          value={explanation.row.decision_date}
                          detail={`Entry candle ${formatTimestamp(explanation.row.entry_candle_time)}`}
                        />
                      </div>
                    </article>

                    {explanation.skipped_reason ? (
                      <article className="list-card min-w-0 overflow-hidden">
                        <p className="muted break-words">
                          Scoring was skipped: {humanizeToken(explanation.skipped_reason, asString(explanation.skipped_reason))}
                        </p>
                      </article>
                    ) : null}
                  </div>
                ) : null}
              </QueryState>
            </div>
          </div>

          <div className="xl:col-span-6 min-w-0">
            <div className="grid gap-6">
              <FeatureListCard
                eyebrow="Contributors"
                title="Top positive contributors"
                emptyLabel="No positive contributors were available for this row."
                rows={(explanation?.positive_contributors ?? []) as FeatureRecord[]}
              />

              <FeatureListCard
                eyebrow="Contributors"
                title="Top negative contributors"
                emptyLabel="No negative contributors were available for this row."
                rows={(explanation?.negative_contributors ?? []) as FeatureRecord[]}
              />
            </div>
          </div>
        </div>
      </PageSection>

      <PageSection
        eyebrow="Feature snapshot"
        title="Historical row inputs"
        description="A plain-text dump of the feature snapshot used for the selected historical explanation. Fancy charts can join the party later."
      >
        <QueryState
          isLoading={explanationQuery.isLoading}
          isError={explanationQuery.isError}
          isEmpty={!explanation}
          loadingLabel="Loading feature snapshot…"
          errorLabel="Feature snapshot could not be loaded."
          emptyLabel="Pick a row to inspect the underlying feature snapshot."
        >
          <pre className="code-block overflow-x-auto whitespace-pre-wrap break-words">
            {JSON.stringify(explanation?.feature_snapshot ?? {}, null, 2)}
          </pre>
        </QueryState>
      </PageSection>
    </div>
  )
}