"""Roda como o usuario (tarefa descartavel): troca o atalho no config.toml real, com backup."""

import shutil
import sys
from datetime import datetime
from pathlib import Path

from whis.configuracao import caminho_da_configuracao, carregar

LOG = Path(r"C:\Users\gabri\development\whis\.rota-config-log.txt")
VELHO = 'atalho = "ctrl+alt+w"'
NOVO = 'atalho = "ctrl+space"'


def registrar(linha: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def main() -> int:
    caminho = caminho_da_configuracao()
    registrar(f"config={caminho}")
    texto = caminho.read_text(encoding="utf-8")
    if VELHO not in texto:
        registrar(f"linha nao encontrada; atalho carregado={carregar(caminho).palheta_atalho}")
        return 2
    backup = caminho.with_name(f"{caminho.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(caminho, backup)
    registrar(f"backup={backup.name}")
    caminho.write_text(texto.replace(VELHO, NOVO, 1), encoding="utf-8", newline="\n")
    registrar(f"gravado; atalho carregado={carregar(caminho).palheta_atalho}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:  # noqa: BLE001
        registrar(f"EXCECAO: {erro!r}")
        sys.exit(1)
