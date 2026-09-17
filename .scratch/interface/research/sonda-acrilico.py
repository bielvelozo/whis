"""Sonda da camada 7 (2026-09-17): o acrilico do DWM numa janela Tk overrideredirect, sob pythonw.

Uso: pythonw sonda-acrilico.py <log> <png> <variante>
variante: partes separadas por virgula — "accent" pede ACCENT_ENABLE_ACRYLICBLURBEHIND
com tinta escura; "alpha0.92" poe -alpha na raiz. Ex.: "accent,alpha0.92".
Uma janela de fundo (vermelho, branco, azul) fica atras do painel para a
translucidez ser inequivoca; a captura vai para o PNG.

O que ficou provado neste build (Windows 11 26200):
- SetWindowCompositionAttribute devolve 1 e o material aparece (grao + luminosidade
  do papel de parede), mas NAO amostra as janelas atras: os blocos de cor nunca
  atravessam sem -alpha. DWMWA_SYSTEMBACKDROP_TYPE=3 (documentado) faz o mesmo.
- O conteudo GDI do Tk entra com alpha 0: preto vira "so material"; cores somam.
- -transparentcolor (janela em camadas com chave de cor) esconde o material.
- DwmSetWindowAttribute(33, DWMWCP_ROUND) arredonda a janela popup; o contorno
  pintado no canvas acompanha o canto sem sobra visivel.
- accent + -alpha 0.92: material, atravessa de verdade, texto ainda legivel.
"""


import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

LOG = Path(sys.argv[1])
PNG = Path(sys.argv[2])
VARIANTE = sys.argv[3]

BORDA = "#7c6cf2"
TEXTO = "#f2f2f2"
APAGADO = "#8e8e93"
LARGURA, ALTURA, RAIO = 560, 200, 14


def registrar(linha: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int), ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


class MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


def hwnd_da_raiz(raiz) -> int:
    filho = raiz.winfo_id()
    pai = ctypes.windll.user32.GetParent(filho)
    return pai or filho


def accent(hwnd: int, estado: int, flags: int, cor: int) -> None:
    politica = ACCENT_POLICY(estado, flags, cor, 0)
    dados = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.addressof(politica), ctypes.sizeof(politica))
    f = ctypes.windll.user32.SetWindowCompositionAttribute
    f.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
    f.restype = wintypes.BOOL
    registrar(f"accent({estado}, {flags:#x}, {cor:#x}) -> {f(hwnd, ctypes.byref(dados))}")


def dwm(hwnd: int, atributo: int, valor: int) -> None:
    v = ctypes.c_int(valor)
    hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), atributo, ctypes.byref(v), ctypes.sizeof(v))
    registrar(f"DwmSetWindowAttribute({atributo}, {valor}) -> {hr:#x}")


def estender(hwnd: int) -> None:
    m = MARGINS(-1, -1, -1, -1)
    hr = ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(m))
    registrar(f"DwmExtendFrameIntoClientArea(-1) -> {hr:#x}")


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    registrar(f"variante={VARIANTE}")
    fundo = "#1c1c1e"
    selecionado = "#101010" if fundo == "#000000" else "#2c2c30"

    raiz = tk.Tk()
    raiz.withdraw()
    x = (raiz.winfo_screenwidth() - LARGURA) // 2
    y = raiz.winfo_screenheight() // 4

    atras = tk.Toplevel(raiz)
    atras.overrideredirect(True)
    atras.geometry(f"{LARGURA + 120}x{ALTURA + 120}+{x - 60}+{y - 60}")
    tela_atras = tk.Canvas(atras, background="white", highlightthickness=0)
    tela_atras.pack(fill="both", expand=True)
    terco = (LARGURA + 120) // 3
    for i, cor in enumerate(("#ff2020", "#ffffff", "#2040ff")):
        tela_atras.create_rectangle(i * terco, 0, (i + 1) * terco, ALTURA + 120, fill=cor, outline="")
    tela_atras.create_rectangle(0, ALTURA + 40, LARGURA + 120, ALTURA + 120, fill="black", outline="")
    tela_atras.create_text(20, 20, anchor="nw", text="ATRAS", font=("Segoe UI", 28, "bold"), fill="red")

    raiz.overrideredirect(True)
    raiz.attributes("-topmost", True)
    for parte in VARIANTE.split(","):
        if parte.startswith("alpha"):
            raiz.attributes("-alpha", float(parte[5:]))
    tela = tk.Canvas(raiz, highlightthickness=0, bd=0, background=fundo, width=LARGURA, height=ALTURA)
    tela.pack(fill="both", expand=True)
    pontos = [
        1 + RAIO, 1, LARGURA - 1 - RAIO, 1, LARGURA - 1, 1, LARGURA - 1, 1 + RAIO,
        LARGURA - 1, ALTURA - 1 - RAIO, LARGURA - 1, ALTURA - 1, LARGURA - 1 - RAIO, ALTURA - 1,
        1 + RAIO, ALTURA - 1, 1, ALTURA - 1, 1, ALTURA - 1 - RAIO, 1, 1 + RAIO, 1, 1,
    ]
    tela.create_polygon(*pontos, smooth=True, fill=fundo, outline=BORDA, width=2)
    campo = tk.Label(tela, text="Type a command…", font=("Segoe UI", 18), background=fundo, foreground=APAGADO, anchor="w", padx=8)
    tela.create_window(12, 12, anchor="nw", window=campo, width=LARGURA - 24, height=56)
    l1 = tk.Label(tela, text="▤  Open note     daily/atual.md in Obsidian", font=("Segoe UI", 11), background=selecionado, foreground=TEXTO, anchor="w", padx=8)
    tela.create_window(12, 80, anchor="nw", window=l1, width=LARGURA - 24, height=40)
    l2 = tk.Label(tela, text="☀  Generate daily", font=("Segoe UI", 11), background=fundo, foreground=TEXTO, anchor="w", padx=8)
    tela.create_window(12, 120, anchor="nw", window=l2, width=LARGURA - 24, height=40)

    raiz.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")
    raiz.deiconify()
    raiz.update()
    hwnd = hwnd_da_raiz(raiz)
    registrar(f"hwnd={hwnd}")
    if "accent" in VARIANTE:
        accent(hwnd, 4, 2, 0xCC1E1C1C)
    dwm(hwnd, 33, 2)
    raiz.update()

    def capturar() -> None:
        try:
            escala = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        except Exception:  # noqa: BLE001
            escala = 1.0
        caixa = tuple(int(v * escala) for v in (x - 70, y - 70, x + LARGURA + 70, y + ALTURA + 70))
        try:
            ImageGrab.grab(bbox=caixa, all_screens=True).save(PNG)
            registrar(f"png salvo escala={escala} caixa={caixa}")
        except Exception as erro:  # noqa: BLE001
            registrar(f"FALHA na captura: {erro!r}")
        raiz.after(200, raiz.destroy)

    raiz.after(1000, capturar)
    raiz.mainloop()
    registrar("fim")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:  # noqa: BLE001
        registrar(f"EXCECAO: {erro!r}")
        raise
