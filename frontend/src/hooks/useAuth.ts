import { useState, useEffect, useCallback } from 'react'

interface User {
  id: string
  username: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

export function useAuth() {
  const [state, setState] = useState<AuthState>(() => {
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    const user = userStr ? JSON.parse(userStr) : null
    return { user, token, isAuthenticated: !!token && !!user }
  })

  const login = useCallback(async (username: string, password: string, isRegister = false) => {
    const endpoint = isRegister ? '/users/register' : '/users/login'
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Failed')
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify({ id: data.user_id, username: data.username }))
    setState({
      user: { id: data.user_id, username: data.username },
      token: data.access_token,
      isAuthenticated: true,
    })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setState({ user: null, token: null, isAuthenticated: false })
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    if (!token || !userStr) return
    try {
      const user = JSON.parse(userStr)
      setState({ user, token, isAuthenticated: true })
    } catch {
      logout()
    }
  }, [logout])

  return { ...state, login, logout }
}
