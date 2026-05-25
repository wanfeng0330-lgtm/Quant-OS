import apiClient from './client'
import type {
  Stock,
  StockPrice,
  StockSearchParams,
  StockListParams,
  Factor,
  FactorValue,
  FactorComputeParams,
  FactorAnalysis,
  BacktestParams,
  BacktestResult,
  BacktestRun,
  Agent,
  AgentRun,
  PaginatedResponse,
  ApiResponse,
  Workflow,
  WorkflowTemplate,
  WorkflowRun,
  ReportTemplate,
  ResearchReport,
  ResearchGoal,
  ChatResponse,
} from './types'

// Market Data API
export const marketApi = {
  getStock: (tsCode: string) =>
    apiClient.get<ApiResponse<Stock>>(`/v1/market/stocks/${tsCode}`),

  searchStocks: (params: StockSearchParams) =>
    apiClient.get<ApiResponse<Stock[]>>('/v1/market/stocks/search', { params }),

  listStocks: (params: StockListParams) =>
    apiClient.get<ApiResponse<PaginatedResponse<Stock>>>('/v1/market/stocks', { params }),

  getStockPrices: (tsCode: string, startDate?: string, endDate?: string, limit?: number) =>
    apiClient.get<ApiResponse<StockPrice[]>>(`/v1/market/stocks/${tsCode}/ohlcv`, {
      params: { start_date: startDate, end_date: endDate, limit },
    }),
}

// Factor API
export const factorApi = {
  listFactors: (category?: string) =>
    apiClient.get<ApiResponse<Factor[]>>('/v1/factors', { params: { category } }),

  getFactor: (factorId: string) =>
    apiClient.get<ApiResponse<Factor>>(`/v1/factors/${factorId}`),

  computeFactor: (params: FactorComputeParams) =>
    apiClient.post<ApiResponse<{ factor_name: string; values: FactorValue[]; count: number }>>(
      '/v1/factors/compute',
      params
    ),

  analyzeFactor: (factorName: string, startDate: string, endDate: string, method?: string) =>
    apiClient.post<ApiResponse<FactorAnalysis>>('/v1/factors/analyze', {
      factor_name: factorName,
      start_date: startDate,
      end_date: endDate,
      method,
    }),

  evaluateExpression: (expression: string, startDate: string, endDate: string, stockPool?: string[]) =>
    apiClient.post<ApiResponse<{ values: FactorValue[]; count: number; expression: string; coverage: string }>>(
      '/v1/factors/evaluate',
      { expression, start_date: startDate, end_date: endDate, stock_pool: stockPool }
    ),

  listFunctions: () =>
    apiClient.get<ApiResponse<{ name: string; description: string }[]>>('/v1/factors/functions'),

  getIcAnalysis: (factorId: string, startDate: string, endDate: string) =>
    apiClient.get<ApiResponse<{
      factor_name?: string
      ic_series: { date: string; ic: number; rank_ic: number }[]
      ic_mean: number
      ic_std: number
      icir: number
      rank_ic_mean: number
      ic_positive_ratio: number
      periods: number
    }>>(`/v1/factors/${factorId}/ic-analysis`, { params: { start_date: startDate, end_date: endDate } }),

  getLayeredReturns: (factorId: string, startDate: string, endDate: string, layers?: number) =>
    apiClient.get<ApiResponse<{
      factor_name?: string
      layers: { layer: number; avg_daily_return: number; cumulative_return: number; stocks_avg: number }[]
      long_short: { avg_daily_return: number; cumulative_return: number; sharpe: number; win_rate: number }
      total_periods: number
    }>>(`/v1/factors/${factorId}/layered`, { params: { start_date: startDate, end_date: endDate, layers } }),
}

// Backtest API
export const backtestApi = {
  runBacktest: (params: BacktestParams) =>
    apiClient.post<ApiResponse<BacktestResult>>('/v1/backtest/run', params),

  getBacktestResult: (backtestId: string) =>
    apiClient.get<ApiResponse<BacktestResult>>(`/v1/backtest/${backtestId}`),

  listBacktests: (strategyId?: string, status?: string, limit?: number) =>
    apiClient.get<ApiResponse<BacktestRun[]>>('/v1/backtest', {
      params: { strategy_id: strategyId, status, limit },
    }),
}

// Agent API
export const agentApi = {
  listAgents: () =>
    apiClient.get<ApiResponse<Agent[]>>('/v1/agents'),

  getAgent: (agentId: string) =>
    apiClient.get<ApiResponse<Agent>>(`/v1/agents/${agentId}`),

  startAgentRun: (agentId: string, message: string) =>
    apiClient.post<ApiResponse<AgentRun>>(`/v1/agents/${agentId}/runs`, { message }),

  getAgentRun: (runId: string) =>
    apiClient.get<ApiResponse<AgentRun>>(`/v1/agents/runs/${runId}`),

  listAgentRuns: (agentId: string, limit?: number) =>
    apiClient.get<ApiResponse<AgentRun[]>>(`/v1/agents/${agentId}/runs`, {
      params: { limit },
    }),
}

// Workflow API
export const workflowApi = {
  listWorkflows: () =>
    apiClient.get<ApiResponse<Workflow[]>>('/v1/workflows'),

  listTemplates: () =>
    apiClient.get<ApiResponse<WorkflowTemplate[]>>('/v1/workflows/templates'),

  createWorkflow: (data: { name: string; description?: string; dag?: any; template?: string }) =>
    apiClient.post<ApiResponse<Workflow>>('/v1/workflows', data),

  getWorkflow: (workflowId: string) =>
    apiClient.get<ApiResponse<Workflow>>(`/v1/workflows/${workflowId}`),

  runWorkflow: (workflowId: string, input?: Record<string, any>) =>
    apiClient.post<ApiResponse<{ run_id: string; workflow_id: string; status: string }>>(
      `/v1/workflows/${workflowId}/run`,
      { input: input || {} }
    ),

  getWorkflowRun: (runId: string) =>
    apiClient.get<ApiResponse<WorkflowRun>>(`/v1/workflows/runs/${runId}`),

  listWorkflowRuns: (workflowId: string, limit?: number) =>
    apiClient.get<ApiResponse<WorkflowRun[]>>(`/v1/workflows/${workflowId}/runs`, { params: { limit } }),

  cancelWorkflowRun: (runId: string) =>
    apiClient.post<ApiResponse<{ status: string }>>(`/v1/workflows/runs/${runId}/cancel`),
}

// Sentiment API
export const sentimentApi = {
  getOverview: () =>
    apiClient.get<ApiResponse<{
      date: string
      limit_up_count: number
      limit_down_count: number
      consecutive_high: number
      market_sentiment: string
      sentiment_score: number
      up_count: number
      down_count: number
      flat_count: number
      total_volume_billion: number
      total_amount_billion: number
    }>>('/v1/sentiment/overview'),

  getNorthbound: () =>
    apiClient.get<ApiResponse<{
      today_net_flow_billion: number
      today_status: string
      monthly_net_flow_billion: number
      flows: { date: string; net_flow_billion: number; cumulative_billion: number }[]
      top_buy: { name: string; net_buy_million: number }[]
      top_sell: { name: string; net_sell_million: number }[]
    }>>('/v1/sentiment/northbound'),

  getDragonTiger: () =>
    apiClient.get<ApiResponse<{
      date: string
      entries: { ts_code: string; name: string; pct_chg: number; net_buy_million: number; reason: string }[]
      summary: string
    }>>('/v1/sentiment/dragon-tiger'),

  getIndustryRotation: () =>
    apiClient.get<ApiResponse<{
      date: string
      industries: { name: string; pct_1d: number; pct_5d: number; pct_20d: number; net_flow_million: number; momentum: string }[]
      hot_sectors: string[]
      cold_sectors: string[]
    }>>('/v1/sentiment/industry-rotation'),

  getLimitStats: () =>
    apiClient.get<ApiResponse<{
      date: string
      limit_up_count: number
      limit_down_count: number
      consecutive_high: number
      limit_up_stocks: { name: string; ts_code: string; reason: string; consecutive: number }[]
      limit_down_stocks: { name: string; ts_code: string; reason: string }[]
      limit_up_reasons: Record<string, number>
    }>>('/v1/sentiment/limit-stats'),
}

// Report API
export const reportApi = {
  listTemplates: () =>
    apiClient.get<ApiResponse<ReportTemplate[]>>('/v1/reports/templates'),

  listReports: () =>
    apiClient.get<ApiResponse<ResearchReport[]>>('/v1/reports'),

  getReport: (reportId: string) =>
    apiClient.get<ApiResponse<ResearchReport>>(`/v1/reports/${reportId}`),

  generateReport: (data: { template: string; title?: string; params?: Record<string, any> }) =>
    apiClient.post<ApiResponse<ResearchReport>>('/v1/reports', data),

  deleteReport: (reportId: string) =>
    apiClient.delete<ApiResponse<{ deleted: boolean }>>(`/v1/reports/${reportId}`),
}

// Research Goal API
export const researchApi = {
  createGoal: (goal: string, context?: Record<string, any>) =>
    apiClient.post<ApiResponse<ResearchGoal>>('/v1/research/goals', { goal, context: context || {} }),

  listGoals: () =>
    apiClient.get<ApiResponse<ResearchGoal[]>>('/v1/research/goals'),

  getGoal: (goalId: string) =>
    apiClient.get<ApiResponse<ResearchGoal>>(`/v1/research/goals/${goalId}`),

  deleteGoal: (goalId: string) =>
    apiClient.delete<ApiResponse<{ deleted: boolean }>>(`/v1/research/goals/${goalId}`),
}

// Chat API
export const chatApi = {
  sendResearchMessage: (message: string, conversationId?: string) =>
    apiClient.post<ApiResponse<ChatResponse>>('/v1/agents/chat/research', {
      message,
      conversation_id: conversationId,
    }),
}

// System API
export const systemApi = {
  healthCheck: () =>
    apiClient.get<ApiResponse<{ status: string; components: Record<string, any> }>>('/v1/system/health'),
}

// Data Sync API
export const syncApi = {
  getStatus: () =>
    apiClient.get<ApiResponse<any>>('/v1/sync/status'),
  triggerSync: () =>
    apiClient.post<ApiResponse<any>>('/v1/sync/all'),
  runSyncNow: () =>
    apiClient.post<ApiResponse<any>>('/v1/sync/run'),
}
