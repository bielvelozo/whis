"""De onde sai o nome da reunião quando ninguém digita nada.

A bandeja é um ícone: não tem onde pedir um título sem abrir uma caixa de
diálogo que o pystray não oferece. Sem título, toda reunião vira
`<data>-<hora>-reuniao` no vault, e a navegação por nome de arquivo (user story
10) fica pior do que precisa.

O título vem então de onde ele já existe: a janela da reunião. O Meet põe o nome
da sala no título da aba, o Zoom e o Teams põem o da reunião. Este módulo varre
as janelas visíveis, encontra a que parece ser a reunião e devolve um título
limpo — ou `None`, e aí a gravação segue sem título, como antes.

É palpite, e palpite erra: por isso o resultado só vira o **nome** do arquivo,
nunca conteúdo da nota, e o usuário pode renomear no Obsidian sem quebrar o
wikilink (nota e transcrição compartilham o basename).
"""

from __future__ import annotations

import logging
import re

_log = logging.getLogger("second_brain.janelas")

#: Padrões de título de janela que denunciam uma reunião, em ordem de confiança.
#: O grupo `titulo` é o que sobra depois de tirar o nome do aplicativo.
PADROES = (
    re.compile(r"^(?P<titulo>.+?)\s*[-–—]\s*Google Meet\b", re.IGNORECASE),
    re.compile(r"^Meet\s*[-–—]\s*(?P<titulo>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<titulo>.+?)\s*[-–—]\s*Zoom(?: Meeting)?\b", re.IGNORECASE),
    re.compile(r"^Zoom Meeting\b(?P<titulo>)$", re.IGNORECASE),
    re.compile(r"^(?P<titulo>.+?)\s*\|\s*Microsoft Teams\b", re.IGNORECASE),
    re.compile(r"^(?P<titulo>.+?)\s*[-–—]\s*Microsoft Teams\b", re.IGNORECASE),
)

#: Códigos de sala do Meet (`abc-defg-hij`) não são nome de reunião nenhum.
_CODIGO_DE_SALA = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$", re.IGNORECASE)

#: Sobras do navegador que não pertencem ao nome da reunião.
_SUFIXOS_DE_NAVEGADOR = re.compile(
    r"\s*[-–—]\s*(Google Chrome|Microsoft\s*Edge|Mozilla Firefox|Brave|Opera)\s*$",
    re.IGNORECASE,
)

_RUIDO_INICIAL = re.compile(r"^\(\d+\)\s*")  # "(3) Fulano - Google Meet"


def titulo_de_reuniao(janelas=None) -> str | None:
    """O nome da reunião em andamento, se alguma janela denunciar um.

    `janelas` é a lista de títulos a examinar — injetável para teste. Em
    produção vem das janelas visíveis do Windows.
    """
    titulos = list(janelas) if janelas is not None else listar_janelas()
    for bruto in titulos:
        limpo = _extrair(bruto)
        if limpo:
            _log.info("Título da reunião deduzido da janela: %r", limpo)
            return limpo
    return None


def listar_janelas() -> list[str]:
    """Títulos das janelas visíveis do Windows, sem dependência nova.

    Fora do Windows (só no desenvolvimento) devolve lista vazia, e quem chama
    segue sem título.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except (ImportError, ValueError):  # pragma: no cover — não é Windows
        return []
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover — não é Windows
        return []

    titulos: list[str] = []
    assinatura = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    def visitar(janela, _parametro):  # pragma: no cover — depende do desktop
        if not user32.IsWindowVisible(janela):
            return True
        tamanho = user32.GetWindowTextLengthW(janela)
        if tamanho <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(tamanho + 1)
        user32.GetWindowTextW(janela, buffer, tamanho + 1)
        if buffer.value.strip():
            titulos.append(buffer.value)
        return True

    try:
        user32.EnumWindows(assinatura(visitar), 0)
    except OSError as erro:  # pragma: no cover — API do sistema indisponível
        _log.debug("Não foi possível listar as janelas: %s", erro)
        return []
    return titulos


def _extrair(bruto: str) -> str | None:
    texto = _RUIDO_INICIAL.sub("", _SUFIXOS_DE_NAVEGADOR.sub("", bruto.strip()))
    for padrao in PADROES:
        encontrado = padrao.match(texto)
        if encontrado is None:
            continue
        titulo = (encontrado.group("titulo") or "").strip(" -–—|·")
        if not titulo or _CODIGO_DE_SALA.match(titulo):
            return None  # é uma reunião, mas sem nome que valha a pena
        return titulo
    return None
