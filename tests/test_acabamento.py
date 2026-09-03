"""O acabamento da bandeja: instância única, título automático e amarração ao Windows.

Três coisas que só aparecem no uso diário e que nenhum teste de pipeline pegaria:
subir a bandeja duas vezes, gravar uma reunião sem nome, e depender de alguém
lembrar de rodar comandos. Nada aqui mexe no Windows da máquina de teste — o
executor de processos externos é injetado, e o que se prova é o comando montado.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from second_brain import automacao, janelas
from second_brain.coletor import Coletor
from second_brain.configuracao import Configuracao
from second_brain.fakes import ResumoFake, STTFake
from second_brain.instancia import OutraInstancia, Trava, caminho_da_trava
from test_coletor import GravadorDublê


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


# -- título da reunião ------------------------------------------------------


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        ("Planejamento do trimestre - Google Meet", "Planejamento do trimestre"),
        ("(3) Daily do time - Google Meet - Google Chrome", "Daily do time"),
        ("Retrospectiva da sprint | Microsoft Teams", "Retrospectiva da sprint"),
        ("Alinhamento com o cliente - Zoom Meeting", "Alinhamento com o cliente"),
    ],
)
def test_o_titulo_sai_da_janela_da_reuniao(janela: str, esperado: str):
    assert janelas.titulo_de_reuniao([janela]) == esperado


@pytest.mark.parametrize(
    "janela",
    [
        "Meet - abc-defg-hij",  # código de sala não é nome de reunião
        "second-brain - Visual Studio Code",
        "Caixa de entrada - Outlook",
        "",
    ],
)
def test_janela_sem_nome_de_reuniao_nao_vira_titulo(janela: str):
    assert janelas.titulo_de_reuniao([janela]) is None


def test_a_primeira_reuniao_encontrada_ganha():
    """Com várias janelas abertas, a de reunião é a que importa."""
    abertas = [
        "second-brain - Visual Studio Code",
        "Kickoff do projeto - Google Meet",
        "WhatsApp",
    ]

    assert janelas.titulo_de_reuniao(abertas) == "Kickoff do projeto"


def test_o_coletor_usa_o_titulo_da_janela_quando_ninguem_digita(
    configuracao: Configuracao, caminho_das_gravacoes: Path, caminho_do_vault: Path
):
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorDublê(caminho_das_gravacoes, nome="2026-09-03-1400-kickoff"),
        em_segundo_plano=False,
        deduzir_titulo=lambda: "Kickoff do projeto",
    )

    coletor.iniciar()

    assert coletor.situacao().titulo == "Kickoff do projeto"


def test_titulo_explicito_prevalece_sobre_o_palpite(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorDublê(caminho_das_gravacoes),
        em_segundo_plano=False,
        deduzir_titulo=lambda: "Palpite da janela",
    )

    coletor.iniciar("o que eu digitei")

    assert coletor.situacao().titulo == "o que eu digitei"


def test_palpite_que_explode_nao_derruba_a_gravacao(
    configuracao: Configuracao, caminho_das_gravacoes: Path, caminho_do_vault: Path
):
    """Deduzir título é conveniência; falhar nisso não pode custar a reunião."""

    def quebrado() -> str:
        raise RuntimeError("a API de janelas do Windows recusou")

    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorDublê(caminho_das_gravacoes),
        em_segundo_plano=False,
        deduzir_titulo=quebrado,
    )

    coletor.iniciar()
    coletor.parar()

    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


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
    assert "-m second_brain bandeja" in script
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


def test_a_limpeza_agendada_roda_o_comando_limpar_diariamente(tmp_path: Path):
    espiao = ExecutorEspiao()

    automacao.agendar_limpeza(hora="12:00", executar=espiao, config=tmp_path / "c.toml")

    comando = espiao.comandos[0]
    assert comando[0] == "schtasks" and "/Create" in comando
    assert automacao.NOME_DA_TAREFA in comando
    assert "DAILY" in comando and "12:00" in comando
    tarefa = comando[comando.index("/TR") + 1]
    assert "second_brain" in tarefa and "limpar" in tarefa
    assert "c.toml" in tarefa  # a tarefa aponta a mesma configuração


def test_a_limpeza_agendada_nunca_apaga_direto():
    """A tarefa chama `limpar`, que só apaga o que já virou nota e venceu."""
    espiao = ExecutorEspiao()

    automacao.agendar_limpeza(executar=espiao)

    tarefa = espiao.comandos[0][espiao.comandos[0].index("/TR") + 1]
    assert "--dias" not in tarefa  # respeita o prazo da configuração
    assert "reprocessar" not in tarefa


def test_desagendar_limpeza_diz_quando_nao_havia_tarefa():
    assert automacao.desagendar_limpeza(executar=ExecutorEspiao(codigo=1)) is False
    assert automacao.desagendar_limpeza(executar=ExecutorEspiao(codigo=0)) is True
