# Guia de Contribuição

Que bom te ver por aqui! 🎉 A **BNCC API** é um projeto público, gratuito e open-source, e
contribuições são muito bem-vindas — seja código, correção de dados, documentação ou só um bom
relato de bug, tudo ajuda quem constrói educação no Brasil.

Este guia é o documento completo para contribuir. Antes de começar, leia também:

- O **[Código de Conduta](CODE_OF_CONDUCT.md)** — participar do projeto significa concordar com ele.
- A **[Política de Segurança](SECURITY.md)** — falhas de segurança **não** vão para issues públicas.
- A **[Constituição](.specify/memory/constitution.md)** — os princípios não-negociáveis (I a VII)
  que governam este projeto. Suas contribuições precisam respeitá-los, e este guia mostra como.

---

## 🧭 Antes de escrever código

- **Abra ou encontre uma issue primeiro.** Para mudanças não triviais, alinhe a proposta em uma
  issue antes de investir tempo. Isso evita retrabalho e garante que a mudança faça sentido para o
  contrato público.
- **Divergência de dado BNCC?** Se você encontrou diferença entre o que a API retorna e o documento
  oficial, **não corrija direto no PR sem contexto**: abra uma issue pelo template
  *"Divergência de dado BNCC"*. A fidelidade aos dados oficiais (Princípio IV) é prioridade máxima e
  toda correção precisa apontar a fonte oficial.
- **Boas primeiras contribuições:** melhorias de documentação, novos exemplos de uso, testes
  adicionais e validação de cobertura dos dados da BNCC.

---

## 🔀 Fluxo de trabalho (fork → branch → PR)

1. Faça um **fork** do repositório e clone o seu fork.
2. Crie uma branch a partir de `main` seguindo a **convenção de nomes**:
   - `feat/` — nova funcionalidade (ex.: `feat/filtro-por-eixo`)
   - `fix/` — correção de bug (ex.: `fix/paginacao-habilidades`)
   - `docs/` — documentação (ex.: `docs/exemplos-curl`)
   - `test/`, `refactor/`, `chore/` — quando fizer sentido
3. Faça suas mudanças **com testes** (ver seção de qualidade).
4. Rode os portões locais antes de subir (ver abaixo).
5. Faça commit e push na sua branch.
6. Abra um **Pull Request** contra `main`, preenchendo o template de PR (o checklist de conformidade
   constitucional é obrigatório).

Mensagens de commit no estilo [Conventional Commits](https://www.conventionalcommits.org/pt-br/)
(`feat:`, `fix:`, `docs:`…) são apreciadas, mas não obrigatórias.

---

## 💻 Setup do ambiente local

Pré-requisitos: **Python 3.11+**. O snapshot `data/bncc_v1.json` já vem versionado — **você não
precisa dos PDFs** para rodar a API.

```bash
git clone https://github.com/<seu-usuario>/bncc_api.git
cd bncc_api

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate        # Linux/Mac

pip install -r requirements.txt
cp .env.example .env              # ajuste se quiser

alembic upgrade head              # cria o banco da plataforma (contas/keys/uso)
uvicorn app.main:app --reload     # sobe em http://localhost:8000
```

A busca com IA é **opcional**: sem chaves de LLM, os endpoints determinísticos funcionam
normalmente; só a `/busca-semantica` fica indisponível.

---

## 🧪 Qualidade e portões de CI

Estes são os mesmos portões que o CI executa. **Um PR só é mergeado se todos passarem** — rode-os
localmente antes de abrir o PR:

```bash
pytest --cov=app --cov-report=term-missing   # testes + cobertura (gate ≥ 80%)
ruff check app/ scripts/ tests/              # lint
black --check app/ scripts/ tests/           # formatação
mypy app/                                     # tipos (código novo)
pre-commit run --all-files                    # portões locais (segredos via detect-secrets, lint, format)
```

Resumo dos portões bloqueantes:

| Portão | Regra |
|---|---|
| **Testes** | Suíte `pytest` verde |
| **Cobertura** | **≥ 80%** de linhas (Princípio III) — um PR não pode derrubar a cobertura abaixo disso |
| **Lint** | `ruff check` sem erros |
| **Formatação** | `black --check` sem diferenças |
| **Tipos** | `mypy` limpo em código novo |
| **Segredos** | `pre-commit` (detect-secrets) — nada de credenciais commitadas |

---

## 📐 Regras do projeto (da Constituição)

Estas regras não são burocracia — elas mantêm a API confiável para quem depende dela. O checklist do
PR cobre cada uma:

### Princípio I — Contrato primeiro, sem quebra dentro da versão

- O contrato OpenAPI é a fonte da verdade. Todo endpoint público deve ser tipado com Pydantic e
  aparecer na documentação gerada.
- **Não quebre o contrato `/api/v1`.** Remoção/renomeação de campo, mudança de tipo, mudança de
  semântica ou novo campo obrigatório em request são **proibidos** dentro da versão publicada.
  Mudanças incompatíveis exigem uma **nova versão de caminho** (ex.: `/api/v2`).
- Adições retrocompatíveis (novos endpoints, campos opcionais) são bem-vindas.
- **Mexeu na superfície pública?** Atualize o **[CHANGELOG](CHANGELOG.md)** (formato
  [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)).

### Princípio III — Testes primeiro

- Todo endpoint público precisa de **testes de contrato** (status, formato de resposta, erros).
- **Correção de bug exige teste de regressão**: um teste que **falha antes** da correção e **passa
  depois**. PR de bugfix sem teste de regressão não é aceito.

### Princípio IV — Fidelidade dos dados da BNCC

- Códigos, competências, componentes e etapas devem preservar a nomenclatura e a estrutura oficiais.
- Transformações de dados (`scripts/`) devem ser **determinísticas, versionadas e reproduzíveis** a
  partir das fontes em `data/`.
- Campos derivados/enriquecidos (embeddings, resumos de IA) devem ser claramente distinguíveis do
  dado oficial na resposta.
- **Divergência com a fonte é defeito de correção**, não de estilo — abra o template de
  *Divergência de dado BNCC* apontando página/documento oficial.

### Princípio V — Segurança por padrão

- Todo input é validado por schema Pydantic na fronteira; parâmetros que alimentam busca/LLM são
  sanitizados e limitados.
- **Nunca commite segredos.** `SECRET_KEY`, chaves de LLM e afins vêm do ambiente.
- Falhas de segurança seguem a [Política de Segurança](SECURITY.md), não issues públicas.

---

## ✅ Checklist antes de abrir o PR

- [ ] Testes incluídos e cobertura **≥ 80%** mantida.
- [ ] `ruff`, `black --check` e `mypy` limpos; `pre-commit` verde.
- [ ] Não quebra o contrato `/api/v1` (ou fez bump de versão).
- [ ] `CHANGELOG.md` atualizado se a superfície pública mudou.
- [ ] Dados BNCC preservam fidelidade à fonte oficial.
- [ ] Nenhum segredo commitado.

---

## 🤝 Dúvidas

Abra uma issue com o template de *sugestão de melhoria* ou de *bug*, conforme o caso. Obrigado por
contribuir — cada melhoria ajuda quem constrói educação no Brasil. 💚
