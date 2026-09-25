"""A efeméride da Wikipédia, sem rede.

Amostras reais baixadas em 2026-09-25 e cortadas: `events` de 29/06 (três
acontecimentos que não são futebol, depois as Copas de 1986 e 1958) e o `all`
de 25/09, cujos `events` não falam de futebol mas cujos `births` e `deaths`
trazem futebolistas — o caso que a primeira edição do protótipo errou.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from whis.efemeride import UA_WIKIPEDIA, Efemeride, buscar_efemeride

AMOSTRAS = Path(__file__).parent / "fixtures" / "jornal"

#: 29/06 às 09:00 de Brasília.
AGORA = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


def carregar(nome: str) -> dict:
    return json.loads((AMOSTRAS / nome).read_text(encoding="utf-8"))


def transporte(corpo: dict | int, registro: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(pedido)
        if isinstance(corpo, int):
            return httpx.Response(corpo)
        return httpx.Response(200, json=corpo)

    return httpx.MockTransport(responder)


def test_pede_os_acontecimentos_do_dia_em_brasilia_com_o_ua_do_whis():
    registro: list[httpx.Request] = []

    buscar_efemeride(datetime(2026, 9, 25, 2, 30, tzinfo=UTC), transporte=transporte({"events": []}, registro))

    assert len(registro) == 1
    assert str(registro[0].url) == "https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/09/24"
    assert registro[0].headers["User-Agent"] == UA_WIKIPEDIA == "Whis/0.1 (+https://github.com/bielvelozo/whis)"


def test_primeiro_acontecimento_de_futebol_com_link_e_miniatura_da_primeira_pagina():
    efemeride = buscar_efemeride(AGORA, transporte=transporte(carregar("wikipedia_events_0629.json")))

    assert efemeride == Efemeride(
        ano=1986,
        texto="A Argentina vence a Copa do Mundo FIFA pela segunda vez.",
        link="https://pt.wikipedia.org/wiki/Argentina",
        imagem=(
            "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1a/Flag_of_Argentina.svg/"
            "langpt-330px-Flag_of_Argentina.svg.png"
            "?utm_source=pt.wikipedia.org&utm_campaign=api&utm_content=thumbnail"
        ),
    )


def test_events_antes_de_births_nascimento_de_futebolista_nunca_entra():
    tudo = carregar("wikipedia_all_0925_nascimentos_de_futebolista.json")
    assert any("futebolista" in n["text"] for n in tudo["births"])

    assert buscar_efemeride(AGORA, transporte=transporte(tudo)) is None


def test_sem_acontecimento_de_futebol_no_dia_devolve_none():
    so_outros = carregar("wikipedia_events_0629.json")
    so_outros["events"] = [e for e in so_outros["events"] if "Copa" not in e["text"]]

    assert buscar_efemeride(AGORA, transporte=transporte(so_outros)) is None


def test_criterio_de_futebol_nao_pega_selecao_natural_nem_clube_qualquer():
    eventos = {
        "events": [
            {"year": 1859, "text": "Darwin publica sua teoria da seleção natural.", "pages": []},
            {"year": 1900, "text": "É fundado um clube de xadrez em Lisboa.", "pages": []},
            {"year": 1910, "text": "É fundado o Sport Club Corinthians Paulista, clube de futebol.", "pages": []},
        ]
    }

    efemeride = buscar_efemeride(AGORA, transporte=transporte(eventos))

    assert efemeride is not None and efemeride.ano == 1910


def test_sem_miniatura_a_imagem_e_omitida():
    eventos = copy.deepcopy(carregar("wikipedia_events_0629.json"))
    for evento in eventos["events"]:
        for pagina in evento["pages"]:
            pagina.pop("thumbnail", None)

    efemeride = buscar_efemeride(AGORA, transporte=transporte(eventos))

    assert efemeride is not None
    assert efemeride.imagem is None
    assert efemeride.link == "https://pt.wikipedia.org/wiki/Argentina"


def test_sem_pagina_relacionada_fica_sem_link():
    eventos = {"events": [{"year": 1950, "text": "O Uruguai vence a Copa do Mundo FIFA.", "pages": []}]}

    assert buscar_efemeride(AGORA, transporte=transporte(eventos)) == Efemeride(
        ano=1950, texto="O Uruguai vence a Copa do Mundo FIFA.", link=None, imagem=None
    )


def test_falha_de_rede_devolve_none_e_registra(caplog):
    def sem_conexao(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    assert buscar_efemeride(AGORA, transporte=httpx.MockTransport(sem_conexao)) is None
    assert "Efeméride" in caplog.text


def test_http_de_erro_devolve_none():
    assert buscar_efemeride(AGORA, transporte=transporte(429)) is None
