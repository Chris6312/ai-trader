import { Activity, ArrowRightLeft, Coins, ShieldCheck } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import { fetchPaperAccountSummaries } from '../api/paperAccounts'
import { QueryState } from '../components/QueryState'
import { PageSection } from '../components/PageSection'
import { SummaryCard } from '../components/SummaryCard'
import { formatMoney, formatSignedMoney, formatTimestamp } from '../lib/formatters'

export function DashboardPage() {
  const summaryQuery = useQuery({
    queryKey: ['paper-account-summaries'],
    queryFn: fetchPaperAccountSummaries,
    refetchInterval: 15_000,
  })

  const summaries = summaryQuery.data ?? []
  const totalEquity = summaries.reduce((sum, item) => sum + Number(item.equity), 0)
  const totalOpenOrders = summaries.reduce((sum, item) => sum + item.open_order_count, 0)
  const totalPositions = summaries.reduce((sum, item) => sum + item.position_count, 0)
  const totalUnrealized = summaries.reduce((sum, item) => sum + Number(item.unrealized_pnl), 0)

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Overview"
        title="Operator dashboard"
        description="A compact launchpad for the paper broker cockpit. Keep the home view light, keep the detail lanes on their own pages, and let the most important paper-account signals rise to the top."
      >
        <div className="summary-grid summary-grid--hero">
          <SummaryCard
            label="Combined equity"
            value={formatMoney(totalEquity)}
            tone="good"
            detail="Combined stock and crypto paper equity."
          />
          <SummaryCard
            label="Open positions"
            value={String(totalPositions)}
            detail="Across both asset-class paper accounts."
          />
          <SummaryCard
            label="Open orders"
            value={String(totalOpenOrders)}
            detail="Queued orders waiting in the paper engine."
          />
          <SummaryCard
            label="Unrealized PnL"
            value={formatSignedMoney(totalUnrealized)}
            tone={totalUnrealized >= 0 ? 'good' : 'warn'}
            detail="Live paper mark-to-market posture."
          />
        </div>
      </PageSection>

      <div className="two-column-grid">
        <PageSection
          eyebrow="Paper accounts"
          title="Asset-class snapshots"
          description="Stock and crypto accounts stay readable here, while deeper positions and orders get their own full lanes."
        >
          <QueryState
            isLoading={summaryQuery.isLoading}
            isError={summaryQuery.isError}
            isEmpty={summaries.length === 0}
            loadingLabel="Warming up paper-account snapshots…"
            errorLabel="The frontend could not reach the paper account API. Check that the backend is running on port 8000."
            emptyLabel="No paper-account snapshots yet. Once the backend is up, summary cards will bloom here."
          >
            <div className="stack-list">
              {summaries.map((item) => (
                <article key={item.asset_class} className="list-card">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">{item.asset_class}</p>
                      <h3>{item.asset_class === 'stock' ? 'Stock paper account' : 'Crypto paper account'}</h3>
                    </div>
                    <div className="stack-inline stack-inline--tight">
                      <span className="status-pill">{item.base_currency}</span>
                      <span className="status-pill">Updated {formatTimestamp(item.updated_at)}</span>
                    </div>
                  </div>
                  <div className="metric-row">
                    <div>
                      <span className="metric-row__label">Cash available</span>
                      <strong>{formatMoney(item.cash_available, item.base_currency)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Cash reserved</span>
                      <strong>{formatMoney(item.cash_reserved, item.base_currency)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Equity</span>
                      <strong>{formatMoney(item.equity, item.base_currency)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Realized PnL</span>
                      <strong>{formatSignedMoney(item.realized_pnl, item.base_currency)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Unrealized PnL</span>
                      <strong>{formatSignedMoney(item.unrealized_pnl, item.base_currency)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Order / position counts</span>
                      <strong>
                        {item.open_order_count} / {item.position_count}
                      </strong>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </QueryState>
        </PageSection>

        <PageSection
          eyebrow="Operator posture"
          title="Why this lane stays uncluttered"
          description="The shell from Phase 5 stays intact. Phase 6 fills it with live account state, but it still keeps detailed order, position, and mutation work on their own pages."
        >
          <div className="feature-list">
            <div className="feature-list__item">
              <Activity size={18} />
              <div>
                <h3>Account pulse first</h3>
                <p className="muted">Home should tell you whether paper capital, orders, and exposure are calm or noisy in one glance.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <ArrowRightLeft size={18} />
              <div>
                <h3>Orders and positions split cleanly</h3>
                <p className="muted">Table density and control actions stay off the dashboard so the screen remains readable under pressure.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <ShieldCheck size={18} />
              <div>
                <h3>Controls stay fenced</h3>
                <p className="muted">Reset, wipe, close, and cancel-all actions remain isolated on the Controls route where confirmations belong.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <Coins size={18} />
              <div>
                <h3>Reference-frontend habits preserved</h3>
                <p className="muted">Dense but readable cards, strong nav hierarchy, and wide content lanes still shape the cockpit.</p>
              </div>
            </div>
          </div>
        </PageSection>
      </div>
    </div>
  )
}
