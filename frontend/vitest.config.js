import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()], test: { environment: 'jsdom', setupFiles: ['./src/__tests__/setup.js'], testTimeout: 30000, include: ['src/__tests__/**/*.test.jsx'] } })
