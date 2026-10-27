import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const root = path.dirname(fileURLToPath(import.meta.url))

// Mijoz extension: clients/<CLIENT_NAME>/frontend_ext/index.tsx (yo'q bo'lsa, bo'sh stub)
const clientName = process.env.CLIENT_NAME ?? 'example'
const clientEntry = path.resolve(root, `../../clients/${clientName}/frontend_ext/index.tsx`)
const clientAlias = existsSync(clientEntry)
  ? clientEntry
  : path.resolve(root, 'src/extensions/empty.ts')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@core': path.resolve(root, 'src'),
      '@client': clientAlias,
    },
    // clients/ papkasidagi fayllar ham core'dagi bir xil React nusxasini ishlatishi uchun
    dedupe: ['react', 'react-dom', 'react-router-dom', 'lucide-react', '@tanstack/react-query'],
  },
  server: {
    host: true,
    port: 5173,
    fs: { allow: [path.resolve(root, '../..')] },
    // gateway (6788) orqali HMR websocket
    hmr: { clientPort: Number(process.env.GATEWAY_PORT ?? 6788) },
  },
  test: { environment: 'node' },
})
