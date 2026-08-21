"""Comportamento da costura: uma pasta de gravação vira nota + transcrição.

Nada aqui olha para dentro do pipeline: os testes leem o vault, como o
usuário leria no Obsidian.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao
from fixtures.leitura import corpo, ler_frontmatter
from second_brain.fakes import RESUMO_PADRAO, TRANSCRICAO_PADRAO, ResumoFake, STTFake
from second_brain.gravacao import STATUS_FALHOU, STATUS_TRANSCRITO, ler_estado
from second_brain.portas import ErroDeResumo, ErroDeSTT, Resumo

BASENAME = "2026-08-20-1430-daily-do-time"


def test_processar_cria_nota_e_transcricao_no_vault(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    processar_gravacao(pasta_de_gravacao)

    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()
    assert (caminho_do_vault / "transcricoes" / f"{BASENAME}.md").is_file()


def test_vault_e_estrutura_nascem_na_primeira_execucao(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    assert not caminho_do_vault.exists()

    processar_gravacao(pasta_de_gravacao)

    for pasta in ("reunioes", "transcricoes", "diario", "notas"):
        assert (caminho_do_vault / pasta).is_dir(), f"{pasta}/ não foi criada"


def test_frontmatter_da_nota_tem_os_campos_minimos(
    processar_gravacao, pasta_de_gravacao: Path
):
    resultado = processar_gravacao(pasta_de_gravacao)

    campos = ler_frontmatter(resultado.nota)
    assert campos["data"] == "2026-08-20"
    assert campos["tipo"] == "reuniao"
    assert campos["participantes"] == ["eu", "outros"]
    assert campos["transcricao"] == f"[[transcricoes/{BASENAME}]]"


def test_nota_linka_a_transcricao_por_wikilink(processar_gravacao, pasta_de_gravacao: Path):
    resultado = processar_gravacao(pasta_de_gravacao)

    assert f"[[transcricoes/{BASENAME}]]" in corpo(resultado.nota)


def test_transcricao_aponta_de_volta_para_a_nota(processar_gravacao, pasta_de_gravacao: Path):
    resultado = processar_gravacao(pasta_de_gravacao)

    campos = ler_frontmatter(resultado.transcricao)
    assert campos["tipo"] == "transcricao"
    assert campos["reuniao"] == f"[[reunioes/{BASENAME}]]"


def test_nota_traz_o_resumo_vindo_da_porta(processar_gravacao, pasta_de_gravacao: Path):
    resultado = processar_gravacao(pasta_de_gravacao)

    texto = corpo(resultado.nota)
    assert "# daily do time" in texto
    for decisao in RESUMO_PADRAO.decisoes:
        assert decisao in texto
    for acao in RESUMO_PADRAO.acoes:
        assert acao in texto
    for topico in RESUMO_PADRAO.topicos:
        assert topico in texto


def test_transcricao_distingue_eu_dos_outros(processar_gravacao, pasta_de_gravacao: Path):
    resultado = processar_gravacao(pasta_de_gravacao)

    texto = corpo(resultado.transcricao)
    assert "**eu:**" in texto
    assert "**outros:**" in texto
    for fala in TRANSCRICAO_PADRAO.falas:
        assert fala.texto in texto


def test_nome_dos_arquivos_vem_da_pasta_de_gravacao(
    processar_gravacao, caminho_das_gravacoes: Path, caminho_do_vault: Path
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2025-12-31-0905-retro-do-ano", titulo="retro do ano"
    )

    processar_gravacao(pasta)

    assert (caminho_do_vault / "reunioes" / "2025-12-31-0905-retro-do-ano.md").is_file()
    assert (caminho_do_vault / "transcricoes" / "2025-12-31-0905-retro-do-ano.md").is_file()


def test_gravacao_sem_titulo_usa_o_slug_da_pasta(
    processar_gravacao, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-01-05-0800-reuniao", titulo=None
    )

    resultado = processar_gravacao(pasta)

    assert "# reuniao" in corpo(resultado.nota)


def test_estado_da_gravacao_registra_o_processamento(
    processar_gravacao, pasta_de_gravacao: Path
):
    processar_gravacao(pasta_de_gravacao)

    estado = ler_estado(pasta_de_gravacao)
    assert estado.status == STATUS_TRANSCRITO
    assert estado.nota == f"reunioes/{BASENAME}.md"
    assert estado.transcricao == f"transcricoes/{BASENAME}.md"
    assert estado.erro is None
    assert estado.processado_em


def test_reprocessar_a_mesma_pasta_nao_duplica_notas(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    primeiro = processar_gravacao(pasta_de_gravacao)
    conteudo_original = primeiro.nota.read_text(encoding="utf-8")

    outro_resumo = ResumoFake(Resumo(decisoes=("resumo diferente",)))
    segundo = processar_gravacao(pasta_de_gravacao, resumo=outro_resumo)

    assert len(list((caminho_do_vault / "reunioes").glob("*.md"))) == 1
    assert len(list((caminho_do_vault / "transcricoes").glob("*.md"))) == 1
    assert segundo.reaproveitado is True
    assert segundo.nota.read_text(encoding="utf-8") == conteudo_original


def test_reprocesso_forcado_reescreve_os_mesmos_dois_arquivos(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    processar_gravacao(pasta_de_gravacao)

    outro_resumo = ResumoFake(Resumo(decisoes=("decisão revista",)))
    segundo = processar_gravacao(pasta_de_gravacao, resumo=outro_resumo, reprocessar=True)

    assert len(list((caminho_do_vault / "reunioes").glob("*.md"))) == 1
    assert "decisão revista" in corpo(segundo.nota)


def test_duas_reunioes_no_mesmo_dia_nao_colidem(
    processar_gravacao, caminho_das_gravacoes: Path, caminho_do_vault: Path
):
    manha = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-03-02-0900-reuniao")
    tarde = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-03-02-1600-reuniao")

    processar_gravacao(manha)
    processar_gravacao(tarde)

    assert len(list((caminho_do_vault / "reunioes").glob("*.md"))) == 2


def test_participantes_do_resumo_prevalecem_sobre_os_falantes(
    processar_gravacao, pasta_de_gravacao: Path
):
    resumo = ResumoFake(Resumo(participantes=("Gabriel", "Ana")))

    resultado = processar_gravacao(pasta_de_gravacao, resumo=resumo)

    assert ler_frontmatter(resultado.nota)["participantes"] == ["Gabriel", "Ana"]


def test_falha_no_resumo_nao_escreve_nota_parcial(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    resumo = ResumoFake(erro=ErroDeResumo("Claude fora do ar"))

    with pytest.raises(ErroDeResumo):
        processar_gravacao(pasta_de_gravacao, resumo=resumo)

    assert list((caminho_do_vault / "reunioes").glob("*.md")) == []
    assert list((caminho_do_vault / "transcricoes").glob("*.md")) == []


def test_falha_no_resumo_sinaliza_o_erro_no_estado(
    processar_gravacao, pasta_de_gravacao: Path
):
    resumo = ResumoFake(erro=ErroDeResumo("Claude fora do ar"))

    with pytest.raises(ErroDeResumo):
        processar_gravacao(pasta_de_gravacao, resumo=resumo)

    estado = ler_estado(pasta_de_gravacao)
    assert estado.status == STATUS_FALHOU
    assert "Claude fora do ar" in (estado.erro or "")
    assert estado.nota is None


def test_falha_no_resumo_preserva_a_gravacao(processar_gravacao, pasta_de_gravacao: Path):
    resumo = ResumoFake(erro=ErroDeResumo("Claude fora do ar"))

    with pytest.raises(ErroDeResumo):
        processar_gravacao(pasta_de_gravacao, resumo=resumo)

    assert (pasta_de_gravacao / "microfone.wav").is_file()
    assert (pasta_de_gravacao / "sistema.wav").is_file()
    assert (pasta_de_gravacao / "gravacao.json").is_file()


def test_gravacao_com_resumo_falho_vira_nota_no_reprocesso(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    with pytest.raises(ErroDeResumo):
        processar_gravacao(pasta_de_gravacao, resumo=ResumoFake(erro=ErroDeResumo("caiu")))

    resultado = processar_gravacao(pasta_de_gravacao)

    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()
    assert ler_estado(pasta_de_gravacao).status == STATUS_TRANSCRITO
    for decisao in RESUMO_PADRAO.decisoes:
        assert decisao in corpo(resultado.nota)


# -- Falha do STT: a gravação é preservada e nada parcial entra no vault -----

ERRO_DO_STT = "Deepgram respondeu HTTP 401 ao transcrever microfone.wav"


def test_falha_no_stt_nao_escreve_nota_parcial(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    stt = STTFake(erro=ErroDeSTT(ERRO_DO_STT))

    with pytest.raises(ErroDeSTT):
        processar_gravacao(pasta_de_gravacao, stt=stt)

    assert list((caminho_do_vault / "reunioes").glob("*.md")) == []
    assert list((caminho_do_vault / "transcricoes").glob("*.md")) == []


def test_falha_no_stt_sinaliza_o_erro_no_estado(processar_gravacao, pasta_de_gravacao: Path):
    stt = STTFake(erro=ErroDeSTT(ERRO_DO_STT))

    with pytest.raises(ErroDeSTT):
        processar_gravacao(pasta_de_gravacao, stt=stt)

    estado = ler_estado(pasta_de_gravacao)
    assert estado.status == STATUS_FALHOU
    assert ERRO_DO_STT in (estado.erro or ""), "o erro fica diagnosticável no estado.json"
    assert estado.nota is None
    assert estado.transcricao is None


def test_falha_no_stt_preserva_a_gravacao(processar_gravacao, pasta_de_gravacao: Path):
    stt = STTFake(erro=ErroDeSTT(ERRO_DO_STT))

    with pytest.raises(ErroDeSTT):
        processar_gravacao(pasta_de_gravacao, stt=stt)

    assert (pasta_de_gravacao / "microfone.wav").is_file()
    assert (pasta_de_gravacao / "sistema.wav").is_file()
    assert (pasta_de_gravacao / "gravacao.json").is_file()


def test_falha_no_stt_e_registrada_no_log(
    processar_gravacao, pasta_de_gravacao: Path, caplog
):
    stt = STTFake(erro=ErroDeSTT(ERRO_DO_STT))

    with caplog.at_level("ERROR", logger="second_brain.pipeline"):
        with pytest.raises(ErroDeSTT):
            processar_gravacao(pasta_de_gravacao, stt=stt)

    assert ERRO_DO_STT in caplog.text


def test_gravacao_com_stt_falho_vira_nota_no_reprocesso(
    processar_gravacao, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    with pytest.raises(ErroDeSTT):
        processar_gravacao(pasta_de_gravacao, stt=STTFake(erro=ErroDeSTT("caiu a rede")))

    resultado = processar_gravacao(pasta_de_gravacao)

    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()
    assert ler_estado(pasta_de_gravacao).status == STATUS_TRANSCRITO
    for fala in TRANSCRICAO_PADRAO.falas:
        assert fala.texto in corpo(resultado.transcricao)
