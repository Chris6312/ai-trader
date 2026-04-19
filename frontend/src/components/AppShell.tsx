import { Menu, PanelLeftClose, PanelLeftOpen, Search } from 'lucide-react'
import type { ReactNode } from 'react'

import { APP_ROUTES, type AppRouteDefinition, type AppRouteKey } from '../app/navigation'

interface AppShellProps {
  activeRoute: AppRouteKey
  route: AppRouteDefinition
  onNavigate: (route: AppRouteKey) => void
  children: ReactNode
  sidebarOpen: boolean
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  onToggleCollapse: () => void
}

export function AppShell({
  activeRoute,
  route,
  onNavigate,
  children,
  sidebarOpen,
  sidebarCollapsed,
  onToggleSidebar,
  onToggleCollapse,
}: AppShellProps) {
  return (
    <div className="shell">
      <aside
        className={[
          'sidebar',
          sidebarOpen ? 'sidebar--open' : '',
          sidebarCollapsed ? 'sidebar--collapsed' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <div className="sidebar__brand-wrap">
          <div className="sidebar__brand">
            <div className="brand-mark">AI</div>
            {!sidebarCollapsed ? (
              <div>
                <p className="eyebrow">Paper cockpit</p>
                <h1>AI-Trader v1</h1>
              </div>
            ) : null}
          </div>
          {!sidebarCollapsed ? <span className="status-pill status-pill--good">Paper environment</span> : null}
        </div>

        <nav className="sidebar__nav" aria-label="Primary">
          {APP_ROUTES.map((item) => {
            const Icon = item.icon
            const isActive = item.key === activeRoute
            return (
              <button
                key={item.key}
                type="button"
                className={`sidebar__nav-item ${isActive ? 'is-active' : ''}`}
                onClick={() => onNavigate(item.key)}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <Icon size={18} />
                {!sidebarCollapsed ? <strong>{item.label}</strong> : null}
              </button>
            )
          })}
        </nav>

      </aside>

      <div className="shell__backdrop" hidden={!sidebarOpen} onClick={onToggleSidebar} />

      <div className="shell__main">
        <header className="topbar panel panel--soft">
          <div className="topbar__left">
            <button type="button" className="icon-button mobile-only" onClick={onToggleSidebar}>
              <Menu size={18} />
            </button>
            <button type="button" className="icon-button desktop-only" onClick={onToggleCollapse}>
              {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <div>
              <p className="eyebrow">Paper broker views</p>
              <h2>{route.label}</h2>
            </div>
          </div>

          <div className="topbar__right">
            <div className="search-pill">
              <Search size={16} />
              <span>Search coming later</span>
            </div>
            <span className="status-pill">America/New_York</span>
            <span className="status-pill status-pill--good">Paper mode</span>
          </div>
        </header>

        <main className="view">{children}</main>
      </div>
    </div>
  )
}
