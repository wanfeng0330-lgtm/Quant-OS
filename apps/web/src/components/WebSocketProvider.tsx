import { useEffect, ReactNode } from 'react'
import { useWebSocketStore } from '@/services/websocketService'

interface WebSocketProviderProps {
  children: ReactNode
  url?: string
}

const defaultWsUrl = import.meta.env.VITE_WS_URL || ''

export default function WebSocketProvider({
  children,
  url = defaultWsUrl,
}: WebSocketProviderProps) {
  const { connect, disconnect, isConnected } = useWebSocketStore()

  useEffect(() => {
    if (!url) return
    connect(url)
    return () => {
      disconnect()
    }
  }, [connect, disconnect, url])

  return (
    <>
      {children}
      {url && !isConnected && (
        <div className="fixed inset-x-4 bottom-20 z-50 sm:inset-x-auto sm:bottom-4 sm:right-4">
          <div className="mx-auto flex max-w-xs items-center justify-center gap-2 rounded-md border border-warning-200 bg-warning-100 px-3 py-2 shadow-lg dark:border-warning-700 dark:bg-warning-900/50">
            <div className="h-2 w-2 rounded-full bg-warning-500" />
            <span className="truncate text-sm text-warning-700 dark:text-warning-300">
              WebSocket 连接中
            </span>
          </div>
        </div>
      )}
    </>
  )
}
