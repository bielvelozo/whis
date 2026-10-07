"""O deck nos arquivos do tipo Slides: um `<section>` por arquivo e o `deck.json`."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

import pytest

from whis.deck import Deck, ItemDoSlide, Slide, montar_deck
from whis.nota_viva import NotaViva
from whis.slides_do_deck import ACENTO, CAMINHO_DO_INDICE, slides_do_deck

HOJE = date(2026, 9, 30)
AGORA = datetime(2026, 9, 30, 16, 55, tzinfo=timezone.utc)
PERMITIDAS = {"section", "div", "h2", "ul", "li", "p", "b", "i", "a", "span"}


def deck_de(*itens: ItemDoSlide) -> Deck:
    return Deck(slides=(Slide("fiz", "O que eu fiz", "O que eu fiz", tuple(itens)),))


def html_de(*textos: str) -> str:
    deck = deck_de(*(ItemDoSlide(texto) for texto in textos))
    return slides_do_deck(deck, HOJE, agora=AGORA)["project/slides/fiz.html"]


def arquivos_de(texto_da_nota: str) -> dict[str, str]:
    return slides_do_deck(montar_deck(NotaViva.de_texto(texto_da_nota)), HOJE, agora=AGORA)


def test_um_arquivo_por_slide_com_um_section_de_id_igual_ao_nome():
    arquivos = arquivos_de("## O que eu fiz\n\n- a\n\n## Pontos\n\n- b\n")

    assert sorted(arquivos) == ["project/deck.json", "project/slides/fiz.html", "project/slides/pontos.html"]
    for id_ in ("fiz", "pontos"):
        conteudo = arquivos[f"project/slides/{id_}.html"]
        assert conteudo.startswith(f'<section id="{id_}" ')
        assert conteudo.count("<section") == 1
        assert conteudo.rstrip().endswith("</section>")


def test_so_elementos_e_estilos_que_o_tipo_slides_aceita():
    conteudo = html_de("**a** *b* `c` [d](https://e.com) [[f|g]]", "texto")

    assert set(re.findall(r"</?([a-zA-Z0-9-]+)", conteudo)) <= PERMITIDAS
    for estilo in re.findall(r'style="([^"]*)"', conteudo):
        for fora_do_subconjunto in ("margin", "var(", "z-index", "padding-left", "padding-top"):
            assert fora_do_subconjunto not in estilo
        assert not re.search(r"\d(\.\d+)?em\b", estilo)
    assert "<ul" not in "".join(re.findall(r"<li>(.*?)</li>", conteudo)), "lista aninhada não existe no tipo"
    assert "class=" not in conteudo and "<style" not in conteudo
    assert all(int(tamanho) >= 24 for tamanho in re.findall(r"font-size:(\d+)px", conteudo))


def test_html_da_nota_sai_escapado():
    conteudo = html_de('<script>alert(1)</script> & "aspas"')

    assert "<script" not in conteudo
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;aspas&quot;" in conteudo


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("**feito**", "<b>feito</b>"),
        ("*quase*", "<i>quase</i>"),
        ("_quase_", "<i>quase</i>"),
        ("nome_de_funcao_x", "nome_de_funcao_x"),
        ("`git push`", f'<span style="color:{ACENTO}">git push</span>'),
        ("[PR](https://github.com/x/y/pull/1)", '<a href="https://github.com/x/y/pull/1">PR</a>'),
        ("[[notas/frete|frete]]", "frete"),
        ("[[frete]]", "frete"),
        ("[x](javascript:alert(1))", "[x](javascript:alert(1))"),
    ],
)
def test_markdown_simples_vira_formatacao(texto: str, esperado: str):
    assert f"<li>{esperado}</li>" in html_de(texto)


def test_sub_item_e_uma_lista_irma_mais_recuada_e_menor():
    conteudo = slides_do_deck(
        deck_de(ItemDoSlide("pai"), ItemDoSlide("filho", 1)), HOJE, agora=AGORA
    )["project/slides/fiz.html"]

    pai, filho = re.findall(r'<ul style="padding:0 0 0 (\d+)px;font-size:(\d+)px', conteudo)
    assert int(filho[0]) > int(pai[0]) and int(filho[1]) < int(pai[1])
    assert "<li>pai</li></ul>" in conteudo


def test_rodape_com_a_data_por_extenso_e_a_pagina():
    arquivos = arquivos_de("## O que eu fiz\n\n- a\n\n## Pontos\n\n- b\n")

    assert "Daily · 30 de setembro de 2026 (quarta-feira) · 1/2" in arquivos["project/slides/fiz.html"]
    assert "· 2/2" in arquivos["project/slides/pontos.html"]


def test_o_indice_segue_o_formato_do_tipo():
    linhas = "\n".join(f"- item {n}" for n in range(12))
    arquivos = arquivos_de(f"## O que eu fiz\n\n{linhas}\n\n## Pontos\n\n- b\n")

    indice = json.loads(arquivos[CAMINHO_DO_INDICE])
    assert indice["v"] == 4 and indice["lists"] == "css" and indice["title"] == "Daily"
    assert indice["createdOnFiles"] == {"v": 1, "at": "2026-09-30T16:55:00Z"}
    assert indice["order"] == ["fiz", "fiz-2", "pontos"]
    assert indice["cover"] == "fiz"
    assert indice["sections"] == {
        "fiz": {"description": "O que eu fiz", "start": "fiz"},
        "pontos": {"description": "Pontos", "start": "pontos"},
    }
    assert indice["designSystems"] == []
    [face] = indice["faces"].values()
    assert face["href"].startswith("https://fonts.googleapis.com/css2?")
    assert sorted(arquivos) == sorted([CAMINHO_DO_INDICE, *(f"project/slides/{i}.html" for i in indice["order"])])


def test_deck_vazio_nao_tem_arquivo():
    assert slides_do_deck(Deck(), HOJE, agora=AGORA) == {}
