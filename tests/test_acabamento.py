"""O acabamento da bandeja: instância única e amarração ao Windows.

Duas coisas que só aparecem no uso diário: subir a bandeja duas vezes, e
depender de alguém lembrar de rodar comandos. Nada aqui mexe no Windows da
máquina de teste — o executor de processos externos é injetado, e o que se
prova é o comando montado.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whis import automacao
from whis.configuracao import Configuracao
from whis.instancia import OutraInstancia, Trava, caminho_da_trava


# -- instância única --------------------------------------------------------


def test_a_segunda_bandeja_e_recusada(tmp_path: Path):
    with Trava(tmp_path / "bandeja.lock"):
        with pytest.raises(OutraInstancia, match="já existe uma bandeja"):
            Trava(tmp_path / "bandeja.lock").adquirir()


def test_a_trava_volta_a_ficar_livre_depois_de_liberada(tmp_path: Path):
    primeira = Trava(tmp_path / "bandeja.lock").adquirir()
    primeira.liberar()

    segunda = Trava(tmp_path / "bandeja.lock").adquirir()  # não levanta
    segunda.liberar()


def test_a_recusa_diz_onde_procurar_o_icone(tmp_path: Path):
    """Quem clicou duas vezes precisa saber que o ícone já está lá."""
    with Trava(tmp_path / "bandeja.lock"):
        with pytest.raises(OutraInstancia) as erro:
            Trava(tmp_path / "bandeja.lock").adquirir()

    assert "ícones" in str(erro.value) and "relógio" in str(erro.value)


def test_a_trava_registra_quem_esta_segurando(tmp_path: Path):
    import os

    with Trava(tmp_path / "bandeja.lock") as trava:
        assert trava.pid_registrado() == os.getpid()


def test_a_trava_mora_ao_lado_da_configuracao(configuracao: Configuracao):
    assert caminho_da_trava(configuracao).parent == configuracao.origem.parent


# -- amarração ao Windows ---------------------------------------------------


class ExecutorEspiao:
    """Guarda os comandos em vez de rodá-los. Nenhum atalho real é criado."""

    def __init__(self, codigo: int = 0, saida: str = "") -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._saida = saida

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        return subprocess.CompletedProcess(comando, self._codigo, "", self._saida)


def test_o_atalho_aponta_para_a_bandeja_sem_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao()

    destino = automacao.instalar_inicializacao(executar=espiao)

    script = " ".join(espiao.comandos[0])
    assert destino.name == automacao.NOME_DO_ATALHO
    assert "Startup" in str(destino)
    assert "-m whis bandeja" in script
    assert "pythonw" in script.lower() or "python" in script.lower()


def test_falha_do_windows_ao_criar_o_atalho_vira_erro_legivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    espiao = ExecutorEspiao(codigo=1, saida="acesso negado")

    with pytest.raises(automacao.ErroDeAutomacao, match="acesso negado"):
        automacao.instalar_inicializacao(executar=espiao)


def test_remover_inicializacao_sem_atalho_nao_quebra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert automacao.remover_inicializacao() is None
