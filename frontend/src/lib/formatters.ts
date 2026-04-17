export function formatMoney(value: string | number, currency = 'USD'): string {
  const amount = typeof value === 'number' ? value : Number(value)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0)
}

export function formatSignedMoney(value: string | number, currency = 'USD'): string {
  const amount = typeof value === 'number' ? value : Number(value)
  const formatted = formatMoney(amount, currency)
  if (!Number.isFinite(amount) || amount === 0) {
    return formatted
  }
  return amount > 0 ? `+${formatted}` : formatted
}

export function formatQuantity(value: string | number): string {
  const amount = typeof value === 'number' ? value : Number(value)
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 8,
  }).format(Number.isFinite(amount) ? amount : 0)
}

export function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

export function titleCase(value: string): string {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
