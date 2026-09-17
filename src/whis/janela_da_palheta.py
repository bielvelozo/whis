"""A janela da palheta, copiada do Raycast: campo grande, lista de ações, rodapé com as teclas.

Tk, que já vem com o Python. A janela é um `overrideredirect` vestida de
acrílico pelo DWM (`acrilico.py`), com cantos arredondados pelo próprio
Windows 11; quando o Windows recusa o acrílico, volta ao painel de
`-transparentcolor` com um `-alpha` leve. O desenho é o do Raycast de
propósito, a pedido do usuário na terceira prova: painel quase preto e quase
opaco (só o material do acrílico atravessa — um `-alpha` por cima deixava o
texto de trás legível, e ele pediu preto), borda fina de 1 px, o campo em
cima, uma linha por ação — glifo, título, descrição e, à direita, o nome do
comando — com a selecionada num realce arredondado que não encosta na borda,
e um rodapé com o nome e as teclas. O que é roxo é o que é do Whis.

Tudo é desenhado no canvas; o único widget dentro dele é o `Text` de uma linha
(Segoe UI 18) com placeholder, em que a primeira palavra ganha cor quando é um
comando — ou o texto inteiro, quando é o rótulo de uma ação. A lista é
filtrada pelo que se digita (pelo nome do comando e por qualquer palavra do
rótulo). ↑/↓ escolhem; Tab completa o campo com o comando da selecionada (e,
já completo, passa à próxima); Enter executa o texto digitado — um rótulo
inteiro vale como o comando — ou, com o campo vazio, a ação selecionada;
clicar numa linha executa; Esc e perder o foco escondem.

O Tk só aceita chamadas do thread que o criou. O atalho global e o menu da
bandeja vivem em outros threads, então tudo que eles pedem entra por `pedir`,
numa fila que o thread do Tk esvazia a cada 50 ms — o arranjo provado pela
sonda da camada 3. Nada longo roda no handler: quem despacha devolve na hora.

`PortaJanela` é o que a palheta e a bandeja enxergam; o teste monta um dublê.
O filtro, o destaque e o completar são funções puras, testadas sem Tk.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

_log = logging.getLogger("whis.janela_da_palheta")

LARGURA = 720
RAIO = 12
MARGEM = 12
ALTURA_DO_CAMPO = 52
ALTURA_DA_LINHA = 40
ALTURA_DO_RODAPE = 40
#: O realce da linha selecionada fica este tanto para dentro da borda do painel.
RECUO_DA_LINHA = 8
FONTE = ("Segoe UI", 18)
FONTE_DA_LINHA = ("Segoe UI", 11)
FONTE_DA_DESCRICAO = ("Segoe UI", 9)
FONTE_DO_ICONE = ("Segoe UI", 12)
FONTE_DO_RODAPE = ("Segoe UI", 9)

FUNDO = "#0e0e10"
FUNDO_SELECIONADO = "#232327"
SEPARADOR = "#222226"
BORDA = "#4a4380"
DESTAQUE = "#8b7cf6"
TEXTO = "#f2f2f2"
TEXTO_APAGADO = "#8a8a92"
TECLA = "#1c1c20"
BORDA_DA_TECLA = "#36363c"
#: Uma cor que nenhum pixel do painel usa: é o que o Windows torna transparente
#: no fallback sem acrílico.
COR_TRANSPARENTE = "#010203"

#: A tinta do acrílico: o fundo do painel, com esta opacidade, sobre o material.
#: Alta de propósito — o material clareia com o papel de parede, e o painel
#: tem que ler como preto. É a única translucidez: um `-alpha` na janela, por
#: menor que fosse, deixava o texto de trás legível através do painel.
OPACIDADE_DA_TINTA = 0xE8
#: Sem acrílico, a janela inteira quase opaca, porque não há material embaixo.
ALPHA_SEM_ACRILICO = 0.96

PLACEHOLDER = "Type a command…"

#: A cadência com que o thread do Tk olha a fila de pedidos de outros threads.
INTERVALO_DA_FILA_MS = 50

#: Quanto esperar depois de perder o foco antes de esconder: o foco pode estar
#: só trocando de widget dentro da própria janela.
ATRASO_DO_FOCO_MS = 150


@dataclass(frozen=True)
class Acao:
    """Uma linha da lista: o nome do comando, o glifo, o título, a descrição e se leva argumento."""

    nome: str
    icone: str
    rotulo: str | Callable[[], str]
    descricao: str = ""
    aceita_argumento: bool = False

    def rotulo_atual(self) -> str:
        return self.rotulo() if callable(self.rotulo) else self.rotulo


def filtrar(acoes: Sequence[Acao], texto: str) -> tuple[Acao, ...]:
    """As ações que a primeira palavra digitada começa: pelo nome do comando primeiro, depois
    por qualquer palavra do rótulo; todas com o campo vazio."""
    palavras = texto.split()
    if not palavras:
        return tuple(acoes)
    prefixo = palavras[0].casefold()
    pelo_nome = tuple(acao for acao in acoes if acao.nome.casefold().startswith(prefixo))
    pelo_rotulo = tuple(
        acao
        for acao in acoes
        if acao not in pelo_nome
        and any(palavra.startswith(prefixo) for palavra in acao.rotulo_atual().casefold().split())
    )
    return pelo_nome + pelo_rotulo


def comando_pelo_rotulo(texto: str, acoes: Sequence[Acao]) -> str | None:
    """O nome do comando cujo rótulo é o texto digitado (sem diferenciar maiúsculas), ou `None`."""
    procurado = " ".join(texto.split()).casefold()
    if not procurado:
        return None
    return next((acao.nome for acao in acoes if acao.rotulo_atual().casefold() == procurado), None)


def completar(acao: Acao) -> str:
    """O que o Tab põe no campo: o comando, e um espaço quando ele aceita argumento."""
    return f"{acao.nome} " if acao.aceita_argumento else acao.nome


def comando_destacado(texto: str, acoes: Sequence[Acao]) -> tuple[int, int] | None:
    """`(inicio, fim)` do destaque: a primeira palavra quando é exatamente um comando, ou o
    texto inteiro quando é exatamente um rótulo; senão `None`."""
    sem_indentacao = texto.lstrip()
    inicio = len(texto) - len(sem_indentacao)
    miolo = sem_indentacao.rstrip()
    if not miolo:
        return None
    palavra = miolo.split(None, 1)[0]
    if palavra.casefold() in {acao.nome.casefold() for acao in acoes}:
        return inicio, inicio + len(palavra)
    if comando_pelo_rotulo(miolo, acoes) is not None:
        return inicio, inicio + len(miolo)
    return None


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
        raiz.configure(background=FUNDO)

        tela = tk.Canvas(raiz, highlightthickness=0, bd=0, background=FUNDO)
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
        campo.bind("<Tab>", self._tab)
        campo.bind("<KeyRelease>", lambda _evento: self._atualizar())
        campo.bind("<FocusOut>", self._ao_perder_o_foco)

        placeholder = tk.Label(
            campo, text=PLACEHOLDER, font=FONTE, background=FUNDO, foreground=TEXTO_APAGADO
        )
        placeholder.bind("<Button-1>", lambda _evento: campo.focus_set())

        # O campo entra no canvas uma vez só: apagá-lo a cada redesenho desmontaria
        # o widget, e com ele o foco e o cursor.
        janela_do_campo = tela.create_window(
            MARGEM, MARGEM, anchor="nw", window=campo, width=LARGURA - 2 * MARGEM, height=ALTURA_DO_CAMPO
        )

        self._tk = tk
        self._raiz = raiz
        self._tela = tela
        self._campo = campo
        self._janela_do_campo = janela_do_campo
        self._placeholder = placeholder
        self._fila: queue.Queue[Callable[[], object]] = queue.Queue()
        self._callback: Callable[[str], object] | None = None
        self._acoes: tuple[Acao, ...] = ()
        self._visiveis: tuple[Acao, ...] = ()
        #: Os realces das linhas desenhadas, um item do canvas por ação visível.
        self._linhas: list[int] = []
        self._selecionada = 0
        self._visivel = False
        self._encerrada = False
        #: `None` até a primeira abertura; depois, se o Windows aceitou o acrílico.
        self._acrilico: bool | None = None
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
        # Um rótulo pode ter mudado com a janela escondida ("Start recording" →
        # "Stop recording"): a lista é sempre redesenhada ao abrir.
        self._visiveis = ()
        self._atualizar()
        self._raiz.deiconify()
        self._raiz.lift()
        self._vestir()
        self._campo.focus_force()
        self._visivel = True

    def esconder(self) -> None:
        self._despir()
        self._raiz.withdraw()
        self._visivel = False

    def visivel(self) -> bool:
        return self._visivel

    def texto(self) -> str:
        return self._campo.get("1.0", "end-1c")

    def acoes_visiveis(self) -> tuple[Acao, ...]:
        return self._visiveis

    def titulos_desenhados(self) -> list[str]:
        """Os títulos como estão na tela agora (para o teste ver um rótulo dinâmico mudar)."""
        return [self._tela.itemcget(item, "text") for item in self._tela.find_withtag("titulo")]

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

    def _vestir(self) -> None:
        """A cada abertura, com a janela já mapeada (só então existe o HWND que o DWM enxerga).

        A cada abertura, e não uma vez só, porque o DWM deste build esquece a
        tinta quando a janela some e volta: `_despir` a tira ao esconder e aqui
        ela volta inteira. Os cantos são pedidos uma vez.
        """
        if self._acrilico is False:
            return
        from . import acrilico

        hwnd = acrilico.hwnd_da_raiz(self._raiz)
        if hwnd and acrilico.aplicar_acrilico(hwnd, acrilico.tinta_abgr(FUNDO, OPACIDADE_DA_TINTA)):
            if self._acrilico is None:
                acrilico.arredondar_cantos(hwnd)
            self._acrilico = True
            return
        self._acrilico = False
        _log.warning("Sem acrílico: a palheta fica só translúcida (alpha %.2f).", ALPHA_SEM_ACRILICO)
        self._raiz.configure(background=COR_TRANSPARENTE)
        self._tela.configure(background=COR_TRANSPARENTE)
        try:
            self._raiz.attributes("-transparentcolor", COR_TRANSPARENTE)
            self._raiz.attributes("-alpha", ALPHA_SEM_ACRILICO)
        except self._tk.TclError:  # fora do Windows os cantos ficam quadrados
            pass

    def _despir(self) -> None:
        if not self._acrilico:
            return
        from . import acrilico

        acrilico.desligar_acrilico(acrilico.hwnd_da_raiz(self._raiz))

    def _atualizar(self) -> None:
        """Refaz o destaque, o placeholder e a lista a partir do texto de agora."""
        texto = self.texto()
        if "\n" in texto:
            texto = texto.replace("\n", " ")
            self._campo.delete("1.0", "end")
            self._campo.insert("1.0", texto)

        self._campo.tag_remove("comando", "1.0", "end")
        faixa = comando_destacado(texto, self._acoes)
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
        tela = self._tela
        topo_da_lista = MARGEM + ALTURA_DO_CAMPO + 14
        altura_da_lista = len(visiveis) * ALTURA_DA_LINHA + 8 if visiveis else 0
        self._painel(topo_da_lista + altura_da_lista + ALTURA_DO_RODAPE)

        self._linhas = []
        for indice, acao in enumerate(visiveis):
            y = topo_da_lista + 4 + indice * ALTURA_DA_LINHA
            centro = y + ALTURA_DA_LINHA // 2
            marca = f"linha{indice}"
            realce = tela.create_polygon(
                *_cantos_arredondados(RECUO_DA_LINHA, y, LARGURA - RECUO_DA_LINHA, y + ALTURA_DA_LINHA, 8),
                smooth=True,
                fill=FUNDO,
                outline="",
                tags=(marca, "desenho"),
            )
            tela.create_text(
                RECUO_DA_LINHA + 22, centro, text=acao.icone, font=FONTE_DO_ICONE, fill=DESTAQUE, tags=(marca, "desenho")
            )
            titulo = tela.create_text(
                RECUO_DA_LINHA + 44,
                centro,
                text=acao.rotulo_atual(),
                font=FONTE_DA_LINHA,
                fill=TEXTO,
                anchor="w",
                tags=(marca, "titulo", "desenho"),
            )
            tela.create_text(
                tela.bbox(titulo)[2] + 12,
                centro + 1,
                text=acao.descricao,
                font=FONTE_DA_DESCRICAO,
                fill=TEXTO_APAGADO,
                anchor="w",
                tags=(marca, "desenho"),
            )
            tela.create_text(
                LARGURA - RECUO_DA_LINHA - 16,
                centro,
                text=acao.nome,
                font=FONTE_DA_DESCRICAO,
                fill=DESTAQUE,
                anchor="e",
                tags=(marca, "desenho"),
            )
            tela.tag_bind(marca, "<Button-1>", lambda _evento, i=indice: self._clicar(i))
            tela.tag_bind(marca, "<Enter>", lambda _evento, i=indice: self._apontar(i))
            self._linhas.append(realce)
        self._pintar_selecao()

    def _painel(self, altura: int) -> None:
        raiz, tela = self._raiz, self._tela
        x = (raiz.winfo_screenwidth() - LARGURA) // 2
        y = raiz.winfo_screenheight() // 4
        raiz.geometry(f"{LARGURA}x{altura}+{x}+{y}")
        tela.configure(width=LARGURA, height=altura)
        tela.delete("desenho")
        fundo = tela.create_polygon(
            *_cantos_arredondados(1, 1, LARGURA - 1, altura - 1, RAIO),
            smooth=True,
            fill=FUNDO,
            outline=BORDA,
            width=1,
            tags=("desenho",),
        )
        tela.tag_lower(fundo)
        separador = MARGEM + ALTURA_DO_CAMPO + 7
        tela.create_line(1, separador, LARGURA - 1, separador, fill=SEPARADOR, tags=("desenho",))
        self._rodape(altura)

    def _rodape(self, altura: int) -> None:
        tela = self._tela
        topo = altura - ALTURA_DO_RODAPE
        centro = topo + ALTURA_DO_RODAPE // 2
        tela.create_line(1, topo, LARGURA - 1, topo, fill=SEPARADOR, tags=("desenho",))
        tela.create_text(MARGEM + 6, centro, text="◆", font=FONTE_DO_RODAPE, fill=DESTAQUE, anchor="w", tags=("desenho",))
        tela.create_text(MARGEM + 22, centro, text="Whis", font=FONTE_DO_RODAPE, fill=TEXTO_APAGADO, anchor="w", tags=("desenho",))

        x = LARGURA - MARGEM - 6
        x = self._tecla(x, centro, "Tab")
        x = self._dica(x, centro, "Complete")
        tela.create_line(x, centro - 8, x, centro + 8, fill=BORDA_DA_TECLA, tags=("desenho",))
        x = self._tecla(x - 12, centro, "↵")
        self._dica(x, centro, "Run")

    def _tecla(self, x_direita: int, centro: int, texto: str) -> int:
        """Uma tecla desenhada como no Raycast, encostada em `x_direita`; devolve onde a próxima acaba."""
        tela = self._tela
        item = tela.create_text(
            x_direita - 7, centro, text=texto, font=FONTE_DO_RODAPE, fill=TEXTO_APAGADO, anchor="e", tags=("desenho",)
        )
        esquerda = tela.bbox(item)[0] - 7
        caixa = tela.create_polygon(
            *_cantos_arredondados(esquerda, centro - 10, x_direita, centro + 10, 4),
            smooth=True,
            fill=TECLA,
            outline=BORDA_DA_TECLA,
            width=1,
            tags=("desenho",),
        )
        tela.tag_lower(caixa, item)
        return esquerda - 6

    def _dica(self, x_direita: int, centro: int, texto: str) -> int:
        item = self._tela.create_text(
            x_direita, centro, text=texto, font=FONTE_DO_RODAPE, fill=TEXTO, anchor="e", tags=("desenho",)
        )
        return self._tela.bbox(item)[0] - 12

    def _pintar_selecao(self) -> None:
        for indice, realce in enumerate(self._linhas):
            cor = FUNDO_SELECIONADO if indice == self._selecionada else FUNDO
            self._tela.itemconfigure(realce, fill=cor)

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

    def _tab(self, _evento=None) -> str:
        acao = self.selecionada()
        if acao is None:
            return "break"
        if self.texto() == completar(acao):
            self._mover_selecao(1)
            acao = self.selecionada()
        self.digitar(completar(acao))
        self._campo.mark_set("insert", "end")
        return "break"

    def _enter(self, _evento=None) -> str:
        texto = self.texto().strip()
        if texto:
            self._despachar(comando_pelo_rotulo(texto, self._acoes) or texto)
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
