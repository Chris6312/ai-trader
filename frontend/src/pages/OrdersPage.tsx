import { useMemo, useState } from 'react'
import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query'
import { ArrowUpDown, ScrollText } from 'lucide-react'

import {
  cancelPaperOrder,
  type AssetClass,
  type OrderRecord,
  type OrderStatus,
  fetchPaperOrders,
} from '../api/paperAccounts'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { formatMoney, formatQuantity, formatTimestamp, titleCase } from '../lib/formatters'

const ASSET_CLASSES: AssetClass[] = ['stock', 'crypto']

export function OrdersPage() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<OrderStatus | 'all'>('all')
  const [symbolFilter, setSymbolFilter] = useState('')

  const orderQueries = useQueries({
    queries: ASSET_CLASSES.map((assetClass) => ({
      queryKey: ['paper-orders', assetClass, statusFilter],
      queryFn: () => fetchPaperOrders(assetClass, statusFilter),
      refetchInterval: 15_000,
    })),
  })

  const cancelOrderMutation = useMutation({
    mutationFn: ({ assetClass, orderId }: { assetClass: AssetClass; orderId: string }) =>
      cancelPaperOrder(assetClass, orderId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['paper-orders', variables.assetClass] })
      void queryClient.invalidateQueries({ queryKey: ['paper-account-summaries'] })
    },
  })

  const isLoading = orderQueries.some((query) => query.isLoading)
  const isError = orderQueries.some((query) => query.isError)
  const orders = orderQueries.flatMap((query) => query.data ?? [])
  const filteredOrders = useMemo(
    () => orders.filter((order) => order.symbol.toLowerCase().includes(symbolFilter.trim().toLowerCase())),
    [orders, symbolFilter],
  )

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Orders"
        title="Order queue"
        description="The paper cockpit now has actual order surfaces. You can filter by state, scan both asset classes, and cancel individual open orders without leaving the table lane."
        actions={
          <div className="toolbar-row">
            <label className="field field--inline">
              <span>Status</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as OrderStatus | 'all')}>
                <option value="all">All</option>
                <option value="open">Open</option>
                <option value="filled">Filled</option>
                <option value="canceled">Canceled</option>
              </select>
            </label>
            <label className="field field--inline field--grow">
              <span>Symbol search</span>
              <input
                value={symbolFilter}
                onChange={(event) => setSymbolFilter(event.target.value)}
                placeholder="BTCUSD, AAPL, TSLA…"
              />
            </label>
          </div>
        }
      >
        <div className="stack-list">
          <div className="toolbar-strip">
            <div className="stack-inline stack-inline--tight muted">
              <ArrowUpDown size={16} />
              <span>Showing {filteredOrders.length} orders across stock and crypto paper accounts.</span>
            </div>
            <div className="stack-inline stack-inline--tight muted">
              <ScrollText size={16} />
              <span>Open rows expose a direct cancel action.</span>
            </div>
          </div>

          <QueryState
            isLoading={isLoading}
            isError={isError}
            isEmpty={filteredOrders.length === 0}
            loadingLabel="Loading order rows…"
            errorLabel="Unable to load paper orders."
            emptyLabel="No orders match the current filters."
          >
            <div className="table-card">
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Quantity</th>
                      <th>Avg fill</th>
                      <th>Reserved</th>
                      <th>Updated</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOrders.map((order) => (
                      <OrderRow
                        key={order.id}
                        order={order}
                        isBusy={cancelOrderMutation.isPending}
                        onCancel={(assetClass, orderId) => cancelOrderMutation.mutate({ assetClass, orderId })}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </QueryState>
        </div>
      </PageSection>
    </div>
  )
}

interface OrderRowProps {
  order: OrderRecord
  isBusy: boolean
  onCancel: (assetClass: AssetClass, orderId: string) => void
}

function OrderRow({ order, isBusy, onCancel }: OrderRowProps) {
  const canCancel = order.status === 'open'

  return (
    <tr>
      <td>
        <span className="status-pill">{order.asset_class}</span>
      </td>
      <td>
        <strong>{order.symbol}</strong>
      </td>
      <td>{titleCase(order.side)}</td>
      <td>{titleCase(order.order_type)}</td>
      <td>
        <span className={`status-pill ${order.status === 'open' ? 'status-pill--good' : ''}`}>{titleCase(order.status)}</span>
      </td>
      <td>{formatQuantity(order.quantity)}</td>
      <td>{order.average_fill_price ? formatMoney(order.average_fill_price) : '—'}</td>
      <td>{Number(order.reserved_cash) > 0 ? formatMoney(order.reserved_cash) : formatQuantity(order.reserved_quantity)}</td>
      <td>{formatTimestamp(order.updated_at)}</td>
      <td>
        {canCancel ? (
          <button type="button" className="button button--ghost" disabled={isBusy} onClick={() => onCancel(order.asset_class, order.id)}>
            Cancel
          </button>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
    </tr>
  )
}
