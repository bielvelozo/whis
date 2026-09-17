# 17 — Camada 10: o comando `do` e a seção *Fazer* da nota viva

Type: task
Status: resolved
Blocked by: 16

**What to build:** o pedido dele, nas palavras dele (2026-09-17):

> Incluir uma nova seção de nota que vai ser **Fazer**: o comando vai ser **`do`** e vai ser
> registrado na daily atual com um `[ ]` checkmark pra mim marcar quando eu fizer.

Um oitavo comando na palheta, `do <texto>`, que acrescenta `- [ ] texto` numa seção nova `## Fazer`
de `daily/atual.md`. A caixa é dele: ele marca `[x]` à mão no Obsidian.

**Decisões de desenho, respondidas por ele nesta sessão:**

1. **Posição:** *Fazer* entra **depois de *O que estou fazendo***, antes de *Dúvidas*. A nota lê
   "fiz / estou fazendo / falta fazer", e as duas seções do agente continuam juntas no topo.
2. **Os `[x]` ao virar a janela da daily:** **nada acontece**. A seção é do usuário e é transportada
   literalmente, como *Dúvidas*, *Pontos* e *Falar*; o agente nunca escreve nem apaga ali por conta
   própria. Ele tira os marcados à mão.
3. **Terminal:** o `do` **não** ganha subcomando. `whis daily --anotar` continua indo para *Pontos*;
   a spec desta entrega reduziu o terminal, e o gesto novo é da palheta.

- [x] `nota_viva.py`: `SECAO_FAZER`, a seção na ordem de `SECOES` depois de `SECAO_FAZENDO`,
      `SECOES_ANOTAVEIS` ganhando *Fazer*, `MODELO_DA_NOTA_VIVA` com o título novo. `anotar` numa
      seção com caixa escreve `- [ ] texto`; nas outras, `- texto` como hoje. Nota antiga sem
      *Fazer* ganha a seção **na ordem** (entre *O que estou fazendo* e *Dúvidas*), sem tocar o
      resto — a mesma régua de `_abrir_secao`.
- [x] `palheta.py`: `Comando("do", …, anotar_em(SECAO_FAZER, "do"), parametro="text")`, rótulo `To-do`,
      descrição em inglês como os outros, ícone; `ORDEM_DAS_ACOES` com o `do` depois do `doubt`.
      Toast "Anotado em Fazer" com o botão do Obsidian, pelo mesmo caminho de `note`/`doubt`.
- [x] Prompt da daily (`resumo_dia_claude.py`): a nota passa a ter **seis** seções e *Fazer* entra na
      lista das que são do usuário — chega como contexto, o modelo nunca escreve nela.
- [x] Docs: `CONTEXT.md` › **Nota viva** e **Palheta** (a seção nova e o oitavo comando),
      `docs/smoke-interface.md` (tabela do passo 5), nota de revisão no topo de `.scratch/interface/spec.md`.
- [x] Suíte verde; prova de tela da janela de verdade sob `pythonw` (o `do` na lista, o ícone sem
      tofu); bandeja dele reiniciada pela rota, esperando a tarefa de parar acabar.

## Notas para o executor

- Nunca simule o atalho real dele (`ctrl+space`) com a bandeja no ar.
- Os ids de item (`id_do_item`) servem só às seções do agente; marcar `[x]` muda o id e não importa.
- Testes existentes que fixam a ordem das seções ou a contagem dos comandos podem ser editados —
  listar um a um nos comentários (regra da orquestração).

## Comments

**Camada 10 entregue e fechada** (2026-09-17; direto na sessão principal, com teste primeiro).

- `nota_viva.py`: `SECAO_FAZER` na terceira posição de `SECOES`, `SECOES_ANOTAVEIS` com *Fazer*,
  `SECOES_COM_CAIXA`/`CAIXA` e `anotar` escrevendo `- [ ] texto` só nas seções com caixa. A seção
  nasce na ordem pelo `_abrir_secao` que já existia — nada de novo ali.
- `palheta.py`: oitavo comando `do`, rótulo *To-do*, ícone `☐`, `parametro="text"`, pelo mesmo
  `anotar_em`/`anotar_ponto` de `note`/`doubt`; toast "Anotado em Fazer" com o botão do Obsidian.
- **Achado da prova de tela:** com `do` digitado, a lista trazia *Doubt* selecionado (a ordem era a
  da janela), e Tab completaria `doubt `. `filtrar` passou a pôr o **nome exato** na frente de quem
  só começa igual — um teste novo fixa isso (`test_o_nome_exato_vem_na_frente...`).
- Prompt da daily: seis seções, *Fazer* na lista das dele, com o aviso de que nem a linha marcada
  `[x]` é movida ou reescrita.
- **Testes existentes editados, um a um:** `test_palheta.py` — `COMANDOS` (+`do`), `ACOES` (+linha
  *To-do*), `test_sao_os_sete_comandos…` → `…oito`, os três `filtrar`/`completar` por índice;
  `test_nota_viva.py` — `test_o_modelo_tem_as_cinco_secoes…` → `…seis`; `test_daily.py` —
  `test_o_resultado_traz_as_quatro_secoes…` → `…seis` e a lista da ordem; `test_comando_daily.py` —
  a tupla das seções impressas ganhou `Fazer:`; `test_roteiro_da_daily.py` —
  `test_prompt_diz_que_duvidas_e_falar_sao_do_usuario` → `…que_as_secoes_dele_sao_dele_inclusive_o_fazer`.
- Suíte: **1077 verdes / 8 desselecionados** (+5: 2 na nota viva, 3 na palheta contando o caso
  parametrizado de `do` sem texto). Commit `d02e9de`.
- Prova de tela sob `pythonw` (`research/sonda-do.py`, capturas em `.scratch/prova-do/`): a linha
  *To-do* com o `☐` **sem tofu** no Segoe UI, o nome `do` em roxo à direita, e com `do` digitado a
  linha certa fica selecionada. Bandeja dele reiniciada pela rota às 20:15:55 (pids 17432/23280),
  log real `Atalho global ctrl+space registrado.`
- **Falta a prova dele:** abrir a palheta, rodar `do <algo>` e ver a seção nascer em `daily/atual.md`.
