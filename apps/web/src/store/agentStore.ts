import { create } from 'zustand'
import { agentApi } from '@/api/services'
import type { Agent, AgentRun, AgentMessage } from '@/api/types'
import { cache, generateCacheKey } from '@/utils/cache'

interface AgentState {
  agents: Agent[]
  currentAgent: Agent | null
  currentRun: AgentRun | null
  messages: AgentMessage[]
  loading: boolean
  error: string | null

  // Actions
  fetchAgents: () => Promise<void>
  selectAgent: (agentId: string) => Promise<void>
  startRun: (agentId: string, message: string) => Promise<void>
  fetchRun: (runId: string) => Promise<void>
  addMessage: (message: AgentMessage) => void
  clearError: () => void
}

const normalizeMessages = (messages: AgentMessage[] = []): AgentMessage[] =>
  messages.map((message, index) => ({
    id: message.id || `${message.role}-${index}-${Date.now()}`,
    role: message.role,
    content: message.content,
    timestamp: message.timestamp || new Date().toISOString(),
  }))

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  currentAgent: null,
  currentRun: null,
  messages: [],
  loading: false,
  error: null,

  fetchAgents: async () => {
    set({ loading: true, error: null })
    try {
      const cacheKey = 'agents/list'

      // Check cache first
      const cachedData = cache.get<Agent[]>(cacheKey)
      if (cachedData) {
        set({
          agents: cachedData,
          currentAgent: get().currentAgent || cachedData[0] || null,
          loading: false,
        })
        return
      }

      const response = await agentApi.listAgents()
      if (response.data.success) {
        const agents = response.data.data || []
        set({
          agents,
          currentAgent: get().currentAgent || agents[0] || null,
        })
        // Cache the result for 5 minutes
        cache.set(cacheKey, agents, 5 * 60 * 1000)
      } else {
        set({ error: response.data.error || '获取 Agent 列表失败' })
      }
    } catch (error) {
      set({ error: '获取 Agent 列表失败' })
    } finally {
      set({ loading: false })
    }
  },

  selectAgent: async (agentId: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('agents/detail', { agentId })

      // Check cache first
      const cachedData = cache.get<Agent>(cacheKey)
      if (cachedData) {
        set({ currentAgent: cachedData, messages: [], currentRun: null, loading: false })
        return
      }

      const response = await agentApi.getAgent(agentId)
      if (response.data.success) {
        set({ currentAgent: response.data.data || null, messages: [], currentRun: null })
        // Cache the result for 5 minutes
        cache.set(cacheKey, response.data.data, 5 * 60 * 1000)
      } else {
        set({ error: response.data.error || '获取 Agent 失败' })
      }
    } catch (error) {
      set({ error: '获取 Agent 失败' })
    } finally {
      set({ loading: false })
    }
  },

  startRun: async (agentId: string, message: string) => {
    set({ loading: true, error: null })
    try {
      // Add user message to chat
      const userMessage: AgentMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      }
      set((state) => ({ messages: [...state.messages, userMessage] }))

      const response = await agentApi.startAgentRun(agentId, message)
      if (response.data.success) {
        const run = response.data.data || null
        set({
          currentRun: run,
          messages: normalizeMessages(run?.messages),
        })
      } else {
        set({ error: response.data.error || 'Agent 调用失败' })
      }
    } catch (error) {
      set({ error: 'Agent 调用失败' })
    } finally {
      set({ loading: false })
    }
  },

  fetchRun: async (runId: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('agents/run', { runId })

      // Check cache first
      const cachedData = cache.get<AgentRun>(cacheKey)
      if (cachedData) {
        set({
          currentRun: cachedData,
          messages: normalizeMessages(cachedData.messages),
          loading: false,
        })
        return
      }

      const response = await agentApi.getAgentRun(runId)
      if (response.data.success) {
        const run = response.data.data
        set({
          currentRun: run || null,
          messages: normalizeMessages(run?.messages),
        })
        // Cache the result for 5 minutes
        cache.set(cacheKey, run, 5 * 60 * 1000)
      } else {
        set({ error: response.data.error || '获取 Agent 运行结果失败' })
      }
    } catch (error) {
      set({ error: '获取 Agent 运行结果失败' })
    } finally {
      set({ loading: false })
    }
  },

  addMessage: (message: AgentMessage) => {
    set((state) => ({ messages: [...state.messages, message] }))
  },

  clearError: () => set({ error: null }),
}))
