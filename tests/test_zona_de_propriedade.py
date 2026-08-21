"""A zona de propriedade: o coletor só escreve em `reunioes/` e `transcricoes/`."""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault
from second_brain import vault as modulo_vault


@pytest.fixture
def vault_com_notas_do_usuario(caminho_do_vault: Path) -> Path:
    """Um vault já habitado: notas manuais em `notas/` e uma nota em `diario/`."""
    modulo_vault.preparar(caminho_do_vault)
    (caminho_do_vault / "notas" / "ideias.md").write_text(
        "# Minhas ideias\n\nnão encoste aqui\n", encoding="utf-8"
    )
    (caminho_do_vault / "diario" / "2026-08-19.md").write_text(
        "# 19 de agosto\n", encoding="utf-8"
    )
    return caminho_do_vault


def test_pipeline_escreve_apenas_em_reunioes_e_transcricoes(
    processar_gravacao, pasta_de_gravacao: Path, vault_com_notas_do_usuario: Path
):
    antes = arquivos_do_vault(vault_com_notas_do_usuario)

    processar_gravacao(pasta_de_gravacao)

    novos = arquivos_do_vault(vault_com_notas_do_usuario) - antes
    assert novos, "o pipeline não escreveu nada"
    assert all(
        arquivo.startswith(("reunioes/", "transcricoes/")) for arquivo in novos
    ), f"escrita fora da zona de propriedade: {sorted(novos)}"


def test_notas_do_usuario_permanecem_intactas(
    processar_gravacao, pasta_de_gravacao: Path, vault_com_notas_do_usuario: Path
):
    nota_do_usuario = vault_com_notas_do_usuario / "notas" / "ideias.md"
    conteudo = nota_do_usuario.read_text(encoding="utf-8")
    diario = vault_com_notas_do_usuario / "diario" / "2026-08-19.md"
    conteudo_diario = diario.read_text(encoding="utf-8")

    processar_gravacao(pasta_de_gravacao)

    assert nota_do_usuario.read_text(encoding="utf-8") == conteudo
    assert diario.read_text(encoding="utf-8") == conteudo_diario
    assert list((vault_com_notas_do_usuario / "notas").iterdir()) == [nota_do_usuario]


def test_o_audio_bruto_nunca_entra_no_vault(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    processar_gravacao(pasta_de_gravacao)

    assert not [
        arquivo for arquivo in arquivos_do_vault(caminho_do_vault) if arquivo.endswith(".wav")
    ]
    assert (pasta_de_gravacao / "microfone.wav").is_file()


def test_estado_da_gravacao_fica_fora_do_vault(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    processar_gravacao(pasta_de_gravacao)

    assert (pasta_de_gravacao / "estado.json").is_file()
    assert "estado.json" not in {
        Path(arquivo).name for arquivo in arquivos_do_vault(caminho_do_vault)
    }


@pytest.mark.parametrize("destino", ["notas/roubada.md", "diario/2026-08-20.md", "solta.md"])
def test_escrita_fora_da_zona_e_recusada(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(caminho_do_vault, destino, "não deveria existir")

    assert not (caminho_do_vault / destino).exists()


@pytest.mark.parametrize("zona", ["reunioes", "transcricoes"])
@pytest.mark.parametrize(
    "fuga",
    ["../notas/invadida.md", "../diario/invadida.md", "../../fora-do-vault.md", "sub/../../notas/invadida.md"],
)
def test_traversal_para_fora_da_zona_e_recusado(caminho_do_vault: Path, zona: str, fuga: str):
    modulo_vault.preparar(caminho_do_vault)
    destino = f"{zona}/{fuga}"

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(caminho_do_vault, destino, "ESCRITA INDEVIDA")

    assert list((caminho_do_vault / "notas").iterdir()) == []
    assert list((caminho_do_vault / "diario").iterdir()) == []
    assert not (caminho_do_vault.parent / "fora-do-vault.md").exists()


@pytest.mark.parametrize("destino", ["", "reunioes", "transcricoes/"])
def test_caminho_sem_arquivo_e_recusado(caminho_do_vault: Path, destino: str):
    modulo_vault.preparar(caminho_do_vault)

    with pytest.raises(modulo_vault.ForaDaZonaDePropriedade):
        modulo_vault.escrever(caminho_do_vault, destino, "sem nome de arquivo")


def test_subpasta_dentro_da_zona_continua_permitida(caminho_do_vault: Path):
    modulo_vault.preparar(caminho_do_vault)

    escrito = modulo_vault.escrever(caminho_do_vault, "reunioes/2026/nota.md", "conteúdo")

    assert escrito.read_text(encoding="utf-8") == "conteúdo"
    assert escrito.is_relative_to(caminho_do_vault / "reunioes")
