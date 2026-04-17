import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowRightLeft, Coins, ShieldCheck } from 'lucide-react'

import { fetchPaperAccountSummaries } from '../api/paperAccounts'
import { PageSection } from '../components/PageSection'
import { SummaryCard } from '../components/SummaryCard'

function formatMoney(value: string): string {
  const numericValue = Number(value)
  return Number.isFinite(numericValue)
    ? numericValue.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
      })
    : value
}

export function DashboardPage() {
  const summaryQuery = useQuery({
    queryKey: ['paper-account-summaries'],
    queryFn: fetchPaperAccountSummaries,
  })

  const summaries = summaryQuery.data ?? []
  const totalEquity = summaries.reduce((sum, item) => sum + Number(item.equity), 0)
  const totalOpenOrders = summaries.reduce((sum, item) => sum + item.open_order_count, 0)
  const totalPositions = summaries.reduce((sum, item) => sum + item.position_count, 0)

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Overview"
        title="Operator dashboard"
        description="A clean launchpad for the paper broker cockpit. This shell borrows the best habits from your other frontend: strong hierarchy, compact telemetry, and room for drawers and detail panes later."
      >
        <div className="summary-grid">
          <SummaryCard
            label="Combined equity"
            value={formatMoney(String(totalEquity))}
            tone="good"
            detail="Aggregated from stock and crypto paper accounts."
          />
          <SummaryCard
            label="Open orders"
            value={String(totalOpenOrders)}
            detail="Useful now as a shell metric, richer filters land in the next frontend slice."
          />
          <SummaryCard
            label="Open positions"
            value={String(totalPositions)}
            detail="Position detail drawers are staged for a later phase."
          />
          <SummaryCard
            label="Data status"
            value={summaryQuery.isLoading ? 'Loading…' : summaryQuery.isError ? 'Offline' : 'Connected'}
            tone={summaryQuery.isError ? 'warn' : 'neutral'}
            detail="Dashboard cards degrade politely if the backend is asleep."
          />
        </div>
      </PageSection>

      <div className="two-column-grid">
        <PageSection
          eyebrow="Paper accounts"
          title="Asset-class snapshots"
          description="Thin cards for now, with enough structure to grow into a real cockpit without needing to rip up the flooring later."
        >
          <div className="stack-list">
            {summaries.length === 0 ? (
              <div className="empty-state">
                <p>No account data yet.</p>
                <p className="muted">Start the backend and this card stack will wake up.</p>
              </div>
            ) : (
              summaries.map((item) => (
                <article key={item.asset_class} className="list-card">
                  <div className="list-card__header">
                    <div>
                      <p className="eyebrow">{item.asset_class}</p>
                      <h3>{item.asset_class === 'stock' ? 'Stock paper account' : 'Crypto paper account'}</h3>
                    </div>
                    <span className="status-pill">{item.base_currency}</span>
                  </div>
                  <div className="metric-row">
                    <div>
                      <span className="metric-row__label">Cash available</span>
                      <strong>{formatMoney(item.cash_available)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Equity</span>
                      <strong>{formatMoney(item.equity)}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Open orders</span>
                      <strong>{item.open_order_count}</strong>
                    </div>
                    <div>
                      <span className="metric-row__label">Positions</span>
                      <strong>{item.position_count}</strong>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </PageSection>

        <PageSection
          eyebrow="Roadmap"
          title="Why this shell is shaped this way"
          description="The uploaded reference screens leaned hard into crisp navigation, dense-but-readable telemetry, and drawer-friendly layouts. Those bones are now in place here too."
        >
          <div className="feature-list">
            <div className="feature-list__item">
              <Activity size={18} />
              <div>
                <h3>Summary-first dashboard</h3>
                <p className="muted">The home view stays uncluttered and leaves detailed inspection for dedicated pages.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <ArrowRightLeft size={18} />
              <div>
                <h3>Drawer-ready page rhythm</h3>
                <p className="muted">Wide content lanes, soft panels, and modular sections set up future inspect drawers cleanly.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <ShieldCheck size={18} />
              <div>
                <h3>Operator control posture</h3>
                <p className="muted">Controls have their own route so dangerous actions stay in one fenced garden.</p>
              </div>
            </div>
            <div className="feature-list__item">
              <Coins size={18} />
              <div>
                <h3>Backend-aware cards</h3>
                <p className="muted">Even the phase-5 shell can already sip from the paper account API instead of floating as a static mockup.</p>
              </div>
            </div>
          </div>
        </PageSection>
      </div>
    </div>
  )
}
