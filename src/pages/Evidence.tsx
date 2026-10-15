import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Check, Download, ExternalLink, FileText, MapPin, Search, X } from 'lucide-react';
import { date, number, percent, post, statusLabel } from '../api';
import { Alert, Badge, Card, Empty, Spinner } from '../components/ui';
import type { Association, Batch, Competency, Discipline, Evidence as EvidenceItem, Job, Notify } from '../types';
import './review-evidence.css';

type Props = { batch: Batch; competencyId: string | null; disciplineId?: string | null; onBack: () => void; onUpdate: (batch: Batch) => void; notify: Notify };
const verdictLabels = { covers: 'Cobre', partial: 'Cobre parcialmente', none: 'Não cobre' };
const normalizeSpace = (value: string) => value.replace(/\s+/g, ' ').trim();
const literal = (text: string, source: string) => Boolean(text.trim()) && normalizeSpace(source).includes(normalizeSpace(text));
const isBibliography = (section?: string) => /bibliogr|refer[eê]ncia/i.test(section || '');
const escaped = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const termPattern = (terms: string[]) => new RegExp(`(?<![\\p{L}\\p{N}_+#])(${terms.filter(Boolean).sort((a, b) => b.length - a.length).map(escaped).join('|')})(?![\\p{L}\\p{N}_+#])`, 'giu');
const sectionLabel = (section?: string) => ({ syllabus: 'Ementa', objectives: 'Objetivos', bibliography: 'Bibliografia', 'syllabus/objectives': 'Ementa e objetivos' }[section || ''] || section || 'Ementa');

function Highlight({ text, competency }: { text: string; competency: Competency }) {
  const terms = [...new Set([competency.name, ...competency.synonyms])].filter(Boolean).sort((a, b) => b.length - a.length);
  if (!terms.length) return <>{text}</>;
  const regex = termPattern(terms);
  return <>{text.split(regex).map((piece, index) => terms.some(term => term.toLocaleLowerCase('pt-BR') === piece.toLocaleLowerCase('pt-BR')) ? <mark key={index}>{piece}</mark> : piece)}</>;
}

function safeUrl(value: string) {
  try { const parsed = new URL(value); return ['https:', 'http:'].includes(parsed.protocol) ? parsed.href : null; } catch { return null; }
}

function ppcSource(item: EvidenceItem, discipline: Discipline) {
  if (isBibliography(item.section)) return discipline.bibliography;
  if (/^(?:objetivos?|objectives)$/i.test(item.section || '')) return discipline.objectives;
  return [discipline.syllabus, discipline.objectives, discipline.bibliography].filter(Boolean).join('\n');
}
const jobSource = (job: Job) => `${job.title}\n${job.description}`;
function bibliographyEvidence(competency: Competency, disciplines: Discipline[]): EvidenceItem[] {
  return disciplines.flatMap(item => {
    const match = termPattern([competency.name, ...competency.synonyms]).exec(item.bibliography);
    if (!match) return [];
    return [{ source: 'ppc' as const, source_id: item.id, section: 'bibliography', page: item.page, text: item.bibliography.slice(Math.max(0, match.index - 100), Math.min(item.bibliography.length, match.index + match[0].length + 100)).trim() }];
  });
}

export default function Evidence({ batch, competencyId, disciplineId, onBack, onUpdate, notify }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(competencyId);
  const [query, setQuery] = useState('');
  const [area, setArea] = useState('');
  const [jobArea, setJobArea] = useState('');
  const [showAllJobs, setShowAllJobs] = useState(false);
  const [method, setMethod] = useState('all');
  const [decisionBusy, setDecisionBusy] = useState<string | null>(null);
  const [alias, setAlias] = useState('');
  const [context, setContext] = useState('');
  const [curating, setCurating] = useState(false);
  const [curated, setCurated] = useState(false);
  useEffect(() => { setSelectedId(competencyId); setJobArea(''); setShowAllJobs(false); setMethod('all'); }, [competencyId, disciplineId, batch.id]);
  useEffect(() => { setAlias(''); setContext(''); setCurated(false); setShowAllJobs(false); }, [selectedId]);

  const competencies = batch.results?.competencies || [];
  const selected = competencies.find(item => item.id === selectedId);
  const discipline = disciplineId ? batch.disciplines.find(item => item.id === disciplineId) : undefined;
  const scoped = disciplineId ? competencies.filter(item => item.discipline_ids.includes(disciplineId) || item.concept_discipline_ids.includes(disciplineId) || item.evidence.some(evidence => evidence.source === 'ppc' && evidence.source_id === disciplineId) || Boolean(discipline && bibliographyEvidence(item, [discipline]).length)) : competencies;
  const competencyAreas = [...new Set(scoped.map(item => item.area))].sort();
  const filtered = scoped.filter(item => (!area || item.area === area) && [item.name, item.concept, ...item.synonyms].some(text => text.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR'))));

  const exportLink = <a className="btn secondary small" href={`/api/batches/${batch.id}/export?format=xlsx&tables=associations`} download><Download size={15}/>Exportar evidências</a>;

  if (!batch.results) return <Card><Empty title="As evidências ainda não estão disponíveis" action={<button type="button" className="btn secondary" onClick={onBack}>Voltar ao painel</button>}>Conclua o processamento deste lote para consultar os trechos e as associações.</Empty></Card>;

  if (!selected) return <div className="stack evidence-page">
    <Card title={discipline ? `Competências de ${discipline.name}` : 'Explore as evidências'} subtitle={discipline ? `${discipline.period}º período · ${discipline.hours} h · p. ${discipline.page}. As candidatas por conceito não representam menção literal.` : 'Escolha uma competência para conferir as vagas, o PPC e as associações que sustentam o resultado.'} action={exportLink}>
      <div className="field-grid evidence-filters"><label className="field"><span>Buscar competência</span><div className="search-input"><Search size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Nome, sinônimo ou conceito"/></div></label><label className="field"><span>Área</span><select value={area} onChange={event => setArea(event.target.value)}><option value="">Todas as áreas</option>{competencyAreas.map(item => <option key={item}>{item}</option>)}</select></label></div>
      <div className="competency-evidence-list">{filtered.map(item => <button key={item.id} type="button" className="list-button competency-evidence-button" onClick={() => setSelectedId(item.id)}><span><strong>{item.name}</strong><small className="muted">{item.area} · {item.type === 'concept' ? 'Conceito' : 'Tecnologia'}{disciplineId && item.concept_discipline_ids.includes(disciplineId) ? ' · candidata por conceito, sem menção literal' : disciplineId && !item.discipline_ids.includes(disciplineId) ? ' · menção somente na bibliografia' : ''}</small></span><span className="inline"><span className="small muted">{number(item.count)} vagas · {percent(item.percent)}</span><Badge kind={item.status === 'covered' ? 'success' : item.status === 'gap' ? 'warning' : 'neutral'}>{statusLabel[item.status]}</Badge><ArrowRight size={16}/></span></button>)}</div>
      {!filtered.length && <Empty title="Nenhuma competência encontrada">{disciplineId ? 'Não há menções ou candidatas por conceito para esta disciplina com os filtros selecionados.' : 'Tente outra busca ou outra área.'}</Empty>}
      <p className="small muted evidence-list-count">{filtered.length} de {scoped.length} competências</p>
    </Card>
  </div>;

  const jobById = new Map(batch.jobs.map(job => [job.id, job]));
  const disciplineById = new Map(batch.disciplines.map(item => [item.id, item]));
  const jobEvidence = selected.evidence.filter(item => item.source === 'job');
  const ppcEvidence = [...selected.evidence.filter(item => item.source === 'ppc'), ...bibliographyEvidence(selected, batch.disciplines).filter(item => !selected.evidence.some(existing => existing.source === 'ppc' && existing.source_id === item.source_id && isBibliography(existing.section)))].filter(item => !disciplineId || item.source_id === disciplineId);
  const matchedJobs = [...new Set(selected.job_ids)].map(id => jobById.get(id)).filter((job): job is Job => Boolean(job));
  const jobAreas = [...new Set(matchedJobs.map(job => job.area))].sort();
  const filteredJobs = matchedJobs.filter(job => !jobArea || job.area === jobArea);
  const visibleJobs = showAllJobs ? filteredJobs : filteredJobs.slice(0, 5);
  const ppcIds = [...new Set([...ppcEvidence.map(item => item.source_id), ...selected.discipline_ids, ...selected.concept_discipline_ids])].filter(id => !disciplineId || id === disciplineId);
  const candidateCount = new Set([...selected.discipline_ids, ...selected.concept_discipline_ids].filter(id => !disciplineId || id === disciplineId)).size;
  const associations = (batch.results.associations || []).filter(item => item.competency_id === selected.id && (!disciplineId || item.discipline_id === disciplineId));
  const associationIsVerified = (item: Association) => {
    const job = jobById.get(item.job_id), source = disciplineById.get(item.discipline_id);
    return item.verified && Boolean(job && source && literal(item.job_excerpt, jobSource(job)) && literal(item.ppc_excerpt, `${source.syllabus}\n${source.objectives}`));
  };
  const verifiedAssociations = associations.filter(associationIsVerified);
  const displayedAssociations = verifiedAssociations.filter(item => method === 'all' || item.method === method);
  const discarded = associations.filter(item => !associationIsVerified(item));
  const a2Count = associations.filter(item => item.method === 'A2').length;
  const methodStatus = batch.results.method_status as Record<string, { executed?: boolean }> | undefined;
  const a2Ran = Boolean(methodStatus?.A2?.executed || (batch.results.associations || []).some(item => item.method === 'A2'));

  async function decide(association: Association, decision: 'accepted' | 'rejected') {
    setDecisionBusy(association.id);
    try { onUpdate(await post<Batch>(`/batches/${batch.id}/decisions`, { association_id: association.id, decision })); notify(decision === 'accepted' ? 'Associação aceita. Sua avaliação foi salva.' : 'Associação rejeitada. Sua avaliação foi salva.', 'success'); }
    catch (error) { notify(error instanceof Error ? error.message : 'Não foi possível salvar a avaliação.', 'error'); }
    finally { setDecisionBusy(null); }
  }

  async function curate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    if (!alias.trim() && !context.trim()) { notify('Informe um sinônimo ou uma regra de contexto.', 'error'); return; }
    setCurating(true);
    try {
      await post('/dictionary', { competency_id: selected.id, ...(alias.trim() ? { alias: alias.trim() } : {}), ...(context.trim() ? { context: context.trim() } : {}) });
      setCurated(true); setAlias(''); setContext(''); notify('Curadoria salva para as próximas execuções.', 'success');
    } catch (error) { notify(error instanceof Error ? error.message : 'Não foi possível salvar a curadoria.', 'error'); }
    finally { setCurating(false); }
  }

  function renderPpcEvidence(item: EvidenceItem, index: number, source: Discipline) {
    const bibliography = isBibliography(item.section) || (!literal(item.text, `${source.syllabus}\n${source.objectives}`) && literal(item.text, source.bibliography));
    const verified = literal(item.text, ppcSource(item, source));
    if (!verified) return <Alert key={index} kind="warning">Um trecho desta disciplina não foi localizado no texto de origem e foi omitido da evidência literal.</Alert>;
    return <div className={bibliography ? 'bibliography-band evidence-excerpt' : 'evidence-excerpt'} key={index}><div className="inline small muted"><FileText size={13}/>{bibliography ? 'Bibliografia · não conta' : sectionLabel(item.section)}<span className="mono">p. {item.page || source.page || '—'}</span></div><blockquote><Highlight text={item.text} competency={selected!}/></blockquote><span className="source-verified"><Check size={12}/>Conferido no texto do PPC</span></div>;
  }

  return <div className="stack evidence-page">
    <div className="evidence-toolbar"><button type="button" className="btn ghost small" onClick={() => { setSelectedId(null); setJobArea(''); setMethod('all'); }}><ArrowLeft size={15}/>{discipline ? 'Ver competências da disciplina' : 'Ver todas as competências'}</button><div className="inline"><Badge>{selected.type === 'concept' ? 'Conceito' : 'Tecnologia'}</Badge><Badge>{selected.area}</Badge><Badge kind={selected.status === 'gap' ? 'warning' : 'success'}>{statusLabel[selected.status]}</Badge>{exportLink}</div></div>
    <div className="evidence-active-title"><h2>{selected.name}</h2>{discipline && <p className="small muted">Evidências filtradas pela disciplina {discipline.name}.</p>}</div>
    <div className="evidence-summary"><div><span>Frequência · I1</span><strong>{number(selected.count)} vagas <small>{percent(selected.percent)}</small></strong></div><div><span>Sinônimos reconhecidos</span><strong className="summary-text">{selected.synonyms.length ? selected.synonyms.join(', ') : 'Nenhum sinônimo adicional'}</strong></div><div><span>Pertence ao conceito</span><strong className="summary-text">{selected.concept || 'Não definido'}</strong></div><div><span>No PPC</span><strong>{candidateCount} <small>{candidateCount === 1 ? 'disciplina candidata' : 'disciplinas candidatas'}</small></strong></div></div>
    <div className="two-col evidence-sources">
      <Card title={`Nas vagas · ${filteredJobs.length}`} subtitle="Trechos extraídos das descrições das vagas." action={<label className="field compact-field"><span className="sr-only">Filtrar vagas por área</span><select value={jobArea} onChange={event => { setJobArea(event.target.value); setShowAllJobs(false); }}><option value="">Todas as áreas</option>{jobAreas.map(item => <option key={item}>{item}</option>)}</select></label>}>
        <div className="stack evidence-source-stack">{visibleJobs.map(job => {
          const excerpts = jobEvidence.filter(item => item.source_id === job.id);
          const url = safeUrl(job.url);
          return <article className="evidence-source-card" key={job.id}><div className="evidence-source-title"><h3>{job.title}</h3><Badge>{job.source}</Badge></div><p className="small muted">{job.company}{job.date ? ` · ${date(job.date)}` : ''}</p><p className="small muted inline"><MapPin size={13}/>{job.city || 'Local não informado'} · {job.area}</p>{excerpts.length ? excerpts.map((item, index) => literal(item.text, jobSource(job)) ? <div className="evidence-excerpt" key={index}><blockquote><Highlight text={item.text} competency={selected}/></blockquote><span className="source-verified"><Check size={12}/>Conferido no texto da vaga</span></div> : <Alert key={index} kind="warning">Um trecho não foi localizado nesta vaga e foi omitido da evidência literal.</Alert>) : <p className="small muted">Não há trecho literal armazenado para esta vaga.</p>}{url && <a className="evidence-original" href={url} target="_blank" rel="noreferrer">Abrir a vaga original <ExternalLink size={13}/></a>}</article>;
        })}</div>
        {!filteredJobs.length && <Empty title="Nenhuma vaga neste recorte">Escolha outra área ou outra competência.</Empty>}
        {filteredJobs.length > visibleJobs.length && <button type="button" className="btn secondary small evidence-show-all" onClick={() => setShowAllJobs(true)}>Ver as {filteredJobs.length} vagas <ArrowRight size={14}/></button>}
      </Card>
      <Card title={`No PPC · ${ppcIds.length} ${ppcIds.length === 1 ? 'disciplina' : 'disciplinas'}`} subtitle="Bibliografia identificada separadamente, fora da cobertura.">
        <div className="stack evidence-source-stack">{ppcIds.map(id => {
          const source = disciplineById.get(id);
          if (!source) return null;
          const excerpts = ppcEvidence.filter(item => item.source_id === id);
          const conceptOnly = !selected.discipline_ids.includes(id) && selected.concept_discipline_ids.includes(id);
          return <article className="evidence-source-card" key={id}><div className="evidence-source-title"><h3>{source.name}</h3><span className="mono small muted">p. {source.page || '—'}</span></div><p className="small muted">{source.period}º período · {source.hours} h</p>{conceptOnly && <Alert kind="info">Candidata por conceito: {selected.concept}. Sem menção literal à competência na ementa ou nos objetivos.</Alert>}{excerpts.map((item, index) => renderPpcEvidence(item, index, source))}{!excerpts.length && !conceptOnly && <p className="small muted">Nenhum trecho literal armazenado nesta disciplina.</p>}</article>;
        })}</div>
        {!ppcIds.length && <Empty title="Sem evidência curricular"><BookOpen size={18}/> Não foi identificada menção ou candidata por conceito no PPC. Isso não comprova ausência de ensino.</Empty>}
      </Card>
    </div>
    <Card title="Associações e julgamento" subtitle={`${verifiedAssociations.length} pares com trechos conferidos · ${discarded.length} descartados · ${associations.filter(item => item.decision).length} avaliações humanas`} action={<label className="field compact-field"><span className="sr-only">Método da associação</span><select value={method} onChange={event => setMethod(event.target.value)}><option value="all">Todos os métodos</option><option value="A1">A1 · associação lexical</option><option value="A2">A2 · julgamento do LLM</option></select></label>}>
      {!a2Ran && <Alert kind="info" title="A2 não executado neste lote">O julgamento semântico por LLM não foi realizado. As associações A1 abaixo são resultados lexicais; elas não são julgamentos de um modelo.</Alert>}
      {a2Ran && !a2Count && <Alert kind="info">O LLM foi acionado no lote, mas não há julgamento A2 registrado para esta competência.</Alert>}
      <div className="stack evidence-associations">{displayedAssociations.map(association => {
        const job = jobById.get(association.job_id), source = disciplineById.get(association.discipline_id);
        return <article className="association-card" key={association.id}><div className="association-heading"><div><span className="association-method">{association.method === 'A1' ? 'A1 · ASSOCIAÇÃO LEXICAL' : 'A2 · JULGAMENTO DO LLM'}</span><h3>{job?.title || association.job_id} <span className="muted">×</span> {source?.name || association.discipline_id}</h3></div><Badge kind={association.verdict === 'covers' ? 'success' : association.verdict === 'none' ? 'warning' : 'neutral'}>{association.verdict === 'covers' ? 'Cobre' : verdictLabels[association.verdict]}</Badge></div><p className="association-reason">{association.reason}</p><div className="field-grid association-excerpts"><div><span className="small muted">Trecho da vaga</span><blockquote><Highlight text={association.job_excerpt} competency={selected}/></blockquote><span className="source-verified"><Check size={12}/>Conferido no texto da vaga</span></div><div><span className="small muted">Trecho do PPC · <span className="mono">p. {association.page || source?.page || '—'}</span></span><blockquote><Highlight text={association.ppc_excerpt} competency={selected}/></blockquote><span className="source-verified"><Check size={12}/>Conferido no texto do PPC</span></div></div><div className="association-decision"><span className="small muted">Sua avaliação</span><div className="inline"><button type="button" className={`btn small ${association.decision === 'accepted' ? 'primary' : 'secondary'}`} disabled={decisionBusy !== null} aria-pressed={association.decision === 'accepted'} onClick={() => void decide(association, 'accepted')}>{decisionBusy === association.id ? <Spinner label="Salvando…"/> : <><Check size={14}/>{association.decision === 'accepted' ? 'Aceito' : 'Aceitar'}</>}</button><button type="button" className={`btn small ${association.decision === 'rejected' ? 'reject-selected' : 'secondary'}`} disabled={decisionBusy !== null} aria-pressed={association.decision === 'rejected'} onClick={() => void decide(association, 'rejected')}><X size={14}/>{association.decision === 'rejected' ? 'Rejeitado' : 'Rejeitar'}</button></div></div></article>;
      })}</div>
      {!displayedAssociations.length && <Empty title="Nenhuma associação neste filtro">{method === 'A2' && !a2Ran ? 'O método A2 não foi executado neste lote.' : 'Não há pares com trechos conferidos para esta competência e este método.'}</Empty>}
      {discarded.map(item => <details className="discarded-association" key={item.id}><summary><strong>Descartado · {item.method}</strong> — O trecho citado não foi conferido no texto de origem. Este par não sustenta a cobertura.</summary><div><p className="small muted">Resposta registrada para auditoria, sem validação de literalidade.</p><p>{item.reason}</p><p><strong>Vaga:</strong> {item.job_excerpt}</p><p><strong>PPC:</strong> {item.ppc_excerpt}</p></div></details>)}
    </Card>
    <Card title="Curadoria do dicionário" subtitle="As mudanças valem a partir da próxima execução. O lote atual não é recalculado automaticamente.">
      {curated && <Alert kind="success">Regra salva para os próximos lotes.</Alert>}
      <form onSubmit={event => void curate(event)} className="curation-form"><div className="field-grid"><label className="field"><span>Adicionar um sinônimo para {selected.name}</span><input value={alias} onChange={event => setAlias(event.target.value)} placeholder="Digite uma forma equivalente do termo" maxLength={120}/><small className="muted">Use somente uma equivalência que você tenha conferido.</small></label><label className="field"><span>Palavras vizinhas para a regra de contexto</span><input value={context} onChange={event => setContext(event.target.value)} placeholder="Separe as palavras por vírgula" maxLength={500}/><small className="muted">Para termos ambíguos, defina o contexto que permite reconhecer a competência.</small></label></div><button type="submit" className="btn secondary" disabled={curating || (!alias.trim() && !context.trim())}>{curating ? <Spinner label="Salvando regra…"/> : <><Check size={15}/>Salvar para a próxima execução</>}</button></form>
    </Card>
  </div>;
}
