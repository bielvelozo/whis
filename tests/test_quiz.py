"""O quiz da semana no vault: a nota ida e volta, as respostas viram resultado e o erro volta no sábado seguinte."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from whis.aulas import NotaDeAula
from whis.portas import Aula, PerguntaNova, Resposta
from whis.quiz import (
    PASTA_DOS_QUIZZES,
    Pergunta,
    QuizDaSemana,
    aplicar_respostas,
    atrasadas,
    aulas_do_quiz,
    escrever_quiz,
    ler_nota_do_quiz,
    ler_quizzes,
    montar_nota_do_quiz,
    novo_quiz,
)


def p(id_, aula="2026-10-06-negocios", resultado="", origem="", **extras) -> Pergunta:
    campos = dict(
        id=id_,
        aula=aula,
        pergunta="O que é margem?",
        alternativas=("A", "B", "C"),
        certa=1,
        explicacao="Porque sim.",
        origem=origem,
        resultado=resultado,
    )
    return Pergunta(**{**campos, **extras})


def quiz(data: date, *perguntas: Pergunta, aviso: str = "") -> QuizDaSemana:
    return QuizDaSemana(data, tuple(perguntas), aviso=aviso)


def nota_de_aula(id_: str, status="lida", q="") -> NotaDeAula:
    area = "negocios" if id_.endswith("negocios") else "carros"
    aula = Aula("Titulo", "texto", ("https://exemplo.com",), "", id=id_)
    return NotaDeAula(id=id_, area=area, data=date.fromisoformat(id_[:10]), status=status, aula=aula, quiz=q)


# --- a nota: ida e volta ----------------------------------------------------------------


def test_ida_e_volta_da_nota_do_quiz():
    original = QuizDaSemana(
        date(2026, 10, 10),
        (p("2026-10-10-q1", resultado="errada"), p("2026-10-10-q2", origem="2026-10-03-q4")),
    )
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_ida_e_volta_com_tudo_que_complica_o_formato():
    exotica = Pergunta(
        id="2026-10-10-q1",
        aula="2026-10-06-carros-2",
        pergunta='Qual é o "slip angle"?\nResponda: em graus, # sem pensar.',
        alternativas=("Um ângulo: o do pneu ✓", "Uma # coisa", "Nada ✓", "", "  com espaços  "),
        certa=2,
        explicacao="Linha 1.\n\nLinha 3: depois de um espaço em branco.\nResultado do que importa: nada.",
        origem="2026-10-03-q10",
        resultado="sem resposta",
    )
    original = QuizDaSemana(date(2026, 10, 10), (exotica, p("2026-10-10-q2", resultado="certa")))
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_ida_e_volta_de_explicacao_e_resultado_vazios():
    original = quiz(date(2026, 10, 10), p("2026-10-10-q1", explicacao="", resultado=""))
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_ida_e_volta_com_aviso_e_sem_perguntas():
    original = quiz(date(2026, 10, 10), aviso="Nenhuma aula lida desde o último quiz. O quiz volta no próximo sábado.")
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_ida_e_volta_com_aviso_de_varias_linhas_antes_das_perguntas():
    original = quiz(date(2026, 10, 10), p("2026-10-10-q1"), aviso="quiz novo indisponível hoje\n\n> e mais: isto")
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_ida_e_volta_com_o_texto_do_quiz_com_quebra_de_linha_do_windows():
    original = quiz(date(2026, 10, 10), p("2026-10-10-q1"), aviso="aviso")
    assert ler_nota_do_quiz(montar_nota_do_quiz(original).replace("\n", "\r\n")) == original


def test_alternativas_e_perguntas_voltam_como_tuplas():
    lido = ler_nota_do_quiz(montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1"))))
    assert isinstance(lido.perguntas, tuple) and isinstance(lido.perguntas[0].alternativas, tuple)


def test_formato_da_nota():
    texto = montar_nota_do_quiz(
        quiz(date(2026, 10, 10), p("2026-10-10-q1", resultado="errada", origem="2026-10-03-q4"))
    )
    assert texto.startswith("---\ntipo: quiz\ndata: 2026-10-10\n---\n")
    assert "## 1. O que é margem?\n" in texto
    assert "<!-- id: 2026-10-10-q1 · aula: 2026-10-06-negocios · origem: 2026-10-03-q4 · certa: 1 -->" in texto
    assert "- a) A\n- b) B ✓\n- c) C\n" in texto
    assert "Explicação: Porque sim.\nResultado: errada" in texto


def test_aviso_vai_numa_linha_propria_antes_das_perguntas():
    texto = montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1"), aviso="quiz novo indisponível hoje"))
    assert "\n> quiz novo indisponível hoje\n" in texto
    assert texto.index("> quiz novo") < texto.index("## 1.")


def test_a_certa_vem_do_comentario():
    texto = montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1")))
    [lida] = ler_nota_do_quiz(texto.replace("certa: 1", "certa: 2")).perguntas
    assert lida.certa == 2


def test_sem_o_comentario_a_certa_e_a_do_visto():
    texto = montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1")))
    sem_certa = texto.replace(" · certa: 1", "")
    [lida] = ler_nota_do_quiz(sem_certa).perguntas
    assert lida.certa == 1


def test_pergunta_sem_o_comentario_e_pulada_e_as_outras_ficam():
    boa = montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1"), p("2026-10-10-q2")))
    estragada = boa.replace("<!-- id: 2026-10-10-q1 · ", "<!-- ")
    assert [x.id for x in ler_nota_do_quiz(estragada).perguntas] == ["2026-10-10-q2"]


def test_o_que_nao_e_quiz_nao_e_nota_de_quiz():
    texto = montar_nota_do_quiz(quiz(date(2026, 10, 10), p("2026-10-10-q1")))
    assert ler_nota_do_quiz(texto.replace("tipo: quiz", "tipo: aula")) is None
    assert ler_nota_do_quiz(texto.replace("data: 2026-10-10", "data: sábado")) is None
    assert ler_nota_do_quiz("") is None
    assert ler_nota_do_quiz("# só um título\n") is None


# --- ler e escrever no vault -------------------------------------------------------------


def test_escrever_quiz_grava_na_pasta_dos_quizzes_com_a_data_no_nome(tmp_path):
    original = quiz(date(2026, 10, 10), p("2026-10-10-q1"))
    caminho = escrever_quiz(tmp_path, original)
    assert caminho == (tmp_path / PASTA_DOS_QUIZZES / "2026-10-10.md").resolve()
    assert ler_nota_do_quiz(caminho.read_text("utf-8")) == original


def test_ler_quizzes_vem_por_data(tmp_path):
    for data in (date(2026, 10, 17), date(2026, 10, 3), date(2026, 10, 10)):
        escrever_quiz(tmp_path, quiz(data, p(f"{data}-q1")))
    assert [q.data for q in ler_quizzes(tmp_path)] == [date(2026, 10, 3), date(2026, 10, 10), date(2026, 10, 17)]


def test_ler_quizzes_sem_pasta_e_vazio(tmp_path):
    assert ler_quizzes(tmp_path) == []


def test_ler_quizzes_ignora_o_que_nao_e_quiz(tmp_path):
    escrever_quiz(tmp_path, quiz(date(2026, 10, 10), p("2026-10-10-q1")))
    (tmp_path / PASTA_DOS_QUIZZES / "anotacao.md").write_text("# nada a ver\n", encoding="utf-8")
    assert [q.data for q in ler_quizzes(tmp_path)] == [date(2026, 10, 10)]


def test_escrever_de_novo_substitui_o_quiz_do_dia(tmp_path):
    escrever_quiz(tmp_path, quiz(date(2026, 10, 10), p("2026-10-10-q1")))
    escrever_quiz(tmp_path, quiz(date(2026, 10, 10), p("2026-10-10-q1", resultado="certa")))
    [lido] = ler_quizzes(tmp_path)
    assert lido.perguntas[0].resultado == "certa"


# --- as respostas viram resultado --------------------------------------------------------


def test_respostas_viram_resultado_e_o_vazio_de_quiz_passado_vira_sem_resposta():
    q = quiz(date(2026, 10, 10), p("2026-10-10-q1"), p("2026-10-10-q2"))
    [novo] = aplicar_respostas([q], {"2026-10-10-q1": Resposta(1, True)}, hoje=date(2026, 10, 11))
    assert [x.resultado for x in novo.perguntas] == ["certa", "sem resposta"]


def test_resposta_errada_vira_errada():
    q = quiz(date(2026, 10, 10), p("2026-10-10-q1"))
    [novo] = aplicar_respostas([q], {"2026-10-10-q1": Resposta(0, False)}, hoje=date(2026, 10, 10))
    assert novo.perguntas[0].resultado == "errada"


def test_no_proprio_sabado_o_vazio_continua_vazio():
    q = quiz(date(2026, 10, 10), p("2026-10-10-q1"))
    [novo] = aplicar_respostas([q], {}, hoje=date(2026, 10, 10))
    assert novo.perguntas[0].resultado == ""


def test_quiz_sem_mudanca_volta_a_mesma_instancia():
    fechado = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="certa"), p("2026-10-03-q2", resultado="errada"))
    aberto = quiz(date(2026, 10, 10), p("2026-10-10-q1"))
    novos = aplicar_respostas([fechado, aberto], {}, hoje=date(2026, 10, 10))
    assert novos[0] is fechado and novos[1] is aberto


def test_so_o_quiz_que_mudou_vira_outra_instancia():
    antigo = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="certa"))
    atual = quiz(date(2026, 10, 10), p("2026-10-10-q1"))
    novos = aplicar_respostas([antigo, atual], {"2026-10-10-q1": Resposta(2, False)}, hoje=date(2026, 10, 10))
    assert novos[0] is antigo and novos[1] is not atual and novos[1].perguntas[0].resultado == "errada"


def test_a_resposta_vale_mais_que_o_sem_resposta_que_ja_estava():
    q = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="sem resposta"))
    [novo] = aplicar_respostas([q], {"2026-10-03-q1": Resposta(1, True)}, hoje=date(2026, 10, 17))
    assert novo.perguntas[0].resultado == "certa"


def test_resultado_que_ja_estava_fica_sem_resposta_nova():
    q = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="errada"))
    [novo] = aplicar_respostas([q], {}, hoje=date(2026, 10, 17))
    assert novo is q


def test_aplicar_respostas_guarda_o_aviso_e_o_resto_da_pergunta():
    q = quiz(date(2026, 10, 10), p("2026-10-10-q1", origem="2026-10-03-q1"), aviso="aviso")
    [novo] = aplicar_respostas([q], {"2026-10-10-q1": Resposta(1, True)}, hoje=date(2026, 10, 11))
    assert novo.aviso == "aviso"
    assert novo.perguntas[0] == replace(q.perguntas[0], resultado="certa")


def test_aplicar_respostas_sem_quizzes():
    assert aplicar_respostas([], {"x": Resposta(0, True)}, hoje=date(2026, 10, 10)) == []


# --- as atrasadas -----------------------------------------------------------------------


def test_atrasadas_sao_as_erradas_e_sem_resposta_ainda_nao_acertadas():
    q1 = quiz(
        date(2026, 10, 3),
        p("2026-10-03-q1", resultado="errada"),
        p("2026-10-03-q2", resultado="certa"),
        p("2026-10-03-q3", resultado="sem resposta"),
    )
    q2 = quiz(
        date(2026, 10, 10),
        p("2026-10-10-q1", origem="2026-10-03-q1", resultado="certa"),
        p("2026-10-10-q2", origem="2026-10-03-q3", resultado="errada"),
    )
    [a] = atrasadas([q1, q2], date(2026, 10, 17))
    assert a.origem == "2026-10-03-q3" and a.resultado == "" and a.id == ""


def test_atrasadas_tem_teto_de_dez_mais_antigas_primeiro():
    q = quiz(date(2026, 10, 3), *[p(f"2026-10-03-q{n}", resultado="errada") for n in range(1, 13)])
    lista = atrasadas([q], date(2026, 10, 10))
    assert [a.origem for a in lista] == [f"2026-10-03-q{n}" for n in range(1, 11)]


def test_o_limite_vem_do_chamador():
    q = quiz(date(2026, 10, 3), *[p(f"2026-10-03-q{n}", resultado="errada") for n in range(1, 6)])
    assert len(atrasadas([q], date(2026, 10, 10), limite=3)) == 3
    assert atrasadas([q], date(2026, 10, 10), limite=0) == []


def test_a_ordem_e_a_da_primeira_vez_que_a_pergunta_apareceu():
    antigo = quiz(date(2026, 9, 26), p("2026-09-26-q2", resultado="errada"))
    recente = quiz(
        date(2026, 10, 3),
        p("2026-10-03-q1", resultado="errada"),
        p("2026-10-03-q2", origem="2026-09-26-q2", resultado="errada"),
    )
    assert [a.origem for a in atrasadas([recente, antigo], date(2026, 10, 10))] == [
        "2026-09-26-q2",
        "2026-10-03-q1",
    ]


def test_atrasadas_devolve_o_texto_da_versao_mais_recente():
    q1 = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="errada", pergunta="texto velho"))
    q2 = quiz(date(2026, 10, 10), p("2026-10-10-q1", origem="2026-10-03-q1", resultado="errada", pergunta="texto novo"))
    [a] = atrasadas([q1, q2], date(2026, 10, 17))
    assert a.pergunta == "texto novo" and a.origem == "2026-10-03-q1"


def test_pergunta_acertada_em_qualquer_versao_sai_da_fila():
    q1 = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="errada"))
    q2 = quiz(date(2026, 10, 10), p("2026-10-10-q1", origem="2026-10-03-q1", resultado="errada"))
    q3 = quiz(date(2026, 10, 17), p("2026-10-17-q1", origem="2026-10-03-q1", resultado="certa"))
    assert atrasadas([q1, q2, q3], date(2026, 10, 24)) == []


def test_so_entram_os_quizzes_anteriores_a_hoje():
    ontem = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="errada"))
    hoje = quiz(date(2026, 10, 10), p("2026-10-10-q1", resultado="errada"))
    futuro = quiz(date(2026, 10, 17), p("2026-10-17-q1", resultado="errada"))
    assert [a.origem for a in atrasadas([ontem, hoje, futuro], date(2026, 10, 10))] == ["2026-10-03-q1"]


def test_acerto_de_quiz_futuro_nao_tira_da_fila():
    ontem = quiz(date(2026, 10, 3), p("2026-10-03-q1", resultado="errada"))
    futuro = quiz(date(2026, 10, 17), p("2026-10-17-q1", origem="2026-10-03-q1", resultado="certa"))
    assert len(atrasadas([ontem, futuro], date(2026, 10, 10))) == 1


def test_sem_quiz_nao_ha_atrasada():
    assert atrasadas([], date(2026, 10, 10)) == []


# --- as aulas do quiz --------------------------------------------------------------------


def test_aulas_do_quiz_sao_as_lidas_sem_quiz():
    notas = [
        nota_de_aula("2026-10-06-negocios"),
        nota_de_aula("2026-10-05-carros-1"),
        nota_de_aula("2026-10-05-carros-2", status="pendente"),
        nota_de_aula("2026-10-01-negocios", q="2026-10-03"),
    ]
    assert [n.id for n in aulas_do_quiz(notas)] == ["2026-10-05-carros-1", "2026-10-06-negocios"]


def test_sem_aula_lida_nao_ha_aula_do_quiz():
    assert aulas_do_quiz([nota_de_aula("2026-10-06-negocios", status="pendente")]) == []


# --- o quiz novo -------------------------------------------------------------------------


def nova(aula="2026-10-06-negocios") -> PerguntaNova:
    return PerguntaNova(aula, "Margem é?", ["a", "b", "c"], 2, "porque c")


def test_novo_quiz_numera_novas_e_atrasadas_com_id_do_dia():
    q = novo_quiz(date(2026, 10, 17), novas=[nova()], atrasadas=[p("x", origem="2026-10-03-q3")])
    assert [x.id for x in q.perguntas] == ["2026-10-17-q1", "2026-10-17-q2"]
    assert q.data == date(2026, 10, 17)


def test_pergunta_nova_nasce_sem_origem_nem_resultado():
    [q1] = novo_quiz(date(2026, 10, 17), [nova("2026-10-09-carros-1")], []).perguntas
    assert q1 == Pergunta(
        id="2026-10-17-q1",
        aula="2026-10-09-carros-1",
        pergunta="Margem é?",
        alternativas=("a", "b", "c"),
        certa=2,
        explicacao="porque c",
        origem="",
        resultado="",
    )
    assert isinstance(q1.alternativas, tuple)


def test_atrasada_volta_com_id_novo_texto_igual_e_a_origem():
    antiga = p("2026-10-03-q3", resultado="errada", pergunta="Texto da antiga")
    [volta] = novo_quiz(date(2026, 10, 17), [], [replace(antiga, id="", resultado="", origem="2026-10-03-q3")]).perguntas
    assert volta.id == "2026-10-17-q1" and volta.origem == "2026-10-03-q3" and volta.resultado == ""
    assert (volta.pergunta, volta.alternativas, volta.certa) == (antiga.pergunta, antiga.alternativas, antiga.certa)


def test_atrasada_sem_origem_usa_o_proprio_id_como_origem():
    [volta] = novo_quiz(date(2026, 10, 17), [], [p("2026-10-03-q3", resultado="errada")]).perguntas
    assert volta.origem == "2026-10-03-q3" and volta.resultado == ""


def test_novas_vem_antes_das_atrasadas():
    q = novo_quiz(date(2026, 10, 17), [nova("a"), nova("b")], [p("x", origem="o1"), p("y", origem="o2")])
    assert [(x.aula, x.origem) for x in q.perguntas] == [
        ("a", ""),
        ("b", ""),
        ("2026-10-06-negocios", "o1"),
        ("2026-10-06-negocios", "o2"),
    ]


def test_sem_nada_o_quiz_nasce_vazio():
    q = novo_quiz(date(2026, 10, 17), [], [])
    assert q.perguntas == () and q.aviso == ""


def test_quiz_novo_escrito_e_lido_volta_igual(tmp_path):
    q = novo_quiz(date(2026, 10, 17), [nova()], [p("x", origem="2026-10-03-q3")])
    escrever_quiz(tmp_path, q)
    assert ler_quizzes(tmp_path) == [q]


@pytest.mark.parametrize("n", [0, 1, 3])
def test_numeracao_segue_a_ordem(n):
    q = novo_quiz(date(2026, 10, 17), [nova() for _ in range(n)], [])
    assert [x.id for x in q.perguntas] == [f"2026-10-17-q{i}" for i in range(1, n + 1)]
