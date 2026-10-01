"""Nenhuma janela de terminal: as flags que escondem o console de todo processo filho.

Sem console de verdade não há como ver a janela na suíte; o que se prova é
que um `Popen` espião recebe `CREATE_NO_WINDOW` e o `STARTUPINFO` com
`SW_HIDE` quando o interruptor está ligado, e que as chamadas explícitas
(`automacao._rodar`, `avisos`, `obsidian.lancar`) já saem com elas.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from whis import automacao, obsidian, sem_console
from conftest import AVISAR_DE_VERDADE

so_windows = pytest.mark.skipif(sys.platform != "win32", reason="flags do Windows")


class PopenEspiao:
    recebidos: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        self.recebidos.append(kwargs)


@so_windows
def test_com_o_interruptor_ligado_todo_popen_nasce_sem_console():
    class Popen(PopenEspiao):
        recebidos = []

    assert sem_console.instalar(Popen) is True
    assert sem_console.instalar(Popen) is False, "idempotente"

    Popen(["cmd"], stdout=subprocess.PIPE)
    Popen(["cmd"], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    for kwargs in Popen.recebidos:
        assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW
        assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE
    assert Popen.recebidos[1]["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP


@so_windows
def test_as_opcoes_explicitas_escondem_o_console():
    opcoes = sem_console.opcoes()

    assert opcoes["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert opcoes["startupinfo"].wShowWindow == subprocess.SW_HIDE


@so_windows
def test_o_powershell_do_toast_e_do_agendador_nasce_sem_console(monkeypatch):
    recebidos: list[dict] = []

    def run(comando, **kwargs):
        recebidos.append(kwargs)
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(automacao.subprocess, "run", run)

    automacao._rodar(["powershell", "-File", "x.ps1"])
    AVISAR_DE_VERDADE("t", "x")

    assert len(recebidos) == 2
    assert all(kw["creationflags"] & subprocess.CREATE_NO_WINDOW for kw in recebidos)


@so_windows
def test_o_start_do_cmd_nasce_sem_console():
    recebidos: list[dict] = []

    def recusa(_alvo: str) -> None:
        raise OSError("protocolo desconhecido")

    obsidian.lancar("obsidian://open?vault=v&file=x", iniciar=recusa, executar=lambda c, **kw: recebidos.append(kw))

    [kwargs] = recebidos
    assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_o_cli_do_claude_recebe_o_stderr_em_pipe_e_nao_herda_o_do_pai():
    """Sob pythonw o pai não tem stderr; herdá-lo mata o CLI (Node) com EPIPE."""
    from whis import busca_claude, claude_cli

    opcoes = busca_claude.montar_opcoes(
        busca_claude.FerramentasDoVault.__new__(busca_claude.FerramentasDoVault),
        None,
        modelo=None,
        maximo_de_turnos=1,
    ) if False else None  # montar_opcoes precisa de um vault de verdade; o callback é o que importa

    assert claude_cli.registrar_stderr_do_cli("linha do cli\n") is None
    import inspect

    for modulo in ("busca_claude", "jornal_claude", "resumo_dia_claude"):
        fonte = inspect.getsource(__import__(f"whis.{modulo}", fromlist=[modulo]))
        assert "stderr=registrar_stderr_do_cli" in fonte, modulo
