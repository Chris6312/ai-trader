import { useQuery } from '@tanstack/react-query'
import { RefreshCcw, Wallet } from 'lucide-react'

import {
  type AssetClass,
  fetchPaperBalances,
  fetchPaperAccountSummaries,
} from '../api/paperAccounts'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { SummaryCard } from '../components/SummaryCard'
import { formatMoney, formatSignedMoney, formatTimestamp } from '../lib/formatters'

const ASSET_CLASSES: AssetClass[] = ['stock', 'crypto']

export function AccountsPage() {
  const summaryQuery = useQuery({
    queryKey: ['paper-account-summaries'],
    queryFn: fetchPaperAccountSummaries,
    refetchInterval: 15_000,
  })

  const stockBalancesQuery = useQuery({
    queryKey: ['paper-balances', 'stock'],
    queryFn: () => fetchPaperBalances('stock'),
    refetchInterval: 15_000,
  })

  const cryptoBalancesQuery = useQuery({
    queryKey: ['paper-balances', 'crypto'],
    queryFn: () => fetchPaperBalances('crypto'),
    refetchInterval: 15_000,
  })

  const balanceMap = {
    stock: stockBalancesQuery.data ?? [],
    crypto: cryptoBalancesQuery.data ?? [],
  }

  const summaries = summaryQuery.data ?? []
  const isLoading = summaryQuery.isLoading || stockBalancesQuery.isLoading || cryptoBalancesQuery.isLoading
  const isError = summaryQuery.isError || stockBalancesQuery.isError || cryptoBalancesQuery.isError

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Accounts"
        title="Paper account surfaces"
        description="The balances lane now shows actual stock and crypto paper-account state instead of placeholder carpentry. These panels stay summary-rich so later phases can layer on deeper analytics without redoing the layout."
      >
        <QueryState
          isLoading={isLoading}
          isError={isError}
          isEmpty={summaries.length === 0}
          loadingLabel="Loading account summaries and balances…"
          errorLabel="Unable to load paper-account balances. Make sure the backend is running and the paper API is available."
          emptyLabel="No paper-account state is available yet."
        >
          <div className="page-grid">
            {ASSET_CLASSES.map((assetClass) => {
              const summary = summaries.find((item) => item.asset_class === assetClass)
              const balances = balanceMap[assetClass]
              const title = assetClass === 'stock' ? 'Stock paper account' : 'Crypto paper account'
              const currency = summary?.base_currency ?? 'USD'

              return (
                <section key={assetClass} className="panel account-panel">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">{assetClass}</p>
                      <h3>{title}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight">
                      <span className="status-pill">{currency}</span>
                      {summary ? <span className="status-pill">Updated {formatTimestamp(summary.updated_at)}</span> : null}
                    </div>
                  </div>

                  {summary ? (
                    <div className="summary-grid summary-grid--compact">
                      <SummaryCard label="Equity" value={formatMoney(summary.equity, currency)} tone="good" />
                      <SummaryCard label="Cash available" value={formatMoney(summary.cash_available, currency)} />
                      <SummaryCard label="Cash reserved" value={formatMoney(summary.cash_reserved, currency)} />
                      <SummaryCard
                        label="Realized PnL"
                        value={formatSignedMoney(summary.realized_pnl, currency)}
                        tone={Number(summary.realized_pnl) >= 0 ? 'good' : 'warn'}
                      />
                    </div>
                  ) : null}

                  <div className="balance-list">
                    <div className="section-bar">
                      <div className="stack-inline stack-inline--tight">
                        <Wallet size={16} />
                        <strong>Balances</strong>
                      </div>
                      <span className="status-pill">{balances.length} row{balances.length === 1 ? '' : 's'}</span>
                    </div>

                    {balances.length === 0 ? (
                      <div className="empty-state">No balance rows returned for this account.</div>
                    ) : (
                      balances.map((balance) => (
                        <article key={`${assetClass}-${balance.currency}`} className="detail-card">
                          <div>
                            <p className="eyebrow">{balance.currency}</p>
                            <h4>{balance.currency} balance</h4>
                          </div>
                          <div className="metric-row">
                            <div>
                              <span className="metric-row__label">Total</span>
                              <strong>{formatMoney(balance.total, balance.currency)}</strong>
                            </div>
                            <div>
                              <span className="metric-row__label">Available</span>
                              <strong>{formatMoney(balance.available, balance.currency)}</strong>
                            </div>
                            <div>
                              <span className="metric-row__label">Reserved</span>
                              <strong>{formatMoney(balance.reserved, balance.currency)}</strong>
                            </div>
                            <div>
                              <span className="metric-row__label">Updated</span>
                              <strong>{formatTimestamp(balance.updated_at)}</strong>
                            </div>
                          </div>
                        </article>
                      ))
                    )}
                  </div>

                  {summary ? (
                    <div className="section-bar section-bar--soft">
                      <div className="stack-inline stack-inline--tight muted">
                        <RefreshCcw size={15} />
                        <span>
                          Orders: {summary.open_order_count} · Positions: {summary.position_count} · Unrealized:{' '}
                          {formatSignedMoney(summary.unrealized_pnl, currency)}
                        </span>
                      </div>
                    </div>
                  ) : null}
                </section>
              )
            })}
          </div>
        </QueryState>
      </PageSection>
    </div>
  )
}
