"""O acrílico simulado: o que está atrás da palheta, desfocado e escurecido, como imagem de fundo.

O DWM deste build não desfoca as janelas atrás de um popup (só o papel de
parede), e um `-alpha` na janela mostra o de trás nítido — texto legível
através do painel. O que dá o efeito do Raycast é fazer o desfoque em casa: no
instante de abrir, com a janela ainda escondida, `capturar_atras` copia a tela
na região onde ela vai ficar, `desfocar` reduz, borra, amplia e escurece com a
cor do painel, e a janela desenha isso embaixo de tudo. O que está atrás
aparece como manchas de cor. O fundo acompanha cada abertura, não o que muda
enquanto ela está aberta — são segundos, e a palheta some ao despachar.

A captura é um `BitBlt` do DC da tela: num processo sem DPI awareness (o do
Tk) as coordenadas são as do Tk e a cópia sai na resolução lógica, em ~8 ms.
O `ImageGrab.grab(bbox)` do Pillow não serve — interpreta a caixa em pixels
físicos e captura a tela inteira antes de recortar (~45 ms). Sonda em
`.scratch/interface/research/sonda-acrilico-simulado.py`.
"""

from __future__ import annotations

import ctypes
import sys

from PIL import Image, ImageDraw, ImageFilter

#: O desfoque é feito na imagem reduzida por este fator e ampliada de volta:
#: mais rápido, e o borrão fica largo como o do acrílico de verdade.
FATOR_DE_REDUCAO = 4
RAIO_DO_DESFOQUE = 5

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
HORZRES = 8


def capturar_atras(x: int, y: int, largura: int, altura: int) -> Image.Image:
    """Uma cópia da tela na região, nas coordenadas do Tk. Levanta fora do Windows ou se o GDI falhar."""
    if sys.platform != "win32":
        raise OSError("a captura da tela é só no Windows")
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT
    ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]

    tela = user32.GetDC(None)
    if not tela:
        raise OSError("GetDC da tela falhou")
    memoria = gdi32.CreateCompatibleDC(tela)
    bitmap = gdi32.CreateCompatibleBitmap(tela, largura, altura)
    anterior = gdi32.SelectObject(memoria, bitmap)
    try:
        if not gdi32.BitBlt(memoria, 0, 0, largura, altura, tela, x, y, SRCCOPY | CAPTUREBLT):
            raise OSError("BitBlt da tela falhou")
        cabecalho = _BitmapInfoHeader(
            biSize=ctypes.sizeof(_BitmapInfoHeader), biWidth=largura, biHeight=-altura, biPlanes=1, biBitCount=32
        )
        buffer = ctypes.create_string_buffer(largura * altura * 4)
        if gdi32.GetDIBits(memoria, bitmap, 0, altura, buffer, ctypes.byref(cabecalho), 0) != altura:
            raise OSError("GetDIBits não devolveu a imagem inteira")
        return Image.frombuffer("RGB", (largura, altura), buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memoria, anterior)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memoria)
        user32.ReleaseDC(None, tela)


def desfocar(
    imagem: Image.Image,
    *,
    cor: str,
    opacidade: float,
    raio_dos_cantos: int = 0,
    cor_de_fora: str | None = None,
) -> Image.Image:
    """`imagem` borrada e escurecida com `cor` (`opacidade` 1.0 = só a cor); com raio, o que fica
    fora dos cantos arredondados vai em `cor_de_fora`."""
    largura, altura = imagem.size
    reduzida = imagem.convert("RGB").resize(
        (max(1, largura // FATOR_DE_REDUCAO), max(1, altura // FATOR_DE_REDUCAO)), Image.BILINEAR
    )
    borrada = reduzida.filter(ImageFilter.GaussianBlur(RAIO_DO_DESFOQUE)).resize((largura, altura), Image.BILINEAR)
    escura = Image.blend(borrada, Image.new("RGB", (largura, altura), cor), opacidade)
    if not raio_dos_cantos:
        return escura
    mascara = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, largura - 1, altura - 1), raio_dos_cantos, fill=255)
    return Image.composite(escura, Image.new("RGB", (largura, altura), cor_de_fora or cor), mascara)


def fundo_liso(largura: int, altura: int, cor: str) -> Image.Image:
    """O que vai no lugar da captura quando ela falha."""
    return Image.new("RGB", (largura, altura), cor)


def cor_media(imagem: Image.Image, caixa: tuple[int, int, int, int]) -> str:
    """A cor média de `caixa` em `#rrggbb` — é a cor que o campo, opaco, ganha para sumir no fundo."""
    r, g, b = imagem.crop(caixa).convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]
