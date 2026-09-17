"""Reproduz o fundo bugado: mostra, esconde, mostra de novo; mede a cor do painel a cada vez.

Uso: pythonw repro-fundo.py <log> <pasta> <variante>
variante: nada | reaplicar | nudge | toggle
"""

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab, ImageStat

from whis import acrilico
from whis.janela_da_palheta import FUNDO, LARGURA, OPACIDADE_DA_TINTA, Acao, JanelaDaPalheta

LOG = Path(sys.argv[1])
PASTA = Path(sys.argv[2])
VARIANTE = sys.argv[3]
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(message)s", encoding="utf-8")
log = logging.getLogger("repro")

ACOES = (
    Acao("open", "▤", "Open note", "daily/atual.md in Obsidian"),
    Acao("daily", "☀", "Generate daily", "Update daily/atual.md from git, Linear and Slack (~40 s)"),
    Acao("record", "●", lambda: "Start recording", "Toggle the meeting recorder in the tray"),
    Acao("ask", "?", "Ask", "Ask the vault; the answer becomes a note in respostas/ (~60 s)", True),
    Acao("note", "✎", "Note", "Add a line to Pontos in daily/atual.md", True),
    Acao("doubt", "¿", "Doubt", "Add a line to Dúvidas in daily/atual.md", True),
    Acao("settings", "⚙", "Settings", "Open the settings panel (all config keys)"),
)

SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20


def desligar(hwnd: int) -> None:
    politica = acrilico.AccentPolicy(0, 0, 0, 0)
    dados = acrilico.WindowCompositionAttributeData(19, ctypes.addressof(politica), ctypes.sizeof(politica))
    acrilico._set_window_composition_attribute(hwnd, dados)


def nudge(hwnd: int) -> None:
    ctypes.windll.user32.SetWindowPos(
        wintypes.HWND(hwnd), None, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
    )


def main() -> None:
    log.info("variante=%s", VARIANTE)
    janela = JanelaDaPalheta()
    janela.ao_enviar(lambda texto: None)
    janela.definir_acoes(ACOES)
    raiz = janela.raiz
    hwnd = {"valor": 0}

    def mostrar() -> None:
        janela.mostrar()
        hwnd["valor"] = acrilico.hwnd_da_raiz(raiz)
        if VARIANTE == "reaplicar":
            acrilico.aplicar_acrilico(hwnd["valor"], acrilico.tinta_abgr(FUNDO, OPACIDADE_DA_TINTA))
        elif VARIANTE == "nudge":
            nudge(hwnd["valor"])
        elif VARIANTE == "toggle":
            acrilico.aplicar_acrilico(hwnd["valor"], acrilico.tinta_abgr(FUNDO, OPACIDADE_DA_TINTA))

    def esconder() -> None:
        if VARIANTE == "toggle" and hwnd["valor"]:
            desligar(hwnd["valor"])
        janela.esconder()

    def capturar(nome: str) -> None:
        raiz.update()
        escala = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        x, y = raiz.winfo_x(), raiz.winfo_y()
        altura = raiz.winfo_height()
        caixa = tuple(int(v * escala) for v in (x - 20, y - 20, x + LARGURA + 20, y + altura + 20))
        imagem = ImageGrab.grab(bbox=caixa, all_screens=True)
        imagem.save(PASTA / f"{VARIANTE}-{nome}.png")
        # quatro amostras do painel longe do texto: cantos internos
        w, h = imagem.size
        m = int(20 * escala)
        amostras = {
            "alto-esq": (m + 10, m + 8 + 60, m + 60, m + 8 + 68),
            "alto-dir": (w - m - 60, m + 8 + 60, w - m - 10, m + 8 + 68),
            "baixo-esq": (m + 10, h - m - 60, m + 60, h - m - 52),
            "baixo-dir": (w - m - 60, h - m - 60, w - m - 10, h - m - 52),
        }
        cores = {k: tuple(int(c) for c in ImageStat.Stat(imagem.crop(v)).mean[:3]) for k, v in amostras.items()}
        log.info("%s: %s", nome, cores)

    passos = [
        (500, mostrar),
        (1300, lambda: capturar("1-primeira")),
        (1500, esconder),
        (2300, mostrar),
        (3100, lambda: capturar("2-segunda")),
        (3300, esconder),
        (4100, mostrar),
        (4900, lambda: capturar("3-terceira")),
        (5100, esconder),
        (5300, janela.encerrar),
    ]
    for atraso, passo in passos:
        raiz.after(atraso, passo)
    janela.executar()
    log.info("fim")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log.exception("EXCECAO")
        raise
