"""A prova na proposta de freela: qual peça do *Portfólio* de `criterios.md` citar, com o link.

O resumo pede ao Claude a peça que mais casa com o pedido. O link que volta é
conferido aqui: precisa ser um da lista dele; se não for (ou se o resumo não
trouxe nada), fica a peça com mais palavras em comum com o título e a descrição
do freela, e nenhuma quando nada casa.

A vitrine (velozo.dev) nunca vai em proposta: desde 18/10 ela mostra
o e-mail dele e o botão do Fiverr, o que numa plataforma conta como contato de
fora. Pedido dele em 18/10: o link fica só nos e-mails para agências.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from urllib.parse import urlsplit

from .criterios_da_cacada import PecaDoPortfolio
from .oportunidades import Oportunidade

VITRINE = "velozo.dev"
_ENDERECOS_DA_VITRINE = (VITRINE, "gabrielvelozo.pages.dev")

_POUCO_SENTIDO = frozenset({"para", "pela", "pelo", "como", "mais", "sobre", "entre", "with", "from", "that", "this", "your"})


def e_a_vitrine(link: str) -> bool:
    endereco = link.strip()
    host = urlsplit(endereco if "//" in endereco else f"https://{endereco}").hostname or ""
    return host.removeprefix("www.") in _ENDERECOS_DA_VITRINE


def cita_a_vitrine(texto: str) -> bool:
    texto = (texto or "").casefold()
    return any(endereco in texto for endereco in _ENDERECOS_DA_VITRINE)


def sem_a_vitrine(pecas: Sequence[PecaDoPortfolio]) -> tuple[PecaDoPortfolio, ...]:
    """As peças que podem ir em proposta de plataforma: todas menos a vitrine."""
    return tuple(peca for peca in pecas if not e_a_vitrine(peca.link))


def pedido_do_portfolio(pecas: Sequence[PecaDoPortfolio]) -> str:
    """O bloco que vai no fim de *O que eu procuro*: as peças, uma por linha, com o link."""
    linhas = [
        "- Portfólio para citar na proposta de freela (o resumo escolhe a peça que mais casa com o pedido e "
        "copia o link exatamente como está aqui; link de portfólio pode ir na proposta, contato não):"
    ]
    linhas += [f"  - {peca.como_prova()}" for peca in pecas]
    return "\n".join(linhas)


def conferir_prova(prova: str, oportunidade: Oportunidade, pecas: Sequence[PecaDoPortfolio]) -> str:
    """`prova` se ela cita um link da lista; senão a peça que mais casa, ou vazio se nenhuma casa."""
    pecas = sem_a_vitrine(pecas)
    if not pecas:
        return "" if cita_a_vitrine(prova) else prova
    if any(peca.link in prova for peca in pecas) and not cita_a_vitrine(prova):
        return prova.strip()
    texto = set(_palavras(f"{oportunidade.titulo} {oportunidade.descricao}"))
    pontos = [(len(texto & set(_palavras(f"{peca.nome} {peca.mostra}"))), -indice, peca) for indice, peca in enumerate(pecas)]
    melhor, _, peca = max(pontos, key=lambda ponto: ponto[:2])
    return peca.como_prova() if melhor > 0 else ""


def _palavras(texto: str) -> list[str]:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))
    return [p for p in re.findall(r"[a-z0-9]+", sem_acento) if len(p) >= 4 and p not in _POUCO_SENTIDO]
