"""O que todo adaptador do Claude divide: o prazo para o CLI começar a responder."""

from __future__ import annotations

import os

import pytest

from whis import claude_cli


def test_o_cli_ganha_tres_minutos_para_iniciar(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", raising=False)

    claude_cli.dar_tempo_ao_inicio()

    assert int(os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"]) == claude_cli.INICIO_DO_CLI_MS >= 180_000


def test_prazo_que_alguem_ja_pos_no_ambiente_fica(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "300000")

    claude_cli.dar_tempo_ao_inicio()

    assert os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] == "300000"
