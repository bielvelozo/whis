# Spec: a daily em slides

Status: ready-for-agent

Origem: sessão de brainstorming de 2026-09-30, com as decisões tomadas por ele uma a uma (tabela
abaixo). Glossário em `CONTEXT.md`. ADR 0001 não precisa de emenda: publicar um artifact já é o
que o jornal faz (`.scratch/noticias/spec.md`), pela mesma conta e pelo mesmo caminho.

> **Base do trabalho.** Em 2026-09-30, duas outras sessões deixaram trabalho **não commitado**
> na mesma árvore: a remoção da gravação (ADR 0002; saem `coletor`, `gravador`, `pipeline`,
> `resumo_claude`, `stt_deepgram`, `retencao`, o comando `record` e os campos de gravação da
> `Configuracao`; as funções do CLI foram para `claude_cli.py`; `vault.escrever` passou a exigir
> `zonas=`; suíte com 1101 verdes em `-m "not rede"`) e o conserto do jornal
> (`login_do_claude.py`). As duas mexem em `__main__`, `palheta`, `configuracao`, `painel`,
> `vault`, `portas`, `fakes`, `jornal_claude` e `resumo_dia_claude`, os mesmos arquivos desta
> entrega. **Esta entrega começa depois que ele commitar aquilo** e parte do código como ficou:
> um commit desta entrega não consegue separar, dentro de um mesmo arquivo, o que é dela do que
> é das outras. Nomes citados abaixo que mudaram lá (por exemplo, `caminho_do_cli`) valem pelo
> novo lugar.

## Problem Statement

A daily de hoje é escrita pelo agente: `whis daily` lê git, Linear e Slack desde a última daily,
o Claude monta um roteiro e o Whis acrescenta e move itens em *O que eu fiz* e *O que estou
fazendo* de `daily/atual.md`. Ele não gostou e quase não usa (memória: *"quase não usa diário nem
daily"*). O que ele quer é o contrário: **ele** diz o que fez, o que está fazendo e o que terminou,
escrevendo na nota da daily pelo Obsidian, e o Whis transforma isso num **deck do Claude Slides**
para apresentar na reunião.

Histórico que pesa: em 2026-09-04 ele já tinha pedido a daily *"mais bonita"* que um `.md`; a
página HTML ao lado da nota foi construída, usada um dia e revertida
(`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`). Desta vez o texto é dele, não do
agente, e o formato é de apresentação, não de página para ler.

## Solution

`whis daily` passa a fazer uma coisa só: ler as seções que ele escreveu em `daily/atual.md`,
montar um deck de slides com as linhas **literais**, publicar esse deck no Claude Slides
**sempre no mesmo link** e gravar em `daily/YYYY-MM-DD.md` uma cópia do que foi apresentado. A
tarefa `Whis-Daily` continua disparando nos horários de `[daily].horarios`; `daily` na palheta
gera na hora; o toast traz o link do deck.

O Whis escreve os arquivos do deck (Python, modelo visual fixo); o Claude só **publica**, com o
Haiku, pelo caminho que o jornal já provou (`jornal_claude.PublicacaoClaude`). Nada é inventado,
nada é reescrito.

## Decisões dele (2026-09-30)

| Pergunta | Decisão |
|---|---|
| O que desfazer | O agente escrevendo a daily. A nota fica inteira dele. `[daily].ativa` **fica** e passa a ligar/desligar os slides. |
| Seções de trabalho | Nova seção **`O que terminei`**, além de *O que eu fiz* e *O que estou fazendo*. |
| O que vai para o deck | As três de trabalho + **Dúvidas** + **Falar**. *Pontos* e *Fazer* ficam só na nota. |
| Texto | **Literal**, com visual fixo; o Claude só publica. |
| Endereço | **Sempre o mesmo link**, republicado a cada daily (como o jornal). |
| Limpeza da nota | **Ele** limpa; o Whis nunca mexe no texto dele, só grava a cópia datada. |
| Caminho | **A** (Claude Slides de verdade), com **B** (página HTML publicada como o jornal) de reserva se a sonda da camada 0 reprovar A. |
| Capa | Sem capa: o primeiro slide já é *O que eu fiz*. |
| Registro | Spec em `.scratch/daily-slides/`, no padrão do repositório. |

## O que sai e o que fica

**Sai** — tudo o que só servia à daily escrita pelo agente (a regra é essa; a lista abaixo é o
que se sabe hoje, e o plano confere com `grep` o que ficar órfão):

- em `daily.py`: a coleta das fontes, `do_trabalho`, `janela_da_daily`/`JanelaDaDaily`,
  `_montar_roteiro`, `PRIMEIRA_JANELA` e o `ResultadoDaDaily` atual;
- em `resumo_dia_claude.py`: a parte da daily — `resumir_daily`, `montar_pergunta_da_daily`,
  `_linhas_da_nota_viva`, `interpretar_daily`, `_itens_novos`, `_recusar_periodo_longo`, o prompt
  da daily e o parâmetro `contexto_do_time`. `resumir_dia` e o que ele usa são do diário e ficam;
- em `portas.py`: `Daily`, `ItemNovo`, `PortaDaily`, `ErroDeDaily`; em `fakes.py`: `DailyFake`,
  `DAILY_PADRAO`, `fontes_de_exemplo_da_daily`;
- em `__main__.py`: `montar_fontes_da_daily`, `montar_roteiro_da_daily`, o `_relatar_daily`
  atual e a menção a `referencias_pessoais` no relato; em `palheta.comandos_padrao` e em
  `__main__._comando_bandeja`, as fábricas `fontes_da_daily=`/`roteiro_da_daily=` dão lugar a uma
  fábrica da publicação do deck;
- em `nota_viva.py`: o que o agente escrevia sozinho — `aplicar`, mover de *fazendo* para *fiz*,
  `arquivar_fiz`, `Mudancas`, `SECOES_DO_AGENTE` e o `acrescentar(sob=…)` com os ids de item que
  só serviam às referências do modelo (se nada mais os usar). `_itens`/`Item` podem servir ao
  deck, mas `Item.nivel` é coluna (tab = 4): o deck usa **profundidade** (quantos ancestrais);
- em `vault.py`: `ate_da_daily_anterior`, `desde_da_daily_de`, `arquivo_da_nota_viva`,
  `montar_daily`, `_avisos_da_daily`, `cobertura_da_janela`, `_secao_das_mudancas`, `_alinhado`,
  `_temas_dos_eventos`, `SECAO_MUDANCAS`, `SECAO_ARQUIVO`, e `_data_do_nome`/
  `_momento_do_frontmatter` se nada mais os usar;
- em `configuracao.py`/painel: `[daily].referencias_pessoais` e `[daily].contexto_do_time`
  (**duas chaves a menos** do que houver depois da remoção da gravação; hoje são 31 em
  `CHAVES`, e `test_painel.py`/`test_configuracao_escrita.py` fixam a contagem);
- os testes que só cobrem isso (`test_roteiro_da_daily.py`, `test_daily_do_trabalho.py`, a parte
  daily de `test_resumo_dia_claude.py` e de `test_detalhe_longo_no_prompt.py`, e o que
  `test_daily.py`, `test_comando_daily.py` e `test_nota_viva.py` têm de roteiro, janela e
  movimentação). Conferir cada um antes de apagar: o que cobre o diário fica.

**Fica:**

- as fontes passivas e os coletores: o diário, o `ask` e a futura busca de vagas usam;
- `note`, `doubt` e `do` (e `whis daily --anotar`), acrescentando uma linha em *Pontos*,
  *Dúvidas* e *Fazer* a pedido dele;
- `Whis-Daily`, `[daily].horarios`, `[daily].ativa` (mesma semântica: a tarefa agendada sai com
  0 sem gerar, a palheta esconde `daily`), o Vigia olhando a tarefa;
- as notas datadas antigas em `daily/`, intocadas.

**Config antigo:** o `config.toml` dele ainda tem as duas chaves removidas. Chave desconhecida em
`[daily]` já é ignorada na leitura (só `horarios` é estrita), então ele continua carregando; o
painel as descarta ao salvar, porque só escreve o que está em `CHAVES`. Um teste prova isso.

## A nota

`daily/atual.md` continua sendo a **Nota viva**, agora escrita só por ele. As sete seções, nesta
ordem: *O que eu fiz*, *O que estou fazendo*, **O que terminei**, *Fazer*, *Dúvidas*, *Pontos*,
*Falar*. `MODELO_DA_NOTA_VIVA` ganha a seção nova.

A nota dele já existe sem `## O que terminei`. Em toda geração **real** (não em `--simular`),
inclusive quando a nota está vazia — é justamente quando ele precisa do título para começar a
escrever —, se o título faltar, o Whis o insere vazio depois de *O que estou fazendo*
(`NotaViva._abrir_secao` já faz a inserção na ordem) e grava a nota **literal**
(`escrever_nota_viva`). É a única escrita do Whis ali além de `note`/`doubt`/`do`, e na prática
acontece uma vez. Texto dele nunca é tocado.

## O deck

**Modelo de dados** (`Deck`, puro, sem I/O): uma lista de slides, cada um com `id`, título e
itens; cada item é o texto literal da linha (sem o marcador de lista) e seu nível de recuo.
Função `montar_deck(nota) -> Deck`:

- uma seção vira slide se tiver pelo menos um item com texto; seção vazia não gera slide;
- slides na ordem da nota: `fiz`, `fazendo`, `terminei`, `duvidas`, `falar`;
- linha que não é item de lista (parágrafo solto dentro da seção) entra como item de nível 0;
- seção que não cabe num slide continua em `fiz-2`, `fiz-3`…; os títulos passam a ser
  *O que eu fiz (1/2)*, *O que eu fiz (2/2)* — o primeiro também ganha a contagem.
  O corte estima linhas pela regra do Slides (≈ 0,6 × tamanho da fonte por caractere na largura
  útil de 1664 px) e nunca parte um item nem separa um sub-item do pai quando der para evitar;
- deck sem slide nenhum = **nota vazia**.

**Renderização para o Slides** (`slides_do_deck(deck, hoje) -> dict[caminho, conteúdo]`):

- `project/slides/<id>.html` — exatamente um `<section id="<id>" style="…">` no formato do tipo
  Slides (canvas 1920×1080, só estilo inline do subconjunto permitido, nada de `<style>`, classe,
  `margin`, `em` ou `var()`; fonte ≥ 24 px); título em `<h2>` sempre no mesmo lugar; itens em
  `<ul>` de `<li>` simples; rodapé fixo de 24 px em `bottom:64px` com a data por extenso e
  `n/total`; sem `<aside>`;
- **sub-itens**: o SKILL só descreve `<ul>` de `<li>` simples e descarta o que não conhece. A
  primeira tentativa é `<ul>` aninhado; se a sonda mostrar que o aninhamento some ou achata, o
  sub-item vira um `<ul>` irmão logo abaixo com `padding-left` proporcional à profundidade. Em
  nenhum caso um sub-item pode desaparecer do deck;
- inline markdown convertido: `**negrito**` → `<b>`, `*itálico*`/`_itálico_` → `<i>`,
  `` `código` `` → `<span>` monoespaçado, `[texto](https://…)` → `<a href>`, `[[nota|apelido]]`
  → `apelido`, `[[nota]]` → `nota`. Todo o resto é texto, com HTML **escapado**. Se a sonda
  mostrar que o `<span>` com `font-family` ou o `<a href>` são descartados, cai para o texto puro
  (sem os marcadores do markdown);
- `project/deck.json` — índice `v: 4` com `title: "Daily"`, `order` completo, `faces` (uma
  família do Google Fonts por `href`), `designSystems: []`, `lists: "css"` e
  `createdOnFiles: {v: 1, at: <agora>}`. O índice inteiro é reescrito a cada publicação;
  `lists` vai sempre (o deck nasceu com ele, então não é "acrescentar" num índice existente). Se a
  sonda mostrar que trocar o `at` é recusado, ele passa a ser a hora da criação, guardada como
  `deck_criado:` ao lado de `deck:` em toda cópia datada (inclusive a semente da camada 0 e a
  cópia gravada numa falha), e os dois são lidos da mesma nota. `sections`: uma entrada por **seção da nota** que virou slide,
  `{description: <título da seção>, start: <id do primeiro slide dela>}` — `fiz-2` fica dentro de
  `fiz`;
- visual fixo desenhado uma vez: paleta em hex (um escuro, um claro, um ou dois acentos, sem
  `#fff`/`#000` puros, contraste ≥ 4,5:1), uma escala de 4–5 tamanhos, 1–2 famílias. Aprovado
  por ele no deck de exemplo da camada 0 antes da camada 2.

As regras de formato vêm do SKILL do tipo Slides (`https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL`,
release `1790794300-4a33` em 2026-09-30) e de `artifact-type/reference/format.md` dele. A
camada 0 lê o `format.md` e o `deck-files.md` e fixa num teste o que o Whis gera.

## Geração e publicação

`gerar_daily(agora, *, configuracao, publicacao, pasta=None, simular=False) -> ResultadoDaDaily`:

1. lê `daily/atual.md` (`vault.ler_nota_viva`) e `montar_deck`;
2. `simular` → para aqui com o deck no resultado: **nada** é publicado nem gravado, nem o título
   que falta;
3. se falta `## O que terminei`, insere e grava a nota (ver *A nota*); se `daily/atual.md` nem
   existe, grava o modelo, para o botão do toast de nota vazia abrir uma nota que existe;
4. deck vazio → para aqui, resultado `vazio`: nada publicado, cópia datada não gravada;
5. escreve os arquivos de `slides_do_deck` numa pasta de trabalho fora do vault
   (`tempfile.mkdtemp(prefix="whis-daily-…")`, como o jornal); essa pasta é o `cwd` da sessão do
   CLI (como o jornal usa `html.parent`), porque o CLI só lê arquivo sob o diretório de trabalho,
   e todo caminho no pedido vai absoluto e com `/`;
6. endereço: o `deck:` do frontmatter da nota datada mais recente de `daily/` que tiver um
   (mesmo padrão de `jornal.ultima_url`); nenhum → a publicação **cria** o deck a partir do tipo
   Slides (`type_url` numa constante `TIPO_SLIDES`, fixada pela camada 0; título `Daily`) e
   depois o preenche. São **duas sessões do CLI**: a criação, e em seguida o fluxo normal de
   republicação abaixo. Se a criação passar e o preenchimento falhar, a falha carrega o link
   criado (`ErroDePublicacao` com `url`), e a cópia datada grava esse `deck:` mesmo assim — senão
   a execução seguinte criaria outro deck e o link deixaria de ser fixo;
7. publicação pelo Haiku (`PublicacaoDoDeck`, porta nova ao lado de `PublicacaoClaude`, mesmo
   `_AdaptadorDoJornal`, mesmo `AMBIENTE_DA_PUBLICACAO`), em turnos separados como no jornal:
   `read` do deck → `list` dos arquivos → `publish` com `url`, `root` = pasta de trabalho,
   `file_path` = `<root>/project/deck.json`, `files` com os slides de hoje mais `null` para cada
   `project/slides/*.html` listado que não existe hoje, `overwrite_unread` com os caminhos
   listados; **nunca** `force`, `capabilities`, `contract` ou `type_url` num republish. O
   sucesso é **só** a frase de publicação no resultado da ferramenta: a URL já está no pedido,
   então a queda de `jornal_claude.url_publicada` para o texto final contaria como publicado um
   Haiku que só repetiu o link — a daily não usa essa queda. `_PADRAO_DA_PUBLICACAO` do jornal
   exclui `Published files…`; a sonda registra a frase exata que um publish de arquivos num
   artifact tipado devolve e o padrão da daily é fixado por ela;
8. grava `daily/YYYY-MM-DD.md` (zona `daily/`), a **cópia**: frontmatter `tipo: daily`,
   `deck: <url>`, `gerada: <ISO com fuso>` — **sem** campo `data:` (armadilha da Daily notes do
   Obsidian, passo 8 de `docs/smoke-interface.md`) — e no corpo só as seções que viraram slide,
   na ordem do deck, cada uma com as linhas literais da nota. Gerar de novo no mesmo dia reescreve
   a cópia daquele dia;
9. devolve o resultado; a casca avisa.

**Falhas:**

- publicação falhou (credencial, recusa, sem URL na resposta, tempo esgotado): a cópia datada é
  gravada assim mesmo, com o `deck:` que já existia (ou o recém-criado, ou nenhum se nunca houve)
  e um callout `> [!warning]` dizendo o que falhou, como nas outras notas do Whis; o toast diz *A daily não publicou* e o botão abre
  `daily/atual.md` no Obsidian — é dela que ele lê na reunião; saída **parcial** (3). Login
  vencido segue o caminho que o toast da daily e do jornal já tiver para isso (`_login.vencido`,
  no trabalho da outra sessão);
- nota vazia: saída **0** (não é falha; o Vigia não deve reclamar) e toast *A nota da daily está
  vazia* com o botão que abre `daily/atual.md`;
- edição feita à mão no editor do Slides é sobrescrita na geração seguinte: o deck é a
  renderização da nota. Registrado no `CONTEXT.md`.

**Plano B** (só se a camada 0 reprovar A): `slides_do_deck` dá lugar a `pagina_do_deck(deck)`, um
HTML único de apresentação (setas/toque trocam slide, mesmo visual), e a publicação passa a ser a
do jornal (`PublicacaoClaude` com arquivo único), mantendo o critério da daily: sucesso só pela
frase de publicação no resultado da ferramenta, sem a queda para o texto final. `Deck`, a nota, a cópia datada, a casca e o
toast não mudam — é essa a razão da fronteira.

## Casca

- `whis daily [--simular] [--fakes] [--agendada] [--anotar TEXTO]`: `--simular` imprime os
  slides (título e itens) sem publicar nem gravar. `--fakes` **implica `simular` em todo
  caminho** — no CLI e no `daily` da palheta quando a bandeja roda em `--fakes` —, porque uma
  publicação fake que gravasse a cópia deixaria um `deck:` falso no vault, e a execução real
  seguinte o leria e perderia o link fixo para sempre. A publicação fake existe só para os
  testes, injetada direto em `gerar_daily`. Na palheta, `comandos_padrao` recebe um parâmetro
  `simular` (verdadeiro quando a bandeja roda em `--fakes`), e o `daily` simulado mostra o toast
  *Simulação: N slides, nada publicado*, sem botão. `--anotar` não muda. O relato no terminal: o link do
  deck e quantos slides saíram, ou o motivo de não sair;
- códigos de saída: 0 publicado ou nota vazia; 3 parcial (publicação falhou, cópia gravada);
  1 não nasceu (nem a cópia foi gravada: vault inacessível, config inválida). `_codigo_de_saida`
  (usado por `diario` e `daily`) trata "vazio" como 1: a daily ganha o seu próprio mapeamento, e
  o texto de ajuda (`CODIGOS_DE_SAIDA`, o epílogo comum aos três comandos) diz os códigos dela;
- palheta: `daily` continua com o rótulo *Generate daily*; a descrição passa a ser
  *Publish the daily slides from daily/atual.md (~1 min)*; o `Resultado` leva `link` para o deck;
  `open` continua abrindo `daily/atual.md`;
- toast: *A daily está pronta* + botão **Abrir slides** que abre o deck; nos casos de falha, os
  textos acima com o botão que abre a nota. Hoje `avisar_resultado` põe em todo botão com link o
  rótulo `ROTULO_DO_BOTAO_DO_JORNAL` (*Abrir jornal*): o rótulo passa a vir do `Resultado` (campo
  novo, com *Abrir jornal* como valor do jornal), para a daily não mostrar *Abrir jornal*;
- `Whis-Daily` e seus argumentos (`daily --agendada`) não mudam; o Vigia não muda;
- painel: duas chaves a menos; o comentário de `[daily].ativa` no modelo do TOML fala de slides;
- `CONTEXT.md`: reescrever **Daily** (o deck que ele apresenta, montado do que ele escreve; link
  fixo; cópia datada) e **Nota viva** (sete seções, todas dele; o agente só acrescenta linha a
  pedido — `note`/`doubt`/`do` — e o título que faltar); **Zona de propriedade** deixa de dizer
  que o agente cuida de *O que eu fiz*;
- `docs/smoke-daily.md` reescrito como o roteiro da prova nova, em PowerShell 5.1.

## Riscos nomeados

- **Slides headless não provado.** O jornal publica artifact comum; nunca criamos por `type_url`
  nem publicamos vários arquivos com `root` pelo CLI headless. A ferramenta `Artifact` do CLI
  (versão de `[claude].cli`) pode não ter `type_url`/`root` ou recusar. A camada 0 prova ou
  derruba; B é a saída.
- **Versão do deck.** Um republish de sessão nova exige ler o deck antes (o jornal já faz). Se
  ele abriu e editou no Slides, o `read` resolve; se o CLI recusar por arquivo não lido, o
  `overwrite_unread` cobre os slides listados.
- **Release do tipo.** O tipo Slides é de terceiro (`[core]`) e tem release própria; o formato
  do slide pode mudar. O teste de formato fixa o que geramos; uma recusa no publish vira aviso.
- **O artifact é da conta dele** e a sessão do agente vê um `%APPDATA%` virtual (memória
  `appdata-virtual-na-sessao`): as provas reais passam pela tarefa descartável ou pela tarefa real.

## Camadas

Suíte verde e um commit em `master` por camada. Nenhum teste publica, chama o CLI, mostra toast
ou escreve fora do `tmp_path`.

0. **Sonda** (`.scratch/daily-slides/research/`): primeiro lê `artifact-type/reference/format.md`
   e `deck-files.md` do tipo Slides (a revisão da spec não conseguiu lê-los por subagente; a
   sessão principal lê com `Artifact read` + `path`). Depois, com o CLI de `[claude].cli` e o
   ambiente da publicação do jornal, um Haiku headless (a) cria um deck pelo `type_url` do
   Slides, (b) publica slides e `deck.json` escritos à mão pelo formato acima, **de propósito**
   com sub-item aninhado, `<span>` monoespaçado e `<a href>`, (c) republica de uma sessão nova
   trocando um slide, removendo outro com `null` e trocando o `createdOnFiles.at`. Registra a
   frase exata do resultado de cada publish e mede tempo e custo por passo. Sai com o veredito A
   ou B, com as decisões de sub-item/inline/`at` fechadas e com o **deck de exemplo** (conteúdo
   real da nota dele) para ele aprovar o visual. O link do deck aprovado vira o endereço fixo,
   semeado como `deck:` no frontmatter da nota datada mais recente **de um dia anterior** (zona
   do agente), como o jornal semeou `artifact:` — nunca na de hoje, que a daily velha, ainda
   ativa até a camada 2, reescreveria sem o campo. Toda tag ou propriedade fora do `format.md`
   (`<b>`/`<i>`, `position` do rodapé, `padding-left`, sub-lista, `<span>`, `<a>`) é decidida
   aqui, **olhando o deck renderizado**, não relendo o arquivo publicado (que pode guardar uma
   tag que o visualizador ignora).
1. **O deck, aditivo**: `Deck`/`montar_deck`, `slides_do_deck`, `PublicacaoDoDeck` + fake, com
   testes. Nada da daily atual muda ainda, então a `Whis-Daily` segue rodando a daily velha entre
   as camadas. `montar_deck` lê cada seção pelo título (`conteudo(titulo)`) e **não** mexe em
   `SECOES` — senão a daily velha passaria a ver sete seções.
2. **A troca**, num commit só, para a tarefa agendada nunca apontar para uma daily pela metade:
   `gerar_daily` novo, cópia datada, `SECOES` e `MODELO_DA_NOTA_VIVA` com *O que terminei* na
   terceira posição, título que falta, **toda** a seção *Sai*, e tudo o que precisa estar certo
   no primeiro disparo da `Whis-Daily` depois dele: `_comando_daily` e o `daily` da palheta
   religados (fábrica da publicação no lugar de `fontes_da_daily=`/`roteiro_da_daily=`,
   `--fakes` implicando `simular`), o mapeamento de saída da daily (nota vazia = 0), os toasts
   da daily e o `Resultado` com rótulo de botão (*Abrir slides* na daily, *Abrir jornal* no
   jornal). Config antigo carregando; painel com duas chaves a menos; testes ajustados.
3. **Acabamento**: texto de ajuda com os códigos da daily, o `help` do subcomando `daily` e de
   `--simular`/`--fakes` (hoje falam de fontes e roteiro), a linha de uso no docstring de
   `__main__.py`, descrição do `daily` na palheta,
   comentário de `[daily].ativa` no modelo do TOML, `CONTEXT.md`, `docs/smoke-daily.md`.
4. **Prova**: `whis daily` real publicando no deck fixo; `Whis-Daily` disparada à mão (saída 0,
   toast, cópia datada). O fechamento é dele: a próxima daily do time apresentada pelo deck.

## Testes

- `montar_deck`: seções vazias somem; ordem; recuo; parágrafo solto; corte em `(2/2)` sem partir
  item; nota sem *O que terminei*; *Pontos* e *Fazer* nunca entram;
- `slides_do_deck`: um `<section>` por arquivo com `id` igual ao nome; nada fora da lista de
  elementos permitidos; HTML escapado (`<script>` na nota sai como texto); conversão de cada
  inline markdown; `deck.json` com `order` igual aos arquivos;
- publicação: os pedidos de criação e de republicação (texto do prompt: mapa `files` com os
  slides de hoje, a instrução de pôr `null` em cada slide listado que não está no mapa — quem
  monta esses `null` é o Haiku a partir do `list`, o Python não conhece a lista —, sem `force`),
  e o extrator próprio da daily (padrão fixado pela sonda, as duas grafias de URL, **sem** a
  queda para o texto final de `jornal_claude.url_publicada`);
- costura: `--simular` não escreve nada, nem o título; nota vazia não publica nem grava cópia,
  mas insere o título que falta; falha da publicação grava a cópia com aviso e o `deck:` antigo;
  falha depois da criação grava o `deck:` recém-criado; publish sem a frase da ferramenta é
  falha mesmo com a URL no texto; título inserido uma vez e a nota fica byte a byte igual no
  resto (admitindo a linha em branco que `_abrir_secao` põe antes do título novo); nota
  inexistente vira o modelo gravado; `deck:` lido da cópia mais recente que tem um, ignorando as datadas
  antigas sem ele; a cópia só tem as seções que viraram slide;
- casca: `whis daily --fakes` e o `daily` da palheta com a bandeja em `--fakes` não escrevem no
  vault e não chamam a publicação; `--agendada` com `ativa = false` sai 0 sem gerar; os três códigos de saída da daily
  (nota vazia é 0) sem mudar os do `diario` e do `news`; toast da daily com *Abrir slides* e o do
  jornal ainda com *Abrir jornal*; palheta com o link; config com as chaves antigas carrega.
  Testes existentes a ajustar: `test_comando_codigos_de_saida.py` (hoje daily vazia sai 1),
  `test_avisos_finais.py`, `test_palheta.py`, `test_painel.py`, `test_configuracao_escrita.py`,
  `test_daily_ativa.py`, `test_prompts.py` (usa `DailyFake`, `fontes_de_exemplo_da_daily` e as
  fábricas da daily) e `test_login_do_claude.py` (do conserto do jornal; usa `ResultadoDaDaily`,
  `JanelaDaDaily` e `resultado_da_daily`).

## Fora do escopo

Reescrever ou resumir o texto dele; capa; slides de *Pontos* e *Fazer*; limpar a nota
automaticamente ou por comando; um deck novo por dia; design system; notas do apresentador;
imagens; mudar o diário, o `ask` ou as fontes passivas.
