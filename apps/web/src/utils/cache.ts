/**
 * Simple in-memory cache with TTL support
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

class Cache {
  private store: Map<string, CacheEntry<any>> = new Map()
  private defaultTTL: number = 5 * 60 * 1000 // 5 minutes

  /**
   * Get a value from cache
   * @param key Cache key
   * @returns Cached value or undefined if not found/expired
   */
  get<T>(key: string): T | undefined {
    const entry = this.store.get(key)
    if (!entry) return undefined

    const now = Date.now()
    if (now - entry.timestamp > entry.ttl) {
      this.store.delete(key)
      return undefined
    }

    return entry.data as T
  }

  /**
   * Set a value in cache
   * @param key Cache key
   * @param data Data to cache
   * @param ttl Time to live in milliseconds (optional, uses default if not provided)
   */
  set<T>(key: string, data: T, ttl?: number): void {
    this.store.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTTL,
    })
  }

  /**
   * Check if a key exists and is not expired
   * @param key Cache key
   * @returns True if key exists and is not expired
   */
  has(key: string): boolean {
    return this.get(key) !== undefined
  }

  /**
   * Remove a specific key from cache
   * @param key Cache key
   */
  delete(key: string): void {
    this.store.delete(key)
  }

  /**
   * Clear all cache entries
   */
  clear(): void {
    this.store.clear()
  }

  /**
   * Get cache stats
   * @returns Object with cache size and hit rate info
   */
  stats(): { size: number } {
    return { size: this.store.size }
  }
}

// Create a singleton cache instance
export const cache = new Cache()

/**
 * Generate cache key from API endpoint and params
 * @param endpoint API endpoint
 * @param params Request parameters
 * @returns Cache key string
 */
export function generateCacheKey(endpoint: string, params?: Record<string, any>): string {
  if (!params) return endpoint

  const sortedParams = Object.keys(params)
    .sort()
    .filter(key => params[key] !== undefined && params[key] !== null)
    .map(key => `${key}=${JSON.stringify(params[key])}`)
    .join('&')

  return sortedParams ? `${endpoint}?${sortedParams}` : endpoint
}