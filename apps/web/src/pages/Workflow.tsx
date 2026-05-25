import { useEffect, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Clock,
  Cpu,
  FileText,
  GitBranch,
  Layers,
  Loader2,
  Play,
  Square,
  Terminal,
  XCircle,
  Zap,
} from 'lucide-react'
import { useWorkflowStore } from '@/store/workflowStore'
import { emit } from '@/lib/eventBus'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'


// ---------------------------------------------------------------------------
// Node status colors
// ---------------------------------------------------------------------------
const STATUS_COLORS: Record<string, string> = {
  pending: '#64748b',
  running: '#3b82f6',
  completed: '#22c55e',
  failed: '#ef4444',
  skipped: '#a1a1aa',
}

const STATUS_BG: Record<string, string> = {
  pending: 'rgba(100,116,139,0.1)',
  running: 'rgba(59,130,246,0.15)',
  completed: 'rgba(34,197,94,0.1)',
  failed: 'rgba(239,68,68,0.1)',
  skipped: 'rgba(161,161,170,0.08)',
}

// ---------------------------------------------------------------------------
// Custom DAG Node
// ---------------------------------------------------------------------------
function DagNode({ data }: NodeProps) {
  const status = data.status || 'pending'
  const color = STATUS_COLORS[status]
  const bg = STATUS_BG[status]
  const iconMap: Record<string, JSX.Element> = {
    pending: <Clock className="h-4 w-4" />,
    running: <Loader2 className="h-4 w-4 animate-spin" />,
    completed: <CheckCircle2 className="h-4 w-4" />,
    failed: <XCircle className="h-4 w-4" />,
    skipped: <ChevronRight className="h-4 w-4" />,
  }
  const icon = iconMap[status] || <Clock className="h-4 w-4" />

  const typeIconMap: Record<string, JSX.Element> = {
    task: <Cpu className="h-3 w-3" />,
    condition: <GitBranch className="h-3 w-3" />,
    start: <Play className="h-3 w-3" />,
    end: <Square className="h-3 w-3" />,
    parallel: <Layers className="h-3 w-3" />,
    loop: <Activity className="h-3 w-3" />,
  }
  const typeIcon = typeIconMap[data.nodeType] || <Cpu className="h-3 w-3" />

  return (
    <div
      className="relative rounded-lg border-2 px-4 py-3 shadow-lg transition-all"
      style={{
        borderColor: color,
        background: bg,
        minWidth: 180,
        backdropFilter: 'blur(8px)',
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-500" />
      <div className="flex items-center gap-2">
        <span style={{ color }}>{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">{typeIcon}</span>
            <span className="text-sm font-semibold text-gray-100 truncate">{data.label}</span>
          </div>
          {data.subtitle && (
            <p className="mt-0.5 text-xs text-gray-500 truncate">{data.subtitle}</p>
          )}
        </div>
      </div>
      {data.duration_ms != null && (
        <div className="mt-1.5 flex items-center gap-2 text-xs text-gray-500">
          <span>{data.duration_ms}ms</span>
          {data.tokens != null && <span>{data.tokens} tok</span>}
          {data.model && <span className="truncate">{data.model}</span>}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-500" />
    </div>
  )
}

const nodeTypes = { dagNode: DagNode }

// ---------------------------------------------------------------------------
// Log level styling
// ---------------------------------------------------------------------------
const LOG_LEVEL_STYLES: Record<string, string> = {
  info: 'text-blue-400',
  warn: 'text-yellow-400',
  error: 'text-red-400',
  debug: 'text-gray-500',
}

// ---------------------------------------------------------------------------
// Main Workflow Page
// ---------------------------------------------------------------------------
export default function Workflow() {
  const {
    workflows,
    templates,
    selectedWorkflow,
    currentRun,
    runLogs,
    nodeStatuses,
    loading,
    fetchWorkflows,
    fetchTemplates,
    selectWorkflow,
    createFromTemplate,
    startRun,
    cancelRun,
  } = useWorkflowStore()

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([])
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const [activeTab, setActiveTab] = useState<'dag' | 'logs' | 'details'>('dag')

  useEffect(() => {
    fetchWorkflows()
    fetchTemplates()
  }, [fetchWorkflows, fetchTemplates])

  // Convert workflow DAG to React Flow nodes/edges
  useEffect(() => {
    if (!selectedWorkflow?.dag?.nodes) {
      setRfNodes([])
      setRfEdges([])
      return
    }

    const nodes = selectedWorkflow.dag.nodes
    // Layout: topological sort with level assignment
    const inDeg: Record<string, number> = {}
    const children: Record<string, string[]> = {}
    nodes.forEach((n) => {
      inDeg[n.id] = n.dependencies.length
      children[n.id] = []
    })
    nodes.forEach((n) => {
      n.dependencies.forEach((dep) => {
        children[dep]?.push(n.id)
      })
    })

    const levels: string[][] = []
    const queue = nodes.filter((n) => inDeg[n.id] === 0).map((n) => n.id)
    const levelMap: Record<string, number> = {}
    let currentLevel = 0

    while (queue.length > 0) {
      const levelSize = queue.length
      const levelNodes = queue.splice(0, levelSize)
      levels.push(levelNodes)
      levelNodes.forEach((nid) => {
        levelMap[nid] = currentLevel
        children[nid]?.forEach((child) => {
          inDeg[child]--
          if (inDeg[child] === 0) queue.push(child)
        })
      })
      currentLevel++
    }

    const xGap = 260
    const yGap = 120

    const flowNodes: Node[] = nodes.map((n) => {
      const level = levelMap[n.id] ?? 0
      const idx = levels[level]?.indexOf(n.id) ?? 0
      const levelWidth = levels[level]?.length ?? 1
      const x = (idx - (levelWidth - 1) / 2) * xGap + 400
      const y = level * yGap + 50

      const nodeStatus = nodeStatuses[n.id]?.status || 'pending'
      return {
        id: n.id,
        type: 'dagNode',
        position: { x, y },
        data: {
          label: n.name,
          nodeType: n.type,
          status: nodeStatus,
          subtitle: n.config?.type || n.type,
          duration_ms: nodeStatuses[n.id]?.duration_ms,
          tokens: nodeStatuses[n.id]?.tokens,
          model: nodeStatuses[n.id]?.model,
        },
      }
    })

    const flowEdges: Edge[] = []
    nodes.forEach((n) => {
      n.dependencies.forEach((dep) => {
        flowEdges.push({
          id: `${dep}-${n.id}`,
          source: dep,
          target: n.id,
          animated: nodeStatuses[dep]?.status === 'running',
          style: { stroke: STATUS_COLORS[nodeStatuses[dep]?.status || 'pending'], strokeWidth: 2 },
        })
      })
    })

    setRfNodes(flowNodes)
    setRfEdges(flowEdges)
  }, [selectedWorkflow, nodeStatuses, setRfNodes, setRfEdges])

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [runLogs])

  const handleCreateFromTemplate = async (templateId: string) => {
    await createFromTemplate(templateId)
  }

  const handleRun = async () => {
    if (!selectedWorkflow) return
    emit.workflowStarted(selectedWorkflow.name)
    await startRun(selectedWorkflow.id)
  }

  const isRunning = currentRun?.status === 'running'

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0 overflow-hidden">
      {/* Left: Workflow list */}
      <div className="w-72 flex-shrink-0 border-r border-gray-800 bg-gray-950/50 overflow-y-auto">
        <div className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">研究工作流</h2>
          {templates.map((tpl) => (
            <button
              key={tpl.id}
              onClick={() => handleCreateFromTemplate(tpl.id)}
              className="mb-2 w-full rounded-lg border border-gray-800 bg-gray-900/50 p-3 text-left transition-all hover:border-blue-600 hover:bg-gray-900"
            >
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-medium text-gray-200">{tpl.name}</span>
              </div>
              <p className="mt-1 text-xs text-gray-500">{tpl.description}</p>
              <p className="mt-1 text-xs text-gray-600">{tpl.node_count} 个节点</p>
            </button>
          ))}

          {workflows.length > 0 && (
            <>
              <h2 className="mb-3 mt-6 text-sm font-semibold text-gray-400 uppercase tracking-wider">已创建工作流</h2>
              {workflows.map((wf) => (
                <button
                  key={wf.id}
                  onClick={() => selectWorkflow(wf.id)}
                  className={`mb-2 w-full rounded-lg border p-3 text-left transition-all ${
                    selectedWorkflow?.id === wf.id
                      ? 'border-blue-600 bg-blue-950/30'
                      : 'border-gray-800 bg-gray-900/50 hover:border-gray-700'
                  }`}
                >
                  <span className="text-sm font-medium text-gray-200">{wf.name}</span>
                  <p className="mt-0.5 text-xs text-gray-500">{wf.dag?.nodes?.length || 0} 个节点</p>
                </button>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Center: DAG + controls */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b border-gray-800 bg-gray-950/80 px-4 py-2 backdrop-blur">
          <div className="flex items-center gap-3">
            {selectedWorkflow ? (
              <>
                <GitBranch className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-semibold text-gray-200">{selectedWorkflow.name}</span>
                {currentRun && (
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    currentRun.status === 'running' ? 'bg-blue-900/50 text-blue-400' :
                    currentRun.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                    currentRun.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                    'bg-gray-800 text-gray-400'
                  }`}>
                    {currentRun.status}
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-gray-500">选择或创建工作流</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selectedWorkflow && (
              <>
                {isRunning ? (
                  <Button variant="outline" size="sm" onClick={cancelRun} icon={<Square className="h-3.5 w-3.5" />}>
                    停止
                  </Button>
                ) : (
                  <Button size="sm" onClick={handleRun} loading={loading} icon={<Play className="h-3.5 w-3.5" />}>
                    执行
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800 bg-gray-950/50">
          {(['dag', 'logs', 'details'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'dag' && <GitBranch className="h-3.5 w-3.5" />}
              {tab === 'logs' && <Terminal className="h-3.5 w-3.5" />}
              {tab === 'details' && <FileText className="h-3.5 w-3.5" />}
              {tab === 'dag' ? 'DAG' : tab === 'logs' ? '日志' : '详情'}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'dag' && (
            <div className="h-full w-full" style={{ background: '#0a0a0f' }}>
              {selectedWorkflow ? (
                <ReactFlow
                  nodes={rfNodes}
                  edges={rfEdges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  fitView
                  proOptions={{ hideAttribution: true }}
                  minZoom={0.3}
                  maxZoom={2}
                >
                  <Background color="#1e1e2e" gap={20} />
                  <Controls className="!bg-gray-900 !border-gray-700 !shadow-lg [&>button]:!bg-gray-800 [&>button]:!border-gray-700 [&>button]:!text-gray-300 [&>button:hover]:!bg-gray-700" />
                  <MiniMap
                    nodeColor={(n) => STATUS_COLORS[n.data?.status || 'pending']}
                    maskColor="rgba(0,0,0,0.7)"
                    className="!bg-gray-900 !border-gray-700"
                  />
                </ReactFlow>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <GitBranch className="mx-auto mb-4 h-12 w-12 text-gray-700" />
                    <p className="text-gray-500">选择左侧模板开始研究</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="h-full overflow-y-auto bg-gray-950/80 p-4 font-mono text-sm">
              {runLogs.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <Terminal className="mx-auto mb-4 h-10 w-10 text-gray-700" />
                    <p className="text-gray-500">执行工作流后查看实时日志</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  {runLogs.map((log, i) => (
                    <div key={i} className="flex gap-3 py-0.5">
                      <span className="w-20 flex-shrink-0 text-right text-xs text-gray-600">
                        {log.time ? new Date(log.time).toLocaleTimeString('zh-CN') : ''}
                      </span>
                      <span className={`flex-shrink-0 text-xs uppercase ${LOG_LEVEL_STYLES[log.level || 'info']}`}>
                        {log.level || 'info'}
                      </span>
                      {log.node_id && (
                        <span className="flex-shrink-0 rounded bg-gray-800 px-1.5 py-0.5 text-xs text-purple-400">
                          {log.node_id}
                        </span>
                      )}
                      <span className="text-gray-300">{log.message}</span>
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              )}
            </div>
          )}

          {activeTab === 'details' && (
            <div className="h-full overflow-y-auto p-4">
              {currentRun ? (
                <div className="space-y-4">
                  {/* Run info */}
                  <Card variant="bordered">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">执行信息</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-5">
                        {[
                          ['Run ID', currentRun.id?.slice(0, 8)],
                          ['状态', currentRun.status],
                          ['开始时间', currentRun.started_at ? new Date(currentRun.started_at).toLocaleString('zh-CN') : '-'],
                          ['完成时间', currentRun.completed_at ? new Date(currentRun.completed_at).toLocaleString('zh-CN') : '-'],
                          ['总 Tokens', Object.values(currentRun.node_results || {}).reduce((sum, r) => sum + ((r as any).tokens || 0), 0).toLocaleString()],
                        ].map(([label, value]) => (
                          <div key={label}>
                            <p className="text-xs text-gray-500">{label}</p>
                            <p className="mt-0.5 font-medium text-gray-200">{value || '-'}</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Node results table */}
                  <Card variant="bordered">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">节点结果</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-800 text-gray-500">
                              <th className="px-3 py-2 text-left font-medium">节点</th>
                              <th className="px-3 py-2 text-left font-medium">状态</th>
                              <th className="px-3 py-2 text-right font-medium">耗时</th>
                              <th className="px-3 py-2 text-right font-medium">Tokens</th>
                              <th className="px-3 py-2 text-left font-medium">输出</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(currentRun.node_results || {}).map(([nodeId, result]) => {
                              const nodeDef = selectedWorkflow?.dag?.nodes?.find((n) => n.id === nodeId)
                              return (
                                <tr key={nodeId} className="border-b border-gray-900 hover:bg-gray-900/50">
                                  <td className="px-3 py-2 text-gray-200">{nodeDef?.name || nodeId}</td>
                                  <td className="px-3 py-2">
                                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" style={{ color: STATUS_COLORS[result.status], background: STATUS_BG[result.status] }}>
                                      {result.status}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-400">
                                    {result.duration_ms != null ? `${result.duration_ms}ms` : '-'}
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-400">
                                    {result.tokens ?? '-'}
                                  </td>
                                  <td className="max-w-xs truncate px-3 py-2 text-xs text-gray-500">
                                    {typeof result.output === 'string'
                                      ? result.output.slice(0, 100)
                                      : result.output
                                      ? JSON.stringify(result.output).slice(0, 100)
                                      : result.error || '-'}
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <FileText className="mx-auto mb-4 h-10 w-10 text-gray-700" />
                    <p className="text-gray-500">执行工作流后查看详情</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
