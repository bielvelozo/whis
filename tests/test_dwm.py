"""Os cantos do DWM, sem tocar no Windows: a chamada entra injetada e recusa ou erro viram `False`."""

from __future__ import annotations

from whis.dwm import DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND, arredondar_cantos


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
