# Feature Specification: Plataforma Pública da BNCC API

**Feature Branch**: `001-public-api-platform`

**Created**: 2026-07-03

**Status**: Draft

**Input**: User description: "aderece esse desalinhamento da constituição e também: precisamos de uma api pública mas com controle/login para uso, um material de documentação da api (criado automaticamente) e uma landing page focada em SEO para apresentar a solução. Será uma API da BNCC (Base Nacional Comum Curricular). Precisamos arquiteturar essa api com base na lógica da BNCC, para isso precisamos estudar exaustivamente os materiais (em maioria pdfs) da BNCC. Design sofisticado, minimalista para tudo. É preciso entender exaustivamente toda a BNCC para então pensar na melhor forma de gerar valor nas features possíveis"

## Overview

Transformar a BNCC API em um produto público real: uma plataforma que expõe **toda** a Base
Nacional Comum Curricular do Brasil — modelada fielmente na lógica oficial do documento — de forma
programática, com controle de acesso self-service para desenvolvedores, busca semântica em
linguagem natural, documentação interativa gerada automaticamente e uma landing page de
apresentação com foco em SEO. Todas as superfícies visuais adotam um design sofisticado e
minimalista.

Esta é a versão de **lançamento público (v1)**. A fundação de tudo é o entendimento exaustivo da
BNCC: a estrutura de dados e a arquitetura da API derivam da própria taxonomia da Base (etapas,
áreas, componentes, unidades temáticas, competências e habilidades), não de um modelo arbitrário.

## Clarifications

### Session 2026-07-03

> As respostas abaixo foram resolvidas com os **valores recomendados** (padrões de menor escopo e
> risco) por ausência de resposta interativa; podem ser revistas antes do `/speckit-plan`.

- Q: Limite de requisições do tier gratuito para endpoints determinísticos? → A: **60 req/min por
  API key** (com pequeno burst permitido).
- Q: Como limitar o uso da busca semântica com IA (custo de LLM) no tier gratuito? → A: **Cota
  separada e menor para IA** (~20 req/min + teto diário), medida à parte dos endpoints
  determinísticos.
- Q: Como tratar versionamento/atualização dos dados da BNCC no v1? → A: **Snapshot estático
  versionado** — uma versão publicada, re-extração reproduzível gera novo release (sem
  atualização em runtime).
- Q: Como os desenvolvedores fazem login no portal? → A: **E-mail + senha com verificação de
  e-mail** obrigatória.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consumir a BNCC completa via API estruturada (Priority: P1)

Um desenvolvedor de uma aplicação educacional precisa acessar programaticamente qualquer parte da
BNCC — competências gerais, competências específicas, habilidades por etapa/ano/componente,
objetos de conhecimento, campos de experiência da Educação Infantil e habilidades dos itinerários
do Ensino Médio — com os códigos e textos oficiais preservados e as relações entre esses elementos
navegáveis.

**Why this priority**: É o núcleo de valor. Sem a BNCC completa, correta e modelada na lógica
oficial, nenhuma outra funcionalidade (busca, docs, landing) tem sobre o que operar. Hoje a base de
dados contém apenas uma amostra ínfima (~11 habilidades) frente às ~1.700+ habilidades reais — a
extração exaustiva dos PDFs oficiais é pré-requisito.

**Independent Test**: Consultar a API por qualquer código de habilidade/competência válido e por
filtros (etapa, ano, área, componente, competência geral) e verificar que os dados retornados
correspondem exatamente ao documento oficial da BNCC, incluindo cobertura das três etapas.

**Acceptance Scenarios**:

1. **Given** a base de dados carregada com a BNCC completa, **When** o desenvolvedor solicita uma
   habilidade pelo código oficial (ex.: `EF05MA07`, `EM13MAT101`, `EI03EO01`), **Then** a API
   retorna a descrição oficial e os metadados estruturados (etapa, ano(s), área, componente,
   objeto(s) de conhecimento, competências relacionadas).
2. **Given** a base completa, **When** o desenvolvedor filtra habilidades por etapa=ensino_médio e
   componente, **Then** a API retorna a lista paginada de todas as habilidades correspondentes.
3. **Given** uma habilidade que referencia competências gerais e específicas, **When** o
   desenvolvedor a consulta, **Then** as relações permitem navegar até as competências referenciadas.
4. **Given** um código inexistente ou malformado, **When** consultado, **Then** a API responde com
   erro claro (não encontrado / requisição inválida) sem vazar detalhes internos.

---

### User Story 2 - Obter acesso controlado via portal self-service e API keys (Priority: P2)

Um desenvolvedor se cadastra em um portal, confirma o e-mail e gera suas próprias API keys para
autenticar as chamadas. O uso é gratuito, porém medido: cada key tem limite de requisições e
métricas de uso. Isso torna a API "pública, mas com controle".

**Why this priority**: A API precisa ser aberta ao público, mas o acesso deve ser identificado,
limitado e mensurável para proteger o serviço e viabilizar suporte e evolução. É o que diferencia
um endpoint exposto de um produto público operável.

**Independent Test**: Cadastrar uma conta, verificar e-mail, gerar uma API key, fazer chamadas
autenticadas com sucesso, e confirmar que chamadas sem key ou acima do limite são recusadas.

**Acceptance Scenarios**:

1. **Given** um visitante no portal, **When** ele se cadastra e confirma o e-mail, **Then** obtém
   acesso ao painel para gerar/revogar API keys.
2. **Given** uma API key válida, **When** usada em uma requisição, **Then** a chamada é autenticada
   e contabilizada no consumo da key.
3. **Given** uma requisição sem key ou com key inválida/revogada, **When** enviada, **Then** a API
   responde com erro de autenticação (401) e mensagem acionável.
4. **Given** uma key que excedeu o limite de requisições da janela, **When** faz nova chamada,
   **Then** a API responde com "limite excedido" (429) e informa quando o limite reseta.
5. **Given** um desenvolvedor autenticado, **When** acessa seu painel, **Then** vê o consumo
   recente e os limites atuais de cada key.

---

### User Story 3 - Explorar a API por documentação interativa gerada automaticamente (Priority: P3)

Qualquer pessoa acessa uma documentação sempre atualizada, gerada automaticamente a partir do
contrato da API, com descrição de cada endpoint, esquemas de request/response, exemplos e a
possibilidade de testar chamadas (usando sua API key). A documentação segue o mesmo design
sofisticado e minimalista do produto.

**Why this priority**: A adoção de uma API pública depende diretamente da qualidade e atualidade da
documentação. Gerada automaticamente, ela permanece fiel ao contrato (evita divergência docs↔API).

**Independent Test**: Abrir a documentação e confirmar que todos os endpoints públicos estão
listados com esquemas e exemplos, e que o "testar" executa uma chamada real autenticada.

**Acceptance Scenarios**:

1. **Given** a documentação publicada, **When** um endpoint é adicionado/alterado no contrato,
   **Then** a documentação reflete a mudança sem edição manual.
2. **Given** um usuário na documentação, **When** insere sua API key e executa um endpoint de
   exemplo, **Then** recebe a resposta real da API.
3. **Given** a documentação, **When** consultada, **Then** apresenta guia de início rápido
   (autenticação, primeiro request, limites de uso, versionamento).

---

### User Story 4 - Perguntar à BNCC em linguagem natural (busca semântica com IA) (Priority: P4)

Um desenvolvedor (ou aplicação) faz uma pergunta em linguagem natural — "quais habilidades de
matemática do 5º ano tratam de frações?" — e recebe uma resposta gerada com base nas habilidades
mais relevantes, sempre acompanhada das fontes oficiais (códigos das habilidades/competências
usadas) e seus scores de relevância.

**Why this priority**: Diferencia a plataforma de um simples repositório de dados: permite
"conversar" com a BNCC. Depende da fundação de dados (P1) e do controle de acesso (P2). Como
recurso aumentado por IA, deve degradar graciosamente sem comprometer os recursos determinísticos.

**Independent Test**: Enviar uma pergunta em linguagem natural e verificar que a resposta cita
fontes oficiais rastreáveis e que resultados irrelevantes abaixo do limiar de similaridade não são
apresentados como oficiais.

**Acceptance Scenarios**:

1. **Given** uma pergunta em linguagem natural válida, **When** enviada à busca semântica, **Then**
   a resposta inclui o texto gerado e a lista de fontes oficiais (códigos + relevância).
2. **Given** a camada de IA indisponível (LLM/embeddings fora do ar), **When** um usuário usa os
   endpoints determinísticos (busca por código/filtros), **Then** esses continuam funcionando
   normalmente.
3. **Given** uma pergunta sem correspondência relevante, **When** processada, **Then** a resposta
   indica ausência de resultados confiáveis em vez de inventar dados.
4. **Given** conteúdo gerado por IA, **When** retornado, **Then** é claramente distinguível dos
   dados oficiais da BNCC.

---

### User Story 5 - Descobrir e entender a solução por uma landing page com SEO (Priority: P5)

Um visitante (educador, gestor de produto, desenvolvedor) chega à landing page a partir de uma
busca orgânica e entende rapidamente o que é a plataforma, para quem serve, o que oferece e como
começar — com um caminho claro para o cadastro. A página é sofisticada, minimalista e otimizada
para SEO.

**Why this priority**: É o canal de aquisição e a vitrine pública. Depende de existir um produto
para apresentar (P1–P4), por isso vem depois, mas é essencial para o alcance da API pública.

**Independent Test**: Carregar a landing page e verificar presença de metadados de SEO,
performance/acessibilidade adequadas, conteúdo descritivo e CTA que leva ao cadastro.

**Acceptance Scenarios**:

1. **Given** um visitante orgânico, **When** acessa a landing page, **Then** encontra proposta de
   valor, principais recursos, público-alvo e um CTA claro para começar (cadastro/documentação).
2. **Given** um rastreador de busca, **When** indexa a página, **Then** encontra metadados
   apropriados (título, descrição, dados estruturados, sitemap, tags sociais/Open Graph).
3. **Given** a landing page, **When** avaliada por ferramentas padrão de qualidade web, **Then**
   atinge pontuações altas de SEO, acessibilidade e performance.

---

### Edge Cases

- **Dados oficiais ambíguos ou divergentes entre PDFs**: quando a extração encontrar
  inconsistências, o valor oficial prevalece e a discrepância é registrada como defeito de
  correção (não é "corrigida" silenciosamente).
- **Códigos de habilidade com formatos distintos por etapa** (Educação Infantil `EI##`, Ensino
  Fundamental `EF##`, Ensino Médio `EM13##`): a validação de código deve aceitar todos os padrões
  oficiais.
- **Rate limit atingido no meio de uma paginação**: o consumidor recebe 429 com orientação de
  retry, sem perder o estado já retornado.
- **API key revogada durante uso ativo**: chamadas subsequentes falham com 401 imediatamente.
- **Pergunta em linguagem natural muito curta, vazia ou excessivamente longa**: rejeitada por
  validação de entrada com mensagem clara.
- **Prompt de busca semântica contendo tentativa de injeção**: entrada sanitizada/limitada; a IA
  não expõe dados internos nem foge do escopo da BNCC.
- **Segredos de configuração ausentes em produção** (ex.: chave secreta padrão, CORS aberto): a
  aplicação não deve subir em produção com configuração insegura padrão.

## Requirements *(mandatory)*

### Functional Requirements

**Fundação de dados da BNCC (P1)**

- **FR-001**: O sistema DEVE conter a BNCC completa das três etapas — Educação Infantil, Ensino
  Fundamental (Anos Iniciais e Finais) e Ensino Médio — extraída dos materiais oficiais.
- **FR-002**: O sistema DEVE preservar fielmente códigos, textos e a estrutura oficiais (etapas,
  áreas de conhecimento, componentes curriculares, unidades temáticas, objetos de conhecimento,
  campos de experiência, competências gerais, competências específicas e habilidades).
- **FR-003**: O processo de extração/normalização dos dados DEVE ser determinístico, versionado e
  reproduzível a partir das fontes oficiais, com validação de completude e integridade. O v1 serve
  um **único snapshot estático versionado** da BNCC; atualizações geram um novo release (sem
  edição/atualização de dados em runtime).
- **FR-004**: Usuários MUST be able to consultar qualquer elemento por seu código oficial e listar
  elementos por filtros (etapa, ano, área, componente, competência geral), com paginação.
- **FR-005**: O sistema DEVE expor as relações entre elementos (ex.: habilidade → competências
  gerais/específicas; componente → unidades temáticas → objetos de conhecimento → habilidades) de
  forma navegável.
- **FR-006**: Campos derivados/enriquecidos (ex.: embeddings, resumos) DEVEM ser claramente
  distinguíveis dos dados oficiais nas respostas.

**Controle de acesso self-service (P2)**

- **FR-007**: Visitantes MUST be able to se cadastrar no portal com **e-mail e senha** e
  verificação de e-mail obrigatória antes de obter acesso funcional (geração de keys).
- **FR-008**: Desenvolvedores autenticados MUST be able to gerar, listar e revogar suas próprias
  API keys.
- **FR-009**: O sistema DEVE autenticar cada requisição à API por API key e recusar requisições
  sem key válida.
- **FR-010**: O sistema DEVE aplicar rate limiting por API key e responder com erro de limite
  excedido (incluindo quando o limite reseta) ao ultrapassá-lo. O limite padrão dos endpoints
  determinísticos é de **60 requisições/minuto por key** (com pequeno burst permitido).
- **FR-010a**: Os endpoints de busca semântica (IA) DEVEM ter **cota separada e mais restrita**
  (~20 requisições/minuto por key, com teto diário), medida independentemente da cota dos endpoints
  determinísticos, para conter o custo de LLM.
- **FR-011**: O sistema DEVE registrar métricas de uso por key e exibi-las ao desenvolvedor em um
  painel.
- **FR-012**: O acesso DEVE ser gratuito em um único nível (tier), sem cobrança/billing nesta
  versão.

**Documentação automática (P3)**

- **FR-013**: O sistema DEVE gerar automaticamente a documentação interativa a partir do contrato
  da API, mantendo-a sincronizada sem edição manual.
- **FR-014**: A documentação DEVE listar todos os endpoints públicos com esquemas de
  request/response, exemplos e comportamento de erro.
- **FR-015**: A documentação DEVE permitir testar chamadas reais autenticadas com a API key do
  usuário e incluir um guia de início rápido (autenticação, limites, versionamento).

**Busca semântica com IA (P4)**

- **FR-016**: O sistema DEVE responder perguntas em linguagem natural retornando texto gerado
  acompanhado das fontes oficiais utilizadas (códigos + score de relevância).
- **FR-017**: Resultados abaixo do limiar de relevância NÃO DEVEM ser apresentados como oficiais;
  na ausência de correspondência confiável, o sistema DEVE indicá-lo em vez de inventar dados.
- **FR-018**: Os recursos determinísticos (busca por código/filtros) DEVEM permanecer funcionais
  quando a camada de IA estiver indisponível (degradação graciosa).
- **FR-019**: Entradas de busca semântica DEVEM ser validadas e sanitizadas (tamanho, tipo,
  conteúdo) e as chamadas de IA DEVEM ter limites explícitos de custo (tokens/latência), além da
  cota separada definida em FR-010a.

**Landing page com SEO (P5)**

- **FR-020**: O sistema DEVE oferecer uma landing page pública que apresente proposta de valor,
  recursos, público-alvo e um CTA para cadastro/documentação.
- **FR-021**: A landing page DEVE incluir os metadados de SEO essenciais (título, descrição, dados
  estruturados, sitemap, tags Open Graph/sociais) e ser indexável.

**Design e segurança transversais**

- **FR-022**: Todas as superfícies visuais (landing page, portal do desenvolvedor, documentação)
  DEVEM seguir um design sofisticado e minimalista consistente.
- **FR-023**: A aplicação NÃO DEVE iniciar em ambiente de produção com configuração insegura padrão
  (ex.: chave secreta padrão, CORS totalmente aberto); segredos DEVEM vir do ambiente e a origem
  de requisições DEVE ser restrita em produção. *(Corrige o desalinhamento com a constituição —
  Princípio V — identificado na configuração atual.)*
- **FR-024**: Respostas de erro em todas as superfícies NÃO DEVEM vazar stack traces, caminhos
  internos ou detalhes de infraestrutura.
- **FR-025**: A API pública DEVE ser versionada; mudanças incompatíveis DEVEM gerar nova versão sem
  quebrar consumidores existentes.

### Key Entities *(inclui dados)*

- **Etapa de Ensino**: Educação Infantil, Ensino Fundamental (Anos Iniciais 1º–5º, Anos Finais
  6º–9º) e Ensino Médio; raiz da organização curricular.
- **Área de Conhecimento**: agrupamento oficial (Linguagens, Matemática, Ciências da Natureza,
  Ciências Humanas, Ensino Religioso) que reúne componentes.
- **Componente Curricular**: disciplina/componente dentro de uma área (ex.: Língua Portuguesa,
  Matemática, História).
- **Unidade Temática**: agrupamento temático dentro de um componente (Ensino Fundamental).
- **Objeto de Conhecimento**: conteúdo/conceito associado a habilidades dentro de unidades
  temáticas.
- **Campo de Experiência**: eixo organizador da Educação Infantil (ex.: "O eu, o outro e o nós"),
  com objetivos de aprendizagem e desenvolvimento associados.
- **Competência Geral**: uma das 10 competências gerais da BNCC, transversais a todas as etapas.
- **Competência Específica**: competência de uma área/componente/etapa, referenciada por
  habilidades.
- **Habilidade**: unidade central; possui código oficial, descrição, etapa, ano(s), componente e
  relações com competências e objetos de conhecimento. Inclui habilidades dos itinerários do
  Ensino Médio.
- **Conta de Desenvolvedor**: identidade cadastrada (com e-mail verificado) que possui API keys e
  visualiza seu consumo.
- **API Key**: credencial pertencente a uma conta, usada para autenticar e medir requisições;
  possui estado (ativa/revogada) e limites associados.
- **Registro de Uso**: contabilização de requisições por key para rate limiting e métricas.
- **Fonte de Busca (Documento Fonte)**: referência oficial (código + tipo + relevância) citada nas
  respostas da busca semântica.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das habilidades e competências oficiais das três etapas da BNCC estão
  disponíveis e consultáveis pela API (cobertura verificada contra as fontes oficiais).
- **SC-002**: Uma amostra de auditoria de códigos oficiais retorna 100% de correspondência exata
  entre o texto servido pela API e o documento oficial.
- **SC-003**: Um novo desenvolvedor consegue, sem suporte humano, ir do cadastro à primeira chamada
  autenticada bem-sucedida em menos de 10 minutos.
- **SC-004**: Requisições sem autenticação válida ou acima do limite são recusadas em 100% dos
  casos, com mensagem acionável.
- **SC-005**: 95% das consultas determinísticas (por código/filtros) retornam resultado
  praticamente instantâneo do ponto de vista do usuário sob carga nominal.
- **SC-006**: 100% das respostas da busca semântica que citam habilidades apresentam fontes
  oficiais rastreáveis; nenhuma resposta apresenta conteúdo gerado como se fosse dado oficial.
- **SC-007**: A documentação reflete 100% dos endpoints públicos e permanece sincronizada com o
  contrato sem intervenção manual.
- **SC-008**: A landing page atinge pontuação alta (≥ 90) em SEO, acessibilidade e performance em
  auditoria padrão de qualidade web.
- **SC-009**: A indisponibilidade da camada de IA não afeta a disponibilidade dos endpoints
  determinísticos (0% de degradação nos recursos determinísticos durante falha de IA).
- **SC-010**: Nenhuma configuração insegura padrão permite a inicialização em produção
  (verificado por checagem de configuração).
- **SC-011**: Uma key que excede o limite (60/min determinístico ou ~20/min de IA) recebe resposta
  de limite excedido em 100% das vezes, com indicação de reset; requisições dentro do limite nunca
  são bloqueadas indevidamente.

## Assumptions

- **Modelo de acesso**: portal self-service com API keys (Bearer), gratuito em um único tier, com
  rate limiting e analytics por key — sem integração de pagamento/billing nesta versão (decisão
  confirmada com o solicitante). Login no portal por **e-mail + senha** com verificação de e-mail.
- **Limites do tier gratuito**: **60 req/min** por key nos endpoints determinísticos e **cota
  separada ~20 req/min + teto diário** para a busca semântica com IA (ver FR-010/FR-010a).
- **Versionamento de dados**: v1 serve um **snapshot estático versionado** da BNCC; atualização é
  um novo release (sem atualização em runtime).
- **IA no v1**: a busca semântica em linguagem natural faz parte deste lançamento (decisão
  confirmada), tratada como camada aumentada e opcional em relação aos recursos determinísticos.
- **Fonte da verdade dos dados**: os materiais oficiais da BNCC (PDFs de Ensino Fundamental e
  Ensino Médio já presentes em `data/`, mais a fonte oficial de Educação Infantil) são a base para
  extração exaustiva; a amostra atual (~11 habilidades) é placeholder e será substituída.
- **Escopo de conteúdo**: "toda a BNCC" inclui Educação Infantil, Ensino Fundamental e Ensino
  Médio (incluindo habilidades dos itinerários formativos quando disponíveis nas fontes oficiais).
- **Design**: um único sistema visual sofisticado e minimalista é aplicado de forma consistente à
  landing page, ao portal do desenvolvedor e à documentação.
- **Idioma**: conteúdo e dados primariamente em português (pt-BR), coerente com o documento da BNCC.
- **Verificação de e-mail**: o cadastro exige confirmação de e-mail antes de liberar geração de
  keys, como padrão de segurança.
- **Fora de escopo nesta versão**: cobrança/planos pagos, SSO corporativo, o servidor MCP (fase
  posterior, reutilizando os mesmos serviços de domínio), e integrações específicas de terceiros.

## Dependencies

- Disponibilidade dos materiais oficiais da BNCC em formato processável (PDFs e/ou fontes
  estruturadas) para todas as três etapas.
- Provedor de modelo de linguagem/embeddings para a busca semântica (com limites de custo e
  fallback determinístico).
- Serviço de envio de e-mail para verificação de cadastro.
