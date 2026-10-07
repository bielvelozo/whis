"""O esquema de uma aula: um SVG que o Claude desenha e a página põe inline.

Inline quer dizer que o SVG roda no mesmo documento da página, então só passa
o que é desenho: uma lista fechada de elementos e atributos, nada de script,
evento, link ou recurso de fora.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

LIMITE_DO_ESQUEMA = 30_000

ELEMENTOS = frozenset(
    {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text",
     "tspan", "defs", "marker", "title"}
)
ATRIBUTOS = frozenset(
    {"viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
     "d", "points", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap",
     "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform", "font-size",
     "font-weight", "font-family", "font-style", "text-anchor", "dominant-baseline", "dx", "dy",
     "id", "class", "marker-start", "marker-end", "markerWidth", "markerHeight", "refX", "refY",
     "orient", "markerUnits", "role", "aria-label", "preserveAspectRatio", "letter-spacing"}
)
_NAMESPACE_DO_SVG = "http://www.w3.org/2000/svg"
_URL_LOCAL = re.compile(r"url\(#[\w-]+\)")


def validar_esquema(svg: str) -> str:
    """O SVG como veio, sem o espaço em volta; vazio se qualquer parte não for desenho."""
    texto = (svg or "").strip()
    if not texto.startswith("<svg") or len(texto.encode("utf-8")) > LIMITE_DO_ESQUEMA:
        return ""
    if "<!" in texto or "<?" in texto:
        return ""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return ""
    for elemento in raiz.iter():
        if not isinstance(elemento.tag, str) or not _e_do_svg(elemento.tag):
            return ""
        for nome, valor in elemento.attrib.items():
            if nome not in ATRIBUTOS:
                return ""
            if "url(" in valor and not _URL_LOCAL.fullmatch(valor.strip()):
                return ""
            if "javascript:" in valor.lower():
                return ""
    return texto


def _e_do_svg(tag: str) -> bool:
    """Elemento da lista, sem namespace ou no do SVG: outro namespace muda o que a tag significa."""
    espaco, _, local = tag.rpartition("}")
    return local in ELEMENTOS and espaco in ("", "{" + _NAMESPACE_DO_SVG)
