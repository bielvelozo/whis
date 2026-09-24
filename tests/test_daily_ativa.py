"""Desligar a daily: `[daily].ativa = false`.

A tarefa `Whis-Daily` continua no Agendador e sai com 0 sem escrever nada —
o vigia não reclama e religar é só marcar a caixa de novo — e a palheta
esconde `daily`. `whis daily` no terminal não olha a chave.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whis.__main__ import main
from whis.configuracao import (
    VARIAVEL_DE_AMBIENTE,
    Configuracao,
    ConfiguracaoInvalida,
    carregar,
)
from whis.painel import CAMPOS, montar_configuracao, texto_do_valor, textos_de, valor_do_texto

ATIVA = next(campo for campo in CAMPOS if campo.caminho == "[daily].ativa")


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\ngravacoes = "G"\n{corpo}', encoding="utf-8")
    return arquivo


# -- a chave ----------------------------------------------------------------------


def test_sem_a_chave_a_daily_continua_ativa(tmp_path: Path):
    assert carregar(escrever(tmp_path, "")).daily_ativa is True


def test_false_desliga(tmp_path: Path):
    assert carregar(escrever(tmp_path, "[daily]\nativa = false\n")).daily_ativa is False


@pytest.mark.parametrize("valor", ['"false"', "0", '"nao"'])
def test_o_que_nao_e_booleano_e_recusado(tmp_path: Path, valor: str):
    with pytest.raises(ConfiguracaoInvalida, match=r"\[daily].ativa.*true ou false"):
        carregar(escrever(tmp_path, f"[daily]\nativa = {valor}\n"))


# -- o painel ---------------------------------------------------------------------


def test_o_painel_mostra_e_le_true_e_false():
    ligada = Configuracao(vault=Path("V"), gravacoes=Path("G"))
    desligada = Configuracao(vault=Path("V"), gravacoes=Path("G"), daily_ativa=False)

    assert texto_do_valor(ligada, ATIVA) == "true"
    assert texto_do_valor(desligada, ATIVA) == "false"
    assert valor_do_texto(ATIVA, "false") is False
    assert valor_do_texto(ATIVA, " True ") is True


def test_desmarcar_no_painel_vira_configuracao_desligada(tmp_path: Path):
    textos = textos_de(Configuracao(vault=Path("V"), gravacoes=Path("G")))
    textos[ATIVA] = "false"

    nova = montar_configuracao(textos, origem=tmp_path / "config.toml")

    assert nova.daily_ativa is False


# -- o comando ----------------------------------------------------------------------


@pytest.fixture
def config_da_daily(tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, monkeypatch):
    def montar(*, ativa: bool) -> Path:
        arquivo = tmp_path / "config-da-daily.toml"
        arquivo.write_text(
            f'vault = "{caminho_do_vault.as_posix()}"\n'
            f'gravacoes = "{caminho_das_gravacoes.as_posix()}"\n'
            f"[daily]\nativa = {'true' if ativa else 'false'}\n",
            encoding="utf-8",
        )
        monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
        return arquivo

    return montar


def test_a_tarefa_agendada_com_a_daily_desligada_sai_sem_escrever(
    config_da_daily, caminho_do_vault: Path
):
    config_da_daily(ativa=False)

    codigo = main(["daily", "--fakes", "--agendada"])

    assert codigo == 0
    assert not (caminho_do_vault / "daily").exists()


def test_a_tarefa_agendada_com_a_daily_ligada_gera(config_da_daily, caminho_do_vault: Path):
    config_da_daily(ativa=True)

    main(["daily", "--fakes", "--agendada"])

    assert (caminho_do_vault / "daily" / "atual.md").is_file()


def test_whis_daily_no_terminal_gera_mesmo_com_a_daily_desligada(config_da_daily, caminho_do_vault: Path):
    config_da_daily(ativa=False)

    main(["daily", "--fakes"])

    assert (caminho_do_vault / "daily" / "atual.md").is_file()


# -- a palheta --------------------------------------------------------------------


def _palheta(configuracao, avisos: list):
    from whis.fakes import BuscaFake, DailyFake, fontes_de_exemplo_da_daily
    from whis.palheta import Palheta, comandos_padrao

    comandos = comandos_padrao(
        fontes_da_daily=lambda _c: fontes_de_exemplo_da_daily(),
        roteiro_da_daily=lambda _c: DailyFake(),
        busca=lambda _c: BuscaFake(),
        lancar=lambda _uri: None,
    )

    def avisar(titulo, texto, *, botao=None, executar=None):
        avisos.append((titulo, texto))
        return True

    return Palheta(comandos, configuracao, avisar=avisar, iniciar_thread=lambda alvo: alvo())


def test_com_a_daily_desligada_a_palheta_esconde_e_nao_entende_daily(
    config_da_daily, caminho_do_vault: Path
):
    avisos: list = []
    palheta = _palheta(carregar(config_da_daily(ativa=False)), avisos)

    assert "daily" not in [comando.nome for comando in palheta.acoes()]
    palheta.despachar("daily")

    assert avisos[-1][0] == "Não entendi" and "daily" not in avisos[-1][1].split("Comandos:")[1]
    assert not (caminho_do_vault / "daily" / "atual.md").exists()


def test_religar_pelo_painel_devolve_o_comando_sem_reconstruir_a_palheta(config_da_daily):
    from dataclasses import replace

    palheta = _palheta(carregar(config_da_daily(ativa=False)), [])

    palheta.configuracao = replace(palheta.configuracao, daily_ativa=True)

    assert [comando.nome for comando in palheta.acoes()][:2] == ["open", "daily"]
