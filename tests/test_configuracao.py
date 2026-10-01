"""A configuração local: o caminho do vault e as opções vindos do TOML."""

from __future__ import annotations

from pathlib import Path

import pytest

from whis.configuracao import (
    VARIAVEL_DE_AMBIENTE,
    ConfiguracaoInvalida,
    carregar,
)


def test_variavel_de_ambiente_aponta_a_configuracao(
    arquivo_de_configuracao: Path, caminho_do_vault: Path
):
    configuracao = carregar()

    assert configuracao.vault == Path(caminho_do_vault)
    assert configuracao.origem == arquivo_de_configuracao


def test_caminho_explicito_prevalece_sobre_a_variavel(
    arquivo_de_configuracao: Path, tmp_path: Path
):
    outro = tmp_path / "outro.toml"
    outro.write_text('vault = "V"\n', encoding="utf-8")

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


def test_configuracao_sem_o_vault_e_recusada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text('[claude]\nmodelo = ""\n', encoding="utf-8")
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))

    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar()

    assert "vault" in str(erro.value)


def test_as_chaves_da_gravacao_que_saiu_sao_ignoradas(tmp_path: Path):
    """O config.toml de quando o Whis gravava reunião continua carregando sem edição."""
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        'vault = "V"\ngravacoes = "G"\nretencao_dias = -1\n\n'
        '[deepgram]\napi_key = "dg"\n\n[audio]\ndispositivo_microfone = "Mic"\n',
        encoding="utf-8",
    )

    configuracao = carregar(arquivo)

    assert configuracao.vault == Path("V")
    assert not hasattr(configuracao, "gravacoes")


def test_modelo_do_claude_vem_da_configuracao_local(tmp_path: Path, monkeypatch):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        'vault = "V"\n\n[claude]\nmodelo = "claude-opus-5"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))

    assert carregar().claude_modelo == "claude-opus-5"


def test_sem_secao_claude_o_modelo_fica_vazio(arquivo_de_configuracao: Path):
    assert carregar().claude_modelo == ""
