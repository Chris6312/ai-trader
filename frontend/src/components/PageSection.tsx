import type { ReactNode } from 'react'

interface PageSectionProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  children: ReactNode
}

export function PageSection({ eyebrow, title, description, actions, children }: PageSectionProps) {
  return (
    <section className="panel page-section">
      <div className="page-section__header">
        <div className="page-section__intro">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          <p className="muted copy-block page-section__description">{description}</p>
        </div>
        {actions ? <div className="page-section__actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  )
}
