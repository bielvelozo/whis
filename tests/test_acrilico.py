"""O vidro da palheta: a tinta, a política e os cantos, sem tocar no Windows.

As duas chamadas ao DWM entram como callable injetado: o que se prova é o que
vai na estrutura (`WCA_ACCENT_POLICY` com `ACCENT_ENABLE_ACRYLICBLURBEHIND` e a
tinta) e que recusa, retorno zero e exceção viram `False` com aviso — nunca
exceção, porque a janela precisa abrir de qualquer jeito.
"""

from __future__ import annotations

import ctypes
import logging

from whis.acrilico import (
    ACCENT_DISABLED,
    ACCENT_ENABLE_ACRYLICBLURBEHIND,
    DWMWA_WINDOW_CORNER_PREFERENCE,
    DWMWCP_ROUND,
    WCA_ACCENT_POLICY,
    AccentPolicy,
    aplicar_acrilico,
    arredondar_cantos,
    desligar_acrilico,
    tinta_abgr,
)


def test_a_tinta_vai_como_abgr():
    assert tinta_abgr("#1c1c1e", 0xCC) == 0xCC1E1C1C
    assert tinta_abgr("#ff0000", 0x00) == 0x000000FF
    assert tinta_abgr("#0000ff", 0xFF) == 0xFFFF0000


def test_o_acrilico_pede_a_politica_certa_ao_dwm():
    chamadas: list[tuple[int, int, int, int]] = []

    def chamar(hwnd: int, dados) -> int:
        politica = ctypes.cast(dados.Data, ctypes.POINTER(AccentPolicy)).contents
        chamadas.append((hwnd, dados.Attribute, politica.AccentState, politica.GradientColor))
        return 1

    assert aplicar_acrilico(4242, 0xCC1E1C1C, chamar=chamar) is True
    assert chamadas == [(4242, WCA_ACCENT_POLICY, ACCENT_ENABLE_ACRYLICBLURBEHIND, 0xCC1E1C1C)]


def test_desligar_manda_a_politica_desligada_pelo_mesmo_caminho():
    chamadas: list[tuple[int, int, int]] = []

    def chamar(hwnd: int, dados) -> int:
        politica = ctypes.cast(dados.Data, ctypes.POINTER(AccentPolicy)).contents
        chamadas.append((hwnd, dados.Attribute, politica.AccentState))
        return 1

    assert desligar_acrilico(4242, chamar=chamar) is True
    assert chamadas == [(4242, WCA_ACCENT_POLICY, ACCENT_DISABLED)]
    assert desligar_acrilico(4242, chamar=lambda _hwnd, _dados: 0) is False


def test_recusa_e_excecao_do_windows_viram_false_com_aviso(caplog):
    caplog.set_level(logging.WARNING, logger="whis.acrilico")

    assert aplicar_acrilico(1, 0, chamar=lambda _hwnd, _dados: 0) is False

    def explode(_hwnd, _dados):
        raise AttributeError("function 'SetWindowCompositionAttribute' not found")

    assert aplicar_acrilico(1, 0, chamar=explode) is False
    assert sum("acrílico" in registro.message for registro in caplog.records) == 2


def test_os_cantos_pedem_round_ao_dwm_e_um_hresult_diferente_de_zero_e_false():
    chamadas: list[tuple[int, int, int]] = []

    def chamar(hwnd: int, atributo: int, valor) -> int:
        chamadas.append((hwnd, atributo, valor.value))
        return 0

    assert arredondar_cantos(7, chamar=chamar) is True
    assert chamadas == [(7, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)]
    assert arredondar_cantos(7, chamar=lambda *_: 0x80070057) is False

    def sem_dwmapi(*_):
        raise OSError("sem dwmapi")

    assert arredondar_cantos(7, chamar=sem_dwmapi) is False
