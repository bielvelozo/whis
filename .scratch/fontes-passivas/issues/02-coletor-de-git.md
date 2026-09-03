# 02 — Coletor de git

**What to build:** `fonte_git.py`: a implementação de `PortaFonte` que varre uma raiz de
desenvolvimento atrás de repositórios e devolve os commits do usuário na janela. É a fonte
mais barata e a única sem token — deve funcionar na máquina do usuário no dia em que a
camada 01 fechar.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Varredura de `[git].raiz` atrás de repositórios, respeitando `[git].profundidade` e `[git].excluir`; aceita `.git` como pasta **e como arquivo** (worktree e submódulo)
- [ ] Autoria: usa `[git].autores` quando preenchido; vazio, deduz do `git config user.email` de cada repositório — é o que faz o coletor funcionar num repo com e-mail diferente sem cadastro manual
- [ ] `git log` na janela com `--all --no-merges` e data local, traduzido para `Evento` com `momento` aware, `titulo` = assunto do commit, `referencia` = nome do repositório, e o hash curto disponível para a nota
- [ ] Repositório que falhar (pasta corrompida, git ausente no PATH) não derruba a coleta inteira: o erro entra no log e os outros repositórios seguem
- [ ] `de_configuracao(configuracao) -> FonteGit` e `nome = "git"`, como no contrato
- [ ] Testes sem rede e sem tocar os repositórios do usuário: criam repositórios de verdade em `tmp_path` com `git init` + commits datados, e provam a varredura, o recorte da janela, a exclusão de pastas, a dedução de autor e o repositório quebrado que não contamina os outros
- [ ] Acrescenta **só** o teste do ramo `git` de `montar_fontes`; nenhum outro arquivo compartilhado é editado

## Notas para o executor

- A [pesquisa](../../second-brain/research/12-fontes-passivas.md) tem os detalhes já
  levantados: `--all` importa porque commit em branch não mergeada some sem ele;
  `--date=iso-local` normaliza o fuso; shallow clone é detectável por
  `git rev-parse --is-shallow-repository`; `.git` é arquivo em worktree e submódulo.
- `git -C <repo>` evita `cd` — use.
- Varredura de disco é a parte que pode ficar lenta. A profundidade configurável existe
  para isso; não varra o disco inteiro e não siga junções.
- Nada de dependência nova: `subprocess` e o git que já está na máquina.
