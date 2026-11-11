# Plano de experimentos para o capítulo 5

**Estado: a executar.** Este documento propõe um protocolo de avaliação; não relata experimento realizado, coleta real, execução de LLM ou desempenho observado. A elaboração se limita à leitura do código, da metodologia e dos testes no commit de referência `8300112`. Nenhuma precisão, revocação, F1, concordância, custo ou duração foi preenchida. Os dados de `server/demo.py` e os números ilustrativos dos anexos não constituem evidência empírica do TCC.

O objetivo é avaliar separadamente extração de competências, associação vaga–disciplina e descrição do alinhamento textual do PPC. As definições operacionais estão em [metodologia](../methodology.md); este plano não redefine os indicadores nem transforma presença textual em medida de aprendizagem.

## 1. Perguntas e hipóteses a verificar

| ID | Pergunta ou hipótese prospectiva | Comparação compatível | O que permitiria concluir |
| --- | --- | --- | --- |
| P1 | O vocabulário ampliado recupera mais competências explícitas que o subconjunto de base, e com que alteração de precisão? | M1 × M2, mesmos documentos e universo humano anotado | Efeito do escopo vocabular desta implementação; ambos usam o mesmo reconhecedor lexical |
| P2 | A extração por LLM melhora precisão, revocação ou F1 frente aos métodos lexicais no mesmo suporte? | M1 × M2 × M3, separadamente em vagas e disciplinas | Desempenho de extração no vocabulário e nos documentos efetivamente avaliados; não extração aberta de qualquer competência |
| P3 | O julgamento A2 rejeita candidatas A1 inadequadas e mantém as relações humanas pertinentes? | A1 × A2 no conjunto comum de pares anotados efetivamente julgados | Qualidade da filtragem de candidatas lexicais; não capacidade de descobrir relações fora dessas candidatas |
| P4 | Quais erros persistem em negação, ambiguidade, ausência vocabular, conceito genérico e bibliografia? | FP/FN de cada tarefa, com inspeção de evidências e rótulos humanos | Limitações observadas e hipóteses para um ciclo posterior de desenvolvimento |
| P5 | As saídas são recuperadas de forma consistente com entradas congeladas e qual o esforço operacional? | Repetições lexicais; repetição LLM com cache identificada à parte | Estabilidade no contexto registrado, abrangência, falhas, chamadas e duração; não garantia de determinismo do provedor |
| P6 | Que demandas e lacunas textuais aparecem no corpus real delimitado? | I1–I8 do método lexical ativo, após a validação | Descrição auxiliar para discussão com o NDE, limitada ao corpus; não nota do curso ou estimativa de todo o mercado |

As hipóteses não pressupõem superioridade de um método. As metas já presentes na aplicação — F1 de 0,80 em vagas, F1 de 0,75 no PPC e precisão de 0,70 na associação — são critérios de referência, não resultados, testes de significância ou demonstrações de validade.

## 2. Entradas que precisam ser congeladas

Antes da avaliação final, registrar em um manifesto do estudo, sem credenciais:

1. **PPC institucional real:** instituição, curso, versão, data, procedência autorizada, hash do PDF e seção curricular utilizada. Conferir o documento original e finalizar disciplinas, páginas, ementas, objetivos e bibliografias. Registrar revisões manuais e hash das fontes estruturadas; bibliografia e nome da disciplina não estabelecem cobertura.
2. **Corpus real de vagas:** plataforma/origem, consultas, janela de publicação e data de obtenção, localidade/raio pretendido, critérios de inclusão, remoto/híbrido, campos ausentes e total antes/depois da deduplicação. Preservar o arquivo importado e as fontes estruturadas finais, seus hashes e a identidade de cada anúncio. Não usar o número de anúncios como número de contratações.
3. **Recorte espacial e deduplicação:** documentar os filtros aplicados fora da aplicação quando a entrada for CSV; a importação não geocodifica nem aplica raio. A deduplicação por URL, identificador externo e título + empresa + localidade pode unir atualizações de um anúncio. Congelar o corpus já deduplicado; não repetir coleta para cada método.
4. **Vocabulário e configuração:** salvar o dicionário efetivo, aliases, contextos, relações e marcação `base`; congelar a curadoria antes do teste. Os 34 itens de M1 e 73 de M2 descritos na versão inicial devem ser conferidos no snapshot utilizado. Registrar todos os filtros e os métodos solicitados.
5. **Anotação e execução:** guardar guia datado, partição desenvolvimento/teste, amostra exportada e seu identificador, arquivos originais de cada anotador, IDs de lote, commit, dependências, configuração pública do provedor/modelo, versão de prompt e estado do cache. Registrar o momento em que os anotadores tiveram acesso às predições.

O caminho principal proposto utiliza **CSV real já congelado**, com `tags=""`, para comparar os métodos sobre o mesmo corpus e evitar diferenças entre coletas. Esse plano não executa nem exige nova coleta. Caso um estudo futuro use JobSpy, a obtenção do corpus é uma etapa anterior, com registro de falhas, coleta parcial e limitações da plataforma; ela não deve ser misturada com a comparação de algoritmos.

## 3. Desenvolvimento, teste e anotação cega

### 3.1 Separação antes dos ajustes

A aplicação não implementa gerenciador de partições desenvolvimento/teste. A separação precisa ser definida e arquivada pelo pesquisador **antes** da curadoria e da leitura das predições finais. Agrupar anúncios duplicados, republicados e versões do mesmo texto para impedir que versões próximas caiam em partições distintas.

Usar vagas e, quando houver ajuste guiado por conteúdo curricular, disciplinas de desenvolvimento distintas das unidades de teste. Não ajustar aliases, contextos, segmentação, prompts ou critérios após consultar o padrão-ouro final. Para um único PPC com poucas disciplinas, declarar a restrição e reservar disciplinas para teste antes da curadoria; não alegar avaliação curricular independente se todas já foram usadas no ajuste. Todas as disciplinas do lote serão exportadas, portanto as unidades de desenvolvimento precisam ser identificadas no manifesto e permanecer **sem rótulo de avaliação final** na importação do teste. Outra opção é preparar previamente um corpus de teste curricular separado; essa preparação é externa ao particionamento da aplicação.

Não há percentual de divisão obrigatório no software. Definir tamanho e composição antes de conhecer os erros, conforme disponibilidade e esforço humano; registrar a decisão em vez de escolher o corte pelo melhor F1. Preservar a classificação de áreas e a lista de IDs usada na partição.

### 3.2 Ordem operacional proposta

1. Criar o lote de teste com as fontes reais congeladas e o dicionário já fixado. Finalizar a coleta/importação e a revisão do PPC sem abrir saídas de extração ou associação.
2. Na revisão, baixar **amostra cega** antes de confirmar o processamento. O endpoint `GET /api/batches/{id}/sample` admite o estado `review` depois da coleta e com ao menos uma vaga. Guardar a planilha exatamente exportada e o manifesto dos IDs.
3. Se qualquer disciplina precisar de alteração após o download, descartar a versão anterior da amostra, salvar a revisão e exportar novamente **antes da anotação**. A API invalida a amostra armazenada quando a revisão muda.
4. Entregar aos anotadores somente fontes, vocabulário, guia e planilha sem predições. Anotação cega depende do procedimento humano: exportar uma planilha sem predições depois de o anotador ter visto o painel não restaura o cegamento.
5. Finalizar e arquivar a anotação primária e a segunda anotação independente, quando prevista. Somente então executar os métodos sobre as entradas congeladas e importar os arquivos em seus papéis `primary` e `secondary`.
6. Examinar desempenho e erros após o fechamento dos rótulos. Uma correção sugerida pelos erros finais pertence a novo ciclo/lote; não atualizar o dicionário e reutilizar os mesmos rótulos como novo teste independente.

Os cliques de aceitar/rejeitar em Evidências não substituem uma anotação cega: o avaliador vê a saída do método. Devem ser discutidos como revisão operacional pós-predição e mantidos separados do padrão-ouro.

### 3.3 Amostra determinística e seus limites

`server/reporting.py::make_sample` usa `random.Random("curriculo-mercado:<semente>")`, com o ID do lote como semente padrão. Ordena áreas e IDs, sorteia até 12 vagas por área e **depois limita o agregado a 60 vagas**. Há seis áreas canônicas: Análise, Dados, Infraestrutura, Outra, Programação e Suporte. Se o agregado exceder 60, os últimos estratos na ordenação podem ficar reduzidos ou ausentes; a seleção não garante equilíbrio entre as seis áreas. Registrar a composição efetiva, sem repetir o rótulo ilustrativo de “12 por área” como garantia.

Todas as disciplinas do lote entram na extração. Para cada documento selecionado há uma linha por competência do dicionário fornecido ao amostrador. Com `C` competências e `D` disciplinas, o esforço máximo de extração é `(min(60, vagas selecionáveis) + D) × C` decisões, não somente a quantidade de documentos. Pares de associação são sorteados do produto cartesiano entre vagas selecionadas e disciplinas, até o máximo de 100, independentemente das predições. Se o produto tiver menos itens, a amostra será menor.

As linhas de extração de vagas incluem título e descrição; as do PPC incluem ementa e objetivos. É preciso corrigir referências misturadas a esses campos na revisão, pois o amostrador concatena os campos, enquanto os extratores também possuem proteção por cabeçalho de bibliografia.

O amostrador possui fallback interno para `sample_seed`, mas o fluxo público não oferece controle desse campo. Um novo ID de lote pode gerar outra amostra mesmo com o mesmo corpus. Para comparações finais, privilegiar os métodos no **mesmo lote** e preservar os IDs da amostra original. Reexportar uma amostra de outro lote não garante as mesmas unidades. A seleção é determinística para as mesmas entradas, ordenação e semente; não é uma amostra probabilística representativa do mercado.

O endpoint fornece ao amostrador o dicionário completo reconstruído com o inventário do código e as curadorias salvas em `dictionary_snapshot`, sem aplicar o filtro `tags` da análise. O campo persistido guarda as curadorias, não uma cópia autossuficiente do inventário. Por isso o protocolo preserva o commit e o vocabulário efetivo e fixa `tags=""`. Experimentos com tags exigem definir previamente quais unidades rotular no escopo: linhas fora dele não devem ser transformadas em falsos negativos de uma tarefa diferente.

### 3.4 Guia e concordância humana

Na extração, preencher `present=1` quando a competência estiver explicitamente declarada no texto elegível; `0` para ausência. Registrar exemplos de sinônimos, termos ambíguos, negações, competências desejáveis e referências bibliográficas no guia de desenvolvimento. Evitar inferir uma tecnologia apenas a partir do conceito pedagógico.

Na associação, preencher `related=1/0` para o **par vaga–disciplina**. Definir antes da anotação o que constitui relação curricular e como tratar cobertura parcial. A avaliação binária implementada considera positiva uma candidata `covers` **ou** `partial`; o protocolo humano deve explicitar se esse é o critério adotado. Se for exigida avaliação ordinal de três níveis ou apenas cobertura completa como positivo, a comparação correspondente exige análise adicional, não a métrica binária atual.

Preservar folhas, cabeçalhos e IDs. Células em branco ficam fora das métricas, não representam ausência. Para avaliar documentos selecionados, preferir rotular todas as competências do universo predefinido, incluindo ausências; não selecionar linhas depois de observar predições. Registrar unidades não rotuladas e os motivos.

A segunda anotação é opcional, independente e realizada antes de discussão conjunta. `validation_result` calcula acordo observado e kappa global somente sobre unidades comuns entre anotadores, combinando fontes e tarefas. Esse kappa não equivale a kappas separados por fonte. Quando o acordo esperado é 1 (ambos os anotadores atribuem a mesma classe a todas as unidades comuns), o código retorna kappa indefinido; sem unidades comuns, não há concordância calculável. Não substituir esses casos por 0 ou 1. As métricas de desempenho usam a anotação **primária**; a secundária não produz consenso nem adjudicação automática. Se houver adjudicação posterior, arquivar as duas versões independentes e descrever a análise consensual separadamente.

## 4. Experimentos propostos e parâmetros suportados

| Experimento | Métodos no lote proposto | Entradas e controle | Saída a examinar | Situação |
| --- | --- | --- | --- | --- |
| E1 — Base lexical | `M1, M2, A1` | Corpus e vocabulário congelados; sem LLM; mesma amostra humana | Métricas M1/M2 por fonte, FP/FN, estados e suporte; painel usa M2 | a executar |
| E2 — Extração comparada | `M1, M2, M3` | Mesmas fontes e rótulos; provedor/modelo fixos; orçamento documentado | Métricas M1/M2/M3 no suporte comum por fonte; abrangência e descartes M3 | a executar |
| E3 — Julgamento de associação | `M2, A1, A2` | Fontes e dicionário congelados; candidatas geradas com M2; sem M3 consumindo o orçamento | A1/A2 sobre pares humanos no suporte comum de A2; estados, descartes e pendências | a executar |
| E4 — Repetição operacional | Repetir a configuração do experimento escolhido | Entradas estruturadas idênticas e ordem preservada; cache identificado | Comparação das saídas e evidências, chamadas, acertos de cache e falhas | a executar |
| E5 — Descrição curricular | Método lexical ativo explicitamente identificado | Mesmo corpus real; denominadores visíveis; limiar fixo | I1–I8 e evidências para interpretação com especialistas | a executar |

E1 e E2 podem ser obtidos em um único lote com `M1,M2,M3`, calculando a comparação comum, mas a presença de M3 concluído restringe automaticamente o suporte dos métodos lexicais. Não apresentar a métrica M1/M2 de E1 e a de E2 como uma diferença causada só pelo modelo se os suportes forem diferentes. E3 separado evita o consumo compartilhado de orçamento por M3. Um lote com todos os métodos é suportado, mas M3 roda antes de A2 e pode consumir o orçamento ou impedir sua execução; esse efeito precisa ser registrado.

Para uma execução E1 e outra E2/E3 em lotes diferentes, as fontes podem ser iguais e as amostras distintas devido ao ID. Uma comparação estritamente pareada requer os mesmos IDs humanos de avaliação. O software não fornece um comando público para clonar a amostra entre lotes. Preservar o mesmo lote com todos os métodos é a opção nativa para essa condição; uma avaliação offline com amostra fixa entre lotes é proposta adicional, não automação implementada.

| Parâmetro ou controle | Implementação atual | Decisão do protocolo |
| --- | --- | --- |
| `source` | `csv`, `jobspy` ou `demo` | CSV real congelado; excluir demonstração da avaliação empírica |
| `methods` | Lista de M1/M2/M3/A1/A2; API exige ao menos um M | Registrar solicitados, disponíveis e executados; indisponível não significa resultado zero |
| `tags` | Até 500 caracteres; igualdade normalizada com ID/nome/conceito/área/alias; união por “ou” | Vazio no experimento principal; ablações de escopo precisam protocolo próprio |
| `threshold` | 0–100; padrão 5; altera prioridade I3, não o extrator | Fixar antes do teste; análise de sensibilidade apenas descritiva |
| `target` / `radius` | 1–2000 vagas; 0–500 km | Registrar os valores e o total efetivo; CSV não aplica filtro espacial nem promete atingir a meta |
| `terms` / plataforma | 1–20 termos fora da demo; Indeed/LinkedIn/Glassdoor/Google | Registrar como definição do corpus, não variar entre métodos |
| `llm_limit` | 0–10000; padrão 3000; orçamento compartilhado entre tentativas M3/A2 | Dimensionar antes da execução e reportar tentativas, não presumir conclusão pelo valor configurado |
| Provedor/modelo | `TCC_LLM_BASE_URL`, `TCC_LLM_MODEL`; padrão OpenAI compatível e `gpt-4o-mini` | Registrar endpoint público/modelo e data; nunca chave; confirmar execução real pelo resultado |
| Autenticação LLM | `TCC_LLM_API_KEY` ou `OPENAI_API_KEY` | Configurar somente por ambiente; não copiar para manifesto/planilha |
| Prompt/temperatura | `PROMPT_VERSION="tcc-evidence-v1"`; temperatura 0; JSON Schema estrito | Congelar código e versão; não há editor de prompt nem temperatura pela interface |
| Timeout/retries | Cliente: 45 s por padrão; até duas retentativas, limitadas pelo orçamento; parâmetros do construtor | Manter padrões ou registrar alteração técnica; não são controles públicos da análise |
| Tamanho por chamada | Até 60000 caracteres serializados; sem divisão automática; limites de saída 2400 tokens M3 e 1200 A2 | Identificar textos não processados; não tratá-los como negativos |
| Cache | SQLite em `TCC_DATA_DIR`; hash de entrada/provedor/modelo/método/versão/temperatura | Identificar uso prévio e arquivar evidências; não apagar cache de produção para forçar um experimento |

## 5. Tarefas, suportes e métricas

### Extração M1 × M2 × M3

Unidade: `(fonte, documento, competência)`. Avaliar vagas e PPC **separadamente**, com precisão, revocação e F1 micro contra rótulos primários. M1 é um subconjunto de base do vocabulário; M2 usa o escopo ampliado; M3 recebe a lista canônica do escopo. Menor cobertura vocabular de M1 pode gerar FN no universo amplo: não atribuir esse efeito exclusivamente à qualidade do algoritmo lexical.

O código reconhece M1/M2 em todos os documentos, incluindo documentos sem predições positivas. Para M3 só entram documentos concluídos. `validation_result` intersecta esse suporte por fonte e compara os métodos nos mesmos rótulos. Se M3 não concluir nenhum documento de uma fonte, não recebe métrica nessa fonte nem restringe M1/M2 nela. Falha, cancelamento, ausência de credenciais e orçamento esgotado não são rótulos negativos.

M3 processa primeiro vagas e depois disciplinas; uma execução parcial pode selecionar documentos iniciais e não alcançar o PPC. Informar suporte, exclusões e ordem, além das métricas; um resultado em poucos documentos concluídos não equivale ao desempenho no corpus completo. Citação verificada significa substring real, não interpretação semântica correta.

### Associação A1 × A2

Unidade de avaliação: `(vaga, disciplina)`, diferente da unidade de julgamento `(vaga, disciplina, competência)`. A1 agrega candidatas positivas literais ou conceituais. A2 recebe apenas as candidatas A1, com prioridade para literais, e usa a descrição da vaga e ementa/objetivos; A1 pode ter localizado a competência no **título**. Registrar essa assimetria: comparar A1/A2 mede a etapa operacional completa atual, não um efeito isolado do modelo com entradas perfeitamente idênticas.

`covers` e `partial` concluídos tornam o par positivo. O par só recebe negativo A2 quando todas as candidatas de competência desse par concluíram sem positivo. Um par com positivo já é avaliável mesmo se outras candidatas estiverem pendentes; um par incompleto sem positivo fica fora da avaliação. Citações rejeitadas não viram negativos automáticos.

Com A2 válido, o relatório restringe A1 e A2 aos mesmos pares humanos efetivamente julgados. Como esses pares são candidatas A1, a linha A1 desse recorte tem predições positivas por construção; sua revocação nesse conjunto não mede recuperação global de associações. Não confundir o desempenho A1 isolado nos pares sorteados com A1 no suporte restrito de E3. Ausência de pares humanos em comum com A2 significa comparação não calculável, não precisão zero nem aprovação da meta.

### Cálculo e indicadores

Usar as contagens `TP`, `FP`, `FN`, `TN` e os denominadores do relatório:

- `Precisão = TP / (TP + FP)`.
- `Revocação = TP / (TP + FN)`.
- `F1 = 2 × Precisão × Revocação / (Precisão + Revocação)`.

O código retorna zero quando um denominador é vazio; no texto científico explicitar “não calculável/sem positivos avaliáveis” quando aplicável, junto das contagens. Não inferir fracasso empírico de uma execução ausente ou de denominador nulo. As métricas usam os rótulos não vazios, não todo o produto cartesiano possível.

I1–I8 são estatísticas descritivas do método lexical ativo; quando M1 e M2 estão juntos, M2 alimenta o painel. M3, A2 e aceitar/rejeitar associações não substituem os indicadores. I2 mede cobertura literal ponderada; I4 acrescenta âncoras conceituais como limite lexical conceitual; não é uma “melhora semântica validada” de I2. I5 reutiliza I2 por área; I6 pode se sobrepor entre disciplinas; I7 não recomenda excluir fundamentos; I8 é Jaccard, não causalidade. Sem demanda reconhecida, percentuais zerados por convenção computacional não sustentam conclusão de alinhamento nulo.

## 6. Registro de resultados — preencher somente após executar

Todas as células de resultados abaixo ficam **em branco** até existir evidência. “A executar” é um estado do protocolo, nunca um valor de métrica. Duplicar linhas para distinguir experimentos/suportes; não combinar tarefas ou fontes em uma única média.

| Experimento | Método | Fonte/tarefa | Lote e hash da amostra | Documentos/pares avaliados | Rótulos avaliados | Excluídos | TP | FP | FN | TN | Precisão | Revocação | F1 | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | M1 | Vagas/extração | | | | | | | | | | | | a executar |
| E1 | M2 | Vagas/extração | | | | | | | | | | | | a executar |
| E1 | M1 | PPC/extração | | | | | | | | | | | | a executar |
| E1 | M2 | PPC/extração | | | | | | | | | | | | a executar |
| E2 | M1 | Vagas/extração, suporte comum | | | | | | | | | | | | a executar |
| E2 | M2 | Vagas/extração, suporte comum | | | | | | | | | | | | a executar |
| E2 | M3 | Vagas/extração, suporte comum | | | | | | | | | | | | a executar |
| E2 | M1 | PPC/extração, suporte comum | | | | | | | | | | | | a executar |
| E2 | M2 | PPC/extração, suporte comum | | | | | | | | | | | | a executar |
| E2 | M3 | PPC/extração, suporte comum | | | | | | | | | | | | a executar |
| E3 | A1 | Associação, suporte comum | | | | | | | | | | | | a executar |
| E3 | A2 | Associação, suporte comum | | | | | | | | | | | | a executar |

| Registro complementar | Unidades comuns entre anotadores | Acordo observado | Kappa global | Chamadas de rede | Falhas de chamada | Cache hits | Descartes | Documentos/julgamentos pendentes | Duração total | Custo monetário documentado | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2 | | | | | | | | | | | a executar |
| E3 | | | | | | | | | | | a executar |
| E4 — repetição com cache | | | | | | | | | | | a executar |

Arquivar os valores `validation.supports`, `scope_note`, `method_status`, `results.llm`, `summary` e as evidências, além das tabelas exportadas. Campos sem resultado devem permanecer identificados como pendentes/indefinidos; não preencher usando exemplos dos PDFs ou testes de software.

## 7. Erros, custo, duração e reprodutibilidade

**Erros:** `validation_result` produz FP/FN por unidade e método, sem classificar automaticamente causas. Após fechar o teste, revisar cada erro com fonte, evidência e anotação humana. Propor categorias: vocabulário ausente/fora de escopo, alias/ambiguidade, negação, referência bibliográfica residual, segmentação, âncora conceitual inadequada, interpretação semântica e desacordo de anotação. Se as categorias puderem se sobrepor, definir causa principal ou registrar multilabel antes de totalizar. Registrar separadamente respostas LLM descartadas por contrato/citação e falhas operacionais: não são o mesmo evento que FP/FN semântico.

**Custo:** `results.llm.stats` informa tentativas de rede, falhas, cache e descartes; `summary.llm_calls` informa chamadas. Retentativas consomem orçamento. O contador agregado de descartes não é uma taxa única de alucinação: M3 conta itens de extração e A2 pode contar respostas, com tarefas e denominadores diferentes. A aplicação não armazena automaticamente uso de tokens, preços ou cobrança real do provedor. Um custo monetário exige registro externo auditável de uso, tabela de preços datada e câmbio, quando pertinente; chamadas não equivalem a valor monetário. A estimativa anterior à execução também não é cobrança observada.

**Duração:** os estágios da API não instrumentam separadamente o tempo de M1, M2, M3 e A2. Em `process_batch`, a duração atribuída à extração corresponde ao tempo decorrido do processamento que chama `analyze`; associação e indicadores não recebem cronometragem própria nesse registro. Não apresentar esse valor como benchmark isolado de extração ou latência média do LLM. Para o estudo atual, registrar duração total da execução e da coleta em campos separados, hardware/versões e condição de cache. Tempo de revisão/anotação humana precisa de registro externo. Cronometragem por método é proposta de instrumentação futura.

**Repetição:** preservar a ordem das listas de entradas, o corpus, o dicionário e a configuração. `engine.analyze` produz `fingerprint_kind="input"`, hash das entradas estruturadas, configuração e dicionário; ele não incorpora commit, dependências, respostas, anotações ou toda a configuração LLM do ambiente. Alterar somente a lista de métodos pode mudar o hash mesmo com corpus idêntico. Igualdade desse hash não comprova igualdade de resultados; comparar também predições, indicadores e evidências arquivados.

O cache usa hash próprio de entrada, provedor, modelo, método, versão do prompt e temperatura e reconfere as citações. Uma repetição com cache demonstra recuperação do material armazenado, não uma nova geração independente. O estado de descarte/cache também pode diferir entre a primeira execução e a recuperação, pois só evidências de extração elegíveis são guardadas. Temperatura zero não garante determinismo temporal do provedor. Uma repetição sem cache exigiria ambiente de pesquisa separado e planejamento de consumo; não apagar cache ou dados existentes para produzir essa condição.

## 8. Propostas adicionais que não são automações implementadas

| Proposta futura | Por que pode ser útil | Limite atual |
| --- | --- | --- |
| Particionamento desenvolvimento/teste e clonagem de amostra entre lotes | Evitar vazamento e preservar comparações pareadas | Preparação e manifesto externos; sem fluxo nativo dedicado |
| Vocabulário de interseção M1/M2/M3 em análise complementar | Separar efeito de inventário do efeito do reconhecedor | Relatório atual usa o universo anotado importado; não gera essa ablação automaticamente |
| Intervalos de confiança e comparação pareada por reamostragem de documentos/pares | Quantificar incerteza sem tratar linhas correlacionadas como observações independentes | Sem bootstrap, teste estatístico ou análise de poder implementados |
| Kappa por fonte/tarefa e adjudicação | Evitar que uma medida global esconda divergências específicas | Aplicação oferece kappa global e papéis primário/secundário, sem consenso automático |
| Associação ordinal e avaliação de recuperação de candidatas | Avaliar três vereditos e relações fora das candidatas lexicais | Validação atual é binária; A2 não percorre todos os pares |
| Tempos por método, tokens e custo monetário | Medir esforço computacional comparável e cobrança | Contadores atuais não fornecem benchmark isolado nem faturamento |
| Curadoria ablada e varredura de limiar | Investigar quais regras afetam extração e prioridade de lacunas | Exige lotes/protocolo manual; não há execução automática de grade; limiar I3 não altera F1 de extração |

Essas propostas não devem aparecer no capítulo 5 como funcionalidades entregues ou resultados observados. Se executadas posteriormente, precisam ter procedimento, implementação e evidência identificados à parte.

## 9. Rastreabilidade da leitura estática

| Referência | Funções/elementos consultados | Relação com este protocolo |
| --- | --- | --- |
| [server/engine.py](../../server/engine.py) | `FORMULAS`, `find_matches`, `_discipline_sections`, `_job_sections`, `_extract`, `_run_llm`, `analyze` | Escopo lexical, bibliografia, candidatas, ordem LLM, agregação binária, indicadores e hash de entrada |
| [server/llm.py](../../server/llm.py) | `PROMPT_VERSION`, `MAX_SOURCE_CHARS`, `llm_status`, `LLMClient._invoke`, `extract_competencies`, `judge_pair`, `stats` | Configuração, JSON, citações, cache, orçamento e falhas |
| [server/reporting.py](../../server/reporting.py) | `make_sample`, `import_annotations`, `_metrics`, `validation_result`, `export_tables` | Amostragem, rótulos, suporte comum, métricas, kappa e tabelas |
| [server/app.py](../../server/app.py) | `validate_config`, `process_batch`, `sample_batch`, `annotations_batch`, `export_batch` | Limites públicos, etapas, amostra prévia e importação após processamento |
| [server/areas.py](../../server/areas.py) | `CANONICAL_AREAS`, `canonical_area` | Estratos e classificação heurística de vagas |
| [server/dictionary.py](../../server/dictionary.py) | `DICTIONARY`, `build_dictionary` | Inventário inicial próprio, subconjunto base e curadoria |
| [docs/methodology.md](../methodology.md) | Seções de indicadores, LLM, validação e fingerprint | Definições operacionais e limites científicos |
| [docs/review-evidence.md](../review-evidence.md) | Fluxo de revisão e amostra cega | Ordem de salvar, exportar e renovar a amostra |
| [server/tests/test_engine.py](../../server/tests/test_engine.py) | `MatchingTests`, `IndicatorTests` | Casos de ambiguidade/negação, bibliografia, conceitos, separação de métodos e falhas não negativas |
| [server/tests/test_reporting.py](../../server/tests/test_reporting.py) | `CommonSupportTests` | Suporte comum M3/A2, ausência de saída e conteúdo da amostra cega |
| [server/tests/test_llm.py](../../server/tests/test_llm.py) | `LLMTests` | Contratos offline de rede simulada, credenciais, orçamento, cache e citações |
| [server/tests/test_api.py](../../server/tests/test_api.py) | `test_exports_blind_sample_and_real_validation`, `test_sample_can_be_frozen_before_methods_and_edit_requires_new_sample` | Importação de rótulos e invalidação/renovação da amostra |

Os testes foram **consultados**, não executados para elaborar este plano. Seus exemplos sintéticos e respostas simuladas verificam comportamento do software; não medem desempenho científico nos dados reais do TCC.
