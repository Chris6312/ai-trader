import { apiClient } from './client'

export type AssetClass = 'stock' | 'crypto'
export type OrderStatus = 'open' | 'filled' | 'canceled'
export type OrderSide = 'buy' | 'sell'
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit'

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

export interface BalanceRecord {
  currency: string
  total: string
  available: string
  reserved: string
  updated_at: string
}

export interface PositionRecord {
  symbol: string
  asset_class: AssetClass
  quantity: string
  reserved_quantity: string
  average_entry_price: string
  market_price: string
  market_value: string
  unrealized_pnl: string
  updated_at: string
}

export interface OrderRecord {
  id: string
  symbol: string
  asset_class: AssetClass
  side: OrderSide
  order_type: OrderType
  quantity: string
  status: OrderStatus
  created_at: string
  updated_at: string
  limit_price: string | null
  stop_price: string | null
  reserved_cash: string
  reserved_quantity: string
  filled_quantity: string
  average_fill_price: string | null
  fee_paid: string
}

export interface ResetBalancePayload {
  amount: string
}

export async function fetchPaperAccountSummary(assetClass: AssetClass): Promise<AccountSummary> {
  const response = await apiClient.get<AccountSummary>(`/api/paper/${assetClass}/summary`)
  return response.data
}

export async function fetchPaperAccountSummaries(): Promise<AccountSummary[]> {
  return Promise.all([fetchPaperAccountSummary('stock'), fetchPaperAccountSummary('crypto')])
}

export async function fetchPaperBalances(assetClass: AssetClass): Promise<BalanceRecord[]> {
  const response = await apiClient.get<BalanceRecord[]>(`/api/paper/${assetClass}/balances`)
  return response.data
}

export async function fetchPaperPositions(assetClass: AssetClass): Promise<PositionRecord[]> {
  const response = await apiClient.get<PositionRecord[]>(`/api/paper/${assetClass}/positions`)
  return response.data
}

export async function fetchPaperOrders(
  assetClass: AssetClass,
  status?: OrderStatus | 'all',
): Promise<OrderRecord[]> {
  const response = await apiClient.get<OrderRecord[]>(`/api/paper/${assetClass}/orders`, {
    params: status && status !== 'all' ? { status_value: status } : undefined,
  })
  return response.data
}

export async function resetPaperBalance(
  assetClass: AssetClass,
  payload: ResetBalancePayload,
): Promise<AccountSummary> {
  const response = await apiClient.post<AccountSummary>(`/api/paper/${assetClass}/reset-balance`, payload)
  return response.data
}

export async function wipePaperAccount(assetClass: AssetClass): Promise<AccountSummary> {
  const response = await apiClient.post<AccountSummary>(`/api/paper/${assetClass}/wipe`)
  return response.data
}

export async function cancelPaperOrder(assetClass: AssetClass, orderId: string): Promise<OrderRecord> {
  const response = await apiClient.post<OrderRecord>(`/api/paper/${assetClass}/orders/${orderId}/cancel`)
  return response.data
}

export async function cancelAllPaperOrders(assetClass: AssetClass): Promise<OrderRecord[]> {
  const response = await apiClient.post<OrderRecord[]>(`/api/paper/${assetClass}/orders/cancel-all`)
  return response.data
}

export async function closePaperPositions(assetClass: AssetClass): Promise<OrderRecord[]> {
  const response = await apiClient.post<OrderRecord[]>(`/api/paper/${assetClass}/positions/close`)
  return response.data
}
