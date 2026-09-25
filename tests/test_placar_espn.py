"""O placar da ESPN, sem rede.

As amostras são respostas reais do `scoreboard` baixadas em 2026-09-25 e
cortadas a poucos jogos: a Série A de 19/09 (dois gols de pênalti; um jogo às
21:30 UTC que fica fora das 30 h) e de 20/09 (Corinthians 1 x 3 Fluminense e
um gol contra no Flamengo), a Série B de 25/09 com dois jogos ainda não
encerrados, e a Premier League de 25/09 com `events: []`.

`AGORA` é 21/09 às 00:45 de Brasília: 20/09 às 23:45 em US/Eastern, então a
consulta pede os dias 19 e 20 da ESPN.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from whis.placar_espn import (
    LIGAS,
    TEXTO_INDISPONIVEL,
    TEXTO_SEM_JOGO,
    UA_ESPN,
    Gol,
    Jogo,
    buscar_placar,
)

AMOSTRAS = Path(__file__).parent / "fixtures" / "jornal"
AGORA = datetime(2026, 9, 21, 3, 45, tzinfo=UTC)
SEM_JOGOS = "espn_eng1_20260925_sem_jogos.json"


def carregar(nome: str) -> dict:
    return json.loads((AMOSTRAS / nome).read_text(encoding="utf-8"))


def transporte(
    por_liga_e_dia: dict[tuple[str, str], dict | int],
    registro: list[httpx.Request] | None = None,
    padrao: dict | int | None = None,
) -> httpx.MockTransport:
    """Responde por `(slug, AAAAMMDD)`; o resto recebe `padrao` (`events: []`)."""
    vazio = carregar(SEM_JOGOS) if padrao is None else padrao

    def responder(pedido: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(pedido)
        slug = pedido.url.path.split("/")[-2]
        resposta = por_liga_e_dia.get((slug, pedido.url.params["dates"]), vazio)
        if isinstance(resposta, int):
            return httpx.Response(resposta)
        return httpx.Response(200, json=resposta)

    return httpx.MockTransport(responder)


def serie_a() -> dict[tuple[str, str], dict]:
    return {
        ("bra.1", "20260919"): carregar("espn_bra1_20260919.json"),
        ("bra.1", "20260920"): carregar("espn_bra1_20260920.json"),
    }


def placar_de(respostas: dict, agora: datetime = AGORA, **extra):
    return buscar_placar(agora, transporte=transporte(respostas, **extra))


def test_consulta_ontem_e_hoje_de_cada_liga_com_ua_simples():
    registro: list[httpx.Request] = []

    placar_de({}, registro=registro)

    assert len(registro) == 14
    assert {p.url.params["dates"] for p in registro} == {"20260919", "20260920"}
    assert [p.url.path.split("/")[-2] for p in registro[::2]] == list(LIGAS.values())
    assert all(p.url.host == "site.api.espn.com" for p in registro)
    assert all(p.headers["User-Agent"] == UA_ESPN for p in registro)
    assert "(" not in UA_ESPN


def test_ligas_na_ordem_da_spec():
    assert LIGAS == {
        "Série A": "bra.1",
        "Série B": "bra.2",
        "Copa do Brasil": "bra.copa_do_brazil",
        "Libertadores": "conmebol.libertadores",
        "Sul-Americana": "conmebol.sudamericana",
        "Premier League": "eng.1",
        "La Liga": "esp.1",
    }


def test_dia_da_espn_e_o_de_us_eastern_tambem_fora_do_horario_de_verao():
    registro: list[httpx.Request] = []

    placar_de({}, agora=datetime(2026, 1, 15, 4, 30, tzinfo=UTC), registro=registro)

    assert {p.url.params["dates"] for p in registro} == {"20260113", "20260114"}


def test_jogos_encerrados_nas_ultimas_30_horas_em_ordem_com_hora_de_brasilia():
    placar = placar_de(serie_a())

    assert placar.situacao == "ok"
    assert placar.texto == ""
    assert [
        (j.liga, j.mandante, j.placar_mandante, j.placar_visitante, j.visitante, j.hora_brt)
        for j in placar.jogos
    ] == [
        ("Série A", "Vasco da Gama", 5, 0, "Coritiba", "19/09 20:30"),
        ("Série A", "São Paulo", 1, 0, "Internacional", "19/09 21:00"),
        ("Série A", "Grêmio", 0, 0, "Palmeiras", "20/09 11:00"),
        ("Série A", "Corinthians", 1, 3, "Fluminense", "20/09 16:00"),
        ("Série A", "Flamengo", 2, 1, "Red Bull Bragantino", "20/09 18:30"),
    ]


def test_filtro_de_30_horas_pelo_date_utc():
    antes = placar_de(serie_a(), agora=datetime(2026, 9, 21, 3, 15, tzinfo=UTC))
    depois = placar_de(serie_a(), agora=AGORA)

    assert ("Remo", "Santos") in {(j.mandante, j.visitante) for j in antes.jogos}
    assert ("Remo", "Santos") not in {(j.mandante, j.visitante) for j in depois.jogos}


def test_gols_com_minuto_autor_e_lado():
    corinthians = next(j for j in placar_de(serie_a()).jogos if j.mandante == "Corinthians")

    assert corinthians == Jogo(
        liga="Série A",
        mandante="Corinthians",
        visitante="Fluminense",
        placar_mandante=1,
        placar_visitante=3,
        hora_brt="20/09 16:00",
        gols=(
            Gol("24'", "Hulk", "fora"),
            Gol("56'", "Gustavo Henrique", "casa"),
            Gol("76'", "Hulk", "fora"),
            Gol("90'+3'", "Kevin Serna", "fora"),
        ),
    )


def test_gols_de_penalti_e_contra_sao_marcados():
    jogos = {j.mandante: j for j in placar_de(serie_a()).jogos}

    assert Gol("56'", "Alan Lescano (pên.)", "casa") in jogos["Vasco da Gama"].gols
    assert jogos["São Paulo"].gols == (Gol("15'", "Jonathan Calleri (pên.)", "casa"),)
    assert jogos["Flamengo"].gols[-1] == Gol("86'", "Bruno Henrique (contra)", "fora")
    assert jogos["Grêmio"].gols == ()


def test_so_jogo_encerrado_entra():
    serie_b = carregar("espn_bra2_20260925_nao_encerrados.json")
    agora = datetime(2026, 9, 26, 2, 0, tzinfo=UTC)

    sem_nenhum_encerrado = placar_de({("bra.2", "20260925"): serie_b}, agora=agora)
    serie_b["events"][0]["status"]["type"]["completed"] = True
    com_um_encerrado = placar_de({("bra.2", "20260925"): serie_b}, agora=agora)

    assert sem_nenhum_encerrado.jogos == ()
    assert [(j.mandante, j.visitante) for j in com_um_encerrado.jogos] == [("Novorizontino", "São Bernardo")]


def test_jogo_repetido_nos_dois_dias_aparece_uma_vez():
    mesmo = carregar("espn_bra1_20260919.json")

    placar = placar_de({("bra.1", "20260919"): mesmo, ("bra.1", "20260920"): mesmo})

    assert [j.mandante for j in placar.jogos] == ["Vasco da Gama", "São Paulo"]


def test_events_vazio_em_todas_as_ligas_vira_a_frase_de_sem_jogo():
    placar = placar_de({})

    assert placar.jogos == ()
    assert placar.situacao == "sem_jogo"
    assert placar.texto == TEXTO_SEM_JOGO == "Sem jogo encerrado nas últimas 24 h nos campeonatos acompanhados."


def test_http_403_vira_indisponivel():
    placar = placar_de({}, padrao=403)

    assert placar.jogos == ()
    assert placar.situacao == "indisponivel"
    assert placar.texto == TEXTO_INDISPONIVEL == "Placar indisponível hoje"


def test_liga_que_falha_nao_derruba_as_outras(caplog):
    respostas = serie_a() | {("eng.1", "20260919"): 500, ("eng.1", "20260920"): 500}

    placar = placar_de(respostas)

    assert placar.situacao == "ok"
    assert len(placar.jogos) == 5
    assert "Premier League" in caplog.text


def test_sem_jogo_com_liga_falhando_nao_afirma_que_nao_houve_jogo():
    placar = placar_de({("esp.1", "20260920"): 503})

    assert placar.situacao == "indisponivel"
    assert placar.texto == TEXTO_INDISPONIVEL


def test_json_quebrado_conta_como_falha_da_liga():
    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>Access Denied</html>")

    placar = buscar_placar(AGORA, transporte=httpx.MockTransport(responder))

    assert placar.situacao == "indisponivel"
