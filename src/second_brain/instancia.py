"""Trava de instância única: duas bandejas não podem disputar o microfone.

O modo de falha é banal e caro: o usuário clica no atalho de novo (ou o atalho
de inicialização dispara com a bandeja já aberta), sobem dois ícones iguais, e o
segundo gravador tenta abrir os mesmos dispositivos. Na melhor hipótese a
segunda gravação nasce muda; na pior, o usuário clica no ícone errado e a
reunião não está sendo gravada por ninguém.

A trava é um arquivo com bloqueio de faixa do próprio Windows
(`msvcrt.locking`), não um "arquivo existe?": bloqueio de faixa é do sistema
operacional, então ele **some sozinho** se o processo morrer, travar ou for
morto pelo Gerenciador de Tarefas. Um arquivo-marcador exigiria limpeza manual
depois de todo crash — exatamente na hora em que o usuário menos quer aprender
sobre arquivos de lock.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from types import TracebackType

_log = logging.getLogger("second_brain.instancia")

NOME_DA_TRAVA = "bandeja.lock"


class OutraInstancia(RuntimeError):
    """Já existe uma bandeja rodando nesta máquina."""


class Trava:
    """Bloqueio exclusivo enquanto o processo viver.

    Use como contexto::

        with Trava(caminho):
            ...  # ninguém mais entra aqui

    `pid_registrado()` conta quem está segurando, para a mensagem de erro poder
    dizer algo mais útil que "já tem outra".
    """

    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)
        self._descritor: int | None = None

    def adquirir(self) -> "Trava":
        """Toma a trava, ou levanta `OutraInstancia`."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        descritor = os.open(self.caminho, os.O_RDWR | os.O_CREAT)
        try:
            _travar(descritor)
        except OSError as erro:
            os.close(descritor)
            dono = self.pid_registrado()
            de_quem = f" (processo {dono})" if dono else ""
            raise OutraInstancia(
                f"já existe uma bandeja do Second Brain rodando nesta máquina{de_quem}. "
                f"Procure o ícone perto do relógio — inclusive na setinha de ícones "
                f"ocultos — em vez de abrir outra."
            ) from erro
        # O byte 0 é o que fica travado, e no Windows a trava é obrigatória:
        # ninguém consegue nem ler aquele byte. Por isso o PID mora do byte 1
        # em diante — senão a mensagem "quem está segurando" não teria como ser
        # lida justamente por quem precisa dela.
        os.truncate(descritor, 0)
        os.lseek(descritor, 1, os.SEEK_SET)
        os.write(descritor, str(os.getpid()).encode("ascii"))
        os.fsync(descritor)
        self._descritor = descritor
        _log.debug("Trava de instância única adquirida em %s", self.caminho)
        return self

    def liberar(self) -> None:
        """Devolve a trava. O sistema já faria isso ao fim do processo."""
        if self._descritor is None:
            return
        try:
            _destravar(self._descritor)
        except OSError:  # o processo está saindo; o SO libera de todo jeito
            pass
        os.close(self._descritor)
        self._descritor = None

    def pid_registrado(self) -> int | None:
        """O PID que a trava anotou, quando dá para ler.

        Lê a partir do byte 1: o byte 0 é a faixa travada, e no Windows nem a
        leitura dele é permitida enquanto alguém segura a trava.
        """
        try:
            with open(self.caminho, "rb") as arquivo:
                arquivo.seek(1)
                conteudo = arquivo.read().decode("ascii").strip()
        except (OSError, UnicodeDecodeError):
            return None
        return int(conteudo) if conteudo.isdigit() else None

    def __enter__(self) -> "Trava":
        return self.adquirir()

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None:
        self.liberar()


def caminho_da_trava(configuracao) -> Path:
    """A trava mora ao lado da configuração, com o log da bandeja."""
    base = configuracao.origem.parent if configuracao.origem else Path.home()
    return base / NOME_DA_TRAVA


def _travar(descritor: int) -> None:
    try:
        import msvcrt
    except ImportError:  # fora do Windows (só no desenvolvimento)
        import fcntl

        fcntl.flock(descritor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    msvcrt.locking(descritor, msvcrt.LK_NBLCK, 1)


def _destravar(descritor: int) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(descritor, fcntl.LOCK_UN)
        return
    os.lseek(descritor, 0, os.SEEK_SET)
    msvcrt.locking(descritor, msvcrt.LK_UNLCK, 1)
