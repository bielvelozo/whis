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
from .configuracao import Configuracao
from .fontes import Evento, ErroDeFonte, Janela, PortaFonte, filtrar, janela_do_dia, ordenar
from .portas import ErroDeResumoDoDia, PortaResumoDoDia, ResumoDoDia

_log = logging.getLogger("second_brain.diario")


class TodasAsFontesFalharam(RuntimeError):
    """Nenhuma fonte respondeu — nada é escrito, o comando termina em erro."""


class NenhumaFonteConfigurada(RuntimeError):
    """Não há fonte ligada na configuração para ler."""


@dataclass(frozen=True)
class FalhaDeFonte:
    """Uma fonte que não pôde ser lida, com o motivo que vai para a nota."""

    fonte: str
    motivo: str


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

    coletados, lidas, falhas = _coletar(fontes, janela)
    # O filtro age aqui e em nenhum outro lugar: sobre o que toda fonte
    # devolveu, antes do resumo e antes do vault. Espalhá-lo pelos coletores
    # faria a régua depender de nenhum deles esquecer de aplicá-la.
    eventos, excluidos = filtrar(coletados, configuracao.privacidade_excluir)
    if excluidos:
        _log.info(
            "Filtro de exclusão removeu %d evento(s) — não vão ao Claude nem ao vault.",
            excluidos,
        )
    eventos = ordenar(eventos)

    reunioes = _vault.reunioes_na_janela(configuracao.vault, janela)
    _log.info("%d reunião(ões) do dia já no vault.", len(reunioes))

    if falhas and not lidas:
        raise TodasAsFontesFalharam(
            "Nenhuma fonte respondeu, então nada foi escrito — um diário ausente "
            "é mais honesto que um vazio. Motivos: "
            + "; ".join(f"{falha.fonte}: {falha.motivo}" for falha in falhas)
        )

    parcial = ResultadoDoDiario(
        data=data,
        janela=janela,
        nota=None,
        eventos=eventos,
        excluidos=excluidos,
        fontes_lidas=lidas,
        fontes_com_falha=falhas,
        reunioes=reunioes,
        resumo=None,
    )

    if not eventos and not reunioes:
        _log.info("Nada aconteceu em %s — nenhuma nota foi escrita.", data.isoformat())
        return replace(parcial, vazio=True)

    if simular:
        _log.info("Simulação — o resumo não foi chamado e nada foi escrito.")
        return replace(parcial, simulado=True)

    resumo_do_dia, falha_do_resumo = _resumir(resumo, eventos, reunioes)

    raiz = _vault.preparar(configuracao.vault)
    caminho = _vault.caminho_do_diario(data)
    nota = _vault.escrever(
        raiz,
        caminho,
        _vault.montar_diario(
            data=data,
            janela=janela,
            eventos=eventos,
            reunioes=reunioes,
            fontes_lidas=lidas,
            fontes_com_falha=falhas,
            resumo=resumo_do_dia,
            falha_do_resumo=falha_do_resumo,
        ),
        zonas=_vault.ZONAS_DO_DIARIO,
    )
    _log.info("Diário de %s disponível no vault: %s", data.isoformat(), caminho)

    return replace(
        parcial, nota=nota, resumo=resumo_do_dia, falha_do_resumo=falha_do_resumo
    )


def _coletar(
    fontes: Sequence[PortaFonte], janela: Janela
) -> tuple[tuple[Evento, ...], tuple[str, ...], tuple[FalhaDeFonte, ...]]:
    """Lê as fontes na ordem recebida; uma que falha não impede as outras."""
    eventos: list[Evento] = []
    lidas: list[str] = []
    falhas: list[FalhaDeFonte] = []
    for fonte in fontes:
        nome = getattr(fonte, "nome", type(fonte).__name__)
        try:
            colhidos = tuple(fonte.coletar(janela))
        except ErroDeFonte as erro:
            _log.error("Fonte '%s' não entrou no diário: %s", nome, erro)
            falhas.append(FalhaDeFonte(fonte=nome, motivo=str(erro)))
            continue
        _log.info("Fonte '%s': %d evento(s).", nome, len(colhidos))
        eventos.extend(colhidos)
        lidas.append(nome)
    return tuple(eventos), tuple(lidas), tuple(falhas)


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
