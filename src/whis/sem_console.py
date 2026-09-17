"""Nenhuma janela de terminal, nunca: todo processo filho nasce sem console.

A bandeja e as tarefas agendadas rodam sob `pythonw.exe`, que não tem console.
Um filho de console (`git`, o PowerShell do toast, o `cmd /c start`, o CLI do
Claude que o `claude-agent-sdk` abre por `anyio.open_process`) ganha então um
console **novo**, e é a janela preta que o usuário viu piscar a cada comando.

Duas peças: `opcoes()` são os argumentos que cada chamada explícita passa ao
`subprocess`; `instalar()` é o interruptor global para o que não passa por
nós — faz `subprocess.Popen` nascer com as mesmas flags por padrão. O
`__main__` o liga quando não há console (`sys.stdout is None`); com console,
nada muda, porque o filho herda o do pai.
"""

from __future__ import annotations

import logging
import subprocess
import sys

_log = logging.getLogger("whis.sem_console")

_MARCA = "_whis_sem_console"


def opcoes() -> dict:
    """`creationflags` + `startupinfo` que escondem o console do filho (só no Windows)."""
    if sys.platform != "win32":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": _escondido()}


def instalar(popen: type = subprocess.Popen) -> bool:
    """Faz todo `Popen` nascer sem console. Idempotente; devolve se instalou agora."""
    if sys.platform != "win32" or getattr(popen, _MARCA, False):
        return False
    original = popen.__init__

    def __init__(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        kwargs["startupinfo"] = _escondido(kwargs.get("startupinfo"))
        original(self, *args, **kwargs)

    popen.__init__ = __init__
    setattr(popen, _MARCA, True)
    _log.info("Processos filhos nascem sem console a partir daqui.")
    return True


def _escondido(info=None):
    info = info or subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return info
