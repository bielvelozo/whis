"""`noticias/fontes.md`: criada uma vez a partir do modelo, lida com tolerância."""

from __future__ import annotations

from pathlib import Path

from whis.fontes_do_jornal import (
    CAMINHO_DAS_FONTES,
    MODELO_DAS_FONTES,
    Fonte,
    FonteDoX,
    garantir_fontes,
    interpretar_fontes,
    ler_fontes,
)


def test_o_modelo_tem_as_seis_secoes_e_o_time_sem_musica_nem_nomes():
    fontes = interpretar_fontes(MODELO_DAS_FONTES)

    assert [s.id for s in fontes.secoes] == ["ia", "tecnologia", "mundo", "brasil", "futebol", "carros"]
    assert [s.titulo for s in fontes.secoes][3] == "Política no Brasil"
    assert fontes.time == Fonte("Corinthians", "https://ge.globo.com/rss/ge/futebol/times/corinthians/")
    assert fontes.nomes == ()
    assert fontes.avisos == ()


def test_nomes_de_fonte_com_ponto_e_url_com_query_string_sao_lidos_inteiros():
    fontes = interpretar_fontes(
        "## Música (musica)\n"
        "- YouTube · Nord Keyboards: https://www.youtube.com/feeds/videos.xml?channel_id=UCGrw4WarRRC66qQg8YHhrCw\n"
    )

    assert fontes.secoes[0].fontes == (
        Fonte(
            "YouTube · Nord Keyboards",
            "https://www.youtube.com/feeds/videos.xml?channel_id=UCGrw4WarRRC66qQg8YHhrCw",
        ),
    )


def test_limites_sao_lidos_do_titulo_e_sem_eles_valem_3_a_5():
    fontes = interpretar_fontes(
        "## Música (musica) · 3 a 6 itens\n- A: https://a.example/feed\n"
        "## Carros (carros) · 2 a 3 itens\n- B: https://b.example/feed\n"
        "## Games\n- C: https://c.example/feed\n"
    )

    assert [(s.id, s.minimo, s.maximo) for s in fontes.secoes] == [
        ("musica", 3, 6),
        ("carros", 2, 3),
        ("games", 3, 5),
    ]


def test_secao_nova_vira_secao_do_jornal_com_id_sem_acento_na_ordem_do_arquivo():
    fontes = interpretar_fontes(
        "## Ciência e Saúde · 1 a 2 itens\n- Nature: https://www.nature.com/nature.rss\n"
        + MODELO_DAS_FONTES
    )

    assert fontes.secoes[0].id == "ciencia-e-saude"
    assert fontes.secoes[0].titulo == "Ciência e Saúde"
    assert (fontes.secoes[0].minimo, fontes.secoes[0].maximo) == (1, 2)
    assert len(fontes.secoes) == 7


def test_linha_invalida_e_ignorada_com_aviso(caplog):
    fontes = interpretar_fontes(
        "## Tecnologia (tecnologia)\n"
        "- Ars Technica: https://feeds.arstechnica.com/arstechnica/index\n"
        "- Sem URL nenhuma\n"
        "- FTP: ftp://exemplo.org/feed\n"
        "texto solto\n"
    )

    assert [f.nome for f in fontes.secoes[0].fontes] == ["Ars Technica"]
    assert len(fontes.avisos) == 3
    assert "Sem URL nenhuma" in fontes.avisos[0]
    assert "Sem URL nenhuma" in caplog.text


def test_time_vazio_fica_none_e_nao_vira_secao():
    fontes = interpretar_fontes(
        "## Futebol (futebol)\n- ge: https://ge.globo.com/rss/ge/futebol/\n\n## Time\n\n## Nomes\n"
    )

    assert fontes.time is None
    assert fontes.nomes == ()
    assert [s.id for s in fontes.secoes] == ["futebol"]
    assert fontes.avisos == ()


def test_nomes_podem_quebrar_linha_e_nao_repetem():
    fontes = interpretar_fontes("## Nomes\nNord, Korg,\n  Roland ,korg\n- Kemper\n")

    assert fontes.nomes == ("Nord", "Korg", "Roland", "Kemper")


def test_secao_sem_fonte_valida_fica_fora_com_aviso():
    fontes = interpretar_fontes("## Vazia\n- quebrada\n## Mundo\n- BBC: https://feeds.bbci.co.uk/news/world/rss.xml\n")

    assert [s.id for s in fontes.secoes] == ["mundo"]
    assert any("Vazia" in aviso for aviso in fontes.avisos)


def test_o_modelo_abre_com_dev_com_ia_lida_do_x():
    ia = interpretar_fontes(MODELO_DAS_FONTES).secoes[0]

    assert (ia.id, ia.titulo, ia.minimo, ia.maximo) == ("ia", "Dev com IA", 4, 6)
    assert ia.fontes == ()
    assert [(f.nome, f.tipo) for f in ia.x][:2] == [("X · Seguindo", "seguindo"), ("X · Para você", "para-voce")]
    assert [f.tipo for f in ia.x[2:]] == ["busca"] * 6
    assert ia.x[2] == FonteDoX("X · Claude Code", "busca", '"claude code" min_faves:100')


def test_as_tres_linhas_do_x_viram_fontes_do_x_da_secao():
    fontes = interpretar_fontes(
        "## Dev com IA (ia) · 4 a 6 itens\n"
        "- X · Seguindo: x:seguindo\n"
        "- X · Para você: x:para-voce\n"
        '- X · Claude Code: x:busca "claude code" min_faves:100\n'
        "- Simon Willison: https://simonwillison.net/atom/everything/\n"
    )

    [ia] = fontes.secoes
    assert ia.x == (
        FonteDoX("X · Seguindo", "seguindo"),
        FonteDoX("X · Para você", "para-voce"),
        FonteDoX("X · Claude Code", "busca", '"claude code" min_faves:100'),
    )
    assert ia.fontes == (Fonte("Simon Willison", "https://simonwillison.net/atom/everything/"),)
    assert fontes.avisos == ()


def test_secao_so_com_linhas_do_x_e_valida():
    fontes = interpretar_fontes("## Dev com IA (ia)\n- X · Seguindo: x:seguindo\n")

    assert [s.id for s in fontes.secoes] == ["ia"]
    assert fontes.avisos == ()


def test_linha_do_x_fora_de_ia_fica_na_secao_em_que_esta():
    fontes = interpretar_fontes(
        "## Tecnologia (tecnologia)\n- HN: https://news.ycombinator.com/rss\n- X · Rust: x:busca rust min_faves:50\n"
    )

    assert fontes.secoes[0].x == (FonteDoX("X · Rust", "busca", "rust min_faves:50"),)


def test_linha_do_x_com_tipo_desconhecido_ou_busca_vazia_vira_aviso():
    fontes = interpretar_fontes("## Dev com IA (ia)\n- A: x:qualquer\n- B: x:busca\n- C: x:seguindo\n")

    assert [f.nome for f in fontes.secoes[0].x] == ["C"]
    assert len(fontes.avisos) == 2
    assert "x:qualquer" in fontes.avisos[0]
    assert "x:busca" in fontes.avisos[1]


def test_linha_do_x_no_time_e_ignorada_com_aviso():
    fontes = interpretar_fontes("## Time\n- Corinthians: x:busca corinthians\n")

    assert fontes.time is None
    assert len(fontes.avisos) == 1


def test_fontes_md_e_criado_uma_vez_com_o_modelo(tmp_path: Path):
    vault = tmp_path / "vault"

    caminho = garantir_fontes(vault)

    assert caminho == vault / CAMINHO_DAS_FONTES
    assert caminho.read_text(encoding="utf-8") == MODELO_DAS_FONTES


def test_fontes_md_editado_nunca_e_reescrito(tmp_path: Path):
    vault = tmp_path / "vault"
    caminho = garantir_fontes(vault)
    caminho.write_text("## Só isto\n- Uma: https://uma.example/feed\n", encoding="utf-8")

    fontes = ler_fontes(vault)
    garantir_fontes(vault)

    assert caminho.read_text(encoding="utf-8") == "## Só isto\n- Uma: https://uma.example/feed\n"
    assert [s.id for s in fontes.secoes] == ["so-isto"]


def test_fontes_md_vazio_tambem_nao_e_reescrito(tmp_path: Path):
    vault = tmp_path / "vault"
    caminho = garantir_fontes(vault)
    caminho.write_text("", encoding="utf-8")

    fontes = ler_fontes(vault)

    assert caminho.read_text(encoding="utf-8") == ""
    assert fontes.secoes == ()
    assert fontes.time is None
