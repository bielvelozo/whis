"""A casca das reuniões: `[granola]` no config, `whis meetings`, a palheta, a tarefa e o vigia.

A Granola entra pelo `ReunioesFake` (trocando `montar_reunioes`), a automação
por executor espião, e os toasts pela fixture `toasts` do conftest. Nada fala
com a Granola nem com o Agendador da máquina de teste.
"""

from __future__ import annotations

import subprocess
from functools import partial
from pathlib import Path

import pytest

from whis import __main__ as cli
from whis import automacao
from whis import palheta as _palheta
from whis.configuracao import ConfiguracaoInvalida, carregar
from whis.fakes import ReunioesFake
from whis.painel import CAMPOS
from whis.portas import ErroDaGranola, LoginNecessario
from whis.reunioes import ResultadoDasReunioes

HORARIO = next(campo for campo in CAMPOS if campo.caminho == "[granola].horario")


class ExecutorEspiao:
    def __init__(self, codigo: int = 0, **codigo_por_trecho: int) -> None:
        self.comandos: list[list[str]] = []
        self._codigo = codigo
        self._codigo_por_trecho = codigo_por_trecho

    def __call__(self, comando: list[str]) -> subprocess.CompletedProcess:
        self.comandos.append(comando)
        texto = " ".join(comando)
        for trecho, codigo in self._codigo_por_trecho.items():
            if trecho in texto:
                return subprocess.CompletedProcess(comando, codigo, "", "")
        return subprocess.CompletedProcess(comando, self._codigo, "", "")

    def registros(self) -> list[list[str]]:
        return [c for c in self.comandos if "-File" in c and "agendar_tarefa" in " ".join(c)]


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{(tmp_path / "vault").as_posix()}"\n{corpo}', encoding="utf-8")
    return arquivo


def parametro(comando: list[str], nome: str) -> str:
    return comando[comando.index(nome) + 1]


# -- a chave ----------------------------------------------------------------------


def test_sem_a_chave_a_granola_puxa_as_dezenove(tmp_path: Path):
    assert carregar(escrever(tmp_path, "")).granola_horario == "19:00"


def test_a_chave_preenchida_e_lida(tmp_path: Path):
    assert carregar(escrever(tmp_path, '[granola]\nhorario = "18:30"\n')).granola_horario == "18:30"


@pytest.mark.parametrize("hora", ['"7h"', '"24:00"', "1930"])
def test_horario_da_granola_fora_de_hh_mm_e_recusado(tmp_path: Path, hora: str):
    with pytest.raises(ConfiguracaoInvalida, match=r"\[granola\].horario.*HH:MM"):
        carregar(escrever(tmp_path, f"[granola]\nhorario = {hora}\n"))


def test_o_painel_mostra_o_horario_da_granola():
    assert HORARIO.ajuda.startswith("quando a tarefa agendada puxa as reuniões da Granola")


# -- whis meetings -----------------------------------------------------------------


@pytest.fixture
def granola(monkeypatch):
    """Troca a Granola de `whis meetings` e guarda com que `pode_logar` ela foi montada."""
    estado: dict = {"porta": ReunioesFake(), "pode_logar": []}

    def montar(configuracao, *, fakes=False, pode_logar=True):
        estado["pode_logar"].append(pode_logar)
        return estado["porta"]

    monkeypatch.setattr(cli, "montar_reunioes", montar)
    return estado


def test_meetings_escreve_a_reuniao_com_resumo_e_sai_completo(
    arquivo_de_configuracao: Path, caminho_do_vault: Path, granola, toasts
):
    assert cli.main(["meetings"]) == cli.SAIDA_COMPLETA

    [nota] = list((caminho_do_vault / "reunioes").glob("*.md"))
    assert nota.name.endswith("-daily-do-time-exemplo.md")
    assert granola["pode_logar"] == [True]
    [(titulo, texto, botao)] = toasts
    assert titulo == "Reuniões no vault"
    assert texto.startswith("1 reunião nova: Daily do time (exemplo)")
    assert "1 ainda sem resumo" in texto
    assert botao is not None


def test_meetings_agendada_nao_pode_logar(arquivo_de_configuracao: Path, granola):
    cli.main(["meetings", "--agendada"])

    assert granola["pode_logar"] == [False]


def test_meetings_agendada_sem_nada_novo_nao_avisa(arquivo_de_configuracao: Path, granola, toasts):
    cli.main(["meetings", "--agendada"])
    toasts.clear()

    assert cli.main(["meetings", "--agendada"]) == cli.SAIDA_COMPLETA
    assert toasts == []


def test_meetings_no_terminal_sem_nada_novo_avisa(arquivo_de_configuracao: Path, granola, toasts):
    cli.main(["meetings"])
    toasts.clear()

    cli.main(["meetings"])

    [(titulo, texto, _)] = toasts
    assert titulo == "Nada novo na Granola"
    assert "ainda sem resumo" in texto


def test_meetings_parcial_sai_tres(arquivo_de_configuracao: Path, granola, toasts):
    from whis.fakes import REUNIOES_DE_EXEMPLO

    com_resumo = REUNIOES_DE_EXEMPLO[0]
    outra = type(com_resumo)(**{**com_resumo.__dict__, "id": "outra", "titulo": "Outra"})
    granola["porta"] = ReunioesFake([com_resumo, outra], omitir={"outra"})

    assert cli.main(["meetings", "--agendada"]) == cli.SAIDA_PARCIAL
    assert "1 não veio" in toasts[-1][1]


def test_meetings_com_tudo_falhando_sai_um(arquivo_de_configuracao: Path, granola, toasts):
    granola["porta"] = ReunioesFake(erro_no_lote={0: ErroDaGranola("fora do ar")})

    assert cli.main(["meetings", "--agendada"]) == cli.SAIDA_NAO_NASCEU
    assert toasts[-1][0] == "As reuniões não vieram"


def test_meetings_sem_login_na_tarefa_pede_o_login_pela_palheta(
    arquivo_de_configuracao: Path, caminho_do_vault: Path, granola, toasts
):
    granola["porta"] = ReunioesFake(erro_ao_listar=LoginNecessario("A Granola pediu login"))

    assert cli.main(["meetings", "--agendada"]) == cli.SAIDA_NAO_NASCEU

    [(titulo, texto, _)] = toasts
    assert titulo == "A Granola pediu login"
    assert "meetings na palheta" in texto


def test_meetings_fakes_escreve_num_vault_temporario(
    arquivo_de_configuracao: Path, caminho_do_vault: Path, toasts, capsys
):
    assert cli.main(["meetings", "--fakes"]) == cli.SAIDA_COMPLETA

    saida = capsys.readouterr().out
    temporario = Path(saida.split("Vault temporário: ")[1].splitlines()[0])
    assert list((temporario / "reunioes").glob("*.md"))
    assert not (caminho_do_vault / "reunioes").exists()
    assert toasts == []


def test_o_help_de_meetings_tem_os_codigos(capsys):
    with pytest.raises(SystemExit):
        cli.main(["meetings", "--help"])

    saida = capsys.readouterr().out
    assert "--agendada" in saida and "códigos de saída" in saida


# -- o toast ------------------------------------------------------------------------


def test_o_toast_sem_reunioes_nos_30_dias():
    resultado = _palheta.resultado_das_reunioes(ResultadoDasReunioes())

    assert resultado.titulo == "Nada novo na Granola"
    assert resultado.texto == "Nenhuma reunião nos últimos 30 dias."


def test_o_toast_com_tudo_no_vault():
    resultado = _palheta.resultado_das_reunioes(ResultadoDasReunioes(ja_no_vault=3))

    assert resultado.texto == "3 reuniões dos últimos 30 dias, todas já no vault."


def test_o_toast_de_duas_novas_abre_a_mais_recente():
    resultado = _palheta.resultado_das_reunioes(
        ResultadoDasReunioes(novas=("reunioes/a.md", "reunioes/b.md"), titulos_novos=("A", "B"))
    )

    assert resultado.texto == "2 reuniões novas: A, B"
    assert resultado.nota == "reunioes/b.md"


def test_o_erro_comum_vira_toast_com_a_mensagem():
    resultado = _palheta.resultado_das_reunioes_que_falharam(ErroDaGranola("porta 33418 ocupada"))

    assert resultado.titulo == "As reuniões não vieram"
    assert "33418" in resultado.texto


# -- a palheta ----------------------------------------------------------------------


def comandos(reunioes):
    return {
        comando.nome: comando
        for comando in _palheta.comandos_padrao(
            fontes_da_daily=lambda _c: (),
            roteiro_da_daily=lambda _c: None,
            busca=lambda _c: None,
            reunioes=reunioes,
        )
    }


def test_meetings_na_palheta_puxa_e_devolve_o_toast(configuracao, caminho_do_vault: Path):
    resultado = comandos(lambda _c: ReunioesFake())["meetings"].rodar("", configuracao)

    assert resultado.titulo == "Reuniões no vault"
    assert resultado.nota.startswith("reunioes/")
    assert (caminho_do_vault / resultado.nota).is_file()


def test_meetings_na_palheta_com_a_granola_fora_do_ar(configuracao):
    porta = ReunioesFake(erro_ao_listar=ErroDaGranola("sem rede"))

    resultado = comandos(lambda _c: porta)["meetings"].rodar("", configuracao)

    assert resultado.titulo == "As reuniões não vieram"


def test_meetings_sem_granola_na_execucao_e_falha_explicada(configuracao):
    with pytest.raises(RuntimeError, match="não estão disponíveis"):
        comandos(None)["meetings"].rodar("", configuracao)


def test_meetings_vem_depois_de_news_na_lista():
    assert _palheta.ORDEM_DAS_ACOES.index("meetings") == _palheta.ORDEM_DAS_ACOES.index("news") + 1


def test_a_bandeja_com_fakes_nao_oferece_a_granola(configuracao_do_diario, monkeypatch):
    from whis import bandeja as _bandeja

    configuracao_do_diario()
    chamadas: list[dict] = []
    monkeypatch.setattr(_bandeja, "executar", lambda configuracao, **extras: chamadas.append(extras) or 0)

    assert cli.main(["bandeja", "--fakes"]) == 0

    palheta = chamadas[0]["palheta"]
    meetings = next(comando for comando in palheta.comandos if comando.nome == "meetings")
    with pytest.raises(RuntimeError, match="não estão disponíveis"):
        meetings.rodar("", palheta.configuracao)


# -- a tarefa e o vigia -------------------------------------------------------------


def test_a_tarefa_roda_meetings_agendada_no_horario(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, '[granola]\nhorario = "18:30"\n'))
    espiao = ExecutorEspiao()

    nome = automacao.agendar_reunioes(configuracao, executar=espiao)

    [comando] = espiao.registros()
    assert nome == "Whis-Reunioes"
    assert parametro(comando, "-Nome") == "Whis-Reunioes"
    assert parametro(comando, "-Gatilhos") == "Daily=18:30"
    assert parametro(comando, "-Argumentos").startswith("-m whis meetings --agendada --config ")


def test_desagendar_e_consultar_as_reunioes():
    assert automacao.desagendar_reunioes(executar=ExecutorEspiao(codigo=1)) is False
    assert automacao.reunioes_agendada(executar=ExecutorEspiao(codigo=0)) is True


def test_o_vigia_so_olha_as_reunioes_se_a_tarefa_existe():
    sem = ExecutorEspiao(**{"'Whis-Noticias'": 1, "'Whis-Reunioes'": 1})
    com = ExecutorEspiao(**{"'Whis-Noticias'": 1})

    assert automacao.tarefas_vigiadas(executar=sem) == ["Whis-Daily"]
    assert automacao.tarefas_vigiadas(executar=com) == ["Whis-Daily", "Whis-Reunioes"]


@pytest.fixture
def espiar_automacao(monkeypatch):
    chamadas: list[tuple[str, object]] = []
    estado = {"vigia": True}
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(
        automacao, "agendar_reunioes", lambda configuracao: chamadas.append(("meetings", configuracao.granola_horario))
    )
    monkeypatch.setattr(automacao, "desagendar_reunioes", lambda: chamadas.append(("-meetings", None)) or True)
    monkeypatch.setattr(
        automacao,
        "agendar_vigia",
        lambda configuracao: chamadas.append(("vigia", None)) or ["Whis-Daily", "Whis-Reunioes"],
    )
    monkeypatch.setattr(automacao, "vigia_agendado", lambda: estado["vigia"])
    chamadas_e_estado = (chamadas, estado)
    return chamadas_e_estado


def test_windows_meetings_agenda_e_reagenda_o_vigia(tmp_path: Path, espiar_automacao, capsys):
    chamadas, _ = espiar_automacao
    arquivo = escrever(tmp_path, '[granola]\nhorario = "18:30"\n')

    assert cli.main(["windows", "--meetings", "--config", str(arquivo)]) == 0

    saida = capsys.readouterr().out
    assert chamadas == [("meetings", "18:30"), ("vigia", None)]
    assert "Reuniões agendadas como 'Whis-Reunioes': todo dia às 18:30" in saida
    assert "Whis-Reunioes" in saida


def test_windows_meetings_sem_vigia_diz_como(tmp_path: Path, espiar_automacao, capsys):
    chamadas, estado = espiar_automacao
    estado["vigia"] = False

    cli.main(["windows", "--meetings", "--config", str(escrever(tmp_path, ""))])

    assert chamadas == [("meetings", "19:00")]
    assert "whis windows --daily" in capsys.readouterr().out


def test_windows_remover_meetings_desagenda_e_tira_do_vigia(tmp_path: Path, espiar_automacao, capsys):
    chamadas, _ = espiar_automacao

    assert cli.main(["windows", "--remover", "--meetings", "--config", str(escrever(tmp_path, ""))]) == 0

    assert chamadas == [("-meetings", None), ("vigia", None)]
    assert "'Whis-Reunioes' removida" in capsys.readouterr().out


def test_windows_meetings_monta_o_comando_de_verdade(tmp_path: Path, monkeypatch):
    espiao = ExecutorEspiao(**{"'Whis-Noticias'": 1})
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    for nome in ("agendar_reunioes", "agendar_vigia"):
        monkeypatch.setattr(automacao, nome, partial(getattr(automacao, nome), executar=espiao))
    monkeypatch.setattr(automacao, "vigia_agendado", partial(automacao.vigia_agendado, executar=espiao))
    arquivo = escrever(tmp_path, "")

    assert cli.main(["windows", "--meetings", "--config", str(arquivo)]) == 0

    tarefa, vigia = espiao.registros()
    assert parametro(tarefa, "-Argumentos") == f'-m whis meetings --agendada --config "{arquivo}"'
    assert parametro(vigia, "-Argumentos").endswith("-Tarefas Whis-Daily,Whis-Reunioes")
