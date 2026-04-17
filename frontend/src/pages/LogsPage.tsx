import { FileClock, MessagesSquare } from 'lucide-react'

import { PageSection } from '../components/PageSection'

export function LogsPage() {
  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Logs"
        title="Audit and event stream"
        description="Your reference UI handled audit-style pages well, with dense but readable rows and quick export affordances. This shell reserves the space for that evolution."
      >
        <div className="placeholder-grid">
          <article className="placeholder-card">
            <FileClock size={18} />
            <h3>Audit timeline slot</h3>
            <p className="muted">Table layout, sticky headers, and event filtering can slide in without touching the global shell.</p>
          </article>
          <article className="placeholder-card">
            <MessagesSquare size={18} />
            <h3>System log notes</h3>
            <p className="muted">Useful for control-plane actions, account events, and future backend observability work.</p>
          </article>
        </div>
      </PageSection>
    </div>
  )
}
