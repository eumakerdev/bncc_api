<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0
Rationale: MINOR — redefinição material de uma restrição operacional (stack canônica):
LangChain é removido da stack de RAG. Nenhum princípio ou regra de governança foi
removido/redefinido (critério de MAJOR não atingido). Evidência: langchain/langchain-community
nunca foram importados no código (app/, scripts/, tests/) — o RAG real usa ChromaDB +
sentence-transformers diretamente. Os pinos legados (langchain==0.1.0) travavam a resolução
de dependências (numpy<2, packaging<24 → teto google-cloud-bigquery 3.30.0) e geravam
conflitos recorrentes nos PRs do Dependabot (ex.: PR #29).

Modified principles: nenhum (Princípios I–VII intactos)
Modified sections:
  - Padrões Técnicos & Restrições Operacionais: stack canônica de RAG passa de
    "sentence-transformers/LangChain" para "sentence-transformers" (uso direto, sem framework
    de orquestração).
Added sections: nenhuma
Removed sections: nenhuma

Templates requiring updates:
  ✅ .specify/templates/plan-template.md   (Constitution Check é genérico; alinhado — sem edição necessária)
  ✅ .specify/templates/spec-template.md   (sem referências a princípios; alinhado)
  ✅ .specify/templates/tasks-template.md   (categorias de tarefa cobrem testes/contrato/observabilidade; alinhado)
  ✅ CLAUDE.md                              (stack atualizada na mesma emenda)
  ✅ requirements.txt                       (langchain/langchain-community removidos; comentários atualizados)
  ✅ .github/dependabot.yml                 (ignores de langchain/bigquery removidos)
  ✅ .github/workflows/ci.yml               (comentário sobre stack de IA legada atualizado)
  ✅ docs/seguranca-endurecimento.md        (dívida da stack de IA atualizada)
  ⚠ specs/001-public-api-platform/{plan.md,tasks.md} — mencionam LangChain como registro
    histórico da feature entregue; não editados deliberadamente (snapshot do plano aprovado).

Follow-up TODOs: com o pino langchain removido, numpy/pandas/google-cloud-bigquery ficam
livres para o Dependabot propor upgrades (validados pelos portões de CI).
-->

# BNCC API Constitution

Esta constituição define os princípios inegociáveis que governam o design, a implementação e a
operação da **BNCC API** — uma API pública que expõe a Base Nacional Comum Curricular (BNCC) do
Brasil para ser consumida por aplicações de terceiros. Por ser um contrato público consumido por
sistemas que não controlamos, priorizamos **estabilidade, correção e confiança** acima de
conveniência de desenvolvimento.

## Core Principles

### I. Contrato Primeiro & Versionamento Explícito

A superfície pública da API é um contrato, não um detalhe de implementação.

- O contrato OpenAPI é a fonte da verdade. Todo endpoint público DEVE ter schema de
  request/response tipado (Pydantic) e aparecer na documentação gerada automaticamente.
- A API DEVE ser versionada no caminho (`/api/v1`, `/api/v2`). Mudanças incompatíveis
  (remoção/renomeação de campo, alteração de tipo, mudança de semântica, novo campo obrigatório
  em request) são PROIBIDAS dentro de uma versão já publicada.
- Mudanças incompatíveis DEVEM criar uma nova versão de caminho. A versão anterior DEVE
  permanecer funcional durante um período de depreciação mínimo de **6 meses**, sinalizado por
  cabeçalho `Deprecation` e documentado no CHANGELOG.
- Adições retrocompatíveis (novos endpoints, novos campos opcionais) são permitidas dentro da
  versão corrente.

**Racional:** Consumidores externos quebram silenciosamente quando o contrato muda. Versionar
explicitamente e tratar quebras como eventos de primeira classe é o que torna a API confiável
para terceiros.

### II. Arquitetura em Camadas & Inversão de Dependência

O código DEVE respeitar fronteiras claras entre camadas, com dependências apontando para dentro.

- Camadas obrigatórias: **API/roteadores** (`app/api`) → **serviços/domínio** (`app/services`) →
  **modelos/dados** (`app/models`, fontes de dados). Roteadores NÃO DEVEM conter regra de negócio;
  serviços NÃO DEVEM conhecer objetos HTTP (`Request`/`Response`).
- Dependências externas (ChromaDB, LLMs, provedores de embedding, sistema de arquivos) DEVEM ser
  acessadas por meio de abstrações/serviços injetáveis, nunca instanciadas diretamente dentro de
  handlers de endpoint. A injeção de dependências do FastAPI (`app/core/deps.py`) é o mecanismo
  padrão.
- Configuração DEVE vir de `Settings` (pydantic-settings) e de variáveis de ambiente. Segredos e
  valores de ambiente NÃO DEVEM ser hardcoded no código.

**Racional:** Fronteiras explícitas mantêm a lógica de negócio testável em isolamento e permitem
trocar infraestrutura (ex.: banco vetorial, provedor de LLM) sem reescrever a API.

### III. Testes em Primeiro Lugar (NÃO NEGOCIÁVEL)

Comportamento não coberto por teste é considerado inexistente.

- Todo endpoint público DEVE ter **testes de contrato** que validem status codes, formato de
  resposta e comportamento de erro contra o schema declarado.
- Regras de negócio em serviços DEVEM ter testes unitários; integrações entre camadas e com
  dependências externas DEVEM ter testes de integração (dependências externas mockadas ou em
  container de teste).
- A cobertura de testes DEVE ser mantida em **≥ 80%** de linhas; PRs que reduzam a cobertura
  abaixo desse limite NÃO DEVEM ser mergeados sem justificativa registrada.
- Correções de bug DEVEM incluir um teste de regressão que falha antes da correção e passa depois.

**Racional:** Uma API pública não pode regredir sem aviso. Testes de contrato são a rede de
segurança que garante que o Princípio I seja respeitado na prática.

### IV. Fidelidade e Integridade dos Dados da BNCC

Os dados servidos DEVEM refletir fielmente o documento oficial da BNCC.

- Códigos de habilidade, competências, componentes e etapas de ensino DEVEM preservar a
  nomenclatura e a estrutura oficiais. Transformações de dados (extração, normalização) DEVEM ser
  determinísticas, versionadas e reproduzíveis a partir das fontes em `data/`.
- Qualquer campo derivado ou enriquecido (ex.: embeddings, resumos gerados) DEVE ser claramente
  distinguível dos dados oficiais na resposta da API.
- Pipelines de ingestão/geração (`scripts/`) NÃO DEVEM alterar o significado do dado oficial;
  discrepâncias com a fonte são tratadas como defeitos de correção, não de estilo.

**Racional:** A API é uma fonte de autoridade educacional. Dados incorretos ou ambíguos propagam
erros a todas as aplicações consumidoras e minam a confiança no serviço.

### V. Segurança e Proteção por Padrão

Toda entrada é hostil até prova em contrário; nenhuma superfície pública fica desprotegida.

- Todo input DEVE ser validado por schema Pydantic na fronteira. Parâmetros que alimentam buscas,
  filtros ou prompts de LLM DEVEM ser sanitizados/limitados (tamanho, tipo, faixa).
- Rate limiting DEVE estar ativo em endpoints públicos. Endpoints de escrita ou administrativos,
  quando existirem, DEVEM exigir autenticação.
- Segredos (chaves de API de LLM, `SECRET_KEY`) DEVEM vir do ambiente e NUNCA ser commitados.
  CORS DEVE ser restrito por configuração em produção (`ALLOWED_HOSTS` != `*`).
- Respostas de erro NÃO DEVEM vazar stack traces, caminhos internos ou detalhes de infraestrutura
  ao consumidor.

**Racional:** Exposição pública amplia a superfície de ataque. Proteções por padrão evitam que
uma falha isolada vire incidente, e a integração com LLMs adiciona risco de injeção que precisa
ser contido na fronteira.

### VI. Observabilidade & Operabilidade

Se não pode ser observado, não pode ser operado.

- Logging DEVE ser estruturado e não conter dados sensíveis (segredos, PII). Todo erro tratado
  DEVE ser logado com contexto suficiente para diagnóstico.
- A API DEVE expor endpoints de saúde (`health`/`readiness`) que reflitam o estado de dependências
  críticas (ex.: banco vetorial inicializado).
- Falhas de dependências externas (LLM indisponível, timeout de embedding) DEVEM ser tratadas
  explicitamente e retornar erros claros e acionáveis — nunca uma exceção não tratada (500 opaco).

**Racional:** Um serviço público precisa ser diagnosticável em produção sem depender de acesso ao
processo. Health checks e logs estruturados são pré-requisito para deploy e monitoramento
confiáveis.

### VII. Simplicidade e Determinismo sobre a Camada de IA

A busca semântica e os LLMs aumentam a API, mas não podem comprometer sua previsibilidade.

- Recursos determinísticos (busca por código, filtros estruturados, listagens) DEVEM funcionar de
  forma independente da disponibilidade de LLMs ou embeddings. A indisponibilidade da camada de IA
  DEVE degradar graciosamente, não derrubar a API.
- Complexidade adicional (novo serviço, nova dependência, novo padrão) DEVE ser justificada por um
  requisito concreto; na dúvida, aplica-se YAGNI e escolhe-se a solução mais simples que satisfaça
  o contrato.
- Saídas geradas por IA DEVEM ser tratadas como não confiáveis: validadas, limitadas em custo
  (tokens/latência) e nunca expostas como dado oficial (ver Princípio IV).

**Racional:** Recursos de IA agregam valor mas introduzem custo, latência e não determinismo.
Isolá-los garante que o núcleo da API permaneça rápido, barato e confiável.

## Padrões Técnicos & Restrições Operacionais

- **Stack canônica:** Python 3.11+, FastAPI, Pydantic v2, ChromaDB (banco vetorial),
  sentence-transformers para RAG (uso direto, sem framework de orquestração), Docker +
  Docker Compose para empacotamento. Substituições de componentes estruturais exigem emenda
  a esta constituição.
- **Qualidade de código:** `ruff` e `black` DEVEM passar sem erros; `mypy` DEVERIA passar em
  código novo. Formatação e lint são portões automatizados, não sugestões.
- **Desempenho:** endpoints determinísticos DEVERIAM responder em p95 < 300ms sob carga nominal.
  Endpoints que envolvem LLM DEVEM ter timeout explícito e limite de tokens configurável.
- **Compatibilidade & interoperabilidade:** respostas DEVEM ser JSON estável; o servidor MCP,
  quando publicado, DEVE consumir os mesmos serviços de domínio da API REST, sem duplicar regra de
  negócio.

## Fluxo de Desenvolvimento & Portões de Qualidade

- **Portões de CI (bloqueantes para merge):** suíte de testes verde, cobertura ≥ 80%, `ruff` e
  `black` limpos, build da imagem Docker bem-sucedido.
- **Code review:** todo PR DEVE ser revisado e DEVE verificar conformidade com esta constituição.
  O revisor DEVE recusar mudanças que quebrem o contrato público sem bump de versão (Princípio I).
- **Documentação:** mudanças na superfície pública DEVEM atualizar o OpenAPI (automático) e o
  CHANGELOG; depreciações DEVEM ser anunciadas antes da remoção.
- **Migrações de dados:** mudanças no pipeline de extração/embeddings DEVEM ser reproduzíveis e
  acompanhadas de validação contra a fonte oficial (Princípio IV).

## Governança

Esta constituição **supersede** quaisquer outras práticas ou convenções em conflito. Em caso de
divergência entre um princípio aqui e uma decisão pontual de implementação, o princípio prevalece
até que seja formalmente emendado.

- **Emendas:** propostas por PR que descreva a mudança, o racional e o impacto nos consumidores e
  nos templates dependentes (`.specify/templates/`). Uma emenda só é válida após revisão e
  aprovação registradas.
- **Versionamento desta constituição (SemVer):**
  - **MAJOR** — remoção ou redefinição incompatível de um princípio ou regra de governança.
  - **MINOR** — adição de um novo princípio/seção ou expansão material de guidance existente.
  - **PATCH** — esclarecimentos, correções de redação e refinamentos não semânticos.
- **Conformidade:** revisões de PR e planos de feature DEVEM validar aderência aos princípios. Toda
  complexidade que aparente violar um princípio DEVE ser justificada explicitamente (ex.: seção de
  Complexity Tracking do plano) ou ser rejeitada.
- **Guidance de runtime:** orientações operacionais e de desenvolvimento do dia a dia residem no
  `README.md` e nos artefatos gerados pelo Spec Kit; esta constituição define os limites que essas
  orientações NÃO PODEM violar.

**Version**: 1.1.0 | **Ratified**: 2026-07-03 | **Last Amended**: 2026-07-13
