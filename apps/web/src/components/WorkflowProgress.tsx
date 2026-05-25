import { CHAT_NODE_ORDER, CHAT_NODE_NAMES } from '../store/chatStore'
import type { NodeResult } from '../api/types'

interface WorkflowProgressProps {
  nodeStatuses: Record<string, NodeResult>
  workflowStatus?: string
}

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  running: '◉',
  completed: '✓',
  failed: '✗',
  skipped: '–',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'text-gray-500',
  running: 'text-blue-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
  skipped: 'text-gray-600',
}

const STATUS_BG: Record<string, string> = {
  pending: '',
  running: 'bg-blue-500/10 border-blue-500/30',
  completed: 'bg-green-500/5 border-green-500/20',
  failed: 'bg-red-500/10 border-red-500/30',
  skipped: '',
}

export default function WorkflowProgress({ nodeStatuses, workflowStatus }: WorkflowProgressProps) {
  const isComplete = workflowStatus === 'completed'
  const isFailed = workflowStatus === 'failed'

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-900/80 p-4 backdrop-blur-sm">
      <div className="mb-3 flex items-center gap-2">
        {!isComplete && !isFailed && (
          <div className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
        )}
        {isComplete && <span className="text-green-400 text-sm">✓</span>}
        {isFailed && <span className="text-red-400 text-sm">✗</span>}
        <span className="text-sm font-medium text-gray-200">
          {isComplete ? '研究完成' : isFailed ? '研究失败' : '研究进行中...'}
        </span>
      </div>

      <div className="space-y-1">
        {CHAT_NODE_ORDER.map((nodeId) => {
          const result = nodeStatuses[nodeId]
          const status = result?.status || 'pending'
          const name = CHAT_NODE_NAMES[nodeId] || nodeId

          return (
            <div
              key={nodeId}
              className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs transition-all ${STATUS_BG[status] || 'border-transparent'}`}
            >
              <span className={`${STATUS_COLOR[status]} w-4 text-center text-sm font-bold`}>
                {status === 'running' ? (
                  <span className="inline-block animate-spin">◉</span>
                ) : (
                  STATUS_ICON[status]
                )}
              </span>
              <span className={`${status === 'pending' ? 'text-gray-500' : 'text-gray-200'} flex-1`}>
                {name}
              </span>
              {result?.duration_ms != null && (
                <span className="text-gray-500">{(result.duration_ms / 1000).toFixed(1)}s</span>
              )}
              {result?.model && (
                <span className="text-gray-600 text-[10px]">{result.model}</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
