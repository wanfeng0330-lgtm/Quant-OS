import { create } from 'zustand'
import { chatApi, workflowApi } from '../api/services'
import type { ChatMessage, WorkflowEvent } from '../api/types'

// ---------------------------------------------------------------------------
// full_research template node names (matches backend)
// ---------------------------------------------------------------------------

const NODE_NAMES: Record<string, string> = {
  data_fetch: '数据获取与清洗',
  market_overview: '市场概况采集',
  northbound: '北向资金采集',
  sentiment_data: '情绪数据采集',
  factor_discovery: '因子探索与发现',
  sector_analysis: '行业轮动分析',
  sentiment_calc: '市场情绪研判',
  factor_analysis: '因子IC分析',
  report_synthesis: '综合研究报告',
}

const NODE_ORDER = [
  'data_fetch',
  'market_overview',
  'northbound',
  'sentiment_data',
  'factor_discovery',
  'sector_analysis',
  'sentiment_calc',
  'factor_analysis',
  'report_synthesis',
]

// ---------------------------------------------------------------------------
// Store types
// ---------------------------------------------------------------------------

interface ChatState {
  messages: ChatMessage[]
  isRunning: boolean
  currentRunId: string | null
  ws: WebSocket | null
  error: string | null

  sendMessage: (message: string) => Promise<void>
  clearChat: () => void
  disconnectWs: () => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _idCounter = 0
function nextId(): string {
  return `msg_${Date.now()}_${++_idCounter}`
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isRunning: false,
  currentRunId: null,
  ws: null,
  error: null,

  sendMessage: async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed || get().isRunning) return

    // Add user message
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    }

    // Add progress placeholder
    const progressMsg: ChatMessage = {
      id: nextId(),
      role: 'progress',
      content: '正在启动全量研究分析...',
      timestamp: new Date().toISOString(),
      nodeStatuses: {},
      workflowStatus: 'running',
    }

    set((s) => ({
      messages: [...s.messages, userMsg, progressMsg],
      isRunning: true,
      error: null,
    }))

    try {
      const res = await chatApi.sendResearchMessage(trimmed)
      if (!res.data.success || !res.data.data) {
        throw new Error(res.data.message || 'Failed to start research')
      }

      const { run_id } = res.data.data
      set({ currentRunId: run_id })

      // Open WebSocket for real-time progress
      _connectWs(run_id, set, get, progressMsg.id)
    } catch (err: any) {
      const errorMsg = err?.message || 'Unknown error'
      set((s) => ({
        isRunning: false,
        error: errorMsg,
        messages: s.messages.map((m) =>
          m.id === progressMsg.id
            ? { ...m, role: 'assistant' as const, content: `研究启动失败: ${errorMsg}`, workflowStatus: 'failed' }
            : m
        ),
      }))
    }
  },

  clearChat: () => {
    const { ws } = get()
    if (ws) ws.close()
    set({ messages: [], isRunning: false, currentRunId: null, ws: null, error: null })
  },

  disconnectWs: () => {
    const { ws } = get()
    if (ws) ws.close()
    set({ ws: null })
  },
}))

// ---------------------------------------------------------------------------
// WebSocket connection helper
// ---------------------------------------------------------------------------

function _connectWs(
  runId: string,
  set: (partial: Partial<ChatState> | ((state: ChatState) => Partial<ChatState>)) => void,
  get: () => ChatState,
  progressMsgId: string,
) {
  const wsBaseUrl = import.meta.env.VITE_WS_URL || 'wss://quant-os-production.up.railway.app'
  const wsUrl = `${wsBaseUrl}/ws/workflow/${runId}`
  const ws = new WebSocket(wsUrl)
  const startedAt = Date.now()

  ws.onopen = () => {
    set({ ws })
    // Check if workflow already completed (race condition: events broadcast before WS connected)
    workflowApi.getWorkflowRun(runId).then((res) => {
      if (res.data.success && res.data.data) {
        const run = res.data.data
        if (run.status === 'completed' || run.status === 'failed') {
          ws.close()
          _handleCompletion(run, runId, set, get, progressMsgId, startedAt)
        }
      }
    }).catch(() => {})
  }

  ws.onmessage = (event) => {
    try {
      const raw = JSON.parse(event.data)
      const data: WorkflowEvent = raw

      if (data.type === 'ping') return

      // Handle report event - the final report content (custom event from backend)
      if (raw.type === 'report') {
        const durationMs = Date.now() - startedAt
        const reportContent = typeof raw.output === 'string' ? raw.output : raw.content || ''
        const reportMsg: ChatMessage = {
          id: nextId(),
          role: 'report',
          content: typeof reportContent === 'string' ? reportContent : JSON.stringify(reportContent),
          timestamp: new Date().toISOString(),
          reportMetadata: {
            duration_ms: durationMs,
            nodes_executed: NODE_ORDER.length,
            generated_at: new Date().toISOString(),
          },
        }
        set((s) => ({
          messages: [...s.messages, reportMsg],
        }))
        return
      }

      // Handle done event
      if (data.type === 'done') {
        ws.close()
        set({ ws: null })

        // Fetch final run state
        workflowApi.getWorkflowRun(runId).then((res) => {
          if (res.data.success && res.data.data) {
            _handleCompletion(res.data.data, runId, set, get, progressMsgId, startedAt)
          }
        })
        return
      }

      // Handle log events
      if (data.type === 'log') {
        // Optionally append log to progress message
        return
      }

      // Handle node_start
      if (data.type === 'node_start') {
        const nodeName = NODE_NAMES[data.node_id!] || data.name || data.node_id
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === progressMsgId
              ? {
                  ...m,
                  content: `正在执行: ${nodeName}...`,
                  nodeStatuses: {
                    ...m.nodeStatuses,
                    [data.node_id!]: { status: 'running' },
                  },
                }
              : m
          ),
        }))
        return
      }

      // Handle node_complete / node_result
      if (data.type === 'node_complete' || data.type === 'node_result') {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === progressMsgId
              ? {
                  ...m,
                  nodeStatuses: {
                    ...m.nodeStatuses,
                    [data.node_id!]: {
                      status: (data.status as any) || 'completed',
                      output: data.output,
                      error: data.error,
                      duration_ms: data.duration_ms,
                      model: data.model,
                      provider: data.provider,
                      tokens: data.tokens,
                      tool: data.tool,
                    },
                  },
                }
              : m
          ),
        }))
        return
      }

      // Handle status
      if (data.type === 'status') {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === progressMsgId ? { ...m, workflowStatus: data.status || m.workflowStatus } : m
          ),
        }))
        return
      }
    } catch {
      // ignore parse errors
    }
  }

  ws.onerror = () => {
    set({ ws: null })
  }

  ws.onclose = () => {
    set({ ws: null })
  }
}

// ---------------------------------------------------------------------------
// Completion handler (shared by onopen check and done event)
// ---------------------------------------------------------------------------

function _handleCompletion(
  run: any,
  _runId: string,
  set: (partial: Partial<ChatState> | ((state: ChatState) => Partial<ChatState>)) => void,
  get: () => ChatState,
  progressMsgId: string,
  startedAt: number,
) {
  const finalStatus = run.status === 'completed' ? 'completed' : 'failed'

  // Build node statuses from run results
  const nodeStatuses: Record<string, any> = {}
  for (const [nid, result] of Object.entries(run.node_results || {})) {
    nodeStatuses[nid] = {
      status: (result as any).status || 'completed',
      output: (result as any).output,
      error: (result as any).error,
      duration_ms: (result as any).duration_ms,
      model: (result as any).model,
      provider: (result as any).provider,
      tokens: (result as any).tokens,
      tool: (result as any).tool,
    }
  }

  // If no report message was received, extract from node_results
  if (finalStatus === 'completed') {
    const currentState = get()
    const hasReport = currentState.messages.some((m) => m.role === 'report')
    if (!hasReport) {
      let reportContent = ''
      for (const [nid, result] of Object.entries(run.node_results || {})) {
        if (nid.includes('report')) {
          const output = (result as any).output
          if (typeof output === 'string') {
            reportContent = output
          } else if (output && typeof output === 'object') {
            reportContent = output.output || output.content || JSON.stringify(output)
          }
        }
      }
      if (reportContent) {
        const durationMs = Date.now() - startedAt
        const reportMsg: ChatMessage = {
          id: nextId(),
          role: 'report',
          content: reportContent,
          timestamp: new Date().toISOString(),
          reportMetadata: {
            duration_ms: durationMs,
            nodes_executed: Object.keys(run.node_results || {}).length,
            generated_at: new Date().toISOString(),
          },
        }
        set((s) => ({ messages: [...s.messages, reportMsg] }))
      }
    }
  }

  // Update progress message with node statuses and final state
  set((s) => ({
    isRunning: false,
    currentRunId: null,
    ws: null,
    messages: s.messages.map((m) =>
      m.id === progressMsgId
        ? {
            ...m,
            workflowStatus: finalStatus,
            content: finalStatus === 'completed' ? '研究完成' : '研究执行失败',
            nodeStatuses: nodeStatuses,
          }
        : m
    ),
  }))
}

// Export node metadata for components
export const CHAT_NODE_NAMES = NODE_NAMES
export const CHAT_NODE_ORDER = NODE_ORDER
