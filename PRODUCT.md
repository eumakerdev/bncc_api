# Product

## Register

brand

## Platform

web

## Users

Quem constrói software para a educação brasileira: desenvolvedores e times de
produto de edtechs, integradores de sistemas de gestão escolar, e equipes
técnicas de secretarias e redes de ensino. Chegam com um problema concreto e
pouco tempo — precisam dos códigos e textos oficiais da BNCC dentro do produto
deles hoje, não de mais um PDF para raspar. O contexto de uso é o do
desenvolvedor avaliando se pode confiar numa fonte de dados: ele vai ler,
desconfiar, testar uma chamada e decidir em minutos.

Existe um segundo leitor que não escreve código — gestor de rede, coordenador
pedagógico, pessoa de política pública — que chega para entender o que é isso e
se dá para confiar. A página precisa não perdê-lo, mas o desenvolvedor é quem
converte.

## Product Purpose

Expor toda a Base Nacional Comum Curricular como API pública, gratuita e
estável, para que ninguém mais precise extrair a BNCC de PDF na mão. Sucesso é
a BNCC API virar a camada de dado curricular que os produtos educacionais
brasileiros assumem como dada — e o projeto se manter no ar sem depender de
cobrar por isso.

## Positioning

A BNCC inteira, fiel ao documento oficial, gratuita e auditável — mantida como
bem público, com as contas abertas.

## Conversion & proof

- CTA primário: criar conta e gerar a API key (`/portal/signup`). Secundário,
  para quem ainda não vai se cadastrar: o guia de início rápido (`/guia`).
- A linha que fica depois de 10 segundos: toda a BNCC, de graça, em uma API que
  não inventa código.
- Escada de crenças, nesta ordem: (1) isso cobre a BNCC inteira, não uma
  amostra; (2) o texto é fiel ao documento oficial e dá para auditar; (3) é
  gratuito de verdade, sem pegadinha nem cartão; (4) não vai sumir amanhã nem
  quebrar meu contrato; (5) começar custa minutos, não uma reunião.
- Proof disponível: o snapshot versionado e a auditoria de extração
  (`scripts/audit_extraction.py`, 0 achados ERROR); a seção pública de
  transparência com uso real e custo real de infraestrutura; o código aberto sob
  MIT. Não há depoimentos, logos de clientes nem imprensa — a prova é o dado e a
  prestação de contas, não a validação social.

## Brand Personality

Cívico, transparente, generoso. A voz é de quem construiu uma coisa pública e
está prestando contas dela: direta, sem hype, sem vender. Assume que o leitor é
competente e não precisa ser convencido com adjetivo. Admite limite com a mesma
naturalidade com que mostra número — a seção que diz "R$ 0 de apoio recebido"
é a voz da marca, não uma exceção a ela. A emoção alvo é confiança tranquila,
com um fundo de convite: isso aqui é seu também.

## Anti-references

Três coisas que esta página não pode parecer:

Site de startup SaaS — hero com gradiente, grid infinito de cards com ícone,
selo de investidor, print de dashboard flutuando. É o visual mais saturado da
web e mataria a leitura de bem público.

Portal de governo — gov.br, densidade burocrática de links, cara de sistema
legado. O risco natural da lane cívica, e o que faria o desenvolvedor fechar a
aba.

Revista editorial tipográfica — serifada display em itálico, capitulares,
colunas com filete, metadados em maiúsculas espaçadas. Lane saturada e sem
relação com o que o produto é.

Sem fotografia de banco de imagens. O dado é a imagem: visualizações da própria
BNCC, cobertura curricular, código real de resposta.

## Design Principles

**Praticar o que se prega.** O projeto vende dado auditável e contas abertas; a
página precisa ser ela mesma auditável e aberta. Número na tela é número real
puxado do banco, nunca ilustração.

**Mostrar, não adjetivar.** "1.703 habilidades" e uma resposta JSON real valem
mais que "completo e confiável". Toda afirmação da página deve ter como ser
verificada por quem lê.

**Admitir limite em voz alta.** O que é não-oficial, o que é gerado por IA, o
que ainda não existe e quanto o projeto já recebeu de apoio (zero) aparecem com
o mesmo destaque das conquistas. A honestidade é o diferencial competitivo.

**Bem público, não produto grátis.** O tom é de infraestrutura compartilhada
com as contas na mesa, não de plano free esperando upsell.

**Minutos até a primeira chamada.** Cada seção é medida por quanto aproxima o
leitor de uma requisição bem-sucedida. O que não aproxima, sai.

## Accessibility & Inclusion

WCAG 2.2 AA como meta explícita e verificada, não aspiração. Texto corrido
≥4.5:1 contra o fundo, texto grande ≥3:1, foco sempre visível, nenhuma
informação transmitida só por cor (os gráficos de custo por serviço precisam de
rótulo além do matiz). Alvos de toque ≥44px. `prefers-reduced-motion` com
alternativa real em toda animação. Conteúdo funcional sem JavaScript, como já
acontece hoje no menu e nos formulários — degradação graciosa é requisito, não
cortesia.
