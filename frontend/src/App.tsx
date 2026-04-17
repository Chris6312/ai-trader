import { useEffect, useMemo, useState } from 'react'

import { APP_ROUTES, DEFAULT_ROUTE, isAppRouteKey, type AppRouteKey } from './app/navigation'
import { AppShell } from './components/AppShell'
import { AccountsPage } from './pages/AccountsPage'
import { ControlsPage } from './pages/ControlsPage'
import { DashboardPage } from './pages/DashboardPage'
import { LogsPage } from './pages/LogsPage'
import { OrdersPage } from './pages/OrdersPage'
import { PositionsPage } from './pages/PositionsPage'

function getRouteFromHash(hash: string): AppRouteKey {
  const normalized = hash.replace(/^#\/?/, '')
  return isAppRouteKey(normalized) ? normalized : DEFAULT_ROUTE
}

function renderRoute(route: AppRouteKey) {
  switch (route) {
    case 'accounts':
      return <AccountsPage />
    case 'orders':
      return <OrdersPage />
    case 'positions':
      return <PositionsPage />
    case 'controls':
      return <ControlsPage />
    case 'logs':
      return <LogsPage />
    case 'dashboard':
    default:
      return <DashboardPage />
  }
}

function App() {
  const [activeRoute, setActiveRoute] = useState<AppRouteKey>(() => getRouteFromHash(window.location.hash))
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  useEffect(() => {
    const onHashChange = () => {
      setActiveRoute(getRouteFromHash(window.location.hash))
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const activeDefinition = useMemo(
    () => APP_ROUTES.find((item) => item.key === activeRoute) ?? APP_ROUTES[0],
    [activeRoute],
  )

  const handleNavigate = (route: AppRouteKey) => {
    window.location.hash = route
    setActiveRoute(route)
    setSidebarOpen(false)
  }

  return (
    <AppShell
      activeRoute={activeRoute}
      route={activeDefinition}
      onNavigate={handleNavigate}
      sidebarOpen={sidebarOpen}
      sidebarCollapsed={sidebarCollapsed}
      onToggleSidebar={() => setSidebarOpen((current) => !current)}
      onToggleCollapse={() => setSidebarCollapsed((current) => !current)}
    >
      {renderRoute(activeRoute)}
    </AppShell>
  )
}

export default App
