import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  Brain,
  Cable,
  Database,
  FileText,
  FlaskConical,
  GitBranch,
  Key,
  LayoutDashboard,
  LineChart,
  MemoryStick,
  MessageSquare,
  PieChart,
  Radio,
  ScrollText,
  Search,
  Settings,
  Shield,
  TrendingUp,
  Zap,
} from 'lucide-react'

interface Command {
  id: string
  name: string
  description: string
  icon: JSX.Element
  action: () => void
  keywords: string[]
  group: string
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const commands: Command[] = [
    // Dashboard
    { id: 'nav-dashboard', name: 'Dashboard', description: '系统首页', icon: <LayoutDashboard className="h-4 w-4" />, action: () => { navigate('/'); setOpen(false) }, keywords: ['dashboard', '首页', 'home'], group: '' },
    // Research
    { id: 'nav-market', name: 'Market', description: 'A股行情和K线图', icon: <TrendingUp className="h-4 w-4" />, action: () => { navigate('/market'); setOpen(false) }, keywords: ['market', '行情', 'k线', 'stock'], group: 'Research' },
    { id: 'nav-factors', name: 'Factor Lab', description: '因子库、表达式编辑器、IC分析', icon: <BarChart3 className="h-4 w-4" />, action: () => { navigate('/factors'); setOpen(false) }, keywords: ['factor', '因子', 'ic', 'alpha', 'lab'], group: 'Research' },
    { id: 'nav-strategy', name: 'Strategy Lab', description: '策略开发与测试', icon: <FlaskConical className="h-4 w-4" />, action: () => { navigate('/strategy'); setOpen(false) }, keywords: ['strategy', '策略'], group: 'Research' },
    { id: 'nav-alpha', name: 'Alpha Explorer', description: 'Alpha因子探索与发现', icon: <Search className="h-4 w-4" />, action: () => { navigate('/alpha'); setOpen(false) }, keywords: ['alpha', '探索', 'explorer'], group: 'Research' },
    { id: 'nav-reports', name: 'Reports', description: 'AI生成的研究报告', icon: <FileText className="h-4 w-4" />, action: () => { navigate('/reports'); setOpen(false) }, keywords: ['report', '报告', '研究'], group: 'Research' },
    // AI Workspace
    { id: 'nav-agent', name: 'Agents', description: 'AI研究助手', icon: <Bot className="h-4 w-4" />, action: () => { navigate('/agent'); setOpen(false) }, keywords: ['agent', 'ai', '助手', 'chat'], group: 'AI Workspace' },
    { id: 'nav-workflow', name: 'Workflow', description: 'DAG工作流编排和执行', icon: <GitBranch className="h-4 w-4" />, action: () => { navigate('/workflow'); setOpen(false) }, keywords: ['workflow', '工作流', 'dag'], group: 'AI Workspace' },
    { id: 'nav-trace', name: 'Trace', description: 'Agent执行追踪', icon: <Radio className="h-4 w-4" />, action: () => { navigate('/trace'); setOpen(false) }, keywords: ['trace', '追踪', '执行', '链路'], group: 'AI Workspace' },
    { id: 'nav-memory', name: 'Memory', description: 'Agent记忆与上下文管理', icon: <MemoryStick className="h-4 w-4" />, action: () => { navigate('/memory'); setOpen(false) }, keywords: ['memory', '记忆', '上下文'], group: 'AI Workspace' },
    { id: 'nav-prompts', name: 'Prompts', description: 'Prompt模板管理', icon: <MessageSquare className="h-4 w-4" />, action: () => { navigate('/prompts'); setOpen(false) }, keywords: ['prompt', '提示词', '模板'], group: 'AI Workspace' },
    // Analytics
    { id: 'nav-backtest', name: 'Backtests', description: '策略回测和绩效分析', icon: <LineChart className="h-4 w-4" />, action: () => { navigate('/backtest'); setOpen(false) }, keywords: ['backtest', '回测', '策略'], group: 'Analytics' },
    { id: 'nav-portfolio', name: 'Portfolio', description: '组合管理与调仓', icon: <PieChart className="h-4 w-4" />, action: () => { navigate('/portfolio'); setOpen(false) }, keywords: ['portfolio', '组合', '调仓'], group: 'Analytics' },
    { id: 'nav-risk', name: 'Risk', description: '风险分析与控制', icon: <Shield className="h-4 w-4" />, action: () => { navigate('/risk'); setOpen(false) }, keywords: ['risk', '风险', '回撤'], group: 'Analytics' },
    { id: 'nav-sentiment', name: 'Market Breadth', description: '涨跌停、北向资金、行业轮动', icon: <Zap className="h-4 w-4" />, action: () => { navigate('/sentiment'); setOpen(false) }, keywords: ['sentiment', '情绪', '涨停', '北向', 'breadth'], group: 'Analytics' },
    // Data
    { id: 'nav-providers', name: 'Providers', description: '数据源提供商管理', icon: <Cable className="h-4 w-4" />, action: () => { navigate('/providers'); setOpen(false) }, keywords: ['provider', '数据源'], group: 'Data' },
    { id: 'nav-datasources', name: 'Data Sources', description: '数据源配置与管理', icon: <Database className="h-4 w-4" />, action: () => { navigate('/datasources'); setOpen(false) }, keywords: ['data', '数据'], group: 'Data' },
    // System
    { id: 'nav-models', name: 'Models', description: 'LLM模型配置', icon: <Brain className="h-4 w-4" />, action: () => { navigate('/models'); setOpen(false) }, keywords: ['model', '模型', 'llm'], group: 'System' },
    { id: 'nav-apikeys', name: 'API Keys', description: 'API密钥管理', icon: <Key className="h-4 w-4" />, action: () => { navigate('/apikeys'); setOpen(false) }, keywords: ['api', 'key', '密钥'], group: 'System' },
    { id: 'nav-logs', name: 'Logs', description: '系统日志', icon: <ScrollText className="h-4 w-4" />, action: () => { navigate('/logs'); setOpen(false) }, keywords: ['log', '日志'], group: 'System' },
    { id: 'nav-settings', name: 'Settings', description: '系统设置', icon: <Settings className="h-4 w-4" />, action: () => { navigate('/settings'); setOpen(false) }, keywords: ['setting', '设置', '配置'], group: 'System' },
    { id: 'nav-research', name: 'AI Research', description: 'AI自主研究，自然语言目标驱动', icon: <Brain className="h-4 w-4" />, action: () => { navigate('/research'); setOpen(false) }, keywords: ['research', '研究', 'ai', 'goal', '目标'], group: '' },
  ]

  const filtered = commands.filter(cmd => {
    if (!query) return true
    const q = query.toLowerCase()
    return (
      cmd.name.toLowerCase().includes(q) ||
      cmd.description.toLowerCase().includes(q) ||
      cmd.keywords.some(k => k.includes(q))
    )
  })

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(v => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault()
      filtered[selectedIndex].action()
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-lg overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900">
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-gray-200 px-4 dark:border-gray-700">
          <Search className="h-5 w-5 text-gray-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索命令、页面、功能..."
            className="h-12 flex-1 bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400 dark:text-white"
          />
          <kbd className="hidden rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:border-gray-600 dark:bg-gray-800 sm:inline">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">无匹配结果</div>
          ) : (
            <div className="space-y-0.5">
              {filtered.map((cmd, i) => (
                <button
                  key={cmd.id}
                  onClick={cmd.action}
                  onMouseEnter={() => setSelectedIndex(i)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                    i === selectedIndex
                      ? 'bg-primary-50 dark:bg-primary-950/30'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                  }`}
                >
                  <div className={`flex h-8 w-8 items-center justify-center rounded-md ${
                    i === selectedIndex
                      ? 'bg-primary-100 text-primary-600 dark:bg-primary-900/50 dark:text-primary-400'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
                  }`}>
                    {cmd.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium ${
                      i === selectedIndex ? 'text-primary-700 dark:text-primary-300' : 'text-gray-900 dark:text-white'
                    }`}>
                      {cmd.name}
                    </p>
                    <p className="text-xs text-gray-500">{cmd.description}</p>
                  </div>
                  {cmd.group && (
                    <span className="text-[10px] text-gray-400">{cmd.group}</span>
                  )}
                  {i === selectedIndex && (
                    <kbd className="rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] text-gray-400 dark:border-gray-600 dark:bg-gray-800">
                      Enter
                    </kbd>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-2 dark:border-gray-700">
          <div className="flex items-center gap-3 text-[10px] text-gray-400">
            <span><kbd className="rounded border border-gray-200 bg-gray-100 px-1 dark:border-gray-600 dark:bg-gray-800">↑↓</kbd> 导航</span>
            <span><kbd className="rounded border border-gray-200 bg-gray-100 px-1 dark:border-gray-600 dark:bg-gray-800">Enter</kbd> 选择</span>
            <span><kbd className="rounded border border-gray-200 bg-gray-100 px-1 dark:border-gray-600 dark:bg-gray-800">Esc</kbd> 关闭</span>
          </div>
          <span className="text-[10px] text-gray-400">QuantOS Command Palette</span>
        </div>
      </div>
    </div>
  )
}
