import { useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  BookOpen,
  Code2,
  GitBranch,
  LineChart,
  Play,
  TrendingUp,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart as ReLineChart,
  Line,
  Legend,
  ReferenceLine,
} from 'recharts'
import { factorApi } from '@/api/services'
import { useFactorStore } from '@/store'
import { emit } from '@/lib/eventBus'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import type { Factor, FactorValue } from '@/api/types'

const factorCategories = [
  { id: 'all', name: '全部' },
  { id: 'alpha101', name: 'Alpha101' },
  { id: 'technical', name: '技术' },
  { id: 'liquidity', name: '流动性' },
  { id: 'fundamental', name: '基本面' },
  { id: 'custom', name: '自定义' },
]

const EXPRESSION_HELP = [
  { func: 'ts_mean(field, window)', desc: '滚动均值' },
  { func: 'ts_std(field, window)', desc: '滚动标准差' },
  { func: 'ts_max(field, window)', desc: '滚动最大值' },
  { func: 'ts_min(field, window)', desc: '滚动最小值' },
  { func: 'ts_rank(field, window)', desc: '滚动排名百分位' },
  { func: 'ts_delta(field, n)', desc: 'N日变化量' },
  { func: 'ts_corr(f1, f2, window)', desc: '滚动相关系数' },
  { func: 'rank(field)', desc: '截面排名百分位' },
  { func: 'delta(field, n)', desc: '差分' },
  { func: 'log(field)', desc: '对数' },
  { func: 'abs(field)', desc: '绝对值' },
  { func: 'decay_linear(field, w)', desc: '线性衰减加权' },
]

const PRESET_EXPRESSIONS = [
  { name: '动量因子 (20日)', expr: 'ts_mean(close, 20) / close - 1' },
  { name: '波动率因子', expr: 'ts_std(close, 20) / ts_mean(close, 20)' },
  { name: '量价背离', expr: 'ts_corr(close, volume, 20)' },
  { name: '价格位置', expr: '(close - ts_min(low, 20)) / (ts_max(high, 20) - ts_min(low, 20))' },
  { name: '成交额动量', expr: 'ts_mean(amount, 5) / ts_mean(amount, 20)' },
]

type TabKey = 'factors' | 'expression' | 'analysis'

export default function FactorEngine() {
  const { factors, loading, error, fetchFactors } = useFactorStore()
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedFactor, setSelectedFactor] = useState<Factor | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('factors')
  const [startDate, setStartDate] = useState('2025-06-01')
  const [endDate, setEndDate] = useState('2026-05-22')

  // Expression editor state
  const [expression, setExpression] = useState('ts_mean(close, 20) / ts_std(close, 20)')
  const [exprResult, setExprResult] = useState<FactorValue[]>([])
  const [exprLoading, setExprLoading] = useState(false)
  const [exprError, setExprError] = useState<string | null>(null)
  const [exprCoverage, setExprCoverage] = useState('')

  // IC analysis state
  const [icData, setIcData] = useState<{
    factor_name?: string
    ic_series: { date: string; ic: number; rank_ic: number }[]
    ic_mean: number
    ic_std: number
    icir: number
    rank_ic_mean: number
    ic_positive_ratio: number
    periods: number
  } | null>(null)
  const [icLoading, setIcLoading] = useState(false)

  // Layered returns state
  const [layeredData, setLayeredData] = useState<{
    factor_name?: string
    layers: { layer: number; avg_daily_return: number; cumulative_return: number; stocks_avg: number }[]
    long_short: { avg_daily_return: number; cumulative_return: number; sharpe: number; win_rate: number }
    total_periods: number
  } | null>(null)
  const [layeredLoading, setLayeredLoading] = useState(false)

  useEffect(() => {
    document.title = '因子实验室 - QuantOS'
    fetchFactors()
  }, [fetchFactors])

  const filteredFactors = selectedCategory === 'all'
    ? factors
    : selectedCategory === 'custom'
    ? factors.filter((f) => f.category === 'custom')
    : factors.filter((f) => f.category === selectedCategory)

  // Histogram data from expression results
  const histogramData = useMemo(() => {
    const values = exprResult
      .map((item) => item.value)
      .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
    if (values.length === 0) return []
    const min = Math.min(...values)
    const max = Math.max(...values)
    const binCount = Math.min(20, Math.max(5, Math.ceil(Math.sqrt(values.length))))
    const width = max === min ? 1 : (max - min) / binCount
    const bins = Array.from({ length: binCount }, (_, i) => ({
      value: Number((min + width * (i + 0.5)).toFixed(4)),
      count: 0,
    }))
    values.forEach((v) => {
      const idx = Math.min(Math.floor((v - min) / width), binCount - 1)
      bins[idx].count += 1
    })
    return bins
  }, [exprResult])

  const handleEvaluate = async () => {
    setExprLoading(true)
    setExprError(null)
    try {
      const res = await factorApi.evaluateExpression(expression, startDate, endDate)
      if (res.data.success) {
        setExprResult(res.data.data?.values || [])
        setExprCoverage(res.data.data?.coverage || '')
        emit.factorComputed(expression.slice(0, 30), res.data.data?.values?.length || 0)
      } else {
        setExprError(res.data.error || 'Evaluation failed')
      }
    } catch (e: any) {
      setExprError(e.response?.data?.detail || e.message || 'Evaluation failed')
    } finally {
      setExprLoading(false)
    }
  }

  const handleIcAnalysis = async () => {
    if (!selectedFactor) return
    setIcLoading(true)
    setActiveTab('analysis')
    try {
      const res = await factorApi.getIcAnalysis(selectedFactor.id, startDate, endDate)
      if (res.data.success) {
        setIcData(res.data.data || null)
        emit.factorAnalysisComplete(selectedFactor.factor_name || selectedFactor.name)
      }
    } catch {
      // silent
    } finally {
      setIcLoading(false)
    }
  }

  const handleLayeredReturns = async () => {
    if (!selectedFactor) return
    setLayeredLoading(true)
    setActiveTab('analysis')
    try {
      const res = await factorApi.getLayeredReturns(selectedFactor.id, startDate, endDate, 5)
      if (res.data.success) {
        setLayeredData(res.data.data || null)
      }
    } catch {
      // silent
    } finally {
      setLayeredLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-950 dark:text-white">因子实验室</h1>
          <p className="text-sm text-gray-500">Alpha 因子研究、IC 分析、分层回测</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="rounded bg-gray-100 px-2 py-1 dark:bg-gray-800">Data: baostock</span>
          <span className="rounded bg-gray-100 px-2 py-1 dark:bg-gray-800">Engine: v0.2.1</span>
        </div>
      </div>

      {/* Parameters bar */}
      <Card variant="bordered">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">因子类别</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="h-9 rounded-md border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
              >
                {factorCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <Input label="开始日期" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="!w-40" />
            <Input label="结束日期" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="!w-40" />
            {selectedFactor && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={handleIcAnalysis} loading={icLoading} icon={<LineChart className="h-3.5 w-3.5" />}>
                  IC 分析
                </Button>
                <Button size="sm" variant="outline" onClick={handleLayeredReturns} loading={layeredLoading} icon={<GitBranch className="h-3.5 w-3.5" />}>
                  分层收益
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-800">
        {([['factors', '因子库', BarChart3], ['expression', '表达式编辑器', Code2], ['analysis', 'IC & 分层分析', LineChart]] as const).map(([key, label, Icon]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === key
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'factors' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[24rem_1fr]">
          {/* Factor list */}
          <Card variant="bordered">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-base">
                <span>因子列表</span>
                <span className="text-sm font-normal text-gray-500">{filteredFactors.length} 个</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-[36rem] space-y-1.5 overflow-y-auto pr-1">
                {filteredFactors.map((factor) => (
                  <button
                    key={factor.id}
                    onClick={() => setSelectedFactor(factor)}
                    className={`w-full rounded-lg border p-3 text-left transition-all ${
                      selectedFactor?.id === factor.id
                        ? 'border-primary-300 bg-primary-50 dark:border-primary-800 dark:bg-primary-950'
                        : 'border-transparent hover:bg-gray-50 dark:hover:bg-gray-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                          {factor.display_name || factor.name}
                        </p>
                        <p className="mt-0.5 text-xs text-gray-500 line-clamp-1">{factor.description || factor.category}</p>
                      </div>
                      <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        {factor.category}
                      </span>
                    </div>
                    {factor.parameters?.formula && (
                      <p className="mt-1.5 truncate font-mono text-xs text-gray-400">{factor.parameters.formula}</p>
                    )}
                  </button>
                ))}
                {filteredFactors.length === 0 && !loading && (
                  <div className="py-10 text-center text-sm text-gray-500">暂无因子</div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Factor detail */}
          <Card variant="bordered">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {selectedFactor ? (selectedFactor.display_name || selectedFactor.name) : '选择因子查看详情'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedFactor ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      ['名称', selectedFactor.name],
                      ['类别', selectedFactor.category],
                      ['方向', selectedFactor.direction === '1' ? '正向' : '反向'],
                      ['版本', `v${selectedFactor.version || 1}`],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                        <p className="text-xs text-gray-500">{label}</p>
                        <p className="mt-0.5 text-sm font-medium text-gray-900 dark:text-white">{value}</p>
                      </div>
                    ))}
                  </div>
                  {selectedFactor.parameters?.formula && (
                    <div className="rounded-md bg-gray-900 p-3">
                      <p className="mb-1 text-xs text-gray-400">Formula</p>
                      <code className="font-mono text-sm text-green-400">{selectedFactor.parameters.formula}</code>
                    </div>
                  )}
                  {selectedFactor.description && (
                    <div className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                      <p className="text-xs text-gray-500">描述</p>
                      <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">{selectedFactor.description}</p>
                    </div>
                  )}
                  {/* Quick analysis metrics */}
                  {icData && icData.factor_name === (selectedFactor.factor_name || selectedFactor.name) && (
                    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-950/30">
                      <p className="mb-2 text-xs font-medium text-blue-700 dark:text-blue-400">IC Analysis Summary</p>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <p className="text-[10px] text-gray-500">IC Mean</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{icData.ic_mean.toFixed(4)}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">ICIR</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{icData.icir.toFixed(4)}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">IC+%</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{(icData.ic_positive_ratio * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  )}
                  {layeredData && layeredData.factor_name === (selectedFactor.factor_name || selectedFactor.name) && (
                    <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950/30">
                      <p className="mb-2 text-xs font-medium text-green-700 dark:text-green-400">Layered Returns Summary</p>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <p className="text-[10px] text-gray-500">L/S Return</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{layeredData.long_short.cumulative_return.toFixed(2)}%</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">Sharpe</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{layeredData.long_short.sharpe.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-gray-500">Win Rate</p>
                          <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{(layeredData.long_short.win_rate * 100).toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleIcAnalysis} loading={icLoading} icon={<LineChart className="h-3.5 w-3.5" />}>
                      IC 分析
                    </Button>
                    <Button size="sm" variant="outline" onClick={handleLayeredReturns} loading={layeredLoading} icon={<GitBranch className="h-3.5 w-3.5" />}>
                      分层收益
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="py-16 text-center text-gray-500">
                  <BarChart3 className="mx-auto mb-3 h-10 w-10 text-gray-300" />
                  <p>选择左侧因子查看详情</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'expression' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_20rem]">
          <div className="space-y-4">
            {/* Expression editor */}
            <Card variant="bordered">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Code2 className="h-4 w-4 text-primary-500" />
                  因子表达式编辑器
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="relative">
                    <textarea
                      value={expression}
                      onChange={(e) => setExpression(e.target.value)}
                      placeholder="例: ts_mean(close, 20) / ts_std(close, 20)"
                      className="h-24 w-full rounded-lg border border-gray-300 bg-gray-50 p-3 font-mono text-sm text-gray-900 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                      spellCheck={false}
                    />
                    <div className="absolute right-2 top-2 flex gap-1">
                      <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        close, open, high, low, volume, amount, vwap
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Button onClick={handleEvaluate} loading={exprLoading} icon={<Play className="h-4 w-4" />}>
                      计算因子
                    </Button>
                    {exprCoverage && (
                      <span className="text-sm text-gray-500">覆盖率: {exprCoverage}</span>
                    )}
                    {exprResult.length > 0 && (
                      <span className="text-sm text-gray-500">{exprResult.length} 条结果</span>
                    )}
                  </div>
                  {/* Preset expressions */}
                  <div>
                    <p className="mb-1.5 text-xs text-gray-500">预设表达式</p>
                    <div className="flex flex-wrap gap-1.5">
                      {PRESET_EXPRESSIONS.map((preset) => (
                        <button
                          key={preset.name}
                          onClick={() => setExpression(preset.expr)}
                          className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[11px] text-gray-600 transition-colors hover:border-primary-300 hover:bg-primary-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:border-primary-600"
                        >
                          {preset.name}
                        </button>
                      ))}
                    </div>
                  </div>
                  {exprError && (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-900/30 dark:text-red-300">
                      {exprError}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Results */}
            {exprResult.length > 0 && (
              <Card variant="bordered">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">因子分布</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={histogramData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey="value" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                        <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
                        <Tooltip
                          contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6' }}
                          formatter={(value: number) => [value, '频数']}
                        />
                        <Bar dataKey="count" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-800">
                          <th className="px-3 py-2 text-left font-medium">股票代码</th>
                          <th className="px-3 py-2 text-left font-medium">日期</th>
                          <th className="px-3 py-2 text-right font-medium">因子值</th>
                        </tr>
                      </thead>
                      <tbody>
                        {exprResult.slice(0, 30).map((v, i) => (
                          <tr key={`${v.ts_code}-${v.trade_date}-${i}`} className="border-b border-gray-100 dark:border-gray-900">
                            <td className="px-3 py-1.5 font-mono text-gray-900 dark:text-white">{v.ts_code}</td>
                            <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300">{v.trade_date}</td>
                            <td className="px-3 py-1.5 text-right font-mono text-gray-900 dark:text-white">
                              {v.value != null ? v.value.toFixed(6) : 'N/A'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Function reference */}
          <Card variant="bordered">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen className="h-4 w-4 text-gray-500" />
                函数参考
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {EXPRESSION_HELP.map((item) => (
                  <button
                    key={item.func}
                    onClick={() => setExpression(item.func.replace(/field/g, 'close').replace(/window/g, '20').replace(/f1/g, 'close').replace(/f2/g, 'volume').replace(/\bn\b/g, '5').replace(/\bw\b/g, '20'))}
                    className="w-full rounded-md border border-transparent p-2 text-left transition-colors hover:border-gray-200 hover:bg-gray-50 dark:hover:border-gray-700 dark:hover:bg-gray-800/50"
                  >
                    <p className="font-mono text-xs text-primary-600 dark:text-primary-400">{item.func}</p>
                    <p className="mt-0.5 text-xs text-gray-500">{item.desc}</p>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'analysis' && (
        <div className="space-y-5">
          {/* IC Analysis */}
          {icData && (
            <Card variant="bordered">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-base">
                  <span>IC 分析 - {icData.factor_name}</span>
                  <span className="text-sm font-normal text-gray-500">{icData.periods} 期</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
                  {[
                    ['IC 均值', icData.ic_mean.toFixed(4)],
                    ['IC 标准差', icData.ic_std.toFixed(4)],
                    ['ICIR', icData.icir.toFixed(4)],
                    ['RankIC', icData.rank_ic_mean.toFixed(4)],
                    ['IC 正值占比', (icData.ic_positive_ratio * 100).toFixed(1) + '%'],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                      <p className="text-xs text-gray-500">{label}</p>
                      <p className="mt-0.5 font-mono text-lg font-semibold text-gray-900 dark:text-white">{value}</p>
                    </div>
                  ))}
                </div>

                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <ReLineChart data={icData.ic_series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10, fill: '#9ca3af' }}
                        tickFormatter={(v) => v.slice(5)}
                      />
                      <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
                      <Tooltip
                        contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6' }}
                        labelFormatter={(v) => v}
                      />
                      <Legend />
                      <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="ic" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="IC" />
                      <Line type="monotone" dataKey="rank_ic" stroke="#22c55e" strokeWidth={1.5} dot={false} name="RankIC" />
                    </ReLineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Layered Returns */}
          {layeredData && (
            <Card variant="bordered">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-base">
                  <span>分层收益 - {layeredData.factor_name || selectedFactor?.name}</span>
                  <span className="text-sm font-normal text-gray-500">{layeredData.total_periods} 期</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* Long-short summary */}
                {layeredData.long_short && (
                  <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      ['多空日均收益', layeredData.long_short.avg_daily_return.toFixed(4) + '%'],
                      ['多空累计收益', layeredData.long_short.cumulative_return.toFixed(2) + '%'],
                      ['多空夏普', layeredData.long_short.sharpe.toFixed(4)],
                      ['多空胜率', (layeredData.long_short.win_rate * 100).toFixed(1) + '%'],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                        <p className="text-xs text-gray-500">{label}</p>
                        <p className="mt-0.5 font-mono text-lg font-semibold text-gray-900 dark:text-white">{value}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Layer bar chart */}
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={layeredData.layers}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="layer" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `L${v}`} />
                      <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(v) => `${v}%`} />
                      <Tooltip
                        contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6' }}
                        formatter={(value: number) => [`${value.toFixed(2)}%`, '累计收益']}
                      />
                      <Bar dataKey="cumulative_return" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Layer details table */}
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-800">
                        <th className="px-3 py-2 text-left font-medium">分层</th>
                        <th className="px-3 py-2 text-right font-medium">日均收益</th>
                        <th className="px-3 py-2 text-right font-medium">累计收益</th>
                        <th className="px-3 py-2 text-right font-medium">平均持股数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {layeredData.layers.map((l) => (
                        <tr key={l.layer} className="border-b border-gray-100 dark:border-gray-900">
                          <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">Layer {l.layer}</td>
                          <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-white">{l.avg_daily_return.toFixed(4)}%</td>
                          <td className={`px-3 py-2 text-right font-mono ${l.cumulative_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {l.cumulative_return.toFixed(2)}%
                          </td>
                          <td className="px-3 py-2 text-right text-gray-500">{l.stocks_avg}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {!icData && !layeredData && (
            <div className="py-20 text-center text-gray-500">
              <TrendingUp className="mx-auto mb-4 h-12 w-12 text-gray-300" />
              <p className="text-lg font-medium">选择因子并执行分析</p>
              <p className="mt-1 text-sm">在因子库中选择因子，然后点击 IC 分析或分层收益</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </div>
      )}
    </div>
  )
}
