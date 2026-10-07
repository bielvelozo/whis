"""O adaptador do Claude que escreve as perguntas novas do quiz, sem tocar a rede.

Mesmo molde de `test_jornal_claude`: a única parte que fala com o Claude é
`_mensagens`, que aqui devolve mensagens gravadas.
"""

from __future__ import annotations

import asyncio

import pytest
from claude_agent_sdk import AssistantMessage, CLIConnectionError, ResultMessage, TextBlock

from whis.claude_cli import VARIAVEIS_DE_API_PAGA
from whis.portas import Aula, ErroDeQuiz, PerguntaNova, PerguntasNovas, PortaQuiz
from whis.quiz_claude import (
    ESQUEMA_DO_QUIZ,
    SISTEMA_QUIZ,
    QuizClaude,
    interpretar_perguntas,
    montar_pedido_do_quiz,
)

NEGOCIOS = "2026-10-06-negocios"
CARROS = "2026-10-06-carros-1"


def _resultado(**extras) -> ResultMessage:
    campos = {
        "subtype": "success",
        "duration_ms": 4000,
        "duration_api_ms": 3500,
        "is_error": False,
        "num_turns": 1,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.02,
        "usage": {"input_tokens": 900, "output_tokens": 400},
    }
    return ResultMessage(**{**campos, **extras})


def _texto(texto: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=texto)], model="claude-sonnet-4-5")


class _Gravado:
    """Troca a rede por mensagens gravadas e guarda o prompt e as opções de cada chamada."""

    def __init__(self, mensagens: list, **extras) -> None:
        super().__init__(**extras)
        self.mensagens = mensagens
        self.prompts: list[str] = []
        self.opcoes: list = []

    async def _mensagens(self, prompt, opcoes):
        self.prompts.append(prompt)
        self.opcoes.append(opcoes)
        for mensagem in self.mensagens:
            if isinstance(mensagem, BaseException):
                raise mensagem
            if mensagem == "dormir":
                await asyncio.sleep(5)
                continue
            yield mensagem


class QuizGravada(_Gravado, QuizClaude):
    pass


@pytest.fixture(autouse=True)
def _sem_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)


def _aula(id_: str, titulo: str = "Margem", texto: str = "Margem é o que sobra depois do custo.") -> Aula:
    return Aula(titulo, texto, ("https://exemplo.com/a",), "", id=id_)


def _bruta(aula: str = NEGOCIOS, **extras) -> dict:
    return {
        "aula": aula,
        "pergunta": "Margem é?",
        "alternativas": ["a", "b", "c"],
        "certa": 2,
        "explicacao": "Porque c.",
        **extras,
    }


AULAS = [_aula(NEGOCIOS), _aula(CARROS, "Turbo", "O turbo usa o gás de escape para girar uma turbina.")]


# --- a porta ------------------------------------------------------------------------------


def test_o_adaptador_cumpre_a_porta():
    assert isinstance(QuizClaude(), PortaQuiz)


# --- interpretar as perguntas --------------------------------------------------------------


def test_uma_pergunta_por_aula_validada():
    dados = {
        "perguntas": [
            {"aula": NEGOCIOS, "pergunta": "Margem é?", "alternativas": ["a", "b", "c"], "certa": 2, "explicacao": "e"},
            {"aula": NEGOCIOS, "pergunta": "Sem alternativa", "alternativas": ["a"], "certa": 0, "explicacao": "e"},
            {"aula": NEGOCIOS, "pergunta": "Certa fora", "alternativas": ["a", "b", "c"], "certa": 3, "explicacao": "e"},
            {"aula": "id-que-nao-veio", "pergunta": "x", "alternativas": ["a", "b", "c"], "certa": 0, "explicacao": "e"},
        ]
    }
    assert [q.pergunta for q in interpretar_perguntas(dados, {NEGOCIOS})] == ["Margem é?"]


def test_a_pergunta_aceita_vira_pergunta_nova_com_tupla():
    [pergunta] = interpretar_perguntas({"perguntas": [_bruta()]}, {NEGOCIOS})
    assert pergunta == PerguntaNova(NEGOCIOS, "Margem é?", ("a", "b", "c"), 2, "Porque c.")
    assert isinstance(pergunta.alternativas, tuple)


def test_quatro_alternativas_valem_e_a_ultima_pode_ser_a_certa():
    [pergunta] = interpretar_perguntas({"perguntas": [_bruta(alternativas=list("abcd"), certa=3)]}, {NEGOCIOS})
    assert pergunta.alternativas == ("a", "b", "c", "d") and pergunta.certa == 3


def test_espaco_em_volta_sai_e_alternativa_de_varias_linhas_vira_uma():
    bruta = _bruta(
        pergunta="  Margem é?\n", explicacao=" Porque c. ", alternativas=[" a ", "b\n  com quebra", "c"]
    )
    [pergunta] = interpretar_perguntas({"perguntas": [bruta]}, {NEGOCIOS})
    assert pergunta.pergunta == "Margem é?" and pergunta.explicacao == "Porque c."
    assert pergunta.alternativas == ("a", "b com quebra", "c")


@pytest.mark.parametrize(
    "extras",
    [
        {"aula": "outra-aula"},
        {"aula": ""},
        {"alternativas": ["a", "b"]},
        {"alternativas": ["a", "b", "c", "d", "e"]},
        {"alternativas": []},
        {"alternativas": "a, b, c"},
        {"alternativas": ["a", "b", ""]},
        {"alternativas": ["a", "b", 3]},
        {"alternativas": ["a", "b", "B"]},
        {"certa": -1},
        {"certa": 3},
        {"certa": 99},
        {"certa": 1.0},
        {"certa": True},
        {"certa": "1"},
        {"certa": None},
        {"pergunta": ""},
        {"pergunta": "   "},
        {"pergunta": None},
        {"explicacao": ""},
        {"explicacao": "  "},
        {"explicacao": 3},
    ],
)
def test_pergunta_fora_do_formato_e_descartada(extras):
    assert interpretar_perguntas({"perguntas": [_bruta(**extras)]}, {NEGOCIOS}) == ()


@pytest.mark.parametrize("dados", [{}, {"perguntas": None}, {"perguntas": "x"}, {"perguntas": [None, 3, "x", []]}])
def test_dados_sem_lista_de_perguntas_dao_nada(dados):
    assert interpretar_perguntas(dados, {NEGOCIOS}) == ()


def test_a_boa_fica_quando_a_vizinha_e_descartada():
    dados = {"perguntas": [_bruta(certa=7), _bruta(CARROS, pergunta="Turbo é?"), _bruta(pergunta="")]}
    assert [q.aula for q in interpretar_perguntas(dados, {NEGOCIOS, CARROS})] == [CARROS]


def test_ordem_das_perguntas_e_a_que_o_claude_devolveu():
    dados = {"perguntas": [_bruta(CARROS, pergunta="2"), _bruta(NEGOCIOS, pergunta="1")]}
    assert [q.pergunta for q in interpretar_perguntas(dados, {NEGOCIOS, CARROS})] == ["2", "1"]


# --- o pedido e o esquema --------------------------------------------------------------------


def test_o_pedido_leva_o_id_o_titulo_e_o_texto_de_cada_aula():
    pedido = montar_pedido_do_quiz(AULAS)
    for aula in AULAS:
        assert aula.id in pedido and aula.titulo in pedido and aula.texto in pedido
    assert pedido.index(NEGOCIOS) < pedido.index(CARROS)


def test_o_pedido_nao_leva_o_que_nao_e_da_aula():
    aula = Aula("T", "Texto", ("https://exemplo.com/fonte-secreta",), "- 2026-10-06 — negócios: x", id=NEGOCIOS)
    pedido = montar_pedido_do_quiz([aula])
    assert "fonte-secreta" not in pedido and "negócios: x" not in pedido


def test_as_regras_estao_no_prompt():
    for trecho in ("português", "uma pergunta", "3 ou 4", "texto da aula", "explicação", "plausíve"):
        assert trecho in SISTEMA_QUIZ


def test_esquema_do_quiz():
    item = ESQUEMA_DO_QUIZ["properties"]["perguntas"]["items"]
    assert ESQUEMA_DO_QUIZ["required"] == ["perguntas"] and ESQUEMA_DO_QUIZ["additionalProperties"] is False
    assert set(item["properties"]) == {"aula", "pergunta", "alternativas", "certa", "explicacao"}
    assert set(item["required"]) == set(item["properties"])
    assert item["additionalProperties"] is False
    assert item["properties"]["alternativas"]["type"] == "array"
    assert item["properties"]["certa"]["type"] == "integer"


# --- a chamada ---------------------------------------------------------------------------------


def test_quiz_sem_ferramentas_e_com_saida_estruturada():
    quiz = QuizGravada(
        [_resultado(structured_output={"perguntas": [_bruta(), _bruta(CARROS, pergunta="Turbo é?")]}, total_cost_usd=0.03)]
    )

    resultado = quiz.perguntar(AULAS)

    opcoes = quiz.opcoes[0]
    assert opcoes.system_prompt == SISTEMA_QUIZ
    assert opcoes.tools == [] and opcoes.allowed_tools == []
    assert opcoes.max_turns == 4
    assert opcoes.output_format == {"type": "json_schema", "schema": ESQUEMA_DO_QUIZ}
    assert opcoes.permission_mode == "dontAsk"
    assert quiz.timeout_s == 240
    assert quiz.prompts == [montar_pedido_do_quiz(AULAS)]
    assert [q.aula for q in resultado.perguntas] == [NEGOCIOS, CARROS]
    assert resultado.medida.custo_usd == pytest.approx(0.03)


def test_etapa_e_erro_do_adaptador():
    assert QuizClaude.etapa == "quiz" and QuizClaude.erro is ErroDeQuiz


def test_o_modelo_e_o_cli_vao_nas_opcoes():
    quiz = QuizGravada([_resultado(structured_output={"perguntas": [_bruta()]})], modelo="sonnet", cli=r"D:\claude\claude.exe")
    quiz.perguntar(AULAS)
    assert quiz.opcoes[0].model == "sonnet" and quiz.opcoes[0].cli_path == r"D:\claude\claude.exe"


def test_pergunta_de_aula_que_nao_foi_enviada_e_descartada():
    quiz = QuizGravada([_resultado(structured_output={"perguntas": [_bruta(), _bruta("2026-09-01-negocios")]})])
    assert [q.aula for q in quiz.perguntar([_aula(NEGOCIOS)]).perguntas] == [NEGOCIOS]


def test_sem_aulas_o_claude_nem_e_chamado():
    quiz = QuizGravada([_resultado(structured_output={"perguntas": [_bruta()]})])

    resultado = quiz.perguntar([])

    assert resultado == PerguntasNovas()
    assert quiz.prompts == [] and quiz.opcoes == []


def test_sem_aulas_nem_confere_a_credencial(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-paga-de-teste")
    assert QuizGravada([]).perguntar([]) == PerguntasNovas()


def test_sem_saida_estruturada_vira_erro_de_quiz():
    quiz = QuizGravada([_texto("Não consegui."), _resultado(result="Não consegui.")])

    with pytest.raises(ErroDeQuiz, match="saída estruturada"):
        quiz.perguntar(AULAS)


def test_saida_estruturada_que_nao_e_objeto_vira_erro_de_quiz():
    quiz = QuizGravada([_resultado(structured_output=["perguntas"])])

    with pytest.raises(ErroDeQuiz, match="saída estruturada"):
        quiz.perguntar(AULAS)


def test_todas_as_perguntas_descartadas_viram_erro_de_quiz():
    quiz = QuizGravada([_resultado(structured_output={"perguntas": [_bruta(certa=9), _bruta("outra")]})])

    with pytest.raises(ErroDeQuiz, match="descartadas"):
        quiz.perguntar(AULAS)


def test_api_key_paga_no_ambiente_recusa_antes_de_chamar(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-paga-de-teste")
    quiz = QuizGravada([_resultado(structured_output={"perguntas": [_bruta()]})])

    with pytest.raises(ErroDeQuiz, match="OAuth"):
        quiz.perguntar(AULAS)

    assert quiz.prompts == []


def test_falha_do_sdk_vira_erro_de_quiz():
    quiz = QuizGravada([CLIConnectionError("CLI sumiu")])

    with pytest.raises(ErroDeQuiz, match="CLIConnectionError"):
        quiz.perguntar(AULAS)


def test_tempo_esgotado_vira_erro_de_quiz():
    quiz = QuizGravada(["dormir"], timeout_s=0.05)

    with pytest.raises(ErroDeQuiz, match="não terminou"):
        quiz.perguntar(AULAS)


def test_resultado_em_erro_vira_erro_de_quiz():
    quiz = QuizGravada([_resultado(is_error=True, subtype="error_during_execution", result="deu ruim")])

    with pytest.raises(ErroDeQuiz, match="deu ruim"):
        quiz.perguntar(AULAS)
