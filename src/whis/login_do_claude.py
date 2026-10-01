"""O login do Claude vencido, reconhecido na mensagem que o CLI devolve.

Os adaptadores embrulham o erro do SDK num texto e é só esse texto que chega
aos toasts; o CLI usa as mesmas frases seja qual for o adaptador.
"""

from __future__ import annotations

import re

TITULO = "O login do Claude venceu"
PEDIDO = "Rode 'claude auth login' num terminal."

_SINAIS_DO_CLI = re.compile(r"Failed to authenticate|OAuth session expired|Please run /login")


def vencido(texto: str | None) -> bool:
    return bool(texto and _SINAIS_DO_CLI.search(texto))
