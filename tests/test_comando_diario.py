"""O subcomando `second-brain diario` — a mesma costura, pela linha de comando.

Como no `processar`, o padrão é o real: sem `--fakes` o comando vai ao git, ao
Linear, ao Slack e ao Claude. Os testes usam `--fakes`, que é a forma explícita
de exercitar o diário inteiro sem rede.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fixtures.leitura import ler_frontmatter
from second_brain.__main__ import main
from second_brain.fontes import data_do_diario

DIA = "2026-09-03"


def test_comando_diario_escreve_a_nota_do_dia(
    configuracao_do_diario, caminho_do_vault: Path
):
    configuracao_do_diario()

    codigo = main(["diario", DIA, "--fakes"])

    assert codigo == 0
    nota = caminho_do_vault / "diario" / f"{DIA}.md"
    assert nota.is_file()
    assert ler_frontmatter(nota)["tipo"] == "diario"


def test_comando_diario_sem_data_usa_o_dia_da_janela(
    configuracao_do_diario, caminho_do_vault: Path
):
    """Às 02:00 de quinta o diário a gerar ainda é o de quarta."""
    configuracao = configuracao_do_diario(inicio_do_dia="04:00")
    esperado = data_do_diario(datetime.now().astimezone(), configuracao.diario_inicio_do_dia)

    codigo = main(["diario", "--fakes"])

    assert codigo == 0
    assert (caminho_do_vault / "diario" / f"{esperado.isoformat()}.md").is_file()


def test_comando_diario_aceita_a_configuracao_por_argumento(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch: pytest.MonkeyPatch
):
    configuracao = configuracao_do_diario()
    monkeypatch.delenv("SECOND_BRAIN_CONFIG", raising=False)

    codigo = main(["diario", DIA, "--fakes", "--config", str(configuracao.origem)])

    assert codigo == 0
    assert (caminho_do_vault / "diario" / f"{DIA}.md").is_file()


def test_comando_diario_simular_mostra_sem_escrever(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["diario", DIA, "--fakes", "--simular"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert not (caminho_do_vault / "diario" / f"{DIA}.md").exists()
    assert "Simulação" in saida
    assert "[git]" in saida and "[linear]" in saida


def test_comando_diario_simular_conta_o_que_o_filtro_removeu(
    configuracao_do_diario, capsys: pytest.CaptureFixture
):
    """A ferramenta com que o usuário confere o filtro antes de confiar nele."""
    configuracao_do_diario(excluir=("frete",))

    codigo = main(["diario", DIA, "--fakes", "--simular"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "filtro de exclusão removeu 2 evento(s)" in saida
    assert "frete" not in saida.casefold()


def test_comando_diario_sem_fonte_configurada_falha_com_mensagem(
    configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture
):
    """Lista vazia e "todas falharam" são problemas diferentes, com mensagens diferentes."""
    configuracao_do_diario()

    codigo = main(["diario", DIA])

    assert codigo == 1
    assert "Nenhuma fonte passiva está ligada" in caplog.text
    assert "[linear].api_key" in caplog.text
    assert not (caminho_do_vault / "diario" / f"{DIA}.md").exists()


def test_comando_diario_recusa_data_fora_do_formato(configuracao_do_diario):
    configuracao_do_diario()

    with pytest.raises(SystemExit) as saida:
        main(["diario", "03/09/2026", "--fakes"])

    assert saida.value.code == 2


def test_comando_diario_deixa_rastro_no_arquivo_de_log(configuracao_do_diario):
    """Quem costuma chamar este comando é a tarefa agendada, que não tem console."""
    configuracao = configuracao_do_diario()

    main(["diario", DIA, "--fakes"])

    log = configuracao.origem.parent / "bandeja.log"
    assert log.is_file()
    assert DIA in log.read_text(encoding="utf-8")
