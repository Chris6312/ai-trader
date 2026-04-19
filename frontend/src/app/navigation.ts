import {
  Activity,
  BadgeDollarSign,
  BookOpenText,
  BrainCircuit,
  CandlestickChart,
  LayoutDashboard,
  ListChecks,
  type LucideIcon,
} from 'lucide-react'

export type AppRouteKey =
  | 'dashboard'
  | 'accounts'
  | 'orders'
  | 'positions'
  | 'controls'
  | 'logs'
  | 'ml'

export interface AppRouteDefinition {
  key: AppRouteKey
  label: string
  shortLabel: string
  icon: LucideIcon
}

export const APP_ROUTES: AppRouteDefinition[] = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    shortLabel: 'Home',
    icon: LayoutDashboard,
  },
  {
    key: 'accounts',
    label: 'Accounts',
    shortLabel: 'Acct',
    icon: BadgeDollarSign,
  },
  {
    key: 'orders',
    label: 'Orders',
    shortLabel: 'Orders',
    icon: CandlestickChart,
  },
  {
    key: 'positions',
    label: 'Positions',
    shortLabel: 'Pos',
    icon: Activity,
  },
  {
    key: 'ml',
    label: 'ML Transparency',
    shortLabel: 'ML',
    icon: BrainCircuit,
  },
  {
    key: 'controls',
    label: 'Controls',
    shortLabel: 'Ctrl',
    icon: ListChecks,
  },
  {
    key: 'logs',
    label: 'Logs',
    shortLabel: 'Logs',
    icon: BookOpenText,
  },
]

export const DEFAULT_ROUTE: AppRouteKey = 'dashboard'

export function isAppRouteKey(value: string): value is AppRouteKey {
  return APP_ROUTES.some((route) => route.key === value)
}
