import { create } from 'zustand'
import { factorApi } from '@/api/services'
import type { Factor, FactorValue, FactorAnalysis } from '@/api/types'
import { cache, generateCacheKey } from '@/utils/cache'

interface FactorState {
  factors: Factor[]
  selectedFactor: Factor | null
  factorValues: FactorValue[]
  factorAnalysis: FactorAnalysis | null
  loading: boolean
  error: string | null

  // Actions
  fetchFactors: (category?: string) => Promise<void>
  selectFactor: (factorId: string) => Promise<void>
  computeFactor: (params: {
    factor_name: string
    start_date: string
    end_date: string
    stock_pool?: string[]
    params?: Record<string, any>
  }) => Promise<void>
  analyzeFactor: (factorName: string, startDate: string, endDate: string, method?: string) => Promise<void>
  clearError: () => void
}

export const useFactorStore = create<FactorState>((set) => ({
  factors: [],
  selectedFactor: null,
  factorValues: [],
  factorAnalysis: null,
  loading: false,
  error: null,

  fetchFactors: async (category?: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('factors/list', { category })

      // Check cache first
      const cachedData = cache.get<Factor[]>(cacheKey)
      if (cachedData) {
        set({ factors: cachedData, loading: false })
        return
      }

      const response = await factorApi.listFactors(category)
      if (response.data.success) {
        set({ factors: response.data.data || [] })
        // Cache the result for 5 minutes
        cache.set(cacheKey, response.data.data, 5 * 60 * 1000)
      } else {
        set({ error: response.data.error || 'Failed to fetch factors' })
      }
    } catch (error) {
      set({ error: 'Failed to fetch factors' })
    } finally {
      set({ loading: false })
    }
  },

  selectFactor: async (factorId: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('factors/detail', { factorId })

      // Check cache first
      const cachedData = cache.get<Factor>(cacheKey)
      if (cachedData) {
        set({ selectedFactor: cachedData, loading: false })
        return
      }

      const response = await factorApi.getFactor(factorId)
      if (response.data.success) {
        set({ selectedFactor: response.data.data || null })
        // Cache the result for 5 minutes
        cache.set(cacheKey, response.data.data, 5 * 60 * 1000)
      } else {
        set({ error: response.data.error || 'Failed to get factor' })
      }
    } catch (error) {
      set({ error: 'Failed to get factor details' })
    } finally {
      set({ loading: false })
    }
  },

  computeFactor: async (params) => {
    set({ loading: true, error: null })
    try {
      const response = await factorApi.computeFactor(params)
      if (response.data.success) {
        set({ factorValues: response.data.data?.values || [] })
      } else {
        set({ error: response.data.error || 'Failed to compute factor' })
      }
    } catch (error) {
      set({ error: 'Failed to compute factor' })
    } finally {
      set({ loading: false })
    }
  },

  analyzeFactor: async (factorName: string, startDate: string, endDate: string, method?: string) => {
    set({ loading: true, error: null })
    try {
      const response = await factorApi.analyzeFactor(factorName, startDate, endDate, method)
      if (response.data.success) {
        set({ factorAnalysis: response.data.data || null })
      } else {
        set({ error: response.data.error || 'Failed to analyze factor' })
      }
    } catch (error) {
      set({ error: 'Failed to analyze factor' })
    } finally {
      set({ loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))