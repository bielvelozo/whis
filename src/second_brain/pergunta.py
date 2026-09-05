"""A costura da busca: `responder(pergunta, conversa) → Resposta`.

A DM do Slack e o comando de diagnóstico são cascas finas sobre esta função,
como a bandeja é sobre o coletor. Tudo que é externo entra por porta injetada
— a busca por `PortaBusca` —, então o mesmo caminho roda em teste (com
`BuscaFake`) e em produção (com o Claude).

A ordem é fixa: recusa a pergunta vazia, monta as `Ferramentas` (é nelas que a
fronteira da pasta privada mora), pergunta com o histórico do fio, acrescenta
a pergunta e a resposta ao fio, e registra no log. `ErroDeBusca` sobe para quem
chamou, que decide o que fazer com ele.
"""

from __future__ import annotations

import logging
from datetime import datetime

from .busca import PortaBusca, Resposta
from .configuracao import Configuracao
from .conversa import AGENTE, USUARIO, Conversa
from .ferramentas import Ferramentas

_log = logging.getLogger("second_brain.pergunta")

#: O que entra no fio quando a busca devolve texto vazio: o fio guarda falas,
#: e um turno em branco não é fala.
SEM_RESPOSTA = "Não achei."


class PerguntaVazia(ValueError):
    """Mensagem sem pergunta nenhuma — não há o que buscar."""


def responder(
    pergunta: str,
    *,
    configuracao: Configuracao,
    busca: PortaBusca,
    conversa: Conversa | None = None,
    agora: datetime | None = None,
) -> Resposta:
    """Responde à pergunta com o vault, citando de onde tirou cada afirmação.

    `agora` é o relógio do fio: injetado nos testes, o relógio da máquina no
    resto. `conversa` é opcional para o comando de diagnóstico poder perguntar
    sem fio nenhum.
    """
    if not pergunta or not pergunta.strip():
        raise PerguntaVazia("Escreva uma pergunta — a mensagem veio vazia.")
    momento = agora if agora is not None else datetime.now().astimezone()

    ferramentas = Ferramentas(configuracao)
    if conversa is not None:
        conversa.expirar(momento)
    historico = conversa.historico() if conversa is not None else ()
    _log.info("Pergunta: %r (%d turnos de contexto)", _resumida(pergunta), len(historico))

    resposta = busca.perguntar(pergunta, ferramentas, historico=historico)

    if conversa is not None:
        conversa.acrescentar(USUARIO, pergunta, agora=momento)
        conversa.acrescentar(AGENTE, resposta.texto or SEM_RESPOSTA, agora=momento)

    _log.info(
        "Resposta: %s, %d citações, %d notas lidas, equivalente a %s na tabela da "
        "API — a assinatura não cobra por token.",
        "achou" if resposta.achou else "não achou",
        len(resposta.citacoes),
        ferramentas.notas_lidas,
        _dinheiro(resposta.custo_usd),
    )
    return resposta


def _resumida(pergunta: str, tamanho: int = 120) -> str:
    limpa = " ".join(pergunta.split())
    return limpa if len(limpa) <= tamanho else limpa[: tamanho - 1] + "…"


def _dinheiro(valor: float | None) -> str:
    return f"US$ {valor:.4f}" if isinstance(valor, (int, float)) else "não informado"
