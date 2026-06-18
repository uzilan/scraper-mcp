import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/ui/',
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
      '/documents': 'http://localhost:8000',
      '/swagger-ui': 'http://localhost:8000',
      '/proxy': 'http://localhost:8000',
    },
  },
})
