<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="app/web/static/logo-dark.svg">
  <img alt="BNCC API" src="app/web/static/logo.svg" width="340">
</picture>

# BNCC API

**Toda a Base Nacional Comum Curricular do Brasil, em uma API pública, gratuita e open-source.**

Dados oficiais das três etapas (Educação Infantil, Ensino Fundamental e Ensino Médio) — habilidades,
competências e taxonomia completa — servidos de forma programática, com documentação automática e
busca semântica com IA.

[![CI](https://github.com/eumakerdev/bncc_api/actions/workflows/ci.yml/badge.svg)](https://github.com/eumakerdev/bncc_api/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.13x-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#-licença)
[![Cobertura](https://img.shields.io/badge/coverage-%E2%89%A580%25-brightgreen.svg)](#-testes-e-qualidade)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-como-contribuir)

**[bncc.api.br](https://bncc.api.br)**

[Demo ao vivo](https://bncc.api.br) ·
[Documentação (Swagger)](https://bncc.api.br/docs) ·
[Reportar bug](https://github.com/eumakerdev/bncc_api/issues) ·
[Apoiar o projeto](#-apoie-o-projeto-)

</div>

---

## 💡 Por que esta API existe

Oi! Eu sou o **Fábio Santana — [EuMaker](https://github.com/eumakerdev)**.

Toda vez que eu ia desenvolver alguma aplicação educacional, esbarrava no mesmo problema: **acessar a
BNCC de forma programática é uma dor**. Os dados oficiais vivem espalhados em PDFs gigantes, colunas
mal alinhadas e tabelas que não foram feitas para máquinas lerem. Eu me pegava, de novo e de novo,
copiando códigos de habilidade na mão, recortando descrições e montando planilhas para depois virar
JSON.

Cansei de reinventar essa roda. Então resolvi extrair a BNCC **inteira**, com fidelidade ao documento
oficial, e servir tudo por uma API limpa — do jeito que eu gostaria de ter encontrado pronto. E como
essa dor é de todo mundo que constrói coisas para educação no Brasil, decidi abrir o código.

Dado curricular é público. Acredito que ele tem que estar à disposição de quem constrói — sem paywall,
sem fila. Por isso a API é **gratuita, open-source e aceita contribuidores**. Se ela te poupar o
trabalho que me poupou, [me pague um café](#-apoie-o-projeto-) ☕.

---

## ✨ O que ela faz

| Recurso                        | Descrição                                                                                                                                                                                                                                              |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 📖 **BNCC completa**           | As **3 etapas** (EI/EF/EM): 1.703 habilidades, 10 competências gerais e toda a taxonomia oficial — etapas, áreas, componentes, unidades temáticas e objetos de conhecimento.                                                                           |
| 💻 **Computação**              | O **Complemento de Computação à BNCC** (Parecer CNE/CP 02/2022): 140 habilidades `CO` nas 3 etapas, com os eixos **Pensamento Computacional**, **Mundo Digital** e **Cultura Digital** (EI/EF). Filtráveis por `componente=computacao` e por `eixo`.   |
| 🎯 **Fidelidade ao documento** | Extração **determinística, versionada e reproduzível** a partir dos PDFs oficiais. Um snapshot publicado (`bncc_v1.json`), com checksum das fontes. Nada de dado inventado.                                                                            |
| 🔑 **Acesso self-service**     | Crie uma conta no portal, verifique o e-mail e gere suas próprias **API keys**. Sem burocracia, sem esperar aprovação.                                                                                                                                 |
| 🤖 **Busca semântica com IA**  | Pergunte em linguagem natural (“quais habilidades de matemática do 5º ano tratam de frações?”) e receba resposta com **fontes oficiais rastreáveis**. Conteúdo gerado é sempre marcado como **não-oficial**.                                           |
| 📚 **Docs automáticas**        | Swagger UI e ReDoc gerados do próprio código (OpenAPI). Mudou um endpoint? A doc atualiza sozinha.                                                                                                                                                     |
| 🌐 **Landing + portal SSR**    | Página de apresentação com foco em SEO e um portal para gerenciar contas, keys e consumo.                                                                                                                                                              |
| 🛡️ **Seguro por padrão**       | Rate limiting, API keys hasheadas, senhas com Argon2, headers de segurança em toda resposta (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS em produção) e _fail-fast_ de configuração: a app **não sobe insegura** em produção. |

> A busca com IA **nunca** compromete os dados oficiais: se a camada de IA cair, todos os endpoints
> determinísticos continuam respondendo normalmente (degradação graciosa).

---

## 🗺️ Endpoints principais

Base: `/api/v1` · Autenticação por API key (`Authorization: Bearer <sua-key>`).

### Dados oficiais (determinísticos · 60 req/min)

| Método | Rota                                     | O que retorna                                                                                                 |
| ------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/habilidades`                           | Lista habilidades com filtros (etapa, ano, área, componente, competência, **eixo** de Computação) + paginação |
| `GET`  | `/habilidades/{codigo}`                  | Uma habilidade pelo código oficial (ex.: `EF05MA07`, `EM13MAT101`, `EI03EO01`)                                |
| `GET`  | `/habilidades/{codigo}/relacoes`         | Grafo de relações navegáveis da habilidade                                                                    |
| `GET`  | `/competencias/gerais`                   | As 10 competências gerais da BNCC                                                                             |
| `GET`  | `/competencias/gerais/{numero}`          | Uma competência geral específica                                                                              |
| `GET`  | `/competencias/especificas`              | Competências específicas por área                                                                             |
| `GET`  | `/taxonomia`                             | Árvore completa da taxonomia oficial                                                                          |
| `GET`  | `/sistema/versao-dados`                  | Versão e contagens do snapshot                                                                                |
| `GET`  | `/sistema/health` · `/sistema/readiness` | Liveness/readiness                                                                                            |

### Busca com IA (não-oficial · 20 req/min + 500/dia)

| Método | Rota               | O que retorna                                               |
| ------ | ------------------ | ----------------------------------------------------------- |
| `POST` | `/busca-semantica` | Resposta em linguagem natural + fontes oficiais rastreáveis |

### Conta e API keys (portal)

| Método                | Rota                                                                   | O que faz                                                        |
| --------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `POST`                | `/auth/signup` · `/auth/verify-email` · `/auth/login` · `/auth/logout` | Ciclo de conta com verificação de e-mail                         |
| `GET`                 | `/auth/me`                                                             | Dados da conta autenticada                                       |
| `POST` `GET` `DELETE` | `/keys` · `/keys/{id}`                                                 | Criar (segredo exibido **uma única vez**), listar e revogar keys |
| `GET`                 | `/keys/{id}/usage` · `/usage`                                          | Consumo por key e agregado                                       |

**Superfícies web:** `/` (landing) · `/portal` (contas/keys) · `/docs` (Swagger) · `/redoc` · `/guia`

### Exemplo rápido

```bash
# Buscar uma habilidade de Matemática do 5º ano
curl -H "Authorization: Bearer $KEY" \
  https://bncc.api.br/api/v1/habilidades/EF05MA07

# Perguntar em linguagem natural
curl -X POST https://bncc.api.br/api/v1/busca-semantica \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"quais habilidades de matemática do 5º ano tratam de frações?"}'
```

---

## 🚀 Rodando localmente

### Pré-requisitos

- Python 3.11+ (ou Docker + Docker Compose)
- O snapshot `data/bncc_v1.json` já vem versionado no repositório — **você não precisa dos PDFs**
  para rodar a API.

### Com Docker (mais simples)

```bash
git clone https://github.com/eumakerdev/bncc_api.git
cd bncc_api
cp .env.example .env      # ajuste se quiser
docker-compose up --build
```

### Ambiente local

```bash
git clone https://github.com/eumakerdev/bncc_api.git
cd bncc_api

python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate       # Linux/Mac

pip install -r requirements.txt
cp .env.example .env             # em produção: SECRET_KEY forte + ALLOWED_HOSTS restrito

alembic upgrade head             # cria o banco da plataforma (contas/keys/uso)
uvicorn app.main:app --reload
```

A API sobe em **http://localhost:8000** — landing em `/`, docs em `/docs`, portal em `/portal`.

> 🤖 **Busca com IA é opcional.** Sem chaves de LLM configuradas, todos os endpoints determinísticos
> funcionam normalmente; só a `/busca-semantica` fica indisponível. Para habilitá-la, gere os vetores
> com `python scripts/generate_embeddings.py` e configure `OPENAI_API_KEY` **ou** `GOOGLE_API_KEY` no `.env`.

---

## 🏗️ Arquitetura

Camadas com dependências apontando **para dentro** — a regra de negócio nunca conhece HTTP:

```
app/api      →  roteadores FastAPI (sem regra de negócio)
app/services →  domínio (BNCC, IA, contas, keys, uso — sem objetos HTTP)
app/models   →  schemas Pydantic v2
app/web      →  landing + portal + docs (Jinja2 + Tailwind, SSR)
app/core     →  config, deps injetáveis, segurança, erros
data/        →  snapshot oficial da BNCC (read-only em runtime)
scripts/     →  extração determinística, validação de cobertura, embeddings
```

**Stack:** Python 3.11 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 async + Alembic (SQLite em dev →
Postgres em prod) · ChromaDB + sentence-transformers para RAG · JWT + Argon2 · Jinja2 + Tailwind.

O projeto é governado por uma [Constituição](.specify/memory/constitution.md) com princípios
não-negociáveis: **contrato primeiro, testes primeiro, fidelidade à BNCC, segurança por padrão e
determinismo sobre IA**. A especificação completa da v1 está em
[`specs/001-public-api-platform/`](specs/001-public-api-platform/).

---

## 🧪 Testes e qualidade

```bash
pytest --cov=app --cov-report=term-missing     # testes + cobertura (gate ≥ 80%)
ruff check app/ scripts/ tests/                # lint
black app/ scripts/ tests/                     # formatação
mypy app/                                       # tipos (código novo)
pre-commit run --all-files                      # portões locais (segredos, lint, format)
```

---

## 🤝 Como contribuir

**Contribuições são muito bem-vindas!** Seja código, correção de dados, documentação, ou só reportar
um bug — tudo ajuda.

1. Faça um **fork** do projeto
2. Crie uma branch (`git checkout -b feat/minha-melhoria`)
3. Faça suas mudanças **com testes** (a cobertura ≥ 80% é gate de CI)
4. Rode os portões locais: `pre-commit run --all-files` e `pytest`
5. Commit e push (`git push origin feat/minha-melhoria`)
6. Abra um **Pull Request** descrevendo o que mudou e por quê

Boas primeiras contribuições: melhorias de documentação, novos exemplos de uso, testes adicionais,
validação de cobertura de dados da BNCC. Achou uma divergência entre a API e o documento oficial?
[Abra uma issue de divergência BNCC](https://github.com/eumakerdev/bncc_api/issues/new/choose) — fidelidade aos dados é prioridade máxima.

Antes de abrir um PR, leia o **[guia de contribuição](CONTRIBUTING.md)** (setup, portões de CI e
regras de contrato) e o **[código de conduta](CODE_OF_CONDUCT.md)**. Encontrou uma
vulnerabilidade? **Não abra uma issue pública** — siga a [política de segurança](SECURITY.md).

---

## ❤️ Apoie o projeto

Esta API é gratuita e vai continuar sendo. Mas "grátis" não quer dizer "sem custo": ela roda em
infraestrutura real (Cloud Run + Postgres) e essa conta chega todo mês. Hoje a **Expertia** e a
**EuMaker** bancam isso — e há um teto de quanto conseguimos segurar sozinhos conforme o uso cresce.

Por isso o custo real da infraestrutura fica **público na landing** (`/#transparencia`): o valor
faturado pelo Google Cloud, atualizado sozinho, sem estimativa. Se você vai pedir apoio, mostra a
conta. Se a API poupou seu tempo ou entrou no que você construiu, qualquer valor ajuda a manter tudo
no ar — nem que seja um cafezinho recorrente.

### 🌍 GitHub Sponsors _(internacional)_

**[github.com/sponsors/eumakerdev](https://github.com/sponsors/eumakerdev)** — cartão internacional,
avulso ou mensal, sem taxa de plataforma.

### 🇧🇷 Pix

<img src="docs/assets/pix-qrcode.png" alt="QR Code Pix para doação" width="180" align="right" />

Aponte a câmera para o QR Code ao lado, **ou** copie o código abaixo e cole em
**Pix › Copia e Cola** no app do seu banco (você escolhe o valor):

```
00020126360014BR.GOV.BCB.PIX0114+55719990084435204000053039865802BR5913FABIO SANTANA6006BRASIL62110507BNCCAPI63040E12
```

Ou use a chave (telefone) diretamente: `+5571999008443`

<br clear="right" />

Qualquer valor faz diferença — e um ⭐ no repositório também ajuda muito a dar visibilidade! 🙏

---

## 📄 Licença

Distribuído sob a licença **MIT**. Sinta-se livre para usar, modificar e distribuir. Veja o arquivo
[`LICENSE`](LICENSE) para os termos completos.

---

## ⚖️ Sobre os dados da BNCC

Os dados curriculares são extraídos dos documentos oficiais da **Base Nacional Comum Curricular**,
publicados pelo **Ministério da Educação (MEC)**. Esta é uma iniciativa **independente e não-oficial**:
não há vínculo com o MEC. Os textos das habilidades e competências são reproduções fiéis do documento
oficial; qualquer conteúdo gerado por IA é explicitamente marcado como **não-oficial**.

---

<div align="center">

Feito com 💚 por **[Fábio Santana — EuMaker](https://github.com/eumakerdev)**, para quem constrói educação no Brasil.

</div>
