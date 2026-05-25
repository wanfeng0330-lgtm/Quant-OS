import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketOptions {
  url: string
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  onClose?: (event: CloseEvent) => void
  onOpen?: (event: Event) => void
  reconnectAttempts?: number
  reconnectInterval?: number
}

interface WebSocketState {
  isConnected: boolean
  isReconnecting: boolean
  error: string | null
  lastMessage: any | null
}

export function useWebSocket({
  url,
  onMessage,
  onError,
  onClose,
  onOpen,
  reconnectAttempts = 5,
  reconnectInterval = 3000,
}: WebSocketOptions) {
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isReconnecting: false,
    error: null,
    lastMessage: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = (event) => {
        setState((prev) => ({
          ...prev,
          isConnected: true,
          isReconnecting: false,
          error: null,
        }))
        reconnectCountRef.current = 0
        onOpen?.(event)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setState((prev) => ({
            ...prev,
            lastMessage: data,
          }))
          onMessage?.(data)
        } catch (e) {
          // Handle non-JSON messages
          setState((prev) => ({
            ...prev,
            lastMessage: event.data,
          }))
          onMessage?.(event.data)
        }
      }

      ws.onerror = (event) => {
        setState((prev) => ({
          ...prev,
          error: 'WebSocket error occurred',
        }))
        onError?.(event)
      }

      ws.onclose = (event) => {
        setState((prev) => ({
          ...prev,
          isConnected: false,
        }))
        onClose?.(event)

        // Attempt to reconnect
        if (reconnectCountRef.current < reconnectAttempts) {
          setState((prev) => ({
            ...prev,
            isReconnecting: true,
          }))
          reconnectCountRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: 'Failed to create WebSocket connection',
      }))
    }
  }, [url, onMessage, onError, onClose, onOpen, reconnectAttempts, reconnectInterval])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setState((prev) => ({
      ...prev,
      isConnected: false,
      isReconnecting: false,
    }))
  }, [])

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
      return true
    }
    return false
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    ...state,
    send,
    connect,
    disconnect,
  }
}