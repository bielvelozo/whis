"""A nota da daily como ele a escreve no Obsidian, ainda sem `## O que terminei`."""

from __future__ import annotations

from pathlib import Path

NOTA_DA_DAILY = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "- FN-123 frete do checkout corrigido\n"
    "\t- subiu em produção\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "- FN-130 diário automático\n"
    "\n"
    "## Fazer\n"
    "\n"
    "- [ ] não vai para o deck\n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- quem revisa o PR do frete?\n"
    "\n"
    "## Pontos\n"
    "\n"
    "- também não vai\n"
    "\n"
    "## Falar\n"
    "\n"
    "- sexta eu saio mais cedo\n"
)


def escrever_nota_da_daily(vault: Path, texto: str = NOTA_DA_DAILY) -> Path:
    arquivo = Path(vault) / "daily" / "atual.md"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(texto.encode("utf-8"))
    return arquivo
