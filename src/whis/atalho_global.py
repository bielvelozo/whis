"""O atalho global de teclado que abre a palheta de qualquer janela.

`RegisterHotKey` do Windows, pelo `pywin32` que já está na venv — sem hook de
teclado: o sistema só avisa quando **aquela** combinação é pressionada, e nada
do que o usuário digita passa por aqui. A `WM_HOTKEY` chega à fila de mensagens
do thread que registrou, e por isso o atalho vive num thread próprio com o seu
próprio `GetMessage`: o `pystray` consome as mensagens do thread dele, e o Tk
as do principal — nenhum dos dois entregaria a nossa (sonda em
`.scratch/interface/research/sonda-palheta.py`).

O que este módulo sabe é analisar a combinação e rodar o laço. Quem registra e
quem lê a fila entram por porta injetada, para o laço ser provado sem tocar no
teclado da máquina de teste.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

_log = logging.getLogger("whis.atalho_global")

#: Os modificadores e as mensagens de `winuser.h`, escritos aqui para o parse
#: não depender do `pywin32` (a configuração o importa em toda máquina).
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
#: Sem ele, segurar a tecla dispara a palheta várias vezes pelo auto-repeat.
MOD_NOREPEAT = 0x4000
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312

#: O identificador que o Windows devolve em `wParam` — só temos um atalho.
ID_DO_ATALHO = 1

ATALHO_PADRAO = "ctrl+alt+w"

_MODIFICADORES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

_TECLAS = {
    "space": 0x20,
    "espaco": 0x20,
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
    **{letra: ord(letra.upper()) for letra in "abcdefghijklmnopqrstuvwxyz"},
    **{digito: ord(digito) for digito in "0123456789"},
}


class AtalhoInvalido(ValueError):
    """A combinação escrita na configuração não é um atalho que o Windows aceite."""


@dataclass(frozen=True)
class Atalho:
    """Uma combinação já traduzida para o que `RegisterHotKey` espera."""

    modificadores: int
    tecla: int
    texto: str


def analisar_atalho(texto: str) -> Atalho:
    """`"ctrl+alt+space"` → `Atalho`. Maiúsculas e espaços não importam.

    Exige pelo menos um modificador: uma tecla solta como atalho global
    engoliria aquela letra em todo programa da máquina.
    """
    partes = [parte.strip().casefold() for parte in texto.split("+")]
    if not texto.strip() or any(not parte for parte in partes):
        raise AtalhoInvalido("o atalho veio vazio ou com um '+' sobrando")

    *modificadores, ultima = partes
    combinados = 0
    for parte in modificadores:
        if parte not in _MODIFICADORES:
            raise AtalhoInvalido(
                f"'{parte}' não é modificador; antes da tecla só valem "
                f"{', '.join(sorted(set(_MODIFICADORES)))}"
            )
        if combinados & _MODIFICADORES[parte]:
            raise AtalhoInvalido(f"'{parte}' aparece duas vezes")
        combinados |= _MODIFICADORES[parte]

    if ultima in _MODIFICADORES:
        raise AtalhoInvalido("o atalho precisa terminar numa tecla, não num modificador")
    if ultima not in _TECLAS:
        raise AtalhoInvalido(
            f"'{ultima}' não é uma tecla conhecida; valem letra, dígito, space e f1..f12"
        )
    if not combinados:
        raise AtalhoInvalido("o atalho precisa de pelo menos um modificador (ctrl, alt, shift, win)")

    return Atalho(modificadores=combinados, tecla=_TECLAS[ultima], texto="+".join(partes))


#: `registrar(id, modificadores, tecla) -> registrou?` — o adaptador real
#: traduz a exceção do `pywin32` em `False`.
Registrador = Callable[[int, int, int], object]
#: `proxima_mensagem() -> (mensagem, wparam)`, ou `None` quando a fila fechou.
LeitorDeMensagens = Callable[[], tuple[int, int] | None]


class AtalhoGlobal:
    """O thread que registra a combinação e chama `ao_disparar` a cada tecla.

    `iniciar()` só devolve depois que o registro aconteceu (ou falhou), para a
    bandeja saber na hora se o atalho está tomado por outro programa.
    `ao_disparar` roda **no thread do atalho**: quem precisa do Tk enfileira.
    """

    def __init__(
        self,
        atalho: Atalho,
        ao_disparar: Callable[[], None],
        *,
        registrar: Registrador | None = None,
        desregistrar: Callable[[int], None] | None = None,
        proxima_mensagem: LeitorDeMensagens | None = None,
        id_do_thread: Callable[[], int] | None = None,
        encerrar_thread: Callable[[int], None] | None = None,
    ) -> None:
        self.atalho = atalho
        self._ao_disparar = ao_disparar
        self._registrar = registrar or _registrar_no_windows
        self._desregistrar = desregistrar or _desregistrar_no_windows
        self._proxima_mensagem = proxima_mensagem or _proxima_mensagem_do_windows
        self._id_do_thread = id_do_thread or _id_do_thread_atual
        self._encerrar_thread = encerrar_thread or _encerrar_thread_do_windows
        self._thread: threading.Thread | None = None
        self._tid: int | None = None
        self._pronto = threading.Event()
        self.registrado = False
        self.disparos = 0

    def iniciar(self, *, espera_s: float = 5.0) -> bool:
        """Sobe o thread e devolve se o Windows aceitou a combinação."""
        self._thread = threading.Thread(target=self._laco, name="whis-atalho", daemon=True)
        self._thread.start()
        self._pronto.wait(espera_s)
        return self.registrado

    def parar(self, *, espera_s: float = 3.0) -> None:
        """Encerra o laço (`WM_QUIT` no thread dele) e desregistra a combinação."""
        if self.registrado and self._tid is not None and self._thread is not None and self._thread.is_alive():
            try:
                self._encerrar_thread(self._tid)
            except Exception as erro:  # noqa: BLE001 — o processo está saindo
                _log.debug("Não foi possível avisar o thread do atalho: %s", erro)
        if self._thread is not None:
            self._thread.join(espera_s)

    def _laco(self) -> None:
        self._tid = self._id_do_thread()
        try:
            self.registrado = bool(
                self._registrar(ID_DO_ATALHO, self.atalho.modificadores | MOD_NOREPEAT, self.atalho.tecla)
            )
        except Exception as erro:  # noqa: BLE001 — falhar aqui não pode derrubar a bandeja
            _log.error("Não foi possível registrar o atalho %s: %s", self.atalho.texto, erro)
            self.registrado = False
        self._pronto.set()
        if not self.registrado:
            _log.warning("O atalho %s não foi registrado — a palheta abre só pelo menu.", self.atalho.texto)
            return
        _log.info("Atalho global %s registrado.", self.atalho.texto)

        try:
            while True:
                mensagem = self._proxima_mensagem()
                if mensagem is None:
                    break
                tipo, wparam = mensagem
                if tipo == WM_QUIT:
                    break
                if tipo == WM_HOTKEY and wparam == ID_DO_ATALHO:
                    self.disparos += 1
                    try:
                        self._ao_disparar()
                    except Exception:  # noqa: BLE001 — um disparo com erro não mata o atalho
                        _log.exception("O atalho disparou, mas abrir a palheta falhou.")
        finally:
            try:
                self._desregistrar(ID_DO_ATALHO)
                _log.info("Atalho global %s desregistrado.", self.atalho.texto)
            except Exception as erro:  # noqa: BLE001
                _log.debug("Erro ao desregistrar o atalho: %s", erro)


# -- os adaptadores do Windows ---------------------------------------------


def _registrar_no_windows(id_: int, modificadores: int, tecla: int) -> bool:
    import pywintypes
    import win32gui

    try:
        win32gui.RegisterHotKey(None, id_, modificadores, tecla)
    except pywintypes.error as erro:
        _log.warning("RegisterHotKey recusou a combinação: %s", erro)
        return False
    return True


def _desregistrar_no_windows(id_: int) -> None:
    import win32gui

    win32gui.UnregisterHotKey(None, id_)


def _proxima_mensagem_do_windows() -> tuple[int, int] | None:
    """`GetMessage` do thread do atalho: `(mensagem, wParam)`, ou `None` no `WM_QUIT`."""
    import win32gui

    retorno, mensagem = win32gui.GetMessage(None, 0, 0)
    if retorno == 0:
        return None
    _hwnd, tipo, wparam, _lparam, _tempo, _ponto = mensagem
    return tipo, wparam


def _id_do_thread_atual() -> int:
    import win32api

    return win32api.GetCurrentThreadId()


def _encerrar_thread_do_windows(tid: int) -> None:
    import win32api

    win32api.PostThreadMessage(tid, WM_QUIT, 0, 0)
