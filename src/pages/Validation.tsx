import { useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Check, ChevronDown, Download, FileCheck2, FileSpreadsheet, Fingerprint, Info, Upload } from 'lucide-react';
import { date, number, upload } from '../api';
import { Alert, Badge, Card, Empty, Spinner } from '../components/ui';
import type { Batch, Notify } from '../types';
import './validation.css';

type Metric = { source?: string; method: string; precision: number | null; recall: number | null; f1: number | null; tp: number; fp: number; fn: number; items?: number; documents?: number; scope_note?: string };
type Annotation = { filename: string; imported_at: string; counts: { jobs: number; disciplines: number; pairs: number } };
type ValidationData = {
  primary?: Annotation | null;
  secondary?: Annotation | null;
  extraction?: Metric[];
  association?: Metric[];
  errors?: Array<{ type: string; method: string; source?: string; document_id?: string }>;
  agreement?: { kappa: number | null; items: number } | null;
  fingerprint?: string;
  sample_exported_at?: string;
  scope_note?: string;
};
type Props = { batch: Batch; onUpdate: (batch: Batch) => void; notify: Notify };
type TableKey = 'indicators' | 'gaps' | 'disciplines' | 'jobs' | 'associations' | 'validation';

const exportTables: { key: TableKey; label: string; description: string }[] = [
  { key: 'indicators', label: 'Indicadores I1 a I8', description: 'Resultados gerais e por área' },
  { key: 'gaps', label: 'Lacunas prioritárias', description: 'Competências demandadas sem cobertura' },
  { key: 'disciplines', label: 'Contribuição por disciplina', description: 'Cobertura e competências do currículo' },
  { key: 'jobs', label: 'Vagas do lote', description: 'Corpus utilizado nesta análise' },
  { key: 'associations', label: 'Associações e evidências', description: 'Trechos e julgamentos vaga–disciplina' },
  { key: 'validation', label: 'Validação e erros', description: 'Métricas calculadas com anotação humana' },
];
const methodLabels: Record<string, string> = { M1: 'Dicionário base', M2: 'Dicionário ampliado', M3: 'Modelo de linguagem', A1: 'Associação lexical', A2: 'Julgamento por modelo de linguagem' };
const errorLabels: Record<string, string> = { false_positive: 'Falso positivo', false_negative: 'Falso negativo', fp: 'Falso positivo', fn: 'Falso negativo', vocabulary: 'Vocabulário ausente', ambiguity: 'Ambiguidade', negation: 'Negação', bibliography: 'Bibliografia', hallucination: 'Alucinação do LLM' };
const metricValue = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? number(value, 2) : '—';

async function downloadFile(path: string, fallbackName: string) {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Não foi possível preparar o arquivo. Tente novamente.');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  let filename = plain || fallbackName;
  if (encoded) { try { filename = decodeURIComponent(encoded); } catch { /* Keep the fallback name. */ } }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function F1Bar({ value, target, best }: { value: number | null; target?: number; best: boolean }) {
  const valid = typeof value === 'number' && Number.isFinite(value);
  return <div className="validation-f1">
    <div className={`validation-f1-track ${valid && typeof target === 'number' && value >= target ? 'reached' : ''}`} aria-hidden="true">
      <span style={{ width: `${valid ? Math.max(0, Math.min(100, value * 100)) : 0}%` }} />
      {typeof target === 'number' && <i style={{ left: `${target * 100}%` }} />}
    </div>
    <span className={best ? 'validation-best' : ''}>{metricValue(value)}</span>
  </div>;
}

function MetricRows({ rows, target, association = false }: { rows: Metric[]; target: number; association?: boolean }) {
  const best = Math.max(...rows.map(row => typeof row.f1 === 'number' ? row.f1 : -1));
  const scopeNotes = [...new Set(rows.map(row => row.scope_note).filter((note): note is string => Boolean(note)))];
  return <><div className="table-wrap"><table className="validation-metrics-table">
    <thead><tr><th scope="col">Método</th><th scope="col">Itens avaliados</th><th scope="col">Precisão</th><th scope="col">Revocação</th><th scope="col">F1</th><th scope="col">{association ? 'Meta de precisão' : 'Meta de F1'}</th></tr></thead>
    <tbody>{rows.map(row => {
      const evaluated = association ? row.precision : row.f1;
      const hasValue = typeof evaluated === 'number' && Number.isFinite(evaluated);
      const reached = hasValue && evaluated >= target;
      return <tr key={`${row.source || 'association'}-${row.method}`}>
        <th scope="row"><span className="validation-method-code">{row.method}</span><span className="muted small">{methodLabels[row.method] || 'Método executado'}</span></th>
        <td className="validation-support"><span>{typeof row.items === 'number' ? number(row.items) : '—'}</span>{typeof row.documents === 'number' && <small className="muted">{number(row.documents)} {row.documents === 1 ? 'documento' : 'documentos'}</small>}</td>
        <td>{metricValue(row.precision)}</td><td>{metricValue(row.recall)}</td>
        <td><F1Bar value={row.f1} target={association ? undefined : target} best={typeof row.f1 === 'number' && row.f1 === best} /></td>
        <td><Badge kind={reached ? 'success' : hasValue ? 'warning' : 'neutral'}>{reached ? 'Atinge' : hasValue ? 'Abaixo' : 'Sem rótulos'}</Badge></td>
      </tr>;
    })}</tbody>
  </table></div>{scopeNotes.map(note => <p className="validation-support-note small muted" key={note}><Info size={14} /><span>{note}</span></p>)}</>;
}

export default function Validation({ batch, onUpdate, notify }: Props) {
  const validation = (batch.validation || {}) as ValidationData;
  const primary = validation.primary;
  const secondary = validation.secondary;
  const extraction = validation.extraction || [];
  const association = validation.association || [];
  const errors = validation.errors || [];
  const fingerprint = validation.fingerprint || (typeof batch.results?.fingerprint === 'string' ? batch.results.fingerprint : '');
  const [downloading, setDownloading] = useState<'sample' | 'results' | 'log' | null>(null);
  const [importing, setImporting] = useState<'primary' | 'secondary' | null>(null);
  const [sampleDownloaded, setSampleDownloaded] = useState(false);
  const [format, setFormat] = useState<'xlsx' | 'csv'>('xlsx');
  const [tables, setTables] = useState<TableKey[]>(exportTables.map(table => table.key));
  const [error, setError] = useState('');
  const primaryInput = useRef<HTMLInputElement>(null);
  const secondaryInput = useRef<HTMLInputElement>(null);
  const busy = downloading !== null;
  const hasAnnotations = Boolean(primary);
  const sampleDone = sampleDownloaded || Boolean(validation.sample_exported_at) || hasAnnotations;
  const errorTypes = Array.from(new Set(errors.map(item => item.type)));
  const errorMethods = Array.from(new Set(errors.map(item => item.method))).sort();

  async function download(kind: 'sample' | 'results' | 'log') {
    setDownloading(kind); setError('');
    try {
      const path = kind === 'sample' ? `/batches/${batch.id}/sample` : kind === 'log' ? `/batches/${batch.id}/log` : `/batches/${batch.id}/export?format=${format}&tables=${tables.join(',')}`;
      const filename = kind === 'sample' ? `amostra-lote-${batch.id}.xlsx` : kind === 'log' ? `log-lote-${batch.id}.json` : `resultados-lote-${batch.id}.${format === 'csv' ? 'zip' : 'xlsx'}`;
      await downloadFile(path, filename);
      if (kind === 'sample') setSampleDownloaded(true);
      notify(kind === 'sample' ? 'Amostra preparada. Anote o arquivo antes de importá-lo.' : kind === 'log' ? 'Log da execução baixado.' : 'Resultados exportados com sucesso.', 'success');
    } catch (cause) { const message = cause instanceof Error ? cause.message : 'Não foi possível baixar o arquivo.'; setError(message); notify(message, 'error'); }
    finally { setDownloading(null); }
  }

  async function importFile(event: ChangeEvent<HTMLInputElement>, annotator: 'primary' | 'secondary') {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setImporting(annotator); setError('');
    try {
      const updated = await upload<Batch>(`/batches/${batch.id}/annotations`, file, { annotator });
      onUpdate(updated);
      notify(annotator === 'primary' ? 'Anotação importada. Métricas atualizadas com os rótulos preenchidos.' : 'Segunda anotação importada. Concordância atualizada.', 'success');
    } catch (cause) { const message = cause instanceof Error ? cause.message : 'Não foi possível importar a anotação.'; setError(message); notify(message, 'error'); }
    finally { setImporting(null); }
  }

  function toggleTable(key: TableKey) { setTables(current => current.includes(key) ? current.filter(item => item !== key) : [...current, key]); }

  return <div className="validation-page stack">
    {error && <Alert kind="error" title="Operação não concluída">{error}</Alert>}
    <div className="validation-steps">
      <Card className="validation-step-card">
        <div className="validation-step-heading"><span className={`validation-step-number ${sampleDone ? 'done' : ''}`}>{sampleDone ? <Check size={17} /> : '1'}</span><h2>Exportar amostra</h2></div>
        <p className="muted small">Uma base comum para comparar os métodos com a avaliação humana.</p>
        <div className="validation-sample-summary"><FileSpreadsheet size={22} /><div><strong>Amostra de avaliação</strong><span className="muted small">Vagas, disciplinas e pares do lote</span></div></div>
        <p className="small muted">O arquivo não inclui previsões dos métodos. Preencha apenas os rótulos humanos nas abas de anotação.</p>
        <button className="btn secondary" disabled={busy} onClick={() => download('sample')}>{downloading === 'sample' ? <Spinner label="Preparando…" /> : <><Download size={16} />Baixar amostra (XLSX)</>}</button>
        <details className="validation-guide"><summary><Info size={15} /> Guia de anotação <ChevronDown size={14} /></summary>
          <div className="validation-guide-body"><p><strong>1.</strong> Anote sem consultar a saída dos métodos. Mantenha uma amostra de desenvolvimento separada para ajustar o dicionário.</p><p><strong>2.</strong> Na aba <code>extraction</code>, leia o documento e a competência. Preencha <code>present</code> com <strong>1</strong> se a competência está presente ou <strong>0</strong> se está ausente.</p><p><strong>3.</strong> Na aba <code>associations</code>, compare a vaga com a disciplina. Preencha <code>related</code> com <strong>1</strong> se existe cobertura ou <strong>0</strong> se não existe.</p><p>Campos vazios são ignorados. Preserve os nomes das abas, as colunas e os identificadores. Envie o mesmo arquivo a um segundo anotador para medir concordância.</p></div>
        </details>
      </Card>

      <Card className="validation-step-card">
        <div className="validation-step-heading"><span className={`validation-step-number ${primary ? 'done' : ''}`}>{primary ? <Check size={17} /> : '2'}</span><h2>Importar anotações</h2></div>
        <p className="muted small">Use o arquivo da amostra preenchido de forma independente.</p>
        {primary ? <div className="validation-imported"><FileCheck2 size={25} /><strong title={primary.filename}>{primary.filename}</strong><span className="muted small">Importado em {date(primary.imported_at, true)}</span><span className="small">{number(primary.counts.jobs)} vagas · {number(primary.counts.disciplines)} disciplinas · {number(primary.counts.pairs)} pares</span></div> : <div className="validation-upload-state"><Upload size={23} /><strong>Aguardando anotação</strong><span className="muted small">As métricas aparecem após a importação.</span></div>}
        <input ref={primaryInput} className="validation-file-input" type="file" accept=".xlsx" aria-label="Arquivo de anotação principal" onChange={event => importFile(event, 'primary')} disabled={importing !== null} />
        <button className="btn secondary" disabled={importing !== null} onClick={() => primaryInput.current?.click()}>{importing === 'primary' ? <Spinner label="Calculando métricas…" /> : <><Upload size={16} />{primary ? 'Substituir arquivo' : 'Importar anotação'}</>}</button>
        <p className="small muted validation-step-footnote">Formato XLSX · rótulos 0 e 1</p>
      </Card>

      <Card className="validation-step-card">
        <div className="validation-step-heading"><span className={`validation-step-number ${secondary ? 'done' : ''}`}>{secondary ? <Check size={17} /> : '3'}</span><h2>Concordância</h2><Badge>Opcional</Badge></div>
        <p className="muted small">Compare anotações independentes da mesma amostra.</p>
        {validation.agreement && typeof validation.agreement.kappa === 'number' ? <div className="validation-kappa"><span>κ = {number(validation.agreement.kappa, 2)}</span><p className="muted small">Kappa de Cohen em {number(validation.agreement.items)} rótulos compartilhados.</p></div> : <div className="validation-upload-state"><span className="validation-kappa-placeholder">κ —</span><span className="muted small">{secondary ? 'Não há rótulos compartilhados suficientes para calcular o kappa.' : 'Adicione uma segunda avaliação para calcular o kappa de Cohen.'}</span></div>}
        {secondary && <p className="small muted validation-secondary-filename" title={secondary.filename}>{secondary.filename}</p>}
        <input ref={secondaryInput} className="validation-file-input" type="file" accept=".xlsx" aria-label="Arquivo do segundo anotador" onChange={event => importFile(event, 'secondary')} disabled={!hasAnnotations || importing !== null} />
        <button className="btn secondary" disabled={!hasAnnotations || importing !== null} onClick={() => secondaryInput.current?.click()}>{importing === 'secondary' ? <Spinner label="Calculando concordância…" /> : <><Upload size={16} />{secondary ? 'Substituir 2º anotador' : 'Importar 2º anotador'}</>}</button>
        {!hasAnnotations && <p className="small muted validation-step-footnote">Disponível após a anotação principal.</p>}
      </Card>
    </div>

    {hasAnnotations && validation.scope_note && <Alert title="Base da comparação">{validation.scope_note}</Alert>}

    <Card title="Extração de competências" subtitle="Precisão, revocação e F1 sobre os rótulos humanos preenchidos." action={<span className="small muted validation-metric-legend">Negrito: melhor F1 em cada fonte</span>}>
      {hasAnnotations && extraction.length ? <div className="validation-source-groups">{['jobs', 'ppc'].map(source => {
        const rows = extraction.filter(row => row.source === source);
        if (!rows.length) return null;
        const target = source === 'jobs' ? 0.8 : 0.75;
        return <div className="validation-source-group" key={source}><div className="validation-source-title"><h3>{source === 'jobs' ? 'Vagas' : 'PPC'}</h3><span className="muted small">Meta F1 ≥ {number(target, 2)}</span></div><MetricRows rows={rows} target={target} /></div>;
      })}</div> : <Empty title="As métricas começam com a anotação humana">Exporte a amostra, preencha os rótulos e importe o arquivo para avaliar os métodos executados.</Empty>}
      <div className="validation-target-note"><span>Metas de referência</span><Badge>Vagas · F1 ≥ 0,80</Badge><Badge>PPC · F1 ≥ 0,75</Badge></div>
    </Card>

    <Card title="Associação vaga–disciplina" subtitle="Avaliação dos pares anotados por uma pessoa." action={<Badge>Precisão ≥ 0,70</Badge>}>
      {hasAnnotations && association.length ? <MetricRows rows={association} target={0.7} association /> : <Empty title="Aguardando pares anotados">Preencha a coluna “related” na aba de associações para comparar os métodos disponíveis.</Empty>}
    </Card>

    <div className="two-col validation-detail-grid">
      <Card title="Erros por tipo" subtitle="Diferenças encontradas entre a extração e a anotação humana.">
        {hasAnnotations && errors.length ? <div className="table-wrap"><table className="validation-errors-table"><thead><tr><th scope="col">Tipo de erro</th>{errorMethods.map(method => <th scope="col" key={method}>{method}</th>)}</tr></thead><tbody>{errorTypes.map(type => <tr key={type}><th scope="row">{errorLabels[type] || type.replaceAll('_', ' ')}</th>{errorMethods.map(method => <td key={method}>{number(errors.filter(item => item.type === type && item.method === method).length)}</td>)}</tr>)}<tr className="validation-error-total"><th scope="row">Total</th>{errorMethods.map(method => <td key={method}>{number(errors.filter(item => item.method === method).length)}</td>)}</tr></tbody></table></div> : <div className="validation-detail-empty"><Info size={21} /><p className="muted small">{hasAnnotations ? 'Nenhum erro registrado nos rótulos avaliados. As categorias aparecem quando existem divergências.' : 'Importe uma anotação para examinar as divergências de cada método.'}</p></div>}
        <p className="muted small validation-method-note">Os tipos exibidos correspondem aos erros identificados na avaliação.</p>
      </Card>
      <Card title="Reprodutibilidade" subtitle="Registro desta execução para acompanhar seus resultados.">
        <div className="validation-fingerprint-heading"><Fingerprint size={23} /><div><strong>{fingerprint ? 'Assinatura da execução disponível' : 'Registro do lote'}</strong><p className="muted small">A comparação entre duas execuções ainda não foi realizada.</p></div></div>
        <dl className="validation-repro-list"><div><dt>Lote</dt><dd>#{batch.id}</dd></div><div><dt>Criado em</dt><dd>{date(batch.created_at, true)}</dd></div><div><dt>Métodos configurados</dt><dd>{batch.config.methods.join(', ') || '—'}</dd></div></dl>
        {fingerprint && <div className="validation-fingerprint"><span className="small muted">Identificador calculado</span><code>{fingerprint}</code></div>}
        <button className="btn ghost small" disabled={busy} onClick={() => download('log')}>{downloading === 'log' ? <Spinner label="Preparando…" /> : <><Download size={14} />Baixar log da execução</>}</button>
      </Card>
    </div>

    <Card title="Baixar resultados" subtitle="Escolha as tabelas para o relatório do TCC ou a reunião do NDE." className="validation-export-card">
      <fieldset className="validation-export-options"><legend className="validation-sr-only">Tabelas para exportar</legend>{exportTables.map(table => <label className={`validation-table-option ${tables.includes(table.key) ? 'selected' : ''}`} key={table.key}><input type="checkbox" checked={tables.includes(table.key)} onChange={() => toggleTable(table.key)} /><span><strong>{table.label}</strong><span className="muted small">{table.description}</span></span></label>)}</fieldset>
      <div className="validation-export-bottom"><fieldset className="validation-format"><legend>Formato do arquivo</legend><label><input type="radio" name="validation-format" value="xlsx" checked={format === 'xlsx'} onChange={() => setFormat('xlsx')} /><span><strong>XLSX</strong><span className="muted small">Uma aba por tabela</span></span></label><label><input type="radio" name="validation-format" value="csv" checked={format === 'csv'} onChange={() => setFormat('csv')} /><span><strong>CSV</strong><span className="muted small">Um arquivo por tabela, em ZIP</span></span></label></fieldset><div className="validation-download-action"><button className="btn primary" disabled={busy || tables.length === 0} onClick={() => download('results')}>{downloading === 'results' ? <Spinner label="Preparando arquivos…" /> : <><Download size={17} />Baixar {tables.length} {tables.length === 1 ? 'tabela' : 'tabelas'}</>}</button><span className="muted small">Lote #{batch.id} · {date(batch.created_at)}</span></div></div>
      <p className="validation-privacy-note"><Info size={15} />A exportação contém os dados de vagas e do currículo utilizados na análise. Revise o conteúdo antes de compartilhá-lo.</p>
    </Card>
  </div>;
}
