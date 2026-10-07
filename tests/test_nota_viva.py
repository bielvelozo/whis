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
    SECAO_FAZENDO,
    SECAO_FAZER,
    SECAO_FIZ,
    SECAO_PONTOS,
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
    "## Pontos\n"
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

    nota.acrescentar(SECAO_PONTOS, "lembrar do deploy")

    assert nota.texto() == (
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Pontos\n- lembrar do deploy\n"
    )


def test_anotar_sem_secao_e_append_only_no_fim_de_pontos():
    """O `note`: o que ele anota vai para *Pontos*, que vira slide."""
    nota = NotaViva.de_texto(NOTA)

    linha = nota.anotar("perguntar do skeleton")

    assert linha == "- perguntar do skeleton"
    assert nota.texto() == NOTA.replace(
        "- avisar que sexta eu saio mais cedo\n", "- avisar que sexta eu saio mais cedo\n- perguntar do skeleton\n", 1
    )


def test_note_na_nota_real_dele_entra_em_pontos_e_falar_fica_como_estava():
    """Em 2026-10-07 a nota dele tinha `## Pontos` com um `- ` sozinho e linhas em branco, e *Falar* depois."""
    real = (
        "## Dúvidas\n- \n\n\n\n## Pontos\n- \n\n\n\n## O que eu fiz\n\n- fiz\n\n"
        "## Falar\n- Falar sobre o Daniel que me passou a página \n"
    )
    nota = NotaViva.de_texto(real)

    nota.anotar("validar os fluxos que o lucas subiu")

    assert nota.texto() == real.replace(
        "## Pontos\n- \n", "## Pontos\n- \n- validar os fluxos que o lucas subiu\n", 1
    )


def test_anotar_em_fazer_escreve_a_caixa_e_a_secao_nasce_depois_de_fazendo():
    """O `do`: a linha entra com `[ ]` para ele marcar, e a seção nova entra na ordem."""
    nota = NotaViva.de_texto(NOTA)

    linha = nota.anotar("responder o ribeiro", SECAO_FAZER)

    texto = nota.texto()
    assert linha == "- [ ] responder o ribeiro"
    assert "2. Testando no android  \n\n\t   \n\n## Fazer\n- [ ] responder o ribeiro\n\n## Dúvidas\n" in texto
    assert texto.replace("## Fazer\n- [ ] responder o ribeiro\n\n", "", 1) == NOTA


def test_anotar_em_duvidas_e_nunca_numa_secao_sem_comando():
    nota = NotaViva.de_texto(NOTA)

    nota.anotar("o pix expira?", SECAO_DUVIDAS)

    assert "- o pix pendente expira sozinho?\n- o pix expira?\n" in trecho(nota.texto(), SECAO_DUVIDAS)
    with pytest.raises(ValueError):
        nota.anotar("x", "Falar")


def test_anotar_em_fiz_e_fazendo_entra_sem_caixa_no_fim_da_secao():
    nota = NotaViva.de_texto(NOTA)

    assert nota.anotar("subi o pix", SECAO_FIZ) == "- subi o pix"
    assert nota.anotar("revisando o checkout", SECAO_FAZENDO) == "- revisando o checkout"

    texto = nota.texto()
    assert "1. Planejei e ativei o pix transparente da AppMax no checkout\n- subi o pix\n\n## O que estou fazendo\n" in texto
    assert "2. Testando no android  \n- revisando o checkout\n\n\t   \n" in texto


def test_a_secao_nova_entra_na_ordem_das_cinco_mesmo_sem_a_seguinte_imediata():
    nota = NotaViva.de_texto("---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Pontos\n- x\n")

    nota.anotar("dúvida", SECAO_DUVIDAS)

    assert nota.texto() == (
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n- feito\n\n## Dúvidas\n- dúvida\n\n## Pontos\n- x\n"
    )


# -- abrir o título que falta -------------------------------------------------


def test_garantir_secao_abre_o_titulo_que_falta_no_lugar_dele_uma_vez_so():
    nota = NotaViva.de_texto(NOTA)

    assert nota.garantir_secao(SECAO_FAZER) is True
    assert nota.garantir_secao(SECAO_FAZER) is False

    texto = nota.texto()
    assert texto.count("## Fazer") == 1
    assert texto.replace("## Fazer\n\n", "", 1) == NOTA
    assert texto.index("## O que estou fazendo") < texto.index("## Fazer") < texto.index("## Dúvidas")


@pytest.mark.parametrize("titulo", ["O que terminei", "Falar"])
def test_secao_aposentada_fica_intocada_e_nao_e_mais_secao(titulo):
    antiga = NOTA.replace("## Dúvidas\n", f"## {titulo}\n\n- o que estava lá\n\n## Dúvidas\n", 1)
    nota = NotaViva.de_texto(antiga)

    assert nota.texto() == antiga
    assert titulo not in [secao for secao, _ in nota.secoes()]


# -- o modelo ------------------------------------------------------------------


def test_o_modelo_tem_as_cinco_secoes_na_ordem_e_nenhuma_explicacao():
    """Ele sabe o que cada seção é (ticket 13): só o frontmatter e os títulos."""
    nota = NotaViva.do_modelo()

    assert [secao for secao, _ in nota.secoes()] == [
        SECAO_FIZ,
        SECAO_FAZENDO,
        SECAO_FAZER,
        SECAO_DUVIDAS,
        SECAO_PONTOS,
    ]
    assert all(linhas == () for _, linhas in nota.secoes())
    assert MODELO_DA_NOTA_VIVA.startswith("---\ntipo: daily-atual\n---\n")
    assert "\ndata:" not in MODELO_DA_NOTA_VIVA, "campo `data` vira link da Daily notes do Obsidian"
    assert ">" not in MODELO_DA_NOTA_VIVA
    assert [linha for linha in MODELO_DA_NOTA_VIVA.splitlines() if linha and not linha.startswith(("##", "---", "tipo:"))] == []


# -- concluir ------------------------------------------------------------------

#: *O que estou fazendo* com sub-item, linha em branco e embed dentro da subárvore,
#: espaço à direita e o item vazio que o Obsidian deixa.
FAZENDO = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "- já estava aqui\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "- FN-1786 foto extra \n"
    "\t- revisar o hub\n"
    "\n"
    "\t\t![[print.png]]\n"
    "- Achados do ribeiro\n"
    "\t- Problema A\n"
    "\t- Problema B\n"
    "- \n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- o pix expira?\n"
)
BLOCO_DA_FOTO = "- FN-1786 foto extra \n\t- revisar o hub\n\n\t\t![[print.png]]\n"


def item(nota: NotaViva, texto: str):
    return next(candidato for candidato in nota.itens(SECAO_FAZENDO) if candidato.texto == texto)


def concluir(nota: NotaViva, *textos: str) -> None:
    for texto in textos:
        alvo = item(nota, texto)
        assert nota.concluir(alvo.inicio, alvo.linha) is not None


def test_itens_trazem_a_subarvore_literal_e_os_pais_sem_o_item_vazio():
    itens = NotaViva.de_texto(FAZENDO).itens(SECAO_FAZENDO)

    assert [i.texto for i in itens] == [
        "FN-1786 foto extra",
        "revisar o hub",
        "Achados do ribeiro",
        "Problema A",
        "Problema B",
    ]
    foto, hub, achados, problema_a, _ = itens
    assert foto.linhas == ("- FN-1786 foto extra ", "\t- revisar o hub", "", "\t\t![[print.png]]")
    assert foto.ancestrais == () and hub.ancestrais == (foto.inicio,)
    assert problema_a.ancestrais == (achados.inicio,)


def test_concluir_leva_o_item_e_a_subarvore_para_o_fim_de_fiz_e_o_resto_fica_byte_a_byte():
    nota = NotaViva.de_texto(FAZENDO)
    foto = item(nota, "FN-1786 foto extra")

    assert nota.concluir(foto.inicio, foto.linha) == foto.linhas
    assert nota.texto() == FAZENDO.replace(BLOCO_DA_FOTO, "", 1).replace(
        "- já estava aqui\n", "- já estava aqui\n" + BLOCO_DA_FOTO, 1
    )


def test_concluir_um_sub_item_copia_o_pai_que_fica_em_fazendo():
    nota = NotaViva.de_texto(FAZENDO)
    problema_a = item(nota, "Problema A")

    assert nota.concluir(problema_a.inicio, problema_a.linha) == ("- Achados do ribeiro", "\t- Problema A")
    texto = nota.texto()
    assert "- já estava aqui\n- Achados do ribeiro\n\t- Problema A\n\n## O que estou fazendo\n" in texto
    assert "- Achados do ribeiro\n\t- Problema B\n- \n" in trecho(texto, SECAO_FAZENDO)


def test_concluir_dois_irmaos_copia_o_pai_uma_vez_so():
    nota = NotaViva.de_texto(FAZENDO)

    concluir(nota, "Problema A", "Problema B")

    assert trecho(nota.texto(), SECAO_FIZ).endswith(
        "- já estava aqui\n- Achados do ribeiro\n\t- Problema A\n\t- Problema B\n"
    )


def test_concluir_o_pai_depois_dos_filhos_nao_o_repete():
    nota = NotaViva.de_texto(FAZENDO)

    concluir(nota, "Problema A", "Problema B", "Achados do ribeiro")

    texto = nota.texto()
    assert trecho(texto, SECAO_FIZ).count("- Achados do ribeiro") == 1
    assert "Achados" not in trecho(texto, SECAO_FAZENDO)


def test_o_pai_nao_casa_com_o_mesmo_texto_em_outra_profundidade_de_fiz():
    nota = NotaViva.de_texto(FAZENDO.replace("- já estava aqui\n", "- já estava aqui\n\t- Achados do ribeiro\n", 1))

    concluir(nota, "Problema A")

    assert "- já estava aqui\n\t- Achados do ribeiro\n- Achados do ribeiro\n\t- Problema A\n" in nota.texto()


def test_concluir_sem_fiz_abre_a_secao_no_lugar_dela():
    nota = NotaViva.de_texto(FAZENDO.replace("## O que eu fiz\n\n- já estava aqui\n\n", "", 1))

    concluir(nota, "FN-1786 foto extra")

    assert nota.texto().startswith(
        "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n"
        + BLOCO_DA_FOTO
        + "\n## O que estou fazendo\n\n- Achados do ribeiro\n"
    )


def test_concluir_preserva_o_crlf():
    nota = NotaViva.de_texto(FAZENDO.replace("\n", "\r\n"))

    concluir(nota, "FN-1786 foto extra")

    texto = nota.texto()
    assert "\n" not in texto.replace("\r\n", "")
    assert "- já estava aqui\r\n- FN-1786 foto extra \r\n" in texto


def test_com_a_nota_mudada_acha_pela_linha_unica_ou_nao_mexe():
    achados = item(NotaViva.de_texto(FAZENDO), "Achados do ribeiro")
    topo = "## O que estou fazendo\n\n"

    deslocada = NotaViva.de_texto(FAZENDO.replace(topo, topo + "- novo no topo\n", 1))
    assert deslocada.concluir(achados.inicio, achados.linha) is not None
    assert "- Achados do ribeiro" in trecho(deslocada.texto(), SECAO_FIZ)

    renomeada = FAZENDO.replace("- Achados do ribeiro\n", "- Achados do Ribeiro\n", 1)
    sumida = NotaViva.de_texto(renomeada)
    assert sumida.concluir(achados.inicio, achados.linha) is None
    assert sumida.texto() == renomeada

    repetida = FAZENDO.replace("- \n", "- Achados do ribeiro\n", 1).replace(topo, topo + "- novo\n", 1)
    assert NotaViva.de_texto(repetida).concluir(achados.inicio, achados.linha) is None
