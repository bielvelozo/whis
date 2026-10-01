"""Semeia o endereço do deck aprovado na nota datada mais recente de um dia anterior.

    PYTHONPATH=src .venv/Scripts/python.exe .scratch/daily-slides/research/semear-deck.py <url>

Nunca na nota de hoje: a daily velha, ainda ativa até a troca, reescreve a de
hoje sem o campo.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from whis.configuracao import carregar

url = sys.argv[1]
pasta = Path(carregar().vault) / "daily"
anteriores = sorted(
    (
        arquivo
        for arquivo in pasta.glob("*.md")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", arquivo.stem) and date.fromisoformat(arquivo.stem) < date.today()
    ),
    reverse=True,
)
alvo = anteriores[0]
texto = alvo.read_bytes().decode("utf-8")
quebra = "\r\n" if "\r\n" in texto else "\n"
abertura = f"---{quebra}"
assert texto.startswith(abertura), f"{alvo} não começa com frontmatter"
assert "deck:" not in texto.split(f"{quebra}---", 1)[0], f"{alvo} já tem deck:"
alvo.write_bytes(texto.replace(abertura, f'{abertura}deck: "{url}"{quebra}', 1).encode("utf-8"))
print(f"deck: {url} semeado em {alvo}")
