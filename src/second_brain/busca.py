"""A porta da busca: o que o agente devolve quando lhe perguntam alguma coisa.

Irmã das portas de `portas.py`, com uma diferença de forma: o adaptador real
não recebe só dados — recebe as `Ferramentas` do vault e um histórico de
conversa, e decide sozinho onde olhar. A costura (`pergunta.py`) e a DM do
Slack só conhecem esta porta; o Claude entra por `busca_claude.py`, o fake por
`fakes.BuscaFake`.

`Resposta.achou=False` é resposta legítima, não erro: "não achei isso no
vault" é o que impede o usuário de confundir invenção com memória. `ErroDeBusca`
é para o que impediu a busca de acontecer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .conversa import Turno
from .ferramentas import Ferramentas


@dataclass(frozen=True)
class Citacao:
    """De onde uma afirmação veio — sempre um arquivo do vault ou uma fonte.

    `origem` é um caminho relativo ao vault (`diario/2026-09-03.md`) ou, para
    as fontes ao vivo, o nome da fonte e o identificador (`linear:FN-1610`,
    `slack:#dev-codereview`), para o usuário saber que aquilo não veio do vault.
    """

    origem: str
    trecho: str = ""


@dataclass(frozen=True)
class Resposta:
    """O que a busca devolve. `texto` vazio com `achou=False` é "não sei"."""

    texto: str
    citacoes: tuple[Citacao, ...] = ()
    achou: bool = True
    custo_usd: float | None = None


class ErroDeBusca(RuntimeError):
    """A busca não pôde ser feita — sem credencial, sem rede, resposta ilegível."""


@runtime_checkable
class PortaBusca(Protocol):
    """Responde a uma pergunta usando as ferramentas do vault e o fio da conversa."""

    def perguntar(
        self,
        pergunta: str,
        ferramentas: Ferramentas,
        historico: tuple[Turno, ...] = (),
    ) -> Resposta:
        """Devolve a resposta com as citações que a sustentam.

        Levanta `ErroDeBusca` quando a busca não pôde acontecer.
        """
        ...
