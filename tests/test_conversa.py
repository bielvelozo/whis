"""O fio de 24 horas: expira por silêncio, mora ao lado do `config.toml`.

Tudo com relógio injetado — ninguém espera 24 horas para rodar a suíte. Os
testes leem o arquivo como o atendente leria na próxima mensagem: abrindo o fio
com `agora`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault
from whis import vault as modulo_vault
from whis.configuracao import Configuracao
from whis.conversa import (
    AGENTE,
    NOME_DO_ARQUIVO,
    USUARIO,
    Conversa,
    Conversas,
    Turno,
)

FUSO = timezone(timedelta(hours=-3))
MANHA = datetime(2026, 9, 4, 9, 0, tzinfo=FUSO)
DM = "D0123456789"


def horas(quantidade: float) -> datetime:
    return MANHA + timedelta(hours=quantidade)


@pytest.fixture
def conversas(tmp_path: Path) -> Conversas:
    return Conversas(tmp_path / NOME_DO_ARQUIVO)


def com_uma_pergunta(conversas: Conversas, *, chave: str = DM, momento: datetime = MANHA) -> None:
    fio = conversas.abrir(chave, agora=momento)
    fio.acrescentar(USUARIO, "o que ficou decidido sobre a retenção?", agora=momento)
    fio.acrescentar(AGENTE, "180 dias, na reunião de ontem.", agora=momento)
    conversas.guardar(chave, fio)


# -- A expiração por silêncio -----------------------------------------------


def test_de_manha_para_a_tarde_o_fio_continua(conversas: Conversas):
    com_uma_pergunta(conversas)

    fio = conversas.abrir(DM, agora=horas(7))

    assert [turno.quem for turno in fio.historico()] == [USUARIO, AGENTE]


def test_um_minuto_antes_de_24h_o_fio_ainda_continua(conversas: Conversas):
    com_uma_pergunta(conversas)

    assert not conversas.abrir(DM, agora=horas(24) - timedelta(minutes=1)).vazia()


@pytest.mark.parametrize("silencio", [24, 25, 24 * 7])
def test_depois_de_24h_de_silencio_o_fio_comeca_limpo(conversas: Conversas, silencio: int):
    com_uma_pergunta(conversas)

    assert conversas.abrir(DM, agora=horas(silencio)).vazia()


def test_o_silencio_conta_do_ultimo_turno_nao_do_primeiro(conversas: Conversas):
    """Uma conversa que seguiu à noite continua no dia seguinte."""
    com_uma_pergunta(conversas)
    fio = conversas.abrir(DM, agora=horas(20))
    fio.acrescentar(USUARIO, "e quem levantou isso?", agora=horas(20))
    conversas.guardar(DM, fio)

    de_novo = conversas.abrir(DM, agora=horas(30))

    assert len(de_novo.historico()) == 3


def test_o_fio_expira_pela_meia_noite_de_nada(conversas: Conversas):
    """Meia-noite não é fronteira: 23h de um dia e 9h do seguinte são o mesmo fio."""
    noite = datetime(2026, 9, 4, 23, 0, tzinfo=FUSO)
    com_uma_pergunta(conversas, momento=noite)

    assert not conversas.abrir(DM, agora=datetime(2026, 9, 5, 9, 0, tzinfo=FUSO)).vazia()


def test_acrescentar_depois_do_silencio_esquece_o_fio_antigo():
    fio = Conversa()
    fio.acrescentar(USUARIO, "pergunta velha", agora=MANHA)

    fio.acrescentar(USUARIO, "pergunta nova", agora=horas(25))

    assert [turno.texto for turno in fio.historico()] == ["pergunta nova"]


def test_expirar_em_memoria_diz_se_esqueceu():
    fio = Conversa()
    fio.acrescentar(USUARIO, "pergunta", agora=MANHA)

    assert fio.expirar(horas(1)) is False
    assert fio.expirar(horas(24)) is True
    assert fio.vazia()


def test_fio_vazio_nunca_esta_expirado():
    assert Conversa().expirada(horas(1000)) is False


def test_momento_sem_fuso_ganha_o_fuso_local():
    fio = Conversa()
    fio.acrescentar(USUARIO, "pergunta", agora=datetime(2026, 9, 4, 9, 0))

    assert fio.historico()[0].momento.tzinfo is not None
    assert fio.expirada(datetime(2026, 9, 5, 9, 0)) is True
    assert fio.expirada(datetime(2026, 9, 5, 8, 59)) is False


# -- A persistência ---------------------------------------------------------


def test_guardar_e_abrir_preservam_texto_quem_e_momento(conversas: Conversas):
    com_uma_pergunta(conversas)

    fio = conversas.abrir(DM, agora=horas(1))

    assert fio.historico() == (
        Turno(USUARIO, "o que ficou decidido sobre a retenção?", MANHA),
        Turno(AGENTE, "180 dias, na reunião de ontem.", MANHA),
    )


def test_fios_de_chaves_diferentes_nao_se_misturam(conversas: Conversas):
    com_uma_pergunta(conversas, chave="D-celular")
    com_uma_pergunta(conversas, chave="terminal")

    assert len(conversas.abrir("D-celular", agora=horas(1)).historico()) == 2
    assert conversas.abrir("D-outra", agora=horas(1)).vazia()


def test_guardar_um_fio_vazio_remove_a_chave_do_arquivo(conversas: Conversas):
    com_uma_pergunta(conversas)

    conversas.guardar(DM, Conversa())

    assert DM not in conversas.arquivo.read_text(encoding="utf-8")


def test_guardar_limpa_os_outros_fios_ja_expirados(conversas: Conversas):
    com_uma_pergunta(conversas, chave="velha", momento=MANHA)

    com_uma_pergunta(conversas, chave="nova", momento=horas(48))

    assert "velha" not in conversas.arquivo.read_text(encoding="utf-8")
    assert not conversas.abrir("nova", agora=horas(49)).vazia()


def test_sem_arquivo_o_fio_e_vazio(conversas: Conversas):
    assert conversas.abrir(DM, agora=MANHA).vazia()
    assert not conversas.arquivo.exists()


def test_a_gravacao_nao_deixa_temporario_para_tras(conversas: Conversas):
    com_uma_pergunta(conversas)

    assert [arquivo.name for arquivo in conversas.arquivo.parent.iterdir()] == [NOME_DO_ARQUIVO]


def test_o_arquivo_mora_ao_lado_da_configuracao_e_nao_no_vault(configuracao: Configuracao):
    modulo_vault.preparar(configuracao.vault)
    conversas = Conversas.de_configuracao(configuracao)

    com_uma_pergunta(conversas)

    assert conversas.arquivo == configuracao.origem.parent / NOME_DO_ARQUIVO
    assert conversas.arquivo.is_file()
    assert NOME_DO_ARQUIVO not in {
        Path(arquivo).name for arquivo in arquivos_do_vault(configuracao.vault)
    }


# -- Arquivo ilegível não derruba nada --------------------------------------


@pytest.mark.parametrize(
    "conteudo",
    [
        "{ isto não é json",
        "",
        "[]",
        '{"versao": 1}',
        '{"versao": 1, "conversas": [1, 2, 3]}',
        '{"versao": 1, "conversas": {"D0123456789": [{"quem": "usuario"}]}}',
        '{"versao": 1, "conversas": {"D0123456789": [{"quem": "usuario", "texto": "x", "momento": "ontem"}]}}',
    ],
)
def test_arquivo_ilegivel_vale_como_conversa_vazia(
    conversas: Conversas, conteudo: str, caplog: pytest.LogCaptureFixture
):
    conversas.arquivo.write_text(conteudo, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="whis.conversa"):
        fio = conversas.abrir(DM, agora=MANHA)

    assert fio.vazia()
    assert any("ilegível" in registro.message for registro in caplog.records)


def test_depois_de_um_arquivo_ilegivel_a_conversa_volta_a_ser_guardada(conversas: Conversas):
    conversas.arquivo.write_text("{ isto não é json", encoding="utf-8")

    com_uma_pergunta(conversas)

    assert len(conversas.abrir(DM, agora=horas(1)).historico()) == 2
