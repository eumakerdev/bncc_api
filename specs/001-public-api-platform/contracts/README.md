# API Contracts — BNCC API v1

A **fonte da verdade** do contrato é o OpenAPI gerado automaticamente pelo FastAPI em
`/api/v1/openapi.json` (Constituição, Princípio I; FR-013). Os arquivos aqui descrevem, em linguagem
de contrato, o comportamento esperado de cada grupo de endpoints para guiar implementação e **testes
de contrato** (Princípio III). Divergências entre estes documentos e o OpenAPI gerado são resolvidas
em favor de schemas Pydantic tipados — o código é a fonte, estes docs são a especificação de aceite.

## Convenções gerais

- **Base path**: `/api/v1` (versionado — FR-025). Mudanças incompatíveis criam `/api/v2`.
- **Autenticação da API de dados**: `Authorization: Bearer <api_key>` (FR-009). Sem key válida → `401`.
- **Autenticação do portal**: sessão JWT (cookie httpOnly ou header) após login com e-mail+senha verificado.
- **Rate limiting** (FR-010/010a): cota determinística (60/min) e cota de IA (~20/min + teto diário),
  separadas. Excedido → `429` com header `Retry-After` e corpo indicando o reset.
- **Erros** (FR-024): corpo `ErrorResponse { detail, error_code?, timestamp? }`; nunca stack trace,
  paths internos ou detalhes de infra. Status usados: `400` (validação), `401` (auth), `404` (não
  encontrado), `429` (limite), `503` (dependência indisponível — ex.: IA/health).
- **Paginação**: `PaginatedResponse { items, total, page, size, pages }`.
- **Idioma**: conteúdo em pt-BR (coerente com a BNCC).

## Grupos de contrato

| Arquivo | Grupo | Prioridade | Auth |
|---------|-------|-----------|------|
| [bncc-data.md](./bncc-data.md) | Habilidades, competências, taxonomia | P1 | API key |
| [auth-portal.md](./auth-portal.md) | Cadastro, verificação de e-mail, login | P2 | Sessão portal |
| [api-keys-usage.md](./api-keys-usage.md) | Gerência de keys e métricas de uso | P2 | Sessão portal |
| [semantic-search.md](./semantic-search.md) | Busca semântica com IA | P4 | API key (cota IA) |

Documentação interativa (P3) e landing page (P5) não expõem contratos REST próprios além do OpenAPI
gerado: a página de docs consome `/api/v1/openapi.json`; a landing é HTML server-rendered com metadados
de SEO (`/`, `/sitemap.xml`, `/robots.txt`).
