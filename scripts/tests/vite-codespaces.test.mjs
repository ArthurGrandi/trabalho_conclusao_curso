import assert from 'node:assert/strict';
import { once } from 'node:events';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { createServer } from 'vite';

const configFile = fileURLToPath(new URL('../../vite.config.ts', import.meta.url));
const root = fileURLToPath(new URL('../../', import.meta.url));

async function withDevServer(environment, run) {
  const keys = ['CODESPACE_NAME', 'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'TCC_WEB_PORT', 'TCC_API_PORT'];
  const original = Object.fromEntries(keys.map((key) => [key, process.env[key]]));
  const backend = http.createServer((request, response) => {
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ path: request.url, service: 'test-api' }));
  });
  let vite;
  try {
    backend.listen(0, '127.0.0.1');
    await once(backend, 'listening');
    for (const key of keys) delete process.env[key];
    Object.assign(process.env, environment, { TCC_API_PORT: String(backend.address().port) });
    vite = await createServer({
      root,
      configFile,
      logLevel: 'silent',
      optimizeDeps: { noDiscovery: true, include: [] },
      server: { host: '127.0.0.1', port: 0, strictPort: false, watch: null, preTransformRequests: false },
    });
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    await run(vite, (path, host) => new Promise((resolve, reject) => {
      http.get(`${origin}${path}`, { headers: { Host: host } }, (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => resolve(new Response(Buffer.concat(chunks), { status: response.statusCode })));
        response.on('error', reject);
      }).on('error', reject);
    }));
  } finally {
    await vite?.close();
    await new Promise((resolve) => backend.close(resolve));
    for (const key of keys) {
      if (original[key] === undefined) delete process.env[key];
      else process.env[key] = original[key];
    }
  }
}

test('Codespaces frontend accepts its forwarded host, serves local access, and preserves the API proxy', async () => {
  const host = 'curriculo-test-5173.app.github.dev';
  await withDevServer({ CODESPACE_NAME: 'curriculo-test' }, async (vite, request) => {
    assert.deepEqual(vite.config.server.hmr, { host, protocol: 'wss', clientPort: 443 });

    for (const allowed of [host, 'localhost', '127.0.0.1']) {
      const response = await request('/', allowed);
      assert.equal(response.status, 200, allowed);
      assert.match(await response.text(), /<div id="root"><\/div>/);
    }

    const response = await request('/api/health', host);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { path: '/api/health', service: 'test-api' });

    for (const blocked of ['unrelated.example', 'another-codespace-5173.app.github.dev', `${host}.example`]) {
      const response = await request('/', blocked);
      assert.equal(response.status, 403, blocked);
      assert.match(await response.text(), /Blocked request/);
    }
  });
});

test('Codespaces frontend uses the configured forwarding domain and frontend port', async () => {
  const host = 'curriculo-test-5180.forwarding.example';
  await withDevServer({
    CODESPACE_NAME: 'curriculo-test',
    GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN: 'forwarding.example',
    TCC_WEB_PORT: '5180',
  }, async (vite, request) => {
    assert.equal(vite.config.server.hmr.host, host);
    assert.equal((await request('/', host)).status, 200);
    assert.equal((await request('/', 'curriculo-test-5173.app.github.dev')).status, 403);
  });
});

test('local development keeps host validation enabled without Codespaces variables', async () => {
  await withDevServer({}, async (vite, request) => {
    assert.equal(vite.config.server.hmr, undefined);
    assert.equal((await request('/', 'localhost')).status, 200);
    assert.equal((await request('/', 'unrelated.example')).status, 403);
  });
});
