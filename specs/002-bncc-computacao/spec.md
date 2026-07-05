# Feature 002 — Complemento de Computação à BNCC

**Estado:** implementado · **Etapas cobertas:** EI, EF, EM · **Fonte oficial:**
`data/BNCCComputaoCompletodiagramado (1).pdf` (Normas sobre Computação na Educação
Básica — Complemento à BNCC, Parecer CNE/CP nº 02/2022, homologado em 2022).

## Objetivo

Expor, com a mesma fidelidade e contrato do restante da BNCC, as **habilidades de
Computação** das três etapas, adicionadas pelo Complemento oficial. As habilidades
usam o par de letras oficial **`CO`** (Computação):

| Etapa | Códigos | Qtde. | Organização |
|---|---|---|---|
| Educação Infantil | `EI03CO01`–`EI03CO11` | 11 | por **eixo** |
| Ensino Fundamental | `EF01CO..`–`EF09CO..`, `EF15CO..`, `EF69CO..` | 103 | por **eixo** + objeto de conhecimento |
| Ensino Médio | `EM13CO01`–`EM13CO26` | 26 | por competência específica (sem eixo) |

**Total: 140 habilidades.** Três eixos na EI/EF: `pensamento_computacional`,
`mundo_digital`, `cultura_digital`.

## Requisitos

- **FR-C01 (Fidelidade — Princípio IV).** Extração determinística, versionada e
  reproduzível a partir do PDF oficial. A descrição servida é o texto **verbatim**
  da coluna HABILIDADE. O checksum SHA-256 da fonte é registrado no snapshot
  (`metadata.checksum_fontes.computacao`).
- **FR-C02 (Contrato — Princípio I).** As habilidades de Computação usam o mesmo
  schema `Habilidade`, com `area_conhecimento = componente = "computacao"` e um
  campo **opcional** novo `eixo` (EI/EF). Adições retrocompatíveis: novos valores
  de enum (`AreaConhecimento.COMPUTACAO`, `ComponenteCurricular.COMPUTACAO`,
  `EixoComputacao`) e um novo filtro opcional — **sem quebra** dentro de `/api/v1`.
- **FR-C03 (API).** `GET /api/v1/habilidades` aceita o filtro `eixo`; as
  habilidades de Computação são recuperáveis por código, por `componente=computacao`
  e por `eixo`. `metadata.contagens.computacao` traz totais por etapa e por eixo.
- **FR-C04 (Testes — Princípio III).** Testes de contrato do filtro `eixo` e da
  serialização; testes unitários dos helpers de extração; validação de cobertura
  estendida (`scripts/validate_bncc_coverage.py`).

## Fora de escopo (v1) — dívida registrada

As colunas **OBJETO DE CONHECIMENTO** (EF) e **COMPETÊNCIA ESPECÍFICA** (EM) são
células mescladas cujo recorte por coordenada ainda **não** é determinístico o
bastante (contaminação por cabeçalhos e por fragmentos do rótulo rotacionado de
eixo). Em respeito ao Princípio IV, **não são servidas** nesta versão — melhor
omitir do que servir dado incorreto. Reabrir quando houver um recorte confiável.

## Notas de extração (reprodutibilidade)

O documento diagramado guarda o texto das células **sem** caracteres de espaço
(espaçamento posicional). O extrator (`scripts/extract_bncc_computacao.py`):

1. recompõe as palavras por coordenada com `x_tolerance=1.5` (recupera os espaços);
2. isola a coluna HABILIDADE pela borda esquerda do código `(E..CO..)`;
3. lê o **eixo** dos rótulos — horizontais na EI, **rotacionados 90°** no EF
   (caracteres `upright=False`), casados por multiconjunto de letras (robusto ao
   intercalamento) — e o atribui a cada habilidade por proximidade vertical;
4. descarta blocos de EXEMPLOS/EXPLICAÇÃO e a referência cruzada `EM13MAT315`.

Reexecução: `python scripts/extract_bncc_data.py --validate` (regenera o snapshot
completo, incluindo Computação) e `python scripts/validate_bncc_coverage.py`.
