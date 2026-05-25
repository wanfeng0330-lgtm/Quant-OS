/**
 * QuantOS EventBus — cross-module event-driven architecture.
 *
 * Connects to the backend WebSocket event stream and provides
 * a local pub/sub for frontend components to react to system events.
 */

type EventHandler = (event: StreamEvent) => void

export interface StreamEvent {
  type: string
  time: string
  category?: string
  message?: string
  level?: string
  data?: Record<string, any>
}

/** Typed event categories for the QuantOS event system */
export type EventType =
  // Factor events
  | 'factor:computed'
  | 'factor:analysis_complete'
  | 'factor:expression_evaluated'
  // Workflow events
  | 'workflow:started'
  | 'workflow:completed'
  | 'workflow:failed'
  | 'workflow:node_started'
  | 'workflow:node_completed'
  // Backtest events
  | 'backtest:started'
  | 'backtest:completed'
  | 'backtest:failed'
  // Agent events
  | 'agent:message'
  | 'agent:thinking'
  | 'agent:tool_call'
  | 'agent:completed'
  // Risk events
  | 'risk:alert'
  | 'risk:style_drift'
  | 'risk:drawdown_warning'
  // Market events
  | 'market:limit_up'
  | 'market:limit_down'
  | 'market:northbound_flow'
  | 'market:sentiment_change'
  // System events
  | 'system:connected'
  | 'system:disconnected'
  | 'system:error'
  // Research events
  | 'research:goal_created'
  | 'research:plan_generated'
  | 'research:report_generated'
  // Wildcard
  | '*'

export interface TypedStreamEvent extends StreamEvent {
  type: EventType
}

class EventBus {
  private handlers = new Map<string, Set<EventHandler>>()
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private connected = false
  private eventLog: StreamEvent[] = []
  private maxLogSize = 200

  /** Subscribe to an event type. Use '*' for all events. */
  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    this.handlers.get(eventType)!.add(handler)
    return () => this.handlers.get(eventType)?.delete(handler)
  }

  /** Subscribe to multiple event types at once. */
  onMany(eventTypes: string[], handler: EventHandler): () => void {
    const unsubs = eventTypes.map(t => this.on(t, handler))
    return () => unsubs.forEach(u => u())
  }

  /** Emit a local event (not sent to server). */
  emit(eventType: string, data?: Partial<StreamEvent>) {
    const event: StreamEvent = {
      type: eventType,
      time: new Date().toISOString(),
      ...data,
    }
    this.dispatch(event)
  }

  /** Emit a typed event with category and level. */
  emitTyped(
    type: EventType,
    opts?: { message?: string; category?: string; level?: string; data?: Record<string, any> }
  ) {
    this.emit(type, {
      category: opts?.category ?? type.split(':')[0],
      level: opts?.level ?? 'info',
      message: opts?.message,
      data: opts?.data,
    })
  }

  /** Connect to backend WebSocket event stream. */
  connect() {
    if (this.ws) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.hostname}:8001/ws/events`

    try {
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        this.connected = true
        this.emit('system:connected', { message: 'EventStream connected' })
      }

      this.ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as StreamEvent
          if (event.type === 'ping') return
          this.dispatch(event)
        } catch { /* ignore */ }
      }

      this.ws.onclose = () => {
        this.connected = false
        this.ws = null
        this.emit('system:disconnected', { message: 'EventStream disconnected' })
        // Auto-reconnect after 5s
        this.reconnectTimer = setTimeout(() => this.connect(), 5000)
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    } catch { /* ignore */ }
  }

  /** Disconnect from backend WebSocket. */
  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
    this.connected = false
  }

  isConnected() {
    return this.connected
  }

  /** Get recent event log. */
  getLog(limit?: number): StreamEvent[] {
    return limit ? this.eventLog.slice(-limit) : [...this.eventLog]
  }

  /** Get event count by category. */
  getStats(): Record<string, number> {
    const stats: Record<string, number> = {}
    for (const e of this.eventLog) {
      const cat = e.category || 'other'
      stats[cat] = (stats[cat] || 0) + 1
    }
    return stats
  }

  private dispatch(event: StreamEvent) {
    // Log event
    this.eventLog.push(event)
    if (this.eventLog.length > this.maxLogSize) {
      this.eventLog = this.eventLog.slice(-this.maxLogSize)
    }

    // Dispatch to specific handlers
    this.handlers.get(event.type)?.forEach(h => {
      try { h(event) } catch { /* ignore */ }
    })
    // Dispatch to wildcard handlers
    this.handlers.get('*')?.forEach(h => {
      try { h(event) } catch { /* ignore */ }
    })
  }
}

// Singleton
export const eventBus = new EventBus()

// Auto-connect on import
eventBus.connect()

/** Convenience helpers for emitting typed events */
export const emit = {
  factorComputed: (name: string, count: number) =>
    eventBus.emitTyped('factor:computed', { message: `因子 ${name} 计算完成`, data: { factor_name: name, count } }),

  factorAnalysisComplete: (name: string) =>
    eventBus.emitTyped('factor:analysis_complete', { message: `因子 ${name} 分析完成` }),

  workflowStarted: (name: string) =>
    eventBus.emitTyped('workflow:started', { message: `工作流 ${name} 开始执行` }),

  workflowCompleted: (name: string, duration: number) =>
    eventBus.emitTyped('workflow:completed', { message: `工作流 ${name} 执行完成`, data: { duration_ms: duration } }),

  workflowFailed: (name: string, error: string) =>
    eventBus.emitTyped('workflow:failed', { message: `工作流 ${name} 执行失败`, level: 'error', data: { error } }),

  backtestStarted: (strategyId: string) =>
    eventBus.emitTyped('backtest:started', { message: '回测开始', data: { strategy_id: strategyId } }),

  backtestCompleted: (sharpe: number, maxDd: number) =>
    eventBus.emitTyped('backtest:completed', { message: `回测完成 Sharpe=${sharpe.toFixed(2)}`, data: { sharpe, max_drawdown: maxDd } }),

  riskAlert: (message: string, data?: Record<string, any>) =>
    eventBus.emitTyped('risk:alert', { message, level: 'warn', data }),

  agentThinking: (agentName: string) =>
    eventBus.emitTyped('agent:thinking', { message: `${agentName} 思考中...`, data: { agent: agentName } }),

  agentToolCall: (agentName: string, tool: string) =>
    eventBus.emitTyped('agent:tool_call', { message: `${agentName} 调用 ${tool}`, data: { agent: agentName, tool } }),

  marketSentimentChange: (score: number, label: string) =>
    eventBus.emitTyped('market:sentiment_change', { message: `市场情绪: ${label}`, data: { score, label } }),
}
