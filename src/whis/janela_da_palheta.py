"""A janela da palheta, no estilo Raycast: campo grande, lista de ações, sem borda.

Tk, que já vem com o Python. A janela é um `overrideredirect` com
`-transparentcolor`: o que se vê é um painel escuro de cantos arredondados
desenhado num canvas, com borda fina em cor de destaque; fora dele a janela é
transparente. Dentro, um `Text` de uma linha (Segoe UI 18) com placeholder, em
que a primeira palavra ganha cor quando é um comando, e abaixo a lista de
ações — uma linha por comando, filtrada pelo que se digita, com a selecionada
destacada. ↑/↓ escolhem; Enter executa o texto digitado ou, com o campo vazio,
a ação selecionada; clicar numa linha executa; Esc e perder o foco escondem.

O Tk só aceita chamadas do thread que o criou. O atalho global e o menu da
bandeja vivem em outros threads, então tudo que eles pedem entra por `pedir`,
numa fila que o thread do Tk esvazia a cada 50 ms — o arranjo provado pela
sonda da camada 3. Nada longo roda no handler: quem despacha devolve na hora.

`PortaJanela` é o que a palheta e a bandeja enxergam; o teste monta um dublê.
O filtro e o destaque são funções puras, testadas sem Tk.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

_log = logging.getLogger("whis.janela_da_palheta")

LARGURA = 680
RAIO = 14
MARGEM = 12
ALTURA_DO_CAMPO = 56
ALTURA_DA_LINHA = 40
FONTE = ("Segoe UI", 18)
FONTE_DA_LINHA = ("Segoe UI", 11)
FONTE_DA_DESCRICAO = ("Segoe UI", 9)
FONTE_DO_ICONE = ("Segoe UI", 13)

FUNDO = "#1c1c1e"
FUNDO_SELECIONADO = "#2c2c30"
BORDA = "#7c6cf2"
DESTAQUE = "#7c6cf2"
TEXTO = "#f2f2f2"
TEXTO_APAGADO = "#8e8e93"
#: Uma cor que nenhum pixel do painel usa: é o que o Windows torna transparente.
COR_TRANSPARENTE = "#010203"

PLACEHOLDER = "Type a command…"

#: A cadência com que o thread do Tk olha a fila de pedidos de outros threads.
INTERVALO_DA_FILA_MS = 50

#: Quanto esperar depois de perder o foco antes de esconder: o foco pode estar
#: só trocando de widget dentro da própria janela.
ATRASO_DO_FOCO_MS = 150


@dataclass(frozen=True)
class Acao:
    """Uma linha da lista: o nome do comando, o glifo, o título e a descrição."""

    nome: str
    icone: str
    rotulo: str | Callable[[], str]
    descricao: str = ""

    def rotulo_atual(self) -> str:
        return self.rotulo() if callable(self.rotulo) else self.rotulo


def filtrar(acoes: Sequence[Acao], texto: str) -> tuple[Acao, ...]:
    """As ações cujo nome começa com a primeira palavra digitada; todas com o campo vazio."""
    palavras = texto.strip().split(None, 1)
    if not palavras:
        return tuple(acoes)
    prefixo = palavras[0].casefold()
    return tuple(acao for acao in acoes if acao.nome.casefold().startswith(prefixo))


def comando_destacado(texto: str, nomes: Sequence[str]) -> tuple[int, int] | None:
    """`(inicio, fim)` da primeira palavra quando ela é exatamente um comando; senão `None`."""
    sem_indentacao = texto.lstrip()
    inicio = len(texto) - len(sem_indentacao)
    palavra = sem_indentacao.split(None, 1)[0] if sem_indentacao.strip() else ""
    if not palavra or palavra.casefold() not in {nome.casefold() for nome in nomes}:
        return None
    return inicio, inicio + len(palavra)


class PortaJanela(Protocol):
    """O que a palheta precisa de uma janela — Tk ou dublê."""

    def mostrar(self) -> None: ...

    def esconder(self) -> None: ...

    def ao_enviar(self, callback: Callable[[str], object]) -> None: ...

    def definir_acoes(self, acoes: Sequence[Acao]) -> None: ...


class JanelaDaPalheta:
    """A janela de verdade. Cria o `Tk` — só uma por processo, no thread principal."""

    def __init__(self) -> None:
        import tkinter as tk

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.title("Whis")
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        raiz.configure(background=COR_TRANSPARENTE)
        try:
            raiz.attributes("-transparentcolor", COR_TRANSPARENTE)
        except tk.TclError:  # fora do Windows os cantos ficam quadrados
            pass

        tela = tk.Canvas(raiz, highlightthickness=0, bd=0, background=COR_TRANSPARENTE)
        tela.pack(fill="both", expand=True)

        campo = tk.Text(
            tela,
            height=1,
            font=FONTE,
            wrap="none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            background=FUNDO,
            foreground=TEXTO,
            insertbackground=TEXTO,
            padx=8,
            pady=6,
            undo=False,
        )
        campo.tag_configure("comando", foreground=DESTAQUE, font=(*FONTE, "bold"))
        campo.bind("<Return>", self._enter)
        campo.bind("<KP_Enter>", self._enter)
        campo.bind("<Escape>", lambda _evento: (self.esconder(), "break")[1])
        campo.bind("<Up>", lambda _evento: self._mover_selecao(-1))
        campo.bind("<Down>", lambda _evento: self._mover_selecao(1))
        campo.bind("<Tab>", lambda _evento: self._mover_selecao(1))
        campo.bind("<KeyRelease>", lambda _evento: self._atualizar())
        campo.bind("<FocusOut>", self._ao_perder_o_foco)

        placeholder = tk.Label(
            campo, text=PLACEHOLDER, font=FONTE, background=FUNDO, foreground=TEXTO_APAGADO
        )
        placeholder.bind("<Button-1>", lambda _evento: campo.focus_set())

        lista = tk.Frame(tela, background=FUNDO)

        self._tk = tk
        self._raiz = raiz
        self._tela = tela
        self._campo = campo
        self._placeholder = placeholder
        self._lista = lista
        self._fila: queue.Queue[Callable[[], object]] = queue.Queue()
        self._callback: Callable[[str], object] | None = None
        self._acoes: tuple[Acao, ...] = ()
        self._visiveis: tuple[Acao, ...] = ()
        self._linhas: list[tk.Frame] = []
        self._selecionada = 0
        self._visivel = False
        self._encerrada = False
        self._desenhar(())

    @property
    def raiz(self):
        """O `Tk` — é dele que o painel de configuração nasce como `Toplevel`."""
        return self._raiz

    # -- a porta ------------------------------------------------------------

    def ao_enviar(self, callback: Callable[[str], object]) -> None:
        self._callback = callback

    def definir_acoes(self, acoes: Sequence[Acao]) -> None:
        self._acoes = tuple(acoes)
        self._atualizar()

    def mostrar(self) -> None:
        self._campo.delete("1.0", "end")
        self._selecionada = 0
        self._atualizar()
        self._raiz.deiconify()
        self._raiz.lift()
        self._campo.focus_force()
        self._visivel = True

    def esconder(self) -> None:
        self._raiz.withdraw()
        self._visivel = False

    def visivel(self) -> bool:
        return self._visivel

    def texto(self) -> str:
        return self._campo.get("1.0", "end-1c")

    def acoes_visiveis(self) -> tuple[Acao, ...]:
        return self._visiveis

    def selecionada(self) -> Acao | None:
        if not self._visiveis:
            return None
        return self._visiveis[min(self._selecionada, len(self._visiveis) - 1)]

    def digitar(self, texto: str) -> None:
        """Põe texto no campo como se tivesse sido digitado (para a sonda e o teste)."""
        self._campo.delete("1.0", "end")
        self._campo.insert("1.0", texto)
        self._atualizar()

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

    # -- o desenho ------------------------------------------------------------

    def _atualizar(self) -> None:
        """Refaz o destaque, o placeholder e a lista a partir do texto de agora."""
        texto = self.texto()
        if "\n" in texto:
            texto = texto.replace("\n", " ")
            self._campo.delete("1.0", "end")
            self._campo.insert("1.0", texto)

        self._campo.tag_remove("comando", "1.0", "end")
        faixa = comando_destacado(texto, [acao.nome for acao in self._acoes])
        if faixa is not None:
            self._campo.tag_add("comando", f"1.{faixa[0]}", f"1.{faixa[1]}")

        if texto:
            self._placeholder.place_forget()
        else:
            self._placeholder.place(x=8, y=6)

        visiveis = filtrar(self._acoes, texto)
        if visiveis != self._visiveis:
            self._visiveis = visiveis
            self._selecionada = 0
            self._desenhar(visiveis)
        else:
            self._pintar_selecao()

    def _desenhar(self, visiveis: Sequence[Acao]) -> None:
        tk = self._tk
        for linha in self._linhas:
            linha.destroy()
        self._linhas = []
        for indice, acao in enumerate(visiveis):
            linha = tk.Frame(self._lista, background=FUNDO, height=ALTURA_DA_LINHA)
            linha.pack(fill="x")
            linha.pack_propagate(False)
            icone = tk.Label(
                linha, text=acao.icone, width=3, font=FONTE_DO_ICONE, background=FUNDO, foreground=DESTAQUE
            )
            icone.pack(side="left", padx=(6, 2))
            rotulo = tk.Label(
                linha, text=acao.rotulo_atual(), font=FONTE_DA_LINHA, background=FUNDO, foreground=TEXTO
            )
            rotulo.pack(side="left")
            descricao = tk.Label(
                linha,
                text=acao.descricao,
                font=FONTE_DA_DESCRICAO,
                background=FUNDO,
                foreground=TEXTO_APAGADO,
            )
            descricao.pack(side="left", padx=(10, 0))
            for widget in (linha, icone, rotulo, descricao):
                widget.bind("<Button-1>", lambda _evento, i=indice: self._clicar(i))
                widget.bind("<Enter>", lambda _evento, i=indice: self._apontar(i))
            self._linhas.append(linha)

        altura = MARGEM * 2 + ALTURA_DO_CAMPO + (len(visiveis) * ALTURA_DA_LINHA + 6 if visiveis else 0)
        self._painel(altura)
        self._pintar_selecao()

    def _painel(self, altura: int) -> None:
        raiz, tela = self._raiz, self._tela
        x = (raiz.winfo_screenwidth() - LARGURA) // 2
        y = raiz.winfo_screenheight() // 4
        raiz.geometry(f"{LARGURA}x{altura}+{x}+{y}")
        tela.configure(width=LARGURA, height=altura)
        tela.delete("all")
        tela.create_polygon(
            *_cantos_arredondados(1, 1, LARGURA - 2, altura - 2, RAIO),
            smooth=True,
            fill=FUNDO,
            outline=BORDA,
            width=2,
        )
        tela.create_window(
            MARGEM, MARGEM, anchor="nw", window=self._campo, width=LARGURA - 2 * MARGEM, height=ALTURA_DO_CAMPO
        )
        if self._linhas:
            tela.create_line(
                MARGEM, MARGEM + ALTURA_DO_CAMPO + 2, LARGURA - MARGEM, MARGEM + ALTURA_DO_CAMPO + 2, fill="#2c2c30"
            )
            tela.create_window(
                MARGEM,
                MARGEM + ALTURA_DO_CAMPO + 6,
                anchor="nw",
                window=self._lista,
                width=LARGURA - 2 * MARGEM,
                height=len(self._linhas) * ALTURA_DA_LINHA,
            )

    def _pintar_selecao(self) -> None:
        for indice, linha in enumerate(self._linhas):
            cor = FUNDO_SELECIONADO if indice == self._selecionada else FUNDO
            linha.configure(background=cor)
            for filho in linha.winfo_children():
                filho.configure(background=cor)

    # -- os gestos ------------------------------------------------------------

    def _mover_selecao(self, passo: int) -> str:
        if self._visiveis:
            self._selecionada = (self._selecionada + passo) % len(self._visiveis)
            self._pintar_selecao()
        return "break"

    def _apontar(self, indice: int) -> None:
        self._selecionada = indice
        self._pintar_selecao()

    def _clicar(self, indice: int) -> None:
        if indice < len(self._visiveis):
            self._despachar(self._visiveis[indice].nome)

    def _enter(self, _evento=None) -> str:
        texto = self.texto().strip()
        if texto:
            self._despachar(texto)
        elif (acao := self.selecionada()) is not None:
            self._despachar(acao.nome)
        else:
            self.esconder()
        return "break"

    def _despachar(self, texto: str) -> None:
        self.esconder()
        if self._callback is None:
            return
        try:
            self._callback(texto)
        except Exception:  # noqa: BLE001 — o handler nunca deixa exceção subir ao Tk
            _log.exception("O despacho da palheta falhou.")

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

    def _ao_perder_o_foco(self, _evento=None) -> None:
        self._raiz.after(ATRASO_DO_FOCO_MS, self._esconder_se_sem_foco)

    def _esconder_se_sem_foco(self) -> None:
        try:
            com_foco = self._raiz.focus_get()
        except (self._tk.TclError, KeyError):
            com_foco = None
        if self._visivel and com_foco is None:
            self.esconder()


def _cantos_arredondados(x1: int, y1: int, x2: int, y2: int, raio: int) -> list[int]:
    """Os pontos de um retângulo de cantos arredondados para `create_polygon(smooth=True)`."""
    return [
        x1 + raio, y1, x2 - raio, y1, x2, y1, x2, y1 + raio,
        x2, y2 - raio, x2, y2, x2 - raio, y2, x1 + raio, y2,
        x1, y2, x1, y2 - raio, x1, y1 + raio, x1, y1,
    ]
