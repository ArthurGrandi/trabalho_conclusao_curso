import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

async function createReviewBatch(request: APIRequestContext) {
  const response = await request.post('/api/batches', { data: {
    config: { course: 'Curso de teste da amostra', city: 'Itajaí, SC', radius: 40, platform: 'indeed', target: 2, terms: ['Python'], tags: '', threshold: 5, llm_limit: 100, methods: ['M2', 'A1'], source: 'csv' },
    ppc: { filename: 'ppc-teste-amostra.pdf', size: 100, pages: 1, disciplines: [{ id: 'disciplina-amostra', name: 'Algoritmos', period: 1, hours: 80, page: 1, syllabus: 'Programação em Python e algoritmos. Listas, funções e dicionários.', objectives: 'Desenvolver programas em Python.', bibliography: 'Material de referência para programação.' }] },
    jobs: [{ id: 'vaga-amostra', title: 'Desenvolvedor Python', description: 'Desenvolvimento de aplicações em Python e SQL.', company: 'Empresa de teste', city: 'Itajaí, SC', date: '2026-10-01', url: '', source: 'CSV', area: 'Desenvolvimento' }],
  } });
  expect(response.status()).toBe(201);
  return response.json();
}

test('amostra cega salva a revisão, avisa após edição e é preservada ao confirmar', async ({ page, request }) => {
  const batch = await createReviewBatch(request);
  const operations: string[] = [];
  page.on('request', sent => {
    if (sent.url().endsWith(`/api/batches/${batch.id}/disciplines`)) operations.push('save');
    if (sent.url().endsWith(`/api/batches/${batch.id}/sample`)) operations.push('sample');
    if (sent.url().endsWith(`/api/batches/${batch.id}/confirm`)) operations.push('confirm');
  });
  await page.goto(`/#/lotes/${batch.id}/review`);
  await expect(page.getByRole('heading', { name: 'Revisão do PPC', exact: true })).toBeVisible();
  await page.getByLabel('Nome da disciplina', { exact: true }).fill('Algoritmos e Python');
  const firstDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Baixar amostra cega', exact: true }).click();
  const first = await firstDownload;
  expect(first.suggestedFilename()).toBe(`lote-${batch.id}-amostra-cega.xlsx`);
  expect(await first.failure()).toBeNull();
  expect(operations).toEqual(['save', 'sample']);
  const saved = await (await request.get(`/api/batches/${batch.id}`)).json();
  expect(saved.status).toBe('review');
  expect(saved.results).toBeNull();
  expect(saved.disciplines[0].name).toBe('Algoritmos e Python');

  const path = await first.path();
  expect(path).toBeTruthy();
  const python = existsSync(resolve('.venv/bin/python')) ? resolve('.venv/bin/python') : 'python3';
  execFileSync(python, ['-c', `
import io, sys
from pathlib import Path
from openpyxl import load_workbook
book = load_workbook(io.BytesIO(Path(sys.argv[1]).read_bytes()), read_only=True)
assert {'extraction', 'associations'}.issubset(book.sheetnames)
for name, label in [('extraction', 'present'), ('associations', 'related')]:
    sheet = book[name]
    rows = sheet.iter_rows(values_only=True)
    headers = list(next(rows))
    assert 'prediction' not in headers and 'predicted' not in headers
    assert all(row[headers.index(label)] is None for row in rows)
`, path!]);

  await page.getByLabel('Carga horária (h)', { exact: true }).fill('90');
  await expect(page.getByText('O PPC mudou após o download.', { exact: false })).toBeVisible();
  const renewedDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Baixar amostra cega', exact: true }).click();
  expect(await (await renewedDownload).failure()).toBeNull();
  await expect(page.getByText('O PPC mudou após o download.', { exact: false })).toHaveCount(0);
  expect(operations).toEqual(['save', 'sample', 'save', 'sample']);

  await page.getByRole('button', { name: 'Confirmar 1 disciplinas', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Processando a análise', exact: true })).toBeVisible();
  expect(operations).toEqual(['save', 'sample', 'save', 'sample', 'confirm']);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});

test('amostra cega aguarda a coleta e mostra falha de geração sem perder a revisão', async ({ page, request }) => {
  const batch = await createReviewBatch(request);
  const batchPath = `**/api/batches/${batch.id}`;
  await page.route(batchPath, route => route.fulfill({ json: { ...batch, collection: { ...batch.collection, running: true }, stages: batch.stages.map((stage: { key: string }) => stage.key === 'collection' ? { ...stage, status: 'running' } : stage) } }));
  await page.goto(`/#/lotes/${batch.id}/review`);
  await expect(page.getByRole('button', { name: 'Baixar amostra cega', exact: true })).toBeDisabled();
  await page.unroute(batchPath);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Baixar amostra cega', exact: true })).toBeEnabled();
  await page.route(`**/api/batches/${batch.id}/sample`, route => route.fulfill({ status: 409, json: { detail: 'A geração da amostra precisa ser repetida.' } }));
  await page.getByRole('button', { name: 'Baixar amostra cega', exact: true }).click();
  await expect(page.getByText('A geração da amostra precisa ser repetida.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Baixar amostra cega', exact: true })).toBeEnabled();
  await expect(page.getByLabel('Nome da disciplina', { exact: true })).toHaveValue('Algoritmos');
});
