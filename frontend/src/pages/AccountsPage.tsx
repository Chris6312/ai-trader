import { Database, Wallet } from 'lucide-react'

import { PageSection } from '../components/PageSection'

export function AccountsPage() {
  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Accounts"
        title="Account surfaces"
        description="This route is reserved for balances, equity cards, buying power, and asset-class summaries. The shell is in place so Phase 6 can focus on real data presentation rather than layout carpentry."
      >
        <div className="placeholder-grid">
          <article className="placeholder-card">
            <Wallet size={18} />
            <h3>Balance panels</h3>
            <p className="muted">Stock and crypto balances will live here with loading, error, and empty states.</p>
          </article>
          <article className="placeholder-card">
            <Database size={18} />
            <h3>Account detail rail</h3>
            <p className="muted">Room is reserved for per-account metadata, refresh timestamps, and future persisted broker state.</p>
          </article>
        </div>
      </PageSection>
    </div>
  )
}
