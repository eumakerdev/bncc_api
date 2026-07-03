# Contract: Dados da BNCC (P1)

Endpoints determinísticos, somente leitura sobre o snapshot versionado. **Auth**: API key (Bearer).
**Cota**: determinística (60/min). Todos retornam dados **oficiais** (nenhum campo derivado/IA).

## GET /api/v1/habilidades/{codigo}
Retorna uma habilidade pelo código oficial (EI/EF/EM).
- **200** → `Habilidade` (código, descrição, etapa, anos, área, componente, competências gerais/
  específicas, objetos de conhecimento, campo de experiência se EI).
- **400** → código malformado (não casa com os padrões EI/EF/EM).
- **404** → código válido mas inexistente.
- **Aceite** (US1/AS1): `EF05MA07`, `EM13MAT101`, `EI03EO01` retornam descrição oficial + metadados.

## GET /api/v1/habilidades
Lista paginada com filtros. **Query**: `etapa`, `ano`, `area_conhecimento`, `componente`,
`competencia_geral` (1–10), `page` (≥1), `size` (1–100).
- **200** → `PaginatedResponse<Habilidade>`.
- **Aceite** (US1/AS2): `?etapa=ensino_medio&componente=...` retorna todas as correspondentes,
  paginadas.

## GET /api/v1/habilidades/{codigo}/relacoes
Relações navegáveis de uma habilidade (FR-005).
- **200** → competências gerais/específicas referenciadas + objetos de conhecimento + unidade temática.
- **404** → habilidade inexistente.
- **Aceite** (US1/AS3): permite navegar da habilidade às competências referenciadas.

## GET /api/v1/competencias/gerais  •  GET /api/v1/competencias/gerais/{numero}
As 10 competências gerais.
- **200** → lista ordenada por `numero` / uma competência. **404** para `numero` fora de 1–10.

## GET /api/v1/competencias/especificas
Filtros: `area`, `componente`, `etapa`.
- **200** → lista de `CompetenciaEspecifica` (EI/EF/EM). 

## GET /api/v1/taxonomia (novo)
Exposição da estrutura navegável: etapas → áreas → componentes → unidades temáticas → objetos de
conhecimento; campos de experiência (EI). Suporta a documentação e a navegação (FR-005).
- **200** → árvore da taxonomia oficial.

## GET /api/v1/sistema/versao-dados (novo)
Metadados do snapshot: `versao`, `data_publicacao`, `checksum_fontes`, `contagens` por etapa/
componente (FR-025, rastreabilidade; SC-001).
- **200** → objeto de metadados do snapshot.

## Erros comuns
`401` sem key válida (FR-009); `429` acima de 60/min (burst de até 10) com `Retry-After` (FR-010,
edge case de paginação preserva estado já retornado); `400` com mensagem clara e sem vazar internos
(US1/AS4, FR-024).

## Cobertura de teste de contrato (Princípio III)
- Código válido de cada etapa → 200 com schema correto.
- Código malformado → 400; inexistente → 404.
- Filtro por etapa/componente → paginação correta (`total`, `pages`).
- Relações resolvem para entidades existentes.
- Sem key → 401; acima do limite → 429 com `Retry-After`.
