"""A foto de uma aula: a imagem de capa da página que ela usou como fonte."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class _ProcuraImagem(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.og: str | None = None
        self.twitter: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        atributos = {nome.lower(): (valor or "").strip() for nome, valor in attrs}
        conteudo = atributos.get("content", "")
        if not conteudo:
            return
        nomes = {atributos.get("property", "").lower(), atributos.get("name", "").lower()}
        if "og:image" in nomes and self.og is None:
            self.og = conteudo
        elif "twitter:image" in nomes and self.twitter is None:
            self.twitter = conteudo


def imagem_da_pagina(html: str, url: str) -> str | None:
    """`og:image`, ou `twitter:image` sem ela, como URL absoluta `http`; `None` sem nenhuma."""
    procura = _ProcuraImagem()
    procura.feed(html)
    procura.close()
    for candidata in (procura.og, procura.twitter):
        if candidata:
            absoluta = urljoin(url, candidata)
            if absoluta.startswith("http"):
                return absoluta
    return None
