"""A nota viva como texto: o que o agente pode fazer nela, e o que nunca muda.

Os testes daqui não tocam o vault: entram com um markdown e olham o markdown
que sai. A régua é a da entrega — cada linha que já estava na nota volta byte a
byte, e a única coisa que o agente faz é acrescentar, mover e arquivar.
"""

from __future__ import annotations

import hashlib

import pytest

from whis.nota_viva import (
    MODELO_DA_NOTA_VIVA,
    SECAO_DUVIDAS,
    SECAO_FALAR,
    SECAO_FAZENDO,
    SECAO_FAZER,
    SECAO_FIZ,
    SECAO_PONTOS,
    NotaViva,
    id_do_item,
)
from whis.portas import Daily, ItemNovo

#: Uma nota no formato das dailies à mão do usuário: `1.` com sub-itens por tab,
#: um item com espaço à direita, linha em branco dentro da seção.
NOTA = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz \n"
    "\n"
    "1. Planejei e ativei o pix transparente da AppMax no checkout\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "1. Estou fazendo mais correções dos achados do ribeiro\n"
    "\t1. FN-1786: a foto extra do Porta Retrato não será cobrada de novo no hub.\n"
    "\t2. Card \"A pagar agora\" e adicionais do porta-retrato (FN-1784)\n"
    "\t\t1. Problema A, adicionais de outros itens \n"
    "\t\t2. Problema B, linhas pagas dentro de \"A pagar agora\"\n"
    "2. Testando no android  \n"
    "\n"
    "\t   \n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- o pix pendente expira sozinho?\n"
    "\n"
    "## Falar\n"
    "\n"
    "- avisar que sexta eu saio mais cedo\n"
)


def hash_de(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def trecho(texto: str, titulo: str) -> str:
    """O texto de uma seção, do título até o próximo `## `."""
    inicio = texto.index(f"## {titulo}")
    fim = texto.find("\n## ", inicio + 1)
    return texto[inicio:] if fim == -1 else texto[inicio:fim]


# -- ler ---------------------------------------------------------------------


def test_ler_e_escrever_sem_mexer_devolve_o_mesmo_texto():
    assert NotaViva.de_texto(NOTA).texto() == NOTA


def test_quebra_de_linha_do_windows_e_preservada():
    com_crlf = NOTA.replace("\n", "\r\n")

    assert NotaViva.de_texto(com_crlf).texto() == com_crlf


def test_os_itens_de_uma_secao_vem_com_a_subarvore_e_os_ancestrais():
    itens = NotaViva.de_texto(NOTA).itens(SECAO_FAZENDO)

    textos = [item.texto for item in itens]
    assert textos[0].startswith("Estou fazendo mais correções")
    assert textos[-1] == "Testando no android"
    grupo, foto, card, problema_a, problema_b, android = itens
    assert grupo.fim == android.inicio, "a subárvore do grupo vai até o item seguinte"
    assert problema_a.ancestrais == (grupo.inicio, card.inicio)
    assert android.ancestrais == ()


def test_o_titulo_da_secao_aceita_espaco_no_fim_e_acento_faltando():
    nota = NotaViva.de_texto(NOTA.replace("## Dúvidas", "## duvidas"))

    assert nota.conteudo(SECAO_FIZ) == ("1. Planejei e ativei o pix transparente da AppMax no checkout",)
    assert nota.conteudo(SECAO_DUVIDAS) == ("- o pix pendente expira sozinho?",)


def test_o_id_e_estavel_e_nao_depende_da_posicao():
    nota = NotaViva.de_texto(NOTA)
    android = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto == "Testando no android")

    assert android.id == id_do_item("Testando no android")
    assert len(android.id) == 6


def test_dois_itens_com_o_mesmo_texto_ganham_ids_diferentes():
    nota = NotaViva.de_texto("## O que estou fazendo\n- repetido\n- repetido\n")

    primeiro, segundo = nota.itens(SECAO_FAZENDO)
    assert primeiro.id == id_do_item("repetido")
    assert segundo.id != primeiro.id


def test_as_secoes_do_usuario_nao_tem_id():
    nota = NotaViva.de_texto(NOTA)

    assert nota.itens(SECAO_DUVIDAS) == ()
    assert nota.com_ids(SECAO_DUVIDAS) == ("- o pix pendente expira sozinho?",)
    assert "(id " in nota.com_ids(SECAO_FAZENDO)[0]


# -- mover -------------------------------------------------------------------


def test_mover_leva_a_linha_e_a_subarvore_byte_a_byte_e_tira_de_fazendo():
    nota = NotaViva.de_texto(NOTA)
    card = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto.startswith("Card"))

    movido = nota.mover(card.id)

    texto = nota.texto()
    assert movido == (
        "1. Estou fazendo mais correções dos achados do ribeiro",
        "\t2. Card \"A pagar agora\" e adicionais do porta-retrato (FN-1784)",
        "\t\t1. Problema A, adicionais de outros itens ",
        "\t\t2. Problema B, linhas pagas dentro de \"A pagar agora\"",
    )
    assert trecho(texto, SECAO_FIZ) == (
        "## O que eu fiz \n"
        "\n"
        "1. Planejei e ativei o pix transparente da AppMax no checkout\n"
        "1. Estou fazendo mais correções dos achados do ribeiro\n"
        "\t2. Card \"A pagar agora\" e adicionais do porta-retrato (FN-1784)\n"
        "\t\t1. Problema A, adicionais de outros itens \n"
        "\t\t2. Problema B, linhas pagas dentro de \"A pagar agora\"\n"
    )
    assert trecho(texto, SECAO_FAZENDO) == (
        "## O que estou fazendo\n"
        "\n"
        "1. Estou fazendo mais correções dos achados do ribeiro\n"
        "\t1. FN-1786: a foto extra do Porta Retrato não será cobrada de novo no hub.\n"
        "2. Testando no android  \n"
        "\n"
        "\t   \n"
    )


def test_mover_nao_duplica_um_ancestral_que_ja_esta_em_fiz():
    nota = NotaViva.de_texto(NOTA)
    por_texto = {item.texto[:8]: item for item in nota.itens(SECAO_FAZENDO)}

    nota.mover(por_texto["FN-1786:"].id)
    nota.mover(por_texto['Card "A '].id)

    fiz = trecho(nota.texto(), SECAO_FIZ)
    assert fiz.count("Estou fazendo mais correções dos achados do ribeiro") == 1
    assert fiz.index("FN-1786") < fiz.index("Card \"A pagar agora\"")


def test_mover_um_item_de_primeiro_nivel_vai_para_o_fim_de_fiz():
    nota = NotaViva.de_texto(NOTA)
    android = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto == "Testando no android")

    nota.mover(android.id)

    assert trecho(nota.texto(), SECAO_FIZ).endswith(
        "1. Planejei e ativei o pix transparente da AppMax no checkout\n2. Testando no android  \n"
    )
    assert "Testando no android" not in trecho(nota.texto(), SECAO_FAZENDO)


def test_mover_id_inexistente_ou_ja_em_fiz_nao_muda_nada(caplog):
    nota = NotaViva.de_texto(NOTA)
    em_fiz = nota.itens(SECAO_FIZ)[0].id

    with caplog.at_level("WARNING", logger="whis.nota_viva"):
        assert nota.mover("ffffff") is None
        assert nota.mover(em_fiz) is None

    assert nota.texto() == NOTA
    assert "ffffff" in caplog.text and em_fiz in caplog.text


def test_mover_aceita_o_id_como_o_modelo_copia_da_pergunta():
    nota = NotaViva.de_texto(NOTA)
    android = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto == "Testando no android")

    assert nota.mover(f"(id {android.id})") is not None


# -- acrescentar -------------------------------------------------------------


def test_acrescentar_sem_pai_entra_no_fim_da_secao_antes_das_linhas_em_branco():
    nota = NotaViva.de_texto(NOTA)

    entrou = nota.acrescentar(SECAO_FAZENDO, "Revisar o flow de pix pendente que o Lucas pediu")

    assert entrou == ("- Revisar o flow de pix pendente que o Lucas pediu",)
    assert trecho(nota.texto(), SECAO_FAZENDO).endswith(
        "2. Testando no android  \n"
        "- Revisar o flow de pix pendente que o Lucas pediu\n"
        "\n"
        "\t   \n"
    )


def test_acrescentar_sob_um_item_entra_como_ultimo_filho_com_a_indentacao_dos_irmaos():
    nota = NotaViva.de_texto(NOTA)
    grupo = nota.itens(SECAO_FAZENDO)[0]

    nota.acrescentar(SECAO_FAZENDO, "FN-1788: as telas de fotos avulsas vão carregar com skeleton", sob=grupo.id)

    assert (
        "\t\t2. Problema B, linhas pagas dentro de \"A pagar agora\"\n"
        "\t- FN-1788: as telas de fotos avulsas vão carregar com skeleton\n"
        "2. Testando no android  \n"
    ) in nota.texto()


def test_acrescentar_sob_um_item_sem_filhos_indenta_um_nivel_a_mais():
    nota = NotaViva.de_texto(NOTA)
    android = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto == "Testando no android")

    nota.acrescentar(SECAO_FAZENDO, "no Pixel a foto some", sob=android.id)

    assert "2. Testando no android  \n\t- no Pixel a foto some\n" in nota.texto()


def test_acrescentar_em_fiz_sob_um_grupo_de_fazendo_copia_o_cabecalho_literal():
    """É assim que uma correção pronta entra debaixo do mesmo 'Correções do Ribeiro'."""
    nota = NotaViva.de_texto(NOTA)
    grupo = nota.itens(SECAO_FAZENDO)[0]

    entrou = nota.acrescentar(SECAO_FIZ, "FN-1773, o aviso amarelo do envio virou toast", sob=grupo.id)

    assert entrou == (
        "1. Estou fazendo mais correções dos achados do ribeiro",
        "\t- FN-1773, o aviso amarelo do envio virou toast",
    )
    assert trecho(nota.texto(), SECAO_FIZ).endswith(
        "1. Estou fazendo mais correções dos achados do ribeiro\n"
        "\t- FN-1773, o aviso amarelo do envio virou toast\n"
    )
    assert trecho(nota.texto(), SECAO_FAZENDO) == trecho(NOTA, SECAO_FAZENDO)


def test_acrescentar_numa_secao_que_nao_existe_a_cria_no_fim():
    nota = NotaViva.de_texto("---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n")

    nota.acrescentar(SECAO_FALAR, "lembrar do deploy")

    assert nota.texto() == (
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Falar\n- lembrar do deploy\n"
    )


def test_anotar_e_append_only_em_pontos_que_nasce_antes_de_falar():
    """A nota antiga não tem `## Pontos`: a seção entra antes de *Falar*, e nada mais muda."""
    nota = NotaViva.de_texto(NOTA)

    linha = nota.anotar("perguntar do skeleton")

    texto = nota.texto()
    assert linha == "- perguntar do skeleton"
    assert texto.replace("## Pontos\n- perguntar do skeleton\n\n", "", 1) == NOTA
    assert trecho(texto, SECAO_PONTOS).startswith("## Pontos\n- perguntar do skeleton\n")
    assert trecho(texto, SECAO_FALAR) == trecho(NOTA, SECAO_FALAR)


def test_anotar_em_fazer_escreve_a_caixa_e_a_secao_nasce_depois_de_fazendo():
    """O `do`: a linha entra com `[ ]` para ele marcar, e a seção nova entra na ordem."""
    nota = NotaViva.de_texto(NOTA)

    linha = nota.anotar("responder o ribeiro", SECAO_FAZER)

    texto = nota.texto()
    assert linha == "- [ ] responder o ribeiro"
    assert "2. Testando no android  \n\n\t   \n\n## Fazer\n- [ ] responder o ribeiro\n\n## Dúvidas\n" in texto
    assert texto.replace("## Fazer\n- [ ] responder o ribeiro\n\n", "", 1) == NOTA


def test_o_que_ele_marcou_a_mao_em_fazer_fica_como_esta_quando_a_janela_vira():
    """A caixa é dele: nem `anotar` nem o arquivamento de *O que eu fiz* tocam o que está lá."""
    nota = NotaViva.de_texto(
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## O que estou fazendo\n\n"
        "## Fazer\n\n- [x] liguei para o contador\n- [ ] responder o ribeiro\n\n## Falar\n"
    )

    nota.anotar("marcar a consulta", SECAO_FAZER)
    arquivado = nota.arquivar_fiz()

    assert arquivado == ("- feito",)
    assert trecho(nota.texto(), SECAO_FAZER) == (
        "## Fazer\n\n- [x] liguei para o contador\n- [ ] responder o ribeiro\n- [ ] marcar a consulta\n"
    )


def test_anotar_em_duvidas_so_a_pedido_e_nunca_nas_secoes_do_agente_ou_em_falar():
    nota = NotaViva.de_texto(NOTA)

    nota.anotar("o pix expira?", SECAO_DUVIDAS)

    assert "- o pix pendente expira sozinho?\n- o pix expira?\n" in trecho(nota.texto(), SECAO_DUVIDAS)
    for proibida in (SECAO_FIZ, SECAO_FAZENDO, SECAO_FALAR):
        with pytest.raises(ValueError):
            nota.anotar("x", proibida)


def test_a_secao_nova_entra_na_ordem_das_cinco_mesmo_sem_a_seguinte_imediata():
    nota = NotaViva.de_texto("---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Falar\n- x\n")

    nota.anotar("dúvida", SECAO_DUVIDAS)

    assert nota.texto() == (
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Dúvidas\n- dúvida\n\n## Falar\n- x\n"
    )


# -- arquivar ----------------------------------------------------------------


def test_arquivar_fiz_devolve_o_bloco_literal_e_recomeca_a_secao():
    nota = NotaViva.de_texto(NOTA)

    arquivado = nota.arquivar_fiz()

    assert arquivado == ("1. Planejei e ativei o pix transparente da AppMax no checkout",)
    assert trecho(nota.texto(), SECAO_FIZ) == "## O que eu fiz \n"
    assert trecho(nota.texto(), SECAO_FAZENDO) == trecho(NOTA, SECAO_FAZENDO)
    assert trecho(nota.texto(), SECAO_DUVIDAS) == trecho(NOTA, SECAO_DUVIDAS)
    assert trecho(nota.texto(), SECAO_FALAR) == trecho(NOTA, SECAO_FALAR)


# -- aplicar: a resposta do modelo inteira -------------------------------------


def test_aplicar_faz_os_movimentos_antes_dos_acrescimos_e_nao_toca_o_resto():
    nota = NotaViva.de_texto(NOTA)
    antes = {secao: hash_de(trecho(NOTA, secao)) for secao in (SECAO_DUVIDAS, SECAO_FALAR)}
    android = next(item for item in nota.itens(SECAO_FAZENDO) if item.texto == "Testando no android")

    mudancas = nota.aplicar(
        Daily(
            fiz=(ItemNovo("no Pixel a foto abria em branco; corrigido", sob=android.id),),
            fazendo=(ItemNovo("Correções que o Gideon pediu no modal da AppMax"),),
            mover=(android.id,),
        )
    )

    texto = nota.texto()
    assert mudancas.movidas == (("2. Testando no android  ",),)
    assert mudancas.acrescentadas == (
        ("\t- no Pixel a foto abria em branco; corrigido",),
        ("- Correções que o Gideon pediu no modal da AppMax",),
    )
    assert "2. Testando no android  \n\t- no Pixel a foto abria em branco; corrigido\n" in trecho(texto, SECAO_FIZ)
    assert {secao: hash_de(trecho(texto, secao)) for secao in antes} == antes


def test_aplicar_nao_repete_texto_que_ja_esta_na_nota():
    nota = NotaViva.de_texto(NOTA)

    mudancas = nota.aplicar(Daily(fazendo=(ItemNovo("Testando no android"),)))

    assert mudancas.repetidos == ("Testando no android",)
    assert nota.texto() == NOTA


def test_aplicar_monta_um_grupo_com_sub_itens_numa_resposta_so():
    nota = NotaViva.do_modelo()

    nota.aplicar(
        Daily(
            fiz=(
                ItemNovo("Correções que o Ribeiro apontou"),
                ItemNovo("FN-1780, os modais ganharam a linha branca com o X", sob="Correções que o Ribeiro apontou"),
            )
        )
    )

    assert trecho(nota.texto(), SECAO_FIZ) == (
        "## O que eu fiz\n"
        "- Correções que o Ribeiro apontou\n"
        "\t- FN-1780, os modais ganharam a linha branca com o X\n"
    )


def test_aplicar_ignora_pai_inexistente_e_ainda_acrescenta_o_item(caplog):
    nota = NotaViva.de_texto(NOTA)

    with caplog.at_level("WARNING", logger="whis.nota_viva"):
        mudancas = nota.aplicar(Daily(fazendo=(ItemNovo("item órfão", sob="ffffff"),)))

    assert mudancas.ignorados == ("ffffff",)
    assert "2. Testando no android  \n- item órfão\n" in trecho(nota.texto(), SECAO_FAZENDO)
    assert "ffffff" in caplog.text


# -- o modelo ------------------------------------------------------------------


def test_o_modelo_tem_as_seis_secoes_na_ordem_e_nenhuma_explicacao():
    """O usuário sabe o que cada seção é (ticket 13): só o frontmatter e os títulos."""
    nota = NotaViva.do_modelo()

    assert [secao for secao, _ in nota.secoes()] == [
        SECAO_FIZ,
        SECAO_FAZENDO,
        SECAO_FAZER,
        SECAO_DUVIDAS,
        SECAO_PONTOS,
        SECAO_FALAR,
    ]
    assert all(linhas == () for _, linhas in nota.secoes())
    assert MODELO_DA_NOTA_VIVA.startswith("---\ntipo: daily-atual\n---\n")
    assert "\ndata:" not in MODELO_DA_NOTA_VIVA, "campo `data` vira link da Daily notes do Obsidian"
    assert ">" not in MODELO_DA_NOTA_VIVA
    assert [linha for linha in MODELO_DA_NOTA_VIVA.splitlines() if linha and not linha.startswith(("##", "---", "tipo:"))] == []
