"""Os subcomandos da CLI — a mesma costura, pela linha de comando.

`processar` roda com os adaptadores reais por padrão; nos testes ele é chamado
com `--fakes`, que é a forma explícita de exercitar o pipeline inteiro sem
gastar crédito nem tocar a rede. Um teste garante que o padrão *é* mesmo o
real: sem `--fakes` e sem chave da Deepgram, o comando recusa antes de fazer
qualquer coisa.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao, datar_processamento
from second_brain.__main__ import main
from second_brain.configuracao import VARIAVEL_DE_AMBIENTE, carregar
from second_brain.gravacao import STATUS_FALHOU, STATUS_TRANSCRITO, ler_estado

BASENAME = "2026-08-20-1430-daily-do-time"


# -- processar --------------------------------------------------------------


def test_comando_processar_escreve_a_nota_no_vault(
    arquivo_de_configuracao: Path, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    codigo = main(["processar", str(pasta_de_gravacao), "--fakes"])

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()
    assert (caminho_do_vault / "transcricoes" / f"{BASENAME}.md").is_file()


def test_comando_aceita_a_configuracao_por_argumento(
    arquivo_de_configuracao: Path,
    pasta_de_gravacao: Path,
    caminho_do_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(VARIAVEL_DE_AMBIENTE, raising=False)

    codigo = main(
        ["processar", str(pasta_de_gravacao), "--fakes", "--config", str(arquivo_de_configuracao)]
    )

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()


def test_comando_processar_usa_os_adaptadores_reais_por_padrao(
    arquivo_de_configuracao: Path,
    pasta_de_gravacao: Path,
    caminho_do_vault: Path,
    caplog: pytest.LogCaptureFixture,
):
    """Sem `--fakes` o comando vai para a Deepgram — e para antes, sem a chave.

    A configuração dos testes tem `api_key = ""`, então o adaptador real recusa
    a chamada. É a prova de que o padrão não é mais o fake: se fosse, a nota
    apareceria no vault.
    """
    codigo = main(["processar", str(pasta_de_gravacao)])

    assert codigo == 1
    assert "Deepgram" in caplog.text
    assert list((caminho_do_vault / "reunioes").glob("*.md")) == []


def test_comando_falha_com_mensagem_quando_a_pasta_nao_existe(
    arquivo_de_configuracao: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    codigo = main(["processar", str(tmp_path / "2026-08-20-1430-inexistente"), "--fakes"])

    assert codigo == 1
    assert "não encontrada" in caplog.text


def test_comando_falha_quando_nao_ha_configuracao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(tmp_path / "sem-config.toml"))

    codigo = main(["processar", str(tmp_path), "--fakes"])

    assert codigo == 1
    assert "Configuração não encontrada" in caplog.text


# -- reprocessar ------------------------------------------------------------


def test_comando_reprocessar_completa_gravacao_que_falhou(
    arquivo_de_configuracao: Path, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    datar_processamento(
        pasta_de_gravacao, status=STATUS_FALHOU, dias_atras=1, erro="Claude fora do ar"
    )

    codigo = main(["reprocessar", "--fakes"])

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()
    assert ler_estado(pasta_de_gravacao).status == STATUS_TRANSCRITO


def test_comando_reprocessar_e_idempotente(
    arquivo_de_configuracao: Path, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    datar_processamento(pasta_de_gravacao, status=STATUS_FALHOU, dias_atras=1, erro="caiu")

    assert main(["reprocessar", "--fakes"]) == 0
    assert main(["reprocessar", "--fakes"]) == 0
    assert main(["reprocessar", str(pasta_de_gravacao), "--fakes"]) == 0

    assert len(list((caminho_do_vault / "reunioes").glob("*.md"))) == 1
    assert len(list((caminho_do_vault / "transcricoes").glob("*.md"))) == 1


def test_comando_reprocessar_aceita_uma_pasta_especifica(
    arquivo_de_configuracao: Path, pasta_de_gravacao: Path, caminho_do_vault: Path
):
    codigo = main(["reprocessar", str(pasta_de_gravacao), "--fakes"])

    assert codigo == 0
    assert (caminho_do_vault / "reunioes" / f"{BASENAME}.md").is_file()


def test_comando_reprocessar_sem_gravacao_retida_nao_faz_nada(
    arquivo_de_configuracao: Path,
    pasta_de_gravacao: Path,
    caminho_do_vault: Path,
    capsys: pytest.CaptureFixture,
):
    main(["processar", str(pasta_de_gravacao), "--fakes"])
    capsys.readouterr()

    codigo = main(["reprocessar", "--fakes"])

    assert codigo == 0
    assert "Nenhuma gravação retida" in capsys.readouterr().out


def test_comando_reprocessar_segue_para_a_proxima_quando_uma_falha(
    arquivo_de_configuracao: Path,
    caminho_das_gravacoes: Path,
    caminho_do_vault: Path,
):
    quebrada = caminho_das_gravacoes / "2026-08-19-0900-sem-audio"
    quebrada.mkdir()
    datar_processamento(quebrada, status=STATUS_FALHOU, dias_atras=1, erro="caiu")
    boa = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-20-1430-boa")
    datar_processamento(boa, status=STATUS_FALHOU, dias_atras=1, erro="caiu")

    codigo = main(["reprocessar", "--fakes"])

    assert codigo == 1, "a gravação quebrada faz o comando terminar em erro"
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-boa.md").is_file()


# -- limpar -----------------------------------------------------------------


def test_comando_limpar_apaga_a_gravacao_vencida(
    arquivo_de_configuracao: Path, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-01-0900-antiga")
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=19)

    codigo = main(["limpar"])

    assert codigo == 0
    assert not pasta.exists()


def test_comando_limpar_simular_mostra_sem_apagar(
    arquivo_de_configuracao: Path,
    caminho_das_gravacoes: Path,
    capsys: pytest.CaptureFixture,
):
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-01-0900-antiga")
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=19)

    codigo = main(["limpar", "--simular"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert pasta.is_dir()
    assert "Simulação — nada foi apagado" in saida
    assert "2026-08-01-0900-antiga" in saida


def test_comando_limpar_lista_o_que_preservou_e_por_que(
    arquivo_de_configuracao: Path,
    caminho_das_gravacoes: Path,
    capsys: pytest.CaptureFixture,
):
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-01-01-0900-falhou")
    datar_processamento(pasta, status=STATUS_FALHOU, dias_atras=200, erro="caiu")

    codigo = main(["limpar"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert pasta.is_dir()
    assert "Preservadas 1" in saida
    assert "reprocesso" in saida


def test_comando_limpar_aceita_prazo_na_linha_de_comando(
    arquivo_de_configuracao: Path, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-18-0900-recente")
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=3)

    assert main(["limpar", "--dias", "30"]) == 0
    assert pasta.is_dir()

    assert main(["limpar", "--dias", "1"]) == 0
    assert not pasta.exists()


def test_comando_limpar_nao_precisa_de_chave_de_servico(
    arquivo_de_configuracao: Path, caminho_das_gravacoes: Path
):
    """A limpeza é local: nenhum adaptador é montado, nenhuma chave é exigida."""
    assert main(["limpar", "--simular"]) == 0


def test_comando_limpar_relata_a_gravacao_que_nao_conseguiu_apagar(
    arquivo_de_configuracao: Path,
    caminho_das_gravacoes: Path,
    capsys: pytest.CaptureFixture,
):
    """Uma vencida que o sistema de arquivos recusa apagar não vira silêncio.

    O modo de falha é real no Windows: basta um arquivo da pasta estar aberto
    (o Obsidian, um player, o próprio gravador) para o `rmtree` parar no meio.
    Aqui o handle aberto é o do teste — nenhum mock. O comando precisa dizer
    qual gravação ficou para trás e sair com código de erro, jamais imprimir
    "nenhuma venceu o prazo" enquanto uma venceu e continua no disco.
    """
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-01-0900-presa")
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=19)

    with (pasta / "microfone.wav").open("rb"):  # segura a pasta aberta
        codigo = main(["limpar"])

    saida = capsys.readouterr().out
    assert codigo == 1
    assert pasta.is_dir()
    assert "Não foi possível apagar 1" in saida
    assert "2026-08-01-0900-presa" in saida
    assert "Nenhuma gravação venceu o prazo" not in saida


def test_comando_limpar_recusa_prazo_negativo(
    arquivo_de_configuracao: Path, caminho_das_gravacoes: Path
):
    """`--dias -1` apagaria tudo que já virou nota; o parser recusa antes."""
    pasta = criar_pasta_de_gravacao(caminho_das_gravacoes, nome="2026-08-30-0900-hoje")
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=0)

    with pytest.raises(SystemExit) as saida:
        main(["limpar", "--dias=-1"])

    assert saida.value.code == 2
    assert pasta.is_dir()


# -- init -------------------------------------------------------------------


def test_comando_init_cria_a_configuracao_com_os_caminhos(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    destino = tmp_path / "config.toml"

    codigo = main(["init", "--config", str(destino)])

    assert codigo == 0
    conteudo = destino.read_text(encoding="utf-8")
    assert "vault" in conteudo and "gravacoes" in conteudo
    assert "\\" not in conteudo  # caminhos com barra normal, como o TOML exige
    assert "Próximos passos" in capsys.readouterr().out


def test_configuracao_criada_pelo_init_e_lida_sem_erro(tmp_path: Path):
    """O que o init escreve tem que passar pelo carregador — senão não serve."""
    destino = tmp_path / "config.toml"
    main(["init", "--config", str(destino)])

    configuracao = carregar(destino)

    assert configuracao.retencao_dias == 7
    assert configuracao.deepgram_api_key == ""


def test_comando_init_nao_sobrescreve_configuracao_existente(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    destino = tmp_path / "config.toml"
    destino.write_text('vault = "V"\ngravacoes = "G"\n', encoding="utf-8")

    codigo = main(["init", "--config", str(destino)])

    assert codigo == 1
    assert destino.read_text(encoding="utf-8").startswith('vault = "V"')
    assert "--forcar" in capsys.readouterr().out or "forcar" in capsys.readouterr().out


def test_comando_init_forcar_sobrescreve(tmp_path: Path):
    destino = tmp_path / "config.toml"
    destino.write_text('vault = "V"\ngravacoes = "G"\n', encoding="utf-8")

    assert main(["init", "--config", str(destino), "--forcar"]) == 0
    assert "retencao_dias" in destino.read_text(encoding="utf-8")
