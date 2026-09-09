"""O subcomando `whis atender` — a casca da CLI sobre o atendente.

A DM entra pela fábrica `montar_dm`, trocada aqui por `DMFake`; a busca entra
por `--fakes`. O que se prova é o que sobra: o código de saída, a resposta que
saiu na DM e o rastro em `bandeja.log`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.busca import configuracao_da_busca, habitar_vault
from whis import __main__ as cli
from whis.__main__ import main
from whis.atendente import Mensagem
from whis.configuracao import VARIAVEL_DE_AMBIENTE
from whis.fakes import RESPOSTA_PADRAO, DMFake


@pytest.fixture
def configuracao(tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, monkeypatch):
    habitar_vault(caminho_do_vault)
    configuracao = configuracao_da_busca(tmp_path, caminho_do_vault, caminho_das_gravacoes)
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(configuracao.origem))
    return configuracao


def log_de(configuracao) -> str:
    return (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")


def test_atender_fakes_responde_na_dm_e_sai_zero_no_ctrl_c(configuracao, monkeypatch):
    dm = DMFake([Mensagem(canal="D0GABRIEL", usuario="U0GABRIEL", texto="retenção?", ts="1.0")])
    monkeypatch.setattr(cli, "montar_dm", lambda configuracao: dm)

    codigo = main(["atender", "--fakes"])

    assert codigo == 0
    assert RESPOSTA_PADRAO.texto in dm.respostas[0][1]
    assert "Atendente no ar" in log_de(configuracao)
    assert "FAKE" in log_de(configuracao)


def test_atender_sem_os_tokens_sai_um_dizendo_o_que_falta(configuracao, caplog):
    codigo = main(["atender", "--fakes"])

    assert codigo == 1
    assert "[slack].bot_token" in caplog.text
    assert "[slack].app_token" in caplog.text


def test_o_help_do_atender_diz_que_e_socket_mode_sem_porta_aberta(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["atender", "--help"])

    assert saida.value.code == 0
    assert "Socket Mode" in capsys.readouterr().out
