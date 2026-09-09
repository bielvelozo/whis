"""Fonte passiva de git local: os commits do dia nos repositórios da máquina.

A mais barata das três fontes e a única sem token — quem responde é o git que
já está instalado, chamado por subprocesso. A varredura parte de `[git].raiz`,
desce até `[git].profundidade` níveis atrás de repositórios e pula o que
estiver em `[git].excluir`.

O que vale saber antes de mexer:

- **Autoria por repositório.** Sem `[git].autores`, cada repositório responde
  quem é o usuário nele (`git config user.email`). É o que faz o coletor
  funcionar no repositório do trabalho e no pessoal, com e-mails diferentes,
  sem cadastro manual nenhum.
- **`--all`** porque commit em branch não mergeada some sem ele, e
  **`--no-merges`** porque merge commit é ruído no diário.
- **`%aI` em vez de `--date=iso-local`**: a data do commit vem com o fuso em
  que ele foi feito e a conversão para o fuso local acontece aqui, no
  `datetime` — um commit feito em viagem cai na hora certa do dia do usuário.
- **A janela é recortada aqui, não pelo git.** O motivo está em
  `_argumentos_do_log`, e não é detalhe: `--since` esconde commit do dia.
- **Um repositório que falha não derruba os outros**: o motivo vai para o log e
  a coleta segue. Só quando *nenhum* repositório pôde ser lido é que a fonte
  falha inteira — um git mudo que se passasse por "dia sem commits" seria pior
  que um diário marcado como incompleto.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path

from .configuracao import Configuracao
from .fontes import ErroDeFonte, Evento, Janela

_log = logging.getLogger("whis.fonte_git")

#: O nome desta fonte no contrato — vai para o frontmatter e para a seção da nota.
NOME = "git"

#: Quanto esperar por um `git` que travou num repositório antes de desistir dele.
TEMPO_LIMITE_S = 60.0

_CAMPO = "\x1f"
_REGISTRO = "\x1e"

#: Hash completo (para não repetir commit), hash curto (para a nota), data de
#: autoria com fuso, autor e assunto. Separadores de controle porque assunto de
#: commit aceita qualquer pontuação.
_FORMATO = _CAMPO.join(("%H", "%h", "%aI", "%an", "%s")) + _REGISTRO

#: Sob `pythonw.exe` — atalho de logon e tarefa agendada — cada chamada ao git
#: piscaria um console preto na tela do usuário sem esta flag, que só existe no
#: Windows (nos outros sistemas o valor 0 é o "sem flag nenhuma").
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FonteGit:
    """Os commits do usuário na janela, varridos de uma raiz de desenvolvimento.

    `git` é o executável a chamar; existe para o teste apontar um git que não
    existe e provar que a fonte trata isso — não para trocar o git por um dublê.
    """

    nome = NOME

    def __init__(
        self,
        raiz: Path | str,
        *,
        profundidade: int = 3,
        excluir: Sequence[str] = (),
        autores: Sequence[str] = (),
        git: str = "git",
        tempo_limite_s: float = TEMPO_LIMITE_S,
    ) -> None:
        self._raiz = Path(raiz).expanduser()
        self._profundidade = max(int(profundidade), 0)
        self._excluir = tuple(
            padrao.strip().replace("\\", "/").casefold()
            for padrao in excluir
            if padrao and padrao.strip()
        )
        self._autores = tuple(autor.strip() for autor in autores if autor and autor.strip())
        self._git = git
        self._tempo_limite_s = tempo_limite_s

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        """Os commits do usuário na janela, um `Evento` por commit."""
        if not self._raiz.is_dir():
            raise ErroDeFonte(
                f"Raiz de desenvolvimento não encontrada: {self._raiz}. Aponte "
                "[git].raiz para a pasta onde seus repositórios ficam (barras "
                'normais, como "C:/Users/voce/development") ou deixe a chave '
                "vazia para desligar a fonte git."
            )

        repositorios = self.repositorios()
        if not repositorios:
            _log.warning(
                "Nenhum repositório git em %s até %d nível(is). Confira "
                "[git].raiz e [git].profundidade.",
                self._raiz,
                self._profundidade,
            )
            return ()

        eventos: list[Evento] = []
        ja_vistos: set[str] = set()
        falhas: list[str] = []
        for repositorio in repositorios:
            try:
                for identidade, evento in self._commits(repositorio, janela):
                    # Worktree e clone de backup mostram o mesmo commit por
                    # caminhos diferentes; no diário isso viraria a mesma linha
                    # duas vezes, em duas seções.
                    if identidade in ja_vistos:
                        continue
                    ja_vistos.add(identidade)
                    eventos.append(evento)
            except ErroDeFonte as erro:
                falhas.append(f"{repositorio.name}: {erro}")
                _log.error(
                    "Repositório fora do diário — %s: %s", repositorio, erro
                )

        if len(falhas) == len(repositorios):
            raise ErroDeFonte(
                f"Nenhum dos {len(repositorios)} repositórios de {self._raiz} pôde "
                f"ser lido. Primeiro motivo — {falhas[0]}"
            )

        _log.info(
            "git: %d commit(s) em %d repositório(s) lido(s)%s.",
            len(eventos),
            len(repositorios) - len(falhas),
            f", {len(falhas)} com falha" if falhas else "",
        )
        return tuple(eventos)

    def repositorios(self) -> tuple[Path, ...]:
        """Os repositórios sob a raiz, em ordem estável.

        Aceita `.git` como pasta e como **arquivo** — é assim que worktree e
        submódulo se apresentam. Não entra em junção nem em symlink: seguir uma
        junção que aponta para a raiz do disco varreria o computador inteiro.
        """
        encontrados: list[Path] = []
        pendentes: list[tuple[Path, int]] = [(self._raiz, 0)]
        while pendentes:
            pasta, nivel = pendentes.pop()
            if (pasta / ".git").exists():
                encontrados.append(pasta)
            if nivel >= self._profundidade:
                continue
            for filha in _subpastas(pasta):
                if filha.name == ".git" or self._excluida(filha):
                    continue
                pendentes.append((filha, nivel + 1))
        return tuple(sorted(encontrados))

    # -- por repositório ----------------------------------------------------

    def _commits(
        self, repositorio: Path, janela: Janela
    ) -> Iterator[tuple[str, Evento]]:
        autores = self._autores_de(repositorio)
        if not autores:
            _log.warning(
                "Repositório %s sem 'user.email': não dá para saber quais "
                "commits são seus. Rode 'git -C %s config user.email <seu "
                "e-mail>' ou preencha [git].autores na configuração.",
                repositorio,
                repositorio,
            )
            return

        saida = self._executar(repositorio, self._argumentos_do_log(autores))
        referencia = repositorio.name
        for registro in saida.split(_REGISTRO):
            campos = registro.strip("\r\n").split(_CAMPO)
            if len(campos) != 5:
                continue
            completo, curto, data, autor, assunto = campos
            momento = _momento_local(data)
            if momento is None or not janela.contem(momento):
                continue
            yield completo, Evento(
                fonte=NOME,
                momento=momento,
                titulo=f"`{curto}` {assunto.strip() or '(sem assunto)'}",
                referencia=referencia,
                pessoas=(autor.strip(),) if autor.strip() else (),
            )

    def _autores_de(self, repositorio: Path) -> tuple[str, ...]:
        """Quem é o usuário neste repositório — a configuração ou o próprio git.

        `git config user.email` sai com código 1 quando a chave não existe, e
        isso não é falha do repositório: é um repositório em que o usuário
        nunca commitou.
        """
        if self._autores:
            return self._autores
        email = self._executar(
            repositorio, ["config", "user.email"], tolerar=(1,)
        ).strip()
        return (email,) if email else ()

    def _argumentos_do_log(self, autores: Sequence[str]) -> list[str]:
        """O `git log` de todos os commits do usuário — a janela é recortada aqui.

        Nem `--since` nem `--until`, de propósito, apesar de serem o caminho
        óbvio: `--since` **para a caminhada** no primeiro commit mais velho que
        a data, então um tip com data velha (rebase que preserva a data de
        autoria, relógio fora de hora, histórico importado) esconderia em
        silêncio os commits de hoje que vêm depois dele. E `--until` compara a
        data de *commit*, que um rebase de amanhã muda — o commit escrito hoje
        sairia do diário de hoje. Caminhar o histórico inteiro custou 0,9s nos
        15 repositórios (8.815 commits) da máquina do usuário, uma vez por dia.
        """
        return [
            "log",
            "--all",
            "--no-merges",
            # E-mail é texto, não expressão: sem `--fixed-strings` um `+` no
            # endereço viraria quantificador de regex e o git recusaria o log.
            "--fixed-strings",
            "--regexp-ignore-case",
            *(f"--author={autor}" for autor in autores),
            f"--pretty=format:{_FORMATO}",
        ]

    def _executar(
        self, repositorio: Path, argumentos: Sequence[str], *, tolerar: Sequence[int] = ()
    ) -> str:
        comando = [self._git, "-C", str(repositorio), *argumentos]
        try:
            concluido = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._tempo_limite_s,
                creationflags=_SEM_JANELA,
                check=False,
            )
        except FileNotFoundError as erro:
            raise ErroDeFonte(
                f"O git não foi encontrado no PATH ('{self._git}'). Instale o Git "
                "para Windows ou deixe [git].raiz vazio para desligar a fonte."
            ) from erro
        except subprocess.TimeoutExpired as erro:
            raise ErroDeFonte(
                f"O git passou de {self._tempo_limite_s:.0f}s em {repositorio} e "
                "foi interrompido. Confira o repositório à mão ou acrescente a "
                "pasta a [git].excluir."
            ) from erro
        except OSError as erro:
            raise ErroDeFonte(
                f"Não foi possível chamar o git em {repositorio}: {erro}."
            ) from erro

        if concluido.returncode != 0 and concluido.returncode not in tolerar:
            raise ErroDeFonte(
                f"'git {' '.join(argumentos)}' terminou com código "
                f"{concluido.returncode}: {_resumir(concluido.stderr)}"
            )
        return concluido.stdout or ""

    def _excluida(self, pasta: Path) -> bool:
        nome = pasta.name.casefold()
        try:
            caminho = pasta.relative_to(self._raiz).as_posix().casefold()
        except ValueError:
            caminho = pasta.as_posix().casefold()
        return any(padrao == nome or padrao in caminho for padrao in self._excluir)


def de_configuracao(configuracao: Configuracao, **extras: object) -> FonteGit:
    """Monta o coletor a partir da configuração local — o atalho da CLI.

    Só chega aqui com `[git].raiz` preenchida: chave vazia é fonte desligada, e
    quem decide isso é `montar_fontes`.
    """
    if configuracao.git_raiz is None:
        raise ErroDeFonte(
            "Fonte git sem raiz de desenvolvimento: preencha [git].raiz na "
            f"configuração{f' ({configuracao.origem})' if configuracao.origem else ''} "
            "com a pasta onde seus repositórios ficam."
        )
    return FonteGit(
        configuracao.git_raiz,
        profundidade=configuracao.git_profundidade,
        excluir=configuracao.git_excluir,
        autores=configuracao.git_autores,
        **extras,  # type: ignore[arg-type]
    )


def _subpastas(pasta: Path) -> Iterator[Path]:
    """As subpastas reais de `pasta` — sem symlink, sem junção, sem barulho.

    Pasta ilegível (permissão, disco de rede fora do ar) só some da varredura:
    o diário do dia não pode morrer porque uma pasta qualquer da raiz travou.
    """
    try:
        with os.scandir(pasta) as entradas:
            for entrada in entradas:
                try:
                    if entrada.is_symlink() or entrada.is_junction():
                        continue
                    if entrada.is_dir(follow_symlinks=False):
                        yield Path(entrada.path)
                except OSError:
                    continue
    except OSError as erro:
        _log.debug("Pasta ignorada na varredura (%s): %s", pasta, erro)


def _momento_local(bruto: str) -> datetime | None:
    """A data de autoria do commit, convertida para o fuso do usuário."""
    try:
        return datetime.fromisoformat(bruto.strip()).astimezone()
    except ValueError:
        return None


def _resumir(texto: str, limite: int = 200) -> str:
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    resumo = " ".join(linhas) or "sem mensagem de erro"
    return resumo if len(resumo) <= limite else f"{resumo[:limite]}…"
