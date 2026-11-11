# Auditoria dos métodos e indicadores

## Base e alcance da auditoria

Inspeção documental em **10/11/2026 (America/Sao_Paulo)**. Este parecer descreve a implementação no commit **`8300112985bbc873116182feaa4dd3c772677841`**, abreviado como `8300112`. Todas as referências de arquivo, função e linha abaixo se referem a essa revisão. Foram inspecionados `engine.py`, `dictionary.py`, `areas.py`, `llm.py`, `reporting.py` e os testes correspondentes. Não foi localizado `AGENTS.md` nos diretórios consultados.

A auditoria é estática e documental. Não foram executados testes, análises, coleta de vagas ou chamadas a modelos, nem consultados dados operacionais. A existência de código e de testes permite descrever comportamentos previstos e cenários cobertos; não comprova que um método foi executado sobre um corpus real, que houve acesso a um provedor ou que metas científicas foram atingidas. Nenhuma funcionalidade ou dado foi alterado para produzir este documento.

O sistema implementa reconhecimento lexical por vocabulário e regras, aproximação curricular por relações cadastradas e integração opcional com um LLM. Os indicadores do painel permanecem lexicais mesmo quando M3 ou A2 são solicitados. Essa separação está explícita em `analyze`: os indicadores são calculados antes da integração das respostas LLM ([E4], [E6]).

## 1. Métodos efetivamente implementados

| Identificador | Procedimento observado | Entradas elegíveis | Saída e alcance |
| --- | --- | --- | --- |
| M1 | Mesmo reconhecedor lexical de M2, limitado às entradas com `base=True` | Título e descrição de cada vaga; ementa e objetivos de cada disciplina | Presenças por documento e competência no subconjunto de base. Não constitui outro algoritmo de aprendizagem ([D1], [E1], [E2], [E3], [E6]). |
| M2 | Reconhecimento de nomes canônicos e aliases do vocabulário selecionado, com regras de fronteira, contexto e negação | Mesmos campos de M1 | Presenças no vocabulário ampliado. É o método ativo do painel quando M1 e M2 são selecionados simultaneamente ([E3], [E6]). |
| M3 | Extração por chamada ao provedor configurado, com lista fechada de nomes canônicos permitidos | Título e descrição concatenados; ementa e objetivos elegíveis concatenados | Competências e citações verificadas por documento. Não é extração aberta de entidades desconhecidas e não substitui os indicadores lexicais ([E7], [L3]). |
| A1 | Geração de candidatas vaga–disciplina por competência compartilhada literalmente ou por âncora conceitual no PPC | Extração do método lexical ativo | Registros `covers` ou `partial`, acompanhados de trechos. O resultado binário considera positivo qualquer par com uma candidata ([E4], [E6]). |
| A2 | Julgamento LLM das candidatas lexicais, por competência | **Descrição** da vaga e ementa/objetivos da disciplina; o título da vaga não integra esse julgamento | `covers`, `partial` ou `does_not_cover`, com justificativa e duas citações. A integração converte o último rótulo para `none` ([E7], [L4]). |

O dicionário inicial é próprio desta implementação: a lista contém 73 entradas, sendo 49 tecnologias e 24 conceitos; 34 entradas estão marcadas como base. O próprio arquivo declara que não corresponde ao dicionário original ausente dos anexos. Esses números descrevem a lista inicial, antes de curadoria e filtros, e não uma taxonomia empiricamente validada ([D1]).

M1 e M2 compartilham nomes, aliases e mecanismo de decisão para as entradas em comum. A comparação entre eles mede principalmente o efeito da abrangência do vocabulário. Não se deve descrevê-la como comparação entre um algoritmo simples e um reconhecedor estatístico de entidades, nem atribuir os resultados à reprodução de um dicionário original não disponibilizado.

### Reconhecimento lexical, NER e LLM

Reconhecimento de entidades nomeadas, ou NER, designa uma tarefa e pode ser realizado por regras, aprendizagem ou combinações dessas abordagens. Nos módulos auditados não há treinamento, ajuste ou inferência de um modelo dedicado de NER, como um classificador de sequência. M1 e M2 reconhecem menções por vocabulário e expressões regulares. Embora `find_matches` devolva os limites `start` e `end` de ocorrências literais, não há um pipeline explícito dedicado à tipagem e avaliação de entidades por spans, com um esquema próprio de anotação NER. A validação implementada é por presença de competência no documento. É admissível caracterizar o mecanismo como reconhecimento de menções por regras ou por gazetteer, sem apresentá-lo como um NER treinado ([E1], [R3]).

M3 é uma tarefa de extração orientada por instruções a um LLM externo. O código não treina esse modelo. A função recebe a lista de nomes permitidos do vocabulário filtrado e só mantém nomes dessa lista com uma citação presente na fonte. A lista inclui também conceitos amplos de formação e práticas profissionais; nem toda entrada corresponde a uma entidade nomeada no sentido linguístico estrito ([E7], [L3]).

As sugestões de termos desconhecidos são outra heurística: procuram palavras iniciadas por maiúscula ou padrões semelhantes a camel case na descrição, eliminam termos conhecidos e alguns termos comuns e limitam a lista a 20 sugestões. Não são predições de M3, não integram os indicadores e não constituem NER estatístico ([E8]).

## 2. Regras de extração e relações curriculares

O reconhecimento normaliza caixa e acentos por decomposição Unicode, preserva um mapeamento para recuperar substrings originais e trata os aliases como texto escapado. As fronteiras impedem, por exemplo, que `Java` seja identificado apenas dentro de `JavaScript`. Ocorrências sobrepostas da mesma entrada são suprimidas. Aliases maiores são procurados primeiro ([E1]).

Os aliases `C`, `R`, `Go`, `ML`, `AI` e `IA` exigem pelo menos uma expressão de contexto cadastrada em uma vizinhança de 90 caracteres antes ou depois da ocorrência. `R$` é excluído. A regra é uma coocorrência local, não uma interpretação sintática ou desambiguação aprendida. Um contexto técnico próximo pode ser incidental, e um uso técnico distante pode não ser reconhecido ([E1], [D1]).

A negação utiliza padrões locais: examina até 130 caracteres anteriores e 85 posteriores, reconhece algumas expressões negativas, reinicia o contexto anterior após adversativas e trata “não apenas” como exceção. Não resolve todas as formas de negação ou coordenação. Há um caso composto relevante dedutível da ordem das regras: em “Não apenas SQL; não exigimos Java”, encontrar a exceção “não apenas” na janela anterior causa retorno imediato sem verificar a negação posterior de Java. O teste existente cobre a exceção positiva isolada, mas não essa combinação; nenhum exemplo foi executado nesta auditoria. O código não atribui pesos distintos a requisito obrigatório e desejável ([E1], [T1]).

O PPC é analisado somente pelos campos `syllabus` e `objectives`. O nome da disciplina, a carga horária e o campo separado `bibliography` não geram cobertura. Um cabeçalho reconhecido de bibliografia ou referências no início de linha corta o restante daquele campo. Uma referência misturada à ementa sem cabeçalho reconhecível pode continuar elegível; por isso, a revisão da segmentação é metodologicamente relevante ([E2], [L1]).

Cada competência conta uma vez por identificador de vaga, independentemente do número de repetições. A extração guarda até dois trechos por seção, mas essa limitação de evidências não muda a presença binária no documento. O motor recebe os registros prontos: não realiza deduplicação de anúncios por URL ou conteúdo dentro de `analyze`. As fórmulas pressupõem identificadores de entrada únicos ([E2], [E3]).

As tags são separadas por vírgula, ponto e vírgula ou quebra de linha. Após normalização, a correspondência é por igualdade com identificador, nome, conceito, área ou alias; várias tags funcionam como união de escopos. Não há busca semântica por tags. As âncoras conceituais necessárias continuam sendo extraídas, inclusive quando estão fora do escopo demandado ou quando são criadas apenas como âncora auxiliar ([E3], [E8]).

Uma entrada recebe os seguintes estados globais:

| Estado | Condição no código | Interpretação admissível |
| --- | --- | --- |
| `covered` | Há nome ou alias da própria entrada em pelo menos uma ementa ou objetivo | Presença textual curricular; não comprova profundidade ou aprendizagem. |
| `partial` | Não há presença literal da entrada, mas há seu conceito relacionado no PPC | Candidata conceitual; não demonstra ensino da tecnologia específica. |
| `gap` | Não há presença literal nem âncora conceitual elegível | Ausência de evidência textual no vocabulário e corpus analisados. |

Os estados e a relação tecnologia–conceito decorrem de cadastro e reconhecimento lexical. Não são julgamentos de equivalência produzidos por A2. Uma competência pode estar literalmente coberta em uma disciplina e ter uma candidata parcial em outra ([E3], [E4]).

### Classificação por área

As categorias são Programação, Análise, Dados, Suporte, Infraestrutura e Outra. Uma área informada é normalizada por aliases; se não for reconhecida, torna-se Outra. Somente quando a área está vazia o classificador consulta primeiro o título e depois a descrição. As regras de inferência têm prioridade fixa: Suporte, Dados, Infraestrutura, Programação e Análise. Segurança é agrupada em Infraestrutura e qualidade/QA em Programação ([A1]).

Essa categorização é uma heurística operacional, não uma classificação ocupacional aprendida ou validada contra especialistas. A área de uma entrada do dicionário é um agrupamento do vocabulário; I5 usa a área atribuída às **vagas**, não esse agrupamento das competências ([A1], [E5]).

## 3. Indicadores: fórmulas e denominadores reais

Considere `N = len(jobs)`, a quantidade de registros recebidos pelo motor; `J(c)`, os identificadores distintos de vagas com a competência `c`; e `f(c) = |J(c)|`. O conjunto `C` contém as competências do escopo ativo com `f(c) > 0`. As expressões abaixo pressupõem identificadores únicos nos registros.

Defina `L(c)=1` quando existe presença literal elegível de `c` em alguma disciplina, e zero caso contrário. Defina `P(c)=1` quando há presença literal **ou** âncora conceitual elegível no PPC. Para uma disciplina específica, `L_d(c)` indica presença literal nela. O denominador ponderado é `W = Σ[c∈C] f(c)`, isto é, o total de presenças competência–vaga, e não a quantidade de vagas ([E3], [E4], [E5]).

Tecnologias e conceitos são entradas independentes. Se uma vaga mencionar duas entradas relacionadas, ambas podem contribuir para `W`. Uma vaga com várias competências contribui para vários pesos; não há divisão de um peso unitário entre suas competências. Não se pondera por salário, carga horária, nível da vaga ou importância curricular presumida.

| Indicador | Operação implementada | Observações e referência |
| --- | --- | --- |
| I1 — frequência | `round(100 × f(c) / N, 2)` | Presença por vaga, não contagem de repetições; a soma de diferentes competências pode exceder 100% ([E2], [E4]). |
| I2 — cobertura literal ponderada | `round(100 × Σ f(c)L(c) / W, 2)` | Uma parcial conceitual tem peso **zero**. O numerador soma frequências de entradas com estado `covered` ([E4]). |
| I3 — lacunas prioritárias | `{c∈C : L(c)=0 e I1(c)≥τ}` | É uma lista de identificadores, com contagem auxiliar; inclui parciais. O limiar padrão do motor é `τ=5`. A comparação usa I1 **já arredondado**, com igualdade incluída ([E4]). |
| I4 — cobertura lexical com conceito | `round(100 × Σ f(c)P(c) / W, 2)` | Uma parcial conceitual tem peso **um**. É uma aproximação exploratória, não cobertura semântica confirmada por LLM ([E4]). |
| I5 — cobertura por área | Para cada área `a`, `round(100 × Σ f_a(c)L(c) / W_a, 2)`, com `f_a(c)=card(J(c)∩V_a)` e `W_a=Σ f_a(c)` | `card` denota cardinalidade. Recalcula o peso nas vagas da área e mantém o PPC. A resposta também contém a versão conceitual por área. O motor retorna áreas com registros presentes ([E5]). |
| I6 — contribuição por disciplina | `round(100 × Σ f(c)L_d(c) / W, 2)` | Não usa âncoras conceituais. Como disciplinas podem compartilhar competências, a soma pode exceder I2 e 100% ([E5]). |
| I7 — currículo sem demanda observada | `{c do escopo ativo : L(c)=1 e f(c)=0}` | Ausência nas vagas do lote; não constitui evidência de conteúdo dispensável ([E5]). |
| I8 — coocorrência | `round(card(J(A)∩J(B)) / card(J(A)∪J(B)), 4)` | `card` denota cardinalidade. Jaccard entre 0 e 1. A matriz retornada pelo motor limita-se às seis competências mais frequentes; não é uma matriz de todas as entradas ([E5]). |

O método ativo é M2, se solicitado; caso contrário, M1, se solicitado. M3 sozinho deixa o painel lexical sem competências e gera um aviso para selecionar M1 ou M2. As respostas M3 e A2 são integradas separadamente, após o cálculo dos indicadores. A configuração de associação A1/A2 não altera as condições de cobertura utilizadas em I2, I4 ou I6 ([E3], [E6]).

`_percent` devolve `0.0` para denominador vazio. Uma união vazia no Jaccard também recebe zero. Logo, zero pode significar ausência de dados reconhecidos, e não uma cobertura empiricamente medida como nula. O motor avisa quando não há vagas; não há aviso específico para todo caso em que existem vagas, mas `W=0`. Esses resultados exigem leitura conjunta das contagens ([E2], [E5], [E6]).

A fórmula ideal de I3 em termos de frequência exata difere ligeiramente da implementação: arredondar I1 antes de aplicar o limiar pode incluir uma competência cujo percentual não arredondado é pouco inferior a `τ`. Trata-se de uma regra de decisão observável no código, que deve ser registrada se houver competências próximas ao limiar ([E4]).

## 4. Associação e integração LLM

### A1 e dependência das candidatas

Para cada competência demandada do método lexical ativo, `analyze` combina suas vagas com as disciplinas de presença literal ou conceitual. A associação é `covers` quando a própria entrada aparece na disciplina e `partial` quando somente seu conceito aparece. O atributo `verified=True` é preenchido porque os trechos foram extraídos da fonte; não representa aprovação humana ou semântica ([E4]).

Mesmo com A1 desmarcado, candidatas lexicais são geradas quando A2 foi solicitado. Entretanto, elas continuam dependendo de M1 ou M2 como método ativo. Competências encontradas somente por M3 não alimentam essa geração. A combinação de métodos solicitados não garante, portanto, que existam candidatas para A2 ([E3], [E4], [E7]).

### M3 e A2: contrato, execução parcial e verificação

M3 e A2 dependem de chave, provedor e modelo configurados; os padrões de configuração apontam para uma API compatível com OpenAI e o modelo `gpt-4o-mini`. `llm_status` identifica configuração utilizável, sem atestar uma chamada concluída. A auditoria não verificou credenciais nem disponibilidade de provedor ([L1]).

O cliente solicita temperatura zero e saída JSON Schema estrita. O código valida a estrutura, rejeita JSON com chaves duplicadas ou constantes não finitas e exige citações literais contínuas. Em M3, verifica também o nome na lista permitida. Em A2, verifica rótulo, justificativa e a presença de um trecho em cada fonte elegível ([L1], [L2], [L3], [L4]).

Essas verificações estabelecem procedência textual e conformidade de formato. Não verificam automaticamente se a citação sustenta a competência ou o julgamento, se a menção está negada ou se há equivalência pedagógica. A instrução para ignorar negações é enviada ao modelo; ela não é reaplicada pelo validador lexical às respostas M3. Uma citação verdadeira pode sustentar uma conclusão incorreta. Da mesma forma, o descarte de citação inexistente não constitui uma medição completa de alucinação ([L3], [L4]).

O orçamento é compartilhado entre M3 e A2 e inclui retentativas. O cliente admite, por padrão, até duas retentativas além da tentativa inicial. O tamanho máximo do payload serializado por chamada é 60.000 caracteres. Respostas concluídas são armazenadas em cache por hash de entrada, modelo, provedor, método, temperatura e versão do prompt; o cache é conferido antes do limite de chamadas de rede e as citações são revalidadas ([L2]).

Na orquestração, M3 percorre primeiro as vagas e depois as disciplinas. A2 prioriza candidatas literais e ordena-as por identificador. Esgotamento de orçamento, cancelamento e três resultados `failed` consecutivos podem interromper chamadas. O recorte concluído não é uma amostra aleatória: orçamento pequeno pode deixar sobretudo o PPC ou candidatas conceituais sem julgamento ([E7]).

Para a validação binária A2, um par vaga–disciplina torna-se positivo se alguma de suas candidatas concluídas recebeu `covers` ou `partial`. Só se torna negativo quando todas as candidatas daquele par foram concluídas sem positivo. Pares não resolvidos não entram como negativos. Essa redução binária não altera o peso zero de parciais em I2 ([E7]).

Os estados precisam ser distinguidos: “configurado”, “solicitado”, “chamada tentada”, “resposta válida”, “predição disponível” e “método avaliado” não são sinônimos. Contadores do cliente e `method_status.executed` têm critérios diferentes: o primeiro registra métodos com resposta validada, inclusive descarte A2, enquanto o segundo depende de sua presença em `predicted_by_method`. Nenhum desses campos, isoladamente, comprova desempenho científico ([L2], [E6]).

## 5. Validação humana implementada

### Amostra e cegamento

`make_sample` usa uma semente derivada de `sample_seed`, quando presente, ou do identificador do lote. Agrupa as vagas por área, sorteia até 12 por grupo em ordem alfabética de áreas e corta o resultado agregado para 60 vagas. Inclui todas as disciplinas e uma linha por competência do dicionário recebido para cada documento. Sorteia até 100 pares vaga–disciplina do produto cartesiano entre as vagas selecionadas e as disciplinas ([R1]).

A amostra de extração fornece título e descrição para vagas e ementa e objetivos para disciplinas. O campo separado de bibliografia é excluído; porém, `make_sample` não reaplica o corte de cabeçalhos internos usado pelo motor. Os anotadores precisam seguir a instrução de excluir bibliografia, ou o texto deve ter sido corrigido na revisão. A lista de unidades e os textos não contêm predições dos métodos, mas isso não demonstra que um anotador não tenha consultado resultados por outros meios ([R1], [E2]).

A seleção é independente das predições, mas não representa uma amostragem uniforme de todo o mercado. O corte agregado tem uma consequência concreta: com seis áreas contendo pelo menos 12 vagas cada, as cinco primeiras áreas em ordem alfabética ocupam as 60 posições, e Suporte, a última, fica inteiramente fora da amostra. O teste existente de composição da amostra usa uma única vaga e não cobre esse caso ([R1], [T3]).

O cegamento deve ser sustentado por protocolo de anotação, separação de desenvolvimento e teste e registro de quando os anotadores tiveram acesso às saídas. Código de amostragem independente e uma planilha sem predições são condições úteis, mas insuficientes para afirmar avaliação cega ou ausência de ajuste sobre o conjunto de teste.

### Rótulos, métricas e suporte comum

`import_annotations` aceita rótulos binários explícitos; células vazias são excluídas. Verifica pertencimento dos identificadores à amostra, cabeçalhos e duplicidade das unidades. As métricas usam a anotação primária. A anotação secundária é utilizada para concordância, sem adjudicação automática ([R2], [R3]).

Para as unidades anotadas consideradas no suporte comum, `_metrics` acumula verdadeiros positivos (`TP`), falsos positivos (`FP`), falsos negativos (`FN`) e verdadeiros negativos (`TN`) e calcula:

- `Precisão = TP / (TP + FP)`;
- `Revocação = TP / (TP + FN)`;
- `F1 = 2 × Precisão × Revocação / (Precisão + Revocação)`.

Os denominadores vazios recebem zero. A agregação é micro sobre unidades binárias de documento–competência, separada por fonte, ou sobre pares vaga–disciplina. Não há cálculo de intervalo de confiança, teste de significância, F1 macro por competência ou matriz de confusão multiclasse de cobertura parcial. O detalhamento de erros contém `fp` e `fn`; não classifica automaticamente suas causas em ambiguidade, negação, bibliografia ou vocabulário ausente ([R3]).

Na extração, M1, M2 e M3 são comparados na interseção dos documentos processados pelos métodos participantes, por fonte. M1 e M2 cobrem todos os documentos, inclusive aqueles sem predição positiva; M3 depende de `evaluated_documents`. Se M3 não possui documentos concluídos em uma fonte, não recebe métrica nessa fonte nem restringe os demais métodos. Com A2, A1 e A2 são comparados apenas nos mesmos pares anotados efetivamente julgados por A2, incluindo negativos. As quantidades incluídas e excluídas constam de `supports` e `scope_note` ([R3]).

Esse suporte comum evita que uma falha de execução seja transformada em predição negativa, mas não elimina o viés de seleção. Em particular, A2 só recebe candidatas de A1. Quando A1 também é solicitado, todos os pares do suporte A2 são positivos para A1 por construção. Havendo positivos humanos nesse suporte, a revocação de A1 será unitária nesse recorte; isso não mede a recuperação dos pares relevantes que ficaram fora das candidatas. As métricas A1/A2 resultantes avaliam um julgamento condicionado à seleção lexical, não a cobertura global do produto cartesiano ([E4], [E6], [E7], [R3]).

Uma competência fora do subconjunto M1 pode ser contabilizada como falso negativo de M1 em um universo anotado mais amplo. Além disso, `make_sample` percorre o dicionário recebido, enquanto as predições de `analyze` podem ser limitadas por tags. `validation_result` restringe documentos, mas não restringe as competências anotadas ao escopo de tags. Se a amostra mantiver o vocabulário completo e houver positivos fora do filtro, eles serão falsos negativos dos métodos filtrados. O estudo precisa declarar o universo de avaliação e decidir como tratar esse descompasso ([R1], [R3], [E3], [E6]).

Os valores `target` retornados são 0,80 para extração em vagas, 0,75 para extração no PPC e 0,70 para associação. São referências de aceitação; o retorno desses números não demonstra que as metas foram alcançadas. A métrica de referência da associação deve ser identificada como precisão no protocolo, distinguindo-a do F1 também calculado ([R3]).

### Concordância entre anotadores

O kappa de Cohen é calculado somente nas unidades com rótulo de ambos os anotadores. Se `p_o` é o acordo observado, `p_1` e `p_2` são as proporções marginais de positivos:

`p_e = p_1p_2 + (1−p_1)(1−p_2)`

`κ = (p_o−p_e)/(1−p_e)`

Sem unidades comuns, não há resultado; quando `p_e=1`, o retorno é `null`, com nota de indefinição. A implementação combina extração de vagas, extração do PPC e associação em uma medida global. Esse valor não é um kappa separado por tarefa, fonte ou competência, e não compara métodos automáticos entre si ([R3]).

## 6. Testes inspecionados e limites da evidência

| Arquivo e funções | Cenários previstos no código do teste | O que essa inspeção não demonstra |
| --- | --- | --- |
| `test_engine.py`, `MatchingTests` | Fronteiras de nomes, família C, contexto para aliases, negação, contraste e recuperação de substring ([T1]) | Cobertura de toda ambiguidade e negação do português ou desempenho em vagas reais. |
| `test_engine.py`, `IndicatorTests` | Bibliografia separada e interna, parcial fora de I2, pesos por vaga, Jaccard, I7, entrada vazia, separação M1/M2, curadoria e estabilidade do hash ([T1]) | Validade externa dos indicadores, cobertura exaustiva de limiares/IDs repetidos ou reprodução de um estudo. |
| `test_engine.py`, `test_real_method_contract_keeps_model_output_separate` e `test_failed_model_documents_are_not_negative_predictions` | Substituição de `LLMClient` por classes locais para testar contratos, separação do painel e orçamento esgotado ([T1]) | Chamada a um modelo real. O nome “real method” não muda o uso de um substituto nesse teste. |
| `test_llm.py`, `LLMTests` | Transporte HTTP simulado, estrutura da requisição, citações, nomes permitidos, bibliografia, cache, orçamento, retentativas e respostas inválidas ([T2]) | Qualidade do provedor, validade semântica dos julgamentos, custo real ou execução externa concluída. |
| `test_reporting.py`, `CommonSupportTests` | Interseção de documentos, recorte A2, ausência de fonte M3 e presença de título na amostra ([T3]) | Uma integração representativa completa entre geração A1 e A2; a fixture contém a inconsistência descrita abaixo. |
| `test_areas.py`, `AreaTests` | Alguns aliases, prioridade do título, categorias da demonstração e partição dos denominadores por área ([T4]) | Acurácia ocupacional em um corpus anotado ou ausência de viés entre áreas. |

Há uma inconsistência específica em `test_reporting.py`: a fixture `annotated_batch` inclui um par negativo de A2, `(j1,d2)`, que não está entre os pares positivos de A1. Quando ambos vêm da integração do motor auditado, isso não ocorre: A2 só julga candidatas já positivas para A1. O teste de suporte comum espera `FP=0` para A1 nessa fixture; com o par de fato presente nas candidatas A1 e o mesmo rótulo humano negativo, A1 teria um falso positivo. O teste continua útil para o mecanismo de interseção, mas não sustenta uma conclusão empírica sobre a capacidade de A1 rejeitar candidatas nesse recorte ([T3], [E4], [E6], [E7]).

Nenhum dos resultados esperados nos testes foi tratado aqui como resultado observado nesta auditoria. Em particular, não foram atribuídos valores de F1, precisão, revocação, kappa, tempo, custo ou tamanho de corpus a uma execução real.

## 7. Rastreabilidade e achados para o estudo

O `fingerprint` é um SHA-256 das disciplinas, vagas normalizadas, configuração e dicionário completo da análise, serializados com ordenação de chaves. A ordem das listas permanece relevante. O retorno declara `fingerprint_kind="input"`. O hash não inclui, por si, o commit, as dependências, os rótulos humanos, as respostas do LLM nem os valores de modelo/provedor recebidos por variáveis de ambiente ([E6]).

O hash da amostra também identifica suas unidades, não o protocolo de anotação nem necessariamente o conteúdo completo dos textos. Temperatura zero, cache e igualdade de hashes de entrada não comprovam igualdade de saídas em execuções independentes ([R1], [L2]).

| Achado | Consequência metodológica | Tratamento nesta auditoria |
| --- | --- | --- |
| Vocabulário próprio e diferença M1/M2 por subconjunto | Não permite alegar reprodução do dicionário original ou comparação de algoritmos NER distintos. | Caracterização explícita; sem mudança de código. |
| Corte de 60 vagas após sorteio de até 12 por área | Pode excluir integralmente a última área no cenário de seis estratos completos. | Limite identificado por leitura do algoritmo; não houve nova amostragem. |
| A2 condicionado às candidatas lexicais | Precisão e revocação são condicionais; não medem recuperação global de relações. | Denominadores e viés descritos; nenhum desempenho presumido. |
| Fixture A1/A2 não representativa da integração | Pode dar aparência de rejeição correta por A1 que não existe naquele mecanismo de candidatas. | Inconsistência documental dos testes registrada. |
| Tags limitam predições sem limitar automaticamente o universo de competências anotadas | Pode contabilizar positivos fora do escopo como falsos negativos. | Ponto de decisão para o protocolo de avaliação. |
| Citação verificada apenas como substring | Não comprova sustentação semântica, ausência de negação ou equivalência curricular. | `verified` interpretado como procedência textual. |
| Exceção “não apenas” verificada antes das demais negações | Uma exceção anterior pode neutralizar uma negação posterior na mesma janela. | Caso composto deduzido do código e ausente dos exemplos de teste; sem nova execução. |
| I3 aplica o limiar ao percentual arredondado | Casos próximos do limiar podem divergir da formulação por frequência exata. | Regra real de implementação registrada. |
| Denominadores vazios retornam zero | Ausência de dados pode ser confundida com resultado de alinhamento nulo. | Leitura condicionada às contagens e ao suporte. |
| Título integra A1/M3, mas não o julgamento A2; amostra curricular não reaplica todo corte interno de bibliografia | As fontes elegíveis não são idênticas em todas as etapas. | Diferenças explicitadas para interpretação e anotação. |
| Hash de entrada e testes simulados | Não constituem comprovação de experimento reproduzido ou execução de modelo real. | Separação entre implementação, teste previsto e evidência empírica. |

As inconsistências e limitações acima foram documentadas sem alterações funcionais, nova análise de dados ou chamadas externas. Qualquer afirmação de eficácia no TCC ainda depende de corpus identificado, protocolo de anotação, suporte avaliado, resultados preservados e análise empírica apropriada.

## Referências de código no commit `8300112`

Os links apontam para a revisão fixa auditada. As linhas abaixo pertencem a essa revisão, e não a alterações futuras do checkout.

| Código | Caminho | Função ou objeto | Linhas |
| --- | --- | --- | --- |
| [D1] | `server/dictionary.py` | `DICTIONARY`, `_entry`, `build_dictionary` | 1–148 |
| [A1] | `server/areas.py` | `CANONICAL_AREAS`, `_RULES`, `infer_area`, `canonical_area` | 11–51 |
| [E1] | `server/engine.py` | `_normalized_offsets`, `_pattern`, `_is_negated`, `find_matches` | 30–106 |
| [E2] | `server/engine.py` | `_discipline_sections`, `_job_sections`, `_extract`, `_percent` | 109–153 |
| [E3] | `server/engine.py` | `analyze`: escopo, método ativo, âncoras e estados | 277–328 |
| [E4] | `server/engine.py` | `analyze`: candidatas A1, demanda e I1–I4 | 329–357 |
| [E5] | `server/engine.py` | `analyze`: I5–I8 e denominadores retornados | 358–390 |
| [E6] | `server/engine.py` | `analyze`: predições, integração LLM, estados, hash e avisos | 391–420 |
| [E7] | `server/engine.py` | `_run_llm` | 187–274 |
| [E8] | `server/engine.py` | `_tags`, `_unknown_terms` | 156–184 |
| [L1] | `server/llm.py` | `_configuration`, `llm_status`, `_ppc_text`, `_strict_json` | 29–84 |
| [L2] | `server/llm.py` | `LLMClient.__init__`, `stats`, `_invoke` | 87–216 |
| [L3] | `server/llm.py` | `LLMClient.extract_competencies`, validador interno | 218–250 |
| [L4] | `server/llm.py` | `LLMClient.judge_pair`, validador interno | 252–274 |
| [R1] | `server/reporting.py` | `make_sample` | 86–117 |
| [R2] | `server/reporting.py` | `_label`, `import_annotations` | 120–160 |
| [R3] | `server/reporting.py` | `_metrics`, `validation_result` | 163–248 |
| [T1] | `server/tests/test_engine.py` | `MatchingTests`, `IndicatorTests` | 24–161 |
| [T2] | `server/tests/test_llm.py` | `LLMTests`, `client` e transporte simulado | 1–185 |
| [T3] | `server/tests/test_reporting.py` | `annotated_batch`, `CommonSupportTests` | 6–70 |
| [T4] | `server/tests/test_areas.py` | `AreaTests` | 9–35 |

[D1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/dictionary.py#L1-L148
[A1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/areas.py#L11-L51
[E1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L30-L106
[E2]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L109-L153
[E3]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L277-L328
[E4]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L329-L357
[E5]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L358-L390
[E6]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L391-L420
[E7]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L187-L274
[E8]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/engine.py#L156-L184
[L1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/llm.py#L29-L84
[L2]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/llm.py#L87-L216
[L3]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/llm.py#L218-L250
[L4]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/llm.py#L252-L274
[R1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/reporting.py#L86-L117
[R2]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/reporting.py#L120-L160
[R3]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/reporting.py#L163-L248
[T1]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/tests/test_engine.py#L24-L161
[T2]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/tests/test_llm.py#L1-L185
[T3]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/tests/test_reporting.py#L6-L70
[T4]: https://github.com/ArthurGrandi/trabalho_conclusao_curso/blob/8300112985bbc873116182feaa4dd3c772677841/server/tests/test_areas.py#L9-L35
