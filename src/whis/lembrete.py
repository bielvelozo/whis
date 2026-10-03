"""O lembrete da véspera: um toast quando a semana do plano do Claude está para virar.

Ele solta a caçada na madrugada antes da virada semanal, para gastar o que
sobrou da semana sem tocar a cota do trabalho. A virada tem hora fixa por conta
(research 07): a caçada guarda a última que leu do plano (`corrida.virada.json`)
e daqui se acha a próxima somando semanas. Sem nenhuma guardada, uma sonda de um
turno do Haiku lê a hora uma vez.

A tarefa `Whis-Lembrete-Cacada` chama `whis lembrete --agendada` todo dia em
`[cacada].hora_do_lembrete`; o toast sai uma vez por virada, quando ela cai nas
próximas 30 horas. Lembrar não é soltar: a caçada continua sendo só quando ele
chama.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .vault import _DIAS_DA_SEMANA

JANELA_DO_LEMBRETE = timedelta(hours=30)
NOME_DO_ULTIMO = "lembrete.json"


def proxima_virada(conhecida: datetime, agora: datetime) -> datetime:
    """A primeira virada depois de agora, somando ou tirando semanas inteiras da conhecida."""
    semana = timedelta(days=7)
    proxima = conhecida
    while proxima <= agora:
        proxima += semana
    while proxima - semana > agora:
        proxima -= semana
    return proxima


def texto_do_lembrete(virada: datetime, agora: datetime) -> str | None:
    """O texto do toast, ou `None` quando a virada não está nas próximas 30 horas."""
    falta = virada - agora
    if not timedelta(0) < falta <= JANELA_DO_LEMBRETE:
        return None
    local = virada.astimezone()
    dia = "hoje" if local.date() == agora.astimezone().date() else _DIAS_DA_SEMANA[local.weekday()]
    return (
        f"A semana do plano do Claude vira {dia} às {local:%H:%M}. Solte a caçada (hunt) na madrugada antes, "
        f"para usar o que sobrou sem tocar a cota do trabalho."
    )


def ja_lembrado(pasta: Path, virada: datetime) -> bool:
    try:
        dados = json.loads((Path(pasta) / NOME_DO_ULTIMO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return dados.get("virada") == virada.isoformat()


def marcar_lembrado(pasta: Path, virada: datetime) -> None:
    arquivo = Path(pasta) / NOME_DO_ULTIMO
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"virada": virada.isoformat()}), encoding="utf-8")
