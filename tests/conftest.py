"""Fixtures da costura única do repositório: `processar(pasta) → arquivos no vault`.

Todo teste de comportamento do pipeline se monta a partir daqui: um vault em
`tmp_path`, uma pasta de gravação de fixture, uma configuração local apontada
por `SECOND_BRAIN_CONFIG` e as portas fake. As camadas 03, 04 e 06 reaproveitam
estas fixtures — trocar o fake por um adaptador é injetar outro objeto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao
from second_brain import pipeline
from second_brain.configuracao import VARIAVEL_DE_AMBIENTE, Configuracao, carregar
from second_brain.fakes import ResumoFake, STTFake


@pytest.fixture
def caminho_do_vault(tmp_path: Path) -> Path:
    """Onde o vault deve nascer — de propósito, ainda não existe."""
    return tmp_path / "vault"


@pytest.fixture
def caminho_das_gravacoes(tmp_path: Path) -> Path:
    """A pasta de gravações brutas, sempre fora do vault."""
    caminho = tmp_path / "gravacoes"
    caminho.mkdir()
    return caminho


@pytest.fixture
def arquivo_de_configuracao(
    tmp_path: Path,
    caminho_do_vault: Path,
    caminho_das_gravacoes: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Escreve um `config.toml` de teste e aponta `SECOND_BRAIN_CONFIG` para ele."""
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        "\n".join(
            [
                f'vault = "{caminho_do_vault.as_posix()}"',
                f'gravacoes = "{caminho_das_gravacoes.as_posix()}"',
                "retencao_dias = 7",
                "",
                "[deepgram]",
                'api_key = ""',
                "",
                "[audio]",
                'dispositivo_microfone = ""',
                'dispositivo_sistema = ""',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
    return arquivo


@pytest.fixture
def configuracao(arquivo_de_configuracao: Path) -> Configuracao:
    """A configuração como o comando a lê: do disco, pela variável de ambiente."""
    return carregar()


@pytest.fixture
def pasta_de_gravacao(caminho_das_gravacoes: Path) -> Path:
    """Uma pasta de gravação completa, com os dois canais em WAV de verdade."""
    return criar_pasta_de_gravacao(caminho_das_gravacoes)


@pytest.fixture
def stt() -> STTFake:
    """Porta de STT fake — transcrição fixa, pt-BR com termos em inglês."""
    return STTFake()


@pytest.fixture
def resumo() -> ResumoFake:
    """Porta de resumo fake — decisões, ações e tópicos fixos."""
    return ResumoFake()


@pytest.fixture
def processar_gravacao(configuracao: Configuracao, stt: STTFake, resumo: ResumoFake):
    """Roda a costura com as portas fake: `processar_gravacao(pasta)`."""

    def executar(pasta: Path, **extras):
        return pipeline.processar(
            pasta,
            configuracao=extras.pop("configuracao", configuracao),
            stt=extras.pop("stt", stt),
            resumo=extras.pop("resumo", resumo),
            **extras,
        )

    return executar
