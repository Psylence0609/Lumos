import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const EXPECTED_CODES = ['ECONNRESET', 'ECONNREFUSED', 'EPIPE']

/** Suppress expected proxy errors (client/backend closed connection) so they don't spam the terminal. */
function suppressExpectedProxyErrors(proxy: { emit: (event: string, ...args: unknown[]) => boolean; on: (event: string, fn: (err: NodeJS.ErrnoException) => void) => void }) {
  const originalEmit = proxy.emit.bind(proxy)
  proxy.emit = function (event: string, err?: unknown, ...args: unknown[]) {
    if (event === 'error' && err && typeof err === 'object' && EXPECTED_CODES.includes((err as NodeJS.ErrnoException).code)) {
      return true
    }
    return originalEmit(event, err, ...args)
  }
  proxy.on('error', (err: NodeJS.ErrnoException) => {
    if (EXPECTED_CODES.includes(err?.code)) return
    console.error('[proxy]', err?.message ?? err)
  })
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    include: ['animejs'],
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        secure: false,
        configure: suppressExpectedProxyErrors,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        secure: false,
        configure: suppressExpectedProxyErrors,
      },
    },
  },
})
