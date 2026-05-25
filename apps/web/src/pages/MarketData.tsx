import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw, Search, TrendingUp } from 'lucide-react'
import { useMarketStore } from '@/store'
import { CandlestickChart } from '@/components/charts'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import type { StockPrice } from '@/api/types'

type TimeFrame = '1m' | '5d' | 'daily' | 'weekly' | 'monthly'

const TIMEFRAMES: { key: TimeFrame; label: string }[] = [
  { key: '1m', label: '分时' },
  { key: '5d', label: '五日' },
  { key: 'daily', label: '日K' },
  { key: 'weekly', label: '周K' },
  { key: 'monthly', label: '月K' },
]

function aggregateToWeekly(prices: StockPrice[]): StockPrice[] {
  const sorted = [...prices].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  const groups: Record<string, StockPrice[]> = {}
  for (const p of sorted) {
    const d = new Date(p.trade_date)
    const weekStart = new Date(d)
    weekStart.setDate(d.getDate() - d.getDay())
    const key = weekStart.toISOString().slice(0, 10)
    if (!groups[key]) groups[key] = []
    groups[key].push(p)
  }
  return Object.entries(groups).map(([weekStart, items]) => ({
    trade_date: weekStart,
    open: items[0].open,
    high: Math.max(...items.map(i => i.high ?? 0)),
    low: Math.min(...items.map(i => i.low ?? Infinity)),
    close: items[items.length - 1].close,
    volume: items.reduce((s, i) => s + (i.volume ?? 0), 0),
    amount: items.reduce((s, i) => s + (i.amount ?? 0), 0),
    pct_chg: items[items.length - 1].pct_chg,
  }))
}

function aggregateToMonthly(prices: StockPrice[]): StockPrice[] {
  const sorted = [...prices].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  const groups: Record<string, StockPrice[]> = {}
  for (const p of sorted) {
    const key = p.trade_date.slice(0, 7)
    if (!groups[key]) groups[key] = []
    groups[key].push(p)
  }
  return Object.entries(groups).map(([month, items]) => ({
    trade_date: month + '-01',
    open: items[0].open,
    high: Math.max(...items.map(i => i.high ?? 0)),
    low: Math.min(...items.map(i => i.low ?? Infinity)),
    close: items[items.length - 1].close,
    volume: items.reduce((s, i) => s + (i.volume ?? 0), 0),
    amount: items.reduce((s, i) => s + (i.amount ?? 0), 0),
    pct_chg: items[items.length - 1].pct_chg,
  }))
}

export default function MarketData() {
  const {
    stocks,
    selectedStock,
    stockPrices,
    loading,
    error,
    page,
    pageSize,
    total,
    keyword,
    searchStocks,
    selectStock,
    fetchStockPrices,
  } = useMarketStore()
  const [searchKeyword, setSearchKeyword] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [timeframe, setTimeframe] = useState<TimeFrame>('daily')

  useEffect(() => {
    document.title = '行情数据 - QuantOS'
    searchStocks('')
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    setTheme(document.documentElement.classList.contains('dark') || mediaQuery.matches ? 'dark' : 'light')
    const handleChange = (event: MediaQueryListEvent) => setTheme(event.matches ? 'dark' : 'light')
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [searchStocks])

  useEffect(() => {
    if (!selectedStock && stocks.length > 0) {
      selectStock(stocks[0].ts_code)
    }
  }, [selectedStock, selectStock, stocks])

  const handleSearch = () => {
    searchStocks(searchKeyword)
  }

  const handleRefresh = () => {
    if (selectedStock) {
      fetchStockPrices(selectedStock.ts_code)
    }
  }

  const displayData = useMemo(() => {
    if (!stockPrices.length) return []
    const sorted = [...stockPrices].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
    switch (timeframe) {
      case '5d':
        return sorted.slice(-5)
      case 'weekly':
        return aggregateToWeekly(sorted)
      case 'monthly':
        return aggregateToMonthly(sorted)
      case 'daily':
      default:
        return sorted
    }
  }, [stockPrices, timeframe])

  return (
    <div className="space-y-5 sm:space-y-6">
      <Card variant="bordered">
        <CardContent className="p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              placeholder="股票代码或名称"
              value={searchKeyword}
              onChange={(event) => setSearchKeyword(event.target.value)}
              icon={<Search className="h-4 w-4" />}
              onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
            />
            <Button className="sm:w-28" onClick={handleSearch} loading={loading}>
              搜索
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[22rem_1fr]">
        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="flex items-center justify-between gap-3 text-base sm:text-lg">
              <span>股票池</span>
              <span className="text-sm font-normal text-gray-500">{total || stocks.length} 只</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            <div className="max-h-[24rem] space-y-2 overflow-y-auto pr-1 xl:max-h-[34rem]">
              {stocks.map((stock) => (
                <button
                  type="button"
                  key={stock.ts_code}
                  onClick={() => selectStock(stock.ts_code)}
                  className={[
                    'w-full rounded-md border p-3 text-left transition-colors',
                    selectedStock?.ts_code === stock.ts_code
                      ? 'border-primary-300 bg-primary-50 dark:border-primary-800 dark:bg-primary-950'
                      : 'border-transparent bg-gray-50 hover:border-gray-200 hover:bg-gray-100 dark:bg-gray-800/70 dark:hover:border-gray-700 dark:hover:bg-gray-800',
                  ].join(' ')}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-gray-950 dark:text-white">{stock.name}</p>
                      <p className="font-mono text-xs text-gray-500 dark:text-gray-400">{stock.ts_code}</p>
                    </div>
                    <div className="text-right text-xs text-gray-500 dark:text-gray-400">
                      <p>{stock.exchange}</p>
                      <p className="truncate">{stock.industry || '-'}</p>
                    </div>
                  </div>
                </button>
              ))}
              {stocks.length === 0 && !loading && (
                <div className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                  暂无股票数据
                </div>
              )}
            </div>
            {!keyword && total > pageSize && (
              <div className="mt-3 flex items-center justify-between border-t border-gray-200 pt-3 dark:border-gray-700">
                <span className="text-xs text-gray-500">
                  第 {page} / {Math.ceil(total / pageSize)} 页
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => searchStocks('', page - 1)}
                    disabled={page <= 1 || loading}
                    className="rounded p-1.5 text-gray-500 hover:bg-gray-100 disabled:opacity-30 dark:hover:bg-gray-800"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => searchStocks('', page + 1)}
                    disabled={page * pageSize >= total || loading}
                    className="rounded p-1.5 text-gray-500 hover:bg-gray-100 disabled:opacity-30 dark:hover:bg-gray-800"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="flex flex-col gap-3 text-base sm:flex-row sm:items-center sm:justify-between sm:text-lg">
              <span>{selectedStock ? selectedStock.name : '股票详情'}</span>
              <div className="flex items-center gap-2">
                {selectedStock && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefresh}
                    loading={loading}
                    icon={<RefreshCw className="h-4 w-4" />}
                  >
                    刷新
                  </Button>
                )}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            {selectedStock ? (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  {[
                    ['代码', selectedStock.ts_code],
                    ['交易所', selectedStock.exchange],
                    ['板块', selectedStock.board],
                    ['行业', selectedStock.industry || '-'],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-md bg-gray-50 p-3 dark:bg-gray-800/70">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
                      <p className="mt-1 truncate font-medium text-gray-950 dark:text-white">{value}</p>
                    </div>
                  ))}
                </div>

                {/* Timeframe selector */}
                <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
                  {TIMEFRAMES.map((tf) => (
                    <button
                      key={tf.key}
                      onClick={() => setTimeframe(tf.key)}
                      className={[
                        'flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                        timeframe === tf.key
                          ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                      ].join(' ')}
                    >
                      {tf.label}
                    </button>
                  ))}
                </div>

                {displayData.length > 0 ? (
                  <div className="overflow-hidden rounded-md border border-gray-200 dark:border-gray-800">
                    <CandlestickChart
                      data={displayData.map((price) => ({
                        time: price.trade_date,
                        open: price.open,
                        high: price.high,
                        low: price.low,
                        close: price.close,
                        volume: price.volume,
                      }))}
                      height={360}
                      theme={theme}
                    />
                  </div>
                ) : (
                  <div className="flex h-72 items-center justify-center rounded-md bg-gray-50 dark:bg-gray-800/70">
                    <div className="text-center text-gray-500 dark:text-gray-400">
                      <TrendingUp className="mx-auto mb-3 h-10 w-10" />
                      <p>暂无 K 线数据</p>
                    </div>
                  </div>
                )}

                {displayData.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="min-w-[42rem] w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-gray-500 dark:border-gray-800 dark:text-gray-400">
                          <th className="px-3 py-3 text-left font-medium">日期</th>
                          <th className="px-3 py-3 text-right font-medium">开盘</th>
                          <th className="px-3 py-3 text-right font-medium">最高</th>
                          <th className="px-3 py-3 text-right font-medium">最低</th>
                          <th className="px-3 py-3 text-right font-medium">收盘</th>
                          <th className="px-3 py-3 text-right font-medium">涨跌幅</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayData.slice(-12).reverse().map((price) => (
                          <tr key={`${price.trade_date}-${price.close}`} className="border-b border-gray-100 hover:bg-gray-50 dark:border-gray-900 dark:hover:bg-gray-800/60">
                            <td className="px-3 py-3 text-gray-900 dark:text-white">{price.trade_date}</td>
                            <td className="px-3 py-3 text-right font-mono text-gray-900 dark:text-white">{price.open?.toFixed(2) ?? '-'}</td>
                            <td className="px-3 py-3 text-right font-mono text-gray-900 dark:text-white">{price.high?.toFixed(2) ?? '-'}</td>
                            <td className="px-3 py-3 text-right font-mono text-gray-900 dark:text-white">{price.low?.toFixed(2) ?? '-'}</td>
                            <td className="px-3 py-3 text-right font-mono text-gray-900 dark:text-white">{price.close?.toFixed(2) ?? '-'}</td>
                            <td className="px-3 py-3 text-right">
                              <span className={`font-mono font-medium ${(price.pct_chg ?? 0) >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                                {(price.pct_chg ?? 0) >= 0 ? '+' : ''}{price.pct_chg?.toFixed(2) ?? '0.00'}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-16 text-center text-gray-500 dark:text-gray-400">
                <TrendingUp className="mx-auto mb-3 h-10 w-10" />
                <p>请选择股票</p>
              </div>
            )}
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
