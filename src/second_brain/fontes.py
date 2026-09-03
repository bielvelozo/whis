"""Os tipos comuns das fontes passivas: janela, evento, porta e filtro.

Toda fonte passiva — git, Linear, Slack — devolve o mesmo `Evento`, coletado
por `PortaFonte.coletar(janela)`. Nenhuma parte do diário conhece o formato de
uma API específica: quem traduz é o adaptador, e o que circula daqui para
frente é sempre `Evento`.

Este módulo não importa nada do resto do pacote de propósito: ele é a base que
`diario.py`, `vault.py`, `portas.py` e os três coletores compartilham.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol, runtime_checkable

#: Hora em que um dia do diário começa e o anterior termina.
INICIO_DO_DIA_PADRAO = "04:00"

#: A ordem em que as fontes são lidas e aparecem na nota.
ORDEM_DAS_FONTES = ("git", "linear", "slack")


@dataclass(frozen=True)
class Janela:
    """O intervalo que um diário cobre. Sempre com fuso, sempre meio-aberto."""

    data: date
    inicio: datetime
    fim: datetime

    def contem(self, momento: datetime) -> bool:
        """O momento cai nesta janela? Início inclusivo, fim exclusivo."""
        return self.inicio <= momento < self.fim

    def como_texto(self) -> str:
        """A janela no formato que vai para o frontmatter do diário."""
        return f"{self.inicio.isoformat()} → {self.fim.isoformat()}"


@dataclass(frozen=True)
class Evento:
    """Um acontecimento do dia, no formato comum a toda fonte passiva."""

    fonte: str
    momento: datetime
    titulo: str
    detalhe: str = ""
    referencia: str | None = None
    url: str | None = None
    pessoas: tuple[str, ...] = ()


class ErroDeFonte(RuntimeError):
    """A fonte não pôde ser lida. O diário nasce sem ela, marcado."""


@runtime_checkable
class PortaFonte(Protocol):
    """Lê uma fonte passiva no intervalo de um dia."""

    nome: str

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        """Devolve os eventos **dentro da janela**, em qualquer ordem.

        Filtrar por tempo é da fonte, que sabe pedir isso à sua API; o diário
        não re-filtra. `momento` é sempre aware, no fuso local. Um dia sem nada
        é uma tupla vazia, não uma falha; falha é `ErroDeFonte`.
        """
        ...


def analisar_hora(texto: str) -> time:
    """Interpreta `HH:MM` em 24 horas. Levanta `ValueError` no resto.

    Vive aqui, e não em `configuracao`, porque a hora é um conceito da janela:
    quem valida a chave do TOML só traduz este erro para a linguagem do
    usuário.
    """
    return datetime.strptime(texto.strip(), "%H:%M").time()


def janela_do_dia(data: date, inicio_do_dia: str = INICIO_DO_DIA_PADRAO) -> Janela:
    """A janela do diário de `data`: dela às mesmas horas do dia seguinte.

    Com o padrão `04:00`, o trabalho da madrugada cai no diário do dia
    anterior — que é o dia que o usuário viveu. `00:00` recupera o dia civil.
    """
    hora = analisar_hora(inicio_do_dia)
    inicio = datetime.combine(data, hora).astimezone()
    fim = datetime.combine(data + timedelta(days=1), hora).astimezone()
    return Janela(data=data, inicio=inicio, fim=fim)


def data_do_diario(agora: datetime, inicio_do_dia: str = INICIO_DO_DIA_PADRAO) -> date:
    """A que dia do diário pertence este instante — o inverso de `janela_do_dia`.

    É o que a CLI usa quando o usuário não passa data: às 02:00 de quinta,
    com o padrão `04:00`, o diário a gerar ainda é o de quarta.
    """
    hora = analisar_hora(inicio_do_dia)
    if agora.time() < hora:
        return agora.date() - timedelta(days=1)
    return agora.date()


def filtrar(
    eventos: Iterable[Evento], padroes: Sequence[str]
) -> tuple[tuple[Evento, ...], int]:
    """Remove os eventos que casam com o filtro de exclusão.

    Um evento sai se **algum** padrão aparecer como substring em `titulo`,
    `detalhe`, `referencia` ou em qualquer item de `pessoas`, sem diferenciar
    maiúsculas. Devolve o que ficou e quantos saíram.

    Substring, não regex, de propósito: regex em arquivo de configuração ou
    explode na cara do usuário ou casa com tudo e esvazia o diário em silêncio.
    """
    ativos = [padrao.casefold() for padrao in padroes if padrao and padrao.strip()]
    if not ativos:
        return tuple(eventos), 0

    ficaram: list[Evento] = []
    removidos = 0
    for evento in eventos:
        if _casa_com_algum(evento, ativos):
            removidos += 1
        else:
            ficaram.append(evento)
    return tuple(ficaram), removidos


def ordenar(eventos: Iterable[Evento]) -> tuple[Evento, ...]:
    """Os eventos em ordem cronológica — a ordem em que o dia aconteceu."""
    return tuple(sorted(eventos, key=lambda evento: evento.momento))


def nome_legivel(fonte: str) -> str:
    """Como o nome da fonte aparece no título de seção da nota."""
    if fonte == "linear":
        return "Linear"
    return fonte[:1].upper() + fonte[1:]


def _casa_com_algum(evento: Evento, padroes: Sequence[str]) -> bool:
    campos = [evento.titulo, evento.detalhe, evento.referencia or "", *evento.pessoas]
    # As quebras de linha impedem que um padrão case por acidente no emendado
    # de dois campos vizinhos.
    alvo = "\n".join(campos).casefold()
    return any(padrao in alvo for padrao in padroes)
