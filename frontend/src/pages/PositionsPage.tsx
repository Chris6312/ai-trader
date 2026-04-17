import { LayoutList, ScanSearch } from 'lucide-react'

import { PageSection } from '../components/PageSection'

export function PositionsPage() {
  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Positions"
        title="Position watchfloor"
        description="This route is intentionally wide and modular so we can bring over the best parts of your other project later: inspect drawers, telemetry cards, and cleaner operator decision support."
      >
        <div className="placeholder-grid">
          <article className="placeholder-card">
            <LayoutList size={18} />
            <h3>Positions table slot</h3>
            <p className="muted">Open position rows, PnL columns, and future action affordances will live here.</p>
          </article>
          <article className="placeholder-card">
            <ScanSearch size={18} />
            <h3>Inspect drawer lane</h3>
            <p className="muted">The page spacing already leaves breathing room for an inspection drawer without redoing the shell.</p>
          </article>
        </div>
      </PageSection>
    </div>
  )
}
