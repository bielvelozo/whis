"""O acabamento do atendente: subir com o logon e os códigos de `perguntar` no `--help`.

O atalho é provado pelo comando montado, com o executor espião — nenhum
atalho real é criado na máquina de teste. O `--help` é comportamento: é onde o
usuário descobre o que `0`, `3` e `1` querem dizer sem abrir o código.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from second_brain import __main__ as cli
from second_brain import automacao
from second_brain.__main__ import SAIDA_COMPLETA, SAIDA_NAO_NASCEU, SAIDA_PARCIAL, main


class ExecutorEspiao:
    def __init__(self, codigo: int = 0, saida: str = "") -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._saida = saida

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        return subprocess.CompletedProcess(comando, self._codigo, "", self._saida)


# -- o atalho do atendente -----------------------------------------------------


def test_o_atalho_do_atendente_aponta_para_o_atender_sem_console(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao()

    destino = automacao.instalar_atendente(executar=espiao)

    script = " ".join(espiao.comandos[0])
    assert destino.name == automacao.NOME_DO_ATALHO_DO_ATENDENTE
    assert destino != automacao.caminho_do_atalho()
    assert "Startup" in str(destino)
    assert "-m second_brain atender" in script
    assert "bandeja" not in script
    assert "pythonw" in script.lower() or "python" in script.lower()


def test_os_dois_atalhos_convivem_na_mesma_pasta(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    bandeja = automacao.instalar_inicializacao(executar=ExecutorEspiao())
    atendente = automacao.instalar_atendente(executar=ExecutorEspiao())

    assert bandeja.parent == atendente.parent
    assert bandeja.name != atendente.name


def test_falha_do_windows_ao_criar_o_atalho_do_atendente_vira_erro_legivel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    with pytest.raises(automacao.ErroDeAutomacao, match="acesso negado"):
        automacao.instalar_atendente(executar=ExecutorEspiao(codigo=1, saida="acesso negado"))


def test_remover_o_atalho_do_atendente(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert automacao.remover_atendente() is None
    atalho = automacao.caminho_do_atalho_do_atendente()
    atalho.parent.mkdir(parents=True)
    atalho.write_bytes(b"lnk")

    assert automacao.atendente_instalado()
    assert automacao.remover_atendente() == atalho
    assert not automacao.atendente_instalado()


# -- o subcomando windows -------------------------------------------------------


def test_windows_com_atendente_instala_os_dois_atalhos(monkeypatch, capsys):
    feitos: list[str] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: feitos.append("bandeja") or Path("Second Brain.lnk"))
    monkeypatch.setattr(automacao, "instalar_atendente", lambda: feitos.append("atendente") or Path("Second Brain Atendente.lnk"))

    codigo = main(["windows", "--atendente"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert feitos == ["bandeja", "atendente"]
    assert "Atalho do atendente criado em" in saida
    assert "subir sozinho no próximo logon" in saida


def test_windows_sem_a_opcao_nao_mexe_no_atendente(monkeypatch):
    chamado: list[str] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Second Brain.lnk"))
    monkeypatch.setattr(automacao, "instalar_atendente", lambda: chamado.append("atendente"))

    main(["windows"])

    assert chamado == []


def test_windows_remover_com_atendente_tira_os_dois(monkeypatch, capsys):
    removidos: list[str] = []
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: removidos.append("bandeja") or Path("Second Brain.lnk"))
    monkeypatch.setattr(automacao, "remover_atendente", lambda: removidos.append("atendente") or Path("Second Brain Atendente.lnk"))

    codigo = main(["windows", "--atendente", "--remover"])

    assert codigo == 0
    assert removidos == ["bandeja", "atendente"]
    assert "Atalho do atendente removido de" in capsys.readouterr().out


def test_windows_remover_sem_atalho_do_atendente_diz_isso(monkeypatch, capsys):
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(automacao, "remover_atendente", lambda: None)

    main(["windows", "--atendente", "--remover"])

    assert "Não havia atalho do atendente." in capsys.readouterr().out


# -- o --help do perguntar ----------------------------------------------------------


def test_o_help_do_perguntar_documenta_os_codigos_de_saida(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["perguntar", "--help"])

    ajuda = capsys.readouterr().out
    assert saida.value.code == 0
    assert "códigos de saída" in ajuda
    assert f"{SAIDA_COMPLETA}  respondeu, citando" in ajuda
    assert f"{SAIDA_PARCIAL}  respondeu sem achar" in ajuda
    assert f"{SAIDA_NAO_NASCEU}  não conseguiu" in ajuda
    assert "bandeja.log" in ajuda


def test_os_codigos_do_perguntar_sao_os_mesmos_da_daily():
    assert f"{SAIDA_COMPLETA}  " in cli.CODIGOS_DA_PERGUNTA
    assert f"{SAIDA_PARCIAL}  " in cli.CODIGOS_DA_PERGUNTA
    assert f"{SAIDA_NAO_NASCEU}  " in cli.CODIGOS_DA_PERGUNTA
    assert "2  erro de uso" in cli.CODIGOS_DA_PERGUNTA
