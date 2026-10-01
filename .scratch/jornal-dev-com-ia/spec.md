# Spec: Dev com IA no jornal

Status: ready-for-agent

Origem: conversa de 2026-09-30, aberta e fechada com ele numa sessão de brainstorming. Estende o
[spec do jornal](../noticias/spec.md), que continua valendo em tudo o que esta não mexe. Glossário
em `CONTEXT.md`. Pede o **ADR 0003** (camada 4): ler o X por navegador logado é decisão difícil de
desfazer, surpreende quem lê o código e tem risco aceito por ele.

## Problem Statement

Ele quer que o jornal traga, como uma das informações principais, **como desenvolver melhor com
IA**: dicas de harness (Claude Code, Codex, Cursor), skills, prompts, contexto, economia de token.
Para ele a melhor fonte disso hoje é o X. A seção Tecnologia atual são seis feeds de notícia geral
(Ars Technica, The Verge, The Register, Tom's Hardware, Tecnoblog, Hacker News) e quase não traz
isso.

O X não se lê de graça: a API oficial é paga por post lido desde fevereiro de 2026
(US$ 0,005 por post, crédito no console), o plano gratuito acabou, não existe RSS e os espelhos
(Nitter) morreram. Ele escolheu **navegar no X com uma conta só do Whis** e aceitou o risco dos
termos do X.

## Solution

Uma seção nova, **Dev com IA**, logo depois de *Aprender hoje*, alimentada por um leitor do X que
abre o Chrome instalado com um perfil só do Whis, já logado, **lê o que a página mostra** (link,
@autor, hora, texto visível, curtidas) da aba **Seguindo**, da aba **Para você** e de **seis
buscas**, e entrega esses posts como candidatos da coleta. O editor que já existe escolhe de 4 a 6
e escolhe também a **Dica do dia**: o post mais aplicável, com duas ou três frases de como usar.
O jornal traz os links; o post ele abre no X. Sem print, sem imagem, sem API paga.

## User Stories

- Abro o jornal e logo depois de *Aprender hoje* vejo **Dev com IA**: a Dica do dia (o @autor, um
  título em português e como aplicar) e de 4 a 6 posts com @autor, uma frase em português, a hora
  e o link para o post no X.
- Só vem dica prática: harness, skills, hooks, subagentes, contexto, prompts, tokens, fluxo de
  trabalho. Hype, anúncio sem dica e engajamento barato ficam de fora. No máximo 2 do mesmo autor.
- O que já saiu numa das últimas 7 edições não volta.
- Para mudar o que o Whis lê, edito `noticias/fontes.md` no Obsidian: tiro ou ponho uma busca, ou
  uma linha de RSS na mesma seção.
- Para trocar quem a aba Seguindo traz, sigo ou deixo de seguir gente na conta do Whis.
- Faço o login uma vez com `python -m whis x-login`. Quando ele vencer, o jornal sai mesmo assim e
  o toast e a seção dizem "O login do X venceu" e o comando que conserta.
- Se o X mudar a página ou o navegador falhar, a seção diz numa linha que o X ficou indisponível e
  o resto do jornal sai normal.

## Implementation Decisions

### Decisões dele (não derivam do código)

- Fonte: **o X por navegador**, numa **conta só do Whis** (se o X travar, a dele fica intacta). Não
  a API paga, não o Grok, não fontes abertas no lugar do X.
- O que ler: **Seguindo + Para você + buscas por termo**. Buscas **só em inglês** (a em português
  foi descartada).
- Formato: **seção própria com a Dica do dia**, depois *Aprender hoje*; Tecnologia continua com as
  notícias gerais.
- *Aprender hoje* **não muda**: segue sendo de fundamentos de software.
- **Ler a página e trazer os links**, sem print e sem extrair nada além do que identifica o post.

### O bloco de `noticias/fontes.md`

O arquivo é dele e o Whis nunca escreve nele (spec do jornal, *Fontes do jornal*). O bloco vai no
`MODELO_DAS_FONTES` (para quem cria o arquivo do zero) e no smoke, pronto para ele colar **no topo
do arquivo**, já que a ordem das seções é a ordem do arquivo:

```
## Dev com IA (ia) · 4 a 6 itens
- X · Seguindo: x:seguindo
- X · Para você: x:para-voce
- X · Claude Code: x:busca "claude code" min_faves:100
- X · Outros harness: x:busca (codex OR cursor OR "gemini cli" OR opencode) (agent OR cli) min_faves:50
- X · Skills e hooks: x:busca (claude OR codex) (skills OR hooks OR subagents OR "slash commands" OR MCP) min_faves:50
- X · Contexto: x:busca ("context engineering" OR CLAUDE.md OR AGENTS.md OR "plan mode") min_faves:30
- X · Tokens e custo: x:busca ("prompt caching" OR "token usage" OR "context window" OR compact) (claude OR codex OR cursor) min_faves:10
- X · Fluxo de trabalho: x:busca ("agentic coding" OR "spec-driven" OR "parallel agents" OR worktrees) min_faves:30
```

- Linha de fonte do X: `- Nome: x:seguindo`, `- Nome: x:para-voce` ou `- Nome: x:busca <consulta>`.
  A consulta é a sintaxe da caixa de busca do X, tal como ele escreveria. O nome termina no
  primeiro `:` seguido de `x:` (a consulta tem `:` dentro, como `min_faves:100`).
- O Whis acrescenta sozinho a cada busca `-filter:replies` e `since:` com a data de ontem; a busca
  usa a aba *Principais* (`f=top`). URL:
  `https://x.com/search?q=<consulta + acréscimos>&src=typed_query&f=top`.
- Linha `x:` com tipo desconhecido (`x:qualquer`) vira aviso de linha ignorada, como as demais.
- As linhas `x:` ficam num campo novo `x` da `Secao` de `fontes_do_jornal.py` (sem renomear a
  classe), separado de `fontes`: **não contam** em `_total_de_feeds` nem na regra "o jornal não
  nasce" — sem nenhum feed RSS que responda, a edição não nasce, como hoje, mesmo com linhas `x:`.
  Uma seção só com linhas `x:` é válida: o "sem nenhuma fonte válida" de `fechar()` passa a olhar
  `fontes` **ou** `x`.
- Os posts herdam o **id da seção onde a linha está**. O id `ia` é o que liga a regra do editor e a
  Dica do dia; linha `x:` em outra seção vira candidato daquela seção, com a regra dela e sem dica.
- RSS normal continua aceito na seção `ia`, ao lado das linhas `x:`.
- Os `min_faves` são palpite; a camada 0 mede o volume de cada busca e ajusta antes de entrar no
  modelo.

### Lista inicial para a conta do Whis seguir

Ele cria a conta **com o idioma em inglês** (o leitor lê os rótulos "Following", "For you" e
"Likes" e números como "1.2K") e segue; o Whis nunca segue ninguém. Conferir cada @ no X ao seguir (podem ter
mudado): `@bcherny` (Boris Cherny, Claude Code), `@_catwu` (Cat Wu, Claude Code), `@alexalbert__`,
`@claudeai`, `@simonw` (Simon Willison), `@steipete` (Peter Steinberger), `@dexhorthy` (Dex Horthy,
context engineering), `@GeoffreyHuntley`, `@mitsuhiko` (Armin Ronacher), `@karpathy`, `@swyx`,
`@HamelHusain`, `@addyosmani`, `@kieranklaassen`, `@thsottiaux` (Codex), `@IndyDevDan`,
`@KentBeck`.

### Camada 0 — protótipo (portão das demais)

Descartável, em `.scratch/jornal-dev-com-ia/research/01-x-pelo-navegador/`, como o protótipo do
jornal. Antes, ele cria a conta do Whis e segue a lista. O protótipo:

1. abre o Chrome instalado (`channel="chrome"`) num perfil persistente próprio e, na primeira vez,
   com janela, para ele fazer o login;
2. roda as oito páginas sem janela e conta, por página, posts lidos, posts das últimas 24 h e
   segundos;
3. guarda o `outerHTML` de alguns `article` (post comum, repost, anúncio, post longo cortado,
   post sem curtida, post que cita outro) e o HTML de uma **busca sem resultado**, para virar
   fixture.

Responde: o X aceita o Chrome sem janela com sessão válida? Se não, minimizado/fora da tela
resolve? Quantos posts úteis por dia e quais `min_faves` usar? Como a página marca anúncio, repost
e busca vazia, e onde estão a hora e as curtidas? A resposta vai no arquivo de research e decide o modo de abrir
(constante no código, sem chave de config).

### Camada 1 — o leitor do X (`fonte_x.py`, `fontes_do_jornal.py`)

- **Playwright** entra no `pyproject.toml`, usando o **Chrome instalado** (`channel="chrome"`), sem
  `playwright install`. Sem Chrome: falha "Chrome não encontrado".
- **Perfil**: `%LOCALAPPDATA%\whis\navegador-x\`, separado do Chrome dele. Um perfil só serve um
  processo: se `x-login` e `news` disputarem, o segundo falha com mensagem clara.
- **Abas da home**: `https://x.com/home`, depois o clique na aba pelo texto (`Seguindo`/`Following`,
  `Para você`/`For you`), porque o X não dá URL própria a elas.
- **Em cada página**: espera o primeiro `article`, rola 3 ou 4 vezes com pausas de 1,5 a 3 s,
  entrega o `outerHTML` de cada `article`. Só lê: nunca clica em curtir, seguir, postar, abrir
  post. Uma rodada por edição.
- **A leitura do post é Python puro** (`html.parser` da stdlib, sem dependência nova) sobre o
  `outerHTML`, para ser testável com fixture: link do post (a âncora `/status/` que envolve o
  `<time>`), @autor tirado do link, hora do `time[datetime]`, texto visível do bloco de texto do
  post, curtidas do rótulo do botão de curtir, e se é anúncio. Repost vale pelo post original.
  Post citado dentro de outro não vira candidato.
- **Vira `Candidato`**: `secao` = id da seção da linha, `id` = `<secao>-x<N>` (os de RSS seguem
  `<secao>-<N>`, sem colisão), `fonte="@autor"` (é isso que faz o limite de 2 por fonte que já
  existe valer como 2 por autor), `titulo` = começo do texto (até ~120 caracteres), `resumo` =
  texto visível (até ~500), `link` canônico `https://x.com/<autor em minúsculas>/status/<id>`,
  `data` = a hora, `imagem=None`. `Candidato` ganha `curtidas: int | None = None`, que o editor vê
  na linha do candidato.
- **Corte, fora do `_candidatos` dos feeds** (sem o dedupe de título de 60 caracteres, que juntaria
  posts diferentes que começam igual): anúncio fora; mais de 24 h fora; repetido entre páginas
  (mesmo id de status) fora; já publicado nas últimas 7 edições fora (regra existente, pelo link
  canônico). **Teto próprio de 30 posts do X por seção, os mais curtidos primeiro**; o RSS da mesma
  seção segue o teto e a ordem de hoje, à parte.
- **Busca sem resultado** (o marcador de vazio que a camada 0 encontrar) é zero posts, não falha.
- **Falhas** levantam `ErroDoX(motivo)`, com uma subclasse para o login:
  - redirecionado para `/login` ou `/i/flow/login`, ou o X pede verificação → `LoginDoXVenceu`;
  - Playwright ausente, Chrome ausente, tempo esgotado, perfil ocupado;
  - **nem `article` nem o marcador de vazio** numa página que carregou → "a página do X mudou".
- **O que cada falha produz**:
  - **login vencido** para a leitura toda e vira aviso da edição (camada 2);
  - **uma página** que falha sozinha não derruba as outras e vai para `fontes_com_falha` com o
    nome da linha e o motivo (`X · Contexto (tempo esgotado)`), como um feed RSS: rodapé, sem
    deixar a edição parcial;
  - **todas as páginas** falhando (sem ser login) viram o aviso "X indisponível hoje: <motivo>".
- O leitor é uma **porta** (`PortaDoX` em `portas.py`), injetada pela `PortasDoJornal`
  (`montar_portas_do_jornal` no `__main__.py` e o `news` da palheta). A suíte nunca recebe o leitor
  de verdade: trava autouse no `conftest`, como a dos toasts, porque o `MODELO_DAS_FONTES` passa a
  ter linhas `x:`.

### Camada 2 — coleta e editor (`feeds.py`/`jornal.py`, `jornal_claude.py`, `portas.py`, `fakes.py`)

- O leitor do X roda **uma vez por edição, depois de `_coletar_esperando_a_rede`** (nunca dentro
  do laço de espera da rede, que repete a coleta), leva de 1 a 2 min e junta os candidatos às
  seções das linhas. Login vencido ou X todo fora viram aviso da edição:
  `O login do X venceu: rode python -m whis x-login` ou `X indisponível hoje: <motivo>`. A edição
  fica parcial (código 3), como as outras degradações. Sem nenhuma linha `x:` no arquivo, o leitor
  nem abre.
- **Editor**: `SISTEMA_ESCOLHA` ganha a regra da seção — *"Dev com IA: dica prática de
  desenvolvimento com IA — harness (Claude Code, Codex, Cursor e afins), skills, hooks,
  subagentes, contexto (CLAUDE.md, AGENTS.md), prompts, economia de token, fluxo de trabalho.
  Ignore hype, anúncio de produto sem dica, sorteio, curso pago e engajamento barato. Prefira o que
  dá para aplicar amanhã."*
- **Dica do dia**: quando há candidatos em `ia`, `esquema_da_escolha` ganha `dica: {id, titulo,
  como_aplicar}` opcional. `como_aplicar` são duas ou três frases do que o post diz e de como usar,
  **só a partir do texto do post** — nunca comando, flag ou número que não esteja lá. Vale se o
  `id` for de um **post do X** da seção `ia` (id `ia-x<N>`; item RSS da seção não vira dica); senão
  cai e a seção sai só com a lista. Se o post da dica
  também estiver na lista, sai da lista. `Escolha` ganha `dica`. A escolha automática (editor
  falhou) não tem dica.
- `LeitorDoXFake` em `fakes.py` para `--fakes`, com posts fixos.
- Continua **uma** chamada ao editor. Peso estimado: até 30 posts curtos a mais, uns 10 a 15 % sobre
  a edição de US$ 0,99. Navegar não gasta token.

### Camada 3 — nota e página (`jornal.py`, `vault.py`, `pagina_do_jornal.py`)

- `SecaoDoJornal` ganha `dica` opcional (o item e o `como_aplicar`) e `aviso` opcional (o motivo
  de o X não ter entrado nela). O aviso continua também em `Edicao.avisos`, no cabeçalho e no topo
  da nota, como as outras faltas.
- **Página**: a Dica do dia num cartão como o de *Aprender hoje* ("Dica do dia", @autor, título,
  texto, link "Ver no X") ocupa o lugar do item grande. **Post do X nunca sai como item grande**,
  com dica ou sem (escolha automática, linha `x:` em outra seção): sai na lista sem imagem
  (`item sem`) e `_lista` escolhe o `lead` só entre os itens que não são do X. Item do X é o de
  link com host `x.com`. A linha "@autor · HH:MM" desses itens não passa pelo
  `text-transform:uppercase` do `.by` (o @ sairia em maiúsculas).
  `CORES` ganha a cor de `ia`. Seção vazia com `aviso`: o aviso no lugar de "Nada relevante nas
  últimas 24 h"; com itens, o aviso embaixo da lista.
- **Nota**: `## Dev com IA`, `### Dica do dia`, depois os itens como as outras seções. O link da
  dica sai como `[…](link)`, para o "já publicado" o contar, e entra em `Edicao.links()`.
- Sem capa: posts do X não baixam imagem.

### Camada 4 — a casca (`__main__.py`, `palheta.py`, docs)

- `python -m whis x-login`: abre o Chrome **com janela** no perfil do Whis em
  `https://x.com/login`, espera ele entrar (até a home carregar) ou fechar a janela, diz "Sessão do
  X salva" ou "Login não concluído". O Whis nunca digita nem vê a senha.
- **Toast**: em `resultado_do_jornal`, quando os avisos da edição trazem o login do X vencido, o
  título é **"O login do X venceu"** e o texto "Rode 'python -m whis x-login' num terminal. O
  jornal saiu sem a parte do X.", com o botão da página. Precedência: login do Claude vencido >
  página não saiu (o texto ganha "; o login do X também venceu" quando for o caso) > login do X
  vencido > o toast de hoje.
- **ADR 0003**: o X entra por navegador logado numa conta própria — sem API grátis; a paga e o Grok
  descartados por ele; risco dos termos aceito; consequência: leitor frágil, degradação
  obrigatória, só leitura.
- `docs/smoke-jornal.md`: `x-login`; uma edição com a seção; login vencido simulado apagando o
  perfil; uma linha `x:busca` acrescentada e vista na edição seguinte.

## Testing Decisions

- A leitura do post com as fixtures da camada 0, em `tests/fixtures/jornal/x/`: post comum, repost
  (vale o original), anúncio (fora), post longo cortado, post sem curtida (`curtidas=None`), post
  citado (só o de fora), curtidas "1.2K"; a busca vazia (zero posts, sem falha).
- As linhas `x:` de `fontes.md`: os três tipos, nome com `·`, consulta com `:` dentro, tipo
  desconhecido vira aviso, linha `x:` fora de `ia` herda a seção; a URL da busca com
  `-filter:replies`, `since:` de ontem e `f=top`; linhas `x:` não contam para o jornal nascer.
- A coleta com um leitor falso: corte de 24 h, repetidos entre páginas pelo id do status, já
  publicado pelo link canônico, teto de 30 pelos mais curtidos à parte do RSS, ids `-x<N>`,
  `fonte="@autor"`, dois posts que começam igual continuam dois; sem linha `x:` o leitor não é
  chamado; o leitor é chamado uma vez mesmo quando a espera da rede repete a coleta.
- As falhas: login vencido vira o aviso certo, para a leitura e dá código 3; todas as páginas
  fora viram "indisponível" com o motivo; uma página só fora vai para `fontes_com_falha` e as
  outras seguem.
- O editor: o esquema só tem `dica` quando há `ia`; dica com id válido, com id de outra seção
  (cai), repetida na lista (sai da lista); a regra da seção no prompt.
- Página e nota com e sem Dica do dia; a seção vazia com aviso; o link da dica contado como já
  publicado na edição seguinte.
- O toast do login do X vencido e a precedência (Claude > página não saiu > X).
- O navegador de verdade só no protótipo e no smoke manual, como a ESPN. Nada na suíte abre Chrome.

## Out of Scope

- Curtir, seguir, postar, abrir thread ou respostas: o Whis só lê as páginas da lista.
- Imagens e vídeos dos posts: ele vê no X.
- API paga do X, Grok, Bluesky e outras redes.
- Busca em português.
- Mudar *Aprender hoje*.
- Ler a thread inteira para a Dica do dia: vale o texto visível do post.

## Further Notes

- **Riscos aceitos por ele**: os termos do X proíbem leitura automatizada sem autorização; a conta
  do Whis pode ser limitada, travada para verificação ou suspensa. O X muda a página com
  frequência; quando mudar, a seção degrada até o leitor ser ajustado.
- **Para parecer gente**: uma rodada por dia, oito páginas, pausas, nada além de ler. Mais buscas
  aumentam o risco; sete foi o teto conversado (ficaram seis).
- **Ambiente do agente**: o `%LOCALAPPDATA%` e o `%APPDATA%` que uma sessão de agente enxerga
  podem ser cópias virtuais; o login e a prova valem rodados por ele ou por tarefa agendada
  descartável.
