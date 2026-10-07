"""O subcomando `whis daily`: a nota dele vira slides no link de sempre.

O que o comando imprime e o toast são comportamento: os testes leem a saída
do terminal e o aviso. A publicação é o fake autouse do `conftest`.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from fixtures.daily import NOTA_DA_DAILY, escrever_nota_da_daily
from fixtures.leitura import arquivos_do_vault, ler_frontmatter
from whis import __main__ as cli
from whis import vault as modulo_vault
from whis.__main__ import SAIDA_COMPLETA, SAIDA_PARCIAL, main
from whis.fakes import URL_DO_DECK_FAKE, PublicacaoDoDeckFake
from whis.portas import ErroDePublicacao


def nota_viva(vault: Path) -> Path:
    return vault / "daily" / "atual.md"


def copia_de_hoje(vault: Path) -> Path:
    return vault / "daily" / f"{date.today().isoformat()}.md"


def test_daily_publica_imprime_os_slides_e_o_link_e_sai_com_zero(
    configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)

    codigo = main(["daily"])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 1
    assert "O que eu fiz:\n  FN-123 frete do checkout corrigido\n    subiu em produção\n" in saida
    assert f"Slides: {URL_DO_DECK_FAKE}" in saida
    assert toasts[-1] == ("A daily está pronta", "4 slides no link de sempre.", ("Abrir slides", URL_DO_DECK_FAKE))
    assert ler_frontmatter(copia_de_hoje(caminho_do_vault))["deck"] == URL_DO_DECK_FAKE


@pytest.mark.parametrize("bandeira", ["--fakes", "--simular"])
def test_fakes_e_simular_mostram_os_slides_sem_publicar_escrever_ou_avisar(
    bandeira: str, configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts, capsys
):
    configuracao_do_diario()
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    codigo = main(["daily", bandeira])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 0
    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    assert arquivos_do_vault(caminho_do_vault) == {"daily/atual.md"}
    assert toasts == []
    assert "Simulação" in saida and "Dúvidas:" in saida


def test_nota_vazia_sai_com_zero_e_o_toast_pede_para_escrever(
    configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts
):
    configuracao_do_diario()

    codigo = main(["daily"])

    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 0
    titulo, _texto, botao = toasts[-1]
    assert titulo == "A nota da daily está vazia"
    assert botao[0] == "Abrir no Obsidian"
    assert nota_viva(caminho_do_vault).is_file()
    assert not copia_de_hoje(caminho_do_vault).exists()


def test_publicacao_que_falha_sai_parcial_grava_a_copia_e_o_toast_abre_a_nota(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch, toasts
):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)
    monkeypatch.setattr(
        cli,
        "montar_publicacao_do_deck",
        lambda _c: PublicacaoDoDeckFake(erro=ErroDePublicacao("o Claude caiu")),
    )

    codigo = main(["daily"])

    assert codigo == SAIDA_PARCIAL
    titulo, texto, botao = toasts[-1]
    assert titulo == "A daily não publicou" and "o Claude caiu" in texto
    assert botao[0] == "Abrir no Obsidian"
    assert copia_de_hoje(caminho_do_vault).is_file()


def test_comando_daily_deixa_rastro_no_arquivo_de_log(configuracao_do_diario, caminho_do_vault: Path):
    configuracao = configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)

    main(["daily"])

    log = configuracao.origem.parent / "bandeja.log"
    assert "Daily de" in log.read_text(encoding="utf-8")


# -- --anotar: o único gesto do agente numa seção do usuário -----------------


def test_anotar_faz_a_nota_viva_nascer_do_modelo_com_a_linha_em_pontos(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "quero puxar a retenção de 180 dias"])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert codigo == 0
    assert texto.startswith("---\ntipo: daily-atual\n---\n")
    assert texto.endswith("## Pontos\n- quero puxar a retenção de 180 dias\n")
    assert "Anotado em" in capsys.readouterr().out


def test_anotar_so_acrescenta_em_pontos_e_nao_muda_nenhum_outro_byte(configuracao_do_diario, caminho_do_vault: Path):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    original = (
        "---\ntipo: daily-atual\n---\n\n"
        "## O que eu fiz\n\n1. Planejei o pix \n\n"
        "## O que estou fazendo\n\n1. Correções do ribeiro\n\t1. FN-1786 \n\n"
        "## Dúvidas\n\n- uma dúvida minha\n\n"
        "## Pontos\n\n- ponto antigo\n\n"
        "## Falar\n\n- avisar da folga\n\n"
    )
    nota_viva(caminho_do_vault).write_bytes(original.encode("utf-8"))
    hash_do_original = hashlib.sha256(original.encode("utf-8")).hexdigest()

    main(["daily", "--anotar", "ponto novo"])

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert texto.count("- ponto novo\n") == 1
    assert hashlib.sha256(texto.replace("- ponto novo\n", "", 1).encode("utf-8")).hexdigest() == hash_do_original
    assert "## Pontos\n\n- ponto antigo\n- ponto novo\n\n## Falar\n\n- avisar da folga\n\n" in texto


def test_anotar_nao_publica_nem_escreve_copia(configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    antes = arquivos_do_vault(caminho_do_vault)

    main(["daily", "--anotar", "um ponto"])

    assert arquivos_do_vault(caminho_do_vault) - antes == {"daily/atual.md"}
    assert publicacao_do_deck.chamadas == 0


def test_o_anotado_entra_em_pontos_e_vai_para_o_deck(configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)
    main(["daily", "--anotar", "combinar a retenção de 180 dias"])

    main(["daily"])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert "- sexta eu saio mais cedo\n- combinar a retenção de 180 dias\n" in texto
    assert "- também não vai\n\n" in texto
    assert publicacao_do_deck.chamadas == 1
    assert "combinar a retenção de 180 dias" in publicacao_do_deck.conteudos["project/slides/pontos.html"]
    assert all("também não vai" not in conteudo for conteudo in publicacao_do_deck.conteudos.values())


def test_anotar_vazio_e_recusado(configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "   "])

    assert codigo == 1
    assert "--anotar precisa de um texto" in caplog.text
    assert not nota_viva(caminho_do_vault).exists()
