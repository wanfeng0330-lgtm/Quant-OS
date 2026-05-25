// Market Data Types
export interface Stock {
  ts_code: string
  symbol: string
  name: string
  exchange: string
  board: string
  industry: string
  is_st: boolean
  is_hs: boolean
  list_date: string | null
  total_share: number | null
  float_share: number | null
  status: string
}

export interface StockPrice {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  pct_chg: number
}

export interface StockSearchParams {
  keyword: string
  limit?: number
}

export interface StockListParams {
  exchange?: string
  board?: string
  is_st?: boolean
  status?: string
  page?: number
  size?: number
}

// Factor Types
export interface Factor {
  id: string
  name: string
  factor_name?: string
  display_name?: string
  category: string
  description: string
  parameters: Record<string, any>
  direction?: string
  is_active?: boolean
  version?: number
}

export interface FactorValue {
  ts_code: string
  trade_date: string
  value: number | null
}

export interface FactorComputeParams {
  factor_name: string
  start_date: string
  end_date: string
  stock_pool?: string[]
  params?: Record<string, any>
}

export interface FactorAnalysis {
  factor_name: string
  period: string
  analysis: {
    ic?: {
      mean_ic: number
      ic_ir: number
      ic_positive_ratio: number
    }
    layered?: {
      layers: Array<{
        layer: number
        return: number
        sharpe: number
      }>
    }
  }
}

// Backtest Types
export interface BacktestParams {
  strategy_id: string
  start_date: string
  end_date: string
  benchmark?: string
  initial_capital?: number
  commission_rate?: number
  slippage_rate?: number
}

export interface BacktestResult {
  backtest_id: string
  strategy_id: string
  period: string
  results: {
    total_return: number
    annual_return: number
    max_drawdown: number
    sharpe_ratio: number
    win_rate: number | null
    profit_loss_ratio: number | null
    trade_count: number
  }
  benchmark_return: number | null
  excess_return: number | null
}

export interface BacktestRun {
  id: string
  strategy_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  start_date: string
  end_date: string
  benchmark: string
  created_at: string
}

// Agent Types
export interface Agent {
  id: string
  name: string
  type: string
  agent_type?: string
  description: string
  status: 'active' | 'inactive' | 'idle' | 'running' | 'completed' | 'failed'
  llm_provider?: string
  llm_model?: string
  is_active?: boolean
}

export interface AgentMessage {
  id?: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: string
}

export interface AgentRun {
  id: string
  agent_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  messages: AgentMessage[]
  created_at: string
  completed_at: string | null
}

// Workflow Types
export interface WorkflowNode {
  id: string
  name: string
  type: 'start' | 'end' | 'task' | 'condition' | 'parallel' | 'loop'
  config: Record<string, any>
  dependencies: string[]
}

export interface Workflow {
  id: string
  name: string
  description: string
  dag: { nodes: WorkflowNode[] }
  is_active: boolean
  created_at: string | null
}

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  node_count: number
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  state: Record<string, any>
  node_results: Record<string, NodeResult>
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

export interface NodeResult {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  output?: any
  error?: string
  duration_ms?: number
  model?: string
  provider?: string
  tokens?: number
  tool?: string
}

export interface WorkflowEvent {
  type: 'node_start' | 'node_complete' | 'node_result' | 'log' | 'status' | 'ping' | 'done'
  node_id?: string
  name?: string
  status?: string
  message?: string
  level?: string
  time?: string
  error?: string
  output?: any
  duration_ms?: number
  model?: string
  provider?: string
  tokens?: number
  tool?: string
}

// Report Types
export interface ReportTemplate {
  id: string
  name: string
  description: string
  sections: string[]
}

export interface ResearchReport {
  id: string
  title: string
  template: string
  template_name: string
  status: 'generating' | 'completed' | 'failed'
  content: string | null
  sections: string[]
  params: Record<string, any>
  created_at: string
  updated_at: string
}

// Research Goal Types
export interface ResearchGoal {
  id: string
  goal: string
  status: string
  plan: { step: number; name: string; description: string; tool: string; status: string }[]
  results: { step: number; name: string; status: string; output: string; duration_ms: number }[]
  insights: string[]
  created_at: string
  updated_at: string
}

// Chat Types
export interface ChatResponse {
  run_id: string
  workflow_id: string
  agent_run_id: string
  status: string
  conversation_id?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'progress' | 'report'
  content: string
  timestamp: string
  nodeStatuses?: Record<string, NodeResult>
  workflowStatus?: string
  reportMetadata?: {
    duration_ms: number
    nodes_executed: number
    generated_at: string
  }
}

// Common Types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}
