"""O subcomando `whis perguntar` — a costura da busca, pela linha de comando.

Existe para teste e diagnóstico: o caminho principal é a DM do Slack. O que
importa aqui é o que sobra depois que o terminal fechou — a saída, o código, o
fio em `conversas.json` ao lado da configuração e o rastro no log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.busca import PASTA_PRIVADA, configuracao_da_busca, habitar_vault
from whis import __main__ as cli
from whis.__main__ import FIO_DO_TERMINAL, SAIDA_COMPLETA, SAIDA_NAO_NASCEU, SAIDA_PARCIAL, main
from whis.busca import ErroDeBusca, Resposta
from whis.configuracao import VARIAVEL_DE_AMBIENTE
from whis.conversa import NOME_DO_ARQUIVO
from whis.fakes import RESPOSTA_PADRAO, BuscaFake

PERGUNTA = "o que ficou decidido sobre a retenção de 180 dias?"


@pytest.fixture
def configuracao(tmp_path: Path, caminho_do_vault: Path, monkeypatch):
    habitar_vault(caminho_do_vault)
    configuracao = configuracao_da_busca(
        tmp_path, caminho_do_vault, pastas_privadas=(PASTA_PRIVADA,)
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(configuracao.origem))
    return configuracao


def fios(configuracao) -> dict:
    arquivo = configuracao.origem.parent / NOME_DO_ARQUIVO
    return json.loads(arquivo.read_text(encoding="utf-8"))["conversas"]


def test_perguntar_imprime_a_resposta_e_as_fontes(configuracao, capsys: pytest.CaptureFixture):
    codigo = main(["perguntar", "--fakes", PERGUNTA])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_COMPLETA
    assert RESPOSTA_PADRAO.texto in saida
    assert "Fontes:" in saida
    assert "reunioes/2026-09-03-1403-reuniao.md — retenção de 180 dias" in saida


def test_duas_perguntas_seguidas_continuam_o_fio_do_terminal(configuracao):
    main(["perguntar", "--fakes", PERGUNTA])
    main(["perguntar", "--fakes", "e quem levantou isso?"])

    turnos = fios(configuracao)[FIO_DO_TERMINAL]
    assert [turno["texto"] for turno in turnos if turno["quem"] == "usuario"] == [
        PERGUNTA,
        "e quem levantou isso?",
    ]
    assert len(turnos) == 4


def test_o_fio_chega_a_busca_na_segunda_pergunta(configuracao, monkeypatch):
    busca = BuscaFake()
    monkeypatch.setattr(cli, "montar_busca", lambda configuracao, *, fakes=False: busca)
    main(["perguntar", PERGUNTA])

    main(["perguntar", "e quem levantou isso?"])

    assert [turno.texto for turno in busca.historico_recebido] == [PERGUNTA, RESPOSTA_PADRAO.texto]


def test_sem_fio_nao_le_nem_grava_a_conversa(configuracao):
    main(["perguntar", "--fakes", "--sem-fio", PERGUNTA])

    assert not (configuracao.origem.parent / NOME_DO_ARQUIVO).exists()


def test_o_fio_mora_ao_lado_da_configuracao_e_nao_no_vault(configuracao):
    main(["perguntar", "--fakes", PERGUNTA])

    assert (configuracao.origem.parent / NOME_DO_ARQUIVO).is_file()
    assert not list(Path(configuracao.vault).rglob(NOME_DO_ARQUIVO))


def test_nao_achou_sai_parcial_e_diz_isso(configuracao, monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "montar_busca",
        lambda configuracao, *, fakes=False: BuscaFake(Resposta(texto="", achou=False)),
    )

    codigo = main(["perguntar", PERGUNTA])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_PARCIAL
    assert "Não achei." in saida
    assert "não achou" in saida


def test_erro_de_busca_sai_um_com_o_motivo_no_log(configuracao, monkeypatch, caplog):
    monkeypatch.setattr(
        cli,
        "montar_busca",
        lambda configuracao, *, fakes=False: BuscaFake(erro=ErroDeBusca("sem conta logada")),
    )

    codigo = main(["perguntar", PERGUNTA])

    assert codigo == SAIDA_NAO_NASCEU
    assert "sem conta logada" in caplog.text
    assert "sem conta logada" in (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")


def test_pergunta_vazia_sai_um_sem_chamar_a_busca(configuracao, monkeypatch, caplog):
    busca = BuscaFake()
    monkeypatch.setattr(cli, "montar_busca", lambda configuracao, *, fakes=False: busca)

    codigo = main(["perguntar", "   "])

    assert codigo == SAIDA_NAO_NASCEU
    assert "vazia" in caplog.text
    assert busca.perguntas_recebidas == []


def test_o_log_guarda_a_pergunta_e_o_custo(configuracao):
    main(["perguntar", "--fakes", PERGUNTA])

    log = (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")
    assert "retenção de 180 dias" in log
    assert "assinatura não cobra por token" in log


def test_fakes_avisa_que_nada_vai_ao_claude(configuracao, caplog):
    main(["perguntar", "--fakes", PERGUNTA])

    assert "FAKE" in caplog.text
