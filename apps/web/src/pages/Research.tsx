import { useEffect, useState } from 'react'
import {
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  FlaskConical,
  GitBranch,
  Lightbulb,
  Loader2,
  Search,
  Send,
  Target,
  Trash2,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { researchApi } from '@/api/services'
import type { ResearchGoal } from '@/api/types'

const GOAL_SUGGESTIONS = [
  { text: '研究动量因子的选股能力', icon: <BarChart3 className="h-4 w-4" /> },
  { text: '分析当前市场情绪和行业轮动', icon: <TrendingUp className="h-4 w-4" /> },
  { text: '评估组合风险暴露和优化建议', icon: <FlaskConical className="h-4 w-4" /> },
  { text: '寻找近期表现优异的Alpha因子', icon: <Target className="h-4 w-4" /> },
  { text: '分析北向资金流向对市场的影响', icon: <Zap className="h-4 w-4" /> },
  { text: '构建低波动率稳健组合策略', icon: <GitBranch className="h-4 w-4" /> },
]

const TOOL_ICONS: Record<string, JSX.Element> = {
  data_sync: <BarChart3 className="h-3.5 w-3.5" />,
  factor_engine: <BarChart3 className="h-3.5 w-3.5" />,
  sentiment: <Zap className="h-3.5 w-3.5" />,
  market_data: <TrendingUp className="h-3.5 w-3.5" />,
  backtest: <FlaskConical className="h-3.5 w-3.5" />,
  llm: <Brain className="h-3.5 w-3.5" />,
}

const TOOL_COLORS: Record<string, string> = {
  data_sync: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  factor_engine: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400',
  sentiment: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400',
  market_data: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
  backtest: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
  llm: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400',
}

export default function Research() {
  const [goals, setGoals] = useState<ResearchGoal[]>([])
  const [selectedGoal, setSelectedGoal] = useState<ResearchGoal | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)

  useEffect(() => {
    fetchGoals()
  }, [])

  async function fetchGoals() {
    setFetching(true)
    try {
      const res = await researchApi.listGoals()
      if (res.data?.success && res.data.data) {
        setGoals(res.data.data)
        if (res.data.data.length > 0 && !selectedGoal) {
          setSelectedGoal(res.data.data[0])
        }
      }
    } catch { /* ignore */ }
    setFetching(false)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || loading) return

    setLoading(true)
    try {
      const res = await researchApi.createGoal(input.trim())
      if (res.data?.success && res.data.data) {
        const newGoal = res.data.data
        setGoals(prev => [newGoal, ...prev])
        setSelectedGoal(newGoal)
        setInput('')
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  async function handleDelete(goalId: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await researchApi.deleteGoal(goalId)
      setGoals(prev => prev.filter(g => g.id !== goalId))
      if (selectedGoal?.id === goalId) {
        setSelectedGoal(goals.find(g => g.id !== goalId) || null)
      }
    } catch { /* ignore */ }
  }

  function handleSuggestion(text: string) {
    setInput(text)
  }

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    } catch { return '' }
  }

  return (
    <div className="flex h-full gap-0">
      {/* Left: Goal list */}
      <div className="flex w-80 flex-col border-r border-gray-200 dark:border-gray-700">
        <div className="border-b border-gray-200 p-4 dark:border-gray-700">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <Brain className="h-4 w-4 text-primary-500" />
            AI 研究目标
          </h2>
          <p className="mt-1 text-xs text-gray-500">输入自然语言研究目标，AI 自动规划并执行</p>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="border-b border-gray-200 p-3 dark:border-gray-700">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="描述你的研究目标..."
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>

          {/* Suggestions */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {GOAL_SUGGESTIONS.slice(0, 3).map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSuggestion(s.text)}
                className="flex items-center gap-1 rounded-md bg-gray-100 px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              >
                {s.icon}
                <span className="max-w-[100px] truncate">{s.text}</span>
              </button>
            ))}
          </div>
        </form>

        {/* Goal list */}
        <div className="flex-1 overflow-y-auto">
          {fetching && goals.length === 0 ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : goals.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-gray-400">
              暂无研究目标
            </div>
          ) : (
            <div className="space-y-0.5 p-2">
              {goals.map(goal => (
                <button
                  key={goal.id}
                  onClick={() => setSelectedGoal(goal)}
                  className={`group flex w-full items-start gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors ${
                    selectedGoal?.id === goal.id
                      ? 'bg-primary-50 dark:bg-primary-950/30'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                  }`}
                >
                  <div className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded ${
                    goal.status === 'completed'
                      ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400'
                  }`}>
                    {goal.status === 'completed' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-gray-900 dark:text-white">{goal.goal}</p>
                    <p className="mt-0.5 text-[10px] text-gray-400">{formatTime(goal.created_at)}</p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(goal.id, e)}
                    className="flex-shrink-0 rounded p-1 text-gray-400 opacity-0 hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:hover:bg-red-950/30"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right: Goal detail */}
      <div className="flex-1 overflow-y-auto">
        {!selectedGoal ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <Brain className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-3 text-sm font-medium text-gray-500">选择或创建研究目标</p>
              <p className="mt-1 text-xs text-gray-400">AI 将自动规划研究步骤并执行分析</p>
              <div className="mt-6 grid max-w-sm grid-cols-2 gap-2">
                {GOAL_SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(s.text); }}
                    className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-left text-xs text-gray-600 transition-colors hover:border-primary-300 hover:bg-primary-50 dark:border-gray-700 dark:text-gray-400 dark:hover:border-primary-600 dark:hover:bg-primary-950/30"
                  >
                    {s.icon}
                    <span className="line-clamp-1">{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6">
            {/* Header */}
            <div className="mb-6">
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  selectedGoal.status === 'completed'
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                    : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400'
                }`}>
                  {selectedGoal.status === 'completed' ? '已完成' : '执行中'}
                </span>
                <span className="text-[11px] text-gray-400">{formatTime(selectedGoal.created_at)}</span>
              </div>
              <h1 className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
                {selectedGoal.goal}
              </h1>
            </div>

            {/* Research Plan */}
            <div className="mb-6">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-200">
                <FileText className="h-4 w-4 text-primary-500" />
                研究计划
              </h2>
              <div className="space-y-2">
                {selectedGoal.plan.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-lg border border-gray-100 bg-white p-3 dark:border-gray-800 dark:bg-gray-800/50"
                  >
                    <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md ${
                      TOOL_COLORS[step.tool] || 'bg-gray-100 text-gray-500'
                    }`}>
                      {TOOL_ICONS[step.tool] || <Search className="h-3.5 w-3.5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-gray-900 dark:text-white">
                          Step {step.step}: {step.name}
                        </span>
                        <CheckCircle2 className="h-3 w-3 text-green-500" />
                      </div>
                      <p className="mt-0.5 text-xs text-gray-500">{step.description}</p>
                    </div>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-700">
                      {step.tool}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Results */}
            {selectedGoal.results.length > 0 && (
              <div className="mb-6">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-200">
                  <BarChart3 className="h-4 w-4 text-primary-500" />
                  执行结果
                </h2>
                <div className="space-y-2">
                  {selectedGoal.results.map((result, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-gray-100 bg-white p-3 dark:border-gray-800 dark:bg-gray-800/50"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-gray-900 dark:text-white">{result.name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-400">{result.duration_ms}ms</span>
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                        </div>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-gray-600 dark:text-gray-400">
                        {result.output}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Insights */}
            {selectedGoal.insights.length > 0 && (
              <div>
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-200">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  研究洞察
                </h2>
                <div className="space-y-2">
                  {selectedGoal.insights.map((insight, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 rounded-lg border border-yellow-100 bg-yellow-50 p-3 dark:border-yellow-900/30 dark:bg-yellow-950/20"
                    >
                      <ChevronRight className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-yellow-500" />
                      <p className="text-xs leading-relaxed text-gray-700 dark:text-gray-300">{insight}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
