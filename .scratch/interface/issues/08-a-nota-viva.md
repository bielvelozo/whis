# 08 — Camada 1: a nota viva

Type: task
Status: ready-for-agent
Blocked by: 07

**What to build:** `daily/atual.md`, a nota que o Whis **mantém** em vez de reescrever — e a regra
que faz a entrega valer: ao mover um item de *O que estou fazendo* para *O que eu fiz*, o texto
do usuário é transportado **byte a byte**.

Spec: [../spec.md](../spec.md), *A daily viva* e *Testing Decisions*. As palavras do usuário:
[05-o-dia-do-usuario.md](05-o-dia-do-usuario.md), rodadas 3, 4 e 7.

- [ ] `daily/atual.md` com quatro seções, nesta ordem: `## O que eu fiz`, `## O que estou fazendo`
      (do agente), `## Dúvidas`, `## Falar` (só do usuário). Nasce de um modelo com callout
      explicando as regras dentro da nota, como `MODELO_DOS_PONTOS` fazia.
- [ ] Terceira zona de propriedade declarada no `CONTEXT.md` (a sessão principal escreve o
      glossário; o executor aponta o que precisa constar).
- [ ] A porta `Daily` muda: recebe os eventos da janela **e os itens abertos** de *O que estou
      fazendo* (com um identificador estável por item); devolve itens **novos** para *fiz* e para
      *fazendo* e a lista de identificadores a **mover**. O modelo nunca devolve texto de item
      existente; quem move é `vault`, copiando a linha literal.
- [ ] Texto novo segue a régua das dailies à mão dele: agrupado por quem pediu, ancorado no
      sintoma, id da issue inline, roteiro seco (sem personalidade). Prompt em
      `resumo_dia_claude.py`.
- [ ] `anotar X` (`daily --anotar`) escreve em `## Falar` de `daily/atual.md`, append-only.
      `notas/daily.md` é aposentado: não é lido nem escrito. O agente **lê** *Dúvidas* e *Falar*
      só para não duplicar; nunca os escreve.
- [ ] `daily/YYYY-MM-DD.md` continua nascendo com frontmatter (âncora `desde`/`ate`), a cobertura
      da janela e as listas cruas; o roteiro falado vive em `atual.md`.
- [ ] `DailyFake` atualizado; `--fakes` exercita a nota viva de ponta a ponta.
- [ ] **Testes que mais importam:** (1) item aberto que continua aberto sai igual ao que entrou,
      byte a byte, após `gerar_daily`; (2) item movido chega em *fiz* byte a byte igual, e some
      de *fazendo*; (3) *Dúvidas* e *Falar* intocadas por `gerar_daily` e por qualquer caminho
      indireto (hash do trecho antes e depois); (4) `--anotar` só acrescenta em *Falar*; (5)
      escrita de `atual.md` só alcança `daily/`.
- [ ] Suíte inteira verde. Testes existentes que afirmam decisão revertida (roteiro dentro da
      nota datada; `--anotar` em `notas/daily.md`) podem ser editados, **listados um a um** no
      comentário de entrega, com o porquê.

## Notas para o executor

- O identificador do item pode ser o índice da linha na seção, ou um hash curto do texto — o
  que importa é que o modelo aponte e a costura copie. Um item que o modelo aponta e não existe
  é ignorado com log, nunca inventado.
- Linhas aninhadas sob um item (sub-bullets, continuação) viajam com ele.
- `resumo_dia_claude.interpretar_daily` ganha os campos novos; resposta ilegível continua não
  custando a nota.
- Rodar duas vezes no mesmo dia não duplica item: o que já está em *fazendo* ou *fiz* não volta.
