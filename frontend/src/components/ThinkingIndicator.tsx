export function ThinkingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gray-200 text-gray-600 dark:bg-gray-600 dark:text-gray-300">
        ◇
      </div>
      <div className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-600 dark:bg-gray-800">
        <span className="flex gap-1">
          <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">Thinking…</span>
      </div>
    </div>
  )
}
