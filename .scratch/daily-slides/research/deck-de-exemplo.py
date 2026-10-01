"""Publica o deck de exemplo com a nota de verdade dele, no endereço da sonda.

    PYTHONPATH=src .venv/Scripts/python.exe .scratch/daily-slides/research/deck-de-exemplo.py <url-da-sonda>
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from whis.configuracao import carregar
from whis.deck import montar_deck
from whis.deck_claude import PublicacaoDoDeckClaude
from whis.slides_do_deck import slides_do_deck
from whis.vault import ler_nota_viva

AQUI = Path(__file__).resolve().parent

url = sys.argv[1]
configuracao = carregar()
deck = montar_deck(ler_nota_viva(configuracao.vault))
print(f"Vault: {configuracao.vault} — {len(deck.slides)} slide(s)")
if deck.vazio():
    raise SystemExit("A nota está vazia: escreva em daily/atual.md antes do deck de exemplo.")

agora = datetime.now().astimezone()
raiz = AQUI / "deck-de-exemplo"
arquivos = slides_do_deck(deck, agora.date(), agora=agora)
for caminho, conteudo in arquivos.items():
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8", newline="\n")

feita = PublicacaoDoDeckClaude(cli=configuracao.claude_cli or None).publicar(raiz, tuple(sorted(arquivos)), url)
print(f"Publicado em {feita.url} — US$ {feita.medida.custo_usd} em {feita.medida.segundos} s")
