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
  description: string
  icon: LucideIcon
}

export const APP_ROUTES: AppRouteDefinition[] = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    shortLabel: 'Home',
    description: 'Session pulse, shell health, and quick-glance broker status.',
    icon: LayoutDashboard,
  },
  {
    key: 'accounts',
    label: 'Accounts',
    shortLabel: 'Acct',
    description: 'Paper account balances, equity posture, and readiness panels.',
    icon: BadgeDollarSign,
  },
  {
    key: 'orders',
    label: 'Orders',
    shortLabel: 'Orders',
    description: 'Open orders, order states, and forthcoming order filters.',
    icon: CandlestickChart,
  },
  {
    key: 'positions',
    label: 'Positions',
    shortLabel: 'Pos',
    description: 'Open paper positions, exposure, and detail drawers to come.',
    icon: Activity,
  },
  {
    key: 'ml',
    label: 'ML Transparency',
    shortLabel: 'ML',
    description: 'Model registry, feature importance, drift review, and row explanations.',
    icon: BrainCircuit,
  },
  {
    key: 'controls',
    label: 'Controls',
    shortLabel: 'Ctrl',
    description: 'Operator actions for reset, wipe, close, and account controls.',
    icon: ListChecks,
  },
  {
    key: 'logs',
    label: 'Logs',
    shortLabel: 'Logs',
    description: 'Audit trails, action history, and backend event visibility.',
    icon: BookOpenText,
  },
]

export const DEFAULT_ROUTE: AppRouteKey = 'dashboard'

export function isAppRouteKey(value: string): value is AppRouteKey {
  return APP_ROUTES.some((route) => route.key === value)
}
