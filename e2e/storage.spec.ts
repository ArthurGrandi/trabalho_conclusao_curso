import { expect, test } from '@playwright/test';

// Read-only smoke check: unlike the platform workflow suite, this test creates
// no batches, annotations or dictionary edits in the configured database.
test('o indicador de armazenamento corresponde à API sem expor a credencial', async ({ page }) => {
  const remoteDatabaseRequests: string[] = [];
  page.on('request', request => {
    const hostname = new URL(request.url()).hostname;
    if (hostname === 'api.supabase.com' || hostname === 'mcp.supabase.com' || hostname.endsWith('.supabase.co')) {
      remoteDatabaseRequests.push(hostname);
    }
  });
  const healthResponse = await page.request.get('/api/health');
  expect(healthResponse.status()).toBe(200);
  const health = await healthResponse.json();
  expect(['sqlite', 'supabase']).toContain(health.storage?.backend);
  expect(health.storage.cloud).toBe(health.storage.backend === 'supabase');
  const healthContainsCredential = /SUPABASE_ACCESS_TOKEN|\bsbp_[A-Za-z0-9]{20,}\b/.test(JSON.stringify(health));
  expect(healthContainsCredential, 'A resposta de saúde não deve expor a credencial do servidor').toBe(false);

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Nova análise', exact: true })).toBeVisible();
  const expectedBadge = health.storage.cloud ? 'Dados no Supabase' : 'Dados locais · SQLite';
  await expect(page.locator('.sidebar-meta')).toContainText(expectedBadge);
  const browserContainsCredential = await page.evaluate(() => {
    const credentialPattern = /SUPABASE_ACCESS_TOKEN|\bsbp_[A-Za-z0-9]{20,}\b/;
    return credentialPattern.test(document.documentElement.innerHTML)
      || credentialPattern.test(JSON.stringify(localStorage))
      || credentialPattern.test(JSON.stringify(sessionStorage));
  });
  expect(browserContainsCredential, 'O navegador não deve receber a credencial do servidor').toBe(false);
  expect(remoteDatabaseRequests, 'O acesso ao Supabase deve acontecer somente no servidor').toEqual([]);
});
