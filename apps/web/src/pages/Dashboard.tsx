import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  FlaskConical,
  GitBranch,
  LineChart,
  Radio,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { eventBus } from '@/lib/eventBus'

const stats = [
  { name: '可用股票', value: '6', change: 'Synthetic + Provider', icon: TrendingUp, href: '/market' },
  { name: '内置因子', value: '50+', change: 'Alpha / 技术 / 流动性', icon: BarChart3, href: '/factors' },
  { name: '回测链路', value: '已打通', change: '因子排序信号', icon: FlaskConical, href: '/backtest' },
  { name: 'AI Agent', value: 'Mimo', change: 'OpenAI 兼容接口', icon: Bot, href: '/agent' },
]

const systemStatus = [
  { name: 'Market Live', status: 'online', detail: 'AKShare' },
  { name: 'Agent Online', status: 'online', detail: 'DeepSeek V3' },
  { name: 'Factor Engine', status: 'ready', detail: 'v0.2.1' },
  { name: 'Backtest Engine', status: 'ready', detail: 'Qlib+Backtrader' },
  { name: 'EventBus', status: 'online', detail: 'WebSocket' },
  { name: 'Data Provider', status: 'online', detail: 'AKShare + Synthetic' },
]

const marketOverview = [
  { name: '上证指数', value: '3,124.56', change: '+0.85%', positive: true },
  { name: '沪深300', value: '3,708.22', change: '+0.64%', positive: true },
  { name: '创业板指', value: '2,012.34', change: '-0.45%', positive: false },
  { name: '科创50', value: '987.65', change: '+2.15%', positive: true },
]

const quickActions = [
  { label: 'Factor Lab', desc: '因子研究与IC分析', icon: BarChart3, href: '/factors' },
  { label: 'Workflow', desc: 'DAG工作流执行', icon: GitBranch, href: '/workflow' },
  { label: 'Backtest', desc: '策略回测与绩效', icon: FlaskConical, href: '/backtest' },
  { label: 'AI Research', desc: 'AI自主研究', icon: Brain, href: '/research' },
  { label: 'Trace', desc: 'Agent执行追踪', icon: Radio, href: '/trace' },
  { label: 'Market Breadth', desc: '市场情绪分析', icon: Zap, href: '/sentiment' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [eventCount, setEventCount] = useState(0)

  useEffect(() => {
    document.title = 'Dashboard - QuantOS'
    const unsub = eventBus.on('*', () => setEventCount(c => c + 1))
    return unsub
  }, [])

  return (
    <div className="space-y-4">
      {/* System Status Bar */}
      <Card variant="bordered">
        <CardContent className="p-3">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">System</span>
            {systemStatus.map((s) => (
              <div key={s.name} className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${
                  s.status === 'online' ? 'bg-green-500' : s.status === 'ready' ? 'bg-blue-500' : 'bg-gray-400'
                }`} />
                <span className="text-xs text-gray-700 dark:text-gray-300">{s.name}</span>
                <span className="text-[10px] text-gray-400">{s.detail}</span>
              </div>
            ))}
            <div className="ml-auto flex items-center gap-1.5 text-[10px] text-gray-400">
              <Activity className="h-3 w-3" />
              <span>{eventCount} events</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <button
            key={stat.name}
            onClick={() => navigate(stat.href)}
            className="text-left"
          >
            <Card variant="bordered" className="transition-colors hover:border-primary-300 dark:hover:border-primary-700">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                    <p className="mt-1 text-2xl font-semibold text-gray-950 dark:text-white">{stat.value}</p>
                    <p className="mt-0.5 text-xs text-gray-500">{stat.change}</p>
                  </div>
                  <div className="rounded-md bg-primary-50 p-2 text-primary-700 dark:bg-primary-950 dark:text-primary-300">
                    <stat.icon className="h-5 w-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.15fr]">
        {/* Market overview */}
        <Card variant="bordered">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-primary-500" />
              市场概览
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {marketOverview.map((item) => (
                <div key={item.name} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                  <span className="text-sm font-medium text-gray-800 dark:text-gray-100">{item.name}</span>
                  <div className="text-right">
                    <span className="mr-3 font-mono text-sm text-gray-950 dark:text-white">{item.value}</span>
                    <span className={`font-mono text-sm font-medium ${item.positive ? 'text-green-600' : 'text-red-600'}`}>
                      {item.change}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card variant="bordered">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-base">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => navigate(action.href)}
                  className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-left transition-all hover:border-primary-300 hover:bg-primary-50 dark:border-gray-700 dark:bg-gray-800/50 dark:hover:border-primary-700 dark:hover:bg-primary-950/30"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-gray-100 dark:bg-gray-800">
                    <action.icon className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{action.label}</p>
                    <p className="text-[11px] text-gray-500">{action.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline status */}
      <Card variant="bordered">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <LineChart className="h-4 w-4 text-primary-500" />
            Research Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {['Data Agent', 'Factor Agent', 'Backtest Agent', 'Risk Agent', 'Research Agent', 'Portfolio Agent'].map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800/50">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  <span className="whitespace-nowrap text-xs font-medium text-gray-700 dark:text-gray-300">{step}</span>
                </div>
                {i < 5 && (
                  <div className="h-px w-6 bg-gray-300 dark:bg-gray-600" />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
