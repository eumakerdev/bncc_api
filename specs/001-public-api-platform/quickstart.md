# Quickstart & Validation: Plataforma Pública da BNCC API

Guia executável para validar a feature ponta a ponta. Mapeia cenários às histórias (US1–US5) e aos
Success Criteria (SC-###). **Não** contém implementação — apenas passos de execução e resultados
esperados. Detalhes de entidades em [data-model.md](./data-model.md); comportamento por endpoint em
[contracts/](./contracts/).

## Pré-requisitos
- Python 3.11+ (ou Docker + Docker Compose).
- Fontes oficiais em `data/` (`bncc_ensino_fundamental.pdf`, `bncc_ensino_medio.pdf`; fonte de EI).
- `.env` a partir de `.env.example`. **Em produção**: `SECRET_KEY` forte e `ALLOWED_HOSTS` restrito
  (a app não sobe insegura — FR-023/SC-010).

## Setup
```bash
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 1) Extrair a BNCC completa (determinístico, versionado) → data/bncc_v1.json
python scripts/extract_bncc_data.py --validate

# 2) Validar cobertura/integridade contra a fonte oficial
python scripts/validate_bncc_coverage.py

# 3) Migrações do banco da plataforma (contas/keys/uso)
alembic upgrade head

# 4) Gerar embeddings (camada de IA, opcional para determinístico)
python scripts/generate_embeddings.py

# 5) Subir a aplicação
uvicorn app.main:app --reload
```
Docker: `docker-compose up --build`. API em `http://localhost:8000`.

## Cenário 1 — BNCC completa via API (US1 · SC-001/002/005)
```bash
# habilidades de cada etapa (usar uma API key válida — ver Cenário 2)
curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/habilidades/EF05MA07
curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/habilidades/EM13MAT101
curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/habilidades/EI03EO01
# filtro + paginação
curl -H "Authorization: Bearer $KEY" "http://localhost:8000/api/v1/habilidades?etapa=ensino_medio&size=20"
# relações navegáveis
curl -H "Authorization: Bearer $KEY" http://localhost:8000/api/v1/habilidades/EF05MA07/relacoes
```
**Esperado**: descrição/metadados oficiais exatos; código malformado → 400; inexistente → 404; três
etapas presentes (`/api/v1/sistema/versao-dados` mostra contagens > 0 por etapa).

## Cenário 2 — Acesso self-service (US2 · SC-003/004/011)
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup -d '{"email":"dev@ex.com","password":"..."}'
# dev: pegar o link de verificação (em dev, logado no console) e confirmar
curl -X POST http://localhost:8000/api/v1/auth/verify-email -d '{"token":"..."}'
curl -X POST http://localhost:8000/api/v1/auth/login -d '{"email":"dev@ex.com","password":"..."}'
# com a sessão, criar key (segredo exibido uma única vez)
curl -X POST http://localhost:8000/api/v1/keys -H "Cookie: <sessao>" -d '{"name":"minha-app"}'
```
**Esperado**: sem verificar e-mail → não gera key (403); chamada sem key → 401; acima de 60/min →
429 com `Retry-After`; painel mostra consumo por key. **SC-003**: cadastro→1ª chamada < 10 min.

## Cenário 3 — Documentação automática (US3 · SC-007)
- Abrir `http://localhost:8000/docs` (Swagger) e a página de docs estilizada.
- **Esperado**: todos os endpoints públicos listados com schemas/exemplos; "testar" executa chamada
  real autenticada por API key; adicionar/alterar um endpoint no código reflete nas docs **sem edição
  manual** (fonte = `/api/v1/openapi.json`).

## Cenário 4 — Busca semântica com IA (US4 · SC-006/009)
```bash
curl -X POST http://localhost:8000/api/v1/busca-semantica -H "Authorization: Bearer $KEY" \
  -d '{"query":"quais habilidades de matemática do 5º ano tratam de frações?"}'
```
**Esperado**: resposta gerada + `fontes` com `codigo`+`relevancia` (rastreáveis); conteúdo gerado
distinguível do oficial; pergunta sem match → "sem resultados confiáveis" (não inventa); acima de
~20/min ou teto diário → 429 no bucket `ai`. **Degradação (SC-009)**: com IA fora do ar, o endpoint de
IA responde 503 acionável e **todos os endpoints determinísticos do Cenário 1 seguem 200**.

## Cenário 5 — Landing page SEO (US5 · SC-008)
- Abrir `http://localhost:8000/` e rodar Lighthouse.
- **Esperado**: proposta de valor, recursos, público-alvo e CTA para cadastro; meta tags, Open Graph,
  JSON-LD, `/sitemap.xml` e `/robots.txt`; Lighthouse ≥ 90 em SEO/acessibilidade/performance.

## Cenário 6 — Segurança de configuração (FR-023 · SC-010)
```bash
ENVIRONMENT=production SECRET_KEY=your-secret-key-change-in-production uvicorn app.main:app
```
**Esperado**: a aplicação **falha rápido** ao iniciar (SECRET_KEY placeholder / `ALLOWED_HOSTS=*` em
produção). Erros de runtime nunca vazam stack trace/paths (FR-024).

## Testes automatizados (Constituição, Princípio III)
```bash
pytest                                   # contrato + integração + unidade
pytest --cov=app --cov-report=term-missing   # cobertura ≥ 80% (gate de CI)
ruff check app/ && black --check app/    # lint/format (gates de CI)
```
**Esperado**: suíte verde; cobertura ≥ 80%; testes de contrato cobrindo status/schema/erro de cada
endpoint público; teste de regressão para a config insegura (FR-023).
