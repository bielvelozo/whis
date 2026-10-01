"""O deck da daily: as seções que ele escreveu em `daily/atual.md`, em slides.

Puro, sem I/O. Recebe a nota e devolve os slides com o texto de cada linha
como ele escreveu, sem o marcador de lista e com a profundidade do recuo.
Quem desenha os arquivos do tipo Slides é `slides_do_deck`; quem publica é a
porta da publicação.

O corte em mais de um slide estima a altura de cada linha pela regra do tipo
Slides (cerca de 0,6 × o tamanho da fonte por caractere na largura útil):
nada encolhe para caber, a seção continua no slide seguinte e um sub-item só
se separa do pai quando o grupo inteiro não cabe num slide.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .nota_viva import (
    SECAO_DUVIDAS,
    SECAO_FALAR,
    SECAO_FAZENDO,
    SECAO_FIZ,
    NotaViva,
    texto_e_profundidade,
)

SECOES_DO_DECK = (
    (SECAO_FIZ, "fiz"),
    (SECAO_FAZENDO, "fazendo"),
    (SECAO_DUVIDAS, "duvidas"),
    (SECAO_FALAR, "falar"),
)

LARGURA_UTIL = 1664
#: 1080 − 128 no topo − 160 com o rodapé − o cabeçalho (faixa de 8, vão de 24, título de 72 × 1,1) − o vão de 48.
ALTURA_DA_LISTA = 633
FONTE_DO_ITEM = 40
FONTE_DO_SUBITEM = 32
ALTURA_DA_LINHA = 1.35
ESPACO_ENTRE_ITENS = 16
RECUO_POR_NIVEL = 48
LARGURA_DO_CARACTERE = 0.6


@dataclass(frozen=True)
class ItemDoSlide:
    texto: str
    profundidade: int = 0


@dataclass(frozen=True)
class Slide:
    id: str
    titulo: str
    secao: str
    itens: tuple[ItemDoSlide, ...]


@dataclass(frozen=True)
class SecaoDoDeck:
    """Uma seção da nota que virou slide, com as linhas dela exatamente como estão."""

    titulo: str
    linhas: tuple[str, ...]


@dataclass(frozen=True)
class Deck:
    slides: tuple[Slide, ...] = ()
    secoes: tuple[SecaoDoDeck, ...] = ()

    def vazio(self) -> bool:
        return not self.slides


def montar_deck(nota: NotaViva) -> Deck:
    slides: list[Slide] = []
    secoes: list[SecaoDoDeck] = []
    for titulo, id_base in SECOES_DO_DECK:
        linhas = nota.conteudo(titulo)
        itens = tuple(ItemDoSlide(texto, profundidade) for texto, profundidade in texto_e_profundidade(linhas))
        if not itens:
            continue
        secoes.append(SecaoDoDeck(titulo, linhas))
        paginas = paginar(itens)
        for numero, pagina in enumerate(paginas, start=1):
            slides.append(
                Slide(
                    id=id_base if numero == 1 else f"{id_base}-{numero}",
                    titulo=titulo if len(paginas) == 1 else f"{titulo} ({numero}/{len(paginas)})",
                    secao=titulo,
                    itens=pagina,
                )
            )
    return Deck(slides=tuple(slides), secoes=tuple(secoes))


def altura(item: ItemDoSlide) -> float:
    fonte = FONTE_DO_ITEM if item.profundidade == 0 else FONTE_DO_SUBITEM
    largura = LARGURA_UTIL - RECUO_POR_NIVEL * (item.profundidade + 1)
    por_linha = max(1, int(largura / (LARGURA_DO_CARACTERE * fonte)))
    linhas = max(1, math.ceil(len(item.texto) / por_linha))
    return linhas * fonte * ALTURA_DA_LINHA + ESPACO_ENTRE_ITENS


def paginar(itens: Sequence[ItemDoSlide]) -> tuple[tuple[ItemDoSlide, ...], ...]:
    paginas: list[list[ItemDoSlide]] = [[]]
    usada = 0.0
    for grupo in _grupos(itens):
        pedacos = [grupo] if _soma(grupo) <= ALTURA_DA_LISTA else [[item] for item in grupo]
        for pedaco in pedacos:
            tamanho = _soma(pedaco)
            if paginas[-1] and usada + tamanho > ALTURA_DA_LISTA:
                paginas.append([])
                usada = 0.0
            paginas[-1].extend(pedaco)
            usada += tamanho
    return tuple(tuple(pagina) for pagina in paginas if pagina)


def _grupos(itens: Sequence[ItemDoSlide]) -> list[list[ItemDoSlide]]:
    grupos: list[list[ItemDoSlide]] = []
    for item in itens:
        if item.profundidade == 0 or not grupos:
            grupos.append([item])
        else:
            grupos[-1].append(item)
    return grupos


def _soma(itens: Sequence[ItemDoSlide]) -> float:
    return sum(altura(item) for item in itens)
