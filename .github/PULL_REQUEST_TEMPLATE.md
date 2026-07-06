<!--
Obrigado por contribuir com a BNCC API! 💚
Preencha a descrição e marque o checklist de conformidade constitucional.
Leia o CONTRIBUTING.md se ainda não leu: ../blob/main/CONTRIBUTING.md
-->

## Descrição

<!-- O que este PR faz e por quê. Descreva a mudança de forma clara. -->

## Issue relacionada

<!-- Ex.: Closes #123. Se não houver issue, explique o contexto. -->

## Tipo de mudança

- [ ] 🐛 Correção de bug
- [ ] ✨ Nova funcionalidade
- [ ] 📐 Correção de fidelidade de dado BNCC
- [ ] 📚 Documentação
- [ ] ♻️ Refatoração / manutenção (sem mudança de comportamento público)

## Checklist de conformidade constitucional

> Baseado na [Constituição](../blob/main/.specify/memory/constitution.md) do projeto. Todos os itens
> aplicáveis devem estar marcados antes do merge.

- [ ] **Testes incluídos** e a cobertura **≥ 80%** foi mantida (Princípio III). Bugfix inclui **teste de regressão** que falha antes e passa depois.
- [ ] `ruff check`, `black --check` e `mypy` estão **limpos**; `pre-commit` passou.
- [ ] **Não quebra o contrato `/api/v1`** — ou, se quebra, foi feito **bump de versão** de caminho (Princípio I).
- [ ] **CHANGELOG atualizado** se houve mudança na superfície pública (Princípio I).
- [ ] **Dados da BNCC preservam fidelidade** à fonte oficial; derivados de IA seguem marcados como não-oficiais (Princípio IV).
- [ ] **Nenhum segredo commitado** (chaves, `SECRET_KEY`, credenciais) — configuração vem do ambiente (Princípio V).

## Notas para revisão

<!-- Qualquer detalhe que ajude quem for revisar: decisões de design, trade-offs, o que testar manualmente. -->
