# Dados no Supabase

A plataforma pode guardar os lotes no projeto Supabase `dcfcxrvjkvppulhhxvoq`. A referência pública está em [`supabase/project.json`](../supabase/project.json); nenhuma credencial fica nesse arquivo. Quando esse armazenamento está ativo, a barra lateral mostra **Dados no Supabase**.

## Executar neste ambiente

O servidor reutiliza o `SUPABASE_ACCESS_TOKEN` já configurado nos segredos deste ambiente. Não é necessário gerar outra chave para iniciar a plataforma:

```bash
npm start
```

No modo padrão, `auto`, a presença de `SUPABASE_ACCESS_TOKEN` seleciona o Supabase. Uma seleção explícita de projeto por `SUPABASE_PROJECT_REF` também exige a configuração remota válida. Sem essas variáveis, a plataforma usa SQLite local.

## Usar no seu Codespace

Os segredos deste ambiente cloud não são enviados ao GitHub. Para usar o mesmo banco no seu Codespace:

1. Abra [GitHub → Settings → Codespaces](https://github.com/settings/codespaces) e crie um segredo de desenvolvimento chamado `SUPABASE_ACCESS_TOKEN`.
2. Salve nele o **mesmo PAT já criado no Supabase** e autorize o repositório `ArthurGrandi/trabalho_conclusao_curso`. O valor deve ser inserido apenas nesse campo protegido; não o adicione ao código, a commits ou ao chat.
3. Se o Codespace já estiver aberto, pare e inicie-o novamente para receber o segredo.
4. Na pasta do projeto, execute:

   ```bash
   git pull --ff-only origin main
   npm start
   ```

Abra a porta **8000** na aba **Ports/Portas**, mantendo-a privada. Confirme **Dados no Supabase** na barra lateral. `npm start` prepara as dependências e a interface quando necessário.

## Configuração

| Variável | Comportamento |
| --- | --- |
| `TCC_STORAGE_BACKEND=auto` | Padrão: seleciona Supabase quando há credencial ou projeto definido no ambiente; caso contrário, SQLite. |
| `TCC_STORAGE_BACKEND=supabase` | Exige Supabase configurado e acessível. |
| `TCC_STORAGE_BACKEND=sqlite` | Usa somente o SQLite local, mesmo que exista um PAT no ambiente. |
| `SUPABASE_ACCESS_TOKEN` | PAT com escopo do projeto, disponível somente no servidor. |
| `SUPABASE_PROJECT_REF` | Opcional; substitui a referência de `supabase/project.json`. |
| `TCC_DATA_DIR` | Diretório local para SQLite, backups e estado da importação; padrão `.tcc-data` na pasta do projeto. |

O PAT expira no prazo escolhido ao gerar a credencial no Supabase; por exemplo, sete dias se essa foi a duração selecionada. Quando expirar, substitua o valor no mesmo segredo `SUPABASE_ACCESS_TOKEN` e reinicie o servidor. O nome da variável e o projeto permanecem iguais. Para a operação atual, as permissões já configuradas incluem **Project Settings: Read**, **Database: Read-write**, **Migrations: Read-write** e **Advisors: Read**.

O servidor acessa um endereço HTTPS fixo da Management API do Supabase, preserva a verificação TLS e envia os dados por parâmetros vinculados às consultas. O PAT não é entregue ao navegador e não exige uma chave adicional de Data API para esse caminho de persistência.

Se o Supabase falhar, a plataforma informa o erro. Ela **não troca automaticamente para SQLite**, evitando que novos lotes sejam salvos em outro banco sem indicação. Após corrigir a conexão, **Tentar novamente** repete a verificação e retoma uma eventual importação incompleta. Enquanto a inicialização não concluir, o acesso aos dados permanece bloqueado. Para escolher a alternativa local explicitamente:

```bash
TCC_STORAGE_BACKEND=sqlite npm start
```

## Estrutura e importação dos dados existentes

A persistência usa somente o esquema privado `alinhamento`, separado de `public`. Os lotes completos e as edições do dicionário são preservados em JSONB. As visualizações relacionais permitem consultar partes desses documentos, como disciplinas e vagas, sem manter outra cópia independente dos resultados. As migrações estão em [`supabase/migrations`](../supabase/migrations).

Na inicialização, o servidor verifica se a migração necessária está instalada. Se encontrar um `platform.sqlite3` no diretório local de dados, importa os lotes e as edições do dicionário para o Supabase:

- Cria um backup consistente em `.tcc-data/backups` antes da primeira gravação remota e mantém o SQLite original.
- Registra a origem para que reiniciar a aplicação não duplique os mesmos registros. Preserve também `.tcc-data/import-state`.
- Interrompe a importação se um registro dessa origem tiver sido alterado depois de importado; não substitui silenciosamente o conteúdo remoto.
- Atribui os identificadores remotos e preserva a semente da amostra (`sample_seed`), mantendo a seleção da avaliação cega quando o número do lote mudar.

Os caminhos de backup e estado acompanham `TCC_DATA_DIR` quando ele estiver definido. Uma importação interrompida pode ser retomada com os mesmos arquivos. Os recibos já gravados identificam os registros concluídos.

Para inspecionar apenas as contagens do SQLite, sem importar nem gravar arquivos:

```bash
.venv/bin/python -m server.import_sqlite --dry-run
```

Depois da migração, use o Supabase como origem dos novos trabalhos. Escolher SQLite posteriormente não copia de volta os lotes criados na nuvem. O diretório local ainda pode conter backups e cache de processamento, portanto exporte os resultados e preserve os arquivos necessários antes de excluir um Codespace.

## Limites deste MVP

A Management API é uma API de controle com endpoint de consulta **experimental/Beta**, sujeita a latência, indisponibilidade e limites de requisições. O adaptador espaça as chamadas no processo e respeita as esperas informadas pelo provedor ao atingir o limite. Esse transporte foi escolhido para o uso individual no MVP de pesquisa, com a credencial já disponível; uma aplicação de produção multiusuário exige outra arquitetura.

O Supabase fornece persistência; esta mudança não acrescenta autenticação de usuários à aplicação. Mantenha o acesso à plataforma restrito ao seu ambiente de desenvolvimento. Processamentos em andamento continuam dependendo do servidor: fechar o Codespace interrompe a execução, ainda que os lotes já persistidos permaneçam no Supabase.

A auditoria da estrutura registra apenas o aviso informativo [RLS Enabled No Policy](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) nas três tabelas privadas. Isso é intencional: nenhum usuário anônimo ou autenticado da Data API recebe acesso. Não crie políticas públicas permissivas para ocultar esse aviso.

Como o banco é compartilhado, iniciar outra instância não marca automaticamente os lotes em processamento de outros servidores como falhos. Se uma execução foi interrompida de fato, cancele o lote na interface e crie outro; não há retomada automática da coleta ou de chamadas LLM.
