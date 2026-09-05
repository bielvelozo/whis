"""As chaves do atendente no `config.toml`: o bot token e o app-level token.

Nascem vazias — configuração antiga continua carregando — e são conferidas
pelo prefixo: a página da app mostra três tokens parecidos, e colar o errado só
se revelaria com o atendente já no ar, sem console.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from second_brain.__main__ import MODELO_DE_CONFIGURACAO
from second_brain.configuracao import ConfiguracaoInvalida, carregar


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\ngravacoes = "G"\n{corpo}', encoding="utf-8")
    return arquivo


def test_configuracao_sem_os_tokens_do_atendente_continua_carregando(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, ""))

    assert configuracao.slack_bot_token == ""
    assert configuracao.slack_app_token == ""


def test_os_dois_tokens_chegam_achatados_e_sem_espacos(tmp_path: Path):
    configuracao = carregar(
        escrever(tmp_path, '\n[slack]\nbot_token = " xoxb-EXEMPLO "\napp_token = "xapp-EXEMPLO"\n')
    )

    assert configuracao.slack_bot_token == "xoxb-EXEMPLO"
    assert configuracao.slack_app_token == "xapp-EXEMPLO"


def test_user_token_no_lugar_do_bot_token_e_apontado_pelo_nome(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, '\n[slack]\nbot_token = "xoxp-EXEMPLO"\n'))

    mensagem = str(erro.value)
    assert "[slack].bot_token" in mensagem
    assert "xoxb-" in mensagem
    assert "User OAuth Token" in mensagem
    assert "EXEMPLO" not in mensagem


def test_bot_token_no_lugar_do_app_token_e_apontado(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, '\n[slack]\napp_token = "xoxb-EXEMPLO"\n'))

    assert "[slack].app_token" in str(erro.value)
    assert "xapp-" in str(erro.value)


def test_token_de_tipo_desconhecido_tambem_e_recusado(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, '\n[slack]\nbot_token = "abc"\n'))

    assert "outro tipo" in str(erro.value)


def test_o_modelo_de_configuracao_traz_as_duas_chaves_vazias():
    dados = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V", gravacoes="G"))

    assert dados["slack"]["bot_token"] == ""
    assert dados["slack"]["app_token"] == ""
