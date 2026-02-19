import { useState, useEffect, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatWindow } from './components/ChatWindow'
import { MemoryPanel } from './components/MemoryPanel'
import { LoginScreen } from './components/LoginScreen'
import { useAuth } from './hooks/useAuth'
import { useDocuments } from './hooks/useDocuments'
import { useMemory } from './hooks/useMemory'
import { Toast } from './components/Toast'

function App() {
  const { user, token, login, logout, isAuthenticated } = useAuth()
  const { documents, fetchDocuments, deleteDocument, uploadFile } = useDocuments(token)
  const [memoryRefreshTrigger, setMemoryRefreshTrigger] = useState(0)
  const { memory, insights, loading, fetchMemory, fetchInsights, deleteMemory } = useMemory(token, memoryRefreshTrigger)
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('darkMode') === 'true'
  })
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    localStorage.setItem('darkMode', String(darkMode))
  }, [darkMode])

  useEffect(() => {
    if (isAuthenticated) fetchDocuments()
  }, [isAuthenticated, fetchDocuments])

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }, [])

  const refreshMemory = useCallback(() => {
    setMemoryRefreshTrigger((t) => t + 1)
  }, [])

  if (!isAuthenticated) {
    return (
      <>
        <LoginScreen onLogin={login} onToast={showToast} />
        {toast && <Toast {...toast} />}
      </>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900 transition-colors">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-800 shadow-sm">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">RAG Chat</h1>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-400">
            Ollama
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">{user?.username}</span>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="rounded-xl p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-400"
            aria-label="Toggle dark mode"
          >
            {darkMode ? '☀️' : '🌙'}
          </button>
          <button
            onClick={logout}
            className="rounded-xl px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="flex flex-1 min-h-0">
        <Sidebar
          documents={documents}
          onUpload={uploadFile}
          onDelete={deleteDocument}
          onToast={showToast}
          onFetchDocuments={fetchDocuments}
        />
        <ChatWindow
          token={token!}
          memoryEnabled={memoryEnabled}
          onMemoryToggle={setMemoryEnabled}
          onToast={showToast}
          onMemoryUpdate={refreshMemory}
        />
        <MemoryPanel
          memory={memory}
          insights={insights}
          loading={loading}
          onDelete={deleteMemory}
          onToast={showToast}
          onRefresh={() => {
            fetchMemory()
            fetchInsights()
          }}
        />
      </main>

      {toast && <Toast {...toast} />}
    </div>
  )
}

export default App
