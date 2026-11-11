# Estado da implementação e evidências de execução

Auditoria em **10/11/2026 (America/Sao_Paulo)**, código `8300112985bbc873116182feaa4dd3c772677841`. O checkout e a `main` remota apontavam para esse commit. A tarefa realizou inspeção estática e consultas de leitura; não executou novamente o pipeline nem os testes que criam dados.

## Critério de evidência

**Implementado** significa que há um caminho funcional identificável no código. **Testado tecnicamente** significa que existe teste e/ou registro de execução identificável; isso não equivale à avaliação científica. **Uso real relatado** indica informação fornecida pelo autor sem corpus e registro de execução suficientes para auditoria independente. **Validado empiricamente** exigiria corpus real com procedência, protocolo, referências humanas e resultados rastreáveis. Esse último nível não foi estabelecido nesta auditoria.

## Matriz de situação

| Etapa | Implementação encontrada | Evidência disponível de execução | Pendência para o TCC |
| --- | --- | --- | --- |
| Interface e API | React/TypeScript, FastAPI, validação de entrada, navegação e exportação | Testes E2E históricos com cenários sintéticos; relato de uso pelo autor | Avaliação de usabilidade com participantes não localizada |
| Upload/segmentação PPC | PDF textual com PyMuPDF, regras de cabeçalho, revisão humana | Testes com PDF gerado; autor relatou teste com PPC do IFC e enviou captura | Arquivar documento real, hash, versão e revisão; medir qualidade da segmentação |
| Importação CSV/XLSX | Parsing, normalização e deduplicação | Cenários automatizados e dados de teste | Corpus real recortado e procedência verificáveis |
| Coleta JobSpy | Integração externa, busca por termos, tentativas e coleta parcial | Testes de coleta com biblioteca simulada; captura menciona coleta parcial | Log de coleta real, fonte, datas, critérios, anúncios brutos e deduplicados |
| Classificação por área | Heurísticas por título e descrição | Testes locais de regras | Avaliação manual da classificação; não é clustering treinado |
| M1 e M2 | Reconhecimento lexical com vocabulários de abrangência diferente | Testes unitários e fluxo sintético | Medir precisão, revocação e F1 em dados reais anotados |
| M3 | Extração LLM restrita ao vocabulário, JSON validado, evidência literal | Testes com respostas simuladas; sem corpus de respostas reais disponível | Execução controlada por fonte, modelo, prompt, suporte e orçamento |
| A1 | Associação lexical/conceitual com evidência | Testes de regras e demonstração | Avaliação dos pares com padrão de referência humano |
| A2 | Julgamento LLM de candidatas lexicais | Respostas simuladas nos testes; execução real não comprovada | Avaliar suporte comum e viés das candidatas, registrar falhas e exclusões |
| I1–I8 e visualizações | Fórmulas operacionais implementadas | Cálculo em corpus sintético; captura mostra lote concluído | Revisar interpretação com orientador e obter resultados do corpus real |
| Validação humana | XLSX cego, importação primária/secundária, métricas e kappa | Testes com rótulos de teste | Anotações independentes reais; protocolo e eventual adjudicação |
| Persistência Supabase | Adaptador Management API, schema JSONB privado, views e recibos | Estrutura e leitura confirmadas agora; zero registros na consulta | Confirmar uso pelo ambiente do autor e preservar o corpus/execuções |
| Importação SQLite | Backup, manifesto e recibos idempotentes | Testes históricos; código e testes de importação | Importação do histórico real do autor não demonstrada no banco atual |

As referências às funções e limitações de cada método estão em [métodos e indicadores](metodos-e-indicadores.md), e o fluxo está em [arquitetura](arquitetura-e-fluxos.md).

## O que se pode dizer sobre dados reais

Na conversa que originou esta documentação, o autor informou ter utilizado um PPC do IFC. Uma captura fornecida por ele mostra um lote concluído com o arquivo `PPC_Matriz-2023-do-BSI-1.pdf`, recorte Itajaí/SC, raio de 40 km e indicação de **496 vagas · coleta parcial**, na tela de validação aguardando anotação. Essa é evidência contextual de uso relatado e de um estado exibido na interface; a captura não está versionada neste repositório.

Não estavam disponíveis nesta auditoria o lote correspondente, o corpus de anúncios, a configuração integral, os logs de coleta, respostas LLM ou anotações humanas. Portanto, não se confirmou independentemente a origem das 496 vagas, quais métodos foram concluídos, a qualidade dos resultados ou a execução de M3/A2. Também não se conclui que esses dados foram perdidos: podem permanecer em outro ambiente local/Codespace, que não foi acessado.

No projeto Supabase consultado havia **zero lotes, zero edições de dicionário, zero recibos e zero linhas nas seis views**. O SQLite configurado neste executor não existia. Entre os arquivos de dados versionados foi localizado `public/modelo-vagas.csv`, um modelo de entrada, não um corpus científico acompanhado de procedência. O cenário `server/demo.py` contém 30 vagas e 12 disciplinas sintéticas e não representa uma pesquisa real do mercado.

## Registros históricos de testes

Foram encontrados e lidos logs locais da preparação anterior da integração. Eles não foram gerados novamente nesta auditoria e não constituem benchmarks científicos. As datas de modificação abaixo correspondem a **05/11/2026, aproximadamente 21h43–21h54 de São Paulo** (`06/11/2026 00h43–00h54 UTC`).

| Log local histórico | Resultado registrado | Alcance |
| --- | --- | --- |
| `/tmp/tcc-supabase-all-tests-release.log` | `Ran 118 tests ... OK` | Suíte backend; inclui verificações de armazenamento e lógica, sem desempenho empírico real |
| `/tmp/tcc-supabase-e2e-final.log` | `14 passed (2.2m)` | Navegador desktop e viewport móvel, com cenários/arquivos sintéticos |
| `/tmp/tcc-supabase-host-tests.log` | 3 testes aprovados | Configuração de host/proxy do Vite para Codespaces |

Checksums SHA-256 dos logs consultados, para distinguir esses artefatos de uma execução posterior:

```text
all-tests-release: 2282ed4435374985c07e8903261c649c3a96b9211a9f7f8d705e7521db466dac
e2e-final:         bd0ae009adf93a71c01293a6a38148c97e451b012a1191e4386b096a21029ab1
host-tests:        80e868940de2dcee9e271d561eab596e604da5b53d9fffc18509cb8f6e2672d1
```

Esses caminhos `/tmp` não fazem parte do Git e podem desaparecer. As contagens acima transcrevem o registro observado, não são uma certificação permanente do commit nem substituem um relatório arquivado de execução. Os testes versionados podem ser examinados em [server/tests](../../server/tests), [e2e](../../e2e) e [scripts/tests](../../scripts/tests).

## Achados técnicos relevantes para os capítulos 4 e 5

1. **Não foi identificado NER treinado.** M1/M2 usam regras e dicionário; M3 usa LLM. Não descrever as regras como treinamento de um reconhecedor de entidades.
2. **A2 é uma etapa posterior à geração lexical de candidatas.** Sua avaliação não mede descoberta de todos os vínculos possíveis. M3 não fornece diretamente as candidatas A2 no código atual.
3. **Cobertura curricular é textual.** Ocorrência em ementa/objetivos não mede aprendizagem, profundidade ou empregabilidade; bibliografia não estabelece cobertura.
4. **Suporte comum é necessário, mas não elimina viés de seleção.** Falhas/limites LLM restringem documentos/pares avaliados. Registrar exclusões e suporte junto das métricas.
5. **Amostra e anotação não são experimento concluído.** A exportação cega deve anteceder a consulta às predições; alvos exibidos na interface são critérios, não resultados.
6. **Persistência compartilhada não torna processamento distribuído.** Tarefas, limites e cache LLM dependem do processo/diretório local; encerrar o servidor interrompe trabalho.
7. **Rastreabilidade é parcial.** O fingerprint de entrada não contém toda a versão do software, provedor/modelo, dependências e respostas. Os arquivos originais de upload devem ser arquivados externamente ao lote.
8. **O MVP não fornece autenticação multiusuário.** Privilégios privados do banco não autenticam o usuário da API FastAPI.

Esses pontos descrevem o sistema auditado. Nenhum deles foi corrigido ou ampliado nesta tarefa de documentação.

## Pendências experimentais, sem resultados presumidos

- Definir corpus, procedência, recorte temporal/espacial, critérios de inclusão e deduplicação; arquivar originais e versões revisadas.
- Separar desenvolvimento do dicionário e teste final; congelar vocabulário, parâmetros e commit antes do teste.
- Definir protocolo de presença e associação, treinar anotadores em desenvolvimento e coletar referências independentes.
- Executar os contrastes M1/M2/M3 e A1/A2 no suporte comparável, registrar falhas, chamadas e uso de cache.
- Reportar TP/FP/FN/TN, precisão/revocação/F1, suporte, concordância e análise de erros; intervalos de confiança/estratificação exigem análise adicional, não estão automatizados no MVP.
- Interpretar I1–I8 com especialistas; descrever limites e evitar extrapolar um recorte de vagas para todo o mercado.

O procedimento detalhado e os campos a preencher constam no [plano de experimentos](plano-de-experimentos.md).
