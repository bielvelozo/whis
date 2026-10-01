"""O toast troca a falha genérica pelo conserto quando o login do Claude venceu."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import login_do_claude
from whis.daily import JanelaDaDaily, ResultadoDaDaily
from whis.jornal import Edicao, ResultadoDoJornal
from whis.palheta import resultado_da_daily, resultado_do_jornal

BRT = timezone(timedelta(hours=-3))

VENCIDO_NA_DAILY = (
    "Falha ao falar com o Claude (ResultError): Claude Code returned an error result: "
    "Failed to authenticate: OAuth session expired and could not be refreshed (exit code: 1)"
)
VENCIDO_NA_PUBLICACAO = (
    "Falha ao falar com o Claude na publicação (ResultError): Claude Code returned an error "
    "result: Failed to authenticate: OAuth session expired and could not be refreshed (exit code: 1)"
)


@pytest.mark.parametrize(
    "texto",
    [VENCIDO_NA_DAILY, VENCIDO_NA_PUBLICACAO, "Invalid API key · Please run /login"],
)
def test_reconhece_o_login_vencido_na_mensagem_do_cli(texto: str):
    assert login_do_claude.vencido(texto)


@pytest.mark.parametrize(
    "texto",
    [
        None,
        "",
        "O Claude não terminou a escolha em 300s — cancelada.",
        "Deepgram respondeu HTTP 504 ao transcrever microfone.wav",
    ],
)
def test_outras_falhas_nao_sao_login_vencido(texto: str | None):
    assert not login_do_claude.vencido(texto)


def daily_com(falha: str | None) -> ResultadoDaDaily:
    agora = datetime(2026, 9, 29, 13, 55, tzinfo=BRT)
    return ResultadoDaDaily(
        janela=JanelaDaDaily(data=date(2026, 9, 29), desde=agora, ate=agora),
        nota=Path("daily/2026-09-29.md"),
        eventos=(),
        excluidos=0,
        fontes_lidas=("git",),
        fontes_com_falha=(),
        reunioes=(),
        roteiro=None,
        nota_viva=Path("daily/atual.md"),
        secoes=(),
        mudancas=None,
        falha_do_roteiro=falha,
    )


def jornal_sem_pagina(falha: str) -> ResultadoDoJornal:
    edicao = Edicao(data=date(2026, 9, 29), gerado_em=datetime(2026, 9, 29, 8, 20, tzinfo=BRT), secoes=())
    return ResultadoDoJornal(
        edicao=edicao, nota=None, pagina=None, url=None, parcial=True, falha_da_publicacao=falha
    )


def test_a_daily_sem_roteiro_por_login_vencido_pede_o_login():
    resultado = resultado_da_daily(daily_com(VENCIDO_NA_DAILY))

    assert resultado.titulo == "O login do Claude venceu"
    assert resultado.texto.startswith("Rode 'claude auth login' num terminal.")
    assert "nota viva ficou como estava" in resultado.texto
    assert resultado.nota == "daily/atual.md"


def test_a_daily_sem_roteiro_por_outro_motivo_continua_como_era():
    resultado = resultado_da_daily(daily_com("o Claude caiu"))

    assert resultado.titulo == "A daily está pronta"
    assert resultado.texto == "A nota nasceu parcial: o Claude caiu. A nota viva ficou como estava."


def test_o_jornal_sem_pagina_por_login_vencido_pede_o_login_e_abre_a_nota():
    resultado = resultado_do_jornal(jornal_sem_pagina(VENCIDO_NA_PUBLICACAO))

    assert resultado.titulo == "O login do Claude venceu"
    assert resultado.texto.startswith("Rode 'claude auth login' num terminal.")
    assert "não foi publicado" in resultado.texto
    assert resultado.nota == "noticias/2026-09-29.md"
    assert resultado.link is None


def test_o_jornal_sem_pagina_por_outro_motivo_continua_como_era():
    resultado = resultado_do_jornal(jornal_sem_pagina("HTTP 500 do Artifact"))

    assert resultado.titulo == "O jornal não foi publicado"
    assert resultado.texto.endswith("a página não saiu: HTTP 500 do Artifact")
