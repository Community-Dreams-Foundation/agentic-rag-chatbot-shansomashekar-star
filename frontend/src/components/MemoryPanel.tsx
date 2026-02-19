import { useState } from 'react'

interface MemoryPanelProps {
  memory: { user_memory: string; company_memory: string }
  insights: string
  loading: boolean
  onDelete: (target: 'USER_MEMORY' | 'COMPANY_MEMORY') => Promise<boolean>
  onToast: (msg: string, type: 'success' | 'error') => void
  onRefresh: () => void
}

export function MemoryPanel({ memory, insights, loading, onDelete, onToast, onRefresh }: MemoryPanelProps) {
  const [expanded, setExpanded] = useState<'user' | 'company' | null>(null)

  const hasUser = !!memory.user_memory?.trim()
  const hasCompany = !!memory.company_memory?.trim()

  const handleDelete = async (target: 'USER_MEMORY' | 'COMPANY_MEMORY') => {
    const ok = await onDelete(target)
    if (ok) onToast(`${target === 'USER_MEMORY' ? 'User' : 'Company'} memory cleared`, 'success')
    else onToast('Failed to clear memory', 'error')
  }

  return (
    <aside className="flex w-72 flex-col border-l border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Memory & Insights
          </h2>
          <button
            onClick={onRefresh}
            className="rounded-lg px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/30"
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            Summarizing...
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-700/50">
              <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                {insights || '• User: No entries yet\n• Company: No entries yet'}
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setExpanded(expanded === 'user' ? null : 'user')}
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  User Memory {hasUser && `(${memory.user_memory.split('\n').filter(Boolean).length})`}
                </button>
                {hasUser && (
                  <button
                    onClick={() => handleDelete('USER_MEMORY')}
                    className="text-xs text-red-500 hover:text-red-600 dark:text-red-400"
                  >
                    Clear
                  </button>
                )}
              </div>
              {expanded === 'user' && (
                <pre className="max-h-40 overflow-y-auto rounded-lg bg-gray-100 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                  {memory.user_memory || '(empty)'}
                </pre>
              )}

              <div className="flex items-center justify-between">
                <button
                  onClick={() => setExpanded(expanded === 'company' ? null : 'company')}
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Company Memory {hasCompany && `(${memory.company_memory.split('\n').filter(Boolean).length})`}
                </button>
                {hasCompany && (
                  <button
                    onClick={() => handleDelete('COMPANY_MEMORY')}
                    className="text-xs text-red-500 hover:text-red-600 dark:text-red-400"
                  >
                    Clear
                  </button>
                )}
              </div>
              {expanded === 'company' && (
                <pre className="max-h-40 overflow-y-auto rounded-lg bg-gray-100 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                  {memory.company_memory || '(empty)'}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
