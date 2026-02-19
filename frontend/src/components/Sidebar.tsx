import { UploadDropzone } from './UploadDropzone'
import type { Document } from '../hooks/useDocuments'

interface SidebarProps {
  documents: Document[]
  onUpload: (file: File) => Promise<{ ok: boolean; data?: unknown }>
  onDelete: (id: string) => Promise<boolean>
  onToast: (msg: string, type: 'success' | 'error') => void
  onFetchDocuments: () => void
}

export function Sidebar({ documents, onUpload, onDelete, onToast, onFetchDocuments }: SidebarProps) {
  const handleReindex = () => {
    onFetchDocuments()
    onToast('Documents refreshed', 'success')
  }

  return (
    <aside className="flex w-72 flex-col border-r border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Documents
          </h2>
          {documents.length > 0 && (
            <button
              onClick={handleReindex}
              className="rounded-lg px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/30"
            >
              Re-index
            </button>
          )}
        </div>

        <UploadDropzone
          onUpload={onUpload}
          onToast={onToast}
          onSuccess={onFetchDocuments}
        />

        <ul className="space-y-1">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="group flex items-center justify-between rounded-xl px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              <span
                className="truncate text-sm text-gray-700 dark:text-gray-300"
                title={doc.filename}
              >
                {doc.filename}
              </span>
              <button
                onClick={async (e) => {
                  e.stopPropagation()
                  const ok = await onDelete(doc.id)
                  if (ok) onToast('Document removed', 'success')
                  else onToast('Failed to remove', 'error')
                }}
                className="rounded p-1 text-gray-400 opacity-0 hover:bg-red-100 hover:text-red-600 group-hover:opacity-100 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                aria-label="Delete"
              >
                ×
              </button>
            </li>
          ))}
        </ul>

        {documents.length === 0 && (
          <p className="py-4 text-center text-sm text-gray-500 dark:text-gray-400">
            No documents yet
          </p>
        )}
      </div>
    </aside>
  )
}
