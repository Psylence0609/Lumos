import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://localhost:8443',
        secure: false, // accept self-signed cert
      },
      '/ws': {
        target: 'wss://localhost:8443',
        ws: true,
        secure: false,
      },
    },
  },
})
