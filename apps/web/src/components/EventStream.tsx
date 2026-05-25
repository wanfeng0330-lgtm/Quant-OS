import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart3,
  Bot,
  FileText,
  GitBranch,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import { eventBus, type StreamEvent } from '@/lib/eventBus'

const CATEGORY_ICONS: Record<string, JSX.Element> = {
  factor: <BarChart3 className="h-3.5 w-3.5" />,
  workflow: <GitBranch className="h-3.5 w-3.5" />,
  report: <FileText className="h-3.5 w-3.5" />,
  market: <TrendingUp className="h-3.5 w-3.5" />,
  agent: <Bot className="h-3.5 w-3.5" />,
  system: <Activity className="h-3.5 w-3.5" />,
}

const CATEGORY_COLORS: Record<string, string> = {
  factor: 'text-blue-500 bg-blue-50 dark:bg-blue-950/30',
  workflow: 'text-purple-500 bg-purple-50 dark:bg-purple-950/30',
  report: 'text-green-500 bg-green-50 dark:bg-green-950/30',
  market: 'text-orange-500 bg-orange-50 dark:bg-orange-950/30',
  agent: 'text-cyan-500 bg-cyan-50 dark:bg-cyan-950/30',
  system: 'text-gray-500 bg-gray-50 dark:bg-gray-800',
}

const TYPE_BADGES: Record<string, { label: string; color: string }> = {
  factor_computed: { label: '因子', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400' },
  workflow_started: { label: '开始', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400' },
  workflow_completed: { label: '完成', color: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400' },
  report_generated: { label: '报告', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400' },
  market_alert: { label: '预警', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400' },
  system_event: { label: '系统', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400' },
}

interface EventStreamProps {
  open: boolean
  onClose: () => void
}

export default function EventStream({ open, onClose }: EventStreamProps) {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [connected, setConnected] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    // Subscribe to all events via EventBus
    const unsubscribe = eventBus.on('*', (event) => {
      setEvents(prev => [...prev.slice(-99), event])
    })

    // Check connection status periodically
    const interval = setInterval(() => {
      setConnected(eventBus.isConnected())
    }, 2000)

    return () => {
      unsubscribe()
      clearInterval(interval)
    }
  }, [open])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  if (!open) return null

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return ''
    }
  }

  return (
    <div className="fixed bottom-0 right-0 top-0 z-50 flex w-96 flex-col border-l border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary-500" />
          <span className="text-sm font-semibold text-gray-900 dark:text-white">事件流</span>
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{events.length} 条</span>
          <button
            onClick={() => setEvents([])}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
          >
            清空
          </button>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Events */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2">
        {events.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <Zap className="mx-auto h-8 w-8 text-gray-300 dark:text-gray-600" />
              <p className="mt-2 text-sm text-gray-400">等待事件...</p>
              <p className="text-xs text-gray-400">运行工作流或计算因子以查看实时事件</p>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5">
            {events.map((event, i) => {
              const category = event.category || 'system'
              const badge = TYPE_BADGES[event.type] || TYPE_BADGES.system_event
              return (
                <div
                  key={i}
                  className="group rounded-lg border border-gray-100 p-2.5 transition-colors hover:border-gray-200 dark:border-gray-800 dark:hover:border-gray-700"
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded ${CATEGORY_COLORS[category] || CATEGORY_COLORS.system}`}>
                      {CATEGORY_ICONS[category] || <AlertCircle className="h-3.5 w-3.5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${badge.color}`}>
                          {badge.label}
                        </span>
                        <span className="text-[10px] text-gray-400">{formatTime(event.time)}</span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-gray-700 dark:text-gray-300">
                        {event.message || event.type}
                      </p>
                      {event.data && Object.keys(event.data).length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {Object.entries(event.data).map(([k, v]) => (
                            <span key={k} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">
                              {k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
