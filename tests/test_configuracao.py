"""A configuração local: caminho do vault e das gravações vindos do TOML."""

from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.configuracao import (
    VARIAVEL_DE_AMBIENTE,
    ConfiguracaoInvalida,
    carregar,
)


def test_variavel_de_ambiente_aponta_a_configuracao(
    arquivo_de_configuracao: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path
):
    configuracao = carregar()

    assert configuracao.vault == Path(caminho_do_vault)
    assert configuracao.gravacoes == Path(caminho_das_gravacoes)
    assert configuracao.retencao_dias == 7
    assert configuracao.origem == arquivo_de_configuracao


def test_caminho_explicito_prevalece_sobre_a_variavel(
    arquivo_de_configuracao: Path, tmp_path: Path
):
    outro = tmp_path / "outro.toml"
    outro.write_text('vault = "V"\ngravacoes = "G"\n', encoding="utf-8")

    configuracao = carregar(outro)

    assert configuracao.vault == Path("V")


def test_configuracao_ausente_diz_qual_arquivo_criar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    inexistente = tmp_path / "nao-existe.toml"
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(inexistente))

    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar()

    assert str(inexistente) in str(erro.value)


def test_configuracao_sem_os_caminhos_obrigatorios_e_recusada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text("retencao_dias = 7\n", encoding="utf-8")
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))

    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar()

    assert "vault" in str(erro.value)
    assert "gravacoes" in str(erro.value)


def test_chave_da_deepgram_vem_da_configuracao_local(tmp_path: Path, monkeypatch):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        'vault = "V"\ngravacoes = "G"\n\n[deepgram]\napi_key = "chave-de-teste"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))

    assert carregar().deepgram_api_key == "chave-de-teste"
