"""A nota viva como texto: o que o agente pode fazer nela, e o que nunca muda.

Os testes daqui não tocam o vault: entram com um markdown e olham o markdown
que sai. A régua é a da entrega — cada linha que já estava na nota volta byte a
byte, e a única coisa que o agente faz é anotar a pedido e abrir um título que
falte.
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
    SECAO_TERMINEI,
    NotaViva,
)

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


def test_o_titulo_da_secao_aceita_espaco_no_fim_e_acento_faltando():
    nota = NotaViva.de_texto(NOTA.replace("## Dúvidas", "## duvidas"))

    assert nota.conteudo(SECAO_FIZ) == ("1. Planejei e ativei o pix transparente da AppMax no checkout",)
    assert nota.conteudo(SECAO_DUVIDAS) == ("- o pix pendente expira sozinho?",)


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


# -- abrir o título que falta -------------------------------------------------


def test_garantir_secao_abre_o_titulo_que_falta_no_lugar_dele_uma_vez_so():
    nota = NotaViva.de_texto(NOTA)

    assert nota.garantir_secao(SECAO_TERMINEI) is True
    assert nota.garantir_secao(SECAO_TERMINEI) is False

    texto = nota.texto()
    assert texto.count("## O que terminei") == 1
    assert texto.replace("## O que terminei\n\n", "", 1) == NOTA
    assert texto.index("## O que estou fazendo") < texto.index("## O que terminei") < texto.index("## Dúvidas")


# -- o modelo ------------------------------------------------------------------


def test_o_modelo_tem_as_sete_secoes_na_ordem_e_nenhuma_explicacao():
    """Ele sabe o que cada seção é (ticket 13): só o frontmatter e os títulos."""
    nota = NotaViva.do_modelo()

    assert [secao for secao, _ in nota.secoes()] == [
        SECAO_FIZ,
        SECAO_FAZENDO,
        SECAO_TERMINEI,
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
