import { useMemo, useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { LayoutList, ScanSearch } from 'lucide-react'

import { type AssetClass, type PositionRecord, fetchPaperPositions } from '../api/paperAccounts'
import { PageSection } from '../components/PageSection'
import { QueryState } from '../components/QueryState'
import { formatMoney, formatQuantity, formatSignedMoney, formatTimestamp } from '../lib/formatters'

const ASSET_CLASSES: AssetClass[] = ['stock', 'crypto']

export function PositionsPage() {
  const [assetFilter, setAssetFilter] = useState<AssetClass | 'all'>('all')
  const positionQueries = useQueries({
    queries: ASSET_CLASSES.map((assetClass) => ({
      queryKey: ['paper-positions', assetClass],
      queryFn: () => fetchPaperPositions(assetClass),
      refetchInterval: 15_000,
    })),
  })

  const isLoading = positionQueries.some((query) => query.isLoading)
  const isError = positionQueries.some((query) => query.isError)
  const positions = positionQueries.flatMap((query) => query.data ?? [])
  const filteredPositions = useMemo(
    () => positions.filter((position) => assetFilter === 'all' || position.asset_class === assetFilter),
    [assetFilter, positions],
  )

  return (
    <div className="page-grid">
      <PageSection
        eyebrow="Positions"
        title="Position watchfloor"
        description="Open paper positions now render in a proper table lane with exposure, pricing, and unrealized PnL. The layout still keeps space for deeper inspect drawers later."
        actions={
          <div className="toolbar-row">
            <label className="field field--inline">
              <span>Asset class</span>
              <select value={assetFilter} onChange={(event) => setAssetFilter(event.target.value as AssetClass | 'all')}>
                <option value="all">All</option>
                <option value="stock">Stock</option>
                <option value="crypto">Crypto</option>
              </select>
            </label>
          </div>
        }
      >
        <div className="stack-list">
          <div className="toolbar-strip">
            <div className="stack-inline stack-inline--tight muted">
              <LayoutList size={16} />
              <span>{filteredPositions.length} live paper positions visible.</span>
            </div>
            <div className="stack-inline stack-inline--tight muted">
              <ScanSearch size={16} />
              <span>Drawer-ready lane preserved for later inspection depth.</span>
            </div>
          </div>

          <QueryState
            isLoading={isLoading}
            isError={isError}
            isEmpty={filteredPositions.length === 0}
            loadingLabel="Loading position rows…"
            errorLabel="Unable to load paper positions."
            emptyLabel="No open paper positions are currently active."
          >
            <div className="table-card">
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Symbol</th>
                      <th>Quantity</th>
                      <th>Reserved</th>
                      <th>Avg entry</th>
                      <th>Market price</th>
                      <th>Market value</th>
                      <th>Unrealized PnL</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPositions.map((position) => (
                      <PositionRow key={`${position.asset_class}-${position.symbol}`} position={position} />
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

function PositionRow({ position }: { position: PositionRecord }) {
  const pnlValue = Number(position.unrealized_pnl)

  return (
    <tr>
      <td>
        <span className="status-pill">{position.asset_class}</span>
      </td>
      <td>
        <strong>{position.symbol}</strong>
      </td>
      <td>{formatQuantity(position.quantity)}</td>
      <td>{formatQuantity(position.reserved_quantity)}</td>
      <td>{formatMoney(position.average_entry_price)}</td>
      <td>{formatMoney(position.market_price)}</td>
      <td>{formatMoney(position.market_value)}</td>
      <td>
        <span className={pnlValue >= 0 ? 'text-good' : 'text-danger'}>{formatSignedMoney(position.unrealized_pnl)}</span>
      </td>
      <td>{formatTimestamp(position.updated_at)}</td>
    </tr>
  )
}
