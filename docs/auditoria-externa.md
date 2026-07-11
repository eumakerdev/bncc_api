# Auditoria externa e incremental de fidelidade da BNCC

Fluxo **repetível, externo, agêntico e incremental** para auditar a fidelidade das
descrições servidas pela API contra **fontes independentes** — cobrindo o corpus
(~1.717 habilidades) **aos poucos**, ao longo do tempo. Governado pela Constituição
(`.specify/memory/constitution.md`, Princípio IV — *Fidelidade dos dados* — e
Princípio VII — *IA como camada não confiável, nunca dado oficial*).

> **Este fluxo NÃO altera dados.** Ele produz **relatórios em Markdown** para
> decisão humana. Uma correção só entra no snapshot depois de aprovada, pelo fluxo
> existente `scripts/reconcile_bncc_descriptions.py` (chaveado por código,
> idempotente). Nenhuma fonte é tratada como verdade final.

## Onde isto se encaixa

Já existiam três defesas de fidelidade, todas *internas* ou *de uma só vez*:

| Ferramenta | O que faz | Limite |
|---|---|---|
| `scripts/audit_extraction.py` | qualidade do texto por assinaturas internas | auto-referencial (só olha o próprio snapshot) |
| `scripts/validate_bncc_coverage.py` | códigos/contagens/integridade referencial | não olha o *conteúdo* das descrições |
| `scripts/reconcile_bncc_descriptions.py` + `bncc_description_fixes.json` | correções adjudicadas contra 2 testemunhas | rodado **uma vez** (auditoria 2026-07-06), manual |

Esta auditoria externa fecha a lacuna: cruza **cada** habilidade contra testemunhas
**independentes**, de forma **repetível e incremental**, e entrega relatórios.

## O fluxo de uma boa auditoria (as etapas)

1. **Selecionar um lote** de habilidades ainda não auditadas (rastreado no ledger).
2. **Coletar testemunhas** independentes de cada código (allowlist de fontes).
3. **Comparar deterministicamente** o texto do snapshot com cada testemunha
   (cobertura + similaridade). Classificar: concordante / divergente / sem fontes.
4. **Assessoria agêntica** nas divergências: um agente pesquisa o texto oficial,
   adjudica (defeito real do snapshot × ruído da testemunha × inconclusivo) e
   **propõe** correção no relatório — com citação e confiança.
5. **Revisão humana**: você decide. As correções aprovadas viram entradas em
   `scripts/bncc_description_fixes.json` e entram pelo `reconcile`.
6. **Registrar progresso** no ledger e no índice `PROGRESSO.md`; repetir com o
   próximo lote (cobertura do corpus cresce ao longo do tempo).

## Componentes

```
scripts/audit/engine.py           # comparação determinística (cobertura/similaridade)
scripts/audit/sources/            # adaptadores de fonte (allowlist)
  arbiter_pdf.py                  #   PDF oficial homologado (árbitro EI/EF)
  bncc_mcp_csv.py                 #   CSV github.com/dfdb76/bncc-mcp (2ª testemunha)
  mec_portal.py                   #   Portal BNCC/MEC (online + cache; a confirmar)
scripts/audit_external.py         # CLI: lote → relatório + ledger + PROGRESSO
audit/
  ledger.json                     # estado por código (versionado)
  PROGRESSO.md                    # índice legível (gerado)
  relatorios/                     # relatórios .md por lote (versionados)
  fontes/bncc_mcp/                # CSVs vendorizados (offline; ver bootstrap)
  cache/                          # respostas de fontes (gitignored)
.claude/agents/bncc-auditor.md    # o agente assessor
```

### Métrica de fidelidade: **cobertura**

A classificação usa **cobertura** = fração do texto do snapshot que está sustentada
pela testemunha (soma dos blocos casados ÷ tamanho do snapshot, via
`difflib.SequenceMatcher`). Ela responde à pergunta certa — *"o texto oficial que
servimos está presente na fonte?"* — e **tolera bleed de coluna** na extração da
testemunha (texto EXTRA na fonte não penaliza). A `similaridade` (razão simétrica)
é mostrada só como informação. Um código é **concordante** se a **melhor** fonte
cobre ≥ `--limiar` (padrão `0.92`); **divergente** se nenhuma fonte cobre; **sem
fontes** se nenhuma testemunha conhece o código.

## Como rodar

Use o Python do venv (traz `pdfplumber`/`pikepdf`/`httpx`):

```bash
# próximos 25 códigos não auditados (offline: só cache/arquivos locais)
venv/Scripts/python.exe scripts/audit_external.py --lote 25 --offline

# auditar códigos específicos
venv/Scripts/python.exe scripts/audit_external.py --codigos EF01CI04,EF02LP28

# revisitar já auditados (ex.: após vendorizar uma nova fonte)
venv/Scripts/python.exe scripts/audit_external.py --lote 25 --reauditar
```

Saída: `audit/relatorios/AAAA-MM-DD-lote-NNNN.md` + `audit/ledger.json` +
`audit/PROGRESSO.md` atualizados. Exit code é `0` mesmo com divergências (são
achados, não erros). A **primeira** execução extrai o texto do árbitro (~1 min) e o
cacheia em `audit/cache/arbiter_pdf.json`; as seguintes leem o cache.

### Passo agêntico (assessor)

Depois de gerar um lote, acione o agente sobre o relatório para enriquecer as
divergências (ele só edita o `.md`, nunca `data/`):

> Use o subagente `bncc-auditor` no relatório `audit/relatorios/2026-07-11-lote-0001.md`.

Para cobrir o corpus **aos poucos**, encadeie via `/loop` (um lote por iteração):

> `/loop venv/Scripts/python.exe scripts/audit_external.py --lote 25 --offline` e
> depois acione `bncc-auditor` no relatório mais novo.

## Bootstrap das fontes (uma vez)

- **Árbitro (EI/EF)** — já disponível: `data/BNCC_EI_EF_110518_versaofinal_site.pdf`
  (o adaptador normaliza com pikepdf e cacheia). Não cobre o **Complemento de
  Computação** (`*CO*`) — esses códigos aparecem como *sem fontes* até haver uma
  testemunha própria.
- **CSV bncc-mcp (2ª testemunha, e referência de EM)** — baixe os CSVs de
  `github.com/dfdb76/bncc-mcp` para `audit/fontes/bncc_mcp/`. O adaptador detecta as
  colunas de código e descrição pelo cabeçalho automaticamente.
- **Portal MEC** — dirigido por cache (`audit/cache/mec_portal/{codigo}.json`). O
  gancho `MecPortalSource._coletar` está pronto para receber a coleta online quando
  uma fonte por código for confirmada; enquanto isso, opera só sobre cache semeado.

## Aplicando uma correção aprovada (decisão humana)

1. No relatório, revise a **Proposta de correção** do agente e a citação.
2. Copie a entrada aprovada para `scripts/bncc_description_fixes.json` (formato
   `{ "CODIGO": {"descricao": "...", "fonte": "...", "motivo": "..."} }`).
3. `venv/Scripts/python.exe scripts/reconcile_bncc_descriptions.py` (idempotente).
4. Rode os portões: `pytest tests/contract/test_audit_extraction.py` e
   `python scripts/validate_bncc_coverage.py`.

## Princípios em jogo

- **IV — Fidelidade**: a comparação é determinística, versionada e reproduzível
  (cache offline); discrepâncias são tratadas como defeitos de correção.
- **VII — IA não confiável**: o agente **propõe**; nada de IA vira dado oficial sem
  adjudicação contra o árbitro e decisão humana.
- **II — Camadas**: adaptadores isolam a infraestrutura (PDF/CSV/rede); o motor não
  faz I/O de rede e é testável em isolamento.
