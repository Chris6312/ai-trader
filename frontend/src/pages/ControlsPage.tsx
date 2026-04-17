import { ShieldAlert, SlidersHorizontal } from 'lucide-react'

import { PageSection } from '../components/PageSection'

export function ControlsPage() {
  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Controls"
        title="Operator controls"
        description="This route fences off the sharp tools. Reset, wipe, cancel-all, and close-position actions belong on their own page with loud labels and calm spacing."
      >
        <div className="placeholder-grid">
          <article className="placeholder-card">
            <SlidersHorizontal size={18} />
            <h3>Action console</h3>
            <p className="muted">This area is reserved for forms and action buttons backed by the paper account control APIs from Phase 4.</p>
          </article>
          <article className="placeholder-card">
            <ShieldAlert size={18} />
            <h3>Confirmation zone</h3>
            <p className="muted">Dangerous actions should remain heavily confirmed and visually isolated from passive monitoring views.</p>
          </article>
        </div>
      </PageSection>
    </div>
  )
}
