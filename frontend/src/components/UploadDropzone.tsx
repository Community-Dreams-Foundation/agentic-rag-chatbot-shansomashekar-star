import { useState, useCallback } from 'react'

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<{ ok: boolean; data?: unknown }>
  onToast: (msg: string, type: 'success' | 'error') => void
  onSuccess: () => void
}

const ACCEPTED = '.pdf,.txt,.md,.html,.htm'

export function UploadDropzone({ onUpload, onToast, onSuccess }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const handleFile = useCallback(
    async (file: File) => {
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
      if (!ACCEPTED.includes(ext)) {
        onToast('Unsupported file type. Use PDF, TXT, MD, or HTML.', 'error')
        return
      }
      setUploading(true)
      setProgress(10)
      try {
        const { ok, data } = await onUpload(file)
        setProgress(80)
        if (ok) {
          setProgress(100)
          onToast(`Added ${(data as { filename?: string })?.filename || file.name}`, 'success')
          onSuccess()
        } else {
          onToast('Upload failed', 'error')
        }
      } catch {
        onToast('Upload failed', 'error')
      } finally {
        setUploading(false)
        setProgress(0)
      }
    },
    [onUpload, onToast, onSuccess]
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const onDragLeave = useCallback(() => setIsDragging(false), [])

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
      e.target.value = ''
    },
    [handleFile]
  )

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !uploading && document.getElementById('file-input')?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-all ${
        isDragging
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
          : 'border-gray-300 hover:border-gray-400 dark:border-gray-600 dark:hover:border-gray-500'
      } ${uploading ? 'pointer-events-none opacity-80' : ''}`}
    >
      <input
        id="file-input"
        type="file"
        accept={ACCEPTED}
        onChange={onInputChange}
        className="hidden"
      />
      {uploading ? (
        <>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Indexing...</p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
            <div
              className="h-full bg-blue-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </>
      ) : (
        <>
          <div className="mx-auto mb-2 text-2xl text-gray-400">↑</div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Drop files here or click to upload
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">PDF, TXT, MD, HTML</p>
        </>
      )}
    </div>
  )
}
