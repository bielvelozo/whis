r"""Onde o Whis escreve o log quando não há ninguém olhando o terminal.

Os comandos que rodam sem console — a bandeja (iniciada pelo atalho de logon,
com `pythonw.exe`) e as tarefas agendadas da daily e do jornal — não teriam
outro lugar para contar o que fizeram e por que falharam.

O arquivo mora ao lado do `config.toml`, em `%APPDATA%\whis\`, que é o
lugar que o usuário já conhece por causa da configuração.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .configuracao import Configuracao

NOME_DO_ARQUIVO = "bandeja.log"

_FORMATO = "%(asctime)s  %(levelname)s  %(name)s  %(message)s"


def arquivo_de_log(configuracao: Configuracao) -> Path:
    """O caminho do log — ao lado da configuração que originou a execução."""
    base = configuracao.origem.parent if configuracao.origem else Path.home()
    return base / NOME_DO_ARQUIVO


def acrescentar_arquivo(configuracao: Configuracao, *, verboso: bool = False) -> Path:
    """Manda os logs do `whis` também para o arquivo. Idempotente.

    Chamar duas vezes na mesma execução não duplica linhas: um segundo handler
    para o mesmo arquivo escreveria tudo em dobro.
    """
    destino = arquivo_de_log(configuracao)
    destino.parent.mkdir(parents=True, exist_ok=True)

    raiz = logging.getLogger("whis")
    raiz.setLevel(logging.DEBUG if verboso else logging.INFO)
    for handler in raiz.handlers:
        if isinstance(handler, logging.FileHandler) and Path(
            handler.baseFilename
        ) == destino.resolve():
            return destino

    arquivo = logging.FileHandler(destino, encoding="utf-8")
    arquivo.setFormatter(logging.Formatter(_FORMATO))
    raiz.addHandler(arquivo)
    return destino
