# Revisão, anotação cega e evidências

Durante a **Revisão do PPC**, confira as disciplinas e salve as correções. A divisão oferece uma prévia editável; a junção reúne os campos e preserva os textos. **Desfazer** recupera versões locais. A bibliografia permanece fora da cobertura. Lotes encerrados ficam somente para consulta.

Quando a coleta terminar e houver vagas, use **Baixar amostra cega** antes de confirmar o processamento. O botão salva primeiro as alterações pendentes e baixa o XLSX de `GET /api/batches/{id}/sample`. Anote os rótulos humanos sem consultar o painel ou as associações preditas. Posteriormente, importe a planilha em **Validação e exportação**.

Qualquer edição salva na revisão invalida a amostra congelada no servidor. Se o PPC mudar depois de um download, a tela orienta baixar uma nova amostra; descarte a versão anterior e anote a atual. Confirmar uma revisão já salva não repete o `PATCH`, preservando a amostra recém-baixada. O aviso específico de alteração é local à permanência nesta tela; ao reabrir, permanece a orientação geral de renovar a amostra após mudanças.

Em **Evidências**, cada trecho é conferido contra o título/descrição da vaga ou os campos da disciplina. Menções em referências aparecem separadas e não aumentam a cobertura. Candidatas por conceito indicam explicitamente a ausência de menção literal da tecnologia. A1 é uma associação lexical; A2 só aparece como julgamento do modelo quando há execução real registrada. Aceitar ou rejeitar registra a avaliação humana; as alterações do dicionário valem para o próximo lote.

Para conferir o fluxo de download, salvamento e renovação pela interface, com a API e o Vite iniciados:

```sh
npx playwright test e2e/review-blind-sample.spec.ts
```
