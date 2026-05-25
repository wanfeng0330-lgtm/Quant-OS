import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../store/chatStore'
import WorkflowProgress from '../components/WorkflowProgress'
import ReportCard from '../components/ReportCard'
import DataSyncStatus from '../components/DataSyncStatus'

const SUGGESTIONS = [
  '分析今日A股市场情绪',
  '研究动量因子的Alpha潜力',
  '北向资金流向与行业轮动分析',
  '综合研究：因子发现与市场研判',
]

export default function Chat() {
  const { messages, isRunning, sendMessage, clearChat, error } = useChatStore()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isRunning) return
    setInput('')
    sendMessage(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSuggestion = (text: string) => {
    setInput(text)
    // Send immediately
    sendMessage(text)
    setInput('')
  }

  const isEmpty = messages.length === 0

  return (
    <div className="h-full flex flex-col">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          /* Welcome state */
          <div className="flex h-full flex-col items-center justify-center px-4">
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500/20 to-primary-700/20 border border-primary-500/20">
              <span className="text-3xl">🔬</span>
            </div>
            <h1 className="mb-2 text-2xl font-bold text-gray-100">
              QuantOS AI 量化研究助手
            </h1>
            <p className="mb-6 text-sm text-gray-500 max-w-md text-center leading-relaxed">
              输入你的研究需求，AI 将自动执行数据获取、因子探索、市场分析、情绪研判，最终生成完整的研究报告。
            </p>

            <div className="mb-6 max-w-lg w-full">
              <DataSyncStatus />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-lg w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSuggestion(s)}
                  className="text-left rounded-xl border border-gray-700/50 bg-gray-900/50 px-4 py-3 text-sm text-gray-300 hover:border-primary-500/40 hover:bg-gray-800/50 transition-all group"
                >
                  <span className="group-hover:text-primary-300 transition-colors">{s}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message stream */
          <div className="mx-auto max-w-3xl px-4 py-6 space-y-4">
            {messages.map((msg) => (
              <div key={msg.id}>
                {msg.role === 'user' && (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary-600 px-4 py-2.5 text-sm text-white shadow-lg shadow-primary-900/20">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                )}

                {msg.role === 'progress' && (
                  <div className="flex justify-start">
                    <div className="max-w-[90%]">
                      <WorkflowProgress
                        nodeStatuses={msg.nodeStatuses || {}}
                        workflowStatus={msg.workflowStatus}
                      />
                    </div>
                  </div>
                )}

                {msg.role === 'report' && (
                  <div className="flex justify-start">
                    <div className="max-w-[90%] w-full">
                      <ReportCard
                        content={msg.content}
                        metadata={msg.reportMetadata}
                      />
                    </div>
                  </div>
                )}

                {msg.role === 'assistant' && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-gray-700/50 bg-gray-900/80 px-4 py-2.5 text-sm text-gray-200">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Error display */}
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="shrink-0 border-t border-gray-800/80 bg-gray-950/90 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isRunning
                  ? '研究进行中，请等待...'
                  : '输入研究需求，例如 "分析今日市场情绪"'
              }
              disabled={isRunning}
              rows={1}
              className="w-full resize-none rounded-xl border border-gray-700/50 bg-gray-900/80 px-4 py-3 pr-12 text-sm text-gray-200 placeholder-gray-600 focus:border-primary-500/50 focus:outline-none focus:ring-1 focus:ring-primary-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={isRunning || !input.trim()}
              className="absolute right-2 bottom-2 rounded-lg bg-primary-600 p-2 text-white hover:bg-primary-500 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              {isRunning ? (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
              )}
            </button>
          </div>

          {/* Clear chat button */}
          {messages.length > 0 && (
            <div className="mt-2 flex justify-center">
              <button
                onClick={clearChat}
                className="text-[11px] text-gray-600 hover:text-gray-400 transition-colors"
              >
                清空对话
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
