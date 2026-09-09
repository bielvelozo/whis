"""A costura das fontes passivas: `gerar_diario(data) → nota em diario/`.

Tudo que é externo entra por porta injetada — as fontes por `PortaFonte`, o
resumo por `PortaResumoDoDia` —, então o mesmo caminho de código roda em teste
(com fakes) e em produção (com git, Linear, Slack e Claude).

O diário nasce com o que conseguiu ler. Uma fonte que falha vira marca na nota,
não interrupção; só quando **todas** falham nada é escrito, porque um diário
ausente por falha não pode ser confundido com um dia tranquilo.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from . import vault as _vault
# `FalhaDeFonte` e `TodasAsFontesFalharam` são re-exportados de propósito: quem
# trata o diário os conhece por aqui desde a camada 01 e não precisa saber que
# eles passaram a morar na coleta compartilhada com a daily.
from .coleta import FalhaDeFonte, TodasAsFontesFalharam, coletar
from .configuracao import Configuracao
from .fontes import Evento, Janela, PortaFonte, janela_do_dia
from .portas import ErroDeResumoDoDia, PortaResumoDoDia, ResumoDoDia

__all__ = [
    "FalhaDeFonte",
    "NenhumaFonteConfigurada",
    "ResultadoDoDiario",
    "TodasAsFontesFalharam",
    "gerar_diario",
]

_log = logging.getLogger("whis.diario")


class NenhumaFonteConfigurada(RuntimeError):
    """Não há fonte ligada na configuração para ler."""


@dataclass(frozen=True)
class ResultadoDoDiario:
    """O que a geração produziu — o suficiente para relatar sem reler a nota."""

    data: date
    janela: Janela
    nota: Path | None
    eventos: tuple[Evento, ...]
    excluidos: int
    fontes_lidas: tuple[str, ...]
    fontes_com_falha: tuple[FalhaDeFonte, ...]
    reunioes: tuple[str, ...]
    resumo: ResumoDoDia | None
    vazio: bool = False
    simulado: bool = False
    falha_do_resumo: str | None = None


def gerar_diario(
    data: date,
    *,
    configuracao: Configuracao,
    fontes: Sequence[PortaFonte],
    resumo: PortaResumoDoDia,
    simular: bool = False,
) -> ResultadoDoDiario:
    """Lê as fontes passivas da janela de `data` e escreve `diario/YYYY-MM-DD.md`.

    Rodar de novo regenera e sobrescreve: a nota é sempre derivada da janela e
    das fontes, e é assim que o diário incorpora o trabalho da noite e as
    reuniões processadas depois.

    `simular=True` coleta e filtra, mas não chama o resumo nem escreve nada —
    é como o usuário confere o filtro de exclusão antes de confiar nele.
    """
    janela = janela_do_dia(data, configuracao.diario_inicio_do_dia)
    _log.info("Diário de %s — janela %s", data.isoformat(), janela.como_texto())

    colhido = coletar(fontes, janela, configuracao=configuracao)

    parcial = ResultadoDoDiario(
        data=data,
        janela=janela,
        nota=None,
        eventos=colhido.eventos,
        excluidos=colhido.excluidos,
        fontes_lidas=colhido.fontes_lidas,
        fontes_com_falha=colhido.fontes_com_falha,
        reunioes=colhido.reunioes,
        resumo=None,
    )

    if colhido.vazia():
        _log.info("Nada aconteceu em %s — nenhuma nota foi escrita.", data.isoformat())
        return replace(parcial, vazio=True)

    if simular:
        _log.info("Simulação — o resumo não foi chamado e nada foi escrito.")
        return replace(parcial, simulado=True)

    resumo_do_dia, falha_do_resumo = _resumir(resumo, colhido.eventos, colhido.reunioes)

    raiz = _vault.preparar(configuracao.vault)
    caminho = _vault.caminho_do_diario(data)
    nota = _vault.escrever(
        raiz,
        caminho,
        _vault.montar_diario(
            data=data,
            janela=janela,
            eventos=colhido.eventos,
            reunioes=colhido.reunioes,
            fontes_lidas=colhido.fontes_lidas,
            fontes_com_falha=colhido.fontes_com_falha,
            resumo=resumo_do_dia,
            falha_do_resumo=falha_do_resumo,
        ),
        zonas=_vault.ZONAS_DO_DIARIO,
    )
    _log.info("Diário de %s disponível no vault: %s", data.isoformat(), caminho)

    return replace(
        parcial, nota=nota, resumo=resumo_do_dia, falha_do_resumo=falha_do_resumo
    )


def _resumir(
    resumo: PortaResumoDoDia, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
) -> tuple[ResumoDoDia | None, str | None]:
    """Chama o resumo do dia; uma falha dele não custa o diário.

    Ao contrário da nota de reunião — onde a transcrição já guarda o conteúdo —,
    aqui as listas cruas não existem em nenhum outro lugar. Perder o diário
    inteiro por causa do Claude seria perder o dia.
    """
    try:
        return resumo.resumir_dia(eventos, reunioes), None
    except ErroDeResumoDoDia as erro:
        _log.error("O dia não foi resumido: %s", erro)
        return None, str(erro)
