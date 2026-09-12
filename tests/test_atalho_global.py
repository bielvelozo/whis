"""O atalho global: o parse da combinação e o thread do laço, sem tocar no teclado.

`RegisterHotKey`, `GetMessage` e `PostThreadMessage` entram como callables
injetados: o que se prova é que o registro recusado é visível na hora, que o
`WM_HOTKEY` certo dispara e o errado não, e que `parar` encerra o laço e
desregistra.
"""

from __future__ import annotations

import queue
import threading

import pytest

from whis.atalho_global import (
    ID_DO_ATALHO,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    WM_HOTKEY,
    Atalho,
    AtalhoGlobal,
    AtalhoInvalido,
    analisar_atalho,
)

# -- o parse ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "modificadores", "tecla", "normalizado"),
    [
        ("ctrl+alt+space", MOD_CONTROL | MOD_ALT, 0x20, "ctrl+alt+space"),
        ("Ctrl + Shift + K", MOD_CONTROL | MOD_SHIFT, ord("K"), "ctrl+shift+k"),
        ("win+f12", MOD_WIN, 0x7B, "win+f12"),
        ("alt+F1", MOD_ALT, 0x70, "alt+f1"),
        ("ctrl+alt+shift+7", MOD_CONTROL | MOD_ALT | MOD_SHIFT, ord("7"), "ctrl+alt+shift+7"),
    ],
)
def test_combinacoes_validas(texto: str, modificadores: int, tecla: int, normalizado: str):
    atalho = analisar_atalho(texto)

    assert atalho == Atalho(modificadores=modificadores, tecla=tecla, texto=normalizado)


@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("space", "modificador"),
        ("ctrl+alt", "terminar numa tecla"),
        ("ctrl+", "sobrando"),
        ("", "vazio"),
        ("ctrl+ctrl+a", "duas vezes"),
        ("ctrl+meta+a", "não é modificador"),
        ("ctrl+enter", "não é uma tecla conhecida"),
        ("ctrl+f13", "não é uma tecla conhecida"),
    ],
)
def test_combinacoes_invalidas_dizem_o_motivo(texto: str, motivo: str):
    with pytest.raises(AtalhoInvalido, match=motivo):
        analisar_atalho(texto)


# -- o thread do laço ----------------------------------------------------------


class Windows:
    """As cinco portas do Windows como uma fila: cada `put` é uma mensagem."""

    def __init__(self, *, aceita: int = 1) -> None:
        self.aceita = aceita
        self.registros: list[tuple[int, int, int]] = []
        self.desregistros: list[int] = []
        self.encerrados: list[int] = []
        self.fila: queue.Queue = queue.Queue()

    def registrar(self, id_: int, modificadores: int, tecla: int) -> int:
        self.registros.append((id_, modificadores, tecla))
        return self.aceita

    def desregistrar(self, id_: int) -> None:
        self.desregistros.append(id_)

    def proxima_mensagem(self):
        return self.fila.get(timeout=5)

    def encerrar_thread(self, tid: int) -> None:
        self.encerrados.append(tid)
        self.fila.put(None)

    def atalho(self, ao_disparar) -> AtalhoGlobal:
        return AtalhoGlobal(
            analisar_atalho("ctrl+alt+space"),
            ao_disparar,
            registrar=self.registrar,
            desregistrar=self.desregistrar,
            proxima_mensagem=self.proxima_mensagem,
            id_do_thread=lambda: 4242,
            encerrar_thread=self.encerrar_thread,
        )


def test_registro_recusado_e_visivel_na_hora_e_nada_fica_rodando():
    windows = Windows(aceita=0)
    atalho = windows.atalho(lambda: None)

    assert atalho.iniciar() is False

    atalho.parar()
    assert atalho.registrado is False
    assert windows.desregistros == []
    assert windows.encerrados == []


def test_registro_aceito_usa_mod_norepeat_e_dispara_so_no_id_certo():
    disparos = threading.Semaphore(0)
    windows = Windows(aceita=1)
    atalho = windows.atalho(disparos.release)

    assert atalho.iniciar() is True
    assert windows.registros == [(ID_DO_ATALHO, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x20)]

    windows.fila.put((WM_HOTKEY, ID_DO_ATALHO))
    windows.fila.put((WM_HOTKEY, 99))
    windows.fila.put((0x0113, ID_DO_ATALHO))  # WM_TIMER: outra mensagem qualquer
    windows.fila.put((WM_HOTKEY, ID_DO_ATALHO))
    assert disparos.acquire(timeout=5) and disparos.acquire(timeout=5)
    assert not disparos.acquire(timeout=0.2)

    atalho.parar()
    assert windows.encerrados == [4242]
    assert windows.desregistros == [ID_DO_ATALHO]
    assert atalho.disparos == 2


def test_um_disparo_que_falha_nao_mata_o_atalho(caplog):
    chamadas: list[int] = []
    pronto = threading.Semaphore(0)

    def disparar() -> None:
        chamadas.append(1)
        pronto.release()
        if len(chamadas) == 1:
            raise RuntimeError("a janela caiu")

    windows = Windows()
    atalho = windows.atalho(disparar)
    atalho.iniciar()

    windows.fila.put((WM_HOTKEY, ID_DO_ATALHO))
    windows.fila.put((WM_HOTKEY, ID_DO_ATALHO))
    assert pronto.acquire(timeout=5) and pronto.acquire(timeout=5)
    atalho.parar()

    assert len(chamadas) == 2
    assert "a janela caiu" in caplog.text or "abrir a palheta falhou" in caplog.text


def test_registrar_que_levanta_conta_como_recusa(caplog):
    def explode(*_args):
        raise OSError("Hot key is already registered")

    atalho = AtalhoGlobal(
        analisar_atalho("ctrl+alt+space"),
        lambda: None,
        registrar=explode,
        desregistrar=lambda _id: None,
        proxima_mensagem=lambda: None,
        id_do_thread=lambda: 1,
        encerrar_thread=lambda _tid: None,
    )

    assert atalho.iniciar() is False
    assert "already registered" in caplog.text
