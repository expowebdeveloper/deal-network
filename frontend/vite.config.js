import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned, not just preferred. The backend hands the browser back to
    // FRONTEND_URL after OAuth and only allows CORS from the origins in
    // backend/.env, so a dev server that silently moves to the next free port
    // breaks sign-in. Fail loudly instead — and keep both files in step.
    port: 5174,
    strictPort: true,
    open: false,
  },
})
