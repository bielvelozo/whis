"""Fixtures das duas costuras do repositório.

A da reunião — `processar(pasta) → arquivos no vault` — se monta com um vault
em `tmp_path`, uma pasta de gravação de fixture, uma configuração local
apontada por `WHIS_CONFIG` e as portas fake. A do diário —
`gerar_diario(data) → nota em diario/` — reaproveita o mesmo vault e ganha uma
configuração própria, porque a janela do dia e o filtro de exclusão mudam de
teste para teste.

As camadas seguintes reaproveitam tudo isto: trocar um fake por um adaptador é
injetar outro objeto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao
from whis import pipeline
from whis.configuracao import VARIAVEL_DE_AMBIENTE, Configuracao, carregar
from whis.fakes import ResumoFake, STTFake


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
    """Escreve um `config.toml` de teste e aponta `WHIS_CONFIG` para ele."""
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
def configuracao_do_diario(
    tmp_path: Path,
    caminho_do_vault: Path,
    caminho_das_gravacoes: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Fábrica da configuração do diário: `configuracao_do_diario(...)`.

    Escreve um `config.toml` com a janela e o filtro que o teste precisa e
    aponta `WHIS_CONFIG` para ele — assim o mesmo cenário serve à
    costura e ao subcomando.
    """

    def montar(
        *, inicio_do_dia: str = "04:00", excluir: tuple[str, ...] = ()
    ) -> Configuracao:
        linhas = [
            f'vault = "{caminho_do_vault.as_posix()}"',
            f'gravacoes = "{caminho_das_gravacoes.as_posix()}"',
            "",
            "[diario]",
            f'inicio_do_dia = "{inicio_do_dia}"',
            "",
            "[privacidade]",
            "excluir = [" + ", ".join(f'"{padrao}"' for padrao in excluir) + "]",
            "",
        ]
        arquivo = tmp_path / "config-do-diario.toml"
        arquivo.write_text("\n".join(linhas), encoding="utf-8")
        monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
        return carregar(arquivo)

    return montar


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
