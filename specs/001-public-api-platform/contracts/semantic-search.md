# Contract: Busca Semântica com IA (P4)

Camada aumentada por IA. **Auth**: API key (Bearer). **Cota separada**: ~20 req/min + teto diário
(FR-010a), medida no bucket `ai`. Sempre cita fontes oficiais; degrada graciosamente (Princípio VII).

## POST /api/v1/busca-semantica
Responde pergunta em linguagem natural com texto gerado + fontes oficiais rastreáveis.
- **Body**: `BuscaSemanticaRequest { query (3–500 chars), max_resultados (1–20), incluir_contexto }`.
  Entrada validada e **sanitizada** (tamanho/tipo/conteúdo; anti-injeção — FR-019, edge cases).
- **200** → `BuscaSemanticaResponse { resposta, fontes: [DocumentoFonte{codigo,tipo,relevancia}],
  documentos_consultados, tempo_processamento }`. Conteúdo gerado é **claramente distinguível** dos
  dados oficiais (FR-016, US4/AS4).
- **200 (sem correspondência confiável)** → resposta indica **ausência de resultados confiáveis** em
  vez de inventar (FR-017; US4/AS3). Fontes abaixo do limiar de similaridade não aparecem como
  oficiais.
- **400** → query vazia/curta/longa demais ou payload inválido (edge case).
- **429** → acima da cota de IA (~20/min ou teto diário) com `Retry-After`.
- **503** → camada de IA (LLM/embeddings) indisponível — erro **acionável**, não 500 opaco (FR-018,
  Princípio VI). **Não afeta** os endpoints determinísticos (US4/AS2; SC-009).

## Garantias (Princípios IV, VI, VII)
- **Rastreabilidade**: 100% das respostas que citam habilidades trazem `codigo` + `relevancia`
  (SC-006). Nenhum conteúdo gerado é apresentado como dado oficial.
- **Limites de custo**: timeout e teto de tokens explícitos por chamada de LLM (FR-019).
- **Degradação graciosa**: falha de IA isolada ao bucket `ai`; determinístico permanece 100%.

## Cobertura de teste de contrato
- query válida → 200 com `fontes` rastreáveis; conteúdo gerado marcado como não-oficial.
- query sem match relevante → resposta de "sem resultados confiáveis" (não inventa).
- query vazia/curta/longa/injeção → 400 (sanitizada).
- acima da cota IA → 429 (bucket `ai`, independente do determinístico).
- IA fora do ar → 503 no endpoint de IA **e** endpoints determinísticos seguem 200 (SC-009).
