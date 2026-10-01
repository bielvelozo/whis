"""A fronteira das ferramentas do vault, sondada nos dois sentidos.

O teste que mais importa desta entrega: um arquivo sob a pasta privada não
aparece na busca, não é lido, não é listado — nem por `..`, nem por barra
invertida, nem por link —, e a recusa diz "não existe", nunca "é privado". O
outro sentido é igualmente obrigatório: a nota pública ao lado, com nome
parecido, continua visível. Uma fronteira que esconde tudo passaria no primeiro
teste e seria inútil.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fixtures.busca import (
    CONTEUDO_PRIVADO,
    NOTA_DE_REUNIAO,
    NOTA_DO_USUARIO,
    NOTA_NA_LIXEIRA,
    NOTA_PRIVADA,
    NOTA_PRIVADA_FUNDA,
    NOTA_PUBLICA,
    NOTA_PUBLICA_ANTIGA,
    NOTA_VIZINHA_DA_PRIVADA,
    PASTA_PRIVADA,
    configuracao_da_busca,
    habitar_vault,
)
from fixtures.leitura import arquivos_do_vault
from whis.ferramentas import Ferramentas, ForaDaFronteira, LimiteDeNotas

TERMO = "retenção 180"


@pytest.fixture
def vault(caminho_do_vault: Path) -> Path:
    return habitar_vault(caminho_do_vault)


@pytest.fixture
def ferramentas_de(tmp_path: Path, vault: Path):
    """Fábrica: `ferramentas_de(pastas_privadas=(...), maximo_de_notas=N)`."""

    def montar(**chaves) -> Ferramentas:
        return Ferramentas(
            configuracao_da_busca(tmp_path, vault, **chaves)
        )

    return montar


@pytest.fixture
def ferramentas(ferramentas_de) -> Ferramentas:
    """As ferramentas com `notas/pessoal` privada — o cenário da entrega."""
    return ferramentas_de(pastas_privadas=(PASTA_PRIVADA,))


def caminhos(achados) -> list[str]:
    return [achado.caminho for achado in achados]


# -- A busca ----------------------------------------------------------------


def test_busca_acha_a_nota_publica_e_diz_a_linha(ferramentas: Ferramentas):
    achados = ferramentas.buscar_no_vault(TERMO)

    da_daily = [achado for achado in achados if achado.caminho == NOTA_PUBLICA]
    assert len(da_daily) == 1
    assert da_daily[0].linha == 3
    assert "Retenção de 180 dias" in da_daily[0].trecho


def test_busca_nao_diferencia_acento_nem_maiusculas(ferramentas: Ferramentas):
    assert NOTA_PUBLICA in caminhos(ferramentas.buscar_no_vault("RETENCAO 180"))


def test_busca_exige_todas_as_palavras_do_termo(ferramentas: Ferramentas):
    assert NOTA_PUBLICA in caminhos(ferramentas.buscar_no_vault("Luan retenção"))
    assert NOTA_PUBLICA not in caminhos(ferramentas.buscar_no_vault("Luan logs"))


def test_busca_nao_alcanca_a_pasta_privada(ferramentas: Ferramentas):
    encontrados = caminhos(ferramentas.buscar_no_vault(TERMO))

    assert encontrados, "o termo existe em notas públicas e a busca não achou nada"
    assert not [caminho for caminho in encontrados if caminho.startswith(PASTA_PRIVADA + "/")]
    assert NOTA_PRIVADA not in encontrados
    assert NOTA_PRIVADA_FUNDA not in encontrados


def test_busca_ve_a_vizinha_de_nome_parecido_com_a_pasta_privada(ferramentas: Ferramentas):
    """`notas/pessoal-trabalho.md` não está sob `notas/pessoal/` — prefixo de texto não é fronteira."""
    assert NOTA_VIZINHA_DA_PRIVADA in caminhos(ferramentas.buscar_no_vault(TERMO))


def test_o_conteudo_privado_nunca_aparece_num_trecho(ferramentas: Ferramentas):
    trechos = [achado.trecho for achado in ferramentas.buscar_no_vault("terapia")]

    assert trechos == []
    assert not any(CONTEUDO_PRIVADO in trecho for trecho in trechos)


def test_busca_ignora_as_pastas_do_obsidian(ferramentas: Ferramentas):
    assert NOTA_NA_LIXEIRA not in caminhos(ferramentas.buscar_no_vault(TERMO))


def test_dentro_de_uma_pasta_a_nota_mais_recente_vem_primeiro(ferramentas: Ferramentas):
    encontrados = caminhos(ferramentas.buscar_no_vault(TERMO))

    assert encontrados.index(NOTA_PUBLICA) < encontrados.index(NOTA_PUBLICA_ANTIGA)


def test_busca_respeita_o_limite(ferramentas: Ferramentas):
    assert len(ferramentas.buscar_no_vault(TERMO, limite=2)) == 2


@pytest.mark.parametrize("termo", ["", "   ", "\n"])
def test_busca_com_termo_vazio_nao_devolve_nada(ferramentas: Ferramentas, termo: str):
    assert ferramentas.buscar_no_vault(termo) == ()


def test_sem_pasta_privada_configurada_o_vault_inteiro_e_visivel(ferramentas_de):
    """A lista nasce vazia: até o usuário escolher a pasta, tudo é visível."""
    ferramentas = ferramentas_de()

    assert NOTA_PRIVADA in caminhos(ferramentas.buscar_no_vault(TERMO))
    assert ferramentas.ler_nota(NOTA_PRIVADA) == CONTEUDO_PRIVADO + "\n"


# -- A leitura --------------------------------------------------------------


def test_ler_nota_publica_devolve_o_conteudo(ferramentas: Ferramentas):
    assert "Retenção de 180 dias ficou decidida" in ferramentas.ler_nota(NOTA_PUBLICA)


@pytest.mark.parametrize(
    "caminho",
    [
        NOTA_PRIVADA,
        NOTA_PRIVADA_FUNDA,
        "notas/./pessoal/terapia.md",
        "notas\\pessoal\\terapia.md",
        "reunioes/../notas/pessoal/terapia.md",
        "notas/pessoal",
        "  notas/pessoal/terapia.md  ",
    ],
)
def test_ler_sob_a_pasta_privada_diz_que_nao_existe(ferramentas: Ferramentas, caminho: str):
    with pytest.raises(ForaDaFronteira) as erro:
        ferramentas.ler_nota(caminho)

    assert "Não existe" in str(erro.value)
    assert "privad" not in str(erro.value).lower()
    assert CONTEUDO_PRIVADO not in str(erro.value)


@pytest.mark.parametrize(
    "fuga", ["../fora.md", "reunioes/../../fora.md", "notas/../../fora.md", ""]
)
def test_ler_fora_do_vault_diz_que_nao_existe(ferramentas: Ferramentas, vault: Path, fuga: str):
    (vault.parent / "fora.md").write_text("FORA DO VAULT\n", encoding="utf-8")

    with pytest.raises(ForaDaFronteira) as erro:
        ferramentas.ler_nota(fuga)

    assert "Não existe" in str(erro.value)


def test_caminho_absoluto_diz_que_nao_existe_mesmo_apontando_para_dentro(
    ferramentas: Ferramentas, vault: Path
):
    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota(str(vault / NOTA_PUBLICA))


def test_a_recusa_do_privado_e_identica_a_do_inexistente(ferramentas: Ferramentas):
    """Se as mensagens diferissem, a diferença já contaria que há algo escondido."""
    with pytest.raises(ForaDaFronteira) as privado:
        ferramentas.ler_nota("notas/pessoal/terapia.md")
    with pytest.raises(ForaDaFronteira) as inexistente:
        ferramentas.ler_nota("notas/inventada/terapia.md")

    assert str(privado.value) == "Não existe no vault: 'notas/pessoal/terapia.md'"
    assert str(inexistente.value) == "Não existe no vault: 'notas/inventada/terapia.md'"


def test_ler_uma_pasta_diz_que_nao_existe(ferramentas: Ferramentas):
    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota("daily")


def ligar_pasta(destino: Path, atalho: Path) -> None:
    """Um link de pasta: simbólico onde der, junção no Windows sem privilégio."""
    try:
        os.symlink(destino, atalho, target_is_directory=True)
        return
    except OSError:
        pass
    try:
        import _winapi

        _winapi.CreateJunction(str(destino), str(atalho))
    except (ImportError, OSError):
        pytest.skip("esta máquina não deixa criar link de pasta")


def test_link_para_dentro_da_pasta_privada_nao_atravessa(ferramentas: Ferramentas, vault: Path):
    """Um atalho numa pasta pública apontando para a privada não é porta de entrada."""
    ligar_pasta(vault / PASTA_PRIVADA, vault / "reunioes" / "atalho")

    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota("reunioes/atalho/terapia.md")
    encontrados = caminhos(ferramentas.buscar_no_vault(TERMO))
    assert not [caminho for caminho in encontrados if "atalho" in caminho]
    assert not any(CONTEUDO_PRIVADO in achado.trecho for achado in ferramentas.buscar_no_vault(TERMO))
    assert "reunioes/atalho/" not in ferramentas.listar("reunioes")
    with pytest.raises(ForaDaFronteira):
        ferramentas.listar("reunioes/atalho")


def test_link_para_fora_do_vault_nao_atravessa(ferramentas: Ferramentas, vault: Path):
    fora = vault.parent / "fora-do-vault"
    fora.mkdir()
    (fora / "segredo.md").write_text("retenção de 180 dias fora do vault\n", encoding="utf-8")
    ligar_pasta(fora, vault / "reunioes" / "externo")

    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota("reunioes/externo/segredo.md")
    assert not [caminho for caminho in caminhos(ferramentas.buscar_no_vault(TERMO)) if "externo" in caminho]
    assert "reunioes/externo/" not in ferramentas.listar("reunioes")


# -- A listagem -------------------------------------------------------------


def test_listar_a_raiz_esconde_a_pasta_privada_e_as_do_obsidian(ferramentas: Ferramentas):
    entradas = ferramentas.listar()

    assert "daily/" in entradas
    assert "notas/" in entradas
    assert "reunioes/" in entradas
    assert not any(entrada.startswith(".") for entrada in entradas)


def test_listar_notas_mostra_a_vizinha_e_esconde_a_pasta_privada(ferramentas: Ferramentas):
    assert ferramentas.listar("notas") == (NOTA_DO_USUARIO, NOTA_VIZINHA_DA_PRIVADA)


@pytest.mark.parametrize("pasta", ["notas/pessoal", "notas/pessoal/", "notas\\pessoal", "notas/pessoal/2026"])
def test_listar_a_pasta_privada_diz_que_nao_existe(ferramentas: Ferramentas, pasta: str):
    with pytest.raises(ForaDaFronteira) as erro:
        ferramentas.listar(pasta)

    assert "Não existe" in str(erro.value)
    assert "privad" not in str(erro.value).lower()


@pytest.mark.parametrize("pasta", ["..", "../", "daily/../..", "inexistente"])
def test_listar_fora_do_vault_ou_pasta_inexistente_diz_que_nao_existe(
    ferramentas: Ferramentas, pasta: str
):
    with pytest.raises(ForaDaFronteira):
        ferramentas.listar(pasta)


def test_listar_uma_pasta_publica_traz_os_caminhos_relativos_ao_vault(ferramentas: Ferramentas):
    assert ferramentas.listar("reunioes") == (NOTA_DE_REUNIAO,)


# -- A fronteira é uma só ---------------------------------------------------


def test_varias_pastas_privadas_valem_para_as_tres_ferramentas(ferramentas_de):
    ferramentas = ferramentas_de(pastas_privadas=(PASTA_PRIVADA, "reunioes"))

    encontrados = caminhos(ferramentas.buscar_no_vault(TERMO))
    assert NOTA_DE_REUNIAO not in encontrados
    assert NOTA_PRIVADA not in encontrados
    assert NOTA_PUBLICA in encontrados
    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota(NOTA_DE_REUNIAO)
    assert "reunioes/" not in ferramentas.listar()


def test_nenhuma_ferramenta_escreve_no_vault(ferramentas: Ferramentas, vault: Path):
    antes = {caminho: (vault / caminho).read_bytes() for caminho in arquivos_do_vault(vault)}

    ferramentas.buscar_no_vault(TERMO)
    ferramentas.ler_nota(NOTA_PUBLICA)
    ferramentas.listar()
    ferramentas.listar("notas")

    assert {caminho: (vault / caminho).read_bytes() for caminho in arquivos_do_vault(vault)} == antes


# -- O teto de notas por pergunta -------------------------------------------


def test_o_teto_de_notas_vale_por_pergunta_e_reler_nao_conta(ferramentas_de):
    ferramentas = ferramentas_de(maximo_de_notas=2)

    ferramentas.ler_nota(NOTA_PUBLICA)
    ferramentas.ler_nota(NOTA_PUBLICA_ANTIGA)
    ferramentas.ler_nota(NOTA_PUBLICA)
    with pytest.raises(LimiteDeNotas) as erro:
        ferramentas.ler_nota(NOTA_DE_REUNIAO)

    assert "maximo_de_notas" in str(erro.value)
    assert ferramentas.notas_lidas == 2
    assert ferramentas_de(maximo_de_notas=2).ler_nota(NOTA_DE_REUNIAO)


def test_o_teto_nao_conta_leitura_recusada(ferramentas_de):
    ferramentas = ferramentas_de(pastas_privadas=(PASTA_PRIVADA,), maximo_de_notas=1)

    with pytest.raises(ForaDaFronteira):
        ferramentas.ler_nota(NOTA_PRIVADA)

    assert ferramentas.notas_lidas == 0
    assert ferramentas.ler_nota(NOTA_PUBLICA)
