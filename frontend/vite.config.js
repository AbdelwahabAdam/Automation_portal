import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5174,
    strictPort: true,
    // xfwd passes the visitor's address on, so the audit log records it instead of the proxy's
    // BACKEND_URL lets the backend be reached by its compose service name instead of localhost
    proxy: { '/api': { target: process.env.BACKEND_URL || 'http://localhost:8001', xfwd: true } },
  },
});
