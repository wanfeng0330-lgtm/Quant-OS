import { useState, useEffect } from 'react'
import { syncApi } from '../api/services'

interface SyncStatus {
  sync_running: boolean
  last_sync_time: string | null
  last_sync_duration_seconds: number | null
  last_sync_error: string | null
  data: {
    stocks: { count: number }
    northbound: { count: number; latest_date: string | null }
    dragon_tiger: { count: number; latest_date: string | null }
    ohlcv: { count: number; latest_date: string | null }
  }
}

export default function DataSyncStatus() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = async () => {
    try {
      const res = await syncApi.getStatus()
      if (res.data.success) {
        setStatus(res.data.data)
      }
    } catch {
      // silent
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    setError(null)
    try {
      const res = await syncApi.triggerSync()
      if (res.data.success) {
        // Poll for completion
        const poll = setInterval(async () => {
          await fetchStatus()
          const s = await syncApi.getStatus()
          if (s.data.success && !s.data.data?.sync_running) {
            clearInterval(poll)
            setSyncing(false)
          }
        }, 5000)
      }
    } catch (e: any) {
      setError(e?.message || '同步启动失败')
      setSyncing(false)
    }
  }

  if (!status) return null

  const d = status.data
  const hasData = d.stocks.count > 0
  const isRunning = status.sync_running || syncing

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3 text-xs">
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 font-medium">数据同步状态</span>
        <button
          onClick={handleSync}
          disabled={isRunning}
          className="px-2 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:text-gray-400 text-white transition-colors"
        >
          {isRunning ? '同步中...' : '立即同步'}
        </button>
      </div>

      {error && <div className="text-red-400 mb-2">{error}</div>}

      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-1">
          <span className={d.stocks.count > 0 ? 'text-green-400' : 'text-red-400'}>
            {d.stocks.count > 0 ? '✓' : '✗'}
          </span>
          <span className="text-gray-300">股票 {d.stocks.count}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={d.northbound.count > 0 ? 'text-green-400' : 'text-red-400'}>
            {d.northbound.count > 0 ? '✓' : '✗'}
          </span>
          <span className="text-gray-300">北向 {d.northbound.count}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={d.dragon_tiger.count > 0 ? 'text-green-400' : 'text-red-400'}>
            {d.dragon_tiger.count > 0 ? '✓' : '✗'}
          </span>
          <span className="text-gray-300">龙虎榜 {d.dragon_tiger.count}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={d.ohlcv.count > 0 ? 'text-green-400' : 'text-red-400'}>
            {d.ohlcv.count > 0 ? '✓' : '✗'}
          </span>
          <span className="text-gray-300">行情 {d.ohlcv.count}</span>
        </div>
      </div>

      {status.last_sync_time && (
        <div className="mt-2 text-gray-500">
          上次同步: {new Date(status.last_sync_time).toLocaleString('zh-CN')}
          {status.last_sync_duration_seconds && ` (${status.last_sync_duration_seconds}s)`}
        </div>
      )}

      {!hasData && !isRunning && (
        <div className="mt-2 text-yellow-400/80">
          数据库为空，点击"立即同步"获取市场数据
        </div>
      )}

      {status.last_sync_error && (
        <div className="mt-1 text-red-400">错误: {status.last_sync_error}</div>
      )}
    </div>
  )
}
