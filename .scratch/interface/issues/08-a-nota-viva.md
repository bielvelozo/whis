# 08 — Camada 1: a nota viva

Type: task
Status: resolved
Blocked by: 07

**What to build:** `daily/atual.md`, a nota que o Whis **mantém** em vez de reescrever — e a regra
que faz a entrega valer: ao mover um item de *O que estou fazendo* para *O que eu fiz*, o texto
do usuário é transportado **byte a byte**.

Spec: [../spec.md](../spec.md), *A daily viva* e *Testing Decisions*. As palavras do usuário:
[05-o-dia-do-usuario.md](05-o-dia-do-usuario.md), rodadas 3, 4 e 7.

- [x] `daily/atual.md` com quatro seções, nesta ordem: `## O que eu fiz`, `## O que estou fazendo`
      (do agente), `## Dúvidas`, `## Falar` (só do usuário). Nasce de um modelo com callout
      explicando as regras dentro da nota, como `MODELO_DOS_PONTOS` fazia.
- [x] Terceira zona de propriedade declarada no `CONTEXT.md` (a sessão principal escreve o
      glossário; o executor aponta o que precisa constar).
- [x] A porta `Daily` muda: recebe os eventos da janela **e os itens abertos** de *O que estou
      fazendo* (com um identificador estável por item); devolve itens **novos** para *fiz* e para
      *fazendo* e a lista de identificadores a **mover**. O modelo nunca devolve texto de item
      existente; quem move é `vault`, copiando a linha literal.
- [x] Texto novo segue a régua das dailies à mão dele: agrupado por quem pediu, ancorado no
      sintoma, id da issue inline, roteiro seco (sem personalidade). Prompt em
      `resumo_dia_claude.py`.
- [x] `anotar X` (`daily --anotar`) escreve em `## Falar` de `daily/atual.md`, append-only.
      `notas/daily.md` é aposentado: não é lido nem escrito. O agente **lê** *Dúvidas* e *Falar*
      só para não duplicar; nunca os escreve.
- [x] `daily/YYYY-MM-DD.md` continua nascendo com frontmatter (âncora `desde`/`ate`), a cobertura
      da janela e as listas cruas; o roteiro falado vive em `atual.md`.
- [x] `DailyFake` atualizado; `--fakes` exercita a nota viva de ponta a ponta.
- [x] **Testes que mais importam:** (1) item aberto que continua aberto sai igual ao que entrou,
      byte a byte, após `gerar_daily`; (2) item movido chega em *fiz* byte a byte igual, e some
      de *fazendo*; (3) *Dúvidas* e *Falar* intocadas por `gerar_daily` e por qualquer caminho
      indireto (hash do trecho antes e depois); (4) `--anotar` só acrescenta em *Falar*; (5)
      escrita de `atual.md` só alcança `daily/`.
- [x] Suíte inteira verde. Testes existentes que afirmam decisão revertida (roteiro dentro da
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

## Comments

**Camada 1 entregue e fechada** (2026-09-12; executor `nota-viva`, revisão e gate na sessão principal).

- Módulo novo `src/whis/nota_viva.py`: a nota como linhas cruas em blocos por título; toda edição é
  inserção ou remoção de linhas inteiras, nunca reescrita. Quebra de linha preservada
  (`vault.escrever(..., literal=True)`). Ids = 6 hex de sha1 do texto do item, desempate por posição.
  `Daily` = `fiz`/`fazendo` (`ItemNovo(texto, sob)`) + `mover` (ids); `PortaDaily.resumir_daily(eventos, reunioes, nota)`.
- Mover copia linha + subárvore e leva os ancestrais como cabeçalhos literais; `sob` aceita id ou o
  texto de outro item novo da mesma resposta (é como o modelo monta "Correções que o Ribeiro apontou"
  com os achados de uma vez). Texto repetido não entra; id desconhecido é logado e ignorado.
- Janela nova arquiva *O que eu fiz* na nota datada (`## O que eu fiz na daily anterior`) e recomeça;
  a presença dessa seção na datada de hoje é o sinal de "já arquivado" na reexecução.
- Três listas vazias são resposta válida (a segunda execução do dia sem novidade não sai marcada);
  JSON sem nenhuma das chaves é recusado. Modelo ilegível: `atual.md` intacta, datada marcada, saída 3.
- **Prova manual na sessão principal**, com uma nota escrita no formato dele (numeração `1.`, sub-itens
  por tab, um item com três espaços à direita, texto solto em *Falar*): após `whis daily --fakes`
  duas vezes e `--anotar`, `cat -A` mostrou tabs e espaços à direita idênticos, o item movido chegou
  literal com a subárvore, *Dúvidas* e *Falar* sem um byte alterado, e `- lembrar do pix` acrescentado
  só no fim de *Falar*.
- Suíte: **904 verdes** (eram 873), 8 desselecionados. Testes existentes editados/removidos por
  afirmarem decisão revertida — listados um a um pelo executor: em `test_daily.py` (roteiro na nota
  datada; `notas/daily.md`/`PontosDaDaily`; `Preciso de`), `test_comando_daily.py` (impressão do
  roteiro; os cinco de `--anotar`), `test_roteiro_da_daily.py` (campos novos; roteiro vazio deixa de ser
  falha), `test_daily_do_trabalho.py` (nove sobre `notas/daily.md`/`MODELO_DOS_PONTOS`/`preciso_de`),
  `test_atendente.py` (dois de `anotar`), `test_comando_codigos_de_saida.py` (helper e um aviso).
  `test_o_preciso_de_dele_nunca_vai_ao_claude` removido de propósito: as seções dele agora **vão** ao
  modelo como contexto só-leitura, por decisão da spec.
- Riscos anotados pelo executor: dedupe de cabeçalho por texto (dois grupos com o mesmo texto aninham
  no primeiro); uma linha `---` dentro de *O que eu fiz* seria cortada na releitura da datada; o
  prompt real ainda não foi provado contra o Claude (fica para a prova na máquina do usuário).
- `docs/smoke-daily.md` e `docs/smoke-atendente.md` atualizados. `CONTEXT.md` ganhou **Nota viva** e
  a zona de propriedade com três contratos.
