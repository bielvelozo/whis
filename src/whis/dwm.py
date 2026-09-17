"""O que a palheta pede ao DWM do Windows 11: os cantos arredondados da janela.

`DwmSetWindowAttribute(DWMWCP_ROUND)` arredonda um popup `overrideredirect`
sem precisar do `-transparentcolor` (uma janela em camadas com chave de cor).
A função devolve `bool` e nunca levanta: fora do Windows 11 a janela abre com
os cantos do fallback.

O acrílico do DWM (`SetWindowCompositionAttribute`) viveu aqui nas camadas 7 e
8 e saiu: neste build (26200) ele rende o material mas não amostra as janelas
atrás de um popup, e ainda esquece a tinta quando a janela some e volta. O
desfoque do que está atrás é feito em casa, em `fundo_desfocado.py`; as
sondas estão em `.scratch/interface/research/sonda-acrilico*.py`.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable

_log = logging.getLogger("whis.dwm")

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


def hwnd_da_raiz(raiz) -> int:
    """O HWND que o DWM enxerga: no Windows o Tk embrulha a raiz num wrapper, pai do `winfo_id()`."""
    filho = int(raiz.winfo_id())
    if sys.platform != "win32":
        return filho
    return int(ctypes.windll.user32.GetParent(filho)) or filho


def arredondar_cantos(
    hwnd: int, *, chamar: Callable[[int, int, ctypes.c_int], int] | None = None
) -> bool:
    """Pede ao DWM os cantos arredondados do Windows 11. `False` fora dele."""
    valor = ctypes.c_int(DWMWCP_ROUND)
    try:
        hresult = (chamar or _dwm_set_window_attribute)(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, valor)
    except Exception as erro:  # noqa: BLE001
        _log.info("Os cantos do DWM não estão disponíveis: %s", erro)
        return False
    if hresult != 0:
        _log.info("O DWM recusou os cantos arredondados (HRESULT %#x).", hresult & 0xFFFFFFFF)
        return False
    return True


def _dwm_set_window_attribute(hwnd: int, atributo: int, valor: ctypes.c_int) -> int:
    from ctypes import wintypes

    return int(
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), atributo, ctypes.byref(valor), ctypes.sizeof(valor)
        )
    )
