import { create } from 'zustand'

export type WebSocketMessageType = 
  | 'stock_price_update'
  | 'factor_value_update'
  | 'backtest_progress'
  | 'agent_message'
  | 'system_notification'

export interface WebSocketMessage {
  type: WebSocketMessageType
  payload: any
  timestamp: string
}

interface WebSocketStore {
  isConnected: boolean
  messages: WebSocketMessage[]
  subscribers: Map<string, Set<(message: WebSocketMessage) => void>>
  
  // Actions
  connect: (url: string) => void
  disconnect: () => void
  subscribe: (type: WebSocketMessageType, callback: (message: WebSocketMessage) => void) => () => void
  unsubscribe: (type: WebSocketMessageType, callback: (message: WebSocketMessage) => void) => void
  addMessage: (message: WebSocketMessage) => void
  clearMessages: () => void
}

let ws: WebSocket | null = null
let reconnectAttempts = 0
const maxReconnectAttempts = 5
let reconnectTimeout: NodeJS.Timeout | null = null

export const useWebSocketStore = create<WebSocketStore>((set, get) => ({
  isConnected: false,
  messages: [],
  subscribers: new Map(),

  connect: (url: string) => {
    if (ws) {
      ws.close()
    }

    ws = new WebSocket(url)

    ws.onopen = () => {
      set({ isConnected: true })
      reconnectAttempts = 0
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        get().addMessage(message)
        
        // Notify subscribers
        const subscribers = get().subscribers.get(message.type)
        if (subscribers) {
          subscribers.forEach((callback) => callback(message))
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = (event) => {
      set({ isConnected: false })
      console.log('WebSocket disconnected:', event.code, event.reason)

      // Attempt to reconnect
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`)
        
        reconnectTimeout = setTimeout(() => {
          get().connect(url)
        }, delay)
      }
    }
  },

  disconnect: () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    set({ isConnected: false })
  },

  subscribe: (type: WebSocketMessageType, callback: (message: WebSocketMessage) => void) => {
    const subscribers = get().subscribers
    if (!subscribers.has(type)) {
      subscribers.set(type, new Set())
    }
    subscribers.get(type)!.add(callback)
    set({ subscribers })

    // Return unsubscribe function
    return () => {
      get().unsubscribe(type, callback)
    }
  },

  unsubscribe: (type: WebSocketMessageType, callback: (message: WebSocketMessage) => void) => {
    const subscribers = get().subscribers
    const typeSubscribers = subscribers.get(type)
    if (typeSubscribers) {
      typeSubscribers.delete(callback)
      if (typeSubscribers.size === 0) {
        subscribers.delete(type)
      }
      set({ subscribers })
    }
  },

  addMessage: (message: WebSocketMessage) => {
    set((state) => ({
      messages: [...state.messages.slice(-99), message], // Keep last 100 messages
    }))
  },

  clearMessages: () => {
    set({ messages: [] })
  },
}))