# Auditoria da persistência e consulta ao Supabase

**Código de referência:** `8300112985bbc873116182feaa4dd3c772677841` (mesmo HEAD da `main` remota na consulta). **Inspeção:** 10/11/2026, aproximadamente 21h27, America/Sao_Paulo. A consulta de contagem retornou `2026-11-11 00:27:27.49071+00` em UTC. Este documento registra uma observação pontual, não monitoramento contínuo.

## Resultado verificado

A integração existe no código, o projeto remoto respondeu e o adaptador da aplicação conseguiu ler a estrutura. **O esquema da aplicação estava vazio na data da auditoria.** Isso confirma disponibilidade para leitura e instalação da estrutura; não comprova que os dados do Codespace do autor foram migrados, nem que há resultados científicos armazenados. Nenhuma gravação foi testada nesta tarefa.

| Verificação | Resultado observado | Evidência |
| --- | --- | --- |
| Projeto associado | `dcfcxrvjkvppulhhxvoq` | `get_project_url` do MCP e [project.json](../../supabase/project.json) |
| URL de projeto | `https://dcfcxrvjkvppulhhxvoq.supabase.co` | MCP; não é o endpoint usado pelo adaptador para SQL |
| Migração remota | `20261106004032`, `create_alinhamento_store` | `list_migrations`; corresponde ao nome da [migração versionada](../../supabase/migrations/20261106004032_create_alinhamento_store.sql) |
| Backend selecionado neste executor | `supabase` | `storage_options()`; credencial configurada, sem leitura ou exposição do valor |
| Leitura pelo transporte da aplicação | `ready=true`, `transport=management_api`, contagens 0/0 | `SupabaseStore.check_ready()` sem iniciar FastAPI |
| SQLite no diretório de dados configurado deste executor | Arquivo `platform.sqlite3` ausente | Verificação de existência, sem criar banco |
| Gravação remota nesta auditoria | Não executada | Apenas metadados e SELECT em modo de leitura |

Não foi feita comparação byte a byte de todos os objetos remotos com o SQL local. A correspondência verificada abrange identificação da migração, objetos, modos de segurança, privilégios consultados e contagens.

### Objetos e volume observado

| Objeto no esquema `alinhamento` | Tipo | Linhas | Segurança observada |
| --- | --- | ---: | --- |
| `batches` | Tabela de documentos de lotes | 0 | RLS habilitado; `FORCE ROW LEVEL SECURITY` desabilitado |
| `dictionary_edits` | Tabela de curadoria | 0 | RLS habilitado; FORCE desabilitado |
| `sqlite_imports` | Tabela de recibos de importação | 0 | RLS habilitado; FORCE desabilitado |
| `jobs` | View | 0 | `security_invoker=true` |
| `disciplines` | View | 0 | `security_invoker=true` |
| `associations` | View | 0 | `security_invoker=true` |
| `annotations` | View | 0 | `security_invoker=true` |
| `evidence` | View | 0 | `security_invoker=true` |
| `validation` | View | 0 | `security_invoker=true` |

A contagem de lotes também retornou zero para `demo=true`, `demo=false`, `status=completed`, presença de resultados e objetos de anotação não vazios. Contagens zero **não significam** F1 zero, ausência de uso anterior ou perda de dados. Não há itens disponíveis para calcular desempenho ou reconstruir uma execução nessa fotografia do banco.

Foram verificadas as seis funções `create_batch`, `create_dictionary_edit`, `import_batch`, `import_dictionary_edit`, `prepare_batch` e `prepare_dictionary_edit`: todas apresentaram `security_definer=false`. Nenhuma delas foi chamada pela auditoria para alterar dados.

### Privilégios

Não havia políticas em `pg_policies` para `alinhamento`. Para os papéis `anon` e `authenticated`, as consultas retornaram `false` em: USAGE do schema, SELECT e INSERT em `batches`, SELECT em `dictionary_edits` e SELECT em `sqlite_imports`.

A migração também revoga privilégios de `PUBLIC`, `anon` e `authenticated` sobre o esquema, tabelas, sequências e funções. A ausência de políticas é coerente com o acesso privilegiado somente pelo servidor. RLS sem FORCE não restringe necessariamente o proprietário nem papéis privilegiados; não se deve descrever essa configuração como proteção contra o próprio backend. A API FastAPI não implementa autenticação de usuários ou isolamento por instituição. CORS não substitui controle de acesso.

## Como a persistência realmente funciona

O navegador chama `/api` no FastAPI. O servidor escolhe um armazenamento na função [`storage_options`](../../server/persistence.py#L16):

| Configuração | Seleção |
| --- | --- |
| `TCC_STORAGE_BACKEND=sqlite` | SQLite local, mesmo com PAT presente |
| `TCC_STORAGE_BACKEND=supabase` | Exige configuração Supabase válida |
| `auto` e presença de `SUPABASE_ACCESS_TOKEN` ou `SUPABASE_PROJECT_REF` no ambiente | Supabase |
| `auto` sem essas variáveis | SQLite; a existência isolada de `supabase/project.json` não ativa o remoto |

O caminho Supabase é **HTTPS para a Management API**, com SQL parametrizado e PAT no backend:

```text
POST https://api.supabase.com/v1/projects/{project_ref}/database/query
body: query, parameters, read_only
```

Referências: [`SupabaseStore.__init__`](../../server/supabase_store.py#L68), [`_query`](../../server/supabase_store.py#L200). Não há cliente `supabase-js` no frontend, conexão PostgreSQL direta, uso de Storage para PDFs nem Supabase Auth no fluxo implementado. O código classifica esse transporte como experimental, apropriado ao MVP individual; não há ensaio de capacidade que sustente uso multiusuário intensivo.

Os lotes são documentos JSONB em `batches.body`, com identidade, revisão e timestamps relacionais. As seis views projetam elementos desses documentos. Vagas e disciplinas não são entidades independentes mantidas por um ORM; os dados canônicos permanecem no lote. O SQLite alternativo segue o mesmo modelo documental, com JSON em colunas TEXT ([`Store`](../../server/storage.py#L14)). Os bytes originais de uploads não são arquivados por esse armazenamento; preservar o PDF/CSV original é responsabilidade do protocolo de pesquisa.

### Consistência e falhas

- Criações usam UUID estável dentro das tentativas de uma operação e funções SQL idempotentes. Isso não equivale a deduplicar duas submissões HTTP independentes do usuário.
- Atualizações usam comparação de `revision` e repetição limitada em conflito ([`update`](../../server/supabase_store.py#L311)). Atualizar um lote regrava o documento JSON; não há transação única abrangendo todo o pipeline.
- Leituras possuem cache curto (padrão 0,4 s). Requisições são espaçadas em 0,65 s por projeto **dentro do mesmo processo**; múltiplos servidores não compartilham esse limitador. O código trata 429 e limites temporais de espera; isso não garante ausência de limitação externa.
- Uma falha remota gera erro explícito, sem troca automática para SQLite. A inicialização verifica a estrutura e pode importar o histórico local; falhas de inicialização bloqueiam os endpoints de dados até uma tentativa bem-sucedida ([`initialize_persistence`](../../server/app.py#L79), [`persistence_readiness`](../../server/app.py#L105)).
- Persistência compartilhada não transfere tarefas, locks ou cache LLM para a nuvem. Um processamento continua dependente do processo FastAPI que o iniciou. A inicialização remota não cancela lotes de outro servidor nem retoma automaticamente trabalhos interrompidos.

## Importação SQLite prevista no código

[`import_sqlite_snapshot`](../../server/import_sqlite.py#L146) lê uma cópia consistente, valida documentos, cria backup e manifesto local antes de escrever. Funções SQL registram origem, identificador e fingerprint. Repetir a mesma importação reconhece recibos existentes; alterações posteriores na origem são recusadas em vez de sobrescrever silenciosamente o remoto. Identificadores podem ser remapeados; `sample_seed` preserva a semente da amostra em lotes importados.

Esse processo é acionado na inicialização quando existe SQLite e `TCC_IMPORT_SQLITE` não é `off`. É uma cópia com controle de repetição, não sincronização bidirecional contínua. Arquivos locais de backup e estado da importação continuam relevantes. Os zero recibos remotos e a ausência de SQLite neste executor não permitem afirmar que houve importação do Codespace do autor.

## Procedimento de auditoria e consultas reproduzíveis

Foram usados MCP para projeto/migrações e consultas SQL protegidas por `BEGIN READ ONLY`, além de `check_ready()` do adaptador, cujas consultas usam `read_only=true`. O servidor não foi iniciado: seu startup pode importar SQLite e modificar estados. Também não foi usado o endpoint de download de amostra, que pode persistir a amostra apesar de usar GET. Não houve coleta, upload, análise, anotação, migração, INSERT, UPDATE, DELETE ou chamada LLM nesta auditoria.

Exemplos das consultas de observação, sem conteúdo textual dos documentos:

```sql
BEGIN READ ONLY;
SELECT clock_timestamp() AS observed_at_utc,
       count(*) AS batches,
       count(*) FILTER (WHERE body->>'demo'='true') AS demo_batches,
       count(*) FILTER (WHERE body->>'demo'='false') AS non_demo_batches,
       count(*) FILTER (WHERE body->>'status'='completed') AS completed_batches
FROM alinhamento.batches;
COMMIT;
```

```sql
BEGIN READ ONLY;
SELECT n.nspname, c.relname, c.relkind,
       c.relrowsecurity, c.relforcerowsecurity, c.reloptions
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='alinhamento' AND c.relkind IN ('r','v')
ORDER BY c.relkind,c.relname;
COMMIT;
```

```sql
BEGIN READ ONLY;
SELECT role_name,
       has_schema_privilege(role_name,'alinhamento','USAGE') AS schema_usage,
       has_table_privilege(role_name,'alinhamento.batches','SELECT') AS batches_select,
       has_table_privilege(role_name,'alinhamento.batches','INSERT') AS batches_insert,
       (SELECT count(*) FROM pg_policies WHERE schemaname='alinhamento') AS policies
FROM (VALUES ('anon'),('authenticated')) AS roles(role_name);
COMMIT;
```

As mesmas consultas poderão retornar outros valores no futuro. Para a configuração operacional, consulte o [guia Supabase](../supabase.md); para o alcance empírico, consulte [estado e evidências](estado-e-evidencias.md).
