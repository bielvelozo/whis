"""O acabamento de `diario` e `daily`: o código de saída e o rastro em log.

Uma execução que ninguém viu precisa deixar duas coisas: um código que diga se
a nota nasceu — e inteira — e um arquivo de log com o motivo do que faltou.
Os testes passam pela costura da CLI (`main([...])`) e verificam o que sobra
depois que o terminal fechou: o código, o arquivo em `daily/` ou `diario/`, e
o `bandeja.log` ao lado da configuração.

As fábricas de `__main__` (`montar_fontes_da_daily`, `montar_roteiro_da_daily`
e as irmãs do diário) são o ponto em que a CLI injeta as portas; trocá-las por
uma fonte ou um roteiro que falham é injetar outra porta, não espiar por
dentro. O caso "todas as fontes falharam" nem precisa disso: uma `[git].raiz`
que não existe faz a fonte de verdade falhar sem rede.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.leitura import corpo, ler_frontmatter
from whis import __main__ as cli
from whis.__main__ import SAIDA_COMPLETA, SAIDA_NAO_NASCEU, SAIDA_PARCIAL, main
from whis.configuracao import VARIAVEL_DE_AMBIENTE
from whis.fakes import (
    EVENTOS_DE_GIT,
    DailyFake,
    FonteDaJanela,
    FonteFake,
    ResumoDoDiaFake,
    fontes_de_exemplo,
)
from whis.fontes import ErroDeFonte
from whis.portas import ErroDeDaily, ErroDeResumoDoDia

DIA = "2026-09-03"
MOTIVO_DO_SLACK = "token do Slack ausente em [slack].user_token"


def _log_de(configuracao) -> str:
    return (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")


def _unica_nota(vault: Path, pasta: str) -> Path:
    """A única nota datada da pasta — a nota viva `daily/atual.md` mora ao lado e não conta."""
    escritas = sorted(nota for nota in (vault / pasta).glob("*.md") if nota.name != "atual.md")
    assert len(escritas) == 1, f"esperava uma nota em {pasta}/, achei {escritas}"
    return escritas[0]


def _sem_nota(vault: Path, pasta: str) -> bool:
    return not (vault / pasta).exists() or list((vault / pasta).glob("*.md")) == []


def _fontes_com_o_slack_falhando(configuracao, *, fakes: bool = False):
    return [FonteDaJanela("git", EVENTOS_DE_GIT), FonteFake("slack", erro=ErroDeFonte(MOTIVO_DO_SLACK))]


def _fontes_do_diario_com_o_slack_falhando(configuracao, *, fakes: bool = False):
    return [*fontes_de_exemplo(), FonteFake("slack", erro=ErroDeFonte(MOTIVO_DO_SLACK))]


@pytest.fixture
def configuracao_so_com_git_inexistente(
    tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, monkeypatch
):
    """Uma configuração real cuja única fonte é um git apontado para o nada."""
    arquivo = tmp_path / "config-git.toml"
    arquivo.write_text(
        "\n".join(
            [
                f'vault = "{caminho_do_vault.as_posix()}"',
                f'gravacoes = "{caminho_das_gravacoes.as_posix()}"',
                "",
                "[git]",
                f'raiz = "{(tmp_path / "nao-existe").as_posix()}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
    return arquivo


# -- o --help documenta os códigos --------------------------------------------


@pytest.mark.parametrize("comando", ["daily", "diario"])
def test_o_help_documenta_os_codigos_de_saida(comando: str, capsys: pytest.CaptureFixture):
    with pytest.raises(SystemExit) as saida:
        main([comando, "--help"])

    ajuda = capsys.readouterr().out
    assert saida.value.code == 0
    assert "códigos de saída" in ajuda
    assert f"{SAIDA_COMPLETA}  a nota nasceu inteira" in ajuda
    assert f"{SAIDA_PARCIAL}  a nota nasceu parcial" in ajuda
    assert f"{SAIDA_NAO_NASCEU}  a nota não nasceu" in ajuda
    assert "bandeja.log" in ajuda


def test_os_tres_codigos_sao_distintos_e_nenhum_e_o_do_argparse():
    assert len({SAIDA_COMPLETA, SAIDA_PARCIAL, SAIDA_NAO_NASCEU}) == 3
    assert 2 not in {SAIDA_COMPLETA, SAIDA_PARCIAL, SAIDA_NAO_NASCEU}


# -- daily: nasceu inteira, parcial, ou não nasceu ---------------------------


def test_daily_inteira_sai_com_zero(configuracao_do_diario, caminho_do_vault: Path):
    configuracao_do_diario()

    assert main(["daily", "--fakes"]) == SAIDA_COMPLETA
    assert ler_frontmatter(_unica_nota(caminho_do_vault, "daily"))["fontes_com_falha"] == []


def test_daily_sem_uma_fonte_nasce_marcada_e_sai_parcial(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    configuracao_do_diario()
    monkeypatch.setattr(cli, "montar_fontes_da_daily", _fontes_com_o_slack_falhando)

    codigo = main(["daily", "--fakes"])

    nota = _unica_nota(caminho_do_vault, "daily")
    assert codigo == SAIDA_PARCIAL
    assert ler_frontmatter(nota)["fontes_com_falha"] == ["slack"]
    assert f"> [!warning] Slack não entrou nesta daily: {MOTIVO_DO_SLACK}" in corpo(nota)


def test_daily_sem_roteiro_nasce_com_as_listas_cruas_e_sai_parcial(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    configuracao_do_diario()
    monkeypatch.setattr(
        cli,
        "montar_roteiro_da_daily",
        lambda configuracao, *, fakes=False: DailyFake(
            erro=ErroDeDaily("o Claude não respondeu a tempo")
        ),
    )

    codigo = main(["daily", "--fakes"])

    nota = _unica_nota(caminho_do_vault, "daily")
    assert codigo == SAIDA_PARCIAL
    assert "A nota viva ficou como estava: o Claude não respondeu a tempo" in corpo(nota)
    assert "## Git" in corpo(nota) and "## Linear" in corpo(nota)


def test_daily_sem_nada_no_periodo_nao_nasce_e_sai_um(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    """Tudo que os fakes trazem envolve Gabriel ou Ana; excluir os dois esvazia o período."""
    configuracao_do_diario(excluir=("Gabriel", "Ana"))

    codigo = main(["daily", "--fakes"])

    assert codigo == SAIDA_NAO_NASCEU
    assert _sem_nota(caminho_do_vault, "daily")
    assert "nenhuma nota foi escrita" in capsys.readouterr().out


def test_daily_com_todas_as_fontes_falhando_nao_nasce_e_sai_um(
    configuracao_so_com_git_inexistente, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture
):
    """A fonte de git de verdade, sem `--fakes`: uma raiz inexistente a faz falhar."""
    codigo = main(["daily"])

    assert codigo == SAIDA_NAO_NASCEU
    assert _sem_nota(caminho_do_vault, "daily")
    assert "Nenhuma fonte respondeu" in caplog.text
    assert "Raiz de desenvolvimento não encontrada" in caplog.text


def test_daily_simulada_com_fonte_falhando_tambem_sai_parcial(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    """O que a simulação mostrou é incompleto, e o código tem que dizer isso."""
    configuracao_do_diario()
    monkeypatch.setattr(cli, "montar_fontes_da_daily", _fontes_com_o_slack_falhando)

    codigo = main(["daily", "--fakes", "--simular"])

    assert codigo == SAIDA_PARCIAL
    assert _sem_nota(caminho_do_vault, "daily")


# -- diario: os mesmos três casos --------------------------------------------


def test_diario_inteiro_sai_com_zero(configuracao_do_diario, caminho_do_vault: Path):
    configuracao_do_diario()

    assert main(["diario", DIA, "--fakes"]) == SAIDA_COMPLETA


def test_diario_sem_uma_fonte_nasce_marcado_e_sai_parcial(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    configuracao_do_diario()
    monkeypatch.setattr(cli, "montar_fontes", _fontes_do_diario_com_o_slack_falhando)

    codigo = main(["diario", DIA, "--fakes"])

    nota = caminho_do_vault / "diario" / f"{DIA}.md"
    assert codigo == SAIDA_PARCIAL
    assert ler_frontmatter(nota)["fontes_com_falha"] == ["slack"]
    assert f"> [!warning] Slack não entrou neste diário: {MOTIVO_DO_SLACK}" in corpo(nota)


def test_diario_sem_resumo_nasce_com_as_listas_cruas_e_sai_parcial(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    configuracao_do_diario()
    monkeypatch.setattr(
        cli,
        "montar_resumo_do_dia",
        lambda configuracao, *, fakes=False: ResumoDoDiaFake(
            erro=ErroDeResumoDoDia("o Claude não respondeu a tempo")
        ),
    )

    codigo = main(["diario", DIA, "--fakes"])

    nota = caminho_do_vault / "diario" / f"{DIA}.md"
    assert codigo == SAIDA_PARCIAL
    assert "o Claude não respondeu a tempo" in corpo(nota)
    assert "## Git" in corpo(nota)


def test_diario_de_dia_vazio_nao_nasce_e_sai_um(
    configuracao_do_diario, caminho_do_vault: Path
):
    configuracao_do_diario(excluir=("Gabriel", "Ana"))

    codigo = main(["diario", DIA, "--fakes"])

    assert codigo == SAIDA_NAO_NASCEU
    assert not (caminho_do_vault / "diario" / f"{DIA}.md").exists()


def test_diario_com_todas_as_fontes_falhando_nao_nasce_e_sai_um(
    configuracao_so_com_git_inexistente, caminho_do_vault: Path
):
    codigo = main(["diario", DIA])

    assert codigo == SAIDA_NAO_NASCEU
    assert _sem_nota(caminho_do_vault, "diario")


# -- o rastro em log -----------------------------------------------------------


def test_o_motivo_da_fonte_que_falhou_e_o_mesmo_no_log_e_na_nota(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    """Quem lê o log e quem lê a nota têm que reconhecer o mesmo problema."""
    configuracao = configuracao_do_diario()
    monkeypatch.setattr(cli, "montar_fontes_da_daily", _fontes_com_o_slack_falhando)

    main(["daily", "--fakes"])

    log = _log_de(configuracao)
    nota = corpo(_unica_nota(caminho_do_vault, "daily"))
    assert f"Fonte 'slack' não pôde ser lida: {MOTIVO_DO_SLACK}" in log
    assert MOTIVO_DO_SLACK in nota


def test_o_log_diz_como_a_daily_terminou(
    configuracao_do_diario, monkeypatch: pytest.MonkeyPatch
):
    configuracao = configuracao_do_diario()
    monkeypatch.setattr(cli, "montar_fontes_da_daily", _fontes_com_o_slack_falhando)

    main(["daily", "--fakes"])

    assert f"a nota nasceu parcial (saída {SAIDA_PARCIAL})" in _log_de(configuracao)


def test_o_log_diz_que_o_diario_nasceu_inteiro(configuracao_do_diario):
    configuracao = configuracao_do_diario()

    main(["diario", DIA, "--fakes"])

    assert f"Diário de {DIA}: a nota nasceu inteira (saída {SAIDA_COMPLETA})" in _log_de(
        configuracao
    )


def test_o_log_guarda_o_motivo_quando_nada_nasceu(configuracao_so_com_git_inexistente):
    """O caso que mais precisa de rastro: não há nota nenhuma para explicar."""
    main(["daily"])

    log = (configuracao_so_com_git_inexistente.parent / "bandeja.log").read_text(
        encoding="utf-8"
    )
    assert "Raiz de desenvolvimento não encontrada" in log
    assert "Nenhuma fonte respondeu" in log


def test_o_log_registra_o_periodo_vazio(configuracao_do_diario):
    configuracao = configuracao_do_diario(excluir=("Gabriel", "Ana"))

    main(["daily", "--fakes"])

    assert "a nota não nasceu, nada no período" in _log_de(configuracao)
