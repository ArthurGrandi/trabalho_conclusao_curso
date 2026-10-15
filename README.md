# Alinhamento · Currículo–Mercado de TI

Plataforma de pesquisa para comparar as competências demandadas em vagas de TI com as ementas e os objetivos de um PPC. Implementa o fluxo dos dois PDFs de UI/UX fornecidos: **Nova análise → Revisão do PPC → Processamento → Painel → Evidências → Validação e exportação**.

A interface segue a identidade dos anexos: Newsreader e IBM Plex, verde sóbrio, cinco etapas, indicadores rastreáveis e layout responsivo. As fontes são servidas localmente.

## GitHub Codespaces

1. No GitHub, clique em **Code → Codespaces** e abra ou crie um Codespace na branch `main`.
2. Aguarde o editor terminar de abrir. No menu do editor, escolha **Terminal → New Terminal / Novo Terminal**. É no painel inferior que você digita os comandos; o README é apenas a documentação.
3. No terminal da pasta do projeto, execute:

   ```bash
   npm start
   ```

4. Aguarde a instalação e a compilação, se for o primeiro uso. Quando aparecer **Uvicorn running ... :8000**, o servidor está iniciado. Mantenha esse terminal aberto.
5. Na aba **Ports / Portas**, encontre a porta **8000** e clique no ícone de globo **Open in Browser / Abrir no navegador**. Caso a porta não apareça, use **Forward a Port / Encaminhar uma porta** e informe `8000`. Mantenha a visibilidade **Private**.

**A porta 8000 abre a plataforma completa, com frontend e API.** Você não precisa iniciar outro terminal nem abrir a porta 5173 para usar a aplicação neste modo. O endereço para acessar o Codespace é fornecido pela aba Portas; o `localhost` do seu computador é outro ambiente.

Se seu Codespace já estava aberto antes da última atualização, interrompa o comando anterior com **Ctrl+C** no respectivo terminal e atualize primeiro:

```bash
git pull --ff-only origin main
npm start
```

O projeto inclui uma configuração de Codespaces com Python 3.12 e Node.js 22, preparação das dependências e encaminhamento das portas. Para aplicar essa configuração em um Codespace antigo, use **Codespaces: Rebuild Container** na paleta de comandos do editor. A criação/reconstrução do contêiner não foi executada neste workspace; os comandos de instalação, execução e acesso HTTP foram testados aqui.

Se a instalação antiga ficou em `pandas-2.2.3.tar.gz` ou `Preparing metadata`, interrompa com **Ctrl+C**, atualize com `git pull --ff-only origin main` e execute `npm start` novamente. O instalador seleciona explicitamente Python 3.12; se necessário, prepara esse interpretador com `uv` em um diretório local. Ambientes `.venv` com outra versão são preservados em `.cache/venv-backups` antes da recriação. Instalações incompletas são detectadas e retomadas. Pandas e NumPy usam pacotes binários, evitando uma compilação inesperada.

## Executar no seu computador

Requisitos: Node.js 22.12+ (testado com 24), Python 3.12 com `venv` e `uv` ou `pip`. Use Linux/macOS ou WSL2 no Windows. Na pasta do projeto, execute `npm start`. O script prepara dependências ausentes, compila a interface quando necessário e inicia tudo na porta 8000. `PORT` altera essa porta. Os dados ficam em `.tcc-data` dentro do projeto; não é necessário exportar um caminho específico.

## Desenvolver com recarregamento automático

```bash
bash scripts/dev.sh
```

Esse modo usa **5173 para o frontend** e **8000 para a API**. Abra a porta **5173** no navegador; o Vite encaminha `/api` ao backend. No Codespaces, o endereço encaminhado é permitido sem desabilitar a validação dos demais hosts. Encerre o modo `npm start` antes de iniciar este modo, para liberar a porta 8000. Dependências Python ficam em `.venv`; JavaScript usa `package-lock.json`.

## Experimentar o fluxo

**Explorar demonstração** cria um lote com **30 vagas e 12 disciplinas sintéticas**, sempre identificado como demonstração. Os indicadores são calculados sobre esse conjunto; os números dos PDFs não são apresentados como resultados científicos.

Para analisar dados próprios:

1. Envie um PPC textual, até 20 MB e 500 páginas. PDFs protegidos, escaneados ou sem texto suficiente são recusados; não há OCR.
2. Importe vagas de CSV/XLSX ou selecione coleta via JobSpy. Um [modelo de CSV](public/modelo-vagas.csv) pode ser baixado na interface.
3. Revise nome, período, carga horária, ementa, objetivos e bibliografia. É possível separar/juntar disciplinas, mover trechos para a bibliografia e desfazer correções.
4. Salve a revisão. Para avaliação cega, baixe a amostra antes de consultar as predições. Confirme e acompanhe o processamento.
5. Filtre o painel por área, consulte os trechos originais e aceite ou rejeite associações. Importe anotações humanas para calcular métricas e exporte resultados em XLSX ou ZIP com CSVs.

A segmentação reconhece cabeçalhos como `Disciplina: Nome`, `Componente curricular: Nome`, `Ementa`, `Objetivos`, `Bibliografia`, `Período` e `Carga horária`. Layouts diferentes ficam em trechos por página com alerta. A segmentação é assistida e precisa de conferência humana, sobretudo em tabelas.

## Dados e métodos

- **M1:** subconjunto base; **M2:** dicionário próprio ampliado de 73 tecnologias e conceitos, com sinônimos e contexto.
- **A1:** associação lexical por competência ou conceito, com trecho literal. Encontrar uma palavra não comprova equivalência pedagógica.
- **M3/A2:** extração e julgamento reais por provedor LLM compatível com a API de chat completions. São opcionais e ficam indisponíveis sem credenciais.
- A bibliografia é preservada como evidência e excluída da cobertura. Regras distinguem Java de JavaScript e tratam termos ambíguos e negação.
- A curadoria vale para próximos lotes. Não recalcula silenciosamente os anteriores. Decisões humanas também não alteram os indicadores automáticos.
- I2 e I4 aparecem juntos. As [fórmulas e limitações](docs/methodology.md) estão documentadas: os anexos não forneciam as definições matemáticas completas nem o dicionário original.

Áreas: Programação, Análise, Dados, Suporte, Infraestrutura e Outra. A classificação usa regras sobre o título e a descrição. Clustering era opcional nos anexos e não foi incluído.

## Coleta e LLM

O setup inclui `python-jobspy`. A coleta usa os termos e o recorte definidos, roda durante a revisão, limita tentativas e registra coleta parcial ou falha sem inventar vagas. Disponibilidade, quantidade e bloqueios dependem da plataforma externa. A importação CSV funciona independentemente da coleta.

Na importação, as vagas devem estar previamente recortadas: município e raio são metadados, sem geocodificação automática do CSV. Para JobSpy, o raio em km é convertido para milhas inteiras, conforme a API da biblioteca; o recorte geográfico final depende da fonte.

Para habilitar M3/A2, configure no ambiente do processo do servidor:

| Variável | Uso |
| --- | --- |
| `TCC_LLM_API_KEY` | Chave do provedor; também aceita `OPENAI_API_KEY` existente |
| `TCC_LLM_BASE_URL` | Base HTTPS, padrão `https://api.openai.com/v1` |
| `TCC_LLM_MODEL` | Modelo, padrão `gpt-4o-mini` |
| `TCC_DATA_DIR` | Opcional: diretório SQLite, padrão `.tcc-data` dentro do projeto |

`.env.example` é uma referência; os scripts não carregam `.env` automaticamente. Não envie chaves pelo chat nem as adicione ao Git. Defina `TCC_DATA_DIR` somente se quiser guardar os dados em outro diretório gravável.

A integração usa temperatura 0, cache por hash, limite de chamadas e conferência das citações. Trechos inexistentes são descartados. Falha remota, limite ou ausência de chave aparecem como método não executado ou execução parcial. Dados de vagas e PPC são enviados ao provedor somente quando os métodos LLM são selecionados e configurados.

As integrações foram testadas com respostas simuladas; a coleta externa e as chamadas a um provedor real não foram verificadas neste ambiente. Nenhuma credencial foi necessária para o fluxo PDF + CSV + M2/A1.

## Validação científica

Não há precisão, revocação, F1 ou kappa pré-preenchidos. As métricas usam apenas rótulos humanos importados. A amostra é determinística, independente das predições, com até 60 vagas, no máximo 12 por área, todas as disciplinas e até 100 pares.

O XLSX contém `extraction`, `associations` e `guide`. Preencha `present` e `related` com 0 ou 1 sem alterar identificadores. Células vazias não são negativos. Um segundo arquivo permite calcular kappa nos itens compartilhados; distribuições que não permitem definir o kappa são indicadas.

Mantenha as amostras de desenvolvimento e teste separadas e anote sem consultar as predições. Uma assinatura de entrada identifica o lote, mas não prova que duas execuções produziram os mesmos resultados.

## Persistência

Lotes, configurações, trechos, decisões e anotações ficam em SQLite, fora das fontes e do Git. Os PDFs originais não são armazenados. Cada análise cria um lote novo.

Processos não sobrevivem ao encerramento do servidor. Uma análise interrompida é marcada no próximo início; coletas e chamadas LLM não são retomadas automaticamente. Este é um MVP de pesquisa para execução local, conforme os anexos, sem autenticação e gestão de usuários.

## Verificar

```bash
.venv/bin/python -m unittest discover -s server/tests -v
npm run build
```

Com API e frontend em execução, os testes de navegador usam Chromium instalado no sistema:

```bash
npm run test:e2e
```

Os testes cobrem extração, negação, contexto, bibliografia, indicadores, citações LLM, orçamento/cache, importações, persistência, anotações e exportações. Playwright exercita o fluxo em desktop e em 390 px; consulte o executável em `playwright.config.ts`.

## Estrutura

```text
src/                  Interface React + TypeScript
server/app.py         API e execução em segundo plano
server/engine.py      Extração, associação e indicadores
server/dictionary.py  Dicionário por lote
server/llm.py         LLM opcional, cache e conferência de citações
server/reporting.py   Anotações humanas e CSV/XLSX
server/storage.py     SQLite
server/uploads.py     PDF e planilhas
server/tests/         Testes Python
e2e/                  Testes da interface
scripts/              Instalação e execução
docs/methodology.md   Decisões metodológicas
```
