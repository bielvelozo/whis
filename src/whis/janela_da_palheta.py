"""A janela da palheta: um campo de texto sem borda, no terço superior da tela.

Tk, que já vem com o Python: `overrideredirect` tira a borda, `-topmost` põe
por cima de tudo, e a janela só é escondida e mostrada — nunca destruída —
entre um atalho e outro. Enter despacha e some; Esc some; perder o foco some.

O Tk só aceita chamadas do thread que o criou. O atalho global e o menu da
bandeja vivem em outros threads, então tudo que eles pedem entra por `pedir`,
numa fila que o thread do Tk esvazia a cada 50 ms — o arranjo provado pela
sonda da camada 3. Nada longo roda no handler: quem despacha devolve na hora.

`PortaJanela` é o que a palheta e a bandeja enxergam; o teste monta um dublê.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable
from typing import Protocol

_log = logging.getLogger("whis.janela_da_palheta")

LARGURA = 640
ALTURA = 64
FONTE = ("Segoe UI", 16)
FUNDO = "#1f1f1f"
FUNDO_DO_CAMPO = "#2c2c2c"
TEXTO = "#f2f2f2"

#: A cadência com que o thread do Tk olha a fila de pedidos de outros threads.
INTERVALO_DA_FILA_MS = 50

#: Quanto esperar depois de perder o foco antes de esconder: o foco pode estar
#: só trocando de widget dentro da própria janela.
ATRASO_DO_FOCO_MS = 150


class PortaJanela(Protocol):
    """O que a palheta precisa de uma janela — Tk ou dublê."""

    def mostrar(self) -> None: ...

    def esconder(self) -> None: ...

    def ao_enviar(self, callback: Callable[[str], object]) -> None: ...


class JanelaDaPalheta:
    """A janela de verdade. Cria o `Tk` — só uma por processo, no thread principal."""

    def __init__(self) -> None:
        import tkinter as tk

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.title("Whis")
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        raiz.configure(background=FUNDO)
        x = (raiz.winfo_screenwidth() - LARGURA) // 2
        y = (raiz.winfo_screenheight() - ALTURA) // 3
        raiz.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")

        campo = tk.Entry(
            raiz,
            font=FONTE,
            relief="flat",
            background=FUNDO_DO_CAMPO,
            foreground=TEXTO,
            insertbackground=TEXTO,
        )
        campo.pack(fill="both", expand=True, padx=10, pady=10)
        campo.bind("<Return>", self._enviar)
        campo.bind("<Escape>", lambda _evento: self.esconder())
        campo.bind("<FocusOut>", self._ao_perder_o_foco)

        self._tk = tk
        self._raiz = raiz
        self._campo = campo
        self._fila: queue.Queue[Callable[[], object]] = queue.Queue()
        self._callback: Callable[[str], object] | None = None
        self._visivel = False
        self._encerrada = False

    @property
    def raiz(self):
        """O `Tk` — é dele que o painel de configuração nasce como `Toplevel`."""
        return self._raiz

    def ao_enviar(self, callback: Callable[[str], object]) -> None:
        self._callback = callback

    def mostrar(self) -> None:
        self._campo.delete(0, "end")
        self._raiz.deiconify()
        self._raiz.lift()
        self._campo.focus_force()
        self._visivel = True

    def esconder(self) -> None:
        self._raiz.withdraw()
        self._visivel = False

    def visivel(self) -> bool:
        return self._visivel

    def pedir(self, acao: Callable[[], object]) -> None:
        """Roda `acao` no thread do Tk — a única porta para os outros threads."""
        self._fila.put(acao)

    def executar(self) -> None:
        """O `mainloop`, com a fila sondada a cada 50 ms. Devolve quando `encerrar` roda."""
        self._raiz.after(INTERVALO_DA_FILA_MS, self._sondar)
        self._raiz.mainloop()

    def encerrar(self) -> None:
        if self._encerrada:
            return
        self._encerrada = True
        self._raiz.after(0, self._raiz.destroy)

    def _sondar(self) -> None:
        try:
            while True:
                acao = self._fila.get_nowait()
                try:
                    acao()
                except Exception:  # noqa: BLE001 — um pedido com erro não para a fila
                    _log.exception("Um pedido à janela da palheta falhou.")
        except queue.Empty:
            pass
        if not self._encerrada:
            try:
                self._raiz.after(INTERVALO_DA_FILA_MS, self._sondar)
            except self._tk.TclError:
                pass

    def _enviar(self, _evento=None) -> None:
        texto = self._campo.get()
        self.esconder()
        if self._callback is None:
            return
        try:
            self._callback(texto)
        except Exception:  # noqa: BLE001 — o handler nunca deixa exceção subir ao Tk
            _log.exception("O despacho da palheta falhou.")

    def _ao_perder_o_foco(self, _evento=None) -> None:
        self._raiz.after(ATRASO_DO_FOCO_MS, self._esconder_se_sem_foco)

    def _esconder_se_sem_foco(self) -> None:
        try:
            com_foco = self._raiz.focus_get()
        except (self._tk.TclError, KeyError):
            com_foco = None
        if self._visivel and com_foco is None:
            self.esconder()
