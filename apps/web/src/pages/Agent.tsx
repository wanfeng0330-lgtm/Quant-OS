import { useEffect, useState } from 'react'
import { Bot, RefreshCw, Send, User } from 'lucide-react'
import { useAgentStore } from '@/store'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'

export default function Agent() {
  const {
    agents,
    currentAgent,
    currentRun,
    messages,
    loading,
    error,
    fetchAgents,
    selectAgent,
    startRun,
    fetchRun,
  } = useAgentStore()
  const [inputMessage, setInputMessage] = useState('')

  useEffect(() => {
    document.title = 'AI Agent - QuantOS'
    fetchAgents()
  }, [fetchAgents])

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !currentAgent) return
    const content = inputMessage.trim()
    setInputMessage('')
    await startRun(currentAgent.id, content)
  }

  const handleRefreshRun = async () => {
    if (currentRun) {
      await fetchRun(currentRun.id)
    }
  }

  return (
    <div className="space-y-5 sm:space-y-6">
      <Card variant="bordered">
        <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
          <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
            <Bot className="h-5 w-5" />
            AI Agent
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => (
              <button
                type="button"
                key={agent.id}
                onClick={() => selectAgent(agent.id)}
                className={[
                  'rounded-md border p-4 text-left transition-colors',
                  currentAgent?.id === agent.id
                    ? 'border-primary-300 bg-primary-50 dark:border-primary-800 dark:bg-primary-950'
                    : 'border-transparent bg-gray-50 hover:border-gray-200 hover:bg-gray-100 dark:bg-gray-800/70 dark:hover:border-gray-700 dark:hover:bg-gray-800',
                ].join(' ')}
              >
                <div className="flex items-start gap-3">
                  <div className="rounded-md bg-primary-100 p-2 text-primary-700 dark:bg-primary-900 dark:text-primary-300">
                    <Bot className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-gray-950 dark:text-white">{agent.name}</p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {agent.llm_provider || 'llm'} / {agent.llm_model || agent.type}
                    </p>
                    <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">
                      {agent.description}
                    </p>
                  </div>
                </div>
              </button>
            ))}
            {agents.length === 0 && !loading && (
              <div className="col-span-full py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                暂无 Agent
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_22rem]">
        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="flex flex-col gap-3 text-base sm:flex-row sm:items-center sm:justify-between sm:text-lg">
              <span>{currentAgent ? currentAgent.name : '对话'}</span>
              {currentRun && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefreshRun}
                  loading={loading}
                  icon={<RefreshCw className="h-4 w-4" />}
                >
                  刷新
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            {currentAgent ? (
              <div className="space-y-4">
                <div className="h-[28rem] overflow-y-auto rounded-md bg-gray-50 p-3 dark:bg-gray-800/70 sm:p-4">
                  {messages.length > 0 ? (
                    <div className="space-y-4">
                      {messages.map((message, index) => (
                        <div
                          key={message.id || `${message.role}-${index}`}
                          className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={[
                              'max-w-[88%] rounded-md p-3 text-sm shadow-sm sm:max-w-[78%]',
                              message.role === 'user'
                                ? 'bg-primary-600 text-white'
                                : 'bg-white text-gray-900 dark:bg-gray-700 dark:text-white',
                            ].join(' ')}
                          >
                            <div className="flex items-start gap-2">
                              {message.role !== 'user' && <Bot className="mt-0.5 h-4 w-4 flex-none" />}
                              <div className="min-w-0">
                                <p className="whitespace-pre-wrap break-words leading-6">{message.content}</p>
                                {message.timestamp && (
                                  <p className={`mt-2 text-xs ${message.role === 'user' ? 'text-primary-100' : 'text-gray-400'}`}>
                                    {new Date(message.timestamp).toLocaleTimeString()}
                                  </p>
                                )}
                              </div>
                              {message.role === 'user' && <User className="mt-0.5 h-4 w-4 flex-none" />}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center text-center text-gray-500 dark:text-gray-400">
                      <Bot className="mb-3 h-10 w-10" />
                      <p>暂无消息</p>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <Input
                    placeholder="输入量化问题"
                    value={inputMessage}
                    onChange={(event) => setInputMessage(event.target.value)}
                    onKeyDown={(event) => event.key === 'Enter' && handleSendMessage()}
                  />
                  <Button
                    className="sm:w-28"
                    onClick={handleSendMessage}
                    loading={loading}
                    disabled={!inputMessage.trim()}
                    icon={<Send className="h-4 w-4" />}
                  >
                    发送
                  </Button>
                </div>
              </div>
            ) : (
              <div className="py-16 text-center text-gray-500 dark:text-gray-400">
                <Bot className="mx-auto mb-3 h-10 w-10" />
                <p>请选择 Agent</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="bordered">
          <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-2">
            <CardTitle className="text-base sm:text-lg">Agent 信息</CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5">
            {currentAgent ? (
              <div className="space-y-4">
                <div className="rounded-md bg-gray-50 p-4 dark:bg-gray-800/70">
                  <p className="font-medium text-gray-950 dark:text-white">{currentAgent.name}</p>
                  <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{currentAgent.description}</p>
                </div>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-gray-500 dark:text-gray-400">类型</span>
                    <span className="font-medium text-gray-950 dark:text-white">{currentAgent.type}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-gray-500 dark:text-gray-400">Provider</span>
                    <span className="font-medium text-gray-950 dark:text-white">{currentAgent.llm_provider || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-gray-500 dark:text-gray-400">Model</span>
                    <span className="max-w-40 truncate font-medium text-gray-950 dark:text-white">{currentAgent.llm_model || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-gray-500 dark:text-gray-400">状态</span>
                    <span className="rounded bg-success-50 px-2 py-1 text-xs font-medium text-success-700 dark:bg-success-900/40 dark:text-success-300">
                      {currentAgent.status === 'inactive' ? '停用' : '可用'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">暂无详情</div>
            )}
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-md border border-danger-200 bg-danger-50 p-4 text-sm text-danger-700 dark:border-danger-900 dark:bg-danger-900/30 dark:text-danger-200">
          {error}
        </div>
      )}
    </div>
  )
}
