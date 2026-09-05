"""Comportamento da costura da busca: `responder(pergunta, conversa) → Resposta`.

A busca entra como fake pela porta, e o fake guarda o que recebeu: é assim que
se prova o que **não** foi enviado ao Claude — a pergunta vazia, o fio
expirado e, pelas ferramentas que o fake tem na mão, a pasta privada.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.busca import (
    CONTEUDO_PRIVADO,
    NOTA_PRIVADA,
    NOTA_PUBLICA,
    PASTA_PRIVADA,
    configuracao_da_busca,
    habitar_vault,
)
from second_brain.busca import Citacao, ErroDeBusca, PortaBusca, Resposta
from second_brain.conversa import AGENTE, USUARIO, Conversa
from second_brain.fakes import RESPOSTA_PADRAO, BuscaFake
from second_brain.ferramentas import Ferramentas, ForaDaFronteira
from second_brain.pergunta import SEM_RESPOSTA, PerguntaVazia, responder

FUSO = timezone(timedelta(hours=-3))
MANHA = datetime(2026, 9, 4, 9, 0, tzinfo=FUSO)
PERGUNTA = "o que ficou decidido sobre a retenção de 180 dias?"


def horas(quantidade: float) -> datetime:
    return MANHA + timedelta(hours=quantidade)


@pytest.fixture
def configuracao_com_pasta_privada(tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path):
    habitar_vault(caminho_do_vault)
    return configuracao_da_busca(
        tmp_path, caminho_do_vault, caminho_das_gravacoes, pastas_privadas=(PASTA_PRIVADA,)
    )


@pytest.fixture
def busca() -> BuscaFake:
    return BuscaFake()


@pytest.fixture
def perguntar(configuracao_com_pasta_privada, busca: BuscaFake):
    """Roda a costura com a busca fake: `perguntar(pergunta, conversa=..., agora=...)`."""

    def executar(pergunta: str = PERGUNTA, **extras) -> Resposta:
        return responder(
            pergunta,
            configuracao=extras.pop("configuracao", configuracao_com_pasta_privada),
            busca=extras.pop("busca", busca),
            agora=extras.pop("agora", MANHA),
            **extras,
        )

    return executar


# -- Caminho feliz ----------------------------------------------------------


def test_responder_devolve_a_resposta_da_busca_com_as_citacoes(perguntar):
    resposta = perguntar()

    assert resposta == RESPOSTA_PADRAO
    assert resposta.achou
    assert resposta.citacoes[0].origem == "reunioes/2026-09-03-1403-reuniao.md"


def test_a_busca_recebe_a_pergunta_como_veio(perguntar, busca: BuscaFake):
    perguntar("  e quem levantou isso?  ")

    assert busca.perguntas_recebidas == ["  e quem levantou isso?  "]


def test_a_busca_recebe_as_ferramentas_do_vault_configurado(perguntar, busca: BuscaFake):
    perguntar()

    assert isinstance(busca.ferramentas_recebidas, Ferramentas)
    assert NOTA_PUBLICA in [
        achado.caminho for achado in busca.ferramentas_recebidas.buscar_no_vault("retenção")
    ]


def test_busca_fake_satisfaz_a_porta():
    assert isinstance(BuscaFake(), PortaBusca)


# -- A pergunta vazia -------------------------------------------------------


@pytest.mark.parametrize("vazia", ["", "   ", "\n\t"])
def test_pergunta_vazia_e_recusada_em_portugues_sem_chamar_a_busca(
    perguntar, busca: BuscaFake, vazia: str
):
    with pytest.raises(PerguntaVazia) as erro:
        perguntar(vazia)

    assert "vazia" in str(erro.value)
    assert busca.perguntas_recebidas == []


# -- A pasta privada não chega ao fake --------------------------------------


def test_o_arquivo_privado_nao_chega_a_quem_responde(perguntar, busca: BuscaFake):
    """O fake tem em mãos exatamente o que o Claude teria — e nada disso alcança a pasta privada."""
    perguntar("o que a terapia disse sobre a retenção?")

    ferramentas = busca.ferramentas_recebidas
    assert ferramentas is not None
    encontrados = ferramentas.buscar_no_vault("retenção 180")
    assert encontrados, "a busca precisa achar as notas públicas para a prova valer"
    assert not [achado for achado in encontrados if achado.caminho.startswith(PASTA_PRIVADA + "/")]
    assert not any(CONTEUDO_PRIVADO in achado.trecho for achado in encontrados)
    with pytest.raises(ForaDaFronteira) as erro:
        ferramentas.ler_nota(NOTA_PRIVADA)
    assert "privad" not in str(erro.value).lower()
    assert not any(
        entrada.startswith(PASTA_PRIVADA + "/") for entrada in ferramentas.listar("notas")
    )


def test_cada_pergunta_ganha_ferramentas_novas(perguntar, busca: BuscaFake):
    perguntar()
    primeiras = busca.ferramentas_recebidas
    perguntar("e quem levantou isso?")

    assert busca.ferramentas_recebidas is not primeiras


# -- O fio da conversa ------------------------------------------------------


def test_sem_conversa_a_busca_recebe_historico_vazio(perguntar, busca: BuscaFake):
    perguntar()

    assert busca.historico_recebido == ()


def test_a_pergunta_e_a_resposta_entram_no_fio(perguntar):
    fio = Conversa()

    perguntar(conversa=fio)

    assert [(turno.quem, turno.texto) for turno in fio.historico()] == [
        (USUARIO, PERGUNTA),
        (AGENTE, RESPOSTA_PADRAO.texto),
    ]
    assert all(turno.momento == MANHA for turno in fio.historico())


def test_a_pergunta_de_acompanhamento_recebe_o_fio_sem_repetir_o_assunto(
    perguntar, busca: BuscaFake
):
    fio = Conversa()
    perguntar(conversa=fio, agora=MANHA)

    perguntar("e quem levantou isso?", conversa=fio, agora=horas(6))

    assert [(turno.quem, turno.texto) for turno in busca.historico_recebido] == [
        (USUARIO, PERGUNTA),
        (AGENTE, RESPOSTA_PADRAO.texto),
    ]
    assert len(fio.historico()) == 4


def test_o_historico_enviado_nao_inclui_a_pergunta_atual(perguntar, busca: BuscaFake):
    fio = Conversa()

    perguntar(conversa=fio)

    assert busca.historico_recebido == ()


def test_o_fio_expirado_nao_chega_a_busca(perguntar, busca: BuscaFake):
    """Uma conversa parada há 25 horas não contamina a pergunta nova."""
    fio = Conversa()
    perguntar(conversa=fio, agora=MANHA)

    perguntar("pergunta de outro assunto", conversa=fio, agora=horas(25))

    assert busca.historico_recebido == ()
    assert [turno.texto for turno in fio.historico()] == [
        "pergunta de outro assunto",
        RESPOSTA_PADRAO.texto,
    ]


def test_o_fio_dentro_da_janela_chega_a_busca(perguntar, busca: BuscaFake):
    fio = Conversa()
    perguntar(conversa=fio, agora=MANHA)

    perguntar("e quem levantou isso?", conversa=fio, agora=horas(23))

    assert len(busca.historico_recebido) == 2


# -- "Não achei" e erro -----------------------------------------------------


def test_nao_achei_e_resposta_valida_e_entra_no_fio(perguntar):
    fio = Conversa()
    nao_achou = Resposta(texto="", achou=False)

    resposta = perguntar(busca=BuscaFake(nao_achou), conversa=fio)

    assert resposta is nao_achou
    assert fio.historico()[-1].texto == SEM_RESPOSTA


def test_erro_de_busca_sobe_e_nao_entra_no_fio(perguntar):
    fio = Conversa()

    with pytest.raises(ErroDeBusca, match="sem rede"):
        perguntar(busca=BuscaFake(erro=ErroDeBusca("sem rede")), conversa=fio)

    assert fio.vazia()


# -- O log ------------------------------------------------------------------


def test_o_log_registra_a_pergunta_as_citacoes_e_o_custo(perguntar, caplog):
    resposta = Resposta(
        texto="x",
        citacoes=(Citacao("daily/2026-09-04.md"), Citacao("linear:FN-1610")),
        custo_usd=0.0123,
    )

    with caplog.at_level(logging.INFO, logger="second_brain.pergunta"):
        perguntar(busca=BuscaFake(resposta))

    mensagens = "\n".join(registro.message for registro in caplog.records)
    assert "retenção de 180 dias" in mensagens
    assert "2 citações" in mensagens
    assert "US$ 0.0123" in mensagens
    assert "assinatura não cobra por token" in mensagens


def test_o_log_diz_quando_nao_achou_e_quando_o_custo_nao_veio(perguntar, caplog):
    with caplog.at_level(logging.INFO, logger="second_brain.pergunta"):
        perguntar(busca=BuscaFake(Resposta(texto="", achou=False)))

    mensagens = "\n".join(registro.message for registro in caplog.records)
    assert "não achou" in mensagens
    assert "não informado" in mensagens
