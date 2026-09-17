"""Protótipo 2 do acrílico simulado: captura por GDI só da região (coordenadas do Tk), desfoca, escurece.

Uso: pythonw sonda-desfoque2.py <log> <pasta> [opacidade]
"""

import ctypes
import logging
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageGrab, ImageTk

LOG = Path(sys.argv[1])
PASTA = Path(sys.argv[2])
OPACIDADE = float(sys.argv[3]) if len(sys.argv) > 3 else 0.82
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(message)s", encoding="utf-8")
log = logging.getLogger("sonda")

LARGURA, ALTURA, RAIO = 720, 406, 12
FUNDO = "#0e0e10"
BORDA = "#4a4380"
TEXTO = "#f2f2f2"
APAGADO = "#8a8a92"
DESTAQUE = "#8b7cf6"
SRCCOPY, CAPTUREBLT = 0x00CC0020, 0x40000000


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


def capturar_gdi(x: int, y: int, w: int, h: int) -> Image.Image:
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
    gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    hdc = user32.GetDC(None)
    log.info("HORZRES do DC da tela=%s", gdi32.GetDeviceCaps(hdc, 8))
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    anterior = gdi32.SelectObject(memdc, bmp)
    try:
        gdi32.BitBlt(memdc, 0, 0, w, h, hdc, x, y, SRCCOPY | CAPTUREBLT)
        cabecalho = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        buffer = ctypes.create_string_buffer(w * h * 4)
        linhas = gdi32.GetDIBits(memdc, bmp, 0, h, buffer, ctypes.byref(cabecalho), 0)
        log.info("GetDIBits linhas=%s", linhas)
        return Image.frombuffer("RGB", (w, h), buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memdc, anterior)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, hdc)


def main() -> None:
    raiz = tk.Tk()
    raiz.withdraw()
    raiz.overrideredirect(True)
    raiz.attributes("-topmost", True)
    x = (raiz.winfo_screenwidth() - LARGURA) // 2
    y = raiz.winfo_screenheight() // 4
    raiz.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")
    escala = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100

    for _ in range(2):
        inicio = time.perf_counter()
        atras = capturar_gdi(x, y, LARGURA, ALTURA)
        log.info("gdi %s em %.1f ms", atras.size, (time.perf_counter() - inicio) * 1000)
    atras.save(PASTA / "gdi-cru.png")
    inicio = time.perf_counter()
    fisico = tuple(int(v * escala) for v in (x, y, x + LARGURA, y + ALTURA))
    pil = ImageGrab.grab(bbox=fisico)
    log.info("pillow %s em %.1f ms", pil.size, (time.perf_counter() - inicio) * 1000)
    pil.save(PASTA / "pillow-cru.png")

    inicio = time.perf_counter()
    pequena = atras.resize((LARGURA // 4, ALTURA // 4), Image.BILINEAR)
    desfocada = pequena.filter(ImageFilter.GaussianBlur(5)).resize((LARGURA, ALTURA), Image.BILINEAR)
    escura = Image.blend(desfocada, Image.new("RGB", (LARGURA, ALTURA), FUNDO), OPACIDADE)
    mascara = Image.new("L", (LARGURA, ALTURA), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, LARGURA - 1, ALTURA - 1), RAIO, fill=255)
    fundo = Image.composite(escura, Image.new("RGB", (LARGURA, ALTURA), "#010203"), mascara)
    log.info("desfoque+tinta em %.1f ms", (time.perf_counter() - inicio) * 1000)

    tela = tk.Canvas(raiz, highlightthickness=0, bd=0, background=FUNDO, width=LARGURA, height=ALTURA)
    tela.pack(fill="both", expand=True)
    foto = ImageTk.PhotoImage(fundo, master=raiz)
    tela.create_image(0, 0, anchor="nw", image=foto)
    pontos = [
        1 + RAIO, 1, LARGURA - 1 - RAIO, 1, LARGURA - 1, 1, LARGURA - 1, 1 + RAIO,
        LARGURA - 1, ALTURA - 1 - RAIO, LARGURA - 1, ALTURA - 1, LARGURA - 1 - RAIO, ALTURA - 1,
        1 + RAIO, ALTURA - 1, 1, ALTURA - 1, 1, ALTURA - 1 - RAIO, 1, 1 + RAIO, 1, 1,
    ]
    tela.create_polygon(*pontos, smooth=True, fill="", outline=BORDA, width=1)
    media = tuple(int(c) for c in escura.crop((12, 12, LARGURA - 12, 64)).resize((1, 1), Image.BOX).getpixel((0, 0)))
    cor_do_campo = "#%02x%02x%02x" % media
    log.info("cor media do campo=%s", cor_do_campo)
    campo = tk.Label(tela, text="Type a command…", font=("Segoe UI", 18), background=cor_do_campo, foreground=APAGADO, anchor="w", padx=8)
    tela.create_window(12, 12, anchor="nw", window=campo, width=LARGURA - 24, height=52)
    tela.create_line(1, 71, LARGURA - 1, 71, fill="#222226")
    for i, (icone, titulo, desc, nome) in enumerate([("▤", "Open note", "daily/atual.md in Obsidian", "open"), ("☀", "Generate daily", "Update daily/atual.md from git, Linear and Slack (~40 s)", "daily"), ("●", "Start recording", "Toggle the meeting recorder in the tray", "record")]):
        yy = 82 + i * 40
        if i == 0:
            tela.create_polygon(16, yy, LARGURA - 16, yy, LARGURA - 8, yy, LARGURA - 8, yy + 8, LARGURA - 8, yy + 32, LARGURA - 8, yy + 40, LARGURA - 16, yy + 40, 16, yy + 40, 8, yy + 40, 8, yy + 32, 8, yy + 8, 8, yy, smooth=True, fill="#232327", outline="")
        tela.create_text(30, yy + 20, text=icone, font=("Segoe UI", 12), fill=DESTAQUE)
        t = tela.create_text(52, yy + 20, text=titulo, font=("Segoe UI", 11), fill=TEXTO, anchor="w")
        tela.create_text(tela.bbox(t)[2] + 12, yy + 21, text=desc, font=("Segoe UI", 9), fill=APAGADO, anchor="w")
        tela.create_text(LARGURA - 24, yy + 20, text=nome, font=("Segoe UI", 9), fill=DESTAQUE, anchor="e")

    raiz.deiconify()
    raiz.update()
    hwnd = ctypes.windll.user32.GetParent(raiz.winfo_id()) or raiz.winfo_id()
    valor = ctypes.c_int(2)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 33, ctypes.byref(valor), ctypes.sizeof(valor))

    def capturar() -> None:
        raiz.update()
        caixa = tuple(int(v * escala) for v in (x - 30, y - 30, x + LARGURA + 30, y + ALTURA + 30))
        ImageGrab.grab(bbox=caixa, all_screens=True).save(PASTA / f"desfoque2-{OPACIDADE}.png")
        log.info("png salvo")
        raiz.after(200, raiz.destroy)

    raiz.after(900, capturar)
    raiz.mainloop()
    log.info("fim")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log.exception("EXCECAO")
        raise
