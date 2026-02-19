import { useState } from 'react'

export interface Citation {
  source: string
  chunk_index: number
  excerpt?: string
}

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  timestamp?: Date
  username?: string
}

export function MessageBubble({ role, content, citations = [], timestamp, username }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const timeStr = timestamp?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <div className={`flex gap-3 ${role === 'user' ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-semibold ${
          role === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-200 text-gray-600 dark:bg-gray-600 dark:text-gray-300'
        }`}
      >
        {role === 'user' ? (username?.[0]?.toUpperCase() || 'U') : '◇'}
      </div>
      <div className={`flex max-w-[85%] flex-col ${role === 'user' ? 'items-end' : ''}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            role === 'user'
              ? 'bg-blue-600 text-white'
              : 'border border-gray-200 bg-white dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100'
          }`}
        >
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{content}</p>
          {role === 'assistant' && (
            <div className="mt-2 flex items-center gap-2">
              {timeStr && (
                <span className="text-xs text-gray-400 dark:text-gray-500">{timeStr}</span>
              )}
              <button
                onClick={handleCopy}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                title="Copy"
              >
                {copied ? '✓' : '⎘'}
              </button>
            </div>
          )}
        </div>
        {role === 'assistant' && citations.length > 0 && (
          <div className="mt-2 w-full">
            <button
              onClick={() => setSourcesOpen(!sourcesOpen)}
              className="flex items-center gap-1 rounded-xl border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50"
            >
              Cited from {citations.length} source{citations.length > 1 ? 's' : ''}
              <span className={sourcesOpen ? 'rotate-180' : ''}>▼</span>
            </button>
            {sourcesOpen && (
              <ul className="mt-2 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800/50">
                {citations.map((c, i) => (
                  <li
                    key={i}
                    className="rounded-lg border-l-2 border-blue-500 bg-white px-3 py-2 text-xs dark:bg-gray-800"
                  >
                    <span className="font-medium text-gray-900 dark:text-white">{c.source}</span>
                    <span className="ml-1 text-gray-500">Chunk {c.chunk_index}</span>
                    {c.excerpt && (
                      <p className="mt-1 text-gray-600 dark:text-gray-400 line-clamp-2">{c.excerpt}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
