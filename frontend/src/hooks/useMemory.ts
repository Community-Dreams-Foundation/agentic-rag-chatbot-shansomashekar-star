import { useState, useCallback, useEffect } from 'react'

export interface MemoryState {
  user_memory: string
  company_memory: string
}

export interface MemoryInsights {
  insights: string
}

export function useMemory(token: string | null, refreshTrigger?: number) {
  const [memory, setMemory] = useState<MemoryState>({ user_memory: '', company_memory: '' })
  const [insights, setInsights] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const fetchMemory = useCallback(async () => {
    if (!token) return
    const res = await fetch('/memory', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setMemory({ user_memory: data.user_memory || '', company_memory: data.company_memory || '' })
    }
  }, [token])

  const fetchInsights = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch('/memory/insights', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setInsights(data.insights || '')
      }
    } finally {
      setLoading(false)
    }
  }, [token])

  const deleteMemory = useCallback(async (target: 'USER_MEMORY' | 'COMPANY_MEMORY'): Promise<boolean> => {
    if (!token) return false
    const res = await fetch(`/memory/${target}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      await fetchMemory()
      await fetchInsights()
    }
    return res.ok
  }, [token, fetchMemory, fetchInsights])

  useEffect(() => {
    fetchMemory()
  }, [fetchMemory, refreshTrigger])

  useEffect(() => {
    fetchInsights()
  }, [fetchInsights, refreshTrigger])

  useEffect(() => {
    if (!token) return
    const id = setInterval(() => {
      fetchMemory()
      fetchInsights()
    }, 10000)
    return () => clearInterval(id)
  }, [token, fetchMemory, fetchInsights])

  return { memory, insights, loading, fetchMemory, fetchInsights, deleteMemory }
}
