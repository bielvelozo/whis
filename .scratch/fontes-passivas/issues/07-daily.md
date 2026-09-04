# 07 — `second-brain daily`

**What to build:** O roteiro falado que o usuário lê na daily do time. Coletor próprio,
com **janela da última daily até agora**, escrevendo `daily/YYYY-MM-DD.md`: o roteiro em
cima (o que ele lê) e as listas cruas embaixo (a memória durável do vault). Mais
`notas/daily.md`, o arquivo da zona dele onde ele anota o que quer levantar.

Escopo acrescentado pelo usuário em 2026-09-03, depois de ler o primeiro diário real, e
**redesenhado na mesma conversa**. Uma versão anterior deste ticket derivava a daily do
diário; está obsoleta e o trabalho parcial dela ficou em `git stash@{0}` (aproveite o que
servir do tipo `Daily` e do prompt, ignore o resto).

Leia o **adendo (seção 9)** do [contrato](../contrato-fonte-passiva.md) inteiro: ele fixa a
janela, o tipo, os dois arquivos e o comportamento do comando.

**Blocked by:** 01, 04

**Status:** resolved

- [x] `portas.py`: `Daily` com `entreguei`, `sigo_em`, `preciso_de` e `duvidas`; `ResumoDoDia` **não** muda
- [x] `resumo_dia_claude.py`: método (ou porta irmã) que devolve `Daily` a partir dos eventos da janela, com prompt que separa **o trabalho dele** do **contexto do time**
- [x] `daily.py`: `gerar_daily(agora)` — janela da última daily de um dia anterior até agora, coleta, filtro de exclusão, reuniões, pontos do usuário, resumo, escrita; mesma degradação graciosa do diário
- [x] `vault.py`: zona `daily/` em `ESTRUTURA` e `ZONAS_DA_DAILY`; `montar_daily`; leitura do `ate` da daily anterior; leitura dos itens desmarcados de `notas/daily.md`; escrita em `notas/daily.md` **só** pelo `--anotar`
- [x] Subcomando `second-brain daily [--anotar TEXTO] [--fakes] [--simular]`, imprimindo o roteiro pronto para ler em voz alta
- [x] O que reaproveita coleta/filtro/reuniões com `diario.py` é **fatorado**, não duplicado — os 39 testes de `test_diario.py` continuam verdes sem edição
- [x] Testes de comportamento: a janela ancora na daily anterior; segunda-feira cobre o fim de semana; rodar duas vezes no mesmo dia mantém o `desde` e estende o `ate`; a primeira daily de todas cai para 24h e diz isso; item desmarcado aparece e item marcado não; `--anotar` cria e acrescenta em `notas/daily.md`; seção manual vazia não aparece; a daily escreve **só** em `daily/` (e em `notas/daily.md` apenas com `--anotar`)
- [x] Suíte inteira verde (**465 hoje**, 6 desselecionados), sem editar teste existente

## Notas para o executor

- **A janela é o coração desta camada.** `desde` = o `ate` da daily mais recente **de um dia
  anterior** (não a de hoje, senão rodar de novo daria janela vazia). Sem nenhuma daily
  anterior, cai para `agora - 24h` e a nota diz que foi a primeira. A âncora mora no
  frontmatter da nota anterior, **não** num arquivo de estado escondido.
- **A linha "Cobre de ... até agora" é obrigatória** na nota. Sem ela o usuário lê a daily
  de sexta numa segunda achando que é de ontem.
- **`preciso_de` só tem o que espera outra pessoa.** Review parado, PR sem merge, aprovação
  pendente. Nota para si mesmo não é daily. Foi o pedido explícito do usuário. Para calibrar,
  do dia real dele: "PRs #1623 e #1628 aguardando merge humano" **entra**; "estado 'expirou'
  não exercitado na validação" **não entra**; "FN-1617, FN-1618 e FN-1619 em In Progress no
  fim do dia" é **`sigo_em`**.
- **O git é dele, o Linear é do time.** A fonte de git já filtra por autor; o Linear traz o
  time inteiro (172 eventos contra 28 commits, medido num dia real). `entreguei` e `sigo_em`
  são o trabalho **dele**; movimentação alheia é contexto e no máximo vira `duvidas` ou
  `preciso_de`. O prompt precisa ser explícito.
- **`notas/` é a zona do usuário.** O agente lê os itens desmarcados e **nunca marca nada** —
  quem marca é ele, no Obsidian, depois de falar. A única escrita permitida é o `--anotar`,
  que é o "pedido explícito" que o glossário prevê. Um bug que reescreva aquele arquivo
  apaga texto que o usuário digitou: trate `notas/daily.md` como append-only.
- Você **pode** editar `portas.py`, `vault.py`, `resumo_dia_claude.py`, `__main__.py` e criar
  `daily.py`. Pode fatorar o que `diario.py` compartilha, desde que os testes dele fiquem
  verdes **sem edição**. Não toque em `fontes.py`, `configuracao.py` nem nos coletores.
- **Nada é agendado.** O usuário decidiu rodar na hora. Não crie tarefa do Windows.
- O diário continua existindo como comando e **deixa de ser agendado** — isso é da camada 06,
  não sua. Não mexa em `automacao.py`.

## Comments

**Camada 07 entregue** — `daily.py`, `coleta.py` (a leitura de fontes fatorada e compartilhada
com `diario.py`), mais `portas.py`, `vault.py`, `resumo_dia_claude.py`, `__main__.py` e 73
testes novos. Suite em **538 verdes**, 7 desselecionados. Os 40 testes de `test_diario.py`
continuam verdes **sem edicao** — a fatoracao nao mexeu no comportamento da costura irma.

O executor **morreu no fim** (stall de 600s do watchdog), enquanto acrescentava um teste de rede
opcional para o prompt. O trabalho ja estava completo e verde; revisei e fechei direto, sem
relancar executor, dentro da politica de execucao direta aprovada.

**Fechada pelo orquestrador.** Provas executadas por mim, nao reportadas:

- **Janela ancorada**: gerei uma daily na sexta as 09:00 e outra na segunda as 09:00. A de
  segunda ancorou exatamente no `ate` da de sexta (`Fri 04/09 09:00 -> Mon 07/09 09:00`) e trouxe
  os commits de **sabado e domingo** — o fim de semana nao caiu no vao.
- **Primeira daily**: sem nota anterior, cai para 24h e a nota **diz isso** em portugues.
- **Rodar de novo no mesmo dia**: manteve o `desde` e estendeu o `ate` (`09:00 -> 11:00`), com
  **um arquivo por dia** em `daily/`.
- **`notas/daily.md` intacto**: escrevi o arquivo a mao com item marcado, item desmarcado e um
  comentario HTML; depois de `gerar_daily` o hash do arquivo **nao mudou**. So os desmarcados
  entraram na nota; o marcado ficou de fora.
- **`--anotar` e append puro**: o comentario do usuario, o item marcado e o texto anterior
  sobreviveram, e o texto antigo continua sendo prefixo do novo.
- **Zona de propriedade**: a daily escreveu so em `daily/`; `notas/ideias.md` e a nota de reuniao
  intactas; `escrever(..., zonas=ZONAS_DA_DAILY)` recusa `diario/` e `notas/`.
- **Mutacoes**: perder a ancora na daily anterior derruba 2 testes; fazer a janela escorregar ao
  rodar de novo no mesmo dia derruba outros 2.

Nao provado: o texto real do Claude para as batidas. O teste de rede gasta a assinatura do
usuario e nao foi rodado; o executor morreu justamente ao acrescenta-lo, entao ele **nao existe**.
Anotado no DEFERRED.
