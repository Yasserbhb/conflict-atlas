import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base so the app works both locally (served at /) and on GitHub
// Pages (served under /conflict-atlas/). Asset + data URLs use import.meta.env.BASE_URL.
// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [react()],
})
