import { useEffect, useState } from 'react'
import {
  BookOpen,
  FileText,
  Plus,
  Trash2,
  RefreshCw,
  TrendingUp,
  BarChart3,
  PieChart,
  Zap,
} from 'lucide-react'
import { reportApi } from '@/api/services'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import type { ReportTemplate, ResearchReport } from '@/api/types'

const TEMPLATE_ICONS: Record<string, JSX.Element> = {
  factor_analysis: <BarChart3 className="h-5 w-5" />,
  market_review: <TrendingUp className="h-5 w-5" />,
  portfolio_review: <PieChart className="h-5 w-5" />,
  alpha_research: <Zap className="h-5 w-5" />,
}

export default function Reports() {
  const [templates, setTemplates] = useState<ReportTemplate[]>([])
  const [reports, setReports] = useState<ResearchReport[]>([])
  const [selectedReport, setSelectedReport] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState<'list' | 'templates'>('list')

  useEffect(() => {
    loadTemplates()
    loadReports()
  }, [])

  const loadTemplates = async () => {
    try {
      const res = await reportApi.listTemplates()
      setTemplates(res.data.data || [])
    } catch { /* ignore */ }
  }

  const loadReports = async () => {
    setLoading(true)
    try {
      const res = await reportApi.listReports()
      setReports(res.data.data || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleGenerate = async (templateId: string) => {
    setGenerating(true)
    try {
      const res = await reportApi.generateReport({
        template: templateId,
        params: { start_date: '2026-01-01', end_date: '2026-05-25' },
      })
      const report = res.data.data
      if (report) {
        setReports(prev => [report, ...prev])
        setSelectedReport(report)
        setActiveTab('list')
      }
    } catch { /* ignore */ }
    setGenerating(false)
  }

  const handleDelete = async (reportId: string) => {
    try {
      await reportApi.deleteReport(reportId)
      setReports(prev => prev.filter(r => r.id !== reportId))
      if (selectedReport?.id === reportId) setSelectedReport(null)
    } catch { /* ignore */ }
  }

  const renderMarkdown = (content: string) => {
    // Simple markdown-to-HTML rendering
    const lines = content.split('\n')
    const elements: JSX.Element[] = []
    let inTable = false
    let tableRows: string[][] = []
    let tableHeaders: string[] = []

    const flushTable = () => {
      if (tableRows.length > 0) {
        elements.push(
          <div key={`table-${elements.length}`} className="my-4 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  {tableHeaders.map((h, i) => (
                    <th key={i} className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-gray-300">{h.trim()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, ri) => (
                  <tr key={ri} className="border-b border-gray-100 dark:border-gray-800">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 text-gray-600 dark:text-gray-400">{cell.trim()}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        tableRows = []
        tableHeaders = []
      }
      inTable = false
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]

      if (line.startsWith('|') && line.includes('|')) {
        const cells = line.split('|').filter(c => c.trim() !== '')
        if (!inTable) {
          inTable = true
          tableHeaders = cells
        } else if (cells.every(c => /^[-:]+$/.test(c.trim()))) {
          // separator row, skip
        } else {
          tableRows.push(cells)
        }
        continue
      } else if (inTable) {
        flushTable()
      }

      if (line.startsWith('# ')) {
        elements.push(<h1 key={i} className="text-2xl font-bold text-gray-900 dark:text-white mb-4 mt-6">{line.slice(2)}</h1>)
      } else if (line.startsWith('## ')) {
        elements.push(<h2 key={i} className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-3 mt-5">{line.slice(3)}</h2>)
      } else if (line.startsWith('### ')) {
        elements.push(<h3 key={i} className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2 mt-4">{line.slice(4)}</h3>)
      } else if (line.startsWith('> ')) {
        elements.push(<blockquote key={i} className="border-l-4 border-primary-400 pl-4 py-2 my-3 text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 rounded-r">{line.slice(2)}</blockquote>)
      } else if (line.startsWith('---')) {
        elements.push(<hr key={i} className="my-6 border-gray-200 dark:border-gray-700" />)
      } else if (line.startsWith('- **')) {
        const match = line.match(/^- \*\*(.+?)\*\*[:：](.*)$/)
        if (match) {
          elements.push(
            <div key={i} className="flex gap-2 ml-4 mb-1">
              <span className="text-gray-400">-</span>
              <span className="font-semibold text-gray-800 dark:text-gray-200">{match[1]}</span>
              <span className="text-gray-600 dark:text-gray-400">{match[2]}</span>
            </div>
          )
        } else {
          elements.push(<li key={i} className="ml-6 mb-1 text-gray-600 dark:text-gray-400 list-disc">{line.slice(2)}</li>)
        }
      } else if (line.startsWith('- ')) {
        elements.push(<li key={i} className="ml-6 mb-1 text-gray-600 dark:text-gray-400 list-disc">{line.slice(2)}</li>)
      } else if (/^\d+\. /.test(line)) {
        const text = line.replace(/^\d+\. /, '')
        elements.push(<li key={i} className="ml-6 mb-1 text-gray-600 dark:text-gray-400 list-decimal">{text}</li>)
      } else if (line.startsWith('```')) {
        // skip code fence markers
      } else if (line.trim() === '') {
        elements.push(<div key={i} className="h-2" />)
      } else {
        // Inline formatting
        let formatted: string | JSX.Element = line
        formatted = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        formatted = (formatted as string).replace(/`(.+?)`/g, '<code class="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-primary-600 dark:text-primary-400 text-xs font-mono">$1</code>')
        elements.push(<p key={i} className="text-sm text-gray-600 dark:text-gray-400 mb-2 leading-relaxed" dangerouslySetInnerHTML={{ __html: formatted as string }} />)
      }
    }
    if (inTable) flushTable()
    return elements
  }

  return (
    <div className="flex h-full gap-4">
      {/* Left sidebar */}
      <div className="flex w-80 flex-shrink-0 flex-col gap-4">
        {/* Tab switcher */}
        <div className="flex rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
          {[
            { id: 'list' as const, label: '报告列表', icon: <FileText className="h-3.5 w-3.5" /> },
            { id: 'templates' as const, label: '模板', icon: <BookOpen className="h-3.5 w-3.5" /> },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'templates' ? (
          <Card variant="bordered" className="flex-1 overflow-hidden">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">报告模板</CardTitle>
            </CardHeader>
            <CardContent className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 240px)' }}>
              <div className="space-y-2">
                {templates.map(t => (
                  <div key={t.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                    <div className="flex items-center gap-2">
                      <div className="text-primary-500">{TEMPLATE_ICONS[t.id] || <FileText className="h-5 w-5" />}</div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-900 dark:text-white">{t.name}</p>
                        <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">{t.description}</p>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {t.sections.slice(0, 3).map(s => (
                        <span key={s} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">{s}</span>
                      ))}
                      {t.sections.length > 3 && (
                        <span className="text-[10px] text-gray-400">+{t.sections.length - 3}</span>
                      )}
                    </div>
                    <Button
                      size="sm"
                      className="mt-2 w-full"
                      onClick={() => handleGenerate(t.id)}
                      disabled={generating}
                    >
                      {generating ? (
                        <><RefreshCw className="mr-1.5 h-3 w-3 animate-spin" />生成中...</>
                      ) : (
                        <><Plus className="mr-1.5 h-3 w-3" />生成报告</>
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card variant="bordered" className="flex-1 overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm">已生成报告</CardTitle>
              <Button size="sm" variant="ghost" onClick={loadReports}>
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </CardHeader>
            <CardContent className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 240px)' }}>
              <div className="space-y-1">
                {reports.length === 0 && !loading && (
                  <div className="py-10 text-center text-sm text-gray-500">
                    暂无报告，去模板页生成
                  </div>
                )}
                {reports.map(report => (
                  <button
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                      selectedReport?.id === report.id
                        ? 'border-primary-300 bg-primary-50 dark:border-primary-800 dark:bg-primary-950'
                        : 'border-transparent hover:bg-gray-50 dark:hover:bg-gray-800/50'
                    } border`}
                  >
                    <div className="flex items-center justify-between">
                      <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{report.title}</p>
                      <button
                        onClick={e => { e.stopPropagation(); handleDelete(report.id) }}
                        className="ml-2 text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        {report.template_name}
                      </span>
                      <span className={`text-[10px] ${
                        report.status === 'completed' ? 'text-green-500' : 'text-yellow-500'
                      }`}>
                        {report.status === 'completed' ? '已完成' : '生成中'}
                      </span>
                      <span className="text-[10px] text-gray-400">
                        {new Date(report.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Report content */}
      <div className="flex-1 overflow-hidden">
        {selectedReport ? (
          <Card variant="bordered" className="h-full overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 pb-3 dark:border-gray-700">
              <div>
                <CardTitle className="text-base">{selectedReport.title}</CardTitle>
                <p className="mt-0.5 text-xs text-gray-500">
                  {selectedReport.template_name} | {new Date(selectedReport.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  selectedReport.status === 'completed'
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                }`}>
                  {selectedReport.status === 'completed' ? '已完成' : '生成中...'}
                </span>
              </div>
            </CardHeader>
            <CardContent className="overflow-y-auto p-6" style={{ maxHeight: 'calc(100vh - 200px)' }}>
              {selectedReport.content ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {renderMarkdown(selectedReport.content)}
                </div>
              ) : (
                <div className="flex h-64 items-center justify-center">
                  <div className="text-center">
                    <RefreshCw className="mx-auto h-8 w-8 animate-spin text-primary-500" />
                    <p className="mt-3 text-sm text-gray-500">正在生成报告...</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card variant="bordered" className="flex h-full items-center justify-center">
            <div className="text-center">
              <FileText className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-3 text-sm text-gray-500">选择一份报告查看，或从模板生成新报告</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
