"""A zona de propriedade: cada escrita só alcança as zonas que a chamada permite."""

from __future__ import annotations

from pathlib import Path

import pytest

from whis import vault as modulo_vault


def test_so_o_coletor_da_granola_alcanca_reunioes_e_ninguem_alcanca_transcricoes():
    """`reunioes/` é do coletor da Granola; `transcricoes/` só é lida desde que a gravação saiu."""
    zonas = {
        nome: valor
        for nome, valor in vars(modulo_vault).items()
        if nome.startswith("ZONAS_") and isinstance(valor, tuple)
    }

    assert zonas
    assert modulo_vault.ZONAS_DAS_REUNIOES == ("reunioes",)
    for nome, permitidas in zonas.items():
        assert "transcricoes" not in permitidas, nome
        if nome != "ZONAS_DAS_REUNIOES":
            assert "reunioes" not in permitidas, nome


@pytest.mark.parametrize(
    "destino", ["notas/roubada.md", "daily/2026-08-20.md", "reunioes/2026-08-20-1400-x.md", "solta.md"]
)
def test_escrita_fora_da_zona_e_recusada(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault, destino, "não deveria existir", zonas=modulo_vault.ZONAS_DO_DIARIO
        )

    assert not (caminho_do_vault / destino).exists()


@pytest.mark.parametrize("zona", ["diario", "daily"])
@pytest.mark.parametrize(
    "fuga",
    ["../notas/invadida.md", "../reunioes/invadida.md", "../../fora-do-vault.md", "sub/../../notas/invadida.md"],
)
def test_traversal_para_fora_da_zona_e_recusado(caminho_do_vault: Path, zona: str, fuga: str):
    modulo_vault.preparar(caminho_do_vault)
    destino = f"{zona}/{fuga}"

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(caminho_do_vault, destino, "ESCRITA INDEVIDA", zonas=(zona,))

    assert list((caminho_do_vault / "notas").iterdir()) == []
    assert list((caminho_do_vault / "reunioes").iterdir()) == []
    assert not (caminho_do_vault.parent / "fora-do-vault.md").exists()


@pytest.mark.parametrize("destino", ["", "diario", "diario/"])
def test_caminho_sem_arquivo_e_recusado(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(
            caminho_do_vault, destino, "sem nome de arquivo", zonas=modulo_vault.ZONAS_DO_DIARIO
        )


def test_subpasta_dentro_da_zona_continua_permitida(caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)

    escrito = modulo_vault.escrever(
        caminho_do_vault, "diario/2026/nota.md", "conteúdo", zonas=modulo_vault.ZONAS_DO_DIARIO
    )

    assert escrito.read_text(encoding="utf-8") == "conteúdo"
    assert escrito.is_relative_to(caminho_do_vault / "diario")
