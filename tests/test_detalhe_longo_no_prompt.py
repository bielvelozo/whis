"""Um comentário de milhares de caracteres não vai inteiro ao Claude.

A primeira daily de segunda-feira real (2026-09-08) cobriu quatro dias com 878
eventos do Linear, um comentário de 7.500 caracteres entre eles, e estourou o
teto de uma chamada: a nota nasceu sem roteiro. O roteiro precisa do gist de
cada evento, não do comentário inteiro; a nota continua guardando tudo.
"""

from __future__ import annotations

from datetime import date, datetime, time

from second_brain.fontes import Evento
from second_brain.resumo_dia_claude import (
    DETALHE_MAXIMO,
    montar_pergunta,
    montar_pergunta_da_daily,
)


def evento(detalhe: str) -> Evento:
    return Evento(
        fonte="linear",
        momento=datetime.combine(date(2026, 9, 8), time(13, 12)).astimezone(),
        titulo="FN-1721 Levantar a tabela de strings — comentário de Gabriel",
        detalhe=detalhe,
        referencia="Plataforma",
    )


def test_detalhe_longo_vai_cortado_com_a_marca_do_corte():
    longo = "linha importante\n" + ("blá " * 3000)

    for montar in (montar_pergunta, montar_pergunta_da_daily):
        pergunta = montar((evento(longo),), ())

        assert "linha importante" in pergunta
        assert len(pergunta) < DETALHE_MAXIMO + 400
        assert "…" in pergunta


def test_detalhe_curto_vai_inteiro():
    curto = "Subiu em produção; falta acompanhar o gráfico de erros."

    pergunta = montar_pergunta_da_daily((evento(curto),), ())

    assert curto in pergunta
    assert "…" not in pergunta


def test_o_corte_e_por_evento_e_nao_pelo_prompt_inteiro():
    eventos = tuple(evento(f"evento {numero} " + "x" * DETALHE_MAXIMO) for numero in range(5))

    pergunta = montar_pergunta_da_daily(eventos, ())

    for numero in range(5):
        assert f"evento {numero}" in pergunta
