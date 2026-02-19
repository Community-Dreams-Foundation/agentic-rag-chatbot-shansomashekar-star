import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/users': { target: 'http://localhost:8000' },
      '/upload': { target: 'http://localhost:8000' },
      '/ask': { target: 'http://localhost:8000' },
      '/documents': { target: 'http://localhost:8000' },
      '/memory': { target: 'http://localhost:8000' },
      '/analyze': { target: 'http://localhost:8000' },
      '/health': { target: 'http://localhost:8000' },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
