"""A costura da daily: `gerar_daily(agora) → nota em daily/`.

A janela não é um dia civil: vai do fim da última daily até agora. Numa
segunda-feira ela cobre o fim de semana inteiro, e é isso que impede que o
trabalho de sábado caia no vão entre duas falas. A âncora mora no frontmatter
da nota anterior — o vault é a fonte da verdade, e o usuário audita a janela
lendo o próprio arquivo.

A daily **não deriva do diário**: os dois recortes são diferentes e um não se
reconstrói do outro depois de resumido. O que as duas costuras compartilham é a
leitura das fontes, em `coleta.py`.

Como a nota carrega também as listas cruas, ela é o registro durável do vault —
o arquivo que o usuário efetivamente lê.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from . import vault as _vault
from .coleta import FalhaDeFonte, coletar
from .configuracao import Configuracao
from .fontes import Evento, Janela, PortaFonte
from .portas import Daily, ErroDeDaily, PortaDaily

_log = logging.getLogger("second_brain.daily")

#: Quanto a primeira daily de todas cobre, por não ter nota anterior.
PRIMEIRA_JANELA = timedelta(hours=24)


@dataclass(frozen=True)
class JanelaDaDaily:
    """O intervalo que uma daily cobre: da última fala até agora."""

    data: date
    desde: datetime
    ate: datetime
    primeira: bool = False

    def como_janela(self) -> Janela:
        """A mesma janela no formato que toda fonte passiva conhece."""
        return Janela(data=self.data, inicio=self.desde, fim=self.ate)


@dataclass(frozen=True)
class ResultadoDaDaily:
    """O que a geração produziu — o suficiente para falar sem reler a nota."""

    janela: JanelaDaDaily
    nota: Path | None
    eventos: tuple[Evento, ...]
    excluidos: int
    fontes_lidas: tuple[str, ...]
    fontes_com_falha: tuple[FalhaDeFonte, ...]
    reunioes: tuple[str, ...]
    roteiro: Daily | None
    pontos: _vault.PontosDaDaily
    vazio: bool = False
    simulado: bool = False
    falha_do_roteiro: str | None = None


def janela_da_daily(agora: datetime, vault: Path) -> JanelaDaDaily:
    """De quando até quando esta daily fala.

    `desde` é o `ate` da daily mais recente **de um dia anterior** — nunca o da
    daily de hoje, senão rodar o comando duas vezes no mesmo dia deixaria a
    segunda com uma janela vazia. Sem nenhuma daily anterior, cobre as últimas
    24 horas e a nota diz que foi a primeira.

    A daily de hoje entra por outro motivo: se ela já existe, o `desde` dela é
    o que vale, e a nova execução só estende o `ate`. Sem isso, a janela de
    quem roda o comando duas vezes escorregaria para frente.
    """
    anterior = _vault.ate_da_daily_anterior(vault, agora.date())
    de_hoje = _vault.desde_da_daily_de(vault, agora.date())

    if de_hoje is not None:
        _log.info("Já há daily hoje — mantendo o início em %s.", de_hoje.isoformat())
        return JanelaDaDaily(
            data=agora.date(), desde=de_hoje, ate=agora, primeira=anterior is None
        )
    if anterior is not None:
        _log.info("Ancorada na daily anterior, que foi até %s.", anterior.isoformat())
        return JanelaDaDaily(data=agora.date(), desde=anterior, ate=agora)

    _log.info("Nenhuma daily anterior no vault — cobrindo as últimas 24 horas.")
    return JanelaDaDaily(
        data=agora.date(), desde=agora - PRIMEIRA_JANELA, ate=agora, primeira=True
    )


def gerar_daily(
    agora: datetime,
    *,
    configuracao: Configuracao,
    fontes: Sequence[PortaFonte],
    roteiro: PortaDaily,
    simular: bool = False,
) -> ResultadoDaDaily:
    """Lê a janela desde a última daily e escreve `daily/YYYY-MM-DD.md`.

    Rodar de novo no mesmo dia mantém o `desde`, estende o `ate` até agora e
    reescreve a nota daquele dia. Nada cai no vão: o que acontecer depois da
    geração entra na daily de amanhã.

    `simular=True` coleta e filtra, mas não chama o Claude nem escreve nada.
    """
    janela = janela_da_daily(agora, configuracao.vault)
    _log.info(
        "Daily de %s — de %s até %s.",
        janela.data.isoformat(),
        janela.desde.isoformat(),
        janela.ate.isoformat(),
    )

    colhido = coletar(fontes, janela.como_janela(), configuracao=configuracao)
    pontos = _vault.pontos_da_daily(configuracao.vault)

    parcial = ResultadoDaDaily(
        janela=janela,
        nota=None,
        eventos=colhido.eventos,
        excluidos=colhido.excluidos,
        fontes_lidas=colhido.fontes_lidas,
        fontes_com_falha=colhido.fontes_com_falha,
        reunioes=colhido.reunioes,
        roteiro=None,
        pontos=pontos,
    )

    # Um ponto escrito à mão é motivo suficiente para a daily existir: ele é a
    # única coisa que não se recupera de lugar nenhum depois.
    if colhido.vazia() and not pontos.tem_algo():
        _log.info("Nada desde a última daily — nenhuma nota foi escrita.")
        return replace(parcial, vazio=True)

    if simular:
        _log.info("Simulação — o Claude não foi chamado e nada foi escrito.")
        return replace(parcial, simulado=True)

    falado, falha = _montar_roteiro(roteiro, colhido.eventos, colhido.reunioes)

    raiz = _vault.preparar(configuracao.vault)
    caminho = _vault.caminho_da_daily(janela.data)
    nota = _vault.escrever(
        raiz,
        caminho,
        _vault.montar_daily(
            janela=janela,
            eventos=colhido.eventos,
            reunioes=colhido.reunioes,
            fontes_lidas=colhido.fontes_lidas,
            fontes_com_falha=colhido.fontes_com_falha,
            roteiro=falado,
            pontos=pontos,
            falha_do_roteiro=falha,
        ),
        zonas=_vault.ZONAS_DA_DAILY,
    )
    _log.info("Daily disponível no vault: %s", caminho)

    return replace(parcial, nota=nota, roteiro=falado, falha_do_roteiro=falha)


def _montar_roteiro(
    roteiro: PortaDaily, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
) -> tuple[Daily | None, str | None]:
    """Pede o roteiro ao Claude; uma falha dele não custa a daily.

    As listas cruas e os pontos do usuário não existem em nenhum outro lugar —
    perder a nota inteira por causa do Claude seria perder o período.
    """
    try:
        return roteiro.resumir_daily(eventos, reunioes), None
    except ErroDeDaily as erro:
        _log.error("A daily ficou sem roteiro: %s", erro)
        return None, str(erro)
