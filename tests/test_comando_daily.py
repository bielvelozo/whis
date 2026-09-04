"""O subcomando `second-brain daily` — a mesma costura, pela linha de comando.

O que o comando imprime é o que o usuário lê em voz alta um minuto depois, e
por isso é comportamento: os testes leem a saída do terminal, não o objeto de
resultado. `--fakes` é a forma explícita de exercitar tudo sem rede.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, ler_frontmatter
from second_brain import vault as modulo_vault
from second_brain.__main__ import main
from second_brain.fakes import DAILY_PADRAO


def nota_de_hoje(vault: Path) -> Path:
    """A daily que o comando acabou de escrever — uma só, sempre a de hoje."""
    escritas = sorted((vault / "daily").glob("*.md"))
    assert len(escritas) == 1, f"esperava uma daily, achei {escritas}"
    return escritas[0]


def test_comando_daily_escreve_a_nota_e_imprime_o_roteiro(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--fakes"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert ler_frontmatter(nota_de_hoje(caminho_do_vault))["tipo"] == "daily"
    assert "Cobre de" in saida and "até agora" in saida
    for batida in ("Entreguei:", "Sigo em:", "Preciso de:", "Dúvidas:"):
        assert batida in saida
    assert DAILY_PADRAO.preciso_de[0] in saida


def test_comando_daily_imprime_os_pontos_do_usuario(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    (caminho_do_vault / "notas" / "daily.md").write_text(
        "# Daily\n\n## Pontos\n- [ ] puxar a retenção de 180 dias\n", encoding="utf-8"
    )

    main(["daily", "--fakes"])

    saida = capsys.readouterr().out
    assert "Meus pontos:" in saida
    assert "puxar a retenção de 180 dias" in saida


def test_comando_daily_simular_mostra_sem_escrever(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--fakes", "--simular"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert list((caminho_do_vault / "daily").glob("*.md")) == []
    assert "Simulação" in saida
    assert "[git]" in saida and "[linear]" in saida


def test_comando_daily_simular_conta_o_que_o_filtro_removeu(
    configuracao_do_diario, capsys: pytest.CaptureFixture
):
    configuracao_do_diario(excluir=("frete",))

    codigo = main(["daily", "--fakes", "--simular"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "filtro de exclusão removeu 2 evento(s)" in saida
    assert "frete" not in saida.casefold()


def test_comando_daily_sem_fonte_configurada_falha_com_mensagem(
    configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily"])

    assert codigo == 1
    assert "Nenhuma fonte passiva está ligada" in caplog.text
    assert not (caminho_do_vault / "daily").exists() or list(
        (caminho_do_vault / "daily").glob("*.md")
    ) == []


def test_comando_daily_deixa_rastro_no_arquivo_de_log(configuracao_do_diario):
    configuracao = configuracao_do_diario()

    main(["daily", "--fakes"])

    log = configuracao.origem.parent / "bandeja.log"
    assert log.is_file()
    assert "Daily" in log.read_text(encoding="utf-8")


# -- --anotar: a única escrita na zona do usuário ---------------------------


def test_anotar_cria_o_arquivo_de_pontos_com_o_cabecalho(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "quero puxar a retenção de 180 dias"])

    arquivo = caminho_do_vault / "notas" / "daily.md"
    texto = arquivo.read_text(encoding="utf-8")
    assert codigo == 0
    assert "# Daily — meus pontos" in texto
    assert "## Pontos" in texto
    assert "- [ ] quero puxar a retenção de 180 dias" in texto
    assert "Anotado em" in capsys.readouterr().out


def test_anotar_acrescenta_sem_reescrever_o_que_ja_estava_la(
    configuracao_do_diario, caminho_do_vault: Path
):
    """Tudo naquele arquivo foi digitado à mão: ele é append-only."""
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    arquivo = caminho_do_vault / "notas" / "daily.md"
    original = (
        "# Daily — meus pontos\n\n"
        "## Dúvidas\n- [ ] uma dúvida minha\n\n"
        "## Pontos\n- [ ] ponto antigo\n- [x] ponto ja falado\n"
    )
    arquivo.write_text(original, encoding="utf-8")

    main(["daily", "--anotar", "ponto novo"])

    texto = arquivo.read_text(encoding="utf-8")
    for linha in original.splitlines():
        assert linha in texto, f"linha do usuário sumiu: {linha!r}"
    assert texto.index("- [ ] ponto antigo") < texto.index("- [ ] ponto novo")
    assert texto.index("- [ ] ponto novo") > texto.index("- [x] ponto ja falado")


def test_anotar_nao_coleta_nem_escreve_daily(
    configuracao_do_diario, caminho_do_vault: Path
):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    antes = arquivos_do_vault(caminho_do_vault)

    main(["daily", "--anotar", "um ponto"])

    novos = arquivos_do_vault(caminho_do_vault) - antes
    assert novos == {"notas/daily.md"}


def test_o_ponto_anotado_aparece_na_daily_seguinte(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    """O ciclo inteiro da user story: anoto agora, falo na próxima daily."""
    configuracao_do_diario()
    main(["daily", "--anotar", "combinar a retenção de 180 dias"])
    capsys.readouterr()

    main(["daily", "--fakes"])

    saida = capsys.readouterr().out
    assert "combinar a retenção de 180 dias" in saida
    assert "combinar a retenção de 180 dias" in nota_de_hoje(caminho_do_vault).read_text(
        encoding="utf-8"
    )


def test_anotar_vazio_e_recusado(
    configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "   "])

    assert codigo == 1
    assert "--anotar precisa de um texto" in caplog.text
    assert not (caminho_do_vault / "notas" / "daily.md").exists()
