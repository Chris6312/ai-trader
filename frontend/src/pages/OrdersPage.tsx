import { ArrowUpDown, ScrollText } from 'lucide-react'

import { PageSection } from '../components/PageSection'

export function OrdersPage() {
  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Orders"
        title="Order queue"
        description="This route keeps the same cockpit vocabulary as your reference project: a broad table surface, strong status chips, and a future detail lane for individual order records."
      >
        <div className="placeholder-grid">
          <article className="placeholder-card">
            <ScrollText size={18} />
            <h3>Orders table slot</h3>
            <p className="muted">Open, canceled, and filled order rows will land here in the next frontend slice.</p>
          </article>
          <article className="placeholder-card">
            <ArrowUpDown size={18} />
            <h3>Filter and sort rail</h3>
            <p className="muted">Structure is ready for state filters, symbol search, and status-focused views.</p>
          </article>
        </div>
      </PageSection>
    </div>
  )
}
