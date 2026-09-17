# 15 — Camada 8: o visual da palheta igual ao Raycast

Type: task
Status: resolved
Blocked by: 14

**What to build:** o que a terceira prova do usuário (2026-09-17, com a camada 7 no ar) pediu, nas
palavras dele, junto de uma captura do Raycast para Windows (Quick AI): *"ficou legal mas o fundo
pode ser mais preto e tipo do raycast mesmo, não tem problema copiar e deixar os detalhes em roxo
pra diferenciar"*.

O que a captura mostra e vale copiar: painel quase preto (não cinza), praticamente opaco, cantos
arredondados e uma borda fina de 1 px; o campo grande em cima com placeholder cinza; uma linha
separadora sutil; as linhas da lista com glifo, título em branco e descrição em cinza, e a
selecionada num realce arredondado que não encosta na borda; um rodapé separado por linha, com o
nome à esquerda e as ações à direita com as teclas desenhadas como teclas (`↵`, `Ctrl` `K`).

- [x] Fundo `#0e0e10` em vez de `#1c1c1e`; tinta do acrílico mais opaca (`0xE8`) e **sem `-alpha`**
      na janela: ficou provado que qualquer alpha (0.98, 0.95) deixa o texto de trás legível
      através do painel, e o pedido era preto — só o material do acrílico atravessa.
- [x] Borda de 1 px em roxo apagado (é o "detalhe" que diferencia); glifos, palavra do comando e o
      nome do comando à direita de cada linha em roxo; o resto branco e cinza como no Raycast.
- [x] Linhas desenhadas no canvas, com o realce da selecionada arredondado e recuado.
- [x] Rodapé: `◆ Whis` à esquerda; `Run ↵` e `Complete Tab` à direita, com as teclas em caixinhas.
- [x] **Bug reportado no meio da prova** — *"Cadê o comando de parar a gravação? só tem de
      iniciar"*: `record` é um só e o rótulo vira *Stop recording* enquanto grava, mas a lista só
      era redesenhada quando o filtro mudava; ao reabrir a palheta com o campo vazio a linha
      continuava *Start recording*. `mostrar()` passa a redesenhar sempre; teste com rótulo
      dinâmico na janela de verdade.
- [x] Suíte verde; prova de tela sob `pythonw` sobre a tela dele; bandeja dele reiniciada.

## Notas para o executor

- Nunca simule o atalho real dele (`ctrl+space`) com a bandeja no ar.
- O reinício é pela rota de `research/rota-tarefa-descartavel/` (parar, depois a ação direta
  `pythonw -m whis bandeja` sem limite de tempo).

## Comments

**Camada 8 entregue e fechada** (2026-09-17; direto na sessão principal, no meio da terceira prova dele).

- Janela redesenhada no canvas: fundo `#0e0e10`, borda de 1 px `#4a4380`, realce da selecionada
  arredondado e recuado (`#232327`), glifo e nome do comando à direita em `#8b7cf6`, rodapé com
  `◆ Whis`, `Run ↵` e `Complete Tab` desenhados como teclas. O campo (`Text`) entra no canvas uma
  vez só — apagá-lo a cada redesenho desmontava o widget, o foco caía e o vigia de foco escondia a
  janela na primeira filtragem (achado da prova, corrigido).
- Opacidade: tinta do acrílico a `0xE8` e **nenhum `-alpha`**. Provado com capturas sobre a nota do
  Obsidian dele: com alpha 0.98 e 0.95 o texto de trás fica legível através do painel; sem alpha o
  painel lê como preto e só o material do DWM atravessa. O fallback sem acrílico continua com
  `-transparentcolor` + `-alpha 0.96`.
- `record`: `mostrar()` redesenha a lista sempre, então *Start recording* vira *Stop recording* ao
  reabrir a palheta gravando; `titulos_desenhados()` deixa o teste da janela de verdade ver isso.
- Suíte: **1071 verdes / 8 desselecionados** (o teste da janela de verdade ganhou o rótulo dinâmico).
  Capturas finais no scratchpad da sessão (`provaFinal/`): vazia, `generate daily`, `note ` + Tab,
  Tab de novo — todas com a janela mapeada e o foco no campo.

**Correção depois da prova dele** (2026-09-17, "o fundo está bugado", com print: parte do painel preta,
parte cinza-azulada em faixas retangulares).

- Reproduzido na janela de verdade sob `pythonw` medindo quatro cantos do painel
  (`research/sonda-acrilico-reexibir.py`): na primeira abertura os quatro dão (28, 28, 32); ao
  esconder e mostrar de novo, três viram (66, 75, 79) — o material do DWM **sem a tinta**. É o DWM
  deste build esquecendo a política do acrílico quando a janela some e volta; o que ele viu em
  faixas é a recomposição parcial forçada por outras janelas por cima.
- Testadas três saídas: reaplicar a política ao mostrar (não resolve), `SetWindowPos` com
  `SWP_FRAMECHANGED` (não resolve), **desligar o acrílico ao esconder e ligar de novo ao mostrar**
  (resolve: as três aberturas dão (28, 28, 32)). É o que `esconder`/`mostrar` fazem agora
  (`_despir`/`_vestir`; `acrilico.desligar_acrilico`), com os cantos pedidos uma vez só.
- Suíte: **1072 verdes / 8 desselecionados** (+1 em `test_acrilico.py`). Bandeja dele reiniciada.
