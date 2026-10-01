"""Os subcomandos da CLI: `init`, a configuração ausente e os comandos que saíram.

Os demais subcomandos têm arquivo próprio (`test_comando_diario`,
`test_comando_daily`, `test_comando_perguntar`, `test_casca_do_jornal`...).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whis.__main__ import main
from whis.configuracao import VARIAVEL_DE_AMBIENTE, carregar


def test_comando_falha_quando_nao_ha_configuracao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(tmp_path / "sem-config.toml"))

    codigo = main(["diario", "--fakes"])

    assert codigo == 1
    assert "Configuração não encontrada" in caplog.text


@pytest.mark.parametrize("comando", ["processar", "reprocessar", "limpar"])
def test_os_comandos_da_gravacao_nao_existem_mais(comando: str):
    with pytest.raises(SystemExit) as saida:
        main([comando])

    assert saida.value.code == 2


def test_windows_nao_agenda_mais_a_limpeza():
    with pytest.raises(SystemExit) as saida:
        main(["windows", "--limpeza"])

    assert saida.value.code == 2


# -- init -------------------------------------------------------------------


def test_comando_init_cria_a_configuracao_com_o_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    destino = tmp_path / "config.toml"

    codigo = main(["init", "--config", str(destino)])

    assert codigo == 0
    conteudo = destino.read_text(encoding="utf-8")
    assert "vault" in conteudo
    assert "gravacoes" not in conteudo and "[deepgram]" not in conteudo and "[audio]" not in conteudo
    assert "\\" not in conteudo  # caminhos com barra normal, como o TOML exige
    assert "Próximos passos" in capsys.readouterr().out


def test_configuracao_criada_pelo_init_e_lida_sem_erro(tmp_path: Path):
    """O que o init escreve tem que passar pelo carregador — senão não serve."""
    destino = tmp_path / "config.toml"
    main(["init", "--config", str(destino)])

    configuracao = carregar(destino)

    assert configuracao.vault.name == "whis-vault"
    assert configuracao.claude_modelo == ""


def test_comando_init_nao_sobrescreve_configuracao_existente(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    destino = tmp_path / "config.toml"
    destino.write_text('vault = "V"\n', encoding="utf-8")

    codigo = main(["init", "--config", str(destino)])

    assert codigo == 1
    assert destino.read_text(encoding="utf-8").startswith('vault = "V"')
    assert "--forcar" in capsys.readouterr().out or "forcar" in capsys.readouterr().out


def test_comando_init_forcar_sobrescreve(tmp_path: Path):
    destino = tmp_path / "config.toml"
    destino.write_text('vault = "V"\n', encoding="utf-8")

    assert main(["init", "--config", str(destino), "--forcar"]) == 0
    assert "[claude]" in destino.read_text(encoding="utf-8")
