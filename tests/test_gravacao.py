"""A pasta de gravação como o contrato a define."""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao, criar_wav
from fixtures.leitura import corpo
from second_brain.gravacao import GravacaoInvalida, ler


def test_pasta_com_nome_fora_do_contrato_e_recusada(caminho_das_gravacoes: Path):
    pasta = caminho_das_gravacoes / "gravacao-qualquer"
    criar_wav(pasta / "microfone.wav")

    with pytest.raises(GravacaoInvalida):
        ler(pasta)


def test_pasta_sem_audio_e_recusada(caminho_das_gravacoes: Path):
    pasta = caminho_das_gravacoes / "2026-08-20-1430-vazia"
    pasta.mkdir()

    with pytest.raises(GravacaoInvalida):
        ler(pasta)


def test_gravacao_sem_o_canal_de_sistema_ainda_vira_nota(
    processar_gravacao, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-08-20-1430-so-microfone", com_sistema=False
    )

    resultado = processar_gravacao(pasta)

    assert resultado.nota.is_file()
    assert resultado.gravacao.canais.sistema is None


def test_pasta_sem_metadados_usa_os_arquivos_encontrados(
    processar_gravacao, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-20-1430-sem-json")
    (pasta / "gravacao.json").unlink()

    resultado = processar_gravacao(pasta)

    assert resultado.gravacao.canais.microfone is not None
    assert resultado.gravacao.canais.sistema is not None
    assert "# sem json" in corpo(resultado.nota)
