import { useState } from 'react'

interface ReportCardProps {
  content: string
  metadata?: {
    duration_ms: number
    nodes_executed: number
    generated_at: string
  }
}

// ---------------------------------------------------------------------------
// Lightweight markdown renderer (handles the subset used in reports)
// ---------------------------------------------------------------------------

function renderMarkdown(text: string): string {
  let html = text

  // Escape HTML
  html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // Code blocks (```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-gray-800 rounded-md p-3 text-xs overflow-x-auto my-2"><code>$2</code></pre>')

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1.5 py-0.5 rounded text-xs text-emerald-300">$1</code>')

  // Horizontal rule
  html = html.replace(/^---+$/gm, '<hr class="border-gray-700 my-4" />')

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-gray-100 mt-4 mb-2">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold text-gray-100 mt-5 mb-2 pb-1 border-b border-gray-700">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-white mt-4 mb-3">$1</h1>')

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-100 font-semibold">$1</strong>')

  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="border-l-2 border-primary-500 pl-3 text-gray-400 text-sm my-2">$1</blockquote>')

  // Tables
  html = html.replace(/^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm, (_match, headerRow, _separator, bodyRows) => {
    const headers = headerRow.split('|').filter((c: string) => c.trim())
    const rows = bodyRows.trim().split('\n').map((row: string) =>
      row.split('|').filter((c: string) => c.trim())
    )

    let table = '<div class="overflow-x-auto my-3"><table class="w-full text-xs border-collapse">'
    table += '<thead><tr>'
    headers.forEach((h: string) => {
      table += `<th class="bg-gray-800/80 text-gray-300 font-medium px-3 py-2 text-left border border-gray-700">${h.trim()}</th>`
    })
    table += '</tr></thead><tbody>'
    rows.forEach((cells: string[]) => {
      table += '<tr>'
      cells.forEach((c: string) => {
        table += `<td class="px-3 py-1.5 text-gray-300 border border-gray-700/50">${c.trim()}</td>`
      })
      table += '</tr>'
    })
    table += '</tbody></table></div>'
    return table
  })

  // Ordered lists
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal text-gray-300 text-sm">$2</li>')

  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-gray-300 text-sm">$1</li>')

  // Paragraphs (double newline)
  html = html.replace(/\n\n/g, '</p><p class="text-gray-300 text-sm leading-relaxed my-2">')

  // Single newlines within paragraphs
  html = html.replace(/\n/g, '<br />')

  // Wrap in paragraph
  html = `<p class="text-gray-300 text-sm leading-relaxed">${html}</p>`

  return html
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReportCard({ content, metadata }: ReportCardProps) {
  const [expanded, setExpanded] = useState(false)

  const previewLines = content.split('\n').filter((l) => l.trim()).slice(0, 3).join('\n')
  const durationSec = metadata ? (metadata.duration_ms / 1000).toFixed(1) : null

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-900/90 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700/50 bg-gray-800/50 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-green-400 text-sm">📊</span>
          <span className="text-sm font-medium text-gray-200">研究报告</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {durationSec && <span>耗时 {durationSec}s</span>}
          {metadata?.nodes_executed && <span>{metadata.nodes_executed} 个节点</span>}
          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-md bg-gray-700/50 px-2.5 py-1 text-gray-300 hover:bg-gray-700 transition-colors"
          >
            {expanded ? '收起' : '展开全文'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {expanded ? (
          <div
            className="prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />
        ) : (
          <div className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
            {previewLines}
            {content.split('\n').length > 3 && (
              <span className="text-gray-600"> ...</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
