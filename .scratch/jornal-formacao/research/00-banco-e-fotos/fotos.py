"""Sonda descartável do ticket 01, pergunta 6: as fontes das aulas têm foto em og:image?

Lê as URLs das linhas "Fontes:" das notas de noticias/ do vault dele, abre 12 delas
(Wikipédia e outras) e testa se a imagem que a página anuncia baixa pela
`_baixar_imagem` do jornal.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "src"))

import httpx  # noqa: E402

from whis.jornal import UA_DAS_CAPAS, _baixar_imagem  # noqa: E402

VAULT = Path("C:/Users/gabri/whis-vault")
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


class Metas(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.og = ""
        self.twitter = ""

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = dict(attrs)
        if (a.get("property") or "").lower() == "og:image" and not self.og:
            self.og = a.get("content") or ""
        if (a.get("name") or "").lower() == "twitter:image" and not self.twitter:
            self.twitter = a.get("content") or ""


def fontes_das_aulas() -> list[str]:
    urls: list[str] = []
    for nota in sorted((VAULT / "noticias").glob("2026-*.md"), reverse=True):
        for linha in nota.read_text("utf-8", errors="replace").splitlines():
            if linha.startswith("Fontes:"):
                for url in LINK.findall(linha):
                    if url not in urls:
                        urls.append(url)
    return urls


def escolher(urls: list[str]) -> list[str]:
    wiki = [u for u in urls if "wikipedia.org" in u][:6]
    outras = [u for u in urls if "wikipedia.org" not in u][:6]
    return wiki + outras


def main() -> None:
    linhas = []
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": UA_DAS_CAPAS}) as cliente:
        for url in escolher(fontes_das_aulas()):
            linha = {"url": url, "og": "", "twitter": "", "baixou": False, "erro": ""}
            try:
                resposta = cliente.get(url)
                metas = Metas()
                metas.feed(resposta.text)
                linha.update(status=resposta.status_code, og=metas.og, twitter=metas.twitter)
                imagem = metas.og or metas.twitter
                if imagem:
                    bytes_ = _baixar_imagem(cliente, urljoin(url, imagem))
                    linha["baixou"] = bytes_ is not None
                    linha["kb"] = round(len(bytes_) / 1024) if bytes_ else 0
            except Exception as erro:  # noqa: BLE001
                linha["erro"] = f"{type(erro).__name__}: {erro}"
            linhas.append(linha)
            print(json.dumps(linha, ensure_ascii=False))
    (Path(__file__).parent / "saida" / "fotos.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    main()
