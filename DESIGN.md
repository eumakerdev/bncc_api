# Identidade visual — BNCC API

Documento único da marca. Se uma cor, um símbolo ou uma fonte aparecer em algum lugar do projeto
sem estar aqui, é divergência — não variação.

**Por que este arquivo existe:** em setembro de 2026 a marca tinha se fragmentado em **quatro
paletas paralelas** e **onze cópias divergentes do símbolo**, incluindo um mark no admin desenhado
com dois chevrons e sem o ponto do estudante. Nada quebrou — a marca só deixou de ser uma marca.
O portão `tests/contract/test_brand_consistency.py` existe para que isso não se repita.

---

## 1. O conceito

A leitura é da **bandeira do Brasil, em registro sóbrio**:

| Papel | Cor | Como aparece |
|---|---|---|
| **Superfície** | verde-bandeira | carrega bandas inteiras, botões, o símbolo |
| **Acento** | ouro | preenchimento, marcador, display — **nunca** texto sobre claro |
| **Dado** | azul-noite | segunda série de gráfico, categorias, âncora |
| **Substrato** | cinza-frio (matiz 258) | papel, superfícies, tinta |

Duas regras que sustentam o "sóbrio":

1. **Nunca os três em saturação cheia na mesma tela.** É o que separa identidade cívica de camisa
   de time.
2. **Os neutros são frios, não esverdeados.** Neutro tingido de verde lê como enjoado; verde
   saturado sobre cinza-frio é o pareamento que lê como sofisticado.

A estratégia é **COMMITTED**: o verde carrega superfície, não é só cor de botão.

---

## 2. Paleta

Fonte da verdade: `app/web/static/styles.css`. Tudo em OKLCH, exceto `--brand` e `--ground`,
fixados em hex porque `theme-color`, os `.svg` e o gerador de raster dependem do valor exato.

**Os números de contraste abaixo são medidos, não estimados.** Ao mexer em qualquer par, recalcule
e atualize o comentário no CSS — é a convenção do arquivo desde a primeira versão.

### Tema claro

| Token | Valor | Contraste medido |
|---|---|---|
| `--brand` | `#0a6b3c` | branco sobre: **6.60:1** |
| `--brand-lift` | `oklch(0.545 0.120 150)` | branco sobre: 4.69:1 |
| `--brand-deep` | `oklch(0.355 0.092 152)` | branco sobre: 10.64:1 |
| `--brand-deeper` | `oklch(0.245 0.062 154)` | branco sobre: 15.91:1 |
| `--brand-wash` | `oklch(0.962 0.022 150)` | `--ink` sobre: 15.80:1 |
| `--gold` | `oklch(0.828 0.145 88)` | sobre `--brand-deep`: 6.18:1 · **sobre papel: 1.67:1** |
| `--gold-deep` | `oklch(0.530 0.118 70)` | sobre papel: 5.31:1 |
| `--azul` | `oklch(0.410 0.140 262)` | branco sobre: 9.05:1 |
| `--azul-deep` | `oklch(0.300 0.130 264)` | branco sobre: 14.02:1 (≈ `#002776`) |
| `--ground` | `#0b120e` | branco sobre: 18.97:1 |
| `--ink` / `--ink-muted` / `--ink-subtle` | matiz 258 | 17.17 / 6.74 / **4.96** (piso do AA) |
| `--ok` | `oklch(0.500 0.096 172)` | branco sobre: 5.70:1 |
| `--danger` | `oklch(0.505 0.185 27)` | branco sobre: 6.46:1 |

### Tema escuro

Papel `oklch(0.178 0.016 258)`. `--brand` clareia para `oklch(0.720 0.135 150)` (8.03:1 sobre o
papel) e a banda drenched inverte: o verde profundo vira superfície e a tinta dela continua clara.
`--brand-fg` (tinta **sobre** o botão) e `--band-ink` (tinta **sobre** a banda) são papéis
diferentes — confundi-los deixava o hero preto-no-verde.

### Regras duras

- **O ouro nunca é texto sobre fundo claro** (1.67:1). Ele é preenchimento, marcador e display
  sobre verde profundo. Quando o ouro precisa mesmo ser texto, existe `--gold-deep`.
- **A rampa de cobertura (`--cov-1..3`) é fixa nos dois temas** — é dado, não superfície. Nenhuma
  passa de L 0.575 (onde o branco ainda fecha 4.5:1) nem desce de L 0.400 (abaixo disso a faixa de
  Educação Infantil, a menor, some contra o papel escuro).
- **`--ok` fica no matiz 172, não no 150.** Com a marca verde, um badge "ok" no mesmo matiz seria
  indistinguível de um elemento de marca ao lado.
- **As séries do gráfico de uso são verde + azul**, não verde + verde: "total" e "bem-sucedidas"
  são quantidades, não aprovação/reprovação.
- **Nenhum hex literal em template.** Use `var(--token)`. Exceções declaradas e testadas: a logo do
  Google (marca de terceiro), o `theme-color` (meta tag não aceita `var()`), o branco do QR do Pix
  (leitura óptica) e o branco dos chevrons do símbolo.

---

## 3. O símbolo

Um estudante (ponto de ouro) sobre um livro aberto em três camadas — as três etapas da BNCC
(EI / EF / EM) —, que também se leem como chevrons de código.

Geometria canônica, em `viewBox="0 0 48 48"`:

```
rect  x=4 y=4 w=40 h=40 rx=12          fill: gradiente --mark-a -> --mark-b (diagonal TL->BR)
path  M13 22l11 4.5L35 22              stroke #ffffff, width 3.5, caps/joins redondos
path  M13 28.6l11 4.5 11-4.5
path  M13 35.2l11 4.5 11-4.5
circle cx=24 cy=13.8 r=3.3             fill: --mark-dot  (o estudante)
```

Cores do símbolo:

| Token | Claro | Escuro |
|---|---|---|
| `--mark-a` | `#07603a` | `#0e8c4c` |
| `--mark-b` | `#12a45a` | `#35c97a` |
| `--mark-dot` | `#f2c04a` | `#f3c64c` |

**Os chevrons são brancos nos dois temas** — eles vivem sobre o tile, que é sempre verde.

### Onde cada variante vive

| Uso | Fonte | Observação |
|---|---|---|
| Qualquer template do app | macro `app/web/templates/_brand.html` | `{% from "_brand.html" import mark %}` → `{{ mark(28, 'nav') }}` |
| favicon SVG, apple-touch, JSON-LD, ReDoc | `static/logo-icon.svg` | 48×48, só o mark |
| README, `info.x-logo` do OpenAPI | `static/logo.svg` / `logo-dark.svg` | 224×48, mark + wordmark |
| Rasters (og, favicon.ico, PWA, LinkedIn) | `scripts/generate_og_image.py` | desenha o mark programaticamente |

O macro parametriza o `id` do gradiente (`bncc-tile-{{ uid }}`) porque `portal/login.html` e
`portal/signup.html` estendem `base.html`: são **duas instâncias na mesma página**, e ids repetidos
fazem o segundo gradiente herdar o primeiro. Use `'nav'`, `'auth'`, `'adm'`.

Os stops do macro vêm de `--mark-*`, então **um único macro serve claro e escuro** — não existe uma
segunda cópia do desenho para o tema escuro.

### O símbolo NUNCA é recolorido

Foi exatamente isso que gerou a pior divergência: os carrosséis do LinkedIn tinham regras CSS
(`svg linearGradient stop { stop-color: var(--brand) }` e
`svg circle[fill="#ffc53d"] { fill: var(--s-red) }`) que repintavam o mark, e os PNGs/PDFs
exportados carregavam um tile azul com ponto vermelho — um símbolo que não existia em nenhuma outra
superfície. As regras foram removidas.

`brand-eumaker.svg` e `brand-expertia.svg` são marcas de terceiros e não seguem esta paleta.

---

## 4. Tipografia

**Inter**, auto-hospedada (SIL OFL 1.1, `static/fonts/LICENSE-Inter.txt`). Variable font, subset
latin, 48 KB para todos os pesos — declarada em `static/fonts.css`, que tem dois consumidores:
`styles.css` e a página do Scalar (`/docs`), que não carrega o design system.

Antes disso `"Inter"` era declarada em `--font` e **nunca carregada**: o site caía no stack do
sistema, e a tipografia mudava de máquina para máquina. O mesmo valia para o gerador de raster, que
escolhia Segoe UI no Windows e DejaVu no CI — o mesmo comando produzia arquivos diferentes.

Sem CDN em runtime: o arquivo é servido do próprio `/static`.

Escala de 1.25 (`--t-xs` 0.79rem → `--t-display` clamp até 4.5rem), corpo em 17px.
Mono: stack do sistema (`ui-monospace, SFMono-Regular, …`).

---

## 5. Inventário de assets

Tudo em `app/web/static/`. Os rasters são **gerados**, nunca editados à mão:

```bash
venv/Scripts/pip install pillow fonttools brotli
venv/Scripts/python scripts/generate_og_image.py
```

| Arquivo | Origem | Consumidor |
|---|---|---|
| `og-image.png` (1200×630) | gerado | `og:image`, `twitter:image` |
| `favicon.ico` (16/32/48) | gerado | rota `/favicon.ico` |
| `apple-touch-icon.png` (180) | gerado | iOS — ignora SVG aqui |
| `icon-192.png`, `icon-512.png` | gerado | `site.webmanifest` |
| `logo-300.png` | gerado | uso avulso em posts/apresentações |
| `linkedin-banner.png` (1584×396) | gerado | capa de página no LinkedIn |
| `linkedin-cover.png` (1128×191) | gerado | capa de perfil |
| `logo.svg`, `logo-dark.svg`, `logo-icon.svg` | escritos à mão | README, `x-logo`, favicon |
| `site.webmanifest` | escrito à mão | PWA |
| `fonts/inter-latin.woff2` | baixado (OFL) | `fonts.css` |

**Não renomeie `logo.svg`.** O caminho `/static/logo.svg` está congelado como `info.x-logo` em
`docs/openapi/v1/*.json` e em `tests/contract/openapi_snapshot.json` — mudar o caminho é mudança de
contrato (Princípio I). Editar o conteúdo é livre.

`og-image.svg` foi **apagado**: estava morto, contradizia o PNG servido e era mais uma cópia
divergente. O card social vem só do script.

---

## 6. Superfícies fora do app

Os carrosséis do LinkedIn (`.tmp/linkedin-carousel/`, fora do versionamento) mantêm layout
editorial e tipografia próprios (Archivo + JetBrains Mono, papel quente `#f6f3ef`) — é uma voz
deliberada para o feed, e o `PRODUCT.md` proíbe explicitamente o visual "SaaS startup". O que eles
**não** têm licença para variar é a paleta de marca e o símbolo: ambos seguem este documento.

Os relatórios datados em `docs/` (`relatorio-teste-producao*.html`) ficam como estão — são registro
histórico; repintá-los seria reescrever evidência.

---

## 7. Ao mexer na marca

1. Mude o token em `styles.css`, nunca o valor no template.
2. Recalcule o contraste do par e escreva o número real no comentário.
3. Se o símbolo mudou: macro + os três `.svg` + `generate_og_image.py`, todos juntos.
4. Rode `pytest tests/contract/test_brand_consistency.py`.
5. Confira nos **dois temas** — o portão pega divergência de arquivo, não de percepção.
6. No deploy: trocar asset estático exige purgar a CDN do Firebase com um novo release
   (`firebase deploy --only hosting --project api-bncc`), mesmo que ele reporte 0 arquivos.
