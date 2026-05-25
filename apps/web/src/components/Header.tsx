import { useLocation } from 'react-router-dom'
import { Activity, Menu, Moon, Search, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/market': 'Market',
  '/factors': 'Factor Lab',
  '/strategy': 'Strategy Lab',
  '/alpha': 'Alpha Explorer',
  '/backtest': 'Backtests',
  '/agent': 'Agents',
  '/workflow': 'Workflow',
  '/trace': 'Trace',
  '/memory': 'Memory',
  '/prompts': 'Prompts',
  '/reports': 'Reports',
  '/sentiment': 'Market Breadth',
  '/research': 'AI Research',
  '/portfolio': 'Portfolio',
  '/risk': 'Risk',
  '/attribution': 'Attribution',
  '/providers': 'Providers',
  '/datasources': 'Data Sources',
  '/factorstore': 'Factor Store',
  '/cache': 'Cache',
  '/dataquality': 'Data Quality',
  '/models': 'Models',
  '/apikeys': 'API Keys',
  '/logs': 'Logs',
  '/monitoring': 'Monitoring',
  '/settings': 'Settings',
}

interface HeaderProps {
  onMenuClick: () => void
  onEventStreamToggle?: () => void
  eventStreamOpen?: boolean
}

export default function Header({ onMenuClick, onEventStreamToggle, eventStreamOpen }: HeaderProps) {
  const location = useLocation()
  const [isDark, setIsDark] = useState(false)
  const title = pageTitles[location.pathname] || 'QuantOS'

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'))
  }, [])

  const toggleDarkMode = () => {
    const next = !isDark
    setIsDark(next)
    document.documentElement.classList.toggle('dark', next)
  }

  return (
    <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/90 backdrop-blur dark:border-gray-800 dark:bg-gray-900/90">
      <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            aria-label="打开导航"
            className="rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800 lg:hidden"
            onClick={onMenuClick}
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="truncate text-lg font-semibold text-gray-950 dark:text-white sm:text-xl">
            {title}
          </h1>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div className="relative hidden sm:block">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="搜索..."
              onClick={() => {
                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))
              }}
              readOnly
              className="h-10 w-56 cursor-pointer rounded-md border border-gray-300 bg-gray-50 pl-9 pr-12 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
            />
            <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] text-gray-400 dark:border-gray-600 dark:bg-gray-700">
              {'⌘'}K
            </kbd>
          </div>
          <button
            type="button"
            aria-label="切换深色模式"
            onClick={toggleDarkMode}
            className="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-white"
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          {onEventStreamToggle && (
            <button
              type="button"
              aria-label="事件流"
              onClick={onEventStreamToggle}
              className={`rounded-md p-2 transition-colors ${
                eventStreamOpen
                  ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-400'
                  : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-300 dark:hover:bg-gray-800'
              }`}
            >
              <Activity className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
