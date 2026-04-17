import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldAlert, SlidersHorizontal } from 'lucide-react'

import {
  cancelAllPaperOrders,
  closePaperPositions,
  type AssetClass,
  fetchPaperAccountSummary,
  resetPaperBalance,
  wipePaperAccount,
} from '../api/paperAccounts'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { SummaryCard } from '../components/SummaryCard'
import { formatMoney, formatSignedMoney, formatTimestamp } from '../lib/formatters'

export function ControlsPage() {
  const queryClient = useQueryClient()
  const [assetClass, setAssetClass] = useState<AssetClass>('stock')
  const [resetAmount, setResetAmount] = useState('100000')
  const [lastAction, setLastAction] = useState('No control actions fired in this session yet.')

  const summaryQuery = useQuery({
    queryKey: ['paper-summary', assetClass],
    queryFn: () => fetchPaperAccountSummary(assetClass),
    refetchInterval: 15_000,
  })

  const onMutationSuccess = (message: string) => {
    setLastAction(message)
    void queryClient.invalidateQueries({ queryKey: ['paper-summary', assetClass] })
    void queryClient.invalidateQueries({ queryKey: ['paper-account-summaries'] })
    void queryClient.invalidateQueries({ queryKey: ['paper-balances', assetClass] })
    void queryClient.invalidateQueries({ queryKey: ['paper-orders', assetClass] })
    void queryClient.invalidateQueries({ queryKey: ['paper-positions', assetClass] })
  }

  const resetMutation = useMutation({
    mutationFn: () => resetPaperBalance(assetClass, { amount: resetAmount }),
    onSuccess: () => onMutationSuccess(`Reset ${assetClass} balance to ${resetAmount}.`),
  })

  const wipeMutation = useMutation({
    mutationFn: () => wipePaperAccount(assetClass),
    onSuccess: () => onMutationSuccess(`Wiped ${assetClass} paper account back to its default starting state.`),
  })

  const cancelAllMutation = useMutation({
    mutationFn: () => cancelAllPaperOrders(assetClass),
    onSuccess: (orders) => onMutationSuccess(`Canceled ${orders.length} open ${assetClass} paper orders.`),
  })

  const closePositionsMutation = useMutation({
    mutationFn: () => closePaperPositions(assetClass),
    onSuccess: (orders) => onMutationSuccess(`Submitted ${orders.length} close orders for ${assetClass} paper positions.`),
  })

  const mutationError = useMemo(
    () => resetMutation.error ?? wipeMutation.error ?? cancelAllMutation.error ?? closePositionsMutation.error,
    [cancelAllMutation.error, closePositionsMutation.error, resetMutation.error, wipeMutation.error],
  )

  const isBusy =
    resetMutation.isPending ||
    wipeMutation.isPending ||
    cancelAllMutation.isPending ||
    closePositionsMutation.isPending

  const summary = summaryQuery.data
  const currency = summary?.base_currency ?? 'USD'

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Controls"
        title="Operator controls"
        description="Use with intent. Actions here mutate simulated account state, so this lane stays fenced off from passive monitoring pages and calls for deliberate clicks instead of drive-by toggles."
      >
        <div className="control-layout">
          <section className="panel control-panel">
            <div className="section-bar">
              <div className="stack-inline stack-inline--tight">
                <SlidersHorizontal size={18} />
                <strong>Action console</strong>
              </div>
              <label className="field field--inline">
                <span>Asset class</span>
                <select value={assetClass} onChange={(event) => setAssetClass(event.target.value as AssetClass)}>
                  <option value="stock">Stock</option>
                  <option value="crypto">Crypto</option>
                </select>
              </label>
            </div>

            <QueryState
              isLoading={summaryQuery.isLoading}
              isError={summaryQuery.isError}
              loadingLabel="Loading paper account summary…"
              errorLabel="Unable to load the selected paper account summary."
            >
              {summary ? (
                <div className="summary-grid summary-grid--compact">
                  <SummaryCard label="Equity" value={formatMoney(summary.equity, currency)} tone="good" />
                  <SummaryCard label="Cash available" value={formatMoney(summary.cash_available, currency)} />
                  <SummaryCard label="Open orders" value={String(summary.open_order_count)} />
                  <SummaryCard label="Positions" value={String(summary.position_count)} />
                </div>
              ) : null}
            </QueryState>

            <div className="control-grid">
              <div className="detail-card detail-card--form">
                <div>
                  <p className="eyebrow">Reset balance</p>
                  <h4>Re-seed buying power</h4>
                </div>
                <label className="field">
                  <span>New balance amount</span>
                  <input value={resetAmount} onChange={(event) => setResetAmount(event.target.value)} placeholder="100000" />
                </label>
                <button type="button" className="button" disabled={isBusy} onClick={() => resetMutation.mutate()}>
                  Reset balance
                </button>
              </div>

              <div className="detail-card detail-card--form">
                <div>
                  <p className="eyebrow">Open orders</p>
                  <h4>Cancel outstanding orders</h4>
                </div>
                <p className="muted">Clears every open order in the selected paper account before new entries are staged.</p>
                <button type="button" className="button button--ghost" disabled={isBusy} onClick={() => cancelAllMutation.mutate()}>
                  Cancel all open orders
                </button>
              </div>

              <div className="detail-card detail-card--form">
                <div>
                  <p className="eyebrow">Exposure</p>
                  <h4>Close all positions</h4>
                </div>
                <p className="muted">Submits paper market exits for every closeable position after canceling open orders.</p>
                <button type="button" className="button button--ghost" disabled={isBusy} onClick={() => closePositionsMutation.mutate()}>
                  Close all positions
                </button>
              </div>

              <div className="detail-card detail-card--form detail-card--danger">
                <div>
                  <p className="eyebrow">Destructive</p>
                  <h4>Wipe account</h4>
                </div>
                <p className="muted">Resets the selected paper account back to its default starting state and clears simulated activity.</p>
                <button type="button" className="button button--danger" disabled={isBusy} onClick={() => wipeMutation.mutate()}>
                  Wipe account
                </button>
              </div>
            </div>
          </section>

          <section className="panel control-panel control-panel--narrow">
            <div className="section-bar">
              <div className="stack-inline stack-inline--tight">
                <ShieldAlert size={18} />
                <strong>Confirmation zone</strong>
              </div>
            </div>

            <div className="stack-list">
              <article className="detail-card">
                <p className="eyebrow">Selected account</p>
                <h4>{assetClass === 'stock' ? 'Stock paper account' : 'Crypto paper account'}</h4>
                {summary ? (
                  <div className="metric-row">
                    <div>
                      <span className="metric-row__label">Updated</span>
                      <strong>{formatTimestamp(summary.updated_at)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Unrealized PnL</span>
                      <strong>{formatSignedMoney(summary.unrealized_pnl, currency)}</strong>
                    </div>
                  </div>
                ) : null}
              </article>

              <article className="detail-card">
                <p className="eyebrow">Last action</p>
                <p>{lastAction}</p>
              </article>

              {mutationError ? (
                <article className="empty-state empty-state--danger">
                  {(mutationError as Error).message || 'A control action failed.'}
                </article>
              ) : null}
            </div>
          </section>
        </div>
      </PageSection>
    </div>
  )
}
