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

**Status:** ready-for-agent

- [ ] `portas.py`: `Daily` com `entreguei`, `sigo_em`, `preciso_de` e `duvidas`; `ResumoDoDia` **não** muda
- [ ] `resumo_dia_claude.py`: método (ou porta irmã) que devolve `Daily` a partir dos eventos da janela, com prompt que separa **o trabalho dele** do **contexto do time**
- [ ] `daily.py`: `gerar_daily(agora)` — janela da última daily de um dia anterior até agora, coleta, filtro de exclusão, reuniões, pontos do usuário, resumo, escrita; mesma degradação graciosa do diário
- [ ] `vault.py`: zona `daily/` em `ESTRUTURA` e `ZONAS_DA_DAILY`; `montar_daily`; leitura do `ate` da daily anterior; leitura dos itens desmarcados de `notas/daily.md`; escrita em `notas/daily.md` **só** pelo `--anotar`
- [ ] Subcomando `second-brain daily [--anotar TEXTO] [--fakes] [--simular]`, imprimindo o roteiro pronto para ler em voz alta
- [ ] O que reaproveita coleta/filtro/reuniões com `diario.py` é **fatorado**, não duplicado — os 39 testes de `test_diario.py` continuam verdes sem edição
- [ ] Testes de comportamento: a janela ancora na daily anterior; segunda-feira cobre o fim de semana; rodar duas vezes no mesmo dia mantém o `desde` e estende o `ate`; a primeira daily de todas cai para 24h e diz isso; item desmarcado aparece e item marcado não; `--anotar` cria e acrescenta em `notas/daily.md`; seção manual vazia não aparece; a daily escreve **só** em `daily/` (e em `notas/daily.md` apenas com `--anotar`)
- [ ] Suíte inteira verde (**465 hoje**, 6 desselecionados), sem editar teste existente

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
