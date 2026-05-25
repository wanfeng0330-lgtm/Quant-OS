import { create } from 'zustand'
import { backtestApi } from '@/api/services'
import type { BacktestResult, BacktestRun } from '@/api/types'
import { cache, generateCacheKey } from '@/utils/cache'

interface BacktestState {
  backtestRuns: BacktestRun[]
  currentResult: BacktestResult | null
  loading: boolean
  error: string | null

  // Actions
  runBacktest: (params: {
    strategy_id: string
    start_date: string
    end_date: string
    benchmark?: string
    initial_capital?: number
    commission_rate?: number
    slippage_rate?: number
  }) => Promise<void>
  fetchBacktestResult: (backtestId: string) => Promise<void>
  listBacktests: (strategyId?: string, status?: string) => Promise<void>
  clearError: () => void
}

export const useBacktestStore = create<BacktestState>((set) => ({
  backtestRuns: [],
  currentResult: null,
  loading: false,
  error: null,

  runBacktest: async (params) => {
    set({ loading: true, error: null })
    try {
      const response = await backtestApi.runBacktest(params)
      if (response.data.success) {
        set({ currentResult: response.data.data || null })
        // Clear backtest list cache when new backtest is run
        cache.delete('backtest/list')
      } else {
        set({ error: response.data.error || 'Backtest failed' })
      }
    } catch (error) {
      set({ error: 'Failed to run backtest' })
    } finally {
      set({ loading: false })
    }
  },

  fetchBacktestResult: async (backtestId: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('backtest/result', { backtestId })

      // Check cache first
      const cachedData = cache.get<BacktestResult>(cacheKey)
      if (cachedData) {
        set({ currentResult: cachedData, loading: false })
        return
      }

      const response = await backtestApi.getBacktestResult(backtestId)
      if (response.data.success) {
        set({ currentResult: response.data.data || null })
        // Cache the result for 10 minutes
        cache.set(cacheKey, response.data.data, 10 * 60 * 1000)
      } else {
        set({ error: response.data.error || 'Failed to fetch result' })
      }
    } catch (error) {
      set({ error: 'Failed to fetch backtest result' })
    } finally {
      set({ loading: false })
    }
  },

  listBacktests: async (strategyId?: string, status?: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('backtest/list', { strategyId, status })

      // Check cache first
      const cachedData = cache.get<BacktestRun[]>(cacheKey)
      if (cachedData) {
        set({ backtestRuns: cachedData, loading: false })
        return
      }

      const response = await backtestApi.listBacktests(strategyId, status, 20)
      if (response.data.success) {
        set({ backtestRuns: response.data.data || [] })
        // Cache the result for 2 minutes
        cache.set(cacheKey, response.data.data, 2 * 60 * 1000)
      } else {
        set({ error: response.data.error || 'Failed to list backtests' })
      }
    } catch (error) {
      set({ error: 'Failed to list backtests' })
    } finally {
      set({ loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))