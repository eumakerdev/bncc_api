# Política de Segurança

Obrigado por ajudar a manter a **BNCC API** segura. 🛡️

A segurança não é um recurso opcional deste projeto — é um princípio fundador. A
[Constituição](.specify/memory/constitution.md) estabelece, no **Princípio V (Segurança e Proteção
por Padrão)**, que toda entrada é hostil até prova em contrário e que nenhuma superfície pública fica
desprotegida. A divulgação responsável de falhas é parte desse compromisso.

## Versões suportadas

Este é um projeto em evolução contínua. Recebem correções de segurança:

| Versão | Suportada |
|---|---|
| `v1` (contrato `/api/v1`, branch `main`) | ✅ Sim |
| Versões anteriores ao contrato `v1` publicado | ❌ Não |

Sempre que possível, atualize para a versão mais recente da branch `main` antes de reportar, para
confirmar que a falha ainda não foi corrigida.

## Como reportar uma vulnerabilidade

**Não abra uma issue pública para vulnerabilidades de segurança.** Issues são visíveis a qualquer
pessoa e podem expor usuários da API antes que uma correção esteja disponível.

Em vez disso, use um destes canais **privados**:

1. **E-mail (preferencial):** envie os detalhes para **fabio@expertia.dev.br**.
2. **GitHub Security Advisories:** use o botão *"Report a vulnerability"* na aba
   **Security** do repositório ([github.com/eumakerdev/bncc_api/security](https://github.com/eumakerdev/bncc_api/security/advisories)),
   que abre um canal privado com o mantenedor.

### O que incluir no relatório

Quanto mais completo o relatório, mais rápida a correção:

- **Descrição** clara da falha e do impacto potencial (ex.: vazamento de dados, negação de serviço,
  bypass de autenticação, injeção em prompt de LLM).
- **Passos para reproduzir** — requisição(ões) exata(s), endpoint afetado, payload e cabeçalhos.
- **Versão/ambiente** onde a falha foi observada (commit, ambiente local ou `bncc.api.br`).
- **Prova de conceito** (se houver) e a mitigação que você sugere, caso tenha uma.

Se a falha envolver **segredos, credenciais ou dados sensíveis**, não os inclua em texto claro em
canais que não sejam os privados acima.

## O que esperar

- **Primeira resposta:** nosso prazo-alvo é **até 72 horas** para confirmar o recebimento do
  relatório.
- **Triagem e correção:** avaliaremos a severidade, manteremos você informado do progresso e
  trabalharemos numa correção. Falhas críticas têm prioridade sobre qualquer outro trabalho.
- **Divulgação coordenada:** pedimos que aguarde a publicação da correção antes de divulgar
  publicamente os detalhes. Daremos crédito ao autor do relatório (se você desejar) no CHANGELOG e
  no advisory correspondente.
- **Regressão:** conforme o **Princípio III** da Constituição, toda correção de segurança acompanha
  um **teste de regressão** que falha antes e passa depois — para que a falha não retorne
  silenciosamente.

## Escopo

Estão no escopo falhas na aplicação deste repositório: a API (`/api/v1`), o portal, a landing, os
pipelines de dados (`scripts/`) e a configuração de segurança (rate limiting, headers, autenticação
por API key, validação de entrada).

Estão **fora do escopo**: os documentos oficiais da BNCC em si (eventuais erros de conteúdo do
documento oficial do MEC não são falhas deste projeto) e serviços de terceiros não controlados por
nós. Divergências entre a API e o documento oficial da BNCC **não são vulnerabilidades** — elas são
tratadas como defeitos de fidelidade de dados (Princípio IV) e devem ser reportadas pelo template
público de *divergência de dado BNCC*.

Obrigado por praticar a divulgação responsável. 🙏
