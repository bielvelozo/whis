"""A loja do cliente, medida antes da proposta: o anúncio que traz o endereço ganha uma abertura com um dado dela.

As fontes de 18/10 pedem que a proposta abra com algo que o freela notou na loja do cliente. O
PageSpeed Insights sem chave vive sem cota (429), então o Whis mede ele mesmo, uma vez e só o
HTML da página inicial: quanto demorou para chegar, o peso, quantos scripts carrega, o tema da
Shopify e se a loja está fechada com senha. Nada é inventado: a proposta só cita o que está aqui.

O endereço vem do texto do anúncio. Rede social, e-mail, a própria plataforma e endereço de rede
local ficam de fora; página que não responde 200 não vira medida.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .fontes_da_cacada import CABECALHOS

_log = logging.getLogger("whis.loja_do_cliente")

TEMPO_LIMITE_S = 20.0
TETO_DO_HTML = 5_000_000

#: Sem os que também são palavra em português ("de", "es"): "loja.de forma" não pode virar endereço.
_TLDS = (
    r"com\.br|net\.br|org\.br|co\.uk|com\.au|com\.mx|com\.ar|com|net|org|store|shop|online|site|loja|br|pt|co|io|app"
    r"|ca|us|eu"
)
_ENDERECO = re.compile(
    rf"(?<![\w@.-])(?:https?://)?(?P<host>(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+(?:{_TLDS}))(?![\w-]|\.\w)"
)
#: Endereços que aparecem em anúncio e não são a loja dele.
FORA = (
    "99freelas.com.br", "freelancer.com", "workana.com", "vintepila.com.br", "instagram.com", "facebook.com", "fb.com",
    "whatsapp.com", "youtube.com", "google.com", "figma.com", "canva.com", "github.com", "linkedin.com", "tiktok.com",
    "pinterest.com", "twitter.com", "x.com", "mercadolivre.com.br", "mercadolibre.com", "shopee.com.br", "amazon.com",
    "amazon.com.br", "dropbox.com", "wetransfer.com", "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
    "shopify.com", "wix.com", "behance.net", "dribbble.com", "trello.com", "vimeo.com", "loom.com", "example.com",
    "exemplo.com", "exemplo.com.br",
)
_TEMA = re.compile(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", re.S)
_SCRIPT_DE_FORA = re.compile(r"<script\b[^>]*\bsrc\s*=", re.I)


@dataclass(frozen=True)
class Loja:
    """O que o Whis mediu na página inicial: só isso pode ir na proposta."""

    endereco: str
    segundos: float
    kb: int
    scripts: int
    tema: str = ""
    com_senha: bool = False

    def como_texto(self) -> str:
        linhas = [f"- endereço: {self.endereco}"]
        if self.com_senha:
            linhas.append("- a loja está fechada com senha (a página inicial manda para /password)")
        segundos = f"{self.segundos:.1f}".replace(".", ",")
        linhas.append(f"- a página inicial respondeu em {segundos} s (só o HTML, sem imagens)")
        linhas.append(f"- o HTML da página inicial tem {self.kb} KB e carrega {self.scripts} scripts")
        if self.tema:
            linhas.append(f"- tema Shopify: {self.tema}")
        return "\n".join(linhas)


def achar(texto: str) -> str | None:
    """A página inicial do primeiro endereço do texto que pode ser a loja ou o site do cliente."""
    for casou in _ENDERECO.finditer(texto or ""):
        host = casou["host"].casefold()
        sem_www = host.removeprefix("www.")
        if any(sem_www == dominio or sem_www.endswith("." + dominio) for dominio in FORA):
            continue
        return f"https://{host}/"
    return None


def medir(
    url: str, *, rede: httpx.BaseTransport | None = None, relogio: Callable[[], float] = time.perf_counter
) -> Loja | None:
    """Abre a página inicial uma vez e mede; sem resposta 200, nada."""
    inicio = relogio()
    try:
        with httpx.Client(transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
            with cliente.stream("GET", url) as resposta:
                if resposta.status_code != 200:
                    _log.info("Loja do cliente: %s respondeu %s; sem medida.", url, resposta.status_code)
                    return None
                corpo = bytearray()
                for pedaco in resposta.iter_bytes():
                    corpo += pedaco
                    if len(corpo) > TETO_DO_HTML:
                        break
                final = resposta.url
    except httpx.HTTPError as erro:
        _log.info("Loja do cliente: %s não abriu (%s); sem medida.", url, erro)
        return None
    segundos = relogio() - inicio
    html = corpo.decode("utf-8", errors="replace")
    return Loja(
        endereco=httpx.URL(url).host.removeprefix("www."),
        segundos=round(segundos, 1),
        kb=round(len(corpo) / 1000),
        scripts=len(_SCRIPT_DE_FORA.findall(html)),
        tema=_tema(html),
        com_senha=final.path.rstrip("/").endswith("/password"),
    )


def medir_do_texto(texto: str, *, rede: httpx.BaseTransport | None = None) -> Loja | None:
    url = achar(texto)
    return medir(url, rede=rede) if url else None


def _tema(html: str) -> str:
    casou = _TEMA.search(html)
    if casou is None:
        return ""
    try:
        dados = json.loads(casou.group(1))
    except ValueError:
        return ""
    if not isinstance(dados, dict):
        return ""
    nome = str(dados.get("schema_name") or dados.get("name") or "").strip()
    versao = str(dados.get("schema_version") or "").strip()
    return f"{nome} {versao}".strip() if nome else ""
