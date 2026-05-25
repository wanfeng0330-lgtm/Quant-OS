import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'

interface ReturnCurveChartProps {
  data: Array<{
    date: string
    strategy_return: number
    benchmark_return?: number
    excess_return?: number
  }>
  height?: number
  showBenchmark?: boolean
  showExcess?: boolean
  theme?: 'light' | 'dark'
}

export default function ReturnCurveChart({
  data,
  height = 400,
  showBenchmark = true,
  showExcess = true,
  theme = 'light',
}: ReturnCurveChartProps) {
  const isDark = theme === 'dark'

  const colors = {
    strategy: '#3b82f6',
    benchmark: '#f59e0b',
    excess: '#22c55e',
    grid: isDark ? '#374151' : '#f3f4f6',
    text: isDark ? '#d1d5db' : '#374151',
    background: isDark ? '#1f2937' : '#ffffff',
  }

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(2)}%`
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div
          className={`p-3 rounded-lg shadow-lg border ${
            isDark
              ? 'bg-gray-800 border-gray-700 text-white'
              : 'bg-white border-gray-200 text-gray-900'
          }`}
        >
          <p className="font-medium mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {entry.name}: {formatPercent(entry.value)}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  return (
    <div className="w-full" style={{ height: `${height}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 5,
          }}
        >
          <defs>
            <linearGradient id="strategyGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={colors.strategy} stopOpacity={0.3} />
              <stop offset="95%" stopColor={colors.strategy} stopOpacity={0} />
            </linearGradient>
            {showBenchmark && (
              <linearGradient id="benchmarkGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={colors.benchmark} stopOpacity={0.3} />
                <stop offset="95%" stopColor={colors.benchmark} stopOpacity={0} />
              </linearGradient>
            )}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis
            dataKey="date"
            stroke={colors.text}
            tick={{ fill: colors.text }}
          />
          <YAxis
            stroke={colors.text}
            tick={{ fill: colors.text }}
            tickFormatter={formatPercent}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ color: colors.text }}
          />
          <Area
            type="monotone"
            dataKey="strategy_return"
            name="策略收益"
            stroke={colors.strategy}
            fill="url(#strategyGradient)"
            strokeWidth={2}
          />
          {showBenchmark && (
            <Area
              type="monotone"
              dataKey="benchmark_return"
              name="基准收益"
              stroke={colors.benchmark}
              fill="url(#benchmarkGradient)"
              strokeWidth={2}
            />
          )}
          {showExcess && (
            <Line
              type="monotone"
              dataKey="excess_return"
              name="超额收益"
              stroke={colors.excess}
              strokeWidth={2}
              dot={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}