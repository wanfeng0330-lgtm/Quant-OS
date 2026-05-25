import { useEffect, useState } from 'react'
import { FlaskConical, History, Play } from 'lucide-react'
import { useBacktestStore } from '@/store'
import { ReturnCurveChart } from '@/components/charts'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'

const statusText = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

export default function Backtest() {
  const { backtestRuns, currentResult, loading, error, runBacktest, listBacktests } = useBacktestStore()
  const [strategyId, setStrategyId] = useState('demo_momentum')
  const [startDate, setStartDate] = useState('2024-01-02')
  const [endDate, setEndDate] = useState('2024-02-29')
  const [benchmark, setBenchmark] = useState('000300.SH')
  const [initialCapital, setInitialCapital] = useState('1000000')

  useEffect(() => {
    document.title = '回测系统 - QuantOS'
    listBacktests()
  }, [listBacktests])

  const handleRunBacktest = async () => {
    await runBacktest({
      strategy_id: strategyId,
      start_date: startDate,
      end_date: endDate,
      benchmark,
      initial_capital: Number(initialCapital),
    })
    await listBacktests()
  }

  const chartData = [
    { date: '01-02', strategy_return: 0, benchmark_return: 0, excess_return: 0 },
    { date: '01-12', strategy_return: currentResult?.results.total_return ? currentResult.results.total_return * 0.25 : 0.02, benchmark_return: 0.01, excess_return: 0.01 },
    { date: '01-26', strategy_return: currentResult?.results.total_return ? currentResult.results.total_return * 0.55 : 0.04, benchmark_return: 0.02, excess_return: 0.02 },
    { date: '02-09', strategy_return: currentResult?.results.total_return ? currentResult.results.total_return * 0.82 : 0.07, benchmark_return: 0.035, excess_return: 0.035 },
    { date: '02-29', strategy_return: currentResult?.results.total_return || 0.1, benchmark_return: currentResult?.benchmark_return || 0.04, excess_return: currentResult?.excess_return || 0.06 },
  ]

  return (
    <div className="space-y-5 sm:space-y-6">
      <Card variant="bordered">
        <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
          <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
            <FlaskConical className="h-5 w-5" />
            回测配置
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
            <Input label="策略 ID" value={strategyId} onChange={(event) => setStrategyId(event.target.value)} />
            <Input label="开始日期" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <Input label="结束日期" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            <Input label="基准指数" value={benchmark} onChange={(event) => setBenchmark(event.target.value)} />
            <Input label="初始资金" type="number" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
          </div>
          <div className="mt-4">
            <Button onClick={handleRunBacktest} loading={loading} icon={<Play className="h-4 w-4" />}>
              运行回测
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_24rem]">
        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="text-base sm:text-lg">回测结果</CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            {currentResult ? (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  {[
                    ['总收益率', currentResult.results.total_return, true],
                    ['年化收益率', currentResult.results.annual_return, true],
                    ['最大回撤', currentResult.results.max_drawdown, false],
                    ['夏普比率', currentResult.results.sharpe_ratio, null],
                  ].map(([label, value, percent]) => (
                    <div key={label as string} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{label as string}</p>
                      <p className={[
                        'mt-1 text-xl font-semibold',
                        percent === true && Number(value) >= 0 ? 'text-success-600' : '',
                        percent === false ? 'text-danger-600' : '',
                        percent === null ? 'text-gray-950 dark:text-white' : '',
                      ].join(' ')}>
                        {percent === null
                          ? Number(value).toFixed(2)
                          : `${Number(value) >= 0 && percent === true ? '+' : ''}${(Number(value) * 100).toFixed(2)}%`}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="overflow-hidden rounded-md border border-gray-200 dark:border-gray-800">
                  <ReturnCurveChart
                    data={chartData}
                    height={320}
                    showBenchmark
                    showExcess
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                    <p className="text-xs text-gray-500">胜率</p>
                    <p className="font-mono font-medium text-gray-950 dark:text-white">
                      {currentResult.results.win_rate === null ? 'N/A' : `${(currentResult.results.win_rate * 100).toFixed(2)}%`}
                    </p>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                    <p className="text-xs text-gray-500">盈亏比</p>
                    <p className="font-mono font-medium text-gray-950 dark:text-white">
                      {currentResult.results.profit_loss_ratio === null ? 'N/A' : currentResult.results.profit_loss_ratio.toFixed(2)}
                    </p>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                    <p className="text-xs text-gray-500">交易次数</p>
                    <p className="font-mono font-medium text-gray-950 dark:text-white">{currentResult.results.trade_count}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-16 text-center text-gray-500 dark:text-gray-400">
                <FlaskConical className="mx-auto mb-3 h-10 w-10" />
                <p>暂无回测结果</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="flex items-center justify-between gap-3 text-base sm:text-lg">
              <span className="flex items-center gap-2">
                <History className="h-5 w-5" />
                回测历史
              </span>
              <span className="text-sm font-normal text-gray-500">{backtestRuns.length} 条</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            <div className="max-h-[32rem] space-y-3 overflow-y-auto pr-1">
              {backtestRuns.map((run) => (
                <div key={run.id} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate font-medium text-gray-950 dark:text-white">{run.strategy_id}</p>
                    <span className={[
                      'rounded px-2 py-1 text-xs font-medium',
                      run.status === 'completed' ? 'bg-success-50 text-success-700 dark:bg-success-900/40 dark:text-success-300' : '',
                      run.status === 'running' ? 'bg-warning-50 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300' : '',
                      run.status === 'failed' ? 'bg-danger-50 text-danger-700 dark:bg-danger-900/40 dark:text-danger-300' : '',
                      run.status === 'pending' ? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' : '',
                    ].join(' ')}>
                      {statusText[run.status]}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    {run.start_date} 至 {run.end_date}
                  </p>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">基准: {run.benchmark || '-'}</p>
                </div>
              ))}
              {backtestRuns.length === 0 && !loading && (
                <div className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">暂无记录</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-md border border-danger-200 bg-danger-50 p-4 text-sm text-danger-700 dark:border-danger-900 dark:bg-danger-900/30 dark:text-danger-200">
          {error}
        </div>
      )}
    </div>
  )
}
