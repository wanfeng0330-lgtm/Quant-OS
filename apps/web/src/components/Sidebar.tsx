import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  Brain,
  Cable,
  Database,
  FileText,
  FlaskConical,
  GitBranch,
  HardDrive,
  Key,
  LayoutDashboard,
  LineChart,
  MemoryStick,
  MessageSquare,
  PieChart,
  Radio,
  ScrollText,
  Search,
  Server,
  Settings,
  Shield,
  TrendingUp,
  Workflow,
  X,
  Zap,
} from 'lucide-react'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    label: '',
    items: [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    ],
  },
  {
    label: 'Research',
    items: [
      { name: 'Market', href: '/market', icon: TrendingUp },
      { name: 'Factor Lab', href: '/factors', icon: BarChart3 },
      { name: 'Strategy Lab', href: '/strategy', icon: FlaskConical },
      { name: 'Alpha Explorer', href: '/alpha', icon: Search },
      { name: 'Reports', href: '/reports', icon: FileText },
    ],
  },
  {
    label: 'AI Workspace',
    items: [
      { name: 'Agents', href: '/agent', icon: Bot },
      { name: 'Workflow', href: '/workflow', icon: GitBranch },
      { name: 'Trace', href: '/trace', icon: Radio },
      { name: 'Memory', href: '/memory', icon: MemoryStick },
      { name: 'Prompts', href: '/prompts', icon: MessageSquare },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { name: 'Backtests', href: '/backtest', icon: LineChart },
      { name: 'Portfolio', href: '/portfolio', icon: PieChart },
      { name: 'Risk', href: '/risk', icon: Shield },
      { name: 'Attribution', href: '/attribution', icon: BarChart3 },
      { name: 'Market Breadth', href: '/sentiment', icon: Zap },
    ],
  },
  {
    label: 'Data',
    items: [
      { name: 'Providers', href: '/providers', icon: Cable },
      { name: 'Data Sources', href: '/datasources', icon: Database },
      { name: 'Factor Store', href: '/factorstore', icon: HardDrive },
      { name: 'Cache', href: '/cache', icon: Server },
      { name: 'Data Quality', href: '/dataquality', icon: Workflow },
    ],
  },
  {
    label: 'System',
    items: [
      { name: 'Models', href: '/models', icon: Brain },
      { name: 'API Keys', href: '/apikeys', icon: Key },
      { name: 'Logs', href: '/logs', icon: ScrollText },
      { name: 'Monitoring', href: '/monitoring', icon: Radio },
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
  },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

function Brand() {
  return (
    <div className="flex h-14 items-center gap-2.5 border-b border-gray-200 px-4 dark:border-gray-800">
      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-600 text-xs font-bold text-white">
        Q
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-950 dark:text-white">QuantOS</p>
        <p className="text-[10px] text-gray-500 dark:text-gray-400">AI Quant Research Terminal</p>
      </div>
    </div>
  )
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  const toggleGroup = (label: string) => {
    setCollapsed(prev => ({ ...prev, [label]: !prev[label] }))
  }

  return (
    <nav className="flex-1 overflow-y-auto px-2 py-2">
      {navGroups.map((group) => (
        <div key={group.label || '__root'} className="mb-1">
          {group.label && (
            <button
              onClick={() => toggleGroup(group.label)}
              className="flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
            >
              <span className={`transition-transform ${collapsed[group.label] ? '-rotate-90' : ''}`}>
                ▾
              </span>
              {group.label}
            </button>
          )}
          {(!group.label || !collapsed[group.label]) && (
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.href}
                  to={item.href}
                  end={item.href === '/'}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    [
                      'flex min-h-[34px] items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium transition-colors',
                      isActive
                        ? 'bg-primary-50 text-primary-700 dark:bg-primary-950/50 dark:text-primary-300'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-950 dark:text-gray-400 dark:hover:bg-gray-800/50 dark:hover:text-white',
                    ].join(' ')
                  }
                >
                  <item.icon className="h-4 w-4 flex-none" aria-hidden="true" />
                  <span>{item.name}</span>
                </NavLink>
              ))}
            </div>
          )}
        </div>
      ))}
    </nav>
  )
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 lg:flex">
        <Brand />
        <Navigation />
        <div className="border-t border-gray-200 px-3 py-2.5 dark:border-gray-800">
          <div className="flex items-center gap-2 text-[11px] text-gray-400">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            <span>AKShare Connected</span>
            <span className="ml-auto">v0.2.1</span>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      <div className={`fixed inset-0 z-50 lg:hidden ${open ? 'block' : 'hidden'}`}>
        <button
          type="button"
          aria-label="关闭导航"
          className="absolute inset-0 bg-gray-950/40"
          onClick={onClose}
        />
        <aside className="relative h-full w-[min(20rem,88vw)] border-r border-gray-200 bg-white shadow-xl dark:border-gray-800 dark:bg-gray-900">
          <button
            type="button"
            aria-label="关闭导航"
            className="absolute right-3 top-3 rounded-md p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
          <Brand />
          <Navigation onNavigate={onClose} />
        </aside>
      </div>
    </>
  )
}
