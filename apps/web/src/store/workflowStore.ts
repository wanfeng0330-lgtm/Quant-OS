import { create } from 'zustand'
import { workflowApi } from '@/api/services'
import { emit } from '@/lib/eventBus'
import type { Workflow, WorkflowTemplate, WorkflowRun, WorkflowEvent, NodeResult } from '@/api/types'

interface WorkflowState {
  workflows: Workflow[]
  templates: WorkflowTemplate[]
  selectedWorkflow: Workflow | null
  currentRun: WorkflowRun | null
  runLogs: WorkflowEvent[]
  nodeStatuses: Record<string, NodeResult>
  loading: boolean
  error: string | null
  ws: WebSocket | null

  fetchWorkflows: () => Promise<void>
  fetchTemplates: () => Promise<void>
  selectWorkflow: (id: string) => Promise<void>
  createFromTemplate: (templateId: string) => Promise<void>
  startRun: (workflowId: string, input?: Record<string, any>) => Promise<void>
  cancelRun: () => Promise<void>
  disconnectWs: () => void
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [],
  templates: [],
  selectedWorkflow: null,
  currentRun: null,
  runLogs: [],
  nodeStatuses: {},
  loading: false,
  error: null,
  ws: null,

  fetchWorkflows: async () => {
    try {
      const response = await workflowApi.listWorkflows()
      if (response.data.success) {
        set({ workflows: response.data.data || [] })
      }
    } catch {
      // silently fail
    }
  },

  fetchTemplates: async () => {
    try {
      const response = await workflowApi.listTemplates()
      if (response.data.success) {
        set({ templates: response.data.data || [] })
      }
    } catch {
      // silently fail
    }
  },

  selectWorkflow: async (id: string) => {
    set({ loading: true })
    try {
      const response = await workflowApi.getWorkflow(id)
      if (response.data.success) {
        const wf = response.data.data!
        set({ selectedWorkflow: wf, currentRun: null, runLogs: [], nodeStatuses: {} })
      }
    } catch {
      set({ error: '加载工作流失败' })
    } finally {
      set({ loading: false })
    }
  },

  createFromTemplate: async (templateId: string) => {
    set({ loading: true })
    try {
      const tplRes = await workflowApi.listTemplates()
      const tpl = (tplRes.data.data || []).find((t) => t.id === templateId)
      const name = tpl?.name || templateId

      const response = await workflowApi.createWorkflow({ name, template: templateId })
      if (response.data.success) {
        const wf = response.data.data!
        set({ selectedWorkflow: wf, currentRun: null, runLogs: [], nodeStatuses: {} })
        // Refresh list
        get().fetchWorkflows()
      }
    } catch {
      set({ error: '创建工作流失败' })
    } finally {
      set({ loading: false })
    }
  },

  startRun: async (workflowId: string, input?: Record<string, any>) => {
    const { disconnectWs } = get()
    disconnectWs()

    set({ loading: true, runLogs: [], nodeStatuses: {}, currentRun: null })
    try {
      const response = await workflowApi.runWorkflow(workflowId, input)
      if (response.data.success) {
        const { run_id } = response.data.data!
        set({
          currentRun: {
            id: run_id,
            workflow_id: workflowId,
            status: 'running',
            state: {},
            node_results: {},
            started_at: new Date().toISOString(),
            completed_at: null,
            created_at: new Date().toISOString(),
          },
        })
        // Connect WebSocket for real-time updates
        _connectWs(run_id, set, get)
      }
    } catch {
      set({ error: '启动工作流失败' })
    } finally {
      set({ loading: false })
    }
  },

  cancelRun: async () => {
    const { currentRun, disconnectWs } = get()
    if (!currentRun) return
    try {
      await workflowApi.cancelWorkflowRun(currentRun.id)
      disconnectWs()
      set((s) => ({
        currentRun: s.currentRun ? { ...s.currentRun, status: 'cancelled' } : null,
      }))
    } catch {
      // ignore
    }
  },

  disconnectWs: () => {
    const { ws } = get()
    if (ws) {
      ws.close()
      set({ ws: null })
    }
  },
}))

// ---------------------------------------------------------------------------
// WebSocket connection helper
// ---------------------------------------------------------------------------

function _connectWs(
  runId: string,
  set: (partial: Partial<WorkflowState> | ((state: WorkflowState) => Partial<WorkflowState>)) => void,
  _get: () => WorkflowState,
) {
  const wsBaseUrl = import.meta.env.VITE_WS_URL || 'wss://quant-os-production.up.railway.app'
  const wsUrl = `${wsBaseUrl}/ws/workflow/${runId}`
  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    set({ ws })
  }

  ws.onmessage = (event) => {
    try {
      const data: WorkflowEvent = JSON.parse(event.data)

      if (data.type === 'ping') return

      if (data.type === 'done') {
        ws.close()
        set({ ws: null })
        workflowApi.getWorkflowRun(runId).then((res) => {
          if (res.data.success) {
            set({ currentRun: res.data.data! })
            const run = res.data.data!
            if (run.status === 'completed') {
              emit.workflowCompleted(_get().selectedWorkflow?.name || 'Workflow', 0)
            } else if (run.status === 'failed') {
              emit.workflowFailed(_get().selectedWorkflow?.name || 'Workflow', 'Execution failed')
            }
          }
        })
        return
      }

      if (data.type === 'log') {
        set((s: WorkflowState) => ({ runLogs: [...s.runLogs, data] }))
      }

      if (data.type === 'node_start') {
        set((s: WorkflowState) => ({
          nodeStatuses: {
            ...s.nodeStatuses,
            [data.node_id!]: { status: 'running' },
          },
        }))
      }

      if (data.type === 'node_complete' || data.type === 'node_result') {
        set((s: WorkflowState) => ({
          nodeStatuses: {
            ...s.nodeStatuses,
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
        }))
      }

      if (data.type === 'status') {
        set((s: WorkflowState) => ({
          currentRun: s.currentRun
            ? { ...s.currentRun, status: (data.status as any) || s.currentRun.status }
            : null,
        }))
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
