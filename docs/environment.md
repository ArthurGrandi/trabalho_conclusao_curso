# Ambiente cloud

O setup foi executado com `bash scripts/setup.sh`; a compilação foi servida e testada com `bash scripts/start.sh`. O modo de desenvolvimento também foi iniciado com portas alternativas e verificado por requisição à API através do Vite. O encerramento envia sinal somente aos grupos de processos criados pelo script.

O rascunho de configuração do ambiente recebeu:

- `install_script`: executar `bash scripts/setup.sh` em `/workspace/trabalho_conclusao_curso`.
- `start_skill`: diretório, reaproveitamento do checkout isolado, inicialização, verificações, dados persistentes e limitações das integrações.
- Destinos de rede adicionais: `apis.indeed.com`, `www.linkedin.com`, `www.glassdoor.com.br`, `www.google.com` e `api.openai.com`. Os destinos predefinidos de gerenciadores de pacotes foram preservados.

Salvar o rascunho não aplica as permissões à instância atual nem publica o ambiente. Para reutilizá-lo, revise e salve em Configurações do ambiente e publique pelo produto.

Nenhum segredo foi adicionado ao rascunho. LLM é opcional e requer credencial configurada com segurança no ambiente do servidor. Coleta externa e chamadas LLM reais permanecem sem validação contra serviços externos; os testes usam respostas simuladas. PDF, CSV, revisão, análise lexical, evidências, anotações e exportações foram verificados funcionalmente sem essas credenciais.
