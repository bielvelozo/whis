"""Os fakes das três portas do Claude no jornal: o que o `--fakes` e a costura recebem."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from whis.esquema import validar_esquema
from whis.fakes import URL_DO_JORNAL_FAKE, EditorFake, FormacaoFake, MarcacoesFake, PublicacaoFake, QuizFake
from whis.portas import (
    Candidato,
    ErroDeEditor,
    ErroDeFormacao,
    ErroDeMarcacoes,
    ErroDePublicacao,
    ErroDeQuiz,
    PortaEditor,
    PortaFormacao,
    PortaMarcacoes,
    PortaPublicacao,
    PortaQuiz,
)

DIA = date(2026, 9, 25)


def _candidato(id: str, secao: str, fonte: str) -> Candidato:
    return Candidato(
        id=id, secao=secao, fonte=fonte, titulo=f"Título {id}", link=f"https://exemplo.com/{id}", resumo=f"Resumo {id}."
    )


CANDIDATOS = {
    "brasil": (
        _candidato("brasil-1", "brasil", "Folha Poder"),
        _candidato("brasil-2", "brasil", "Folha Poder"),
        _candidato("brasil-3", "brasil", "Folha Poder"),
        _candidato("brasil-4", "brasil", "G1 Política"),
        _candidato("brasil-5", "brasil", "Poder360"),
    ),
    "carros": (_candidato("carros-1", "carros", "Carscoops"),),
    "mundo": (),
}
TIME = tuple(_candidato(f"time-{n}", "time", "Corinthians") for n in range(1, 4))


def test_os_fakes_cumprem_as_portas():
    assert isinstance(EditorFake(), PortaEditor)
    assert isinstance(FormacaoFake(), PortaFormacao)
    assert isinstance(PublicacaoFake(), PortaPublicacao)


def test_editor_fake_escolhe_o_minimo_com_titulo_marcado():
    escolha = EditorFake().escolher(CANDIDATOS, {"brasil": (3, 5), "carros": (2, 3), "mundo": (3, 5)}, TIME)

    assert [item.candidato.id for item in escolha.secoes["carros"]] == ["carros-1"]
    assert escolha.secoes["mundo"] == ()
    assert all(item.titulo.startswith("[fake] ") for item in escolha.secoes["brasil"])
    assert escolha.secoes["brasil"][0].resumo == "Resumo brasil-1."


def test_editor_fake_respeita_dois_da_mesma_fonte():
    escolha = EditorFake().escolher(CANDIDATOS, {"brasil": (3, 5)}, ())

    assert [item.candidato.id for item in escolha.secoes["brasil"]] == ["brasil-1", "brasil-2", "brasil-4"]


def test_editor_fake_devolve_ate_dois_do_time_e_medida_com_plano():
    escolha = EditorFake().escolher(CANDIDATOS, {}, TIME)

    assert [item.candidato.id for item in escolha.time] == ["time-1", "time-2"]
    assert escolha.medida.custo_usd is not None
    assert escolha.medida.plano_primeiro is not None and escolha.medida.plano_ultimo is not None


def test_editor_fake_guarda_o_que_recebeu_e_pode_falhar():
    editor = EditorFake(erro=ErroDeEditor("fora do ar"))

    with pytest.raises(ErroDeEditor):
        editor.escolher(CANDIDATOS, {"brasil": (3, 5)}, TIME)

    assert editor.candidatos_recebidos == CANDIDATOS
    assert editor.limites_recebidos == {"brasil": (3, 5)}
    assert editor.time_recebido == TIME


def test_formacao_fake_ensina_uma_de_negocios_e_duas_de_carro_com_url():
    formacao = FormacaoFake().ensinar(DIA, "- 2026-09-24 — carros: o que é JDM\n")

    assert formacao.negocios is not None
    assert len(formacao.carros) == 2
    assert all(aula.fontes and aula.fontes[0].startswith("https://") for aula in formacao.aulas())
    assert all(aula.trilha.startswith("- 2026-09-25 — ") for aula in formacao.aulas())
    assert formacao.medida.plano_ultimo is not None


def test_formacao_fake_guarda_a_trilha_e_pode_falhar():
    formacao = FormacaoFake(erro=ErroDeFormacao("sem busca"))

    with pytest.raises(ErroDeFormacao):
        formacao.ensinar(DIA, "trilha de ontem")

    assert formacao.data_recebida == DIA
    assert formacao.trilha_recebida == "trilha de ontem"


def test_publicacao_fake_devolve_a_url_fixa_e_guarda_o_que_recebeu(tmp_path: Path):
    html = tmp_path / "jornal.html"
    html.write_text("<title>Jornal do Whis</title>", encoding="utf-8")
    capas = {"img/1.jpg": tmp_path / "img" / "1.jpg"}
    publicacao = PublicacaoFake()

    feita = publicacao.publicar(html, capas, "https://claude.ai/artifact/ontem")
    html.unlink()

    assert feita.url == URL_DO_JORNAL_FAKE == "https://claude.ai/artifact/fake-jornal"
    assert feita.medida.custo_usd is not None
    assert publicacao.html == html
    assert publicacao.capas == capas
    assert publicacao.url_recebida == "https://claude.ai/artifact/ontem"
    assert publicacao.pagina == "<title>Jornal do Whis</title>"


def test_publicacao_fake_pode_falhar(tmp_path: Path):
    html = tmp_path / "jornal.html"
    html.write_text("<html></html>", encoding="utf-8")

    with pytest.raises(ErroDePublicacao):
        PublicacaoFake(erro=ErroDePublicacao("sem rede")).publicar(html, {}, None)


def test_formacao_fake_respeita_as_vagas_e_traz_um_esquema_valido():
    formacao = FormacaoFake().ensinar(DIA, "", {"negocios": 0, "carros": 1})

    assert formacao.negocios is None and len(formacao.carros) == 1
    completa = FormacaoFake().ensinar(DIA, "")
    assert validar_esquema(completa.negocios.esquema) == completa.negocios.esquema


def test_marcacoes_fake_devolve_o_que_recebeu_e_pode_falhar():
    marcacoes = MarcacoesFake(leituras={"2026-09-25-negocios": "x"})

    assert marcacoes.ler("url", leituras_desde="2026-09-25", quizzes=[]).leituras == {"2026-09-25-negocios": "x"}
    assert marcacoes.chamadas == [("url", "2026-09-25", ())]
    assert isinstance(marcacoes, PortaMarcacoes)
    with pytest.raises(ErroDeMarcacoes):
        MarcacoesFake(erro=ErroDeMarcacoes("x")).ler("url", leituras_desde=None, quizzes=["2026-09-26"])


def test_quiz_fake_faz_uma_pergunta_por_aula():
    aula = FormacaoFake().ensinar(DIA, "").negocios

    perguntas = QuizFake().perguntar([replace(aula, id="2026-09-25-negocios")]).perguntas

    assert [(p.aula, len(p.alternativas), p.certa) for p in perguntas] == [("2026-09-25-negocios", 3, 1)]
    assert isinstance(QuizFake(), PortaQuiz)
    with pytest.raises(ErroDeQuiz):
        QuizFake(erro=ErroDeQuiz("x")).perguntar([aula])
