import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis,
  Cell,
} from 'recharts'

interface FactorDistributionChartProps {
  type: 'histogram' | 'scatter'
  data: Array<{
    value: number
    count?: number
    x?: number
    y?: number
    z?: number
    label?: string
  }>
  height?: number
  theme?: 'light' | 'dark'
  title?: string
  xAxisLabel?: string
  yAxisLabel?: string
}

export default function FactorDistributionChart({
  type,
  data,
  height = 400,
  theme = 'light',
  title,
  xAxisLabel,
  yAxisLabel,
}: FactorDistributionChartProps) {
  const isDark = theme === 'dark'

  const colors = {
    primary: '#3b82f6',
    secondary: '#f59e0b',
    success: '#22c55e',
    danger: '#ef4444',
    grid: isDark ? '#374151' : '#f3f4f6',
    text: isDark ? '#d1d5db' : '#374151',
    background: isDark ? '#1f2937' : '#ffffff',
  }

  const getColor = (index: number) => {
    const colorList = [colors.primary, colors.secondary, colors.success, colors.danger]
    return colorList[index % colorList.length]
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
          {type === 'histogram' ? (
            <>
              <p className="font-medium mb-1">区间: {label}</p>
              <p className="text-sm">数量: {payload[0].value}</p>
            </>
          ) : (
            <>
              <p className="font-medium mb-1">{payload[0].payload.label || '数据点'}</p>
              <p className="text-sm">X: {payload[0].payload.x?.toFixed(4)}</p>
              <p className="text-sm">Y: {payload[0].payload.y?.toFixed(4)}</p>
            </>
          )}
        </div>
      )
    }
    return null
  }

  if (type === 'histogram') {
    return (
      <div className="w-full" style={{ height: `${height}px` }}>
        {title && (
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4 text-center">
            {title}
          </h3>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis
              dataKey="value"
              stroke={colors.text}
              tick={{ fill: colors.text }}
              label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -5, fill: colors.text } : undefined}
            />
            <YAxis
              stroke={colors.text}
              tick={{ fill: colors.text }}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fill: colors.text } : undefined}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" name="频数" fill={colors.primary} radius={[4, 4, 0, 0]}>
              {data.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(index)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // Scatter plot
  return (
    <div className="w-full" style={{ height: `${height}px` }}>
      {title && (
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4 text-center">
          {title}
        </h3>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis
            dataKey="x"
            stroke={colors.text}
            tick={{ fill: colors.text }}
            label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -5, fill: colors.text } : undefined}
          />
          <YAxis
            dataKey="y"
            stroke={colors.text}
            tick={{ fill: colors.text }}
            label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fill: colors.text } : undefined}
          />
          <ZAxis dataKey="z" range={[20, 200]} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter name="因子值" data={data} fill={colors.primary}>
            {data.map((_entry, index) => (
              <Cell key={`cell-${index}`} fill={getColor(index)} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}