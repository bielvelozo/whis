"""As chaves das fontes passivas no `config.toml`: diário, privacidade e fontes.

Todas nascem com padrão, e o teste mais importante deste arquivo é o primeiro:
uma configuração escrita antes desta entrega continua carregando sem edição.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whis.configuracao import ConfiguracaoInvalida, carregar


def escrever(tmp_path: Path, corpo: str) -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "V"\n{corpo}', encoding="utf-8")
    return arquivo


def test_configuracao_sem_as_secoes_novas_continua_carregando(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, ""))

    assert configuracao.diario_inicio_do_dia == "04:00"
    assert configuracao.diario_hora_da_tarefa == "19:00"
    assert configuracao.privacidade_excluir == ()
    assert configuracao.git_raiz is None
    assert configuracao.git_profundidade == 3
    assert configuracao.linear_api_key == ""
    assert configuracao.slack_user_token == ""
    assert configuracao.slack_conversas_excluidas == ()


def test_chaves_do_diario_e_da_privacidade_chegam_achatadas(tmp_path: Path):
    arquivo = escrever(
        tmp_path,
        "\n".join(
            [
                "",
                "[diario]",
                'inicio_do_dia = "06:30"',
                'hora_da_tarefa = "20:15"',
                "",
                "[privacidade]",
                'excluir = ["terapia", "#pessoal"]',
                "",
            ]
        ),
    )

    configuracao = carregar(arquivo)

    assert configuracao.diario_inicio_do_dia == "06:30"
    assert configuracao.diario_hora_da_tarefa == "20:15"
    assert configuracao.privacidade_excluir == ("terapia", "#pessoal")


def test_chaves_das_tres_fontes_chegam_achatadas(tmp_path: Path):
    """Token de exemplo, nunca um real: nenhum segredo em teste ou fixture."""
    arquivo = escrever(
        tmp_path,
        "\n".join(
            [
                "",
                "[git]",
                'raiz = "C:/Users/exemplo/development"',
                "profundidade = 2",
                'excluir = ["node_modules"]',
                'autores = ["eu@exemplo.com"]',
                "",
                "[linear]",
                'api_key = "lin_api_EXEMPLO"',
                "",
                "[slack]",
                'user_token = "xoxp-EXEMPLO"',
                'conversas_excluidas = ["#pessoal"]',
                "",
            ]
        ),
    )

    configuracao = carregar(arquivo)

    assert configuracao.git_raiz == Path("C:/Users/exemplo/development")
    assert configuracao.git_profundidade == 2
    assert configuracao.git_excluir == ("node_modules",)
    assert configuracao.git_autores == ("eu@exemplo.com",)
    assert configuracao.linear_api_key == "lin_api_EXEMPLO"
    assert configuracao.slack_user_token == "xoxp-EXEMPLO"
    assert configuracao.slack_conversas_excluidas == ("#pessoal",)


def test_raiz_do_git_vazia_desliga_a_fonte(tmp_path: Path):
    configuracao = carregar(escrever(tmp_path, '\n[git]\nraiz = "   "\n'))

    assert configuracao.git_raiz is None


@pytest.mark.parametrize("hora", ['"25:00"', '"sete"', '"4h"', "4"])
def test_inicio_do_dia_invalido_e_configuracao_invalida(tmp_path: Path, hora: str):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, f"\n[diario]\ninicio_do_dia = {hora}\n"))

    assert "[diario].inicio_do_dia" in str(erro.value)
    assert "HH:MM" in str(erro.value)


def test_hora_da_tarefa_invalida_e_configuracao_invalida(tmp_path: Path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, '\n[diario]\nhora_da_tarefa = "meio-dia"\n'))

    assert "[diario].hora_da_tarefa" in str(erro.value)


def test_meia_noite_e_uma_hora_valida(tmp_path: Path):
    """`00:00` é a escolha legítima de quem quer o dia civil puro."""
    configuracao = carregar(escrever(tmp_path, '\n[diario]\ninicio_do_dia = "00:00"\n'))

    assert configuracao.diario_inicio_do_dia == "00:00"


@pytest.mark.parametrize("valor", ["0", "-1", '"tres"'])
def test_profundidade_invalida_do_git_e_configuracao_invalida(tmp_path: Path, valor: str):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar(escrever(tmp_path, f"\n[git]\nprofundidade = {valor}\n"))

    assert "profundidade" in str(erro.value)
