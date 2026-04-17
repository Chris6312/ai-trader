import { apiClient } from './client'

export type AssetClass = 'stock' | 'crypto'

export interface AccountSummary {
  asset_class: AssetClass
  base_currency: string
  cash_total: string
  cash_available: string
  cash_reserved: string
  equity: string
  realized_pnl: string
  unrealized_pnl: string
  open_order_count: number
  position_count: number
  updated_at: string
}

export async function fetchPaperAccountSummary(assetClass: AssetClass): Promise<AccountSummary> {
  const response = await apiClient.get<AccountSummary>(`/api/paper/${assetClass}/summary`)
  return response.data
}

export async function fetchPaperAccountSummaries(): Promise<AccountSummary[]> {
  return Promise.all([
    fetchPaperAccountSummary('stock'),
    fetchPaperAccountSummary('crypto'),
  ])
}
