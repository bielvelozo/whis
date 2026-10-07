"""A nota da aula: o que o jornal escreve em `noticias/aulas/` ele lê igual, e a área só avança lida."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from whis.aulas import (
    PASTA_DAS_AULAS,
    NotaDeAula,
    aplicar_leituras,
    em_cena,
    escrever_aula,
    id_da_aula,
    ler_aulas,
    ler_nota,
    montar_nota,
    nascer,
    vagas,
)
from whis.portas import Aula, Formacao

HOJE = date(2026, 10, 7)
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">'
    '<rect x="5" y="5" width="40" height="40" fill="none" stroke="currentColor"/>'
    '<text x="25" y="28" text-anchor="middle" font-size="8">Custo</text></svg>'
)


def nota(id_, status="pendente", **extras) -> NotaDeAula:
    area = "negocios" if id_.endswith("negocios") else "carros"
    aula = Aula(
        "Margem: o que sobra",
        "Linha 1: com dois-pontos.\n\n# não é título",
        ("https://exemplo.com/a", "https://exemplo.com/b"),
        f"- {id_[:10]} — negócios: margem",
        visual="foto",
        imagem="https://img.exemplo.com/m.jpg",
        id=id_,
    )
    return NotaDeAula(id=id_, area=area, data=date.fromisoformat(id_[:10]), status=status, aula=aula, **extras)


def com_esquema(original: NotaDeAula) -> NotaDeAula:
    return replace(original, aula=replace(original.aula, visual="esquema", imagem="", esquema=SVG))


def arquivo_da(vault: Path, id_: str, sufixo: str = "md") -> Path:
    return vault / PASTA_DAS_AULAS / f"{id_}.{sufixo}"


# --- o id ---------------------------------------------------------------------------


def test_ids_da_aula():
    assert id_da_aula(HOJE, "negocios") == "2026-10-07-negocios"
    assert id_da_aula(HOJE, "carros") == "2026-10-07-carros-1"
    assert id_da_aula(HOJE, "carros", 2) == "2026-10-07-carros-2"


# --- a nota: ida e volta -------------------------------------------------------------


def test_ida_e_volta_da_nota():
    original = nota("2026-10-06-negocios", lida_em="2026-10-06T21:10:00-03:00", quiz="2026-10-10")
    assert ler_nota(montar_nota(original)) == original


def test_ida_e_volta_da_nota_de_carro_lida():
    original = nota("2026-10-06-carros-2", status="lida", lida_em="2026-10-06T21:10:00-03:00")
    assert ler_nota(montar_nota(original)) == original


def test_fontes_voltam_como_tupla_na_mesma_ordem():
    lida = ler_nota(montar_nota(nota("2026-10-06-negocios")))
    assert lida.aula.fontes == ("https://exemplo.com/a", "https://exemplo.com/b")


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "Uma linha só.",
        "Linha 1: com dois-pontos.\n\n# não é título\n\n---\n\n- item: a\n- item: b",
        "\nComeça e termina em linha em branco\n",
        "Tem <!-- um comentário --> e <!-- /texto --> no meio.",
        "Antes\n<!-- /texto -->\nDepois: de um marcador sozinho na linha",
        'Aspas "duplas", barra \\ e `código`.\n\nÉ ação, não é opção.',
    ],
)
def test_texto_com_qualquer_coisa_volta_igual(texto):
    original = nota("2026-10-06-negocios")
    original = replace(original, aula=replace(original.aula, texto=texto))
    assert ler_nota(montar_nota(original)).aula.texto == texto


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("titulo", 'Margem "bruta": o que sobra \\ depois'),
        ("trilha", '- 2026-10-06 — negócios: margem "bruta" e \\ barra'),
        ("imagem", "https://img.exemplo.com/m.jpg?w=1&h=2#frag"),
    ],
)
def test_aspas_e_barras_no_frontmatter_voltam_iguais(campo, valor):
    original = nota("2026-10-06-negocios")
    original = replace(original, aula=replace(original.aula, **{campo: valor}))
    assert ler_nota(montar_nota(original)).aula == original.aula


def test_nota_sem_fontes_volta_com_tupla_vazia():
    original = nota("2026-10-06-negocios")
    original = replace(original, aula=replace(original.aula, fontes=()))
    assert ler_nota(montar_nota(original)).aula.fontes == ()


def test_nota_com_quebra_de_linha_do_windows_le_igual():
    original = nota("2026-10-06-negocios")
    assert ler_nota(montar_nota(original).replace("\n", "\r\n")) == original


def test_o_que_nao_e_guardado_volta_vazio():
    cheia = nota("2026-10-06-negocios")
    cheia = replace(
        cheia, aula=replace(cheia.aula, foto_de="https://exemplo.com/a", foto="img/aula-x.jpg", pendente_desde=HOJE)
    )
    lida = ler_nota(montar_nota(cheia)).aula
    assert (lida.foto_de, lida.foto, lida.pendente_desde, lida.esquema) == ("", "", None, "")


def test_o_esquema_nao_vai_na_nota_so_o_link_do_svg():
    texto = montar_nota(com_esquema(nota("2026-10-06-negocios")))
    assert "<svg" not in texto
    assert "![[2026-10-06-negocios.svg]]" in texto
    assert "visual: esquema" in texto


def test_a_foto_vai_na_nota_como_imagem_da_url_original():
    texto = montar_nota(nota("2026-10-06-negocios"))
    assert "![](https://img.exemplo.com/m.jpg)" in texto
    assert ".svg" not in texto


def test_aula_sem_figura_nao_tem_linha_de_figura():
    original = nota("2026-10-06-negocios")
    original = replace(original, aula=replace(original.aula, visual="", imagem=""))
    texto = montar_nota(original)
    assert "![" not in texto
    assert ler_nota(texto) == original


def test_frontmatter_da_nota():
    texto = montar_nota(nota("2026-10-06-carros-1", quiz="2026-10-10"))
    cabeca = texto.split("---")[1]
    for linha in ("tipo: aula", "area: carros", "data: 2026-10-06", "status: pendente", "visual: foto"):
        assert linha in cabeca
    assert 'id: "2026-10-06-carros-1"' in cabeca
    assert "quiz: 2026-10-10" in cabeca
    assert 'lida_em: ""' in cabeca


def test_area_de_negocios_vai_com_acento_e_volta_sem():
    texto = montar_nota(nota("2026-10-06-negocios"))
    assert "area: negócios" in texto
    assert ler_nota(texto).area == "negocios"


def test_corpo_da_nota():
    texto = montar_nota(nota("2026-10-06-negocios"))
    corpo = texto.split("\n---\n", 1)[1]
    assert corpo.lstrip().startswith("# Margem: o que sobra")
    assert "<!-- texto -->\nLinha 1: com dois-pontos.\n\n# não é título\n<!-- /texto -->" in corpo
    assert "Fontes:\n- https://exemplo.com/a\n- https://exemplo.com/b" in corpo


# --- o status posto à mão -------------------------------------------------------------


def test_status_posto_a_mao_no_obsidian_vale():
    texto = montar_nota(nota("2026-10-06-negocios")).replace("status: pendente", "status: Lida")
    assert ler_nota(texto).status == "lida"


@pytest.mark.parametrize("escrito", ['"lida"', "LIDA", " lida ", "'lida'"])
def test_status_lida_em_qualquer_grafia(escrito):
    texto = montar_nota(nota("2026-10-06-negocios")).replace("status: pendente", f"status: {escrito}")
    assert ler_nota(texto).status == "lida"


@pytest.mark.parametrize("escrito", ["", "feita", "lido", "pendente", "talvez"])
def test_qualquer_outra_coisa_e_pendente(escrito):
    texto = montar_nota(nota("2026-10-06-negocios", status="lida")).replace("status: lida", f"status: {escrito}")
    assert ler_nota(texto).status == "pendente"


def test_status_sem_a_linha_e_pendente():
    texto = montar_nota(nota("2026-10-06-negocios")).replace("status: pendente\n", "")
    assert ler_nota(texto).status == "pendente"


# --- o que não é nota de aula ---------------------------------------------------------


def test_sem_tipo_aula_nao_e_nota_de_aula():
    texto = montar_nota(nota("2026-10-06-negocios")).replace("tipo: aula", "tipo: jornal")
    assert ler_nota(texto) is None


def test_sem_os_marcadores_do_texto_nao_e_nota_de_aula():
    texto = montar_nota(nota("2026-10-06-negocios")).replace("<!-- /texto -->", "")
    assert ler_nota(texto) is None
    assert ler_nota(montar_nota(nota("2026-10-06-negocios")).replace("<!-- texto -->", "")) is None


@pytest.mark.parametrize("texto", ["", "só texto", "---\ntipo: aula\n", "# Título\n\ntexto"])
def test_lixo_nao_e_nota_de_aula(texto):
    assert ler_nota(texto) is None


def test_data_ilegivel_ou_id_perigoso_nao_e_nota_de_aula():
    texto = montar_nota(nota("2026-10-06-negocios"))
    assert ler_nota(texto.replace("data: 2026-10-06", "data: ontem")) is None
    assert ler_nota(texto.replace('id: "2026-10-06-negocios"', 'id: "../fora"')) is None


# --- ler e escrever no vault ----------------------------------------------------------


def test_escrever_aula_grava_a_nota_na_pasta_das_aulas(tmp_path):
    caminho = escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    assert caminho == arquivo_da(tmp_path, "2026-10-06-negocios").resolve()
    assert ler_nota(caminho.read_text("utf-8")) == nota("2026-10-06-negocios")
    assert not arquivo_da(tmp_path, "2026-10-06-negocios", "svg").exists()


def test_ler_aulas_devolve_o_que_foi_escrito_ordenado_por_id(tmp_path):
    notas = [nota("2026-10-06-negocios"), nota("2026-10-05-carros-2"), nota("2026-10-05-carros-1", status="lida")]
    for n in notas:
        escrever_aula(tmp_path, n)
    assert ler_aulas(tmp_path) == sorted(notas, key=lambda n: n.id)


def test_sem_pasta_nao_ha_aula(tmp_path):
    assert ler_aulas(tmp_path) == []


def test_ler_aulas_ignora_o_que_nao_e_nota_de_aula(tmp_path):
    escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    pasta = tmp_path / PASTA_DAS_AULAS
    (pasta / "anotacao.md").write_text("# nada a ver\n", encoding="utf-8")
    (pasta / "quebrada.md").write_text("---\ntipo: aula\n---\nsem marcadores\n", encoding="utf-8")
    assert [n.id for n in ler_aulas(tmp_path)] == ["2026-10-06-negocios"]


def test_status_mudado_no_obsidian_vale_na_leitura(tmp_path):
    escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    arquivo = arquivo_da(tmp_path, "2026-10-06-negocios")
    arquivo.write_text(arquivo.read_text("utf-8").replace("status: pendente", "status: lida"), encoding="utf-8")
    assert ler_aulas(tmp_path)[0].status == "lida"


def test_texto_editado_no_obsidian_vale_na_leitura(tmp_path):
    escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    arquivo = arquivo_da(tmp_path, "2026-10-06-negocios")
    arquivo.write_text(arquivo.read_text("utf-8").replace("Linha 1:", "Linha editada:"), encoding="utf-8")
    assert ler_aulas(tmp_path)[0].aula.texto.startswith("Linha editada:")


def test_esquema_vem_do_arquivo_ao_lado(tmp_path):
    escrever_aula(tmp_path, com_esquema(nota("2026-10-06-negocios")))
    [lida] = ler_aulas(tmp_path)
    assert lida.aula.esquema == SVG
    assert lida.aula.visual == "esquema"
    assert "![[2026-10-06-negocios.svg]]" in arquivo_da(tmp_path, "2026-10-06-negocios").read_text("utf-8")
    assert arquivo_da(tmp_path, "2026-10-06-negocios", "svg").read_text("utf-8") == SVG


def test_esquema_sem_o_arquivo_vira_aula_sem_figura(tmp_path):
    escrever_aula(tmp_path, com_esquema(nota("2026-10-06-negocios")))
    arquivo_da(tmp_path, "2026-10-06-negocios", "svg").unlink()
    [lida] = ler_aulas(tmp_path)
    assert (lida.aula.visual, lida.aula.esquema) == ("", "")
    assert lida.aula.titulo == "Margem: o que sobra"


def test_esquema_do_arquivo_passa_de_novo_pela_validacao(tmp_path):
    escrever_aula(tmp_path, com_esquema(nota("2026-10-06-negocios")))
    arquivo_da(tmp_path, "2026-10-06-negocios", "svg").write_text(
        SVG.replace("<rect", '<script>alert(1)</script><rect'), encoding="utf-8"
    )
    [lida] = ler_aulas(tmp_path)
    assert (lida.aula.visual, lida.aula.esquema) == ("", "")


def test_aula_de_foto_nao_le_svg_nenhum(tmp_path):
    escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    arquivo_da(tmp_path, "2026-10-06-negocios", "svg").write_text(SVG, encoding="utf-8")
    assert ler_aulas(tmp_path)[0].aula.esquema == ""


def test_escrever_de_novo_substitui_a_nota(tmp_path):
    escrever_aula(tmp_path, nota("2026-10-06-negocios"))
    escrever_aula(tmp_path, nota("2026-10-06-negocios", status="lida", lida_em="2026-10-06T22:00:00-03:00"))
    [lida] = ler_aulas(tmp_path)
    assert (lida.status, lida.lida_em) == ("lida", "2026-10-06T22:00:00-03:00")


# --- aplicar as leituras --------------------------------------------------------------


def test_aplicar_leituras_so_leva_pendente_para_lida():
    notas = [nota("2026-10-06-negocios"), nota("2026-10-05-carros-1", status="lida", lida_em="x")]
    novas = aplicar_leituras(notas, {"2026-10-06-negocios": "2026-10-06T22:00:00-03:00"})
    assert novas[0].status == "lida" and novas[0].lida_em == "2026-10-06T22:00:00-03:00"
    assert novas[1] is notas[1]


def test_aula_ja_lida_nao_muda_nem_com_outra_data_na_pagina():
    lida = nota("2026-10-05-carros-1", status="lida", lida_em="antes")
    [nova] = aplicar_leituras([lida], {"2026-10-05-carros-1": "depois"})
    assert nova is lida and nova.lida_em == "antes"


def test_pendente_sem_marca_volta_a_mesma_instancia():
    pendente = nota("2026-10-06-negocios")
    [nova] = aplicar_leituras([pendente], {"outra-aula": "x"})
    assert nova is pendente


def test_leituras_vazias_devolvem_as_mesmas_notas():
    notas = [nota("2026-10-06-negocios"), nota("2026-10-06-carros-1")]
    novas = aplicar_leituras(notas, {})
    assert novas == notas and all(a is b for a, b in zip(novas, notas))


# --- as vagas ---------------------------------------------------------------------------


def test_sem_nenhuma_nota_ha_vaga_para_as_duas_areas():
    assert vagas([], HOJE, sabado=False) == {"negocios": 1, "carros": 2}


def test_vagas_descontam_as_pendentes_antigas():
    notas = [nota("2026-10-06-carros-1"), nota("2026-10-05-negocios")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 0, "carros": 1}


def test_duas_pendentes_de_carro_fecham_a_area():
    notas = [nota("2026-10-06-carros-1"), nota("2026-10-06-carros-2")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 1, "carros": 0}


def test_vaga_nunca_fica_abaixo_de_zero():
    notas = [nota(f"2026-10-0{d}-carros-{n}") for d in (3, 4, 5) for n in (1, 2)]
    notas += [nota("2026-10-02-negocios"), nota("2026-10-03-negocios")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 0, "carros": 0}


def test_ja_nasceu_aula_hoje_nao_ha_vaga():
    notas = [nota("2026-10-07-carros-1", status="lida")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 0, "carros": 0}


def test_aula_de_hoje_pendente_tambem_fecha_as_vagas():
    assert vagas([nota("2026-10-07-negocios")], HOJE, sabado=False) == {"negocios": 0, "carros": 0}


def test_aula_antiga_lida_nao_ocupa_vaga():
    notas = [nota("2026-10-06-negocios", status="lida"), nota("2026-10-06-carros-1", status="lida")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 1, "carros": 2}


def test_sabado_nao_tem_vaga():
    assert vagas([], date(2026, 10, 10), sabado=True) == {"negocios": 0, "carros": 0}


def test_sabado_nao_tem_vaga_mesmo_sem_pendentes_nem_aula_de_hoje():
    assert vagas([nota("2026-10-08-negocios", status="lida")], date(2026, 10, 10), sabado=True) == {
        "negocios": 0,
        "carros": 0,
    }


# --- as aulas que nascem ----------------------------------------------------------------


def test_aula_nova_de_negocios_nasce_pendente_com_o_id_do_dia():
    nova = Aula("Preço", "t", ("https://exemplo.com",), "negócios: preço")
    [nascida] = nascer(Formacao(negocios=nova), HOJE, [])
    assert nascida.id == "2026-10-07-negocios" and nascida.aula.id == nascida.id
    assert (nascida.area, nascida.data, nascida.status, nascida.lida_em, nascida.quiz) == (
        "negocios",
        HOJE,
        "pendente",
        "",
        "",
    )
    assert nascida.aula.titulo == "Preço" and nascida.aula.trilha == "negócios: preço"


def test_aula_nova_de_carro_pega_o_menor_numero_livre_da_data():
    ja = nota("2026-10-07-carros-1", status="lida")
    nova = Aula("Turbo", "t", ("https://exemplo.com",), "carros: turbo")
    [nascida] = nascer(Formacao(carros=(nova,)), HOJE, [ja])
    assert nascida.id == "2026-10-07-carros-2" and nascida.aula.id == nascida.id


def test_duas_aulas_de_carro_na_mesma_chamada_nao_colidem():
    a = Aula("Turbo", "t", ("https://exemplo.com",), "carros: turbo")
    b = Aula("Câmbio", "c", ("https://exemplo.com",), "carros: câmbio")
    nascidas = nascer(Formacao(negocios=Aula("Preço", "p", ("https://exemplo.com",), ""), carros=(a, b)), HOJE, [])
    assert [n.id for n in nascidas] == ["2026-10-07-negocios", "2026-10-07-carros-1", "2026-10-07-carros-2"]


def test_numero_de_carro_livre_ignora_o_de_outras_datas():
    notas = [nota("2026-10-06-carros-1"), nota("2026-10-06-carros-2")]
    nova = Aula("Turbo", "t", ("https://exemplo.com",), "carros: turbo")
    [nascida] = nascer(Formacao(carros=(nova,)), HOJE, notas)
    assert nascida.id == "2026-10-07-carros-1"


def test_numero_livre_preenche_o_buraco():
    nova = Aula("Turbo", "t", ("https://exemplo.com",), "carros: turbo")
    [nascida] = nascer(Formacao(carros=(nova,)), HOJE, [nota("2026-10-07-carros-2")])
    assert nascida.id == "2026-10-07-carros-1"


def test_nascer_leva_a_figura_da_aula():
    nova = Aula("RX-7", "t", ("https://en.wikipedia.org/wiki/Mazda_RX-7",), "carros: rx-7",
                visual="foto", foto_de="https://en.wikipedia.org/wiki/Mazda_RX-7", imagem="https://img.exemplo.com/a.jpg")
    [nascida] = nascer(Formacao(carros=(nova,)), HOJE, [])
    assert (nascida.aula.visual, nascida.aula.foto_de, nascida.aula.imagem) == (
        "foto",
        "https://en.wikipedia.org/wiki/Mazda_RX-7",
        "https://img.exemplo.com/a.jpg",
    )


def test_formacao_vazia_nao_faz_nascer_nada():
    assert nascer(Formacao(), HOJE, []) == ()


# --- o que está em cena ------------------------------------------------------------------


def test_em_cena_poe_pendentes_antigas_depois_as_de_hoje():
    notas = [nota("2026-10-07-carros-1"), nota("2026-10-05-carros-1"), nota("2026-10-04-carros-2", status="lida")]
    cena = em_cena(notas, HOJE)
    assert [a.id for a in cena.carros] == ["2026-10-05-carros-1", "2026-10-07-carros-1"]
    assert cena.carros[0].pendente_desde == date(2026, 10, 5) and cena.carros[1].pendente_desde is None


def test_em_cena_as_de_hoje_aparecem_lidas_ou_nao():
    notas = [nota("2026-10-07-negocios", status="lida"), nota("2026-10-07-carros-1", status="lida"), nota("2026-10-07-carros-2")]
    cena = em_cena(notas, HOJE)
    assert cena.negocios.id == "2026-10-07-negocios"
    assert [a.id for a in cena.carros] == ["2026-10-07-carros-1", "2026-10-07-carros-2"]
    assert all(a.pendente_desde is None for a in cena.aulas())


def test_em_cena_nao_traz_lida_de_dia_anterior_nem_aula_futura():
    notas = [nota("2026-10-06-negocios", status="lida"), nota("2026-10-08-carros-1")]
    cena = em_cena(notas, HOJE)
    assert cena.negocios is None and cena.carros == ()


def test_em_cena_negocios_fica_com_uma_so_a_mais_antiga():
    notas = [nota("2026-10-06-negocios"), nota("2026-10-05-negocios")]
    cena = em_cena(notas, HOJE)
    assert cena.negocios.id == "2026-10-05-negocios" and cena.negocios.pendente_desde == date(2026, 10, 5)


def test_em_cena_carros_ficam_em_duas():
    notas = [nota("2026-10-04-carros-1"), nota("2026-10-05-carros-1"), nota("2026-10-06-carros-1")]
    assert [a.id for a in em_cena(notas, HOJE).carros] == ["2026-10-04-carros-1", "2026-10-05-carros-1"]


def test_em_cena_antigas_ordenam_por_data_e_depois_por_id():
    notas = [nota("2026-10-06-carros-2"), nota("2026-10-05-carros-2"), nota("2026-10-06-carros-1")]
    assert [a.id for a in em_cena(notas, HOJE).carros] == ["2026-10-05-carros-2", "2026-10-06-carros-1"]


def test_em_cena_traz_a_aula_inteira_com_o_id():
    [original] = [nota("2026-10-06-negocios")]
    cena = em_cena([original], HOJE)
    assert cena.negocios == replace(original.aula, id="2026-10-06-negocios", pendente_desde=date(2026, 10, 6))


def test_em_cena_vazia():
    cena = em_cena([], HOJE)
    assert cena.negocios is None and cena.carros == () and cena.aulas() == ()
