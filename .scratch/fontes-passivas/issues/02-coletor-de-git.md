# 02 — Coletor de git

**What to build:** `fonte_git.py`: a implementação de `PortaFonte` que varre uma raiz de
desenvolvimento atrás de repositórios e devolve os commits do usuário na janela. É a fonte
mais barata e a única sem token — deve funcionar na máquina do usuário no dia em que a
camada 01 fechar.

**Blocked by:** 01

**Status:** resolved

- [x] Varredura de `[git].raiz` atrás de repositórios, respeitando `[git].profundidade` e `[git].excluir`; aceita `.git` como pasta **e como arquivo** (worktree e submódulo)
- [x] Autoria: usa `[git].autores` quando preenchido; vazio, deduz do `git config user.email` de cada repositório — é o que faz o coletor funcionar num repo com e-mail diferente sem cadastro manual
- [x] `git log` na janela com `--all --no-merges` e data local, traduzido para `Evento` com `momento` aware, `titulo` = assunto do commit, `referencia` = nome do repositório, e o hash curto disponível para a nota
- [x] Repositório que falhar (pasta corrompida, git ausente no PATH) não derruba a coleta inteira: o erro entra no log e os outros repositórios seguem
- [x] `de_configuracao(configuracao) -> FonteGit` e `nome = "git"`, como no contrato
- [x] Testes sem rede e sem tocar os repositórios do usuário: criam repositórios de verdade em `tmp_path` com `git init` + commits datados, e provam a varredura, o recorte da janela, a exclusão de pastas, a dedução de autor e o repositório quebrado que não contamina os outros
- [x] Acrescenta **só** o teste do ramo `git` de `montar_fontes`; nenhum outro arquivo compartilhado é editado

## Notas para o executor

- A [pesquisa](../../second-brain/research/12-fontes-passivas.md) tem os detalhes já
  levantados: `--all` importa porque commit em branch não mergeada some sem ele;
  `--date=iso-local` normaliza o fuso; shallow clone é detectável por
  `git rev-parse --is-shallow-repository`; `.git` é arquivo em worktree e submódulo.
- `git -C <repo>` evita `cd` — use.
- Varredura de disco é a parte que pode ficar lenta. A profundidade configurável existe
  para isso; não varra o disco inteiro e não siga junções.
- Nada de dependência nova: `subprocess` e o git que já está na máquina.

## Comments

**Camada 02 entregue** — `fonte_git.py` e `tests/test_fonte_git.py`, 30 testes, nenhum arquivo
compartilhado tocado.

O executor achou e consertou um bug de verdade durante as provas manuais: **`git log --since`
esconde commit do dia**. O flag para a caminhada no primeiro commit mais velho que a data, entao
um tip com data de commit velha (rebase que preserva a data de autoria, relogio fora de hora,
historico importado) apaga em silencio os commits do dia que estao abaixo dele. E `--until`
compara data de *commit*, que um rebase de amanha move. A fonte passou a caminhar o historico e
recortar a janela em Python, como o contrato ja exigia.

Isso desvia da letra do criterio ("`git log` na janela") e o executor surfaceou o desvio em vez
de esconder. Aceito: o comportamento externo e o mesmo e o contrato manda a fonte recortar.

**Fechada pelo orquestrador.** Provas conferidas, nao so reportadas:

- Reproduzi o bug do `--since` sozinho, num repositorio construido para isso: dois commits do
  dia, o tip com `GIT_COMMITTER_DATE` de um ano atras. `git log --all --since --until` devolve
  **nada** — pior que o relatado, some com os dois. O coletor recupera os dois.
- Mutacao valida (repus `--since`/`--until` no comando montado): caem exatamente os dois testes
  de regressao novos, `test_commit_do_dia_sob_um_tip_com_data_velha_nao_some` e
  `test_commit_rebaseado_depois_continua_no_dia_em_que_foi_escrito`.
- Rodei o coletor contra a raiz real `C:/Users/gabri/development`: **23 eventos reais** do dia,
  em 6,3s, de dois repositorios (`second-brain` e `flavianasser-monorepo`), com autor deduzido
  do `user.email` de cada um.
- Um repositorio quebrado deixado por engano no scratchpad provou em uso real o criterio "um
  repositorio que falha nao derruba os outros": erro no log, coleta seguiu.
- `pytest` 405 verdes, 5 desselecionados.
