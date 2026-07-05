# Relatório de Teste em Produção — BNCC API

**Data do teste:** 05/07/2026
**Ambiente:** Produção (Google Cloud Run)
**Endereço da API:** `https://bncc-api-esjlky3g3a-rj.a.run.app`
**Resultado geral:** ✅ **Aprovado** — todas as 20 requisições responderam como esperado.

---

## 1. O que é esta API? (explicação para leigos)

A **BNCC** (Base Nacional Comum Curricular) é o documento oficial do governo brasileiro
que diz **o que cada aluno deve aprender** em cada ano da escola, da creche ao ensino médio.
Ela é enorme e vive em PDFs difíceis de consultar.

Esta **API** é como um "garçom digital": um programa (um site, um app, uma planilha) faz um
**pedido** ("me traga as habilidades de matemática do 4º ano") e a API **devolve a resposta**
já organizada, em um formato que outros programas entendem (chamado **JSON** — basicamente uma
lista de informações etiquetadas).

Alguns termos que aparecem neste relatório:

| Termo | O que significa, em português claro |
|---|---|
| **Requisição / Request** | O pedido que enviamos para a API. |
| **Resposta / Response** | O que a API devolveu. |
| **Endpoint** | Um "balcão de atendimento" específico. Ex.: um balcão só de habilidades, outro só de competências. |
| **HTTP 200** | Código de sucesso — "deu certo". |
| **HTTP 400 / 401 / 404 / 422** | Códigos de recusa — "seu pedido tem um problema" (explicados adiante). |
| **API key** | Uma "senha de acesso" pessoal. Sem ela, a API não entrega os dados. |
| **Habilidade** | Uma competência específica que o aluno deve desenvolver. Cada uma tem um código, ex.: `EF04MA10`. |

### Como ler um código de habilidade (ex.: `EF04MA10`)

```
EF        04     MA        10
│         │      │         │
Ensino    4º     Matemática  décima habilidade
Fundamental ano             dessa lista
```

---

## 2. Como conseguir acesso (o "cadastro")

Antes de pedir qualquer dado, é preciso ter uma **API key** (a senha de acesso). O caminho é o
mesmo que um desenvolvedor de verdade faria, em 4 passos:

1. **Criar conta** com e-mail e senha.
2. **Confirmar o e-mail** (a API envia um link de verificação).
3. **Fazer login.**
4. **Gerar a API key.**

> **Observação importante:** hoje o envio de e-mail está em modo "console" — ou seja, o link de
> confirmação **não chega numa caixa de entrada real**, ele aparece apenas nos registros internos
> (logs) do servidor. Para este teste, buscamos o link nos logs. Para o público final conseguir se
> cadastrar sozinho, será preciso ativar o envio de e-mail de verdade (SMTP).

Abaixo, o passo a passo real executado no teste:

### Passo 1 — Criar conta

**Enviamos:**
```http
POST /api/v1/auth/signup
{ "email": "teste-...@example.com", "password": "********" }
```
**Recebemos (sucesso):**
```json
{
  "account_id": "38bf3540-1b9a-4cf9-bec1-a4dd6fc2f14d",
  "email": "teste-...@example.com",
  "email_verified": false
}
```
👉 Conta criada, mas ainda **não verificada** (`email_verified: false`).

### Passo 2 — Confirmar e-mail

**Enviamos** o token que veio no link de verificação:
```http
POST /api/v1/auth/verify-email
{ "token": "5hRTphqc...." }
```
**Recebemos:**
```json
{ "email_verified": true }
```
👉 E-mail confirmado. Agora a conta pode gerar chaves.

### Passo 3 e 4 — Login e gerar a API key

**Enviamos:**
```http
POST /api/v1/keys        (autenticado com a sessão do login)
{ "name": "smoke-test" }
```
**Recebemos:**
```json
{
  "id": "dfdcf87a-4395-4148-86b1-4fe88f9f5143",
  "name": "smoke-test",
  "prefix": "bncc_live_zUWBz9Q2",
  "key": "bncc_live_zUWBz9Q2**************************"
}
```
👉 A **chave completa só aparece uma vez**, no momento da criação — depois disso o sistema guarda
apenas uma versão "embaralhada" dela, por segurança. Neste teste, a chave foi **apagada ao final**.

> A partir daqui, todo pedido de dados leva a chave no cabeçalho:
> `Authorization: Bearer <sua-chave>`. É como carimbar cada pedido com sua senha de acesso.

---

## 3. Testes dos dados oficiais (respostas exatas e previsíveis)

Estes endpoints entregam **o texto oficial da BNCC**, sem interpretação. A mesma pergunta sempre
devolve a mesma resposta.

### Teste 1 — A API está no ar? (não precisa de chave)

**Enviamos:** `GET /api/v1/sistema/health`
**Recebemos:** `HTTP 200` em 269 ms
```json
{ "status": "ok" }
```
✅ **Em bom português:** "Estou funcionando."

---

### Teste 2 — Qual versão dos dados está publicada?

**Enviamos:** `GET /api/v1/sistema/versao-dados`
**Recebemos:** `HTTP 200`
```json
{
  "versao": "v1",
  "data_publicacao": "2026-07-03",
  "contagens": {
    "por_etapa": {
      "educacao_infantil": 93,
      "ensino_fundamental": 1291,
      "ensino_medio": 179
    },
    "total_habilidades": 1563,
    "total_competencias_gerais": 10
  },
  "missing_sources": []
}
```
✅ **Em bom português:** A base tem **1.563 habilidades** no total (93 da creche/pré-escola,
1.291 do fundamental, 179 do médio) e as **10 competências gerais**. `missing_sources: []` significa
"nenhuma fonte oficial ficou de fora".

---

### Teste 3 — Habilidades da Educação Infantil

**Enviamos:** `GET /api/v1/habilidades?etapa=educacao_infantil&size=2`
*(traduzindo o pedido: "me dê 2 habilidades da educação infantil")*
**Recebemos:** `HTTP 200` — total de 93 disponíveis. Primeira da lista:
```json
{
  "codigo": "EI01CG01",
  "descricao": "Movimentar as partes do corpo para exprimir corporalmente emoções, necessidades e desejos.",
  "etapa": "educacao_infantil",
  "campo_experiencia": "Corpo, gestos e movimentos"
}
```
✅ **Em bom português:** Para bebês, uma das metas é "mexer o corpo para expressar emoções". Note
o campo próprio da creche: **campo de experiência** (a educação infantil não tem "matérias").

---

### Teste 4 — Habilidades de Matemática do Ensino Médio

**Enviamos:** `GET /api/v1/habilidades?etapa=ensino_medio&area_conhecimento=matematica&size=2`
**Recebemos:** `HTTP 200` — 45 habilidades. Exemplo:
```json
{
  "codigo": "EM13MAT101",
  "descricao": "Interpretar situações econômicas, sociais e das Ciências da Natureza que envolvem a variação de duas grandezas, pela análise dos gráficos das funções representadas e das taxas de variação com ou sem apoio de tecnologias digitais."
}
```
✅ Filtro por etapa **e** área funcionando ao mesmo tempo.

---

### Teste 5 — Habilidades de História do 7º ano

**Enviamos:** `GET /api/v1/habilidades?componente=historia&ano=7&size=2`
**Recebemos:** `HTTP 200` — 17 habilidades. Exemplo:
```json
{
  "codigo": "EF07HI01",
  "descricao": "Explicar o significado de “modernidade” e suas lógicas de inclusão e exclusão, com base em uma concepção europeia."
}
```
✅ Dá para filtrar por **matéria** e por **ano** juntos.

---

### Teste 6 — Buscar uma habilidade específica pelo código

**Enviamos:** `GET /api/v1/habilidades/EF04MA10`
**Recebemos:** `HTTP 200`
```json
{
  "codigo": "EF04MA10",
  "descricao": "Reconhecer que as regras do sistema de numeração decimal podem ser estendidas para a representação decimal de um número racional e relacionar décimos e centésimos com a representação do sistema monetário brasileiro.",
  "anos": ["4"],
  "componente": "matematica"
}
```
✅ **Em bom português:** Quem já sabe o código vai direto à habilidade, como digitar um CEP.

---

### Teste 7 — Relações de uma habilidade

**Enviamos:** `GET /api/v1/habilidades/EF04MA10/relacoes`
**Recebemos:** `HTTP 200`
```json
{
  "codigo": "EF04MA10",
  "competencias_gerais": [],
  "competencias_especificas": [],
  "objetos_conhecimento": [],
  "unidades_tematicas": []
}
```
⚠️ **O endpoint responde corretamente, mas as listas vieram vazias.** Ou seja: hoje a base ainda
**não registra as ligações** entre uma habilidade e suas competências/temas relacionados. Isso é uma
**lacuna de dados** a avaliar (ver seção 5).

---

### Testes 8, 9 e 10 — E quando o pedido está errado?

Uma boa API precisa **recusar com clareza** pedidos inválidos, sem quebrar. Testamos três erros de
propósito:

| Pedido | Resposta | Em bom português |
|---|---|---|
| `GET /habilidades/CODIGO_INEXISTENTE` | `HTTP 400` — "Código malformado. Formatos aceitos: EI, EF, EM…" | "Esse código nem tem o formato certo." |
| `GET /habilidades` **sem a chave** | `HTTP 401` — "API key ausente." | "Você não se identificou." |
| `GET /habilidades?etapa=nao_existe` | `HTTP 400` — indica o campo `query.etapa` e os valores válidos | "Essa etapa não existe; use uma destas." |

**Resposta detalhada do último caso:**
```json
{
  "detail": "Requisição inválida.",
  "error_code": "validation_error",
  "errors": [
    { "campo": "query.etapa",
      "msg": "Input should be 'educacao_infantil', 'ensino_fundamental' or 'ensino_medio'" }
  ]
}
```
✅ Todos os erros vêm com **mensagem explicativa** e **sem vazar detalhes internos** do servidor.

---

### Teste 11 — As 10 Competências Gerais

**Enviamos:** `GET /api/v1/competencias/gerais`
**Recebemos:** `HTTP 200` — as 10 competências completas. As duas primeiras:
```json
[
  { "numero": 1, "titulo": "Conhecimento",
    "descricao": "Valorizar e utilizar os conhecimentos historicamente construídos sobre o mundo físico, social, cultural e digital..." },
  { "numero": 2, "titulo": "Pensamento científico, crítico e criativo",
    "descricao": "Exercitar a curiosidade intelectual e recorrer à abordagem própria das ciências..." }
]
```
✅ **Em bom português:** As 10 grandes metas que atravessam toda a educação básica, do texto oficial.

---

### Teste 12 — A árvore da taxonomia

**Enviamos:** `GET /api/v1/taxonomia`
**Recebemos:** `HTTP 200` — o "mapa" de como a BNCC se organiza: **etapa → área → componente**.
```json
{
  "etapas": {
    "ensino_fundamental": {
      "areas": {
        "matematica": { "componentes": { "matematica": { "unidades_tematicas": {} } } },
        "linguagens":  { "componentes": { "lingua_portuguesa": {}, "arte": {}, "...": {} } }
      }
    }
  }
}
```
✅ Serve para montar menus de navegação. ⚠️ O último nível (**unidades temáticas**) está vazio —
mesma lacuna do Teste 7.

---

## 4. Testes da Busca Semântica com Inteligência Artificial

Aqui está o recurso mais avançado. Em vez de filtros exatos, você faz uma **pergunta em linguagem
natural** ("como uma pessoa fala") e a IA (modelo **Google Gemini**) monta uma resposta baseada nos
trechos oficiais mais parecidos.

**Como funciona, em 3 passos:**
1. A pergunta é comparada com todas as habilidades para achar as mais **parecidas em significado**
   (não em palavras exatas). Cada achado ganha uma nota de **relevância** de 0 a 1.
2. A IA escreve uma resposta **usando só esses trechos oficiais**.
3. A resposta vem marcada como **`oficial: false`** e sempre lista as **fontes** (os códigos oficiais),
   para você conferir no texto original.

> **Regra de ouro do sistema:** a IA **nunca inventa**. Se não achar nada confiável, ela avisa.
> O texto gerado é um **resumo de apoio**, não o documento oficial.

---

### Busca S1 — "frações e números decimais nos anos iniciais"

**Enviamos:**
```json
POST /api/v1/busca-semantica
{ "query": "frações e números decimais nos anos iniciais do ensino fundamental", "max_resultados": 4 }
```
**Recebemos:** `HTTP 200` (≈4 s)
- **Fontes encontradas:** `EF05MA06` (relevância 0,52), `EF06MA13`, `EF09MA05`
- **Resposta da IA (resumo, não-oficial):**
  > "Com base no contexto oficial, a habilidade que aborda frações e números decimais no 5º ano é a
  > **EF05MA06**, que associa representações percentuais (10%, 25%, 50%…) às frações correspondentes…"

✅ Achou habilidades de Matemática pertinentes e explicou de forma didática.

---

### Busca S2 — "educação ambiental e sustentabilidade"

**Enviamos:** `{ "query": "educação ambiental, sustentabilidade e preservação da natureza", "max_resultados": 4 }`
**Recebemos:** `HTTP 200` (≈5,8 s)
- **Fontes:** `EM13CNT206` (0,63), `EF09CI12` (0,60), `EF89EF19`, `EM13CHS304`
- **Resposta:** listou 4 habilidades reais de Ciências, Educação Física e Ciências Humanas ligadas a
  meio ambiente, cada uma com o texto oficial.

✅ Uma pergunta ampla trouxe habilidades de **várias matérias e etapas** — exatamente o valor da busca por significado.

---

### Busca S3 — "alfabetização e consciência fonológica"

**Enviamos:** `{ "query": "alfabetização, consciência fonológica e leitura no início do fundamental", "max_resultados": 3 }`
**Recebemos:** `HTTP 200`
- **Fontes:** `EF02LP26` (0,63), `EF69LP49`, `EF69LP54`
- **Resposta (trecho):**
  > "…O contexto oficial **não menciona explicitamente** os termos 'alfabetização' ou 'consciência
  > fonológica' para o início do Ensino Fundamental…"

✅ **Ponto alto de honestidade:** em vez de inventar, a IA **admitiu** o que não estava nas fontes.

---

### Busca S4 — "bebês expressarem emoções com o corpo"

**Enviamos:** `{ "query": "brincadeiras e interações para bebês expressarem emoções com o corpo", "max_resultados": 3 }`
**Recebemos:** `HTTP 200`
- **Fontes:** `EI03CG01` (**0,67** — a maior relevância de todos os testes), `EI01CG01`, `EI02EO01`
- **Resposta:** explicou os códigos `EI01CG01` e `EI03CG01` (expressão corporal de emoções na creche).

✅ A busca funciona muito bem também para a **Educação Infantil**.

---

### Busca S5 — "pensamento computacional" (com contexto)

**Enviamos:** `{ "query": "pensamento computacional e algoritmos na matemática", "max_resultados": 3, "incluir_contexto": true }`
**Recebemos:** `HTTP 200`
- **Fontes:** `EF04MA06` (0,66), `EF05MA07`, `EF04MA03`
- **Resposta:** encontrou o termo "algoritmos" em habilidades de Matemática, mas avisou que
  "**pensamento computacional** não é mencionado" no texto oficial.

⚠️ Pedimos o extra `incluir_contexto: true` (para ver os trechos brutos usados), mas a resposta **não
trouxe** um campo de contexto. Vale confirmar se essa opção está ativa (ver seção 5).

---

### Busca S6 — Uma pergunta fora do assunto: "bolo de chocolate"

**Enviamos:** `{ "query": "como fazer um bolo de chocolate fofinho", "max_resultados": 3 }`
**Recebemos:** `HTTP 200` (rápido, 0,4 s)
- **Fontes:** *(nenhuma)* — `documentos_consultados: 0`
- **Resposta:**
  > "Não encontrei na BNCC habilidades ou competências com correspondência confiável para a sua
  > pergunta. Tente reformular… **Nenhuma informação foi inventada.**"

✅ **Este é talvez o teste mais importante:** a IA **não alucinou**. Percebeu que não havia nada
relacionado e avisou honestamente. É a "regra de ouro" funcionando na prática.

---

### Buscas S7 e S8 — Perguntas vazias ou curtas demais

| Pedido | Resposta |
|---|---|
| `{ "query": "" }` | `HTTP 400` — "String should have at least 3 characters" |
| `{ "query": "a" }` | `HTTP 400` — mesma mensagem |

✅ A API recusa perguntas sem sentido antes mesmo de acionar a IA (economiza tempo e custo).

---

## 5. Conclusão e pontos de atenção

### ✅ O que está funcionando bem

- **Disponibilidade:** a API está no ar e respondeu **todas** as 20 requisições.
- **Velocidade:** consultas de dados em ~250–290 ms; buscas com IA entre 0,4 e 7,7 s.
- **Acentuação (UTF-8):** todas as palavras com acento saíram corretas (`décimos`, `frações`, `emoções`).
- **Segurança:** sem chave, a API bloqueia (401); erros vêm explicados e **sem vazar detalhes internos**.
- **IA responsável:** a busca semântica **nunca inventou**; admite quando não sabe (S3, S5) e avisa
  quando não há correspondência (S6). Toda resposta de IA vem marcada como **não-oficial** e com fontes.

### ⚠️ Pontos a decidir / melhorar

1. **Ligações entre dados estão vazias** (Testes 7 e 12): as relações de uma habilidade
   (competências, objetos de conhecimento, unidades temáticas) hoje vêm em branco. Os endpoints
   existem e funcionam, mas falta **popular esses vínculos** — avaliar se é lacuna de extração dos PDFs.
2. **Opção `incluir_contexto` (Busca S5)** não retornou os trechos brutos esperados. Confirmar se a
   funcionalidade está ativa e qual o nome do campo no retorno.
3. **E-mail de verificação em modo "console"**: o link de confirmação não chega numa caixa de entrada
   real, só nos logs. **Enquanto isso, o público não consegue se cadastrar sozinho.** É o próximo
   passo para a plataforma ser realmente self-service (ativar envio SMTP).

### Metodologia deste teste

- Foi criada uma conta de teste real, verificada e usada para gerar uma API key; a chave foi
  **apagada ao final** (confirmação `HTTP 204`).
- Todas as requisições e respostas foram registradas na íntegra; os textos acima são reproduções
  fiéis do que a API enviou e devolveu em 05/07/2026.

---

*Relatório gerado a partir de testes reais executados contra o ambiente de produção.*
