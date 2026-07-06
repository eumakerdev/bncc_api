# Relatório de Teste em Produção — BNCC API

**Data do teste:** 06/07/2026
**Ambiente:** Produção — Google Cloud Run (`https://bncc-api-esjlky3g3a-rj.a.run.app`)
**Versão da API:** 1.1.0 · **Snapshot de dados:** v1 (publicado em 06/07/2026)
**Resultado geral:** ✅ **35 de 35 chamadas se comportaram exatamente como esperado** — 27 casos de sucesso e 8 casos de segurança/erro respondendo corretamente. **Todos os 21 endpoints da API foram exercitados.**

---

## O que é este relatório?

Este documento é um *show case* completo da BNCC API rodando em produção. Ele percorre a jornada
inteira de um desenvolvedor real: criar uma conta, confirmar o e-mail, gerar uma chave de acesso
(API key), consultar os dados oficiais da BNCC de todas as formas possíveis, usar a busca com
inteligência artificial, acompanhar o próprio consumo e, por fim, revogar a chave. Cada exemplo
mostra a chamada feita e um trecho real da resposta.

> **O que é a BNCC API?** Uma API pública que expõe toda a Base Nacional Comum Curricular do
> Brasil — as 1.716 habilidades das três etapas (Educação Infantil, Ensino Fundamental e Ensino
> Médio), as 10 competências gerais, as competências específicas e a taxonomia oficial — além de
> uma busca semântica com IA que responde perguntas em linguagem natural citando as fontes oficiais.

---

## Parte 1 — A jornada self-service (criar conta e chave)

Antes de consultar dados, todo desenvolvedor passa por este fluxo. Foi executado de ponta a ponta
em produção, sem nenhuma intervenção manual no banco:

### Exemplo 1 · Criar a conta

```http
POST /api/v1/auth/signup
{"email": "showcase-teste@expertia.dev.br", "password": "••••••••••"}
```
```json
HTTP 201
{"account_id": "41f820a5-…", "email": "showcase-teste@expertia.dev.br", "email_verified": false}
```
A senha exige no mínimo 10 caracteres com letras e números. A conta nasce **não verificada** — os
dados da BNCC só ficam acessíveis depois de confirmar o e-mail.

### Exemplo 2 · Confirmar o e-mail

O e-mail de verificação chegou com um link contendo o token (em produção o backend de e-mail está
em modo console; o link foi recuperado dos logs do Cloud Run via `gcloud logging read`):

```http
POST /api/v1/auth/verify-email
{"token": "ln8_cByjnQQ7Zf49…"}
```
```json
HTTP 200
{"email_verified": true}
```

### Exemplo 3 · Fazer login no portal

```http
POST /api/v1/auth/login
{"email": "showcase-teste@expertia.dev.br", "password": "••••••••••"}
```
```json
HTTP 200
{"access_token": "eyJhbGciOi…", "token_type": "bearer", "expires_in_minutes": 60}
```
O login devolve um **JWT de sessão do portal**, válido por 60 minutos. Importante: esse token serve
apenas para gerenciar a conta (chaves, uso) — ele **não** dá acesso aos dados da BNCC (ver Exemplo 32).

### Exemplo 4 · Criar uma API key

```http
POST /api/v1/keys          (Authorization: Bearer <JWT da sessão>)
{"name": "showcase-2026-07-06"}
```
```json
HTTP 201
{"id": "15cf0f9c-…", "name": "showcase-2026-07-06", "prefix": "bncc_live_7lD_je3j", "key": "bncc_live_7lD_je3j…"}
```
O segredo completo da chave (53 caracteres, prefixo `bncc_live_`) é exibido **uma única vez**, nesta
resposta. Nas listagens seguintes só aparece o prefixo — a chave é armazenada com hash no servidor.

---

## Parte 2 — Saúde do sistema

### Exemplo 5 · Liveness (público, sem autenticação)

```http
GET /api/v1/sistema/health → HTTP 200 (79 ms)
```

### Exemplo 6 · Readiness (público)

```http
GET /api/v1/sistema/readiness → HTTP 200 (79 ms)
```
```json
{"status": "ready", "components": {"database": "ok", "bncc_snapshot": "ok", "ai": "available"}}
```
Os três componentes críticos estavam saudáveis: banco de dados (Cloud SQL Postgres), o snapshot
oficial da BNCC e a camada de IA (embeddings + LLM).

### Exemplo 7 · Versão e integridade dos dados

```http
GET /api/v1/sistema/versao-dados → HTTP 200 (101 ms)
```
```json
{
  "versao": "v1",
  "data_publicacao": "2026-07-06",
  "checksum_fontes": {
    "educacao_infantil": "7d0004aa…", "ensino_fundamental": "81cd44ba…",
    "ensino_medio": "0428abc3…", "computacao": "60aab0b1…"
  },
  "contagens": {
    "por_etapa": {"educacao_infantil": 104, "ensino_fundamental": 1407, "ensino_medio": 205},
    "computacao": {"total": 140, "por_etapa": {"educacao_infantil": 11, "ensino_fundamental": 103, "ensino_medio": 26}}
  }
}
```
Este endpoint materializa o princípio de **fidelidade e reprodutibilidade**: cada fonte oficial tem
checksum SHA-256, e as contagens permitem auditar a cobertura (104 + 1.407 + 205 = **1.716
habilidades**, incluindo as 140 do Complemento de Computação).

---

## Parte 3 — Habilidades (o coração da API)

Todos os exemplos abaixo usam `Authorization: Bearer <API key>`.

### Exemplo 8 · Listar tudo, com paginação padrão

```http
GET /api/v1/habilidades → HTTP 200 (119 ms)
```
```json
{"total": 1716, "page": 1, "size": 20, "pages": 86, "items": [{"codigo": "EF01CI01", "descricao": "Comparar características de diferentes materiais…", …}]}
```
Paginação clara: `total`, `page`, `size` (1–100) e `pages`.

### Exemplo 9 · Filtrar por etapa — Educação Infantil

```http
GET /api/v1/habilidades?etapa=educacao_infantil&size=3 → HTTP 200 (90 ms) · total: 104
```
As 104 habilidades (objetivos de aprendizagem) da EI, cada uma com seu **campo de experiência**
(ex.: "O eu, o outro e o nós") em vez de componente curricular — fiel à estrutura do documento oficial.

### Exemplo 10 · Combinar filtros — Matemática do 5º ano do EF

```http
GET /api/v1/habilidades?etapa=ensino_fundamental&componente=matematica&ano=5 → HTTP 200 (80 ms) · total: 25
```

### Exemplo 11 · Filtrar por área de conhecimento — Ciências da Natureza no EM

```http
GET /api/v1/habilidades?etapa=ensino_medio&area_conhecimento=ciencias_natureza → HTTP 200 (89 ms) · total: 23
```

### Exemplo 12 · Complemento de Computação

```http
GET /api/v1/habilidades?componente=computacao → HTTP 200 (80 ms) · total: 140
```
As 140 habilidades do Parecer CNE/CP 02/2022 (Computação na Educação Básica), integradas ao mesmo
modelo de dados.

### Exemplo 13 · Computação filtrada por eixo

```http
GET /api/v1/habilidades?componente=computacao&eixo=pensamento_computacional → HTTP 200 (80 ms) · total: 50
```
Os três eixos oficiais funcionam como filtro: `pensamento_computacional`, `mundo_digital` e
`cultura_digital`.

### Exemplo 14 · Paginação explícita

```http
GET /api/v1/habilidades?page=3&size=5 → HTTP 200 (90 ms)
```
```json
itens: EF01CO05, EF01CO06, EF01CO07, EF01ER01, EF01ER02
```
Ordenação estável por código — a mesma página sempre devolve os mesmos itens.

### Exemplo 15 · Detalhe por código — Ensino Fundamental

```http
GET /api/v1/habilidades/EF05MA03 → HTTP 200 (90 ms)
```
```json
{
  "codigo": "EF05MA03",
  "descricao": "Identificar e representar frações (menores e maiores que a unidade), associando-as ao resultado de uma divisão ou à ideia de parte de um todo, utilizando a reta numérica como recurso.",
  "etapa": "ensino_fundamental", "anos": ["5"],
  "area_conhecimento": "matematica", "componente": "matematica",
  "unidade_tematica": "Números",
  "objetos_conhecimento": ["sua representação na reta numérica Representação fracionária dos números"]
}
```

### Exemplo 16 · Detalhe por código — Educação Infantil

```http
GET /api/v1/habilidades/EI03EO01 → HTTP 200 (80 ms)
```
```json
{
  "codigo": "EI03EO01",
  "descricao": "Demonstrar empatia pelos outros, percebendo que as pessoas têm diferentes sentimentos, necessidades e maneiras de pensar e agir.",
  "etapa": "educacao_infantil", "anos": ["03"],
  "campo_experiencia": "O eu, o outro e o nós"
}
```
Repare que a EI usa `campo_experiencia` e o grupo etário como "ano" — o modelo respeita as
diferenças estruturais entre as etapas.

### Exemplo 17 · Detalhe por código — Ensino Médio

```http
GET /api/v1/habilidades/EM13MAT101 → HTTP 200 (80 ms)
```
```json
{
  "codigo": "EM13MAT101",
  "descricao": "Interpretar situações econômicas, sociais e das Ciências da Natureza que envolvem a variação de duas grandezas…",
  "etapa": "ensino_medio", "anos": ["1", "2", "3"],
  "competencias_especificas": ["EMMAT01"]
}
```
No EM, a habilidade já vem **vinculada à competência específica** (EMMAT01) — dá para navegar do
código da habilidade até a competência que ela desenvolve.

### Exemplo 18 · Detalhe por código — Computação

```http
GET /api/v1/habilidades/EF05CO01 → HTTP 200 (72 ms)
```
```json
{"codigo": "EF05CO01", "descricao": "Reconhecer objetos do mundo real e/ou digital que podem ser representados através de listas…", "area_conhecimento": "computacao"}
```

### Exemplo 19 · Relações navegáveis de uma habilidade

```http
GET /api/v1/habilidades/EF05MA03/relacoes → HTTP 200 (93 ms)
```
```json
{"codigo": "EF05MA03", "unidades_tematicas": ["Números"], "objetos_conhecimento": ["sua representação na reta numérica Representação fracionária dos números"], "competencias_gerais": [], "competencias_especificas": []}
```
Devolve só os vínculos da habilidade — útil para montar grafos de navegação sem carregar o objeto
completo.

---

## Parte 4 — Competências e taxonomia

### Exemplo 20 · As 10 competências gerais

```http
GET /api/v1/competencias/gerais → HTTP 200 (76 ms)
```
Lista com as 10 competências gerais da Educação Básica, cada uma com número, título e texto integral.

### Exemplo 21 · Competência geral por número

```http
GET /api/v1/competencias/gerais/5 → HTTP 200 (70 ms)
```
```json
{"numero": 5, "titulo": "Cultura digital", "descricao": "Compreender, utilizar e criar tecnologias digitais de informação e comunicação de forma crítica, significativa, reflexiva e ética…"}
```

### Exemplo 22 · Competências específicas com filtros

```http
GET /api/v1/competencias/especificas?area=matematica&etapa=ensino_medio → HTTP 200 (79 ms)
```
```json
[{"codigo": "EMMAT01", "numero": 1, "descricao": "Utilizar estratégias, conceitos e procedimentos matemáticos para interpretar situações em diversos contextos…"}, … (5 itens)]
```
As 5 competências específicas de Matemática no EM — exatamente as citadas nos campos
`competencias_especificas` das habilidades (ver Exemplo 17).

### Exemplo 23 · Árvore da taxonomia oficial

```http
GET /api/v1/taxonomia → HTTP 200 (179 ms) · ~81 KB
```
```json
{"etapas": {"ensino_fundamental": {"areas": {"ciencias_natureza": {"componentes": {"ciencias": {"unidades_tematicas": {"Matéria e energia": {"objetos": ["Características dos materiais", "Fontes e tipos de energia", …]}}}}}}}}}
```
A hierarquia completa (etapa → área → componente → unidade temática → objetos de conhecimento) em
uma única chamada — ideal para montar menus, filtros em cascata e navegação estruturada.

---

## Parte 5 — Busca semântica com IA

O diferencial da API: perguntas em **linguagem natural**, respondidas por IA (Gemini 2.5 Flash)
com base **exclusivamente** nas fontes oficiais indexadas (RAG sobre ChromaDB), sempre com citação
dos códigos e aviso explícito de conteúdo não-oficial.

### Exemplo 24 · Pergunta de um professor do 5º ano

```http
POST /api/v1/busca-semantica → HTTP 200 (9,2 s — primeira chamada)
{"query": "Como trabalhar frações com alunos do 5º ano?"}
```
```json
{
  "resposta": "Para trabalhar frações com alunos do 5º ano, o contexto oficial indica a habilidade:\n\n* **[EF05MA06]**: Associar as representações 10%, 25%, 50%, 75% e 100% respectivamente à décima parte, quarta parte, metade, três quartos e um inteiro…",
  "fontes": [{"codigo": "EF05MA06", "tipo": "habilidade", "relevancia": 0.562, "titulo": "Habilidade EF05MA06 - Matematica"}, …],
  "documentos_consultados": 5,
  "tempo_processamento": 9.007,
  "oficial": false,
  "aviso": "Conteudo gerado por IA a partir de fontes oficiais da BNCC. A redacao da resposta NAO e um documento oficial - consulte os codigos citados em `fontes` para o texto oficial."
}
```
Destaques: a resposta cita códigos verificáveis, cada fonte traz o grau de `relevancia`, e os campos
`oficial: false` + `aviso` deixam claro o status do conteúdo (Princípio VII da Constituição do
projeto — determinismo sobre IA).

### Exemplo 25 · Tema transversal, com mais fontes

```http
POST /api/v1/busca-semantica → HTTP 200 (3,6 s)
{"query": "habilidades sobre pensamento computacional e algoritmos", "max_resultados": 8}
```
A busca cruzou **Matemática e Computação** naturalmente: retornou EF07CO03, EF09CO02, EF08CO04
(Computação) junto de EF06MA23 e EF04MA06 (algoritmos e fluxogramas em Matemática) — 8 fontes,
como pedido.

### Exemplo 26 · Educação Infantil em linguagem do dia a dia

```http
POST /api/v1/busca-semantica → HTTP 200 (2,9 s)
{"query": "brincadeiras e interações para crianças pequenas", "max_resultados": 4}
```
```json
"resposta": "…**Interagir com outras crianças e adultos** ao explorar espaços, materiais, objetos e brinquedos. (Habilidade [EI01EO03]) · **Demonstrar atitudes de cuidado e solidariedade**… [EI02EO01] · **Resolver conflitos**… [EI02EO07]…"
```
A busca entendeu "crianças pequenas" (termo oficial dos grupos etários da EI) e devolveu objetivos
dos grupos corretos (EI01/EI02/EI03) — o modelo de embeddings multilíngue calibrado para PT-BR
funcionando em produção.

---

## Parte 6 — Conta, chaves e acompanhamento de uso

### Exemplo 27 · Dados da conta

```http
GET /api/v1/auth/me   (JWT da sessão) → HTTP 200 (80 ms)
{"account_id": "41f820a5-…", "email": "showcase-teste@expertia.dev.br", "email_verified": true}
```

### Exemplo 28 · Listar as chaves da conta

```http
GET /api/v1/keys → HTTP 200 (92 ms)
```
```json
[{"id": "15cf0f9c-…", "name": "showcase-2026-07-06", "prefix": "bncc_live_7lD_je3j", "status": "active", "created_at": "2026-07-06T18:00:22Z", "last_used_at": "2026-07-06T18:01:48Z"}]
```
Só o prefixo aparece — o segredo nunca é devolvido de novo. `last_used_at` atualiza em tempo real.

### Exemplo 29 · Uso agregado da conta

```http
GET /api/v1/usage → HTTP 200 (118 ms)
{"account_id": "41f820a5-…", "total_keys": 1, "deterministic_used_today": 0, "ai_used_today": 3}
```

### Exemplo 30 · Uso detalhado por chave (e os limites)

```http
GET /api/v1/keys/{key_id}/usage → HTTP 200 (120 ms)
```
```json
{
  "deterministic": {"used_this_minute": 18, "limit_per_minute": 70, "used_today": 0, "limit_per_day": null},
  "ai":            {"used_this_minute": 3,  "limit_per_minute": 20, "used_today": 3, "limit_per_day": 500}
}
```
O consumo é separado em dois "baldes": **determinístico** (consultas aos dados — 70 req/min, sem
teto diário) e **IA** (busca semântica — 20 req/min e 500 req/dia, por custar dinheiro real de LLM).
As 3 buscas semânticas do teste apareceram contabilizadas corretamente nos dois níveis (conta e chave).

---

## Parte 7 — Segurança e robustez (erros bem-comportados)

Uma API confiável também erra bem. Todos os cenários adversariais responderam com o status certo,
mensagem clara em português e `error_code` estruturado — **sem stack trace, sem vazamento de
detalhes internos**.

### Exemplo 31 · Sem autenticação → 401

```http
GET /api/v1/habilidades   (sem header) → HTTP 401
{"detail": "API key ausente. Envie 'Authorization: Bearer <sua-key>'.", "error_code": "http_401"}
```
A mensagem de erro ensina a corrigir o problema.

### Exemplo 32 · JWT do portal não vale como API key → 401

```http
GET /api/v1/habilidades   (Bearer <JWT da sessão>) → HTTP 401
{"detail": "API key inválida ou revogada.", "error_code": "http_401"}
```
Separação estrita de credenciais: a sessão do portal gerencia a conta, mas não acessa dados.

### Exemplo 33 · Código inexistente → 404

```http
GET /api/v1/habilidades/EF99XX99 → HTTP 404
{"detail": "Habilidade 'EF99XX99' não encontrada.", "error_code": "http_404"}
```

### Exemplo 34 · Filtro inválido → 400 com detalhe de validação

```http
GET /api/v1/habilidades?etapa=faculdade → HTTP 400
```
```json
{"detail": "Requisição inválida.", "error_code": "validation_error",
 "errors": [{"campo": "query.etapa", "msg": "Input should be 'educacao_infantil', 'ensino_fundamental' or 'ensino_medio'"}]}
```
O erro aponta o campo exato e os valores aceitos.

### Exemplo 35 · Busca semântica com query curta demais → 400

```http
POST /api/v1/busca-semantica {"query": "ab"} → HTTP 400
{"detail": "Requisição inválida.", "error_code": "validation_error", "errors": [{"campo": "body.query", "msg": "String should have at least 3 characters"}]}
```

### Bônus · Ciclo de vida completo da chave

Para fechar o teste, a chave foi **revogada** e o comportamento confirmado:

```http
DELETE /api/v1/keys/{key_id}  (JWT) → HTTP 204            ← revogação
GET /api/v1/habilidades       (key revogada) → HTTP 401   ← chave morre na hora
POST /api/v1/auth/logout      (JWT) → HTTP 200 {"logged_out": true}
```
A revogação tem efeito **imediato** — a mesma chave que funcionava segundos antes passou a ser
recusada.

---

## Desempenho observado

| Categoria | Latência típica (do cliente, em Windows/BR) |
|---|---|
| Endpoints de sistema (health/readiness/versão) | 70–270 ms |
| Consultas de dados (habilidades, competências) | **70–120 ms** |
| Taxonomia completa (~81 KB) | 179 ms |
| Busca semântica com IA — primeira chamada | 9,2 s |
| Busca semântica com IA — chamadas seguintes | 2,9–3,6 s |

Os endpoints determinísticos são consistentemente rápidos (o snapshot é servido da memória). A
busca com IA tem o custo esperado de uma chamada de LLM; a primeira execução foi mais lenta
(aquecimento), estabilizando em ~3 s.

---

## Observações e pequenos achados

Nada impede o uso da API — todos os pontos abaixo são refinamentos:

1. **Filtro `competencia_geral` retorna 0 resultados** (`GET /habilidades?competencia_geral=5` →
   `total: 0`). Os campos `competencias_gerais` das habilidades estão vazios no snapshot v1 — o
   vínculo habilidade↔competência geral não existe de forma explícita nos quadros dos documentos
   oficiais (inferi-lo violaria o princípio de fidelidade). O filtro funciona, mas hoje não tem
   dados para casar. Sugestão: documentar essa limitação na descrição do parâmetro no OpenAPI.
2. **Um objeto de conhecimento com texto fora de ordem**: em `EF05MA03`, o objeto veio como
   `"sua representação na reta numérica Representação fracionária dos números"` (a ordem natural
   seria "Representação fracionária dos números e sua representação na reta numérica") — artefato
   de quebra de linha na extração do PDF. Vale um ajuste fino no extrator.
3. **Erros de validação retornam HTTP 400** (não o 422 padrão do FastAPI), com envelope próprio
   (`error_code: validation_error` + lista `errors`). É uma escolha de design consistente e bem
   executada — só vale garantir que está documentada no guia.
4. **Limites de uso não aparecem em headers** (`X-RateLimit-*`): o consumo só é visível via
   `GET /keys/{id}/usage`. Expor headers ajudaria clientes a se autorregularem antes do 429.
5. **E-mail de verificação em modo console**: o fluxo self-service funciona, mas o link de
   verificação hoje só existe nos logs do Cloud Run — um usuário externo real não conseguiria
   ativar a conta sozinho até o SMTP real ser configurado (follow-up já conhecido do deploy).

---

## Conclusão

A BNCC API está **estável, rápida e completa em produção**. O teste cobriu 100% da superfície
pública (21 endpoints, 35 chamadas) e confirmou na prática os princípios do projeto:

- **Contrato primeiro** — tudo sob `/api/v1`, tipado, documentado no OpenAPI, com paginação e
  filtros consistentes;
- **Fidelidade da BNCC** — 1.716 habilidades com checksums das fontes, estruturas fiéis a cada
  etapa (campos de experiência na EI, unidades temáticas no EF, competências específicas no EM,
  eixos na Computação);
- **Segurança por padrão** — verificação de e-mail obrigatória, chaves hasheadas exibidas uma única
  vez, revogação imediata, credenciais de portal e de dados estritamente separadas, erros sem
  vazamento de internals;
- **Determinismo sobre IA** — dados oficiais servidos em ~80 ms independentemente do LLM, e o
  conteúdo de IA sempre rotulado como não-oficial, com fontes citadas e cota própria.

*Conta de teste criada durante o exercício: `showcase-teste@expertia.dev.br` (chave já revogada ao
final do teste).*
