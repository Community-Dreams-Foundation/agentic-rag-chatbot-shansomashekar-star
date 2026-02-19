import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageBubble, type Citation } from './MessageBubble'
import { ThinkingIndicator } from './ThinkingIndicator'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  timestamp: Date
}

interface ChatWindowProps {
  token: string
  memoryEnabled: boolean
  onMemoryToggle: (v: boolean) => void
  onToast: (msg: string, type: 'success' | 'error') => void
  onMemoryUpdate?: () => void
}

export function ChatWindow({ token, memoryEnabled, onMemoryToggle, onToast, onMemoryUpdate }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamingContent])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text.trim(),
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])
      setInput('')
      setIsStreaming(true)
      setStreamingContent('')
      setStreamingCitations([])

      const isAnalysis = /analyze|weather/i.test(text)
      if (isAnalysis) {
        try {
          const res = await fetch('/analyze', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ request: text }),
          })
          const data = await res.json()
          const assistantMsg: Message = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: data.result || 'Error',
            timestamp: new Date(),
          }
          setMessages((prev) => [...prev, assistantMsg])
        } catch {
          onToast('Request failed', 'error')
        }
        setIsStreaming(false)
        return
      }

      const url = `/ask?query=${encodeURIComponent(text)}&token=${encodeURIComponent(token)}`
      const evtSource = new EventSource(url)
      let fullAnswer = ''
      let citations: Citation[] = []

      evtSource.onmessage = (e) => {
        if (e.data === '[DONE]') {
          evtSource.close()
          const assistantMsg: Message = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: fullAnswer,
            citations: citations.length ? citations : undefined,
            timestamp: new Date(),
          }
          setMessages((prev) => [...prev, assistantMsg])
          setStreamingContent('')
          setStreamingCitations([])
          setIsStreaming(false)
          return
        }
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'token') {
            fullAnswer += msg.text || ''
            setStreamingContent(fullAnswer)
          } else if (msg.type === 'cached') {
            fullAnswer = msg.answer || ''
            citations = msg.citations || []
            setStreamingContent(fullAnswer)
            setStreamingCitations(citations)
          } else if (msg.type === 'citations') {
            citations = msg.data || []
            setStreamingCitations(citations)
          } else if (msg.type === 'memory') {
            onMemoryUpdate?.()
          } else if (msg.type === 'error') {
            fullAnswer = msg.message || 'Error'
            setStreamingContent(fullAnswer)
          }
        } catch {}
      }

      evtSource.onerror = () => {
        evtSource.close()
        if (!fullAnswer) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: 'Connection error. Ensure documents are uploaded and Ollama is running.',
              timestamp: new Date(),
            },
          ])
        }
        setIsStreaming(false)
      }
    },
    [token, isStreaming, onToast, onMemoryUpdate]
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([])
    setStreamingContent('')
    onToast('Chat cleared', 'success')
  }

  return (
    <section className="flex flex-1 flex-col min-w-0 bg-gray-50 dark:bg-gray-900">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-2 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <input
              type="checkbox"
              checked={memoryEnabled}
              onChange={(e) => onMemoryToggle(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Memory
          </label>
        </div>
        <button
          onClick={clearChat}
          className="rounded-xl px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-400"
        >
          Clear chat
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4"
      >
        {messages.length === 0 && !streamingContent && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 text-4xl text-blue-500">◇</div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Document-grounded answers
            </h2>
            <p className="mt-2 max-w-md text-sm text-gray-500 dark:text-gray-400">
              Every answer is cited from your documents. No hallucinations — only what's in your files.
            </p>
            <div className="mt-6 flex flex-col gap-2 text-sm italic text-gray-400">
              <span>"Summarize the main points"</span>
              <span>"What does this say about X?"</span>
              <span>"Find information on..."</span>
            </div>
          </div>
        )}

        <div className="space-y-6">
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
              timestamp={msg.timestamp}
            />
          ))}
          {isStreaming && (
            <>
              {streamingContent ? (
                <MessageBubble
                  role="assistant"
                  content={streamingContent}
                  citations={streamingCitations}
                  timestamp={new Date()}
                />
              ) : (
                <ThinkingIndicator />
              )}
            </>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
      >
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your documents..."
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </form>
    </section>
  )
}
