# 01 — O X pelo navegador

Status: aguardando a conta do Whis no X (precisa dele)

A camada 0 do [spec](../spec.md). O leitor (`src/whis/fonte_x.py`) já existe, escrito com a
estrutura conhecida do HTML do X; o protótipo usa o próprio leitor para provar o que só a conta de
verdade responde.

## Antes de rodar (ele)

1. Criar a conta do Whis no X **com o idioma em inglês** (Settings → Accessibility, display and
   languages → Languages).
2. Seguir a lista inicial do spec, conferindo cada @.

## Rodar

Da raiz do repositório, no PowerShell dele (não numa sessão de agente: o `%LOCALAPPDATA%` dela pode
ser outro):

```
.venv\Scripts\python.exe .scratch\jornal-dev-com-ia\research\01-x-pelo-navegador\prototipo.py --login
.venv\Scripts\python.exe .scratch\jornal-dev-com-ia\research\01-x-pelo-navegador\prototipo.py
```

Se a segunda falhar em todas as páginas, rodar de novo com `--com-janela`.

## O que responde

- O X aceita o Chrome sem janela com a sessão válida? O Chrome sem janela se anuncia como
  `HeadlessChrome` no user agent (visto em 2026-09-30, Chrome 154). Se o X recusar, o caminho do
  spec é o Chrome com janela minimizada: `SEM_JANELA = False` em `fonte_x.py`.
- Quantos posts úteis cada página traz nas últimas 24 h, e se os `min_faves` do modelo cortam
  demais ou de menos (`medidas.json`, campo `curtidas`).
- Como a página marca anúncio, repost, busca vazia, a hora e as curtidas: comparar `amostras/` com
  `tests/fixtures/jornal/x/` e trocar as fixtures pelas reais.

## Resposta (2026-09-30, rodada pelo agente)

A conta do Whis ainda não existia: a janela de login abriu e fechou sem login. As medidas vieram de
duas fontes: o Chrome do Whis (perfil sem sessão), pela tarefa descartável `rodar.ps1`, e o Chrome
dele, já logado na conta dele, pela extensão Claude in Chrome, só lendo e rolando.

- **Sem janela, o X recusa.** As oito páginas responderam `net::ERR_HTTP_RESPONSE_CODE_FAILURE` já
  no `goto`, antes de qualquer login. Com janela, a página carrega ("X - The Everything App"); sem
  sessão, fica na casca sem nenhum `article`, e o leitor diz "tempo esgotado" nas abas e "a página
  do X mudou" nas buscas. `SEM_JANELA` passou a `False`: às 08:20 o Chrome aparece na tela por um
  ou dois minutos.
- **A estrutura bate com o leitor:** `article[data-testid="tweet"]`, permalink
  `/<autor>/status/<id de 19 dígitos>` em volta do único `<time datetime>`, um `tweetText` por post
  e curtidas no `aria-label` do botão (`"2395 Likes. Like"`). O número visível não serve: durante a
  animação ele vem colado (`"916917"`).
- **`placementTracking` não é anúncio.** Um post orgânico (com hora e permalink, sem "Ad") estava
  dentro dele. O anúncio de verdade traz o texto `Ad` e não tem `<time>`. A regra virou só o rótulo.
- **Volume das buscas** (aba Principais, 4 rolagens, posts das últimas 24 h): Claude Code 6;
  Outros harness 7; Skills e hooks 6; Contexto 7; Tokens e custo **0** (de 6 lidos, todos mais
  velhos); Fluxo de trabalho 3. Os cortes de Tokens e custo (30 → 10) e de Fluxo de trabalho
  (50 → 30) baixaram. As buscas se repetem (o mesmo post em Claude Code e em Skills): o dedupe
  pelo id do status cobre.
- **Qualidade:** muito hype ("ANTHROPIC HAS REVEALED THE TRICK…", "f*cking gold"), cripto e
  lançamento de produto. Sobra pouco post de dica prática por busca; a regra do editor que manda
  ignorar hype é o filtro principal.
- **Abas da home: não provado.** Na aba de fundo da extensão, a rolagem anda mas o X não desenha
  posts novos (4 no DOM do começo ao fim, com seis rolagens de 3 s). No Chrome do Whis, que abre na
  própria janela, isso precisa ser provado com a conta logada.

## Pendente

- A conta do Whis e o `--login`; depois a rodada `medir-com-janela` com sessão, que grava as
  amostras reais para trocar as fixtures provisórias (pela extensão as strings do HTML voltam
  censuradas, então as fixtures não saem por ela).
