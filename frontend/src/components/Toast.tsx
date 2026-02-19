interface ToastProps {
  message: string
  type: 'success' | 'error'
}

export function Toast({ message, type }: ToastProps) {
  return (
    <div
      className={`fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl px-6 py-3 text-sm font-medium shadow-lg transition-all ${
        type === 'error'
          ? 'bg-red-600 text-white'
          : 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
      }`}
    >
      {message}
    </div>
  )
}
