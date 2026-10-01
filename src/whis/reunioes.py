"""A costura das reuniões: o que a Granola tem e o vault não vira nota em `reunioes/`.

Escreve uma vez só: a reunião cujo `granola_id` já está numa nota de
`reunioes/` não é pedida de novo, mesmo com o título trocado na Granola, e a
nota que existe nunca é reescrita. Reunião ainda sem resumo (acabou de
terminar) fica para a puxada seguinte. Um lote que falha não derruba os
outros: as reuniões dele entram em `falhas`, uma por uma.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from . import vault as _vault
from .configuracao import Configuracao
from .portas import ErroDaGranola, LoginNecessario, PortaReunioes, Reuniao

_log = logging.getLogger("whis.reunioes")

#: O máximo de ids que `get_meetings` aceita numa chamada.
LOTE = 10


@dataclass(frozen=True)
class ResultadoDasReunioes:
    """`novas` são caminhos relativos ao vault, em ordem cronológica, e `titulos_novos` os
    títulos delas na mesma ordem; `sem_resumo`, títulos; `falhas`, uma por reunião, como
    `"<título>: <motivo>"`."""

    novas: tuple[str, ...] = ()
    titulos_novos: tuple[str, ...] = ()
    ja_no_vault: int = 0
    sem_resumo: tuple[str, ...] = ()
    falhas: tuple[str, ...] = ()

    @property
    def nada_veio(self) -> bool:
        """Houve falha e nenhuma nota nasceu: a puxada não serviu para nada."""
        return bool(self.falhas) and not self.novas

    @property
    def parcial(self) -> bool:
        return bool(self.falhas) and bool(self.novas)


def puxar_reunioes(configuracao: Configuracao, porta: PortaReunioes) -> ResultadoDasReunioes:
    """Lista os últimos 30 dias, detalha as que faltam e escreve as que têm resumo.

    Levanta `ErroDaGranola` (ou `LoginNecessario`) quando nem a lista vem.
    """
    raiz = _vault.preparar(configuracao.vault)
    ja_no_vault = _vault.granola_ids_no_vault(raiz)
    listadas = porta.listar()
    pendentes = sorted((r for r in listadas if r.id not in ja_no_vault), key=lambda r: r.inicio)
    _log.info(
        "Granola: %d reunião(ões) nos últimos 30 dias, %d já no vault.",
        len(listadas),
        len(listadas) - len(pendentes),
    )

    novas: list[str] = []
    titulos_novos: list[str] = []
    sem_resumo: list[str] = []
    falhas: list[str] = []
    for inicio in range(0, len(pendentes), LOTE):
        lote = pendentes[inicio : inicio + LOTE]
        try:
            detalhadas = porta.detalhar([r.id for r in lote])
        except LoginNecessario:
            raise
        except ErroDaGranola as erro:
            _log.error("Granola: um lote de %d reunião(ões) não veio: %s", len(lote), erro)
            falhas.extend(f"{r.titulo}: {erro}" for r in lote)
            continue
        recebidas = {r.id for r in detalhadas}
        falhas.extend(f"{r.titulo}: não veio da Granola" for r in lote if r.id not in recebidas)
        for reuniao in sorted(detalhadas, key=lambda r: r.inicio):
            if not reuniao.resumo.strip():
                sem_resumo.append(reuniao.titulo)
                continue
            novas.append(_escrever(raiz, reuniao))
            titulos_novos.append(reuniao.titulo)

    for caminho in novas:
        _log.info("Granola: reunião nova no vault: %s", caminho)
    if sem_resumo:
        _log.info("Granola: ainda sem resumo, fica para a próxima: %s", ", ".join(sem_resumo))
    return ResultadoDasReunioes(
        novas=tuple(novas),
        titulos_novos=tuple(titulos_novos),
        ja_no_vault=len(listadas) - len(pendentes),
        sem_resumo=tuple(sem_resumo),
        falhas=tuple(falhas),
    )


def _escrever(raiz: Path, reuniao: Reuniao) -> str:
    """Escreve a nota num nome livre: `vault.escrever` sobrescreveria sem avisar."""
    base = _vault.caminho_da_reuniao(reuniao.inicio, reuniao.titulo)
    caminho = base
    sufixo = 2
    while (raiz / caminho).exists():
        caminho = f"{base.removesuffix('.md')}-{sufixo}.md"
        sufixo += 1
    _vault.escrever(raiz, caminho, _vault.montar_reuniao(reuniao), zonas=_vault.ZONAS_DAS_REUNIOES)
    return caminho
