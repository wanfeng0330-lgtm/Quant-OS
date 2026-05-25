import { create } from 'zustand'
import { marketApi } from '@/api/services'
import type { Stock, StockPrice } from '@/api/types'
import { cache, generateCacheKey } from '@/utils/cache'

interface MarketState {
  stocks: Stock[]
  selectedStock: Stock | null
  stockPrices: StockPrice[]
  loading: boolean
  error: string | null
  page: number
  pageSize: number
  total: number
  keyword: string

  // Actions
  searchStocks: (keyword: string, page?: number) => Promise<void>
  selectStock: (tsCode: string) => Promise<void>
  fetchStockPrices: (tsCode: string, startDate?: string, endDate?: string) => Promise<void>
  clearError: () => void
}

export const useMarketStore = create<MarketState>((set, get) => ({
  stocks: [],
  selectedStock: null,
  stockPrices: [],
  loading: false,
  error: null,
  page: 1,
  pageSize: 100,
  total: 0,
  keyword: '',

  searchStocks: async (keyword: string, page?: number) => {
    const currentPage = page || 1
    const { pageSize } = get()
    set({ loading: true, error: null, keyword })
    try {
      const trimmed = keyword.trim()

      if (trimmed) {
        const response = await marketApi.searchStocks({ keyword: trimmed, limit: 100 })
        if (response.data.success) {
          const data = response.data.data as any
          const stocks: Stock[] = Array.isArray(data) ? data : data?.items || []
          set({ stocks, page: 1, total: stocks.length })
        } else {
          set({ error: response.data.error || '搜索股票失败' })
        }
      } else {
        const response = await marketApi.listStocks({ page: currentPage, size: pageSize })
        if (response.data.success) {
          const data = response.data.data as any
          const stocks: Stock[] = data?.items || []
          set({ stocks, page: currentPage, total: data?.total || 0 })
        } else {
          set({ error: response.data.error || '获取股票列表失败' })
        }
      }
    } catch (error) {
      set({ error: '搜索股票失败' })
    } finally {
      set({ loading: false })
    }
  },

  selectStock: async (tsCode: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('stocks/detail', { tsCode })

      // Check cache first
      const cachedData = cache.get<Stock>(cacheKey)
      if (cachedData) {
        set({ selectedStock: cachedData })
        await get().fetchStockPrices(tsCode)
        set({ loading: false })
        return
      }

      const response = await marketApi.getStock(tsCode)
      if (response.data.success) {
        set({ selectedStock: response.data.data || null })
        // Cache the result for 5 minutes
        cache.set(cacheKey, response.data.data, 5 * 60 * 1000)
        await get().fetchStockPrices(tsCode)
      } else {
        set({ error: response.data.error || '获取股票详情失败' })
      }
    } catch (error) {
      set({ error: '获取股票详情失败' })
    } finally {
      set({ loading: false })
    }
  },

  fetchStockPrices: async (tsCode: string, startDate?: string, endDate?: string) => {
    set({ loading: true, error: null })
    try {
      const cacheKey = generateCacheKey('stocks/ohlcv', { tsCode, startDate, endDate })

      // Check cache first
      const cachedData = cache.get<StockPrice[]>(cacheKey)
      if (cachedData) {
        set({ stockPrices: cachedData, loading: false })
        return
      }

      const response = await marketApi.getStockPrices(tsCode, startDate, endDate, 100)
      if (response.data.success) {
        set({ stockPrices: response.data.data || [] })
        // Cache the result for 1 minute (price data changes frequently)
        cache.set(cacheKey, response.data.data, 60 * 1000)
      } else {
        set({ error: response.data.error || '获取行情失败' })
      }
    } catch (error) {
      set({ error: '获取行情失败' })
    } finally {
      set({ loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
