"""O placar do jornal: jogos encerrados nas últimas 30 h, com quem marcou.

Vem do `scoreboard` da ESPN (research/04), o único endpoint gratuito achado
que traz autor e minuto de cada gol. A API não é documentada e os termos da
Disney proíbem acesso automatizado: é uso pessoal, 14 chamadas por dia, e a
degradação é honesta — sem jogo, o jornal diz que não houve; sem resposta, diz
que o placar está indisponível. Os números nunca passam pelo modelo: a tabela
sai daqui.

O filtro `dates=` da ESPN é por dia de US/Eastern, então um jogo das 21:30 de
Brasília cai no dia seguinte deles. Por isso a consulta pede ontem e hoje no
fuso deles e corta pelo `date` UTC de cada jogo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

import httpx

_log = logging.getLogger("whis.placar_espn")

ENDPOINT = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"

#: A borda Akamai da ESPN devolve 403 para UA com contato entre parênteses.
UA_ESPN = "whis-jornal/0.1"

TEMPO_LIMITE_S = 15.0
JANELA = timedelta(hours=30)
BRT = timezone(timedelta(hours=-3), "BRT")

LIGAS: dict[str, str] = {
    "Série A": "bra.1",
    "Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brazil",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
}

OK = "ok"
SEM_JOGO = "sem_jogo"
INDISPONIVEL = "indisponivel"

TEXTO_SEM_JOGO = "Sem jogo encerrado nas últimas 24 h nos campeonatos acompanhados."
TEXTO_INDISPONIVEL = "Placar indisponível hoje"


@dataclass(frozen=True)
class Gol:
    """Um gol: minuto como a ESPN escreve (`90'+3'`) e autor já marcado."""

    minuto: str
    autor: str
    lado: str


@dataclass(frozen=True)
class Jogo:
    """Um jogo encerrado; `hora_brt` é `dd/mm HH:MM` no horário de Brasília."""

    liga: str
    mandante: str
    visitante: str
    placar_mandante: int
    placar_visitante: int
    hora_brt: str
    gols: tuple[Gol, ...]


@dataclass(frozen=True)
class Placar:
    """Os jogos e a situação; `texto` é a frase do jornal quando não há tabela."""

    jogos: tuple[Jogo, ...]
    situacao: str
    texto: str


def buscar_placar(agora: datetime, *, transporte: httpx.BaseTransport | None = None) -> Placar:
    """Os jogos encerrados nas últimas 30 h, liga a liga, na ordem de `LIGAS`.

    Liga que falha é registrada no log e o placar segue com as outras. Sem
    jogo nenhum, a frase só afirma "sem jogo" quando todas as ligas
    responderam; se alguma falhou, o placar é dado como indisponível.
    """
    agora = agora.astimezone(UTC)
    dias = [_dia_na_costa_leste(agora - timedelta(days=1)), _dia_na_costa_leste(agora)]
    jogos: list[Jogo] = []
    ligas_com_falha: list[str] = []

    with httpx.Client(
        transport=transporte, timeout=TEMPO_LIMITE_S, headers={"User-Agent": UA_ESPN}
    ) as cliente:
        for liga, slug in LIGAS.items():
            vistos: set[str] = set()
            da_liga: list[tuple[datetime, Jogo]] = []
            falhou = False
            for dia in dict.fromkeys(dias):
                try:
                    resposta = cliente.get(
                        ENDPOINT.format(slug=slug), params={"dates": dia.strftime("%Y%m%d")}
                    )
                    resposta.raise_for_status()
                    eventos = resposta.json().get("events") or []
                except (httpx.HTTPError, ValueError, AttributeError) as erro:
                    _log.warning("Placar da ESPN: %s (%s) em %s falhou: %s", liga, slug, dia, _motivo(erro))
                    falhou = True
                    continue
                for evento in eventos:
                    identificador = str(evento.get("id") or id(evento))
                    if identificador in vistos:
                        continue
                    vistos.add(identificador)
                    lido = _jogo(liga, evento, agora)
                    if lido is not None:
                        da_liga.append(lido)
            if falhou:
                ligas_com_falha.append(liga)
            jogos.extend(jogo for _, jogo in sorted(da_liga, key=lambda par: par[0]))

    if jogos:
        if ligas_com_falha:
            _log.warning("Placar sem %s; segue com as outras ligas", ", ".join(ligas_com_falha))
        return Placar(jogos=tuple(jogos), situacao=OK, texto="")
    if ligas_com_falha:
        return Placar(jogos=(), situacao=INDISPONIVEL, texto=TEXTO_INDISPONIVEL)
    return Placar(jogos=(), situacao=SEM_JOGO, texto=TEXTO_SEM_JOGO)


def _jogo(liga: str, evento: dict, agora: datetime) -> tuple[datetime, Jogo] | None:
    try:
        if not evento["status"]["type"].get("completed"):
            return None
        quando = datetime.fromisoformat(evento["date"].replace("Z", "+00:00")).astimezone(UTC)
        if quando > agora or agora - quando > JANELA:
            return None
        competicao = evento["competitions"][0]
        competidores = competicao["competitors"]
        mandante = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        visitante = next(c for c in competidores if c is not mandante)
        return quando, Jogo(
            liga=liga,
            mandante=mandante["team"]["displayName"],
            visitante=visitante["team"]["displayName"],
            placar_mandante=int(mandante.get("score") or 0),
            placar_visitante=int(visitante.get("score") or 0),
            hora_brt=quando.astimezone(BRT).strftime("%d/%m %H:%M"),
            gols=_gols(competicao, str(mandante["team"].get("id"))),
        )
    except (KeyError, IndexError, StopIteration, TypeError, ValueError) as erro:
        _log.warning("Placar da ESPN: jogo de %s ilegível (%s); ignorado", liga, _motivo(erro))
        return None


def _gols(competicao: dict, id_do_mandante: str) -> tuple[Gol, ...]:
    gols = []
    for lance in competicao.get("details") or []:
        if not lance.get("scoringPlay") or lance.get("shootout"):
            continue
        autor = ", ".join(
            atleta.get("displayName", "") for atleta in lance.get("athletesInvolved") or []
        ).strip(", ") or "?"
        if lance.get("penaltyKick"):
            autor += " (pên.)"
        elif lance.get("ownGoal"):
            autor += " (contra)"
        lado = "casa" if str((lance.get("team") or {}).get("id")) == id_do_mandante else "fora"
        gols.append(Gol(minuto=(lance.get("clock") or {}).get("displayValue", ""), autor=autor, lado=lado))
    return tuple(gols)


def _dia_na_costa_leste(instante: datetime) -> date:
    """O dia civil em US/Eastern, sem depender do `tzdata` (ausente no Windows).

    Horário de verão americano: do segundo domingo de março, 2h locais (7h
    UTC), ao primeiro domingo de novembro, 2h locais (6h UTC).
    """
    ano = instante.year
    inicio = _domingo(ano, 3, 2).replace(hour=7)
    fim = _domingo(ano, 11, 1).replace(hour=6)
    deslocamento = -4 if inicio <= instante < fim else -5
    return (instante + timedelta(hours=deslocamento)).date()


def _domingo(ano: int, mes: int, ordem: int) -> datetime:
    primeiro = datetime(ano, mes, 1, tzinfo=UTC)
    ate_domingo = (6 - primeiro.weekday()) % 7
    return primeiro + timedelta(days=ate_domingo + 7 * (ordem - 1))


def _motivo(erro: Exception) -> str:
    if isinstance(erro, httpx.HTTPStatusError):
        return f"HTTP {erro.response.status_code}"
    return type(erro).__name__
