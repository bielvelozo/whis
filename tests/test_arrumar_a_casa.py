"""Camada 0 da interface: o atalho com AUMID e a remoção do nome antigo.

Tudo por executor espião — nenhum atalho nem tarefa real é tocado na máquina
de teste. O que se prova é o comando montado e o que o subcomando conta.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whis import automacao
from whis.__main__ import main


class ExecutorEspiao:
    def __init__(self, codigo: int = 0, saida: str = "") -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._saida = saida

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        return subprocess.CompletedProcess(comando, self._codigo, "", self._saida)


# -- o atalho do Menu Iniciar com AUMID -------------------------------------


def test_instalar_cria_tambem_o_atalho_do_menu_iniciar_com_aumid(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao()

    automacao.instalar_inicializacao(executar=espiao)

    assert len(espiao.comandos) == 2
    do_menu = espiao.comandos[1]
    assert do_menu[0] == "powershell"
    assert "-File" in do_menu
    assert do_menu[do_menu.index("-File") + 1] == str(automacao.SCRIPT_DO_ATALHO_COM_AUMID)
    assert do_menu[do_menu.index("-Aumid") + 1] == automacao.AUMID
    assert do_menu[do_menu.index("-Argumentos") + 1] == "-m whis bandeja"
    assert do_menu[do_menu.index("-Atalho") + 1] == str(automacao.caminho_do_atalho_do_menu())


def test_o_atalho_do_menu_fica_em_programs_e_nao_em_startup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    menu = automacao.caminho_do_atalho_do_menu()

    assert menu.parent.name == "Programs"
    assert "Startup" not in str(menu)
    assert automacao.caminho_do_atalho().parent == menu.parent / "Startup"


def test_o_script_do_aumid_existe_no_pacote():
    assert automacao.SCRIPT_DO_ATALHO_COM_AUMID.is_file()
    assert "AppUserModel" in automacao.SCRIPT_DO_ATALHO_COM_AUMID.read_text(encoding="utf-8-sig")


def test_falha_no_atalho_do_menu_vira_erro_legivel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    class SoOSegundoFalha(ExecutorEspiao):
        def __call__(self, comando):
            if len(self.comandos) == 1:
                self.comandos.append(comando)
                return subprocess.CompletedProcess(comando, 1, "", "sem permissão no menu")
            return super().__call__(comando)

    with pytest.raises(automacao.ErroDeAutomacao, match="AUMID.*sem permissão no menu"):
        automacao.instalar_inicializacao(executar=SoOSegundoFalha())


def test_remover_inicializacao_leva_o_atalho_do_menu_junto(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    for atalho in (automacao.caminho_do_atalho(), automacao.caminho_do_atalho_do_menu()):
        atalho.parent.mkdir(parents=True, exist_ok=True)
        atalho.write_bytes(b"lnk")

    removido = automacao.remover_inicializacao()

    assert removido == automacao.caminho_do_atalho()
    assert not automacao.caminho_do_atalho().exists()
    assert not automacao.caminho_do_atalho_do_menu().exists()


# -- o nome antigo ----------------------------------------------------------


def test_remover_legado_apaga_o_atalho_e_a_tarefa_do_nome_antigo(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    antigo = automacao.caminho_do_atalho_legado()
    antigo.parent.mkdir(parents=True)
    antigo.write_bytes(b"lnk")
    espiao = ExecutorEspiao()

    legado = automacao.remover_legado(executar=espiao)

    assert legado.atalho == antigo
    assert not antigo.exists()
    assert legado.tarefa is True
    assert espiao.comandos == [["schtasks", "/Delete", "/TN", "SecondBrain-Limpeza", "/F"]]


def test_remover_legado_sem_nada_para_remover_nao_quebra(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    legado = automacao.remover_legado(executar=ExecutorEspiao(codigo=1))

    assert legado.atalho is None
    assert legado.tarefa is False


def test_remover_legado_nunca_toca_nos_atalhos_novos(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    novo = automacao.caminho_do_atalho()
    novo.parent.mkdir(parents=True)
    novo.write_bytes(b"lnk")

    automacao.remover_legado(executar=ExecutorEspiao())

    assert novo.exists()


# -- o subcomando windows ---------------------------------------------------


def test_windows_remover_legado_sozinho_nao_instala_nada(monkeypatch, capsys):
    instalados: list[str] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: instalados.append("bandeja"))
    monkeypatch.setattr(
        automacao,
        "remover_legado",
        lambda: automacao.Legado(atalho=Path("Second Brain.lnk"), tarefa=True),
    )

    codigo = main(["windows", "--remover-legado"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert instalados == []
    assert "Atalho antigo removido de" in saida
    assert "SecondBrain-Limpeza" in saida


def test_windows_remover_legado_diz_quando_nao_havia_nada(monkeypatch, capsys):
    monkeypatch.setattr(
        automacao, "remover_legado", lambda: automacao.Legado(atalho=None, tarefa=False)
    )

    main(["windows", "--remover-legado"])

    saida = capsys.readouterr().out
    assert "Não havia atalho 'Second Brain.lnk'" in saida
    assert "Não havia tarefa 'SecondBrain-Limpeza'" in saida


def test_windows_instala_e_conta_o_atalho_do_menu(monkeypatch, capsys):
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))

    codigo = main(["windows"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "Atalho do Menu Iniciar criado em" in saida
    assert automacao.AUMID in saida
