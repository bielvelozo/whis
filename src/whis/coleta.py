"""O pedaço comum às duas costuras: ler as fontes passivas de uma janela.

Diário e daily leem as mesmas fontes com recortes de tempo diferentes — de
`04:00` a `04:00` num caso, da última fala até agora no outro. O que não muda é
o caminho entre a porta e o resultado: chamar cada fonte na ordem, sobreviver à
que falhar, aplicar o filtro de exclusão num ponto só, ordenar no tempo e achar
as reuniões que já viraram nota.

Este módulo é esse caminho. Nenhuma das duas costuras depende da outra: as duas
dependem daqui.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from . import vault as _vault
from .configuracao import Configuracao
from .fontes import ErroDeFonte, Evento, Janela, PortaFonte, filtrar, ordenar

_log = logging.getLogger("whis.coleta")


class TodasAsFontesFalharam(RuntimeError):
    """Nenhuma fonte respondeu — nada é escrito, o comando termina em erro."""


@dataclass(frozen=True)
class FalhaDeFonte:
    """Uma fonte que não pôde ser lida, com o motivo que vai para a nota."""

    fonte: str
    motivo: str


@dataclass(frozen=True)
class Coleta:
    """O que a janela rendeu: eventos já filtrados, reuniões e o que falhou."""

    eventos: tuple[Evento, ...]
    excluidos: int
    fontes_lidas: tuple[str, ...]
    fontes_com_falha: tuple[FalhaDeFonte, ...]
    reunioes: tuple[str, ...]

    def vazia(self) -> bool:
        """Nada aconteceu na janela — nem evento das fontes, nem reunião."""
        return not self.eventos and not self.reunioes


def coletar(
    fontes: Sequence[PortaFonte], janela: Janela, *, configuracao: Configuracao
) -> Coleta:
    """Lê as fontes da janela, filtra, ordena e acha as reuniões do vault.

    Uma fonte que falha vira `FalhaDeFonte` e a leitura continua nas outras.
    Só quando **todas** falham vem `TodasAsFontesFalharam`: uma nota ausente
    por falha não pode ser confundida com um período tranquilo.
    """
    coletados, lidas, falhas = _ler(fontes, janela)
    # O filtro age aqui e em nenhum outro lugar: sobre o que toda fonte
    # devolveu, antes do resumo e antes do vault. Espalhá-lo pelos coletores
    # faria a régua depender de nenhum deles esquecer de aplicá-la.
    eventos, excluidos = filtrar(coletados, configuracao.privacidade_excluir)
    if excluidos:
        _log.info(
            "Filtro de exclusão removeu %d evento(s) — não vão ao Claude nem ao vault.",
            excluidos,
        )

    reunioes = _vault.reunioes_na_janela(configuracao.vault, janela)
    _log.info("%d reunião(ões) da janela já no vault.", len(reunioes))

    if falhas and not lidas:
        raise TodasAsFontesFalharam(
            "Nenhuma fonte respondeu, então nada foi escrito — uma nota ausente "
            "é mais honesta que uma vazia. Motivos: "
            + "; ".join(f"{falha.fonte}: {falha.motivo}" for falha in falhas)
        )

    return Coleta(
        eventos=ordenar(eventos),
        excluidos=excluidos,
        fontes_lidas=lidas,
        fontes_com_falha=falhas,
        reunioes=reunioes,
    )


def _ler(
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
            _log.error("Fonte '%s' não pôde ser lida: %s", nome, erro)
            falhas.append(FalhaDeFonte(fonte=nome, motivo=str(erro)))
            continue
        _log.info("Fonte '%s': %d evento(s).", nome, len(colhidos))
        eventos.extend(colhidos)
        lidas.append(nome)
    return tuple(eventos), tuple(lidas), tuple(falhas)
