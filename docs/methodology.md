# Metodologia operacional do MVP

Este documento descreve as escolhas implementadas para comparar o conteúdo declarado em um currículo com competências mencionadas em um recorte de vagas de TI. Os documentos de requisitos nomeiam os indicadores I1–I8, mas não fornecem suas definições matemáticas completas nem o dicionário original de 73 competências. As fórmulas e o vocabulário inicial desta implementação são escolhas próprias, explícitas e passíveis de avaliação no TCC. Não devem ser apresentados como uma reprodução validada de um instrumento que não foi fornecido.

A análise produz evidências de presença textual e candidatas de associação. A presença de uma tecnologia na ementa não estabelece a profundidade, a qualidade da aprendizagem ou o domínio dos estudantes. A ausência de menção também não demonstra que o conteúdo nunca é ensinado. Os resultados servem para investigação e revisão curricular com especialistas.

## 1. Unidade de análise e recorte

Um lote reúne as disciplinas revisadas do PPC, as vagas importadas ou coletadas, a configuração do recorte e a curadoria do dicionário vigente na criação do lote. A configuração informa curso, localidade, raio, plataforma, termos de busca, quantidade pretendida de vagas, tags de competência, limiar de prioridade e métodos solicitados. A quantidade efetivamente disponível pode ser menor que a pretendida e é a utilizada nos indicadores.

Vagas são deduplicadas por URL, identificador externo da fonte e combinação normalizada de título, empresa e localidade. Identificadores internos são regenerados e não substituem a identidade da fonte. Descrições diferentes de uma mesma combinação podem representar atualizações do anúncio e não geram uma nova vaga neste critério; anúncios com a mesma função e empregador em localidades distintas permanecem separados. O critério é operacional e deve ser registrado no protocolo do estudo.

O recorte de um CSV deve ser preparado antes da importação: a aplicação não geocodifica localidades nem aplica um filtro espacial ao arquivo. Na coleta JobSpy, o raio de configuração em quilômetros é convertido para milhas inteiras exigidas pela biblioteca. A localização e a aproximação espacial finais dependem da plataforma de origem.

Os textos considerados são:

| Fonte | Texto elegível | Unidade de presença |
| --- | --- | --- |
| Vaga | Título e descrição para a extração lexical e M3 | Competência × vaga |
| PPC | Ementa e objetivos da disciplina | Competência × disciplina |
| Julgamento A2 | Descrição da vaga e ementa/objetivos da disciplina | Competência × vaga × disciplina |

O nome da disciplina, o período, a carga horária e a bibliografia não estabelecem cobertura. A página funciona como referência de localização informada na segmentação; é necessário conferir o PDF original na revisão. O trecho de evidência é uma substring contínua do texto processado, não necessariamente uma reprodução da disposição visual da página.

A mesma competência conta apenas uma vez em uma vaga, mesmo quando aparece no título e repetidamente na descrição. Uma vaga pode mencionar várias competências e contribuir para cada uma delas. A frequência de uma competência representa menções em vagas distintas do recorte, não o número de repetições de palavras, o número de pessoas contratadas ou uma estimativa de demanda de todo o mercado.

Termos de busca selecionam o corpus coletado; tags selecionam o vocabulário da análise. Importações próprias dependem da procedência e dos filtros aplicados pelo pesquisador. Coleta parcial, disponibilidade das plataformas, duplicatas e cobertura geográfica afetam o corpus e precisam ser reportadas.

## 2. Vocabulário, M1 e M2

O arquivo `server/dictionary.py` contém um vocabulário inicial próprio com **73 entradas: 49 tecnologias e 24 conceitos**. Cada entrada possui identificador, nome canônico, sinônimos, conceito relacionado, grupo temático e, quando necessário, palavras de contexto. As relações tecnologia–conceito são hipóteses para localizar conteúdos próximos; não são equivalências pedagógicas.

**M1** é a linha de base lexical restrita às entradas marcadas com `base=True`: são 34 entradas no vocabulário original desta implementação. **M2** utiliza as 73 entradas iniciais, incluindo os conceitos e as relações. Ambos usam o mesmo mecanismo de reconhecimento de nomes, sinônimos, contexto e negação. A comparação mede o efeito desse escopo próprio mais amplo; não constitui, por si só, uma comparação entre dois algoritmos de linguagem distintos.

Os números 34 e 73 descrevem a versão inicial. A curadoria e os filtros podem alterar o conjunto efetivamente utilizado. A aplicação permite adicionar sinônimos e ajustar contextos de competências existentes. As edições são persistidas para o próximo lote; não reescrevem resultados anteriores. Para comparar métodos, é necessário registrar a versão de vocabulário e manter o mesmo corpus e recorte de avaliação.

Quando M1 e M2 são selecionados juntos, o painel de indicadores usa M2. As predições de M1 e M2 continuam separadas para a avaliação humana. Se apenas M1 for selecionado, o painel usa M1. Se nenhum deles for selecionado, não existe painel lexical interpretável; a execução opcional de M3 permanece separada.

### Tags e âncoras conceituais

As tags podem ser separadas por vírgula, ponto e vírgula ou quebra de linha. O filtro normaliza caixa e acentos e compara cada tag **por igualdade** com o identificador, nome, conceito, grupo temático ou algum sinônimo da entrada. Várias tags se combinam por “ou”. Não há busca livre por fragmentos, classificação semântica de tags ou alteração automática das vagas.

Os conceitos relacionados às entradas selecionadas continuam sendo procurados no PPC como âncoras. Uma âncora fora do escopo selecionado pode produzir uma candidata parcial, mas não é acrescentada por esse motivo à lista de competências demandadas. Se nenhuma entrada corresponder às tags, o sistema emite um aviso; resultados vazios não demonstram ausência de demanda no mercado.

## 3. Reconhecimento lexical e limites

A extração normaliza os caracteres para comparação sem distinção de caixa ou acentos, preservando os índices para recuperar o trecho da fonte. Os sinônimos são tratados como texto literal com limites de palavra. Assim, `Java` não é contado apenas por ocorrer dentro de `JavaScript`; os identificadores da família C também recebem tratamento próprio.

Aliases curtos e ambíguos, como `C`, `R`, `Go`, `ML`, `AI` e `IA`, exigem termos de contexto em uma vizinhança de até 90 caracteres. O uso monetário `R$` é excluído. Essa regra reduz alguns falsos positivos, mas depende dos contextos cadastrados e pode produzir falsos negativos ou aceitar usos não técnicos. Contextos são palavras e expressões literais, não regras de expressão regular fornecidas pelo usuário.

Requisitos negados reconhecidos por padrões locais, como “não exige Java” e “sem necessidade de Python”, são suprimidos. Conjunções adversativas, como “mas”, reiniciam o escopo local da negação; “não apenas” não é tratado como negação de requisito. O mecanismo usa janelas de texto e padrões limitados: não resolve toda negação, coordenação, ironia ou ambiguidade da língua portuguesa. Uma menção positiva ou desejável pode ser contada mesmo quando não é um requisito obrigatório. A distinção entre obrigatório e desejável não recebe pesos diferentes.

O campo separado de bibliografia não é enviado à extração curricular. Se uma ementa ou objetivo contiver um cabeçalho de bibliografia ou referências reconhecido no início de linha, o trecho a partir desse cabeçalho é cortado. Essa proteção depende da segmentação e do formato do documento. Uma referência bibliográfica misturada ao texto sem cabeçalho reconhecível pode escapar à heurística; a revisão humana deve corrigi-la antes da análise.

Os estados das competências são definidos em relação ao conjunto de disciplinas:

| Estado | Evidência encontrada | Interpretação |
| --- | --- | --- |
| Coberta | Nome ou sinônimo da própria entrada em ementa/objetivos de pelo menos uma disciplina | Presença literal declarada; não prova domínio pedagógico |
| Parcial | Sem ocorrência literal da entrada, mas com ocorrência do conceito relacionado no PPC | Candidata por conceito; tecnologia não demonstrada explicitamente |
| Lacuna | Sem ocorrência literal nem âncora conceitual elegível no PPC | Ausência de evidência no texto e vocabulário analisados |

Uma entrada que representa um conceito também pode ter cobertura literal quando o próprio conceito ou um de seus sinônimos aparece no PPC. “Literal” designa o reconhecimento da entrada ou de alias declarado; não exige que apenas a grafia canônica apareça.

Por exemplo, uma vaga com Docker e uma ementa com “contêineres” pode gerar uma candidata parcial. Isso não prova ensino de Docker. Uma menção a Docker somente na bibliografia não produz cobertura curricular. As sugestões de termos desconhecidos também são apenas candidatas à curadoria: não integram competências, associações ou indicadores enquanto não forem reconhecidas pelo vocabulário utilizado.

## 4. Indicadores I1–I8

As fórmulas estão registradas em `server/engine.py`, em `FORMULAS`. São calculadas sobre o método lexical ativo e o vocabulário efetivamente selecionado. M3, A2 e decisões de revisão de associações não substituem silenciosamente essas definições.

Considere:

- `V`: conjunto de vagas do lote, com `N = |V|`.
- `C`: competências do escopo com pelo menos uma ocorrência em vaga.
- `J(c)`: conjunto de vagas com a competência `c`; `f(c) = |J(c)|`.
- `L(c)`: 1 quando a competência possui ocorrência literal elegível em alguma disciplina; 0 caso contrário.
- `P(c)`: 1 quando existe ocorrência literal ou uma âncora conceitual elegível em alguma disciplina; 0 caso contrário.
- `W = Σ f(c)`, somando as competências de `C`: total de presenças competência–vaga.

`W` pode ser maior que `N`, pois uma vaga pode mencionar várias competências. Cada tecnologia e cada conceito são entradas próprias; se ambos forem reconhecidos, ambos podem entrar na soma. O dicionário e a granularidade escolhidos, portanto, influenciam os pesos.

### I1 — Frequência relativa da competência

`I1(c) = 100 × f(c) / N`

Expressa o percentual de vagas distintas que mencionam a competência. Uma vaga com cinco ocorrências de Python contribui uma única vez para Python. A soma de I1 de competências diferentes pode ultrapassar 100%.

### I2 — Alinhamento literal ponderado pela demanda

`I2 = 100 × Σ[f(c) × L(c)] / W`

O peso é a frequência observada da competência no recorte. Uma competência literalmente presente no PPC recebe peso de cobertura 1; uma competência apenas parcial por conceito recebe **peso 0**. Uma lacuna também recebe peso 0. O indicador não pondera por carga horária, período, salário, nível da vaga ou julgamento subjetivo de importância.

### I3 — Lacunas prioritárias

`I3 = {c em C : L(c) = 0 e I1(c) ≥ limiar}`

É um conjunto, acompanhado de sua contagem, e não um percentual de cobertura. O limiar configurado é percentual e inclui a igualdade. Competências parciais são incluídas porque não possuem cobertura literal; são identificadas como parciais para distinguir uma âncora conceitual da ausência completa de evidência.

### I4 — Limite lexical com aproximação por conceito

`I4 = 100 × Σ[f(c) × P(c)] / W`

Aqui uma competência parcial por conceito recebe **peso 1**, assim como uma coberta literalmente. I4 é um limite exploratório de aproximação lexical, não um percentual validado de equivalência curricular. A diferença entre I4 e I2 mostra o peso da demanda para a qual apenas uma âncora conceitual foi encontrada. No mesmo corpus e escopo, I4 é maior ou igual a I2.

### I5 — Alinhamento por área de vaga

Para cada área `a`, calcula-se `f_a(c) = |J(c) ∩ V_a|` e `W_a = Σ f_a(c)`:

`I5(a) = 100 × Σ[f_a(c) × L(c)] / W_a`

O PPC permanece o mesmo; o conjunto de vagas muda por área. A resposta também oferece a aproximação conceitual por área, substituindo `L(c)` por `P(c)`. As contagens de vagas e de presenças competência–vaga devem acompanhar a leitura, pois áreas pequenas têm evidência limitada.

As áreas canônicas das vagas são **Programação, Análise, Dados, Suporte, Infraestrutura e Outra**. Um classificador heurístico normaliza aliases de áreas informadas e, quando a área está vazia, procura pistas primeiro no título e depois na descrição. Segurança é agrupada em Infraestrutura; qualidade/QA em Programação; gestão, produto e requisitos em Análise. Uma área explicitamente informada e desconhecida é classificada como Outra. Essa categorização precisa ser auditada no corpus; não é uma classificação ocupacional validada nem um resultado de LLM. Os grupos temáticos das entradas do dicionário têm outra finalidade e não devem ser confundidos com as áreas das vagas.

### I6 — Contribuição literal de cada disciplina

Para uma disciplina `d`, `L_d(c) = 1` quando a própria disciplina contém evidência literal da competência:

`I6(d) = 100 × Σ[f(c) × L_d(c)] / W`

O denominador é a demanda total do recorte, não a demanda exclusiva da disciplina. Uma competência pode estar em várias disciplinas; por isso, a soma das contribuições pode exceder I2 e 100%. Não se deve somar I6 como uma divisão exclusiva da carga curricular. Âncoras conceituais não entram nessa contribuição literal.

### I7 — Competências curriculares sem demanda observada

`I7 = {c do escopo : L(c) = 1 e f(c) = 0}`

Lista competências do vocabulário literalmente presentes no PPC e não encontradas nas vagas do lote. O resultado não implica conteúdo inútil, excesso curricular ou recomendação de exclusão: formação acadêmica tem objetivos que ultrapassam a demanda observada de um recorte de anúncios. Conteúdos fora do dicionário não são examinados por esse indicador.

### I8 — Coocorrência por Jaccard

`I8(A, B) = |J(A) ∩ J(B)| / |J(A) ∪ J(B)|`

Mede a semelhança entre os conjuntos de vagas que mencionam duas competências. O resultado varia de 0 a 1, sem multiplicação por 100. A matriz apresentada usa as seis competências mais frequentes e arredonda o índice a quatro casas decimais. Coocorrência não demonstra causalidade, dependência entre tecnologias ou necessidade de ensinar ambas na mesma disciplina.

### Ausência de dados e arredondamento

Percentuais são arredondados a duas casas decimais. Por convenção computacional, um denominador vazio retorna `0.0`; para Jaccard, uma união vazia também retorna zero. **Ausência de observações não significa alinhamento zero medido.** Deve ser reportada como “não calculável/sem dados”, junto da contagem que explica o denominador vazio. Sem vagas, a execução registra um aviso. Também pode não haver demanda reconhecida quando as vagas existem, mas nenhuma entrada do escopo foi encontrada. Nesses casos, I2, I4, I5 e I6 não sustentam uma conclusão de cobertura.

## 5. Associações A1 e julgamento opcional A2

**A1** gera candidatas por competência: cada vaga com a competência é combinada às disciplinas com presença literal da entrada ou do conceito relacionado. A candidata recebe `covers` para a presença literal ou `partial` para a âncora conceitual e preserva os dois trechos. O nome `covers` é uma classificação operacional lexical, não uma certificação pedagógica. `verified=True` significa que a evidência foi localizada no texto, não que um especialista ou modelo aprovou a relação.

A cobertura literal de uma competência em qualquer disciplina afeta I2; isso é diferente de analisar uma candidata específica a uma disciplina. Uma mesma competência pode ter cobertura literal em uma disciplina e candidata parcial em outra.

**A2** usa uma chamada real a um provedor compatível com a API OpenAI para julgar candidatas A1 por competência. O modelo deve responder `covers`, `partial` ou `does_not_cover`, uma justificativa e um trecho literal de cada fonte. O serviço valida o contrato JSON e exige que os trechos sejam substrings contínuas da descrição da vaga e do texto curricular elegível. Uma citação inventada, modificada ou restrita à bibliografia é descartada.

A2 examina o conjunto de candidatas produzido lexicalmente; não percorre todos os pares possíveis de vaga–disciplina e não descobre relações fora desse conjunto. Por isso, sua avaliação precisa informar a abrangência dos pares efetivamente julgados. Candidatas literais têm prioridade de execução. Para a avaliação binária de um par, uma decisão concluída `covers` ou `partial` torna o par relacionado. Um par só pode ser negativo quando todas as candidatas de competência desse par foram concluídas sem relação positiva. Pares incompletos não são transformados em negativos.

Essa redução binária para a validação de associação é diferente do peso parcial zero em I2 e peso parcial um em I4. Os indicadores continuam seguindo a extração lexical e suas fórmulas, sem substituir pesos por julgamentos A2.

## 6. M3 e condições da execução LLM

**M3** extrai competências em uma execução real do modelo, separada das predições M1 e M2. Recebe os mesmos textos elegíveis e a lista de nomes canônicos do vocabulário selecionado, para permitir uma comparação em um universo de competências conhecido. Não é extração aberta de todo conhecimento possível do modelo. É necessário explicitar que M1 possui um subconjunto de base menor ao comparar sua revocação com M2 ou M3.

O modelo é instruído a identificar apenas competências explícitas, ignorar negações e bibliografia e copiar uma evidência contínua. O serviço verifica a presença do trecho no texto e a pertença do nome ao escopo. Essa verificação confirma a origem textual da citação; não comprova que a interpretação semântica está correta. Um trecho real ainda pode ser irrelevante, negado ou interpretado incorretamente pelo modelo. A avaliação humana continua necessária.

M3 e A2 exigem `TCC_LLM_API_KEY` ou `OPENAI_API_KEY`; o modelo e o provedor podem ser definidos por `TCC_LLM_MODEL` e `TCC_LLM_BASE_URL`. Sem configuração utilizável, os métodos ficam indisponíveis e nenhuma resposta é simulada. Credenciais não fazem parte dos relatórios ou das instruções de anotação. Uma configuração disponível não comprova que a execução ocorreu: os resultados e os estados devem ser consultados.

O cliente usa temperatura zero, JSON Schema, tempo limite, TLS verificado e limite de chamadas por lote. Retentativas também consomem o orçamento. Três falhas consecutivas ou o esgotamento do orçamento interrompem o restante da execução; cancelamentos também podem deixar pendências. O limite atual do payload por chamada é 60.000 caracteres serializados, sem divisão automática de documentos maiores. Documentos com falha ou pendentes não entram como documentos negativos na validação M3.

Respostas concluídas são armazenadas em cache por hash de entrada, provedor, modelo, método, versão do prompt e temperatura. Citações de respostas recuperadas são verificadas novamente. Um acerto de cache não consome chamada de rede. Temperatura zero e cache ajudam a estabilizar uma execução, mas não garantem que o mesmo provedor produza o mesmo resultado em outro momento.

Os documentos enviados ao modelo são tratados como dados não confiáveis. Instruções eventualmente presentes no PPC ou em vagas não são instruções do usuário da plataforma. A operação LLM envia os textos elegíveis ao provedor configurado; a seleção desse provedor e a adequação do envio ao estudo são responsabilidade do operador.

## 7. Protocolo de validação humana e amostra cega

A validação só deve ser chamada de cega se os anotadores não tiverem consultado as predições. A seleção independente de predições e um arquivo sem colunas de resposta dos métodos não garantem, sozinhos, o cegamento. O protocolo recomendado é:

1. Separar um corpus de desenvolvimento para ajustar segmentação, sinônimos, contextos e regras. Não usar os rótulos da avaliação final para ajustar o método que será avaliado nela.
2. Criar o lote de avaliação, concluir a coleta e revisar a segmentação do PPC sem consultar resultados de extração ou associações.
3. Exportar a amostra cega antes de confirmar a execução do lote e antes de consultar o painel ou efetuar nova curadoria. Finalizar as fontes revisadas antes de gerar a amostra; não alterar posteriormente seus textos ou identificadores.
4. Solicitar a anotação primária e, quando disponível, uma segunda anotação independente. Os anotadores devem usar os textos fornecidos e critérios registrados, sem consultar as saídas M1–M3 ou A1–A2.
5. Executar os métodos no lote congelado, importar os arquivos anotados e comparar apenas unidades com rótulo humano explícito no suporte comum dos métodos. A aplicação restringe automaticamente a comparação aos documentos ou pares efetivamente processados pelos métodos comparados.
6. Examinar falsos positivos e falsos negativos. Qualquer correção posterior pertence a um novo ciclo de desenvolvimento e a um novo lote; não constitui melhora validada sobre a mesma amostra de teste.

A exportação prévia está disponível por `GET /api/batches/{id}/sample` enquanto o lote está em revisão, após a coleta terminar e desde que exista ao menos uma vaga. Isso permite obter a planilha antes da confirmação mesmo quando a entrada de validação da interface for usada após o painel. Editar disciplinas depois de baixar a planilha invalida a amostra armazenada e exige uma nova exportação. O endpoint também admite lotes concluídos, mas uma exportação posterior não torna cega uma anotação de quem já consultou os resultados.

A amostragem em `server/reporting.py` usa uma semente derivada do identificador do lote e não consulta as predições. Seleciona até 12 vagas por área e limita o agregado a 60 vagas. Todas as disciplinas entram na amostra de extração. O texto de cada vaga inclui título e descrição, alinhado à entrada dos extratores; o texto curricular inclui ementa e objetivos. Para cada documento selecionado, inclui uma linha para cada competência do dicionário congelado, permitindo anotar presenças e ausências. A amostra de associações sorteia até 100 pares vaga–disciplina do produto cartesiano entre vagas selecionadas e disciplinas. A disponibilidade dos estratos e o limite agregado afetam a composição; a amostra não constitui uma estimativa probabilística representativa de todo o mercado.

Na folha `extraction`, `present=1` indica competência explícita no texto e `present=0` indica ausência. Na folha `associations`, `related=1` indica que a disciplina cobre competências exigidas pela vaga e `related=0` indica ausência dessa relação, conforme o protocolo do estudo. A unidade binária de associação é o par, não cada competência isolada. Os pesquisadores devem definir previamente como tratar cobertura parcial, registrar exemplos e treinar anotadores no conjunto de desenvolvimento. A redução implementada das predições trata candidatas parciais como positivas para essa avaliação binária; se o estudo adotar critério diferente, precisa de uma avaliação própria claramente descrita.

Células em branco não significam zero: ficam fora da avaliação. Os arquivos devem preservar os nomes das folhas, cabeçalhos e IDs da amostra exportada. A importação recusa IDs fora da amostra, unidades duplicadas e rótulos inválidos. A aplicação aceita uma anotação primária e uma secundária; importar novamente para o mesmo papel substitui o respectivo registro. É recomendável arquivar os arquivos originais e o protocolo fora dessa substituição operacional.

### Precisão, revocação e F1

As métricas são calculadas contra os rótulos efetivamente importados da anotação **primária**, separadamente por método e, na extração, por fonte `jobs` ou `ppc`:

- Verdadeiro positivo (`TP`): presença/relação anotada e predita.
- Falso positivo (`FP`): presença/relação predita e ausência anotada.
- Falso negativo (`FN`): presença/relação anotada e não predita.
- Verdadeiro negativo (`TN`): ausência anotada e não predita.
- `Precisão = TP / (TP + FP)`.
- `Revocação = TP / (TP + FN)`.
- `F1 = 2 × Precisão × Revocação / (Precisão + Revocação)`.

O código usa zero quando um desses denominadores é vazio. Uma métrica com denominador vazio deve ser interpretada junto das contagens, sem inferir erro ou sucesso empírico. Sem anotação primária, as métricas permanecem pendentes; a aplicação não preenche valores demonstrativos nem transforma sugestões de método em rótulos humanos.

Na extração, a aplicação calcula automaticamente a interseção dos documentos processados pelos métodos comparados, separadamente por fonte. M1 e M2 processam todos os documentos, inclusive aqueles sem ocorrência positiva. Quando M3 conclui documentos de uma fonte, M1, M2 e M3 são avaliados sobre os mesmos documentos concluídos e os mesmos rótulos humanos desse recorte. Se M3 não concluiu nenhum documento daquela fonte, não recebe métrica nem restringe os demais métodos executados. Uma competência fora do subconjunto M1 pode ser um falso negativo no universo anotado mais amplo; esse efeito do vocabulário precisa acompanhar a comparação.

Na associação, a presença de resultados A2 restringe tanto A1 quanto A2 aos mesmos pares anotados efetivamente julgados por A2, incluindo pares julgados negativos. Falhas, orçamento esgotado, citações descartadas e pendências ficam fora do suporte comum; não se tornam negativos automáticos. Esse recorte contém apenas candidatos lexicais julgados e não representa todos os pares sorteados ou o produto cartesiano vaga–disciplina. Sem resultados válidos de A2, somente os métodos com predições disponíveis recebem métricas.

O resultado informa o recorte por `validation.scope_note` e `validation.supports`; as linhas de métricas apresentam a quantidade de itens, os documentos na extração e uma descrição do suporte. Mesmo com suporte comum automático, uma execução LLM parcial reduz a abrangência da comparação e pode selecionar candidatos mais fáceis, porque a execução é ordenada. Reporte os itens excluídos e as falhas. Concluir a execução amplia a amostra avaliada, mas não elimina o viés do conjunto de candidatas A2.

Os alvos exibidos são F1 de 0,80 para extração em vagas, F1 de 0,75 para extração no PPC e precisão de 0,70 para associação. São referências de aceitação, não resultados alcançados, intervalos de confiança ou evidências de validade do instrumento.

### Concordância entre anotadores

Quando há duas anotações, a concordância utiliza somente as unidades com rótulo de ambos. As chaves distinguem competência × documento × fonte e par vaga–disciplina. O cálculo combina essas unidades em uma medida global; não calcula automaticamente um kappa separado para cada fonte ou tarefa.

Se `p_o` é a proporção de acordo observado e `p_e` o acordo esperado pelas proporções marginais de rótulos positivos de cada anotador:

`p_e = p_1 × p_2 + (1 − p_1) × (1 − p_2)`

`κ = (p_o − p_e) / (1 − p_e)`

Sem unidades em comum, não há resultado de concordância. Quando `p_e = 1`, o denominador é zero e o kappa é indefinido (`null`), mesmo com acordo observado perfeito. A aplicação informa esse caso degenerado, sem fabricar um kappa igual a 1. A anotação secundária serve à concordância; não é automaticamente agregada à primária para as métricas, e o sistema não executa adjudicação de divergências.

## 8. Rastreabilidade, fingerprint e reprodução do estudo

Cada lote preserva fontes estruturadas, configuração, edições de dicionário congeladas, resultados, estados da execução e evidências. As exportações permitem examinar indicadores, lacunas, disciplinas, vagas, associações e validação. Os registros devem ser mantidos junto da procedência do corpus e do protocolo de anotação.

O `fingerprint` dos resultados é um SHA-256 da serialização de disciplinas, vagas, configuração e dicionário completo daquela análise. Chaves de objetos são ordenadas; a ordem das listas continua fazendo parte da entrada. Ele é explicitamente um **hash de entrada** (`fingerprint_kind="input"`). Não incorpora por si só o commit do código, todas as dependências, a configuração LLM recebida por variáveis de ambiente, a versão do provedor, as respostas ou as anotações. Não é um identificador completo de experimento e não demonstra reprodutibilidade empírica.

A amostra também recebe uma identificação curta baseada em suas unidades. Essa identificação auxilia a conferência dos IDs e não substitui o corpus, os textos, o protocolo ou os arquivos anotados.

Para permitir a reprodução de um estudo, arquive o commit e as versões de dependências, os arquivos de entrada com procedência e datas de obtenção, a configuração e o vocabulário, as revisões do PPC, a amostra e os rótulos originais, as regras de anotação, o provedor/modelo e versão do prompt quando aplicável, além de resultados validados, falhas, pendências, chamadas e uso de cache. Não arquive credenciais nos materiais de pesquisa. Repetir a coleta em outra data ou usar o mesmo nome de modelo não garante entradas ou saídas idênticas.

## 9. Demonstração e alcance das conclusões

`server/demo.py` contém 12 disciplinas e 30 vagas **inteiramente sintéticas**, com empresas fictícias, endereços em `example.invalid` e um PPC demonstrativo que não representa documento institucional real. O cenário usa BSI/IFC Camboriú, recorte de Itajaí/SC e raio de 40 km apenas como referência ilustrativa; distribui as vagas fictícias entre Itajaí, Balneário Camboriú, Navegantes, Camboriú e Itapema. Os resultados são calculados a partir desse corpus sintético; não são métricas fabricadas de validação nem uma pesquisa do mercado regional. Nenhuma conclusão empírica do TCC deve usar esses dados como se fossem coletados.

A demonstração inclui presença literal, aproximações conceituais e termos restritos à bibliografia para explorar o comportamento das regras. Não representa um conjunto de teste independente, um padrão-ouro anotado ou uma demonstração de desempenho M3/A2.

O estudo real precisa delimitar o universo de vagas, período de coleta, critérios de inclusão e deduplicação, qualidade da segmentação, vocabulário, filtros e participação de especialistas. O método lexical não observa competências implícitas, conteúdo ministrado fora do PPC, aprendizagem dos estudantes nem resultados de contratação. Relatórios devem distinguir ausência textual, candidata conceitual, julgamento LLM e decisão humana, junto de seus denominadores e limites.
