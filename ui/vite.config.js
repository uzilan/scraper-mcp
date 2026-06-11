import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
  },
  server: {
    proxy: {
      '/namespaces': 'http://localhost:8000',
      '/index': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/links': 'http://localhost:8000',
    },
  },
})
