import { useEffect, useRef } from 'react'
import { eventBus, type StreamEvent } from './eventBus'

/**
 * Subscribe to EventBus events in a React component.
 *
 * @example
 * useEventBus('factor_computed', (e) => {
 *   console.log('Factor computed:', e.data)
 * })
 *
 * useEventBus('*', (e) => {
 *   // Handle all events
 * })
 */
export function useEventBus(eventType: string, handler: (event: StreamEvent) => void) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const unsubscribe = eventBus.on(eventType, (event) => handlerRef.current(event))
    return unsubscribe
  }, [eventType])
}

/**
 * Emit events from React components.
 */
export function useEmitEvent() {
  return (eventType: string, data?: Partial<StreamEvent>) => {
    eventBus.emit(eventType, data)
  }
}
