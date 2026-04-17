interface SummaryCardProps {
  label: string
  value: string
  tone?: 'neutral' | 'good' | 'warn'
  detail?: string
}

export function SummaryCard({ label, value, tone = 'neutral', detail }: SummaryCardProps) {
  return (
    <article className={`summary-card summary-card--${tone}`}>
      <p className="summary-card__label">{label}</p>
      <p className="summary-card__value">{value}</p>
      {detail ? <p className="summary-card__detail muted">{detail}</p> : null}
    </article>
  )
}
