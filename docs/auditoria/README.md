# Auditoria técnica e documentação para o TCC

**Data:** 10/11/2026, America/Sao_Paulo. **Versão auditada:** `8300112985bbc873116182feaa4dd3c772677841`, então correspondente ao checkout e à `main` do repositório `ArthurGrandi/trabalho_conclusao_curso`. Os links de código e números de linha descrevem essa versão; alterações futuras exigem revisão da documentação.

O sistema implementa o fluxo de análise de alinhamento textual entre PPC e vagas com React, FastAPI e processamento Python. Possui métodos lexicais, integração opcional com LLM, indicadores descritivos, avaliação humana e persistência selecionável. A estrutura Supabase foi confirmada por leitura, mas estava **sem registros**. Há evidências históricas de testes de software e relato do autor sobre uso com um PPC real; não foi encontrado um conjunto de resultados científicos reais auditáveis nesta inspeção.

## Roteiro de leitura

| Documento | Conteúdo | Utilização sugerida |
| --- | --- | --- |
| [Arquitetura e fluxos](arquitetura-e-fluxos.md) | Componentes, responsabilidades, Mermaid, entradas e sequência de processamento | Capítulo 4: arquitetura e implementação |
| [Métodos e indicadores](metodos-e-indicadores.md) | M1/M2/M3/A1/A2, lexical × NER × LLM, fórmulas e avaliação implementadas | Capítulo 4: procedimentos e definições operacionais |
| [Persistência Supabase](persistencia-supabase.md) | Modelo de dados, transporte real, importação SQLite e fotografia remota somente leitura | Capítulo 4: armazenamento e limites operacionais |
| [Estado e evidências](estado-e-evidencias.md) | Matriz implementado/testado/relatado/pendente e rastreabilidade das afirmações | Delimitação do que pode ser afirmado nos capítulos 4 e 5 |
| [Plano de experimentos](plano-de-experimentos.md) | Hipóteses, corpus, parâmetros, cegamento, métricas e tabelas sem resultados | Definição prospectiva do capítulo 5 |

## Correspondência com a solicitação do orientador

| Item solicitado | Onde está documentado |
| --- | --- |
| Arquitetura real React + FastAPI + Python e persistência | Arquitetura e fluxos; Persistência Supabase |
| Coleta, PPC, extração, associação, indicadores e validação | Arquitetura e fluxos; Métodos e indicadores |
| Explicação dos métodos com base nas funções | Métodos e indicadores, com referências ao código |
| Diferença entre lexical, NER e LLM | Métodos e indicadores |
| Implementado, executado com dados reais e pendente | Estado e evidências |
| Diagrama Mermaid | Arquitetura e fluxos |
| Experimentos com entradas, parâmetros, saídas e métricas | Plano de experimentos |
| Verificação Supabase sem alterar dados | Persistência Supabase, observações e consultas reproduzíveis |

## Sugestão de organização do capítulo 4

1. Objetivo do artefato e unidade de análise: lote de PPC revisado, vagas e configuração congelada.
2. Arquitetura e comunicação: interface React, API FastAPI, módulos de processamento e persistência; inserir o diagrama Mermaid.
3. Aquisição e preparação: PPC textual, revisão humana, coleta/importação, deduplicação e classificação por área.
4. Métodos de extração e associação: vocabulário, regras, LLM opcional e rastreabilidade das evidências.
5. Indicadores e avaliação: fórmulas operacionais I1–I8, amostra, rótulos humanos e suporte comum.
6. Persistência, exportação e limitações: documentos JSON, Supabase/SQLite, tarefas locais, disponibilidade e escopo de uso.

### Texto-base de apresentação do artefato

> Foi implementada uma aplicação web de apoio à análise do alinhamento textual entre competências mencionadas em vagas de tecnologia da informação e conteúdos declarados em projetos pedagógicos de curso. A interface React organiza a submissão de fontes, a revisão do PPC, o acompanhamento da execução e a consulta às evidências. Uma API FastAPI coordena módulos Python de segmentação, reconhecimento lexical, associação, integração opcional com modelos de linguagem e cálculo de indicadores. A unidade persistida é um lote que reúne entradas estruturadas, configuração, resultados e registros de avaliação. O armazenamento pode utilizar SQLite local ou documentos JSONB em um esquema privado do Supabase, acessado pelo servidor por meio da Management API.

> Os resultados representam presença textual e candidatas de associação entre documentos. Não constituem medidas diretas de aprendizagem, profundidade curricular, empregabilidade ou qualidade global do curso. Os métodos lexicais M1 e M2 compartilham o mecanismo de reconhecimento e diferem na abrangência do vocabulário. M3 utiliza um LLM para extração restrita ao inventário de competências, enquanto A2 julga candidatas da etapa lexical. O desempenho empírico desses procedimentos depende de comparação com referências humanas independentes em um corpus delimitado.

Esses parágrafos sintetizam a implementação, não resultados experimentais. As fórmulas e o inventário são escolhas operacionais deste MVP; não devem ser atribuídos a um instrumento validado externo sem referência e demonstração correspondentes. Para fundamentação teórica, acrescentar literatura acadêmica verificada sobre extração de informação, reconhecimento de entidades, avaliação de classificação e concordância entre anotadores. Referências ao código fornecem rastreabilidade da implementação, não substituem essa fundamentação.

## Sugestão de organização do capítulo 5

1. Perguntas de pesquisa e hipóteses, sem pressupor superioridade do LLM.
2. Corpus e procedência: PPC, vagas, recortes, versões e critérios de seleção.
3. Protocolo: desenvolvimento/teste, anotação cega, métodos, parâmetros e suporte comparável.
4. Métricas: matriz de confusão, precisão, revocação, F1, abrangência e concordância.
5. Resultados e análise de erros: preencher somente depois da execução; separar resultados por fonte e tarefa.
6. Discussão de I1–I8, ameaças à validade, custo operacional e limitações.

Enquanto os experimentos estiverem pendentes, redigir o procedimento no futuro ou como proposta. Não preencher tabelas com as metas exibidas na aplicação, dados demonstrativos ou contagens de testes automatizados. O [plano de experimentos](plano-de-experimentos.md) contém modelos em branco e explicita análises que ainda não são automatizadas.

## Escopo e procedimento desta auditoria

A inspeção abrangeu arquivos de frontend/backend, scripts, dependências declaradas, testes, migração SQL e documentação existente. Foram consultados metadados e contagens remotas em modo de leitura, além da leitura de prontidão pelo adaptador. Logs históricos locais foram examinados como evidência técnica limitada. Relatos do autor foram identificados como tal.

As alterações desta tarefa se limitam a Markdown. Não foram criadas funcionalidades, alterados parâmetros de análise, migrados dados, executados novos experimentos ou chamadas LLM. O servidor não foi iniciado, pois sua inicialização pode importar SQLite. Os testes que criam lotes também não foram reexecutados. A revisão documental verifica referências, coerência com o código e separação entre fatos observados e propostas.

Esta pasta complementa [methodology.md](../methodology.md), [review-evidence.md](../review-evidence.md) e [supabase.md](../supabase.md), concentrando o material de apoio à redação acadêmica e o estado observado na data acima.
