import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CircleGauge, FlaskConical } from 'lucide-react'

import {
  fetchMlExplanation,
  fetchMlExplanationBySymbolDate,
  fetchMlFeatureHealthPanel,
  fetchMlModelRegistry,
  fetchMlOverview,
  fetchMlRows,
  fetchMlRuntimeControl,
  fetchMlStrategyLearningPanel,
  type MLRuntimeControlSummary,
  type MLTransparencyExplanation,
  type MLTransparencyFeatureHealthPanel,
  type MLTransparencyFeatureRecord,
  type MLTransparencyStrategyLearningPanel,
} from '../api/mlTransparency'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { SummaryCard } from '../components/SummaryCard'
import { formatTimestamp } from '../lib/formatters'

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatMetric(value: unknown) {
  const numericValue = asNumber(value)
  if (numericValue === null) {
    return '—'
  }
  return numericValue.toFixed(3)
}

function formatCount(value: unknown) {
  const numericValue = asNumber(value)
  if (numericValue === null) {
    return '—'
  }
  return String(numericValue)
}

function FeatureList({
  title,
  emptyLabel,
  rows,
}: {
  title: string
  emptyLabel: string
  rows: MLTransparencyFeatureRecord[]
}) {
  return (
    <article className="list-card min-w-0 overflow-hidden">
      <div className="list-card__header gap-3">
        <div className="min-w-0">
          <p className="eyebrow">Explainability</p>
          <h3 className="break-words">{title}</h3>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="muted break-words">{emptyLabel}</p>
      ) : (
        <div className="stack-list stack-list--tight min-w-0">
          {rows.map((item) => (
            <div
              key={`${title}-${item.feature_key}`}
              className="metric-row metric-row--feature min-w-0 flex-wrap gap-3"
            >
              <div className="min-w-0 flex-1">
                <span className="metric-row__label break-all">{item.feature_key}</span>
                <strong className="block break-words">
                  {item.contribution !== null && item.contribution !== undefined
                    ? `Contribution ${item.contribution.toFixed(3)}`
                    : `Permutation ${formatMetric(item.permutation_importance)}`}
                </strong>
              </div>
              <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                {item.tree_importance !== null ? (
                  <span className="status-pill">Tree {formatMetric(item.tree_importance)}</span>
                ) : null}
                {item.standardized_mean_shift !== null ? (
                  <span className="status-pill">Shift {formatMetric(item.standardized_mean_shift)}</span>
                ) : null}
                {item.drift_flagged ? <span className="status-pill status-pill--warn">Drift</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  )
}

export function MlTransparencyPage() {
  const registryQuery = useQuery({
    queryKey: ['ml-model-registry'],
    queryFn: fetchMlModelRegistry,
    refetchInterval: 30_000,
  })

  const modelRows = registryQuery.data ?? []
  const [selectedBundleVersion, setSelectedBundleVersion] = useState<string>('')
  const [selectedRowKey, setSelectedRowKey] = useState<string>('')
  const [requestedRuntimeMode, setRequestedRuntimeMode] = useState<string>('active_rank_only')

  useEffect(() => {
    if (modelRows.length === 0) {
      if (selectedBundleVersion) {
        setSelectedBundleVersion('')
      }
      return
    }

    const hasSelectedBundle = modelRows.some((item) => item.bundle_version === selectedBundleVersion)
    if (!selectedBundleVersion || !hasSelectedBundle) {
      setSelectedBundleVersion(modelRows[0].bundle_version)
      setSelectedRowKey('')
    }
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

  useEffect(() => {
    const firstRowKey = rowsQuery.data?.[0]?.row_key ?? ''
    if (!selectedRowKey && firstRowKey) {
      setSelectedRowKey(firstRowKey)
    }
  }, [rowsQuery.data, selectedRowKey])

  const explanationBySymbolQuery = useQuery({
    queryKey: ['ml-explanation-by-symbol', selectedBundleVersion, selectedRowKey],
    queryFn: async () => {
      const selectedRow = rowsQuery.data?.find((item) => item.row_key === selectedRowKey)
      if (!selectedRow) {
        throw new Error('row not found')
      }
      return fetchMlExplanationBySymbolDate(selectedBundleVersion, selectedRow.symbol, selectedRow.decision_date)
    },
    enabled: Boolean(selectedBundleVersion && selectedRowKey && rowsQuery.data?.length),
  })

  const explanationQuery = useQuery({
    queryKey: ['ml-explanation', selectedBundleVersion, selectedRowKey],
    queryFn: () => fetchMlExplanation(selectedBundleVersion, selectedRowKey),
    enabled: Boolean(selectedBundleVersion && selectedRowKey),
  })

  const selectedModel = useMemo(
    () => modelRows.find((item) => item.bundle_version === selectedBundleVersion) ?? modelRows[0] ?? null,
    [modelRows, selectedBundleVersion],
  )

  const runtimeQuery = useQuery({
    queryKey: ['ml-runtime', selectedBundleVersion, selectedModel?.strategy_name, requestedRuntimeMode],
    queryFn: () => fetchMlRuntimeControl(selectedBundleVersion, selectedModel?.strategy_name ?? '', requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion && selectedModel?.strategy_name),
  })

  const explanation = explanationQuery.data as MLTransparencyExplanation | undefined
  const explanationBySymbol = explanationBySymbolQuery.data as MLTransparencyExplanation | undefined

  const strategyPanelQuery = useQuery({
    queryKey: ['ml-strategy-panel', selectedBundleVersion, requestedRuntimeMode],
    queryFn: () => fetchMlStrategyLearningPanel(selectedBundleVersion, requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion),
  })
  const strategyPanel = strategyPanelQuery.data as MLTransparencyStrategyLearningPanel | undefined

  const featureHealthQuery = useQuery({
    queryKey: ['ml-feature-health', selectedBundleVersion, requestedRuntimeMode],
    queryFn: () => fetchMlFeatureHealthPanel(selectedBundleVersion, requestedRuntimeMode),
    enabled: Boolean(selectedBundleVersion),
  })
  const featureHealth = featureHealthQuery.data as MLTransparencyFeatureHealthPanel | undefined

  const runtime = runtimeQuery.data as MLRuntimeControlSummary | undefined

  const artifactStatusValue =
    runtime?.bundle_version === selectedBundleVersion
      ? runtime.verified_artifact
        ? 'Verified'
        : 'Missing'
      : selectedModel?.verified_artifact
        ? 'Verified'
        : 'Missing'

  const artifactStatusTone =
    runtime?.bundle_version === selectedBundleVersion
      ? runtime.verified_artifact
        ? 'good'
        : 'warn'
      : selectedModel?.verified_artifact
        ? 'good'
        : 'warn'

  const artifactStatusDetail =
    runtime?.bundle_version === selectedBundleVersion
      ? `Validation ref: ${selectedModel?.validation_version ?? 'not bundled yet'} · Source: ${String(runtime.metadata?.artifact_source ?? 'unknown')}`
      : `Validation ref: ${selectedModel?.validation_version ?? 'not bundled yet'}`

  const strategyReasonCodes =
    strategyPanel?.runtime_control?.reason_codes?.length
      ? strategyPanel.runtime_control.reason_codes
      : ['guardrails_clear']

  return (
    <div className="page-grid overflow-x-hidden">
      <PageSection
        eyebrow="ML transparency"
        title="What the model learned"
        description="This lane turns the model from a black shoebox into a glass terrarium. You can inspect lineage, top features, drift warnings, and a historical row explanation without handing the ML layer the steering wheel."
        actions={
          <div className="filter-row flex-wrap">
            <label className="field-shell min-w-[260px] flex-1">
              <span>Bundle</span>
              <select
                value={selectedBundleVersion}
                onChange={(event) => {
                  setSelectedBundleVersion(event.target.value)
                  setSelectedRowKey('')
                }}
              >
                {modelRows.map((item) => (
                  <option key={item.bundle_version} value={item.bundle_version}>
                    {item.strategy_name} · {item.bundle_version}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-shell min-w-[220px]">
              <span>Requested mode</span>
              <select value={requestedRuntimeMode} onChange={(event) => setRequestedRuntimeMode(event.target.value)}>
                <option value="disabled">Disabled</option>
                <option value="shadow">Shadow</option>
                <option value="active_rank_only">Active rank-only</option>
              </select>
            </label>
          </div>
        }
      >
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
              detail={selectedModel?.strategy_name ?? 'No persisted ML bundle selected.'}
            />
            <SummaryCard
              label="Model version"
              value={selectedModel?.model_version ?? '—'}
              detail={selectedModel?.model_family ?? 'Awaiting a saved model bundle.'}
            />
            <SummaryCard
              label="Feature count"
              value={String(selectedModel?.feature_count ?? 0)}
              detail={`Label key: ${selectedModel?.label_key ?? '—'}`}
            />
            <SummaryCard
              label="Artifact status"
              value={artifactStatusValue}
              tone={artifactStatusTone}
              detail={artifactStatusDetail}
            />
          </div>

          <article className="list-card min-w-0 overflow-hidden">
            <div className="list-card__header gap-3">
              <div className="min-w-0">
                <p className="eyebrow">Runtime guardrails</p>
                <h3 className="break-words">ML participation cage</h3>
              </div>
              <div className="stack-inline stack-inline--tight min-w-0 flex-wrap">
                <span
                  className={`status-pill ${
                    runtime?.effective_mode === 'active_rank_only'
                      ? 'status-pill--good'
                      : runtime?.effective_mode === 'blocked'
                        ? 'status-pill--warn'
                        : ''
                  }`}
                >
                  {runtime?.effective_mode ?? 'loading'}
                </span>
                <span className="status-pill break-all">{runtime?.ranking_policy ?? 'deterministic_only'}</span>
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
                    <SummaryCard label="Requested mode" value={runtime.requested_mode} />
                    <SummaryCard label="Effective mode" value={runtime.effective_mode} />
                    <SummaryCard
                      label="Bundle age"
                      value={runtime.bundle_age_days !== null ? `${runtime.bundle_age_days}d` : '—'}
                      detail={`Stale after ${runtime.stale_after_days ?? '—'}d`}
                    />
                    <SummaryCard
                      label="Validation"
                      value={runtime.validation_metric_value !== null ? formatMetric(runtime.validation_metric_value) : '—'}
                      detail={runtime.validation_metric_key ?? 'metric'}
                    />
                  </div>

                  <div className="stack-inline stack-inline--tight min-w-0 flex-wrap">
                    {(runtime.reason_codes.length > 0 ? runtime.reason_codes : ['guardrails_clear']).map((item) => (
                      <span
                        key={item}
                        className={`status-pill ${
                          item === 'guardrails_clear'
                            ? 'status-pill--good'
                            : item === 'shadow_mode'
                              ? ''
                              : 'status-pill--warn'
                        }`}
                      >
                        {item}
                      </span>
                    ))}
                  </div>

                  {runtime.missing_feature_keys.length > 0 ? (
                    <p className="muted break-words">
                      Missing features: {runtime.missing_feature_keys.join(', ')}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </QueryState>
          </article>
        </QueryState>
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
                      <p className="eyebrow">{item.strategy_name}</p>
                      <h3 className="break-all">{item.bundle_version}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                      <span className="status-pill break-all">{item.dataset_version}</span>
                      <span className={`status-pill ${item.verified_artifact ? 'status-pill--good' : 'status-pill--warn'}`}>
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
            isEmpty={!overviewQuery.data}
            loadingLabel="Loading transparency overview…"
            errorLabel="The overview endpoint could not be loaded for this bundle."
            emptyLabel="Pick a persisted bundle to see its health card."
          >
            {overviewQuery.data ? (
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
                    {Object.entries(overviewQuery.data.training_metrics).map(([key, value]) => (
                      <div key={key} className="metric-tile min-w-0">
                        <span className="metric-row__label break-all">{key}</span>
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
                    {Object.entries(overviewQuery.data.lineage).map(([key, value]) => (
                      <div key={key} className="metric-tile min-w-0">
                        <span className="metric-row__label break-all">{key}</span>
                        <strong className="break-words">{String(value)}</strong>
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
                  <SummaryCard label="Rows" value={formatCount(strategyPanel.summary.rows_total)} />
                  <SummaryCard label="Symbols" value={formatCount(strategyPanel.summary.symbols_total)} />
                  <SummaryCard label="Positive label rate" value={formatMetric(strategyPanel.summary.positive_label_rate)} />
                  <SummaryCard
                    label="Runtime context"
                    value={String(strategyPanel.summary.runtime_context ?? '—')}
                    detail={String(strategyPanel.summary.ranking_policy ?? '—')}
                  />
                </div>

                <article className="list-card min-w-0 overflow-hidden">
                  <div className="list-card__header gap-3">
                    <div className="min-w-0">
                      <p className="eyebrow">Top learning anchors</p>
                      <h3 className="break-words">{strategyPanel.strategy_name}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight min-w-0 flex-wrap justify-end">
                      {strategyReasonCodes.slice(0, 3).map((item) => (
                        <span
                          key={item}
                          className={`status-pill ${
                            item === 'guardrails_clear'
                              ? 'status-pill--good'
                              : item === 'shadow_mode'
                                ? ''
                                : 'status-pill--warn'
                          }`}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="muted break-words">
                    Window {String(strategyPanel.summary.decision_date_start ?? '—')} to{' '}
                    {String(strategyPanel.summary.decision_date_end ?? '—')} · Drift flags{' '}
                    {String(strategyPanel.summary.drift_flagged_feature_count ?? 0)}
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
                <div className="stack-list min-w-0">
                  <div className="summary-grid min-w-0">
                    <SummaryCard
                      label="Validation ref"
                      value={String(featureHealth.validation_summary.validation_version ?? '—')}
                    />
                    <SummaryCard
                      label="Runtime context"
                      value={String(featureHealth.validation_summary.runtime_context ?? '—')}
                      detail={String(featureHealth.validation_summary.ranking_policy ?? '—')}
                    />
                    <SummaryCard
                      label="Drift flags"
                      value={String(featureHealth.drift_summary.flagged_feature_count ?? 0)}
                      detail={`PSI max ${formatMetric(featureHealth.drift_summary.highest_population_stability_index)}`}
                    />
                    <SummaryCard
                      label="Overlap"
                      value={String(featureHealth.overlapping_feature_keys.length)}
                      detail={featureHealth.overlapping_feature_keys.join(', ') || 'No overlap'}
                    />
                  </div>
                </div>
              ) : null}
            </QueryState>
          </PageSection>
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureList
            title="Feature leaders"
            emptyLabel="No feature-leader summary is attached to this bundle yet."
            rows={featureHealth?.global_feature_leaders ?? []}
          />
        </div>

        <div className="xl:col-span-4 min-w-0">
          <FeatureList
            title="Regime leaders"
            emptyLabel="No regime-leader summary is attached to this bundle yet."
            rows={featureHealth?.regime_feature_leaders ?? []}
          />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-4 min-w-0">
          <FeatureList
            title="Global feature importance"
            emptyLabel="No global feature importance artifact is attached to this bundle yet."
            rows={overviewQuery.data?.global_feature_importance ?? []}
          />
        </div>
        <div className="xl:col-span-4 min-w-0">
          <FeatureList
            title="Regime-sensitive importance"
            emptyLabel="No regime-specific importance artifact is attached to this bundle yet."
            rows={overviewQuery.data?.regime_feature_importance ?? []}
          />
        </div>
        <div className="xl:col-span-4 min-w-0">
          <FeatureList
            title="Drift signals"
            emptyLabel="No drift artifact is attached to this bundle yet."
            rows={overviewQuery.data?.drift_signals ?? []}
          />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-6 min-w-0">
          <PageSection
            eyebrow="Historical explain drawer"
            title="Per-row explanation"
            description="Pick a historical dataset row and inspect the score, probability, and the strongest nudges that pushed the model north or south."
            actions={
              <div className="filter-row flex-wrap">
                <label className="field-shell min-w-[260px] flex-1">
                  <span>Historical row</span>
                  <select value={selectedRowKey} onChange={(event) => setSelectedRowKey(event.target.value)}>
                    {(rowsQuery.data ?? []).map((item) => (
                      <option key={item.row_key} value={item.row_key}>
                        {item.symbol} · {item.decision_date} · {item.row_key.slice(0, 12)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            }
          >
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
                        <span className="status-pill">{explanation.row.asset_class}</span>
                        <span className="status-pill">{explanation.row.timeframe}</span>
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
                      <p className="muted break-words">Scoring was skipped: {explanation.skipped_reason}</p>
                    </article>
                  ) : null}
                </div>
              ) : null}
            </QueryState>
          </PageSection>
        </div>

        <div className="xl:col-span-6 min-w-0">
          <div className="stack-list min-w-0">
            <PageSection
              eyebrow="Contributors"
              title="Positive nudges"
              description="Features that whispered yes loudest."
            >
              <FeatureList
                title="Top positive contributors"
                emptyLabel="No positive contributors were available for this row."
                rows={explanation?.positive_contributors ?? []}
              />
            </PageSection>

            <PageSection
              eyebrow="Contributors"
              title="Negative nudges"
              description="Features that threw sand in the gears."
            >
              <FeatureList
                title="Top negative contributors"
                emptyLabel="No negative contributors were available for this row."
                rows={explanation?.negative_contributors ?? []}
              />
            </PageSection>
          </div>
        </div>
      </div>

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