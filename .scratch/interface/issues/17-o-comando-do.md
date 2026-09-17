# 17 — Camada 10: o comando `do` e a seção *Fazer* da nota viva

Type: task
Status: claimed
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

- [ ] `nota_viva.py`: `SECAO_FAZER`, a seção na ordem de `SECOES` depois de `SECAO_FAZENDO`,
      `SECOES_ANOTAVEIS` ganhando *Fazer*, `MODELO_DA_NOTA_VIVA` com o título novo. `anotar` numa
      seção com caixa escreve `- [ ] texto`; nas outras, `- texto` como hoje. Nota antiga sem
      *Fazer* ganha a seção **na ordem** (entre *O que estou fazendo* e *Dúvidas*), sem tocar o
      resto — a mesma régua de `_abrir_secao`.
- [ ] `palheta.py`: `Comando("do", …, anotar_em(SECAO_FAZER, "do"), parametro="text")`, rótulo `To-do`,
      descrição em inglês como os outros, ícone; `ORDEM_DAS_ACOES` com o `do` depois do `doubt`.
      Toast "Anotado em Fazer" com o botão do Obsidian, pelo mesmo caminho de `note`/`doubt`.
- [ ] Prompt da daily (`resumo_dia_claude.py`): a nota passa a ter **seis** seções e *Fazer* entra na
      lista das que são do usuário — chega como contexto, o modelo nunca escreve nela.
- [ ] Docs: `CONTEXT.md` › **Nota viva** e **Palheta** (a seção nova e o oitavo comando),
      `docs/smoke-interface.md` (tabela do passo 5), nota de revisão no topo de `.scratch/interface/spec.md`.
- [ ] Suíte verde; prova de tela da janela de verdade sob `pythonw` (o `do` na lista, o ícone sem
      tofu); bandeja dele reiniciada pela rota, esperando a tarefa de parar acabar.

## Notas para o executor

- Nunca simule o atalho real dele (`ctrl+space`) com a bandeja no ar.
- Os ids de item (`id_do_item`) servem só às seções do agente; marcar `[x]` muda o id e não importa.
- Testes existentes que fixam a ordem das seções ou a contagem dos comandos podem ser editados —
  listar um a um nos comentários (regra da orquestração).

## Comments
