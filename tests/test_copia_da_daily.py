"""A cópia em `daily/YYYY-MM-DD.md`: o que foi para o deck, e o link de onde a próxima republica."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fixtures.leitura import corpo, ler_frontmatter
from whis import vault

AGORA = datetime(2026, 9, 30, 13, 55, tzinfo=timezone(timedelta(hours=-3)))
URL = "https://claude.ai/artifact/DeckDaDaily123"
ANTIGA = "https://claude.ai/artifact/DeckAntigo789"
SECOES = [("O que eu fiz", ("- FN-123 frete", "\t- subiu")), ("Falar", ("- sexta saio cedo",))]


def escrever(pasta: Path, texto: str, nome: str = "2026-09-30.md") -> Path:
    arquivo = pasta / "daily" / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def test_a_copia_tem_tipo_deck_e_hora_e_nenhum_campo_data(tmp_path: Path):
    arquivo = escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES))

    assert ler_frontmatter(arquivo) == {"tipo": "daily", "deck": URL, "gerada": "2026-09-30T13:55:00-03:00"}


def test_a_copia_guarda_as_secoes_com_as_linhas_literais_e_o_link(tmp_path: Path):
    texto = corpo(escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES)))

    assert texto.lstrip().startswith("# Daily — 30 de setembro de 2026 (quarta-feira)\n")
    assert f"> [!info] [Abrir os slides]({URL})" in texto
    assert "## O que eu fiz\n\n- FN-123 frete\n\t- subiu\n\n## Falar\n\n- sexta saio cedo\n" in texto


def test_sem_deck_a_copia_nao_tem_o_campo_nem_o_link(tmp_path: Path):
    arquivo = escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=None, secoes=SECOES))

    assert "deck" not in ler_frontmatter(arquivo)
    assert "Abrir os slides" not in corpo(arquivo)


def test_o_aviso_vira_callout(tmp_path: Path):
    arquivo = escrever(
        tmp_path,
        vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES, aviso="Os slides não saíram: x"),
    )

    assert "> [!warning] Os slides não saíram: x" in corpo(arquivo)


def test_o_endereco_vem_da_copia_mais_recente_que_tem_um(tmp_path: Path):
    escrever(
        tmp_path,
        vault.montar_copia_da_daily(gerada=AGORA - timedelta(days=2), deck=ANTIGA, secoes=SECOES),
        "2026-09-28.md",
    )
    escrever(tmp_path, "---\ntipo: daily\ndata: 2026-09-29\ndesde: 2026-09-28T13:55:00-03:00\n---\n\n# Antiga\n", "2026-09-29.md")
    escrever(tmp_path, "---\ntipo: daily-atual\n---\n", "atual.md")

    assert vault.ultimo_deck(tmp_path) == ANTIGA

    escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES))

    assert vault.ultimo_deck(tmp_path) == URL


def test_sem_copia_com_deck_nao_ha_endereco(tmp_path: Path):
    assert vault.ultimo_deck(tmp_path) is None

    escrever(tmp_path, "sem frontmatter nenhum", "2026-09-29.md")

    assert vault.ultimo_deck(tmp_path) is None
