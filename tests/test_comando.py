"""O subcomando `processar` — a mesma costura, pela linha de comando."""

from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.__main__ import main
from second_brain.configuracao import VARIAVEL_DE_AMBIENTE


def test_comando_processar_escreve_a_nota_no_vault(
    arquivo_de_configuracao: Path, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    codigo = main(["processar", str(pasta_de_gravacao)])

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()
    assert (caminho_do_vault / "transcricoes" / "2026-08-20-1430-daily-do-time.md").is_file()


def test_comando_aceita_a_configuracao_por_argumento(
    arquivo_de_configuracao: Path,
    pasta_de_gravacao: Path,
    caminho_do_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(VARIAVEL_DE_AMBIENTE, raising=False)

    codigo = main(["processar", str(pasta_de_gravacao), "--config", str(arquivo_de_configuracao)])

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


def test_comando_falha_com_mensagem_quando_a_pasta_nao_existe(
    arquivo_de_configuracao: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    codigo = main(["processar", str(tmp_path / "2026-08-20-1430-inexistente")])

    assert codigo == 1
    assert "não encontrada" in caplog.text


def test_comando_falha_quando_nao_ha_configuracao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(tmp_path / "sem-config.toml"))

    codigo = main(["processar", str(tmp_path)])

    assert codigo == 1
    assert "Configuração não encontrada" in caplog.text
