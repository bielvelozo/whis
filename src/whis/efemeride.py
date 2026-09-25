"""A curiosidade do futebol: um acontecimento deste dia, da Wikipédia.

Só `events` — nunca nascimentos nem mortes. A primeira edição do protótipo
saiu com *"2000 — Alexandro Bernabei, futebolista argentino"*, e ele não
entendeu o que aquilo fazia ali. Sem acontecimento de futebol no dia, a
curiosidade é omitida, sem frase de desculpa: por isso `None`, e não um texto.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

_log = logging.getLogger("whis.efemeride")

ENDPOINT = "https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/{mes:02d}/{dia:02d}"
UA_WIKIPEDIA = "Whis/0.1 (+https://github.com/bielvelozo/whis)"
TEMPO_LIMITE_S = 15.0
BRT = timezone(timedelta(hours=-3), "BRT")

#: Futebol dito com todas as letras. `seleção` e `clube` sozinhos pegariam
#: seleção natural e clube de xadrez; por isso vêm acompanhados.
FUTEBOL = re.compile(
    r"futebol|futebolista|copa do mundo|\bfifa\b|\buefa\b|\bconmebol\b|libertadores|copa am[ée]rica"
    r"|sele[çc][ãa]o (?:brasileira|nacional|de futebol)|clube de futebol|maracan[ãa]|\bpel[ée]\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Efemeride:
    """Um acontecimento do dia, com a página e a miniatura da Wikipédia."""

    ano: int | None
    texto: str
    link: str | None
    imagem: str | None


def buscar_efemeride(
    agora: datetime, *, transporte: httpx.BaseTransport | None = None
) -> Efemeride | None:
    """O primeiro acontecimento de futebol do dia em Brasília; `None` se não houver."""
    hoje = agora.astimezone(BRT)
    url = ENDPOINT.format(mes=hoje.month, dia=hoje.day)
    try:
        with httpx.Client(
            transport=transporte,
            timeout=TEMPO_LIMITE_S,
            follow_redirects=True,
            headers={"User-Agent": UA_WIKIPEDIA},
        ) as cliente:
            resposta = cliente.get(url)
            resposta.raise_for_status()
            acontecimentos = resposta.json().get("events") or []
    except (httpx.HTTPError, ValueError, AttributeError) as erro:
        _log.warning("Efeméride da Wikipédia indisponível (%s): %s", url, erro)
        return None

    for acontecimento in acontecimentos:
        if not isinstance(acontecimento, dict) or not _fala_de_futebol(acontecimento):
            continue
        return _efemeride(acontecimento)
    _log.info("Nenhum acontecimento de futebol em %02d/%02d", hoje.day, hoje.month)
    return None


def _fala_de_futebol(acontecimento: dict) -> bool:
    return bool(FUTEBOL.search(str(acontecimento.get("text") or "")))


def _efemeride(acontecimento: dict) -> Efemeride:
    paginas = acontecimento.get("pages") or [{}]
    pagina = paginas[0] if isinstance(paginas[0], dict) else {}
    link = (((pagina.get("content_urls") or {}).get("desktop") or {}).get("page")) or None
    if link is None and pagina.get("title"):
        link = f"https://pt.wikipedia.org/wiki/{quote(str(pagina['title']))}"
    imagem = (pagina.get("thumbnail") or {}).get("source") or None
    ano = acontecimento.get("year")
    return Efemeride(
        ano=ano if isinstance(ano, int) else None,
        texto=str(acontecimento.get("text") or "").strip(),
        link=link,
        imagem=imagem,
    )
