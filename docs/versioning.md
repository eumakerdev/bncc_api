# Documentação versionada da BNCC API

Referência para mantenedores e consumidores da API sobre como a documentação e o
schema OpenAPI são versionados. O contrato público vive sob `/api/v1` e **não**
sofre quebra dentro da versão maior — mudanças incompatíveis exigem uma nova
versão de caminho (Princípio I da [Constituição](../.specify/memory/constitution.md)).

O recurso mantém o app FastAPI **único** (sem sub-apps montados): os
`app.dependency_overrides` usados pela suíte de testes não se propagam para
sub-apps montados, então a versão é modelada por prefixo de caminho e por um
registro em `app/api/versions.py`, não por montagem.

## Os dois eixos

A documentação é versionada em dois eixos independentes:

- **Eixo 1 — coexistência de versões de contrato.** Cada versão maior do
  contrato (`v1`, futuro `v2`) tem seu próprio conjunto de páginas, schema
  OpenAPI ao vivo e prefixo de caminho estável. Um registro em
  `app/api/versions.py` (`APIVersion`) dirige essas superfícies de forma
  genérica: adicionar uma versão ao registro faz docs e OpenAPI passarem a
  cobri-la sem código específico por versão.
- **Eixo 2 — histórico de releases.** Dentro de uma mesma versão de contrato, o
  schema evolui de forma aditiva a cada release da aplicação. Cada release pode
  ser **congelado** em disco (`docs/openapi/`) e navegado depois, para que o
  consumidor compare o schema atual com o de um release anterior.

## Esquema de URLs

`{slug}` é o slug da versão de contrato (`v1`, futuro `v2`); `{release}` é o
identificador do release congelado (ex.: `1.3.0`).

| URL | Tipo | Descrição |
| --- | --- | --- |
| `/docs` | Página | Referência interativa (Scalar) da versão mais recente. |
| `/docs/{slug}` | Página | Referência interativa de uma versão de contrato específica. |
| `/docs/{slug}?release=X` | Página | Referência de um release histórico via seletor de versão. |
| `GET /api/versions` | JSON | Manifesto legível por máquina das versões disponíveis. |
| `GET /api/{slug}/openapi.json` | JSON | OpenAPI **ao vivo** da versão (v1 pela rota nativa do FastAPI). |
| `GET /api/{slug}/releases/{release}/openapi.json` | JSON | OpenAPI **congelado** de um release. |
| `/api/v1/...` | API | Endpoints do contrato v1 (inalterados). |

Compatibilidade: `/api/v1/openapi.json` e `/docs` seguem se comportando como
antes desta feature — nada no contrato v1 mudou.

## Para consumidores

### Fixar uma versão de contrato

Aponte suas integrações para o prefixo de caminho estável (`/api/v1`). Para gerar
clientes ou validar contra o schema, use o OpenAPI ao vivo da versão:

```
GET /api/v1/openapi.json
```

Descubra as versões disponíveis programaticamente pelo manifesto:

```
GET /api/versions
```

### Ver um release histórico

Para inspecionar o schema como estava em um release anterior (dentro da mesma
versão de contrato), use o OpenAPI congelado:

```
GET /api/v1/releases/1.3.0/openapi.json
```

Ou navegue-o visualmente na referência interativa, pelo seletor de versão:

```
/docs/v1?release=1.3.0
```

## Para mantenedores

### Cortar um novo snapshot de release

Ao publicar um release da aplicação, atualize `APIVersion.release` (em
`app/api/versions.py`) e o campo `version` do app (`app/main.py`) para a nova
release e congele o OpenAPI enriquecido ao vivo — o script lê a release do
registro, sem argumento posicional:

```bash
python scripts/freeze_openapi.py
```

Isso grava `docs/openapi/{slug}/{release}.json` e atualiza o manifesto
`docs/openapi/{slug}/index.json`. O release congelado passa a ser servido em
`GET /api/{slug}/releases/{release}/openapi.json` e fica navegável em
`/docs/{slug}?release=<release>`.

Um teste de contrato garante que o release congelado mais recente casa com o
schema ao vivo e não introduz quebras (análogo a
`tests/contract/test_openapi_contract.py`). Valide localmente com:

```bash
python scripts/freeze_openapi.py --check
```

### Introduzir uma nova versão maior (`/api/v2`)

Uma nova versão de caminho é necessária apenas quando há mudança **incompatível**
de contrato. O passo a passo:

1. Inclua o roteador da v2 em `app/main.py` com `prefix="/api/v2"`.
2. Registre a versão em `app/api/versions.py` com uma entrada
   `APIVersion("v2", ...)`.
3. As superfícies de documentação passam a cobrir a v2 automaticamente: página
   `/docs/v2`, OpenAPI ao vivo em `/api/v2/openapi.json` e a entrada no manifesto
   `/api/versions`.
4. Congele releases da v2 com `scripts/freeze_openapi.py`, como na v1.

A v1 permanece publicada e inalterada enquanto tiver consumidores.

## Regra constitucional

Dentro de uma versão de contrato publicada **não** pode haver mudança
incompatível: novos campos e endpoints são aditivos; remoções ou alterações
incompatíveis exigem uma nova versão de caminho (`/api/v2`). É o que o Eixo 1
(prefixos estáveis por versão) e o teste de contrato do Eixo 2 (sem quebras no
release congelado) protegem, em conjunto, o Princípio I da Constituição.
