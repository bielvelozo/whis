"""Comportamento da retenção: o áudio bruto some, o vault e as falhas ficam.

Os testes montam gravações **datadas no passado** a partir de `tmp_path` — o
`estado.json` é escrito com um `processado_em` calculado a partir de agora, e o
mtime do arquivo é alinhado à mesma data. Nenhum teste dorme nem depende da
hora que o relógio marca.

Como no resto do repositório, a verificação é de comportamento externo: o que
sobrou no disco depois da limpeza, e o que o log disse ter apagado e por quê.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao, criar_wav, datar_processamento
from second_brain import retencao
from second_brain.configuracao import Configuracao
from second_brain.gravacao import STATUS_FALHOU, STATUS_PENDENTE, STATUS_TRANSCRITO


def gravacao_datada(
    gravacoes: Path, nome: str, *, status: str, dias_atras: float, **campos
) -> Path:
    """Uma pasta de gravação completa, com estado datado no passado."""
    pasta = criar_pasta_de_gravacao(gravacoes, nome=nome)
    datar_processamento(pasta, status=status, dias_atras=dias_atras, **campos)
    return pasta


# -- O que a limpeza apaga --------------------------------------------------


def test_limpeza_apaga_gravacao_transcrita_alem_do_prazo(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-daily-antiga",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )

    retencao.limpar_da_configuracao(configuracao)

    assert not pasta.exists(), "gravação transcrita e vencida deveria ter sido apagada"


def test_limpeza_apaga_a_pasta_inteira_inclusive_o_audio_e_a_transcricao_guardada(
    configuracao: Configuracao, caminho_das_gravacoes: Path, processar_gravacao
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-08-01-0900-daily-antiga"
    )
    processar_gravacao(pasta)
    assert (pasta / "transcricao.json").is_file()
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=19)

    retencao.limpar_da_configuracao(configuracao)

    assert not pasta.exists()
    assert not (pasta / "microfone.wav").exists()
    assert not (pasta / "transcricao.json").exists()


def test_limpeza_preserva_gravacao_transcrita_dentro_do_prazo(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-18-0900-daily-recente",
        status=STATUS_TRANSCRITO,
        dias_atras=3,
    )

    retencao.limpar_da_configuracao(configuracao)

    assert pasta.is_dir()
    assert (pasta / "microfone.wav").is_file()


def test_limpeza_preserva_gravacao_no_ultimo_dia_do_prazo(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-14-0900-daily-no-limite",
        status=STATUS_TRANSCRITO,
        dias_atras=6.9,
    )

    retencao.limpar_da_configuracao(configuracao)

    assert pasta.is_dir(), "o prazo é de 7 dias completos"


# -- O que a limpeza nunca apaga --------------------------------------------


def test_limpeza_nunca_apaga_gravacao_que_falhou(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-05-01-1000-reuniao-perdida",
        status=STATUS_FALHOU,
        dias_atras=120,
        erro="Deepgram respondeu HTTP 401",
    )

    retencao.limpar_da_configuracao(configuracao)

    assert pasta.is_dir(), "gravação com falha fica retida indefinidamente"
    assert (pasta / "microfone.wav").is_file()


def test_limpeza_nunca_apaga_gravacao_ainda_nao_processada(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-05-01-1000-nunca-processada"
    )
    assert not (pasta / "estado.json").exists()

    retencao.limpar_da_configuracao(configuracao)

    assert pasta.is_dir()


def test_limpeza_nunca_apaga_gravacao_pendente_antiga(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-01-02-0800-pendente",
        status=STATUS_PENDENTE,
        dias_atras=200,
    )

    retencao.limpar_da_configuracao(configuracao)

    assert pasta.is_dir()


def test_limpeza_nunca_apaga_pasta_fora_do_contrato(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    intrusa = caminho_das_gravacoes / "backup-do-usuario"
    criar_wav(intrusa / "microfone.wav")

    retencao.limpar_da_configuracao(configuracao)

    assert intrusa.is_dir(), "só pasta no formato do gravador é candidata"


def test_limpeza_nao_toca_o_vault(
    configuracao: Configuracao, caminho_das_gravacoes: Path, processar_gravacao
):
    pasta = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-08-01-0900-daily-antiga"
    )
    resultado = processar_gravacao(pasta)
    datar_processamento(pasta, status=STATUS_TRANSCRITO, dias_atras=19)

    retencao.limpar_da_configuracao(configuracao)

    assert not pasta.exists()
    assert resultado.nota.is_file(), "a nota de reunião continua no vault"
    assert resultado.transcricao.is_file(), "a transcrição continua no vault"


def test_limpeza_sem_data_de_processamento_cai_para_a_data_do_arquivo(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    vencida = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-sem-carimbo",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
        processado_em=None,
    )
    recente = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-19-0900-sem-carimbo",
        status=STATUS_TRANSCRITO,
        dias_atras=1,
        processado_em=None,
    )

    retencao.limpar_da_configuracao(configuracao)

    assert not vencida.exists()
    assert recente.is_dir()


# -- Período configurável ---------------------------------------------------


def test_prazo_de_retencao_vem_da_configuracao(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-daily-antiga",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )

    outra = Configuracao(
        vault=configuracao.vault,
        gravacoes=configuracao.gravacoes,
        retencao_dias=30,
    )
    retencao.limpar_da_configuracao(outra)

    assert pasta.is_dir(), "com retencao_dias=30 a gravação de 19 dias fica"


def test_prazo_pode_ser_sobreposto_na_chamada(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-18-0900-daily-recente",
        status=STATUS_TRANSCRITO,
        dias_atras=3,
    )

    retencao.limpar_da_configuracao(configuracao, retencao_dias=1)

    assert not pasta.exists()


# -- Simulação: ver o que seria apagado sem apagar --------------------------


def test_simulacao_nao_apaga_nada(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    pasta = gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-daily-antiga",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )

    limpeza = retencao.limpar_da_configuracao(configuracao, simular=True)

    assert pasta.is_dir(), "simular jamais apaga"
    assert [a.nome for a in limpeza.apagadas] == ["2026-08-01-0900-daily-antiga"]
    assert limpeza.simulado is True


def test_simulacao_diz_no_log_o_que_apagaria_e_por_que(
    configuracao: Configuracao, caminho_das_gravacoes: Path, caplog
):
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-daily-antiga",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )

    with caplog.at_level("INFO", logger="second_brain.retencao"):
        retencao.limpar_da_configuracao(configuracao, simular=True)

    assert "[simulação]" in caplog.text
    assert "2026-08-01-0900-daily-antiga" in caplog.text
    assert "19 dias" in caplog.text
    assert "7 dias de retenção" in caplog.text


def test_limpeza_registra_no_log_o_que_apagou_e_por_que(
    configuracao: Configuracao, caminho_das_gravacoes: Path, caplog
):
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-daily-antiga",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )

    with caplog.at_level("INFO", logger="second_brain.retencao"):
        retencao.limpar_da_configuracao(configuracao)

    assert "Apagada 2026-08-01-0900-daily-antiga" in caplog.text
    assert "19 dias" in caplog.text
    assert "já estão no vault" in caplog.text


# -- O relatório da avaliação -----------------------------------------------


def test_avaliacao_explica_cada_gravacao(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-01-0900-vencida",
        status=STATUS_TRANSCRITO,
        dias_atras=19,
    )
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-18-0900-recente",
        status=STATUS_TRANSCRITO,
        dias_atras=3,
    )
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-05-01-1000-falhou",
        status=STATUS_FALHOU,
        dias_atras=120,
    )

    avaliacoes = {
        a.nome: a
        for a in retencao.avaliar(caminho_das_gravacoes, retencao_dias=7)
    }

    assert avaliacoes["2026-08-01-0900-vencida"].vencida is True
    assert avaliacoes["2026-08-18-0900-recente"].vencida is False
    assert "dentro dos 7 dias" in avaliacoes["2026-08-18-0900-recente"].motivo
    assert avaliacoes["2026-05-01-1000-falhou"].vencida is False
    assert "reprocesso" in avaliacoes["2026-05-01-1000-falhou"].motivo


def test_limpeza_de_pasta_de_gravacoes_inexistente_nao_quebra(tmp_path: Path):
    limpeza = retencao.limpar(tmp_path / "nao-existe", retencao_dias=7)

    assert limpeza.apagadas == ()
    assert limpeza.preservadas == ()


# -- Quais gravações o reprocesso enxerga -----------------------------------


def test_retidas_lista_as_que_falharam_e_as_pendentes(
    caminho_das_gravacoes: Path,
):
    falhou = gravacao_datada(
        caminho_das_gravacoes, "2026-08-01-0900-falhou", status=STATUS_FALHOU, dias_atras=2
    )
    pendente = criar_pasta_de_gravacao(
        caminho_das_gravacoes, nome="2026-08-02-0900-pendente"
    )
    gravacao_datada(
        caminho_das_gravacoes,
        "2026-08-03-0900-pronta",
        status=STATUS_TRANSCRITO,
        dias_atras=2,
    )

    assert set(retencao.retidas(caminho_das_gravacoes)) == {falhou, pendente}


@pytest.mark.parametrize(
    ("bytes_", "esperado"),
    [(0, "0 B"), (512, "512 B"), (1536, "1,5 KB"), (5 * 1024**3, "5,0 GB")],
)
def test_tamanho_legivel_em_portugues(bytes_: int, esperado: str):
    assert retencao.tamanho_legivel(bytes_) == esperado
