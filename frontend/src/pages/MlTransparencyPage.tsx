import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CircleGauge, FlaskConical } from 'lucide-react'

import {
  fetchMlExplanation,
  fetchMlModelRegistry,
  fetchMlOverview,
  fetchMlRows,
  fetchMlRuntimeControl,
  type MLRuntimeControlSummary,
  type MLTransparencyExplanation,
  type MLTransparencyFeatureRecord,
} from '../api/mlTransparency'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { SummaryCard } from '../components/SummaryCard'
import { formatTimestamp } from '../lib/formatters'

function formatMetric(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—'
  }
  return value.toFixed(3)
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
    <article className="list-card">
      <div className="list-card__header">
        <div>
          <p className="eyebrow">Explainability</p>
          <h3>{title}</h3>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="muted">{emptyLabel}</p>
      ) : (
        <div className="stack-list stack-list--tight">
          {rows.map((item) => (
            <div key={`${title}-${item.feature_key}`} className="metric-row metric-row--feature">
              <div>
                <span className="metric-row__label">{item.feature_key}</span>
                <strong>
                  {item.contribution !== null && item.contribution !== undefined
                    ? `Contribution ${item.contribution.toFixed(3)}`
                    : `Permutation ${formatMetric(item.permutation_importance)}`}
                </strong>
              </div>
              <div className="stack-inline stack-inline--tight">
                {item.tree_importance !== null ? <span className="status-pill">Tree {formatMetric(item.tree_importance)}</span> : null}
                {item.standardized_mean_shift !== null ? <span className="status-pill">Shift {formatMetric(item.standardized_mean_shift)}</span> : null}
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
    if (!selectedBundleVersion && modelRows.length > 0) {
      setSelectedBundleVersion(modelRows[0].bundle_version)
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
  const runtime = runtimeQuery.data as MLRuntimeControlSummary | undefined

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="ML transparency"
        title="What the model learned"
        description="This lane turns the model from a black shoebox into a glass terrarium. You can inspect lineage, top features, drift warnings, and a historical row explanation without handing the ML layer the steering wheel."
        actions={
          <div className="filter-row">
            <label className="field-shell">
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
            <label className="field-shell">
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
          <div className="summary-grid summary-grid--hero">
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
              value={selectedModel?.verified_artifact ? 'Verified' : 'Missing'}
              tone={selectedModel?.verified_artifact ? 'good' : 'warn'}
              detail={`Validation ref: ${selectedModel?.validation_version ?? 'not bundled yet'}`}
            />
          </div>
          <article className="list-card">
            <div className="list-card__header">
              <div>
                <p className="eyebrow">Runtime guardrails</p>
                <h3>ML participation cage</h3>
              </div>
              <div className="stack-inline stack-inline--tight">
                <span className={`status-pill ${runtime?.effective_mode === 'active_rank_only' ? 'status-pill--good' : runtime?.effective_mode === 'blocked' ? 'status-pill--warn' : ''}`}>
                  {runtime?.effective_mode ?? 'loading'}
                </span>
                <span className="status-pill">{runtime?.ranking_policy ?? 'deterministic_only'}</span>
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
                <div className="stack-list stack-list--tight">
                  <div className="summary-grid">
                    <SummaryCard label="Requested mode" value={runtime.requested_mode} />
                    <SummaryCard label="Effective mode" value={runtime.effective_mode} />
                    <SummaryCard label="Bundle age" value={runtime.bundle_age_days !== null ? `${runtime.bundle_age_days}d` : '—'} detail={`Stale after ${runtime.stale_after_days ?? '—'}d`} />
                    <SummaryCard label="Validation" value={runtime.validation_metric_value !== null ? formatMetric(runtime.validation_metric_value) : '—'} detail={runtime.validation_metric_key ?? 'metric'} />
                  </div>
                  <div className="stack-inline stack-inline--tight">
                    {(runtime.reason_codes.length > 0 ? runtime.reason_codes : ['guardrails_clear']).map((item) => (
                      <span key={item} className={`status-pill ${item === 'guardrails_clear' ? 'status-pill--good' : item === 'shadow_mode' ? '' : 'status-pill--warn'}`}>
                        {item}
                      </span>
                    ))}
                  </div>
                  {runtime.missing_feature_keys.length > 0 ? (
                    <p className="muted">Missing features: {runtime.missing_feature_keys.join(', ')}</p>
                  ) : null}
                </div>
              ) : null}
            </QueryState>
          </article>
        </QueryState>
      </PageSection>

      <div className="two-column-grid">
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
            <div className="stack-list">
              {modelRows.map((item) => (
                <button
                  key={item.bundle_version}
                  type="button"
                  className={`list-card list-card--button ${item.bundle_version === selectedBundleVersion ? 'is-selected' : ''}`}
                  onClick={() => {
                    setSelectedBundleVersion(item.bundle_version)
                    setSelectedRowKey('')
                  }}
                >
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">{item.strategy_name}</p>
                      <h3>{item.bundle_version}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight">
                      <span className="status-pill">{item.dataset_version}</span>
                      <span className={`status-pill ${item.verified_artifact ? 'status-pill--good' : 'status-pill--warn'}`}>
                        {item.verified_artifact ? 'Ready' : 'Check artifact'}
                      </span>
                    </div>
                  </div>
                  <p className="muted">Model {item.model_version} · Validation {item.validation_version ?? 'pending'}</p>
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
              <div className="stack-list">
                <article className="list-card">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">Training metrics</p>
                      <h3>Baseline health</h3>
                    </div>
                    <CircleGauge className="icon-badge" />
                  </div>
                  <div className="metric-grid metric-grid--three">
                    {Object.entries(overviewQuery.data.training_metrics).map(([key, value]) => (
                      <div key={key} className="metric-tile">
                        <span className="metric-row__label">{key}</span>
                        <strong>{formatMetric(value)}</strong>
                      </div>
                    ))}
                  </div>
                </article>
                <article className="list-card">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">Lineage</p>
                      <h3>Traceability spine</h3>
                    </div>
                    <FlaskConical className="icon-badge" />
                  </div>
                  <div className="metric-grid metric-grid--two">
                    {Object.entries(overviewQuery.data.lineage).map(([key, value]) => (
                      <div key={key} className="metric-tile">
                        <span className="metric-row__label">{key}</span>
                        <strong>{String(value)}</strong>
                      </div>
                    ))}
                  </div>
                </article>
              </div>
            ) : null}
          </QueryState>
        </PageSection>
      </div>

      <div className="three-column-grid">
        <FeatureList
          title="Global feature importance"
          emptyLabel="No global feature importance artifact is attached to this bundle yet."
          rows={overviewQuery.data?.global_feature_importance ?? []}
        />
        <FeatureList
          title="Regime-sensitive importance"
          emptyLabel="No regime-specific importance artifact is attached to this bundle yet."
          rows={overviewQuery.data?.regime_feature_importance ?? []}
        />
        <FeatureList
          title="Drift signals"
          emptyLabel="No drift artifact is attached to this bundle yet."
          rows={overviewQuery.data?.drift_signals ?? []}
        />
      </div>

      <div className="two-column-grid two-column-grid--explain">
        <PageSection
          eyebrow="Historical explain drawer"
          title="Per-row explanation"
          description="Pick a historical dataset row and inspect the score, probability, and the strongest nudges that pushed the model north or south."
          actions={
            <div className="filter-row">
              <label className="field-shell">
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
              <div className="stack-list">
                <article className="list-card">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">{explanation.row.symbol}</p>
                      <h3>{explanation.row.row_key}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight">
                      <span className="status-pill">{explanation.row.asset_class}</span>
                      <span className="status-pill">{explanation.row.timeframe}</span>
                    </div>
                  </div>
                  <div className="summary-grid">
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
                  <article className="list-card">
                    <p className="muted">Scoring was skipped: {explanation.skipped_reason}</p>
                  </article>
                ) : null}
              </div>
            ) : null}
          </QueryState>
        </PageSection>

        <div className="stack-list">
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
          <pre className="code-block">{JSON.stringify(explanation?.feature_snapshot ?? {}, null, 2)}</pre>
        </QueryState>
      </PageSection>
    </div>
  )
}
