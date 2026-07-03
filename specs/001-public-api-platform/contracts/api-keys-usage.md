# Contract: API Keys & Uso (P2)

Gerência de API keys e métricas de consumo. **Auth**: sessão do portal (dev verificado). Exige
`email_verified = true` (FR-007) — caso contrário `403`.

## POST /api/v1/keys
Gera nova API key para a conta autenticada.
- **Body**: `{ name }`.
- **201** → `{ id, name, prefix, key }` — **`key` completa exibida uma única vez**; depois só `prefix`.
- **403** → e-mail não verificado.
- **Aceite** (US2/AS1): dev verificado gera key; a key autentica chamadas subsequentes.

## GET /api/v1/keys
Lista as keys da conta (sem o segredo).
- **200** → `[{ id, name, prefix, status, created_at, last_used_at }]`.

## DELETE /api/v1/keys/{id}
Revoga uma key (`status = revoked`).
- **204** → revogada. Chamadas subsequentes com essa key → `401` imediato (FR-009; edge case
  "key revogada durante uso ativo").
- **404** → key inexistente ou de outra conta.

## GET /api/v1/keys/{id}/usage
Métricas de consumo por key (FR-011).
- **200** → uso recente por bucket: `{ deterministic: {...}, ai: {...} }` com contagens e limites
  atuais (60/min + burst 10 determinístico; 20/min + teto de 500/dia de IA).
- **Aceite** (US2/AS5): painel mostra consumo recente e limites de cada key.

## GET /api/v1/usage (agregado da conta)
- **200** → resumo consolidado do consumo de todas as keys da conta.

## Comportamento de autenticação e limite (na API de dados)
Estes não são endpoints deste grupo, mas o contrato de key define:
- Requisição com key válida → autenticada e **contabilizada** no bucket correto (US2/AS2).
- Key inválida/revogada/ausente → **401** com mensagem acionável (US2/AS3).
- Acima do limite da janela → **429** com `Retry-After` e indicação de reset (US2/AS4; FR-010/010a).

## Segurança
- `key_hash` (SHA-256) no banco; segredo nunca persistido/logado em claro.
- Lookup por `prefix` indexado; comparação por hash.
- Autorização por posse: um dev só vê/gerencia **suas** keys.

## Cobertura de teste de contrato
- criar key (verificado) → 201 com `key` uma vez; (não verificado) → 403.
- listar → nunca expõe segredo.
- revogar → 204; uso posterior da key → 401.
- usage reflete contagem por bucket e limites; excedente → 429 com reset.
