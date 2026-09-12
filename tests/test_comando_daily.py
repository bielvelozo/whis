"""O subcomando `whis daily` — a mesma costura, pela linha de comando.

O que o comando imprime é o que o usuário lê em voz alta um minuto depois, e
por isso é comportamento: os testes leem a saída do terminal, não o objeto de
resultado. `--fakes` é a forma explícita de exercitar tudo sem rede.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import hashlib

from fixtures.leitura import arquivos_do_vault, ler_frontmatter
from whis import vault as modulo_vault
from whis.__main__ import main
from whis.fakes import DAILY_PADRAO, ITEM_ABERTO_DE_EXEMPLO


def nota_de_hoje(vault: Path) -> Path:
    """A daily datada que o comando acabou de escrever — uma só, sempre a de hoje."""
    escritas = sorted(arquivo for arquivo in (vault / "daily").glob("*.md") if arquivo.name != "atual.md")
    assert len(escritas) == 1, f"esperava uma daily, achei {escritas}"
    return escritas[0]


def nota_viva(vault: Path) -> Path:
    return vault / "daily" / "atual.md"


def test_comando_daily_escreve_as_notas_e_imprime_a_nota_viva(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--fakes"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert ler_frontmatter(nota_de_hoje(caminho_do_vault))["tipo"] == "daily"
    assert ler_frontmatter(nota_viva(caminho_do_vault))["tipo"] == "daily-atual"
    assert "Cobre de" in saida and "até agora" in saida
    for secao in ("O que eu fiz:", "O que estou fazendo:", "Dúvidas:", "Falar:"):
        assert secao in saida
    assert f"- {DAILY_PADRAO.fiz[0].texto}" in saida
    assert f"Nota viva: {nota_viva(caminho_do_vault)}" in saida
    assert f"Nota: {nota_de_hoje(caminho_do_vault)}" in saida


def test_comando_daily_duas_vezes_faz_a_nota_viva_nascer_mover_e_nao_duplicar(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    """O `--fakes` de ponta a ponta: nasce, o item aberto sobe na segunda, nada repete."""
    configuracao_do_diario()
    main(["daily", "--fakes"])
    primeira = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    capsys.readouterr()

    codigo = main(["daily", "--fakes"])

    segunda = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    saida = capsys.readouterr().out
    assert codigo == 0
    assert primeira.index(ITEM_ABERTO_DE_EXEMPLO) > primeira.index("## O que estou fazendo")
    assert segunda.index(ITEM_ABERTO_DE_EXEMPLO) < segunda.index("## O que estou fazendo")
    for item in (*DAILY_PADRAO.fiz, *DAILY_PADRAO.fazendo):
        assert segunda.count(item.texto) == 1
    assert "Movido de _O que estou fazendo_ para _O que eu fiz_" in nota_de_hoje(
        caminho_do_vault
    ).read_text(encoding="utf-8")
    assert saida.count(ITEM_ABERTO_DE_EXEMPLO) == 1


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


# -- --anotar: o único gesto do agente numa seção do usuário -----------------


def test_anotar_faz_a_nota_viva_nascer_do_modelo_com_a_linha_em_falar(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "quero puxar a retenção de 180 dias"])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert codigo == 0
    assert texto.startswith("---\ntipo: daily-atual\n---\n")
    assert texto.endswith("## Falar\n- quero puxar a retenção de 180 dias\n")
    assert "Anotado em" in capsys.readouterr().out


def test_anotar_so_acrescenta_em_falar_e_nao_muda_nenhum_outro_byte(
    configuracao_do_diario, caminho_do_vault: Path
):
    """Tudo naquele arquivo foi digitado à mão: ele é append-only."""
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    original = (
        "---\ntipo: daily-atual\n---\n\n"
        "## O que eu fiz\n\n1. Planejei o pix \n\n"
        "## O que estou fazendo\n\n1. Correções do ribeiro\n\t1. FN-1786 \n\n"
        "## Dúvidas\n\n- uma dúvida minha\n\n"
        "## Falar\n\n- ponto antigo\n\n"
    )
    nota_viva(caminho_do_vault).write_bytes(original.encode("utf-8"))
    hash_do_original = hashlib.sha256(original.encode("utf-8")).hexdigest()

    main(["daily", "--anotar", "ponto novo"])

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert texto.count("- ponto novo\n") == 1
    assert hashlib.sha256(texto.replace("- ponto novo\n", "", 1).encode("utf-8")).hexdigest() == hash_do_original
    assert texto.endswith("## Falar\n\n- ponto antigo\n- ponto novo\n\n")


def test_anotar_nao_coleta_nem_escreve_daily(
    configuracao_do_diario, caminho_do_vault: Path
):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    antes = arquivos_do_vault(caminho_do_vault)

    main(["daily", "--anotar", "um ponto"])

    novos = arquivos_do_vault(caminho_do_vault) - antes
    assert novos == {"daily/atual.md"}


def test_o_ponto_anotado_continua_em_falar_depois_da_daily(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    """O ciclo inteiro da user story: anoto agora, leio na próxima daily."""
    configuracao_do_diario()
    main(["daily", "--anotar", "combinar a retenção de 180 dias"])
    capsys.readouterr()

    main(["daily", "--fakes"])

    saida = capsys.readouterr().out
    assert "Falar:\n  - combinar a retenção de 180 dias" in saida
    assert nota_viva(caminho_do_vault).read_text(encoding="utf-8").endswith(
        "## Falar\n- combinar a retenção de 180 dias\n"
    )
    assert "combinar a retenção" not in nota_de_hoje(caminho_do_vault).read_text(encoding="utf-8")


def test_anotar_vazio_e_recusado(
    configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "   "])

    assert codigo == 1
    assert "--anotar precisa de um texto" in caplog.text
    assert not nota_viva(caminho_do_vault).exists()
