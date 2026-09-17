"""O vidro da palheta: o material acrílico do DWM numa janela do Tk.

`SetWindowCompositionAttribute` com `ACCENT_ENABLE_ACRYLICBLURBEHIND` não é
documentada e muda entre builds do Windows; por isso cada função aqui devolve
`bool` e nunca levanta — quem chama decide o fallback, e a janela abre de
qualquer jeito.

O que a sonda de 2026-09-17 provou neste build (Windows 11 26200), em
`.scratch/interface/research/sonda-acrilico.py`: o material aparece (o grão e a
luminosidade do papel de parede), mas o DWM **não amostra as janelas atrás** de
um popup — nem por esta chamada nem pela documentada
`DWMWA_SYSTEMBACKDROP_TYPE`. O conteúdo GDI do Tk entra com alpha 0: preto vira
só material, as outras cores somam por cima, e o texto claro continua claro. O
que deixaria ver o que está atrás é um `-alpha` na janela inteira, por cima do
material — mas mesmo a 95% ele deixa o texto de trás legível através do
painel, e o usuário pediu preto como o Raycast: a palheta usa só o material,
com a tinta quase opaca.

Os cantos são do DWM (`DWMWCP_ROUND`, Windows 11): o `-transparentcolor` que os
fazia antes é uma janela em camadas com chave de cor, e ela esconde o material.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable

_log = logging.getLogger("whis.acrilico")

WCA_ACCENT_POLICY = 19
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def tinta_abgr(cor: str, opacidade: int) -> int:
    """`"#1c1c1e"`, `0xCC` → `0xCC1E1C1C`: o inteiro AABBGGRR que a política espera."""
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return (opacidade << 24) | (b << 16) | (g << 8) | r


def hwnd_da_raiz(raiz) -> int:
    """O HWND que o DWM enxerga: no Windows o Tk embrulha a raiz num wrapper, pai do `winfo_id()`."""
    filho = int(raiz.winfo_id())
    if sys.platform != "win32":
        return filho
    return int(ctypes.windll.user32.GetParent(filho)) or filho


def aplicar_acrilico(
    hwnd: int,
    tinta: int,
    *,
    chamar: Callable[[int, WindowCompositionAttributeData], int] | None = None,
) -> bool:
    """Pede o acrílico ao DWM para `hwnd`, com a tinta por cima. `False` quando o Windows recusa."""
    politica = AccentPolicy(ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, tinta, 0)
    dados = WindowCompositionAttributeData(
        WCA_ACCENT_POLICY, ctypes.addressof(politica), ctypes.sizeof(politica)
    )
    try:
        resultado = (chamar or _set_window_composition_attribute)(hwnd, dados)
    except Exception as erro:  # noqa: BLE001 — API sem contrato: qualquer falha é "não tem"
        _log.warning("O acrílico do DWM não está disponível: %s", erro)
        return False
    if not resultado:
        _log.warning("O Windows recusou o acrílico (SetWindowCompositionAttribute devolveu %r).", resultado)
        return False
    return True


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


def _set_window_composition_attribute(hwnd: int, dados: WindowCompositionAttributeData) -> int:
    from ctypes import wintypes

    funcao = ctypes.windll.user32.SetWindowCompositionAttribute
    funcao.argtypes = [wintypes.HWND, ctypes.POINTER(WindowCompositionAttributeData)]
    funcao.restype = wintypes.BOOL
    return int(funcao(hwnd, ctypes.byref(dados)))


def _dwm_set_window_attribute(hwnd: int, atributo: int, valor: ctypes.c_int) -> int:
    from ctypes import wintypes

    return int(
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), atributo, ctypes.byref(valor), ctypes.sizeof(valor)
        )
    )
