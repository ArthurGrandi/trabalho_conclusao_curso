import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const webPort = Number(process.env.TCC_WEB_PORT || '5173');
const codespaceHost = process.env.CODESPACE_NAME
  ? `${process.env.CODESPACE_NAME}-${webPort}.${process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN || 'app.github.dev'}`
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    port: webPort,
    strictPort: true,
    allowedHosts: codespaceHost ? [codespaceHost] : [],
    hmr: codespaceHost ? { host: codespaceHost, protocol: 'wss', clientPort: 443 } : undefined,
    proxy: { '/api': `http://127.0.0.1:${process.env.TCC_API_PORT || '8000'}` },
  },
});
