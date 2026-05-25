import { useState } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  Radio,
  XCircle,
  Zap,
} from 'lucide-react'

interface TraceSpan {
  id: string
  name: string
  agent: string
  type: 'agent' | 'tool' | 'llm' | 'workflow'
  status: 'running' | 'completed' | 'failed' | 'pending'
  startTime: string
  endTime?: string
  durationMs?: number
  tokens?: number
  model?: string
  input?: string
  output?: string
  children?: TraceSpan[]
}

const MOCK_TRACES: TraceSpan[] = [
  {
    id: 't1',
    name: 'Alpha Research Workflow',
    agent: 'Orchestrator',
    type: 'workflow',
    status: 'completed',
    startTime: '2026-05-25T09:30:00',
    endTime: '2026-05-25T09:35:12',
    durationMs: 312000,
    tokens: 12450,
    model: 'deepseek-v3',
    children: [
      {
        id: 't1-1',
        name: 'DataAgent: 获取A股行情数据',
        agent: 'DataAgent',
        type: 'agent',
        status: 'completed',
        startTime: '2026-05-25T09:30:01',
        endTime: '2026-05-25T09:30:45',
        durationMs: 44000,
        tokens: 820,
        model: 'deepseek-v3',
        input: '获取沪深300成分股最近6个月日线数据',
        output: '成功获取300只股票的OHLCV数据，共36000条记录',
        children: [
          {
            id: 't1-1-1',
            name: 'tool: akshare_fetch',
            agent: 'DataAgent',
            type: 'tool',
            status: 'completed',
            startTime: '2026-05-25T09:30:05',
            endTime: '2026-05-25T09:30:40',
            durationMs: 35000,
            input: '{ "symbols": ["000001.SZ", ...], "start": "2025-11-25", "end": "2026-05-25" }',
            output: '{ "count": 36000, "status": "success" }',
          },
        ],
      },
      {
        id: 't1-2',
        name: 'FactorAgent: 生成候选因子',
        agent: 'FactorAgent',
        type: 'agent',
        status: 'completed',
        startTime: '2026-05-25T09:30:46',
        endTime: '2026-05-25T09:32:10',
        durationMs: 84000,
        tokens: 3200,
        model: 'deepseek-v3',
        input: '基于动量和波动率生成5个候选因子',
        output: '生成5个因子: mom_20, mom_60, vol_20, mom_vol_ratio, price_momentum',
        children: [
          {
            id: 't1-2-1',
            name: 'tool: factor_evaluate',
            agent: 'FactorAgent',
            type: 'tool',
            status: 'completed',
            startTime: '2026-05-25T09:31:00',
            endTime: '2026-05-25T09:31:30',
            durationMs: 30000,
            input: '{ "expression": "ts_mean(close, 20) / ts_std(close, 20)" }',
            output: '{ "factor_name": "mom_20", "count": 34200 }',
          },
          {
            id: 't1-2-2',
            name: 'llm: factor_generation',
            agent: 'FactorAgent',
            type: 'llm',
            status: 'completed',
            startTime: '2026-05-25T09:31:30',
            endTime: '2026-05-25T09:32:10',
            durationMs: 40000,
            tokens: 2400,
            model: 'deepseek-v3',
            input: '基于动量和波动率，设计5个Alpha因子表达式',
            output: '1. mom_20 = ts_mean(close, 20) / close - 1\n2. mom_60 = ts_mean(close, 60) / close - 1\n...',
          },
        ],
      },
      {
        id: 't1-3',
        name: 'BacktestAgent: 回测因子',
        agent: 'BacktestAgent',
        type: 'agent',
        status: 'completed',
        startTime: '2026-05-25T09:32:11',
        endTime: '2026-05-25T09:33:45',
        durationMs: 94000,
        tokens: 1800,
        model: 'deepseek-v3',
        input: '对5个候选因子进行分层回测',
        output: '回测完成，mom_20因子IC=0.035, ICIR=0.43, 多空年化18.5%',
      },
      {
        id: 't1-4',
        name: 'RiskAgent: 风险分析',
        agent: 'RiskAgent',
        type: 'agent',
        status: 'completed',
        startTime: '2026-05-25T09:33:46',
        endTime: '2026-05-25T09:34:30',
        durationMs: 44000,
        tokens: 1200,
        model: 'deepseek-v3',
        input: '分析mom_20因子的风险暴露',
        output: '小盘风格暴露0.35，行业集中在科技，最大回撤-8.2%',
      },
      {
        id: 't1-5',
        name: 'ResearchAgent: 生成研究报告',
        agent: 'ResearchAgent',
        type: 'agent',
        status: 'completed',
        startTime: '2026-05-25T09:34:31',
        endTime: '2026-05-25T09:35:12',
        durationMs: 41000,
        tokens: 5430,
        model: 'deepseek-v3',
        input: '生成完整的因子研究报告',
        output: '研究报告已生成，包含因子逻辑、IC分析、回测结果、风险分析和投资建议',
      },
    ],
  },
]

const TYPE_COLORS: Record<string, string> = {
  workflow: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400',
  agent: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  tool: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  llm: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-400',
}

const STATUS_ICONS: Record<string, JSX.Element> = {
  completed: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  running: <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-500" />,
  pending: <Clock className="h-3.5 w-3.5 text-gray-400" />,
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return '' }
}

function TraceSpanRow({ span, depth = 0, expanded, onToggle }: {
  span: TraceSpan
  depth?: number
  expanded: Set<string>
  onToggle: (id: string) => void
}) {
  const isExpanded = expanded.has(span.id)
  const hasChildren = span.children && span.children.length > 0

  return (
    <>
      <div
        className={`group flex items-center gap-2 border-b border-gray-100 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50 ${
          span.status === 'running' ? 'bg-blue-50/50 dark:bg-blue-950/20' : ''
        }`}
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
      >
        <button
          onClick={() => hasChildren && onToggle(span.id)}
          className={`flex h-4 w-4 items-center justify-center ${hasChildren ? 'cursor-pointer' : 'invisible'}`}
        >
          {hasChildren && (isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)}
        </button>

        {STATUS_ICONS[span.status]}

        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${TYPE_COLORS[span.type]}`}>
          {span.type}
        </span>

        <span className="flex-1 truncate text-xs font-medium text-gray-900 dark:text-white">
          {span.name}
        </span>

        {span.model && (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">
            {span.model}
          </span>
        )}

        {span.tokens && (
          <span className="flex items-center gap-0.5 text-[10px] text-gray-400">
            <Zap className="h-3 w-3" />
            {span.tokens.toLocaleString()}
          </span>
        )}

        {span.durationMs && (
          <span className="text-[10px] text-gray-400">{formatDuration(span.durationMs)}</span>
        )}

        <span className="text-[10px] text-gray-400">{formatTime(span.startTime)}</span>
      </div>

      {isExpanded && span.input && (
        <div className="border-b border-gray-100 bg-gray-50/50 px-6 py-2 dark:border-gray-800 dark:bg-gray-800/30"
          style={{ paddingLeft: `${(depth + 1) * 20 + 32}px` }}
        >
          <div className="mb-1 text-[10px] font-medium text-gray-500">Input</div>
          <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-gray-100 p-2 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {span.input}
          </pre>
          {span.output && (
            <>
              <div className="mb-1 mt-2 text-[10px] font-medium text-gray-500">Output</div>
              <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-gray-100 p-2 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                {span.output}
              </pre>
            </>
          )}
        </div>
      )}

      {isExpanded && hasChildren && span.children!.map(child => (
        <TraceSpanRow
          key={child.id}
          span={child}
          depth={depth + 1}
          expanded={expanded}
          onToggle={onToggle}
        />
      ))}
    </>
  )
}

export default function Trace() {
  const [traces] = useState<TraceSpan[]>(MOCK_TRACES)
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['t1']))
  const [selectedSpan] = useState<TraceSpan | null>(null)
  const [filterType, setFilterType] = useState<string>('all')

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Flatten all spans for stats
  const flattenSpans = (spans: TraceSpan[]): TraceSpan[] => {
    const result: TraceSpan[] = []
    for (const span of spans) {
      result.push(span)
      if (span.children) result.push(...flattenSpans(span.children))
    }
    return result
  }

  const allSpans = flattenSpans(traces)
  const totalTokens = allSpans.reduce((sum, s) => sum + (s.tokens || 0), 0)
  const totalDuration = traces[0]?.durationMs || 0

  return (
    <div className="flex h-full flex-col">
      {/* Stats bar */}
      <div className="flex items-center gap-4 border-b border-gray-200 px-4 py-2.5 dark:border-gray-700">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Radio className="h-3.5 w-3.5 text-primary-500" />
          <span className="font-medium text-gray-900 dark:text-white">Agent Trace</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-gray-500">
          <span>Spans: <span className="font-medium text-gray-700 dark:text-gray-300">{allSpans.length}</span></span>
          <span>Tokens: <span className="font-medium text-gray-700 dark:text-gray-300">{totalTokens.toLocaleString()}</span></span>
          <span>Duration: <span className="font-medium text-gray-700 dark:text-gray-300">{formatDuration(totalDuration)}</span></span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {['all', 'agent', 'tool', 'llm'].map(type => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                filterType === type
                  ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-400'
                  : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Trace tree */}
      <div className="flex-1 overflow-y-auto">
        {traces.map(trace => (
          <TraceSpanRow
            key={trace.id}
            span={trace}
            expanded={expanded}
            onToggle={toggleExpand}
          />
        ))}
      </div>

      {/* Detail panel */}
      {selectedSpan && (
        <div className="border-t border-gray-200 p-4 dark:border-gray-700">
          <div className="text-sm font-medium">{selectedSpan.name}</div>
        </div>
      )}
    </div>
  )
}
