import { useEffect, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  BarChart as BarChartIcon,
  Flame,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { sentimentApi } from '@/api/services'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'

const PIE_COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

export default function Sentiment() {
  const [overview, setOverview] = useState<any>(null)
  const [northbound, setNorthbound] = useState<any>(null)
  const [dragonTiger, setDragonTiger] = useState<any>(null)
  const [industries, setIndustries] = useState<any>(null)
  const [limitStats, setLimitStats] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [ov, nb, dt, ind, ls] = await Promise.all([
        sentimentApi.getOverview(),
        sentimentApi.getNorthbound(),
        sentimentApi.getDragonTiger(),
        sentimentApi.getIndustryRotation(),
        sentimentApi.getLimitStats(),
      ])
      setOverview(ov.data.data)
      setNorthbound(nb.data.data)
      setDragonTiger(dt.data.data)
      setIndustries(ind.data.data)
      setLimitStats(ls.data.data)
    } catch { /* ignore */ }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">市场情绪</h2>
          <p className="text-xs text-gray-500">A股市场情绪监控面板</p>
        </div>
        <Button size="sm" variant="ghost" onClick={loadAll} disabled={loading}>
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
      </div>

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {[
            { label: '涨停数', value: overview.limit_up_count, icon: <TrendingUp className="h-4 w-4" />, color: 'text-green-500 bg-green-50 dark:bg-green-950/30' },
            { label: '跌停数', value: overview.limit_down_count, icon: <TrendingDown className="h-4 w-4" />, color: 'text-red-500 bg-red-50 dark:bg-red-950/30' },
            { label: '连板高度', value: overview.consecutive_high, icon: <Flame className="h-4 w-4" />, color: 'text-orange-500 bg-orange-50 dark:bg-orange-950/30' },
            { label: '情绪评分', value: overview.sentiment_score, icon: <Zap className="h-4 w-4" />, color: 'text-purple-500 bg-purple-50 dark:bg-purple-950/30' },
            { label: '上涨家数', value: overview.up_count, icon: <ArrowUp className="h-4 w-4" />, color: 'text-green-500 bg-green-50 dark:bg-green-950/30' },
            { label: '下跌家数', value: overview.down_count, icon: <ArrowDown className="h-4 w-4" />, color: 'text-red-500 bg-red-50 dark:bg-red-950/30' },
            { label: '成交量(亿)', value: overview.total_volume_billion, icon: <BarChartIcon className="h-4 w-4" />, color: 'text-blue-500 bg-blue-50 dark:bg-blue-950/30' },
            { label: '成交额(亿)', value: overview.total_amount_billion, icon: <BarChartIcon className="h-4 w-4" />, color: 'text-cyan-500 bg-cyan-50 dark:bg-cyan-950/30' },
          ].map(item => (
            <Card key={item.label} variant="bordered">
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className={`rounded-md p-1.5 ${item.color}`}>{item.icon}</div>
                  <div>
                    <p className="text-xs text-gray-500">{item.label}</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{item.value}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Up/Down ratio bar */}
      {overview && (
        <Card variant="bordered">
          <CardContent className="p-3">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">涨跌比</span>
              <div className="flex-1 flex h-3 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className="bg-green-500 transition-all"
                  style={{ width: `${(overview.up_count / (overview.up_count + overview.down_count + overview.flat_count)) * 100}%` }}
                />
                <div
                  className="bg-gray-400 transition-all"
                  style={{ width: `${(overview.flat_count / (overview.up_count + overview.down_count + overview.flat_count)) * 100}%` }}
                />
                <div
                  className="bg-red-500 transition-all"
                  style={{ width: `${(overview.down_count / (overview.up_count + overview.down_count + overview.flat_count)) * 100}%` }}
                />
              </div>
              <div className="flex gap-2 text-[10px]">
                <span className="text-green-500">{overview.up_count}</span>
                <span className="text-gray-400">{overview.flat_count}</span>
                <span className="text-red-500">{overview.down_count}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Limit up/down pie */}
        {limitStats && (
          <Card variant="bordered">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">涨停原因分布</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={Object.entries(limitStats.limit_up_reasons).map(([name, value]) => ({ name, value }))}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {Object.entries(limitStats.limit_up_reasons).map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              {/* Consecutive limit up */}
              <div className="mt-3">
                <p className="mb-1.5 text-xs font-medium text-gray-500">连板股</p>
                <div className="space-y-1">
                  {limitStats.limit_up_stocks.filter((s: any) => s.consecutive > 1).map((s: any) => (
                    <div key={s.ts_code} className="flex items-center justify-between rounded bg-gray-50 px-2 py-1 dark:bg-gray-800/50">
                      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{s.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{s.reason}</span>
                        <span className="rounded bg-orange-100 px-1.5 py-0.5 text-[10px] font-bold text-orange-700 dark:bg-orange-900/40 dark:text-orange-400">
                          {s.consecutive}连板
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Northbound flow chart */}
        {northbound && (
          <Card variant="bordered">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-sm">
                <span>北向资金流向</span>
                <span className={`text-xs font-medium ${northbound.today_net_flow_billion > 0 ? 'text-green-500' : 'text-red-500'}`}>
                  今日{northbound.today_status} {Math.abs(northbound.today_net_flow_billion)}亿
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={northbound.flows?.slice(-20)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(5)} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(v: number) => [`${v}亿`, '净流入']}
                      labelFormatter={v => `日期: ${v}`}
                    />
                    <ReferenceLine y={0} stroke="#6b7280" />
                    <Bar
                      dataKey="net_flow_billion"
                      fill="#3b82f6"
                      radius={[2, 2, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {/* Top buy/sell */}
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <p className="mb-1 text-xs font-medium text-green-500">净买入 TOP</p>
                  {northbound.top_buy?.slice(0, 3).map((s: any) => (
                    <div key={s.name} className="flex items-center justify-between py-0.5">
                      <span className="text-xs text-gray-700 dark:text-gray-300">{s.name}</span>
                      <span className="text-xs text-green-500">+{s.net_buy_million}M</span>
                    </div>
                  ))}
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-red-500">净卖出 TOP</p>
                  {northbound.top_sell?.slice(0, 3).map((s: any) => (
                    <div key={s.name} className="flex items-center justify-between py-0.5">
                      <span className="text-xs text-gray-700 dark:text-gray-300">{s.name}</span>
                      <span className="text-xs text-red-500">-{s.net_sell_million}M</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Industry rotation */}
      {industries && (
        <Card variant="bordered">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-sm">
              <span>行业轮动</span>
              <div className="flex gap-2">
                <span className="text-xs text-green-500">最热: {industries.hot_sectors?.join(', ')}</span>
                <span className="text-xs text-red-500">最冷: {industries.cold_sectors?.join(', ')}</span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={industries.industries?.slice(0, 15)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v: number) => [`${v}%`, '涨跌幅']} />
                  <ReferenceLine x={0} stroke="#6b7280" />
                  <Bar dataKey="pct_1d" name="今日" radius={[0, 2, 2, 0]}>
                    {industries.industries?.slice(0, 15).map((entry: any, i: number) => (
                      <Cell key={i} fill={entry.pct_1d >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Dragon tiger */}
      {dragonTiger && dragonTiger.entries?.length > 0 && (
        <Card variant="bordered">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-sm">
              <span>龙虎榜</span>
              <span className="text-xs text-gray-500">{dragonTiger.summary}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">股票</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">代码</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">涨跌幅</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">净买入(万)</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">上榜原因</th>
                  </tr>
                </thead>
                <tbody>
                  {dragonTiger.entries.map((e: any) => (
                    <tr key={e.ts_code} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{e.name}</td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500">{e.ts_code}</td>
                      <td className={`px-3 py-2 text-right font-mono ${e.pct_chg >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {e.pct_chg >= 0 ? '+' : ''}{e.pct_chg}%
                      </td>
                      <td className={`px-3 py-2 text-right font-mono ${e.net_buy_million >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {e.net_buy_million >= 0 ? '+' : ''}{e.net_buy_million}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">{e.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
