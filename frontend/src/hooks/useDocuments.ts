import { useState, useCallback } from 'react'

export interface Document {
  id: string
  filename: string
  summary?: string
  created_at?: number
}

export function useDocuments(token: string | null) {
  const [documents, setDocuments] = useState<Document[]>([])

  const fetchDocuments = useCallback(async () => {
    if (!token) return
    const res = await fetch('/documents', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setDocuments(data)
    }
  }, [token])

  const deleteDocument = useCallback(async (id: string): Promise<boolean> => {
    if (!token) return false
    const res = await fetch(`/documents/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      setDocuments((prev) => prev.filter((d) => d.id !== id))
    }
    return res.ok
  }, [token])

  const uploadFile = useCallback(async (file: File): Promise<{ ok: boolean; data?: unknown }> => {
    if (!token) return { ok: false }
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch('/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    })
    const data = await res.json()
    if (res.ok) {
      setDocuments((prev) => [...prev, { id: data.doc_id, filename: data.filename }])
    }
    return { ok: res.ok, data } as { ok: boolean; data?: unknown }
  }, [token])

  return { documents, fetchDocuments, deleteDocument, uploadFile }
}
