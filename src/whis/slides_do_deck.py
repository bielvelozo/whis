"""O deck da daily nos arquivos do tipo Slides: `project/deck.json` e um HTML por slide.

O formato é o de `artifact-type/reference/format.md` do tipo Slides (release
1790810190-bbd5, lido na sonda `.scratch/daily-slides/research/01-slides-headless.md`):
um `<section>` por arquivo, canvas de 1920×1080, só estilo inline do
subconjunto que o tipo aceita. O que está fora dele some na leitura sem aviso,
e é por isso que o recuo vai no atalho `padding` (não há `padding-left`), o
sub-item é um `ul` irmão mais recuado (não há lista aninhada) e o código é só
um `span` com cor (span não aceita fonte). Cada item é o seu próprio `ul`: o
vão entre itens fica com o `gap` do `div`, igual à estimativa de `deck.py`.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timezone

from .deck import (
    ALTURA_DA_LINHA,
    ESPACO_ENTRE_ITENS,
    FONTE_DO_ITEM,
    FONTE_DO_SUBITEM,
    RECUO_POR_NIVEL,
    Deck,
    ItemDoSlide,
    Slide,
)
from .vault import _data_por_extenso

TITULO_DO_DECK = "Daily"
CAMINHO_DO_INDICE = "project/deck.json"
PASTA_DOS_SLIDES = "project/slides"

FUNDO = "#16171c"
TEXTO = "#ecebe6"
TEXTO_DO_SUBITEM = "#b9b7c6"
RODAPE = "#8b8a99"
ACENTO = "#8b7cf6"
FAMILIA = "Inter"
PILHA_DE_FONTES = "Inter, 'Segoe UI', sans-serif"
HREF_DA_FONTE = "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
FONTE_DO_TITULO = 72
FONTE_DO_RODAPE = 24

_MARCAS = re.compile(
    r"\[\[(?P<nota>[^\]|]+)(?:\|(?P<apelido>[^\]]+))?\]\]"
    r"|\[(?P<rotulo>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)"
    r"|\*\*(?P<negrito>.+?)\*\*"
    r"|`(?P<codigo>[^`]+)`"
    r"|\*(?P<italico>[^*\s][^*]*)\*"
    r"|(?<!\w)_(?P<sublinhado>[^_\s][^_]*)_(?!\w)"
)


def slides_do_deck(deck: Deck, hoje: date, *, agora: datetime | None = None) -> dict[str, str]:
    """Caminho publicado → conteúdo. Deck vazio não tem arquivo."""
    if deck.vazio():
        return {}
    total = len(deck.slides)
    arquivos = {
        f"{PASTA_DOS_SLIDES}/{slide.id}.html": html_do_slide(slide, hoje, numero, total)
        for numero, slide in enumerate(deck.slides, start=1)
    }
    arquivos[CAMINHO_DO_INDICE] = indice_do_deck(deck, agora or datetime.now(timezone.utc))
    return arquivos


def indice_do_deck(deck: Deck, agora: datetime) -> str:
    inicios: dict[str, str] = {}
    for slide in deck.slides:
        inicios.setdefault(slide.secao, slide.id)
    indice = {
        "v": 4,
        "createdOnFiles": {"v": 1, "at": agora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "lists": "css",
        "title": TITULO_DO_DECK,
        "order": [slide.id for slide in deck.slides],
        "sections": {inicio: {"description": secao, "start": inicio} for secao, inicio in inicios.items()},
        "cover": deck.slides[0].id,
        "faces": {FAMILIA.lower(): {"family": FAMILIA, "href": HREF_DA_FONTE}},
        "designSystems": [],
    }
    return json.dumps(indice, ensure_ascii=False, indent=2) + "\n"


def html_do_slide(slide: Slide, hoje: date, numero: int, total: int) -> str:
    rodape = f"{TITULO_DO_DECK} · {_data_por_extenso(hoje)} · {numero}/{total}"
    return "\n".join(
        [
            f'<section id="{slide.id}" style="background:{FUNDO};color:{TEXTO};font-family:{PILHA_DE_FONTES};'
            'padding:128px 128px 160px;display:flex;flex-direction:column;gap:48px">',
            '<div style="display:flex;flex-direction:column;gap:24px">',
            f'<div style="width:96px;height:8px;background:{ACENTO}"></div>',
            f'<h2 style="font-size:{FONTE_DO_TITULO}px;font-weight:700;line-height:1.1;color:{TEXTO}">'
            f"{html.escape(slide.titulo)}</h2>",
            "</div>",
            f'<div style="display:flex;flex-direction:column;gap:{ESPACO_ENTRE_ITENS}px">',
            *(_lista(item) for item in slide.itens),
            "</div>",
            f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:{FONTE_DO_RODAPE}px;'
            f'color:{RODAPE}">{html.escape(rodape)}</p>',
            "</section>",
        ]
    ) + "\n"


def _lista(item: ItemDoSlide) -> str:
    fonte = FONTE_DO_ITEM if item.profundidade == 0 else FONTE_DO_SUBITEM
    cor = TEXTO if item.profundidade == 0 else TEXTO_DO_SUBITEM
    recuo = RECUO_POR_NIVEL * (item.profundidade + 1)
    return (
        f'<ul style="padding:0 0 0 {recuo}px;font-size:{fonte}px;line-height:{ALTURA_DA_LINHA};color:{cor}">'
        f"<li>{_inline(item.texto)}</li></ul>"
    )


def _inline(texto: str) -> str:
    partes: list[str] = []
    fim = 0
    for marca in _MARCAS.finditer(texto):
        partes.append(html.escape(texto[fim : marca.start()]))
        partes.append(_marca(marca))
        fim = marca.end()
    partes.append(html.escape(texto[fim:]))
    return "".join(partes)


def _marca(marca: re.Match[str]) -> str:
    escapar = html.escape
    if marca["nota"] is not None:
        return escapar((marca["apelido"] or marca["nota"]).strip())
    if marca["url"] is not None:
        return f'<a href="{escapar(marca["url"])}">{escapar(marca["rotulo"])}</a>'
    if marca["negrito"] is not None:
        return f"<b>{escapar(marca['negrito'])}</b>"
    if marca["codigo"] is not None:
        return f'<span style="color:{ACENTO}">{escapar(marca["codigo"])}</span>'
    return f"<i>{escapar(marca['italico'] or marca['sublinhado'])}</i>"
