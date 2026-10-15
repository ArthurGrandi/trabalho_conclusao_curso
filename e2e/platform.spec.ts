import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const textualPdf = '/tmp/tcc-ui-test.pdf';
const scannedPdf = '/tmp/tcc-ui-scanned.pdf';
const jobsCsv = '/tmp/tcc-ui-jobs.csv';
const annotatedSample = '/tmp/tcc-ui-annotated.xlsx';

test.beforeAll(() => {
  const python = existsSync(resolve('.venv/bin/python')) ? resolve('.venv/bin/python') : 'python3';
  execFileSync(python, ['-c', `
import csv
import fitz
document = fitz.open()
page = document.new_page()
page.insert_textbox(fitz.Rect(50, 50, 550, 750), '''PROJETO PEDAGOGICO DO CURSO DE SISTEMAS DE INFORMACAO
Disciplina: Programacao de Computadores
Periodo: 1
Carga horaria: 80
Ementa: Logica de programacao, algoritmos, estruturas de dados e desenvolvimento em Python. Testes automatizados, Git e integracao de APIs REST.
Objetivos: Desenvolver programas em Python, aplicar algoritmos e documentar projetos de software.
Bibliografia: Introducao a computacao. Referencia complementar Docker.
Disciplina: Banco de Dados
Periodo: 2
Carga horaria: 60
Ementa: Modelagem relacional, SQL, PostgreSQL e transacoes. Desenvolvimento de consultas e normalizacao.
Objetivos: Projetar bancos de dados relacionais e construir consultas SQL.
Bibliografia: Material de fundamentos de banco de dados.''', fontsize=11)
document.save('${textualPdf}')
document.close()
document = fitz.open()
page = document.new_page()
page.draw_rect(fitz.Rect(50, 50, 500, 700), color=(0.3, 0.5, 0.4), fill=(0.9, 0.9, 0.9))
document.save('${scannedPdf}')
document.close()
with open('${jobsCsv}', 'w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['title', 'description', 'company', 'city', 'date', 'url'])
    writer.writeheader()
    writer.writerow({'title':'Desenvolvedor Python', 'description':'Desenvolvimento em Python e SQL. Controle de versao Git, PostgreSQL e APIs REST.', 'company':'Empresa teste A', 'city':'Itajai, SC', 'date':'2026-10-01', 'url':'https://example.test/vaga-a'})
    writer.writerow({'title':'Analista de Dados', 'description':'Analise de dados em Python, SQL e PostgreSQL. Dashboards e modelagem relacional.', 'company':'Empresa teste B', 'city':'Itajai, SC', 'date':'2026-10-02', 'url':'https://example.test/vaga-b'})
`]);
});

test.beforeEach(async ({ page }) => {
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(`JavaScript: ${error.message}`));
  page.on('requestfailed', request => {
    if (!request.failure()?.errorText.includes('ERR_ABORTED')) failures.push(`Rede: ${request.url()} ${request.failure()?.errorText}`);
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Nova análise', exact: true })).toBeVisible();
  await expect(page.getByText('Não foi possível conectar ao servidor')).toHaveCount(0);
  // Keep this available to the afterEach check without changing product state.
  (page as Page & { observedFailures?: string[] }).observedFailures = failures;
});

test.afterEach(async ({ page }) => {
  const failures = (page as Page & { observedFailures?: string[] }).observedFailures || [];
  expect(failures, 'Não deve haver falhas inesperadas de JavaScript ou rede').toEqual([]);
  const overflow = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(overflow.document, 'A página deve caber na largura da tela').toBeLessThanOrEqual(overflow.viewport + 1);
});

async function navigateStep(page: Page, name: string) {
  if ((page.viewportSize()?.width || 0) < 900) await page.getByRole('button', { name: 'Abrir menu de etapas' }).click();
  await page.locator('.step-nav a').filter({ hasText: name }).click();
}

test('nova análise exige PPC e apresenta layout utilizável', async ({ page }, testInfo) => {
  await expect(page.getByRole('button', { name: 'Rodar análise' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Escolher arquivo' })).toBeVisible();
  await expect(page.locator('.step-nav a').filter({ hasText: 'Validação e exportação' })).toHaveAttribute('aria-disabled', 'true');
  await page.screenshot({ path: `/tmp/tcc-home-${testInfo.project.name}.png`, fullPage: true });
});

test('demonstração filtra áreas, preserva decisões e exporta arquivos reais', async ({ page }, testInfo) => {
  const created = page.waitForResponse(response => response.url().endsWith('/api/demo') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Explorar demonstração' }).click();
  const batch = await (await created).json();
  await expect(page.getByRole('heading', { name: 'Painel de alinhamento' })).toBeVisible();
  await expect(page.getByText('Demonstração com dados sintéticos.')).toBeVisible();
  if (testInfo.project.name === 'desktop') await page.screenshot({ path: '/tmp/tcc-dashboard-desktop.png', fullPage: true });

  const metric = page.locator('.metric-card').filter({ hasText: 'Vagas no recorte' });
  await expect(metric.locator('.metric-value')).toHaveText(String(batch.jobs.length));
  await page.getByRole('button', { name: 'Dados', exact: true }).click();
  const dataJobs = batch.jobs.filter((job: { area: string }) => job.area === 'Dados').length;
  await expect(metric.locator('.metric-value')).toHaveText(String(dataJobs));
  await expect(page.getByRole('button', { name: 'Dados', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Todas as áreas', exact: true }).click();
  await expect(metric.locator('.metric-value')).toHaveText(String(batch.jobs.length));
  await page.locator('.competency-chart .chart-line').filter({ hasText: /^Python/ }).click();
  await expect(page.getByRole('heading', { name: 'Python', exact: true, level: 1 })).toBeVisible();
  let association = page.locator('.association-card').first();
  await association.getByRole('button', { name: 'Aceitar', exact: true }).click();
  await expect(association.getByRole('button', { name: 'Aceito', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  association = page.locator('.association-card').first();
  await expect(association.getByRole('button', { name: 'Aceito', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await association.getByRole('button', { name: 'Rejeitar', exact: true }).click();
  await expect(association.getByRole('button', { name: 'Rejeitado', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  await expect(page.locator('.association-card').first().getByRole('button', { name: 'Rejeitado', exact: true })).toHaveAttribute('aria-pressed', 'true');

  await navigateStep(page, 'Validação e exportação');
  await expect(page.getByRole('heading', { name: 'Validação e exportação', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'As métricas começam com a anotação humana' })).toBeVisible();
  await expect(page.locator('.validation-metrics-table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Importar 2º anotador' })).toBeDisabled();
  await page.screenshot({ path: `/tmp/tcc-validation-${testInfo.project.name}.png`, fullPage: true });
  const xlsxEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Baixar 6 tabelas' }).click();
  const xlsx = await xlsxEvent;
  expect(xlsx.suggestedFilename()).toBe(`lote-${batch.id}-resultados.xlsx`);
  expect(await xlsx.failure()).toBeNull();
  const xlsxPath = await xlsx.path();
  expect(xlsxPath).toBeTruthy();

  await page.getByRole('radio', { name: /CSV/ }).check();
  await page.getByRole('checkbox', { name: /Lacunas prioritárias/ }).uncheck();
  const csvEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Baixar 5 tabelas' }).click();
  const csv = await csvEvent;
  expect(csv.suggestedFilename()).toBe(`lote-${batch.id}-resultados.zip`);
  expect(await csv.failure()).toBeNull();
  const csvPath = await csv.path();
  const python = existsSync(resolve('.venv/bin/python')) ? resolve('.venv/bin/python') : 'python3';
  execFileSync(python, ['-c', `
import io, sys, zipfile
from pathlib import Path
from openpyxl import load_workbook
workbook = load_workbook(io.BytesIO(Path(sys.argv[1]).read_bytes()), read_only=True)
assert set(workbook.sheetnames) == {'indicators', 'gaps', 'disciplines', 'jobs', 'associations', 'validation'}
with zipfile.ZipFile(sys.argv[2]) as archive:
    assert len(archive.namelist()) == 5
    assert 'gaps.csv' not in archive.namelist()
`, xlsxPath!, csvPath!]);

  const sampleEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Baixar amostra (XLSX)' }).click();
  const sample = await sampleEvent;
  expect(sample.suggestedFilename()).toBe(`lote-${batch.id}-amostra-cega.xlsx`);
  const samplePath = await sample.path();
  expect(samplePath).toBeTruthy();
  // Label a small test-only subset to exercise file import. No labels are shipped with the product.
  execFileSync(python, ['-c', `
from openpyxl import load_workbook
import io
from pathlib import Path
workbook = load_workbook(io.BytesIO(Path(__import__('sys').argv[1]).read_bytes()))
extraction = workbook['extraction']
headers = {cell.value:cell.column for cell in extraction[1]}
assert 'prediction' not in headers and 'predicted' not in headers
for row in range(2, min(extraction.max_row + 1, 22)):
    extraction.cell(row, headers['present'], 0)
associations = workbook['associations']
headers = {cell.value:cell.column for cell in associations[1]}
for row in range(2, min(associations.max_row + 1, 7)):
    associations.cell(row, headers['related'], 1)
workbook.save('${annotatedSample}')
`, samplePath!]);
  await page.getByLabel('Arquivo de anotação principal').setInputFiles(annotatedSample);
  await expect(page.locator('.validation-imported')).toContainText('tcc-ui-annotated.xlsx');
  await expect(page.locator('.validation-metrics-table')).not.toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Importar 2º anotador' })).toBeEnabled();
  await page.getByLabel('Arquivo do segundo anotador').setInputFiles(annotatedSample);
  await expect(page.locator('.validation-kappa')).toContainText('κ = 1,00');
});

test('PDF textual e CSV permitem revisar, salvar e processar um lote', async ({ page }) => {
  await page.locator('input[type=file][accept="application/pdf,.pdf"]').setInputFiles(textualPdf);
  await expect(page.getByText('Texto extraível', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Importar CSV', exact: true }).click();
  await page.getByLabel('Importar CSV de vagas').setInputFiles(jobsCsv);
  await expect(page.getByText('2 vagas únicas prontas para análise.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Rodar análise' })).toBeEnabled();
  const creation = page.waitForResponse(response => response.url().endsWith('/api/batches') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Rodar análise' }).click();
  const batch = await (await creation).json();
  await expect(page.getByRole('heading', { name: 'Revisão do PPC', exact: true })).toBeVisible();
  await page.getByLabel('Nome da disciplina', { exact: true }).fill('Programação e fundamentos — revisão de teste');
  await page.getByRole('button', { name: 'Salvar alterações', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Salvar alterações', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel('Nome da disciplina', { exact: true })).toHaveValue('Programação e fundamentos — revisão de teste');
  await page.getByRole('button', { name: 'Confirmar 2 disciplinas', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Processando a análise', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Abrir painel', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Abrir painel', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Painel de alinhamento', exact: true })).toBeVisible();
  await expect(page.locator('.metric-card').filter({ hasText: 'Vagas no recorte' }).locator('.metric-value')).toHaveText('2');
  const saved = await (await page.request.get(`/api/batches/${batch.id}`)).json();
  expect(saved.status).toBe('completed');
  expect(saved.demo).toBe(false);
  expect(saved.disciplines.some((discipline: { name: string }) => discipline.name === 'Programação e fundamentos — revisão de teste')).toBe(true);
  expect(saved.results.fingerprint).toMatch(/^[a-f0-9]{64}$/);
});

test('PDF sem texto é recusado com orientação e não libera execução', async ({ page }) => {
  const rejection = page.waitForResponse(response => response.url().endsWith('/api/ppc') && response.request().method() === 'POST');
  await page.locator('input[type=file][accept="application/pdf,.pdf"]').setInputFiles(scannedPdf);
  expect((await rejection).status()).toBe(422);
  await expect(page.getByText('Não foi possível ler este PDF', { exact: true })).toBeVisible();
  await expect(page.getByText(/PDF escaneado ou sem texto extraível/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Rodar análise' })).toBeDisabled();
});
