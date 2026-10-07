# Spec: atalhos da daily na palheta

Status: ready-for-agent

Origem: pedido dele em 2026-09-30, com as decisões fechadas uma a uma em 2026-10-01 (tabela
abaixo). Glossário em `CONTEXT.md`; a daily em slides, que esta entrega estende, está em
`.scratch/daily-slides/spec.md`.

## Problem Statement

A daily é o deck montado do que **ele** escreve em `daily/atual.md`. Para escrever ali hoje ele
abre o Obsidian, acha a seção e digita; para dizer que terminou uma coisa, recorta a linha de
*O que estou fazendo* e cola em *O que eu fiz*. Ele pediu, literal: *"Cria os atalhos de escrever
o que eu fiz, o que estou fazendo e uma maneira fácil de mudar o que estou fazendo para feito"*.

Ao responder para onde vai o "feito", ele viu que *O que eu fiz* e *O que terminei* (seção criada
na entrega da daily em slides, em 2026-09-30) dizem a mesma coisa: *"são redundantes, não tem pq
ter os dois"*.

## Solution

1. *O que terminei* sai: a nota volta a ter seis seções e o deck, quatro slides de seção.
2. `did <texto>` e `doing <texto>` na palheta acrescentam uma linha em *O que eu fiz* e em
   *O que estou fazendo*, como `note` faz em *Pontos*.
3. `done` abre na própria palheta a lista dos itens de *O que estou fazendo*; Enter move o
   selecionado, com o que está embaixo dele, para *O que eu fiz*. A janela fica aberta para mover
   outro.

## Decisões dele (2026-10-01)

| Pergunta | Decisão |
|---|---|
| "Feito" vai para *O que eu fiz* ou *O que terminei*? | São redundantes: **fica *O que eu fiz***, *O que terminei* sai. |
| Nomes | **`did`**, **`doing`**, **`done`**, em inglês como os outros comandos. |
| Como `done` escolhe o item | **Lista na palheta**, como `prompts`; não por texto casado. |
| Enter na lista | **Move e a janela fica aberta**; o item some da lista e o rodapé confirma. |
| Registro | Spec em `.scratch/atalhos-da-daily/`, no padrão do repositório. |
| `note` na daily (depois da primeira daily real, 13:55) | **`note` escreve em *Falar***; *Pontos* sai, como *O que terminei*. O `note` dele caiu em *Pontos*, que nunca ia para o deck. |
| `note` de novo (2026-10-07) | **`note` escreve em *Pontos***, e *Pontos* vai para o deck **no lugar de *Falar***; `daily --anotar` e o `anotar` da DM vão junto. *Falar* fica na nota como texto dele, fora do deck. |

## A nota: seis seções

`SECAO_TERMINEI` sai de `nota_viva.py` (constante, `SECOES`, `MODELO_DA_NOTA_VIVA`) e de
`SECOES_DO_DECK` em `deck.py`. Ficam, na ordem: *O que eu fiz*, *O que estou fazendo*, *Fazer*,
*Dúvidas*, *Pontos*, *Falar*. O deck mostra *O que eu fiz*, *O que estou fazendo*, *Dúvidas* e
*Falar*.

A nota real dele não tem `## O que terminei` (lida em 2026-10-01: só *Dúvidas*, *Pontos*, *Fazer*
e uma seção dele), e a primeira geração real da daily é em 2026-10-01 às
13:55. Nada do que ele escreveu muda. Uma nota que ainda tenha `## O que terminei` é tratada como
qualquer seção que não é das seis: fica onde está, intocada, e não entra no deck.

## `did` e `doing`

- `did <texto>` acrescenta `- texto` no fim de *O que eu fiz*; `doing <texto>`, no fim de
  *O que estou fazendo*. Sem caixa `[ ]` — a caixa é só de *Fazer*.
- Seção que falta é aberta no lugar dela, como `note` já faz (`NotaViva._abrir_secao`).
- Dispara e some; o toast é o de `note`: *"Anotado em O que eu fiz"* com o texto e o botão
  *Abrir no Obsidian*. Sem texto: *"Anotar o quê?"* com o uso (`did <o texto>`).
- Por baixo, `SECOES_ANOTAVEIS` ganha *O que eu fiz* e *O que estou fazendo*; `anotar` e
  `vault.anotar_ponto` não mudam de forma.

## `done`

Um `Comando` com `lista`, como `prompts`: `done` (ou `done <busca>`) + Enter, ou o clique na
ação, troca a lista de comandos pela lista dos itens de *O que estou fazendo*.

A `ListaDoFazendo` tem `nome = "Done"` e placeholder *"Search O que estou fazendo…"*; o
`Comando` tem `parametro="search"`, para o Tab completar `done `.

**As linhas.** Todo item de lista (`- `, `* `, `+ `, `1. `) de *O que estou fazendo*, inclusive
os aninhados, na ordem da nota. Linha que não é item (parágrafo, embed `![[…]]`) não aparece
sozinha; vai junto se estiver indentada embaixo de um item. O item só com marcador (`- `, o que
o Obsidian deixa ao dar Enter) também não aparece, pela régua de `_SO_MARCADOR`; dentro de uma
subárvore ele viaja como qualquer linha. Cada `Linha` tem o texto do item como título e, para
um sub-item, o caminho dos pais na descrição, de fora para dentro (`em: Avô › Pai`). O marcador
`- [ ]` / `- [x]`, se ele usar, fica no texto como está.

**O filtro.** O texto digitado filtra por substring no texto do item, sem diferenciar maiúscula
nem acento (a régua de `_chave`). Campo vazio mostra todos.

**O detalhe.** O painel embaixo mostra as linhas literais que vão mudar de seção: o item e a
subárvore dele.

**Enter: mover.** O gesto principal (`<Return>`, dica *"Mark done"*) leva o item para
*O que eu fiz*, pela lógica do mover que existiu até `928a7c0` (`NotaViva.mover`,
`_garantir_cabecalhos`, `_itens`, `_fim_da_subarvore`), sem os ids por hash:

- a linha e tudo o que está mais indentado embaixo dela saem de *O que estou fazendo* e entram
  em *O que eu fiz* **byte a byte** iguais (tab, espaço à direita, linha em branco no meio da
  subárvore);
- a **cadeia** do item é a dos pais, de fora para dentro, mais o próprio item. Cada elo é
  garantido em *O que eu fiz* nessa ordem: o primeiro elo é um item de nível raiz de *O que eu
  fiz* com o mesmo texto; cada elo seguinte é um **filho direto** do elo anterior com o mesmo
  texto. "Mesmo texto" é o texto do item sem marcador nem recuo nas pontas, comparado exato. O
  elo que falta entra com a sua linha literal, como último filho do elo anterior, ou no fim da
  seção se for o primeiro;
- o que está embaixo do item (a subárvore sem a primeira linha) entra como últimos filhos do
  elo do item em *O que eu fiz*. Assim, mover sem pais leva o bloco para o fim da seção; mover um
  sub-item copia os pais como cabeçalho de grupo; e mover o pai **depois** dos filhos não o
  duplica: os filhos já estão sob o pai copiado, e o que restou embaixo dele se junta a eles;
- os pais **ficam** em *O que estou fazendo*;
- *O que eu fiz* que falta é aberta no lugar dela;
- toda outra linha da nota sai igual. Remover e inserir são de linhas inteiras.

A régua de casar elos é mais estrita que a de `_descendente_com_texto` em `928a7c0`, que aceitava
o texto em qualquer profundidade; vale a desta spec, e um teste a fixa.

Depois do mover a janela **fica aberta**: a lista é relida (o item já não está), a seleção fica
na mesma posição, e o rodapé mostra `Moved: <texto>` (`Efeito.mensagem`). Esc, ou Backspace com
o campo vazio, volta aos comandos; Esc de novo fecha.

**O clique.** Clicar numa linha roda o primeiro gesto, como em `prompts`: também move.

**A nota mudou no meio.** Ele pode editar no Obsidian com a lista aberta. A lista guarda, para
cada linha, a posição do item no corpo de *O que estou fazendo* e a linha literal dele, e o
gesto chama `vault.concluir_item(vault, posicao, linha)`. Esse lê a nota de novo e chama
`NotaViva.concluir(posicao, linha)`, que reencontra o item na leitura nova: primeiro a linha
literal na posição guardada; senão, a linha literal em *O que estou fazendo*, se for uma só. Pais
e fim da subárvore são recalculados por essa leitura. Sem item, `concluir` devolve `None`, nada é
gravado, e a `ListaDoFazendo` põe no rodapé *"The note changed — try again"*, com a lista relida.
Com item, devolve as linhas que entraram em *O que eu fiz*, e `concluir_item` grava a nota.

**Lista vazia.** *"Nothing in O que estou fazendo — type: doing <text>"*. Sem nada que case com
a busca: *"No item matches"*.

**Fora da janela.** `done` despachado sem janela (o caminho de `rodar`) devolve um toast que
explica, como `prompts_fora_da_janela`.

## Onde mexe

| Arquivo | O quê |
|---|---|
| `src/whis/nota_viva.py` | Sai *O que terminei*; `SECOES_ANOTAVEIS` com *fiz* e *fazendo*; `Item`, `itens(secao)` e `concluir(posicao, linha)` (o mover sem ids); a docstring do módulo deixa de dizer "as duas únicas escritas" e "toda edição é inserção". |
| `src/whis/vault.py` | `concluir_item(vault, posicao, linha)`: lê, move e grava literal, como `anotar_ponto`; a docstring de `anotar_ponto` passa a citar *fiz*/*fazendo* e `did`/`doing`. |
| `src/whis/deck.py` | Sai *terminei* de `SECOES_DO_DECK`. |
| `src/whis/palheta.py` | `did`, `doing`, `done`; a `ListaDoFazendo`; `ORDEM_DAS_ACOES` com os três logo depois de `daily`; a docstring do módulo; o toast da daily vazia deixa de dizer "terminou" (*"Escreva o que fez e está fazendo, e gere de novo."*). |
| `tests/` | `test_nota_viva`, `test_palheta`, `test_deck`, `test_daily`, `fixtures/daily.py`; testes primeiro. |
| `CONTEXT.md` | **Daily** (quatro slides), **Nota viva** (seis seções; `did`, `doing`, `done`), **Zona de propriedade** (na nota viva o agente acrescenta e, com `done`, move, sempre a pedido), **Palheta** (comandos; `done` abre lista como `prompts`). |
| `docs/smoke-interface.md`, `docs/smoke-daily.md` | Passos dos comandos novos; seis seções. |

Rótulos e descrições na palheta, em inglês como os outros:

| Comando | Rótulo | Descrição |
|---|---|---|
| `did` | Did | Add a line to O que eu fiz in daily/atual.md |
| `doing` | Doing | Add a line to O que estou fazendo in daily/atual.md |
| `done` | Mark done | Move an item from O que estou fazendo to O que eu fiz |

## Fora do escopo

- Desfazer um mover pela palheta: ele conserta no Obsidian.
- `whis daily --anotar` no terminal continua só em *Pontos*.
- Mover de volta, ou entre outras seções.
- Mexer no callout antigo do topo da nota dele: é texto dele.

## Testes

- `NotaViva`: `itens` com aninhamento, tab e espaço, sem o item só com marcador; `concluir` de
  item raiz, de sub-item (pais copiados), de dois irmãos seguidos (um pai copiado só), do pai
  depois dos filhos (sem pai duplicado), de um texto igual em outra profundidade de *fiz* (não
  casa), com subárvore que tem linha em branco e embed, com *O que eu fiz* ausente, com CRLF,
  com a nota mudada (posição deslocada acha pela literal; literal sumida ou repetida devolve
  `None` sem mexer); toda linha fora do bloco movido sai byte a byte; anotar em *fiz* e
  *fazendo* sem caixa; nota sem *O que terminei* no modelo; seção `## O que terminei` antiga
  intocada e fora do deck.
- Palheta: `did`/`doing` gravam e avisam (com o `AvisoEspiao`); texto vazio; `done` tem `lista`;
  `ListaDoFazendo` lista, filtra sem acento, mostra o detalhe, move com Enter e devolve
  `Efeito` com a mensagem; nota mudada entre ler e mover; lista vazia.
- Nenhum teste mostra toast nem publica: as fixtures autouse do `conftest` continuam valendo.

## Prova

Com a bandeja reiniciada no código novo: `doing` uma linha, `did` outra, `done`, filtrar,
Enter, ver o item em *O que eu fiz* no Obsidian e a lista sem ele; mover um sub-item e ver o pai
copiado; mover o pai e ver que ele não se repete. Um clique numa linha também move, sem desfazer:
o passo avisa. Os passos entram em `docs/smoke-interface.md`.
