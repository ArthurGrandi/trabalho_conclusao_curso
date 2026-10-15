import { useEffect, useRef, useState } from 'react';
import { ArrowRight, BookOpen, Check, ChevronDown, Download, FileText, GitMerge, Save, Scissors, Search, Undo2 } from 'lucide-react';
import { api, number } from '../api';
import { Alert, Badge, Card, Empty, Progress, Spinner } from '../components/ui';
import type { Batch, Discipline, Notify } from '../types';
import './review-evidence.css';

type Props = { batch: Batch; onUpdate: (batch: Batch) => void; onConfirm: () => void; onProcessing: () => void; notify: Notify };
type Snapshot = { disciplines: Discipline[]; corrections: number };
type SplitDraft = { firstName: string; secondName: string; first: string; second: string };
const clone = (items: Discipline[]) => items.map(item => ({ ...item }));

export default function Review({ batch, onUpdate, onConfirm, onProcessing, notify }: Props) {
  const [disciplines, setDisciplines] = useState(() => clone(batch.disciplines));
  const [corrections, setCorrections] = useState(batch.corrections);
  const [selectedId, setSelectedId] = useState(() => (batch.disciplines.find(item => item.alert) || batch.disciplines[0])?.id || '');
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState('alerts');
  const [showAll, setShowAll] = useState(false);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [sampling, setSampling] = useState(false);
  const [sampleVersion, setSampleVersion] = useState<number | null>(null);
  const [saveError, setSaveError] = useState('');
  const [showReferences, setShowReferences] = useState(false);
  const [splitDraft, setSplitDraft] = useState<SplitDraft | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const draftRef = useRef(disciplines);
  const correctionsRef = useRef(corrections);
  const versionRef = useRef(0);
  const editedFields = useRef(new Set<string>());

  useEffect(() => {
    const items = clone(batch.disciplines);
    draftRef.current = items;
    correctionsRef.current = batch.corrections;
    setDisciplines(items);
    setCorrections(batch.corrections);
    setSelectedId((items.find(item => item.alert) || items[0])?.id || '');
    setHistory([]); setDirty(false); setSaveError(''); setSplitDraft(null);
    setSampleVersion(null);
    editedFields.current.clear(); versionRef.current = 0;
  }, [batch.id]);

  const selected = disciplines.find(item => item.id === selectedId);
  const alertCount = disciplines.filter(item => item.alert).length;
  const readOnly = batch.status !== 'review';
  const periods = new Set(disciplines.map(item => item.period)).size;
  const filtered = disciplines.filter(item => item.name.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')))
    .sort((a, b) => order === 'alerts' ? Number(Boolean(b.alert)) - Number(Boolean(a.alert)) || a.period - b.period : order === 'period' ? a.period - b.period : 0);
  const visible = showAll ? filtered : filtered.slice(0, 10);
  const collection = batch.stages.find(stage => /coleta|collect|fetch/i.test(`${stage.key} ${stage.label}`));
  const collectionProgress = batch.config.target > 0 ? Math.min(100, batch.jobs.length / batch.config.target * 100) : 0;
  const collectionRunning = (batch.collection as { running?: boolean } | undefined)?.running ?? collection?.status === 'running';
  const sampleReady = !collectionRunning && batch.jobs.length > 0 && (collection?.status === 'completed' || collection?.status === 'warning');
  const sampleStale = sampleVersion !== null && sampleVersion !== versionRef.current;

  function change(next: Discipline[], count = true, record = true) {
    if (record) setHistory(items => [...items.slice(-29), { disciplines: clone(draftRef.current), corrections: correctionsRef.current }]);
    draftRef.current = next;
    if (count) correctionsRef.current += 1;
    versionRef.current += 1;
    setDisciplines(next); setCorrections(correctionsRef.current); setDirty(true); setSaveError('');
  }

  function edit<K extends keyof Discipline>(key: K, value: Discipline[K]) {
    if (!selected || readOnly) return;
    const fieldKey = `${selected.id}:${key}`;
    const firstEdit = !editedFields.current.has(fieldKey);
    editedFields.current.add(fieldKey);
    change(draftRef.current.map(item => item.id === selected.id ? { ...item, [key]: value } : item), firstEdit, firstEdit);
  }

  async function save() {
    if (readOnly) return false;
    const current = draftRef.current;
    if (!current.length || current.some(item => !item.name.trim() || !Number.isFinite(item.hours) || item.hours < 0 || !Number.isFinite(item.period) || item.period < 1)) {
      notify('Preencha o nome, o período e uma carga horária válida de todas as disciplinas.', 'error');
      return false;
    }
    setSaving(true); setSaveError('');
    const version = versionRef.current;
    try {
      const updated = await api<Batch>(`/batches/${batch.id}/disciplines`, { method: 'PATCH', body: JSON.stringify({ disciplines: current, corrections: correctionsRef.current }) });
      onUpdate(updated);
      if (version === versionRef.current) { setDirty(false); editedFields.current.clear(); }
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Não foi possível salvar as alterações.';
      setSaveError(message); notify(message, 'error'); return false;
    } finally { setSaving(false); }
  }

  async function confirm() {
    setConfirming(true);
    if (!dirty || await save()) await onConfirm();
    setConfirming(false);
  }

  async function downloadBlindSample() {
    setSampling(true);
    try {
      if (dirty && !await save()) return;
      const response = await fetch(`/api/batches/${batch.id}/sample`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Não foi possível gerar a amostra. Confira se a coleta terminou e tente novamente.');
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error('A amostra recebida está vazia. Tente novamente.');
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `lote-${batch.id}-amostra-cega.xlsx`;
      document.body.append(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
      setSampleVersion(versionRef.current);
      notify('Amostra baixada. Faça a anotação antes de consultar as predições no painel.', 'success');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Não foi possível baixar a amostra cega.', 'error');
    } finally { setSampling(false); }
  }

  function undo() {
    const snapshot = history.at(-1);
    if (!snapshot) return;
    setHistory(items => items.slice(0, -1));
    correctionsRef.current = snapshot.corrections;
    change(clone(snapshot.disciplines), false, false);
    editedFields.current.clear(); setSplitDraft(null);
    if (!snapshot.disciplines.some(item => item.id === selectedId)) setSelectedId(snapshot.disciplines[0]?.id || '');
  }

  function beginSplit() {
    if (!selected) return;
    const text = selected.syllabus;
    let point = textRef.current?.selectionStart || 0;
    if (point <= 0 || point >= text.length) {
      const secondBlock = /(?:\n|\s)(?:ementa\s*:)/ig;
      let match: RegExpExecArray | null;
      const positions: number[] = [];
      while ((match = secondBlock.exec(text))) positions.push(match.index);
      point = positions.find(position => position > text.length * 0.15) || text.indexOf('\n', Math.floor(text.length / 2));
      if (point <= 0 || point >= text.length) point = text.indexOf(' ', Math.floor(text.length / 2));
      if (point <= 0) point = Math.floor(text.length / 2);
    }
    setSplitDraft({ firstName: selected.name, secondName: '', first: text.slice(0, point).trim(), second: text.slice(point).trim() });
  }

  function split() {
    if (!selected || !splitDraft || !splitDraft.firstName.trim() || !splitDraft.secondName.trim() || !splitDraft.first.trim() || !splitDraft.second.trim()) {
      notify('Informe os dois nomes e confira a ementa de cada disciplina.', 'error'); return;
    }
    const firstHours = Math.floor(selected.hours / 2);
    const next = draftRef.current.flatMap(item => item.id !== selected.id ? [item] : [
      { ...item, name: splitDraft.firstName.trim(), syllabus: splitDraft.first.trim(), hours: firstHours, alert: null },
      { ...item, id: `manual-${crypto.randomUUID()}`, name: splitDraft.secondName.trim(), syllabus: splitDraft.second.trim(), hours: selected.hours - firstHours, objectives: '', bibliography: '', alert: 'Disciplina separada manualmente: confira a carga horária, os objetivos e as referências.' },
    ]);
    change(next); setSplitDraft(null); notify('Disciplina separada. Confira os dados das duas disciplinas antes de salvar.', 'info');
  }

  function merge() {
    if (!selected) return;
    const index = draftRef.current.findIndex(item => item.id === selected.id);
    if (index < 1) return;
    const previous = draftRef.current[index - 1];
    const merged: Discipline = { ...previous, name: `${previous.name} / ${selected.name}`, hours: previous.hours + selected.hours, syllabus: [previous.syllabus, selected.syllabus].filter(Boolean).join('\n\n'), objectives: [previous.objectives, selected.objectives].filter(Boolean).join('\n\n'), bibliography: [previous.bibliography, selected.bibliography].filter(Boolean).join('\n\n'), alert: 'Disciplinas unidas manualmente: confira os campos e mantenha como está após revisar.' };
    change(draftRef.current.filter(item => item.id !== selected.id).map(item => item.id === previous.id ? merged : item));
    setSelectedId(previous.id); setSplitDraft(null);
  }

  function markBibliography() {
    if (!selected || !textRef.current) return;
    const { selectionStart, selectionEnd } = textRef.current;
    if (selectionStart === selectionEnd) { notify('Selecione o trecho na ementa que deve ser marcado como bibliografia.', 'info'); textRef.current.focus(); return; }
    const excerpt = selected.syllabus.slice(selectionStart, selectionEnd);
    change(draftRef.current.map(item => item.id === selected.id ? { ...item, syllabus: `${item.syllabus.slice(0, selectionStart)}${item.syllabus.slice(selectionEnd)}`.trim(), bibliography: [item.bibliography, excerpt].filter(Boolean).join('\n\n') } : item));
    setShowReferences(true);
  }

  return <div className="stack review-page">
    {readOnly && <Alert kind="info" title="A revisão deste lote foi encerrada">Os dados são exibidos somente para consulta, preservando o cálculo e as evidências. Inicie um novo lote para revisar outro PPC.</Alert>}
    <div className="review-collection">
      <div className="inline"><span className={`live-dot ${collection?.status === 'completed' ? 'done' : ''}`} /><div><strong>{collection?.status === 'completed' ? 'Coleta de vagas concluída' : collection?.status === 'failed' ? 'A coleta precisa de atenção' : 'Coleta de vagas em segundo plano'}</strong><p className="small muted">{batch.config.platform} · {number(batch.jobs.length)} de {number(batch.config.target)} vagas{collection?.detail ? ` · ${collection.detail}` : ''}</p></div></div>
      <div className="review-collection-progress"><Progress value={collectionProgress} label="Vagas coletadas em relação à meta" /><button className="btn ghost small" type="button" disabled={saving || confirming || sampling} onClick={async () => { if (!dirty || await save()) onProcessing(); }}>Ver processamento <ArrowRight size={14}/></button></div>
    </div>
    <div className="review-summary"><span><strong>{disciplines.length}</strong> disciplinas em {periods} períodos</span><span className={alertCount ? 'warning-text' : ''}><strong>{alertCount}</strong> alertas para revisar</span><span><BookOpen size={14}/>{disciplines.filter(item => item.bibliography.trim()).length} bibliografias fora da contagem</span><span><strong>{corrections}</strong> {corrections === 1 ? 'correção feita' : 'correções feitas'}</span></div>
    <div className="review-layout">
      <Card title="Disciplinas" subtitle="Selecione uma disciplina para conferir o texto." className="review-list-card">
        <label className="field"><span className="sr-only">Buscar disciplina</span><div className="search-input"><Search size={16}/><input value={query} onChange={event => { setQuery(event.target.value); setShowAll(false); }} placeholder="Buscar disciplina" /></div></label>
        <label className="field"><span className="sr-only">Ordenação das disciplinas</span><select value={order} onChange={event => setOrder(event.target.value)}><option value="alerts">Com alerta primeiro</option><option value="all">Todas · ordem do PPC</option><option value="period">Por período</option></select></label>
        <div className="discipline-list">{visible.map(item => <button type="button" key={item.id} className={`discipline-button ${selectedId === item.id ? 'selected' : ''}`} onClick={() => { setSelectedId(item.id); setSplitDraft(null); setShowReferences(false); }} aria-pressed={selectedId === item.id}><span className="discipline-period">{item.period}º</span><span className="discipline-name"><strong>{item.name}</strong>{item.alert && <span className="warning-text">⚠ {item.alert}</span>}</span><span className="small muted">{item.hours} h</span></button>)}</div>
        {!visible.length && <Empty title="Nenhuma disciplina encontrada">Tente outro nome na busca.</Empty>}
        <div className="review-list-footer"><span className="small muted">Mostrando {visible.length} de {filtered.length}</span>{filtered.length > visible.length && <button type="button" className="btn ghost small" onClick={() => setShowAll(true)}>Ver todas <ChevronDown size={14}/></button>}</div>
      </Card>
      {selected ? <Card title={selected.name} subtitle={`Disciplina · ${selected.period}º período`} action={<Badge kind={selected.alert ? 'warning' : 'success'}>{selected.alert ? 'Revisão pendente' : 'Sem alertas'}</Badge>}>
        <fieldset className="review-fields" disabled={confirming || sampling}>
          {selected.alert && <Alert kind="warning" title="Confira a segmentação"><p>{selected.alert}</p>{!readOnly && <div className="inline review-alert-actions"><button className="btn secondary small" type="button" onClick={beginSplit}><Scissors size={14}/>Separar em duas</button><button className="btn ghost small" type="button" onClick={() => change(draftRef.current.map(item => item.id === selected.id ? { ...item, alert: null } : item))}><Check size={14}/>Manter como está</button></div>}</Alert>}
          <label className="field"><span>Nome da disciplina</span><input readOnly={readOnly} value={selected.name} onChange={event => edit('name', event.target.value)} /></label>
          <div className="field-grid"><label className="field"><span>Período</span><input readOnly={readOnly} type="number" min="1" max="30" value={selected.period} onChange={event => edit('period', Number(event.target.value))}/></label><label className="field"><span>Carga horária (h)</span><input readOnly={readOnly} type="number" min="0" step="1" value={selected.hours} onChange={event => edit('hours', Number(event.target.value))}/></label></div>
          <p className="small muted inline"><FileText size={14}/>Origem no PDF <span className="mono">p. {selected.page || 'não identificada'}</span></p>
          {!readOnly && <div className="segmentation-toolbar"><button type="button" className="btn ghost small" onClick={beginSplit}><Scissors size={14}/>Separar aqui</button><button type="button" className="btn ghost small" disabled={disciplines[0]?.id === selected.id} onClick={merge}><GitMerge size={14}/>Juntar com a anterior</button><button type="button" className="btn ghost small" onClick={markBibliography}><BookOpen size={14}/>Marcar como bibliografia</button><button type="button" className="btn ghost small" disabled={!history.length} onClick={undo}><Undo2 size={14}/>Desfazer</button></div>}
          <label className="field"><span className="field-label-line">Ementa <small className="mono muted">p. {selected.page || '—'}</small></span><textarea readOnly={readOnly} ref={textRef} rows={7} value={selected.syllabus} onChange={event => edit('syllabus', event.target.value)} placeholder="Ementa não encontrada. Transcreva o conteúdo do PPC." /></label>
          {splitDraft && <div className="split-preview stack"><div><h3>Confira a separação</h3><p className="small muted">A carga horária será dividida entre os dois registros. Ajuste os dados após separar; as referências e os objetivos atuais ficam na primeira disciplina.</p></div><div className="field-grid"><div><label className="field"><span>Nome da primeira disciplina</span><input value={splitDraft.firstName} onChange={event => setSplitDraft({ ...splitDraft, firstName: event.target.value })}/></label><label className="field"><span>Primeira ementa</span><textarea rows={5} value={splitDraft.first} onChange={event => setSplitDraft({ ...splitDraft, first: event.target.value })}/></label></div><div><label className="field"><span>Nome da segunda disciplina</span><input value={splitDraft.secondName} onChange={event => setSplitDraft({ ...splitDraft, secondName: event.target.value })}/></label><label className="field"><span>Segunda ementa</span><textarea rows={5} value={splitDraft.second} onChange={event => setSplitDraft({ ...splitDraft, second: event.target.value })}/></label></div></div><div className="inline"><button type="button" className="btn primary small" onClick={split}>Confirmar separação</button><button type="button" className="btn ghost small" onClick={() => setSplitDraft(null)}>Cancelar</button></div></div>}
          <label className="field"><span>Objetivos</span><textarea readOnly={readOnly} rows={4} value={selected.objectives} onChange={event => edit('objectives', event.target.value)} placeholder="Objetivos não identificados no documento." /></label>
          <div className="bibliography-band"><div className="inline"><BookOpen size={18}/><strong>Bibliografia · fora da contagem</strong></div><p className="small muted">As referências ficam guardadas como evidência marcada e não contam como cobertura curricular.</p><button type="button" className="btn ghost small" onClick={() => setShowReferences(value => !value)}>{showReferences ? 'Ocultar referências' : 'Ver referências'} <ChevronDown size={14}/></button>{showReferences && <label className="field"><span>Referências extraídas</span><textarea readOnly={readOnly} rows={5} value={selected.bibliography} onChange={event => edit('bibliography', event.target.value)} placeholder="Nenhuma bibliografia identificada." /></label>}</div>
        </fieldset>
      </Card> : <Card><Empty title="Nenhuma disciplina disponível">Volte à análise para conferir o PPC enviado.</Empty></Card>}
    </div>
    {saveError && <Alert kind="error" title="Alterações ainda não foram salvas">{saveError} O texto permanece nesta tela para você tentar novamente.</Alert>}
    {!readOnly && <div className="review-blind-sample"><div><strong>Anotação independente</strong><p className="small muted">Baixe e anote a amostra antes de consultar as predições no painel. Se houver alterações pendentes, elas serão salvas antes do download.</p>{sampleStale ? <p className="small warning-text" role="status">O PPC mudou após o download. Baixe uma nova amostra e use somente a versão atual para anotar e importar.</p> : <p className="small muted">{sampleVersion !== null ? 'Amostra baixada para esta versão do PPC. Novas edições exigem um novo download.' : !sampleReady ? 'O download será liberado quando a coleta terminar e houver vagas neste lote.' : 'Alterar a revisão invalida uma amostra baixada anteriormente.'}</p>}</div><button type="button" className="btn secondary small" disabled={!sampleReady || saving || confirming || sampling} onClick={() => void downloadBlindSample()}>{sampling ? <Spinner label="Preparando amostra…"/> : <><Download size={15}/>Baixar amostra cega</>}</button></div>}
    <div className="review-confirm-bar"><div><strong>{readOnly ? 'Revisão disponível para consulta' : dirty ? 'Há alterações para salvar' : 'Alterações salvas neste lote'}</strong><p className="small muted">{!readOnly && alertCount ? `Revise os ${alertCount} alertas ou confirme assim mesmo.` : 'A bibliografia permanece fora do cálculo da cobertura.'}</p></div>{!readOnly && <div className="inline"><button type="button" className="btn secondary" disabled={!dirty || saving || confirming || sampling} onClick={() => void save()}>{saving ? <Spinner label="Salvando…"/> : <><Save size={16}/>Salvar alterações</>}</button><button type="button" className="btn primary" disabled={saving || confirming || sampling || !disciplines.length} onClick={() => void confirm()}>{confirming ? <Spinner label="Confirmando…"/> : <>Confirmar {disciplines.length} disciplinas <ArrowRight size={16}/></>}</button></div>}</div>
  </div>;
}
