import type { ReactNode } from 'react'

interface QueryStateProps {
  isLoading?: boolean
  isError?: boolean
  isEmpty?: boolean
  loadingLabel?: string
  errorLabel?: string
  emptyLabel?: string
  children: ReactNode
}

export function QueryState({
  isLoading = false,
  isError = false,
  isEmpty = false,
  loadingLabel = 'Loading…',
  errorLabel = 'Unable to load this section right now.',
  emptyLabel = 'Nothing to show yet.',
  children,
}: QueryStateProps) {
  if (isLoading) {
    return <div className="empty-state">{loadingLabel}</div>
  }

  if (isError) {
    return <div className="empty-state empty-state--danger">{errorLabel}</div>
  }

  if (isEmpty) {
    return <div className="empty-state">{emptyLabel}</div>
  }

  return <>{children}</>
}
