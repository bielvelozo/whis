"""O deck da daily: as seções que ele escreveu viram slides, com o texto como está."""

from __future__ import annotations

from whis.deck import ALTURA_DA_LISTA, ItemDoSlide, altura, montar_deck
from whis.nota_viva import NotaViva

NOTA = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "- FN-123 frete corrigido\n"
    "\t- subiu em produção\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "1. FN-130 diário automático\n"
    "\n"
    "## O que terminei\n"
    "\n"
    "- entregue na semana passada\n"
    "\n"
    "## Fazer\n"
    "\n"
    "- [ ] não entra\n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- quem revisa o PR?\n"
    "\n"
    "## Pontos\n"
    "\n"
    "- também não entra\n"
    "\n"
    "## Falar\n"
    "\n"
    "Parágrafo solto\n"
)


def secao(titulo: str, linhas: list[str]) -> NotaViva:
    return NotaViva.de_texto(f"## {titulo}\n\n" + "\n".join(linhas) + "\n")


def test_cada_secao_com_texto_vira_um_slide_na_ordem_do_deck():
    deck = montar_deck(NotaViva.de_texto(NOTA))

    assert [slide.id for slide in deck.slides] == ["fiz", "fazendo", "duvidas", "falar"]
    assert [slide.titulo for slide in deck.slides] == [
        "O que eu fiz",
        "O que estou fazendo",
        "Dúvidas",
        "Falar",
    ]


def test_o_texto_sai_sem_o_marcador_e_com_a_profundidade():
    fiz, fazendo, *_ = montar_deck(NotaViva.de_texto(NOTA)).slides

    assert fiz.itens == (ItemDoSlide("FN-123 frete corrigido", 0), ItemDoSlide("subiu em produção", 1))
    assert fazendo.itens == (ItemDoSlide("FN-130 diário automático", 0),)


def test_paragrafo_solto_entra_como_item_de_nivel_zero():
    falar = montar_deck(NotaViva.de_texto(NOTA)).slides[-1]

    assert falar.itens == (ItemDoSlide("Parágrafo solto", 0),)


def test_recuo_por_espacos_tambem_e_sub_item():
    deck = montar_deck(secao("O que eu fiz", ["- pai", "  - filho", "    - neto"]))

    assert [item.profundidade for item in deck.slides[0].itens] == [0, 1, 2]


def test_pontos_e_fazer_nunca_entram():
    textos = [item.texto for slide in montar_deck(NotaViva.de_texto(NOTA)).slides for item in slide.itens]

    assert not any("não entra" in texto for texto in textos)


def test_o_que_terminei_antiga_nao_vira_slide():
    textos = [item.texto for slide in montar_deck(NotaViva.de_texto(NOTA)).slides for item in slide.itens]

    assert "entregue na semana passada" not in textos


def test_nota_sem_texto_e_deck_vazio():
    assert montar_deck(NotaViva.de_texto("## O que eu fiz\n\n-\n\t1.\n\n## Falar\n")).vazio()


def test_o_deck_guarda_as_linhas_literais_das_secoes_que_viraram_slide():
    deck = montar_deck(NotaViva.de_texto(NOTA))

    assert [secao.titulo for secao in deck.secoes] == ["O que eu fiz", "O que estou fazendo", "Dúvidas", "Falar"]
    assert deck.secoes[0].linhas == ("- FN-123 frete corrigido", "\t- subiu em produção")


def test_secao_que_nao_cabe_continua_em_outro_slide_com_a_contagem():
    deck = montar_deck(secao("O que eu fiz", [f"- item {n}" for n in range(1, 21)]))

    assert [slide.id for slide in deck.slides] == ["fiz", "fiz-2", "fiz-3"]
    assert [slide.titulo for slide in deck.slides] == [
        "O que eu fiz (1/3)",
        "O que eu fiz (2/3)",
        "O que eu fiz (3/3)",
    ]
    assert [item.texto for slide in deck.slides for item in slide.itens] == [f"item {n}" for n in range(1, 21)]
    assert {slide.secao for slide in deck.slides} == {"O que eu fiz"}


def test_sub_item_nao_se_separa_do_pai_quando_o_grupo_cabe():
    linhas = [f"- solto {n}" for n in range(8)] + ["- pai", "\t- filho 1", "\t- filho 2"]

    primeiro, segundo = montar_deck(secao("O que eu fiz", linhas)).slides

    assert [item.texto for item in segundo.itens] == ["pai", "filho 1", "filho 2"]
    assert len(primeiro.itens) == 8


def test_grupo_maior_que_um_slide_e_partido_item_a_item_sem_perder_nada():
    linhas = ["- pai"] + [f"\t- filho {n}" for n in range(15)]

    deck = montar_deck(secao("O que eu fiz", linhas))

    assert [item.texto for slide in deck.slides for item in slide.itens] == ["pai"] + [f"filho {n}" for n in range(15)]
    assert len(deck.slides) == 2


def test_linha_longa_ocupa_mais_altura_e_cabe_menos_por_slide():
    assert altura(ItemDoSlide("x" * 300)) > altura(ItemDoSlide("x"))
    assert sum(altura(ItemDoSlide(f"item {n}")) for n in range(9)) <= ALTURA_DA_LISTA
