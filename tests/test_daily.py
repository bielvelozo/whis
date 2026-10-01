"""A costura da daily: a nota que ele escreveu vira deck publicado e cópia em `daily/`."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.daily import NOTA_DA_DAILY, escrever_nota_da_daily
from fixtures.leitura import corpo, ler_frontmatter
from whis import vault
from whis.configuracao import Configuracao
from whis.daily import gerar_daily
from whis.fakes import URL_DO_DECK_FAKE, PublicacaoDoDeckFake
from whis.nota_viva import MODELO_DA_NOTA_VIVA
from whis.portas import ErroDePublicacao

AGORA = datetime(2026, 9, 30, 13, 55, tzinfo=timezone(timedelta(hours=-3)))
ANTIGA = "https://claude.ai/artifact/DeckAntigo789"
NOVA = "https://claude.ai/artifact/DeckNovo456"


@pytest.fixture
def configuracao(caminho_do_vault: Path) -> Configuracao:
    return Configuracao(vault=caminho_do_vault)


def gerar(configuracao, publicacao, tmp_path: Path, **extras):
    return gerar_daily(AGORA, configuracao=configuracao, publicacao=publicacao, pasta=tmp_path / "trabalho", **extras)


def copia_de_hoje(caminho_do_vault: Path) -> Path:
    return caminho_do_vault / "daily" / "2026-09-30.md"


def semear(caminho_do_vault: Path, url: str, nome: str = "2026-09-29.md") -> None:
    texto = vault.montar_copia_da_daily(gerada=AGORA - timedelta(days=1), deck=url, secoes=[])
    (caminho_do_vault / "daily").mkdir(parents=True, exist_ok=True)
    (caminho_do_vault / "daily" / nome).write_text(texto, encoding="utf-8")


def test_a_nota_vira_deck_publicado_e_copia_com_o_link(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert resultado.publicado and resultado.url == URL_DO_DECK_FAKE
    assert [slide.id for slide in resultado.deck.slides] == ["fiz", "fazendo", "duvidas", "falar"]
    assert publicacao.url_recebida is None
    assert sorted(publicacao.conteudos) == [
        "project/deck.json",
        "project/slides/duvidas.html",
        "project/slides/falar.html",
        "project/slides/fazendo.html",
        "project/slides/fiz.html",
    ]
    assert json.loads(publicacao.conteudos["project/deck.json"])["order"] == ["fiz", "fazendo", "duvidas", "falar"]
    assert resultado.copia.resolve() == copia_de_hoje(caminho_do_vault).resolve()
    frente = ler_frontmatter(resultado.copia)
    assert frente["tipo"] == "daily" and frente["deck"] == URL_DO_DECK_FAKE and "data" not in frente


def test_a_copia_tem_so_as_secoes_que_viraram_slide_com_as_linhas_literais(
    configuracao, caminho_do_vault: Path, tmp_path: Path
):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    texto = corpo(resultado.copia)
    assert "## O que eu fiz\n\n- FN-123 frete do checkout corrigido\n\t- subiu em produção\n" in texto
    for fora in ("## Pontos", "## Fazer"):
        assert fora not in texto


def test_republica_no_endereco_da_copia_mais_recente_que_tem_um(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)
    semear(caminho_do_vault, ANTIGA, "2026-09-28.md")
    (caminho_do_vault / "daily" / "2026-09-29.md").write_text(
        "---\ntipo: daily\ndesde: 2026-09-28T13:55:00-03:00\n---\n\n# Daily velha\n", encoding="utf-8"
    )
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert publicacao.url_recebida == ANTIGA
    assert resultado.url == ANTIGA
    assert ler_frontmatter(resultado.copia)["deck"] == ANTIGA


def test_a_nota_com_as_quatro_secoes_do_deck_sai_byte_a_byte_igual(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)
    gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY


def test_nota_sem_as_secoes_do_deck_ganha_os_titulos_que_faltam(configuracao, caminho_do_vault: Path, tmp_path: Path):
    """A nota de verdade dele, em 2026-09-30, não tinha *O que eu fiz*, *O que estou fazendo* nem *Falar*."""
    original = "---\ntipo: daily-atual\n---\n\n## Dúvidas\n\n- uma dúvida\n\n## Fazer\n\n- [ ] uma tarefa\n"
    arquivo = escrever_nota_da_daily(caminho_do_vault, original)

    gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    texto = arquivo.read_bytes().decode("utf-8")
    for titulo in ("O que eu fiz", "O que estou fazendo", "Dúvidas", "Falar"):
        assert texto.count(f"## {titulo}\n") == 1
    assert texto.index("## O que eu fiz") < texto.index("## O que estou fazendo") < texto.index("## Fazer")
    assert "## O que terminei" not in texto
    assert "## Dúvidas\n\n- uma dúvida\n" in texto and "- [ ] uma tarefa\n" in texto


def test_simular_nao_publica_nem_escreve_nada_nem_o_titulo(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar_daily(AGORA, configuracao=configuracao, publicacao=None, simular=True)

    assert resultado.simulado and len(resultado.deck.slides) == 4
    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    assert sorted(p.name for p in (caminho_do_vault / "daily").iterdir()) == ["atual.md"]


def test_nota_vazia_nao_publica_nem_grava_copia_mas_ganha_o_titulo(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault, "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n## Falar\n")
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert resultado.vazio and publicacao.chamadas == 0
    assert not copia_de_hoje(caminho_do_vault).exists()
    assert "## O que estou fazendo" in arquivo.read_text(encoding="utf-8")


def test_sem_nota_nenhuma_grava_o_modelo_e_nao_publica(configuracao, caminho_do_vault: Path, tmp_path: Path):
    resultado = gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    assert resultado.vazio
    assert (caminho_do_vault / "daily" / "atual.md").read_bytes().decode("utf-8") == MODELO_DA_NOTA_VIVA


def test_falha_da_publicacao_grava_a_copia_com_aviso_e_o_endereco_antigo(
    configuracao, caminho_do_vault: Path, tmp_path: Path
):
    escrever_nota_da_daily(caminho_do_vault)
    semear(caminho_do_vault, ANTIGA)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("o Claude caiu")), tmp_path)

    assert not resultado.publicado and resultado.falha_da_publicacao == "o Claude caiu"
    assert ler_frontmatter(resultado.copia)["deck"] == ANTIGA
    assert "> [!warning] Os slides não saíram nesta geração: o Claude caiu" in corpo(resultado.copia)


def test_falha_depois_de_criar_guarda_o_endereco_criado(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("preencher falhou", url=NOVA)), tmp_path)

    assert resultado.url == NOVA
    assert ler_frontmatter(resultado.copia)["deck"] == NOVA


def test_falha_sem_deck_nenhum_grava_a_copia_sem_deck(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("sem conta")), tmp_path)

    assert resultado.url is None
    assert "deck" not in ler_frontmatter(resultado.copia)


def test_fora_da_simulacao_a_publicacao_e_obrigatoria(configuracao):
    with pytest.raises(ValueError):
        gerar_daily(AGORA, configuracao=configuracao, publicacao=None)
