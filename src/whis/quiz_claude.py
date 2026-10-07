"""O adaptador do Claude que escreve as perguntas novas do Quiz da semana.

Um turno, sem ferramenta e com saída estruturada, como o editor: o Claude só
recebe o texto das aulas lidas e escreve uma pergunta de múltipla escolha por
aula. A pergunta que sai do formato é descartada; nenhuma pergunta aproveitável
é erro, para a aula não ser dada como cobrada sem ter ganhado pergunta.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .jornal_claude import _AdaptadorDoJornal
from .portas import Aula, ErroDeQuiz, PerguntaNova, PerguntasNovas

_log = logging.getLogger("whis.jornal")

TIMEOUT_DO_QUIZ_S = 240.0
TURNOS_DO_QUIZ = 4
MINIMO_DE_ALTERNATIVAS = 3
MAXIMO_DE_ALTERNATIVAS = 4

SISTEMA_QUIZ = """\
Você escreve o QUIZ da semana de um desenvolvedor de software brasileiro que está aprendendo \
negócios e carros pelo jornal matinal. Você recebe as aulas que ele leu, cada uma com id, título e \
texto. Regras invioláveis:
- Escreva exatamente uma pergunta de múltipla escolha por aula recebida, em português do Brasil, para \
quem está aprendendo: curta, direta, sobre a ideia central da aula e não sobre um detalhe de rodapé.
- Só vale o que está no texto da aula. Nunca cobre número, nome, data ou fato que não esteja nele, nem \
conhecimento de fora.
- Use 3 ou 4 alternativas. Só uma é certa. As erradas precisam ser plausíveis (o erro que um iniciante \
cometeria), nunca absurdas, e do mesmo tamanho e tom da certa. Varie a posição da certa de uma pergunta \
para outra.
- "certa" é o índice da alternativa certa, começando em 0.
- A explicação tem uma ou duas frases e diz por que a certa é a certa, com base no texto da aula.
- Em "aula" ponha o id da aula exatamente como recebido."""

_PERGUNTA = {
    "type": "object",
    "properties": {
        "aula": {"type": "string"},
        "pergunta": {"type": "string"},
        "alternativas": {"type": "array", "items": {"type": "string"}},
        "certa": {"type": "integer"},
        "explicacao": {"type": "string"},
    },
    "required": ["aula", "pergunta", "alternativas", "certa", "explicacao"],
    "additionalProperties": False,
}

ESQUEMA_DO_QUIZ = {
    "type": "object",
    "properties": {"perguntas": {"type": "array", "items": _PERGUNTA}},
    "required": ["perguntas"],
    "additionalProperties": False,
}


class QuizClaude(_AdaptadorDoJornal):
    """A porta do quiz. Levanta `ErroDeQuiz` em qualquer falha, ou sem nenhuma pergunta aproveitável.

    Sem aulas não há o que perguntar: devolve `PerguntasNovas()` sem chamar o Claude.
    """

    etapa = "quiz"
    erro = ErroDeQuiz

    def __init__(
        self,
        *,
        modelo: str | None = None,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DO_QUIZ_S,
    ) -> None:
        super().__init__(modelo=modelo, cli=cli, timeout_s=timeout_s)

    def perguntar(self, aulas: Sequence[Aula]) -> PerguntasNovas:
        if not aulas:
            return PerguntasNovas()
        opcoes = self._opcoes(
            sistema=SISTEMA_QUIZ,
            ferramentas=[],
            max_turns=TURNOS_DO_QUIZ,
            esquema=ESQUEMA_DO_QUIZ,
        )
        _log.info("Pedindo o quiz ao Claude (%d aula(s), modelo: %s)...", len(aulas), self.modelo or "padrão da conta")
        conversa = self._conversar(montar_pedido_do_quiz(aulas), opcoes)
        dados = conversa.resultado.structured_output if conversa.resultado is not None else None
        if not isinstance(dados, dict):
            raise ErroDeQuiz(
                "O Claude não devolveu a saída estruturada do quiz "
                f"(veio {type(dados).__name__}). Começo do texto: {conversa.texto_final()[:200]!r}"
            )
        perguntas = interpretar_perguntas(dados, {aula.id for aula in aulas})
        if not perguntas:
            raise ErroDeQuiz("Nenhuma pergunta do quiz veio no formato — todas descartadas.")
        return PerguntasNovas(perguntas=perguntas, medida=conversa.medida)


def montar_pedido_do_quiz(aulas: Sequence[Aula]) -> str:
    """O turno do usuário: o id, o título e o texto de cada aula, e mais nada."""
    blocos = [f"id: {aula.id}\ntítulo: {aula.titulo}\ntexto:\n{aula.texto}" for aula in aulas]
    return (
        "Aulas lidas desde o último quiz. Escreva uma pergunta por aula.\n\n"
        + "\n\n---\n\n".join(blocos)
    )


def interpretar_perguntas(dados: dict, ids: set[str] | frozenset[str]) -> tuple[PerguntaNova, ...]:
    """Só as perguntas de aulas que foram enviadas, com 3 ou 4 alternativas e `certa` dentro delas."""
    brutas = dados.get("perguntas")
    if not isinstance(brutas, list):
        return ()
    perguntas = (_pergunta(bruta, ids) for bruta in brutas)
    return tuple(pergunta for pergunta in perguntas if pergunta is not None)


def _pergunta(bruta: object, ids: set[str] | frozenset[str]) -> PerguntaNova | None:
    if not isinstance(bruta, dict):
        return None
    aula = _texto(bruta.get("aula"))
    pergunta = _texto(bruta.get("pergunta"))
    explicacao = _texto(bruta.get("explicacao"))
    brutas = bruta.get("alternativas")
    certa = bruta.get("certa")
    if aula not in ids or not pergunta or not explicacao:
        return None
    if not isinstance(brutas, list) or not all(isinstance(a, str) for a in brutas):
        return None
    alternativas = tuple(" ".join(a.split()) for a in brutas)
    if not MINIMO_DE_ALTERNATIVAS <= len(alternativas) <= MAXIMO_DE_ALTERNATIVAS:
        return None
    if not all(alternativas) or len({a.casefold() for a in alternativas}) != len(alternativas):
        return None
    if isinstance(certa, bool) or not isinstance(certa, int) or not 0 <= certa < len(alternativas):
        return None
    return PerguntaNova(aula, pergunta, alternativas, certa, explicacao)


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""
