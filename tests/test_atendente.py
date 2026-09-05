"""Comportamento do atendente: a DM do Slack sobre a costura `responder`, sem Slack.

A DM entra pela porta como `DMFake`, entregando mensagens de fixture e
guardando o que saiu. O que se prova aqui é o que o usuário vê na DM — a
reação, a resposta com as fontes, a mensagem de erro em português — e o que
sobra depois: o fio em `conversas.json`, o ponto em `notas/daily.md`, e o
processo ainda de pé.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.busca import PASTA_PRIVADA, configuracao_da_busca, habitar_vault
from fixtures.leitura import arquivos_do_vault
from second_brain import atendente as modulo
from second_brain.atendente import (
    EMOJI_RECEBIDA,
    Atendente,
    ErroDeDM,
    Mensagem,
    PortaDM,
    formatar_para_slack,
)
from second_brain.busca import Citacao, ErroDeBusca, Resposta
from second_brain.conversa import NOME_DO_ARQUIVO, Conversas
from second_brain.fakes import RESPOSTA_PADRAO, BuscaFake, DMFake
from second_brain.instancia import Trava

FUSO = timezone(timedelta(hours=-3))
MANHA = datetime(2026, 9, 4, 9, 0, tzinfo=FUSO)
DM = "D0GABRIEL"
GABRIEL = "U0GABRIEL"


def mensagem(texto: str, *, canal: str = DM, usuario: str = GABRIEL, ts: str = "1.0", **extras) -> Mensagem:
    return Mensagem(canal=canal, usuario=usuario, texto=texto, ts=ts, **extras)


@pytest.fixture
def configuracao(tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path):
    habitar_vault(caminho_do_vault)
    return configuracao_da_busca(
        tmp_path, caminho_do_vault, caminho_das_gravacoes, pastas_privadas=(PASTA_PRIVADA,)
    )


@pytest.fixture
def conversas(tmp_path: Path) -> Conversas:
    return Conversas(tmp_path / NOME_DO_ARQUIVO)


@pytest.fixture
def busca() -> BuscaFake:
    return BuscaFake()


@pytest.fixture
def atender(configuracao, conversas: Conversas, busca: BuscaFake):
    """Roda o atendente sobre as mensagens: `atender([...], relogios=[...])` → o `DMFake`."""

    def executar(mensagens, *, relogios=(MANHA,), **extras) -> DMFake:
        dm = extras.pop("dm", None)
        if dm is None:
            dm = DMFake(mensagens, parar=threading.Event())
        parar = dm.parar or threading.Event()
        momentos = list(relogios)
        atendente = Atendente(
            configuracao,
            dm=dm,
            busca=extras.pop("busca", busca),
            conversas=extras.pop("conversas", conversas),
            relogio=lambda: momentos.pop(0) if len(momentos) > 1 else momentos[0],
        )
        atendente.executar(parar=parar)
        return dm

    return executar


# -- Caminho feliz ------------------------------------------------------------


def test_mensagem_na_dm_recebe_reacao_e_resposta_com_as_fontes(atender):
    pergunta = mensagem("o que ficou decidido sobre a retenção?")

    dm = atender([pergunta])

    assert dm.reacoes == [(pergunta, EMOJI_RECEBIDA)]
    assert len(dm.respostas) == 1
    assert dm.respostas[0][0] == pergunta
    texto = dm.respostas[0][1]
    assert RESPOSTA_PADRAO.texto in texto
    assert "_Fontes:_" in texto
    assert "`reunioes/2026-09-03-1403-reuniao.md`" in texto


def test_a_reacao_vem_antes_da_resposta(atender, busca: BuscaFake):
    ordem: list[str] = []

    class DMQueAnota(DMFake):
        def reagir(self, mensagem, emoji):
            ordem.append("reagiu")
            super().reagir(mensagem, emoji)

        def responder(self, mensagem, texto):
            ordem.append("respondeu")
            super().responder(mensagem, texto)

    parar = threading.Event()
    atender([], dm=DMQueAnota([mensagem("?")], parar=parar))

    assert ordem == ["reagiu", "respondeu"]


def test_o_atendente_encerra_a_dm_ao_parar(atender):
    dm = atender([mensagem("?")])

    assert dm.iniciada and dm.encerrada


def test_dm_fake_satisfaz_a_porta():
    assert isinstance(DMFake(), PortaDM)


# -- O que não é atendido -----------------------------------------------------


@pytest.mark.parametrize(
    "fora",
    [
        mensagem("em canal", canal="C0PLATAFORMA", tipo_de_canal="channel"),
        mensagem("em group dm", canal="G0GRUPO", tipo_de_canal="mpim"),
        mensagem("de mim mesmo", usuario="U0BOT"),
        mensagem("de outro bot", do_bot=True),
        mensagem("editada", subtipo="message_changed"),
        mensagem("   "),
    ],
)
def test_so_a_dm_com_o_bot_e_atendida(atender, busca: BuscaFake, fora: Mensagem):
    dm = atender([fora])

    assert dm.reacoes == []
    assert dm.respostas == []
    assert busca.perguntas_recebidas == []


# -- O fio por DM ---------------------------------------------------------------


def test_a_pergunta_de_acompanhamento_recebe_o_fio_da_mesma_dm(atender, busca: BuscaFake, conversas):
    atender(
        [mensagem("o que ficou decidido sobre a retenção?"), mensagem("e quem levantou isso?", ts="2.0")],
        relogios=[MANHA, MANHA + timedelta(hours=6)],
    )

    assert [turno.texto for turno in busca.historico_recebido] == [
        "o que ficou decidido sobre a retenção?",
        RESPOSTA_PADRAO.texto,
    ]
    assert len(conversas.abrir(DM, agora=MANHA + timedelta(hours=7)).historico()) == 4


def test_dms_diferentes_tem_fios_diferentes(atender, busca: BuscaFake, conversas):
    atender(
        [mensagem("pergunta no PC"), mensagem("pergunta de outra DM", canal="D0OUTRA", ts="2.0")],
        relogios=[MANHA, MANHA + timedelta(minutes=5)],
    )

    assert busca.historico_recebido == ()
    assert len(conversas.abrir(DM, agora=MANHA).historico()) == 2
    assert len(conversas.abrir("D0OUTRA", agora=MANHA).historico()) == 2


def test_depois_de_25h_de_silencio_o_fio_comeca_limpo(atender, busca: BuscaFake):
    atender(
        [mensagem("ontem"), mensagem("hoje, outro assunto", ts="2.0")],
        relogios=[MANHA, MANHA + timedelta(hours=25)],
    )

    assert busca.historico_recebido == ()


# -- Nada derruba o processo ---------------------------------------------------


def test_erro_de_busca_vira_mensagem_em_portugues_e_o_atendimento_continua(atender):
    dm = atender(
        [mensagem("primeira"), mensagem("segunda", ts="2.0")],
        busca=BuscaFake(erro=ErroDeBusca("sem conta logada")),
    )

    assert len(dm.respostas) == 2
    assert dm.respostas[0][1] == "Não consegui responder agora: sem conta logada"
    assert dm.respostas[1][1] == "Não consegui responder agora: sem conta logada"


def test_excecao_inesperada_nao_derruba_e_fica_no_log(atender, caplog):
    with caplog.at_level(logging.ERROR, logger="second_brain.atendente"):
        dm = atender(
            [mensagem("primeira"), mensagem("segunda", ts="2.0")],
            busca=BuscaFake(erro=RuntimeError("boom")),
        )

    assert len(dm.respostas) == 2
    assert "erro inesperado (RuntimeError)" in dm.respostas[0][1]
    assert "boom" not in dm.respostas[0][1]
    assert "boom" in caplog.text


def test_falha_ao_reagir_nao_impede_a_resposta(atender):
    parar = threading.Event()
    dm = atender([], dm=DMFake([mensagem("?")], parar=parar, erro_ao_reagir=ErroDeDM("sem reactions:write")))

    assert len(dm.respostas) == 1


def test_falha_ao_publicar_fica_no_log_e_a_proxima_e_atendida(atender, busca: BuscaFake, caplog):
    parar = threading.Event()
    with caplog.at_level(logging.ERROR, logger="second_brain.atendente"):
        atender(
            [],
            dm=DMFake(
                [mensagem("primeira"), mensagem("segunda", ts="2.0")],
                parar=parar,
                erro_ao_responder=ErroDeDM("chat:write faltando"),
            ),
        )

    assert busca.perguntas_recebidas == ["primeira", "segunda"]
    assert "chat:write faltando" in caplog.text


def test_erro_de_busca_nao_entra_no_fio(atender, conversas):
    atender([mensagem("?")], busca=BuscaFake(erro=ErroDeBusca("sem rede")))

    assert conversas.abrir(DM, agora=MANHA).vazia()


# -- "Não achei" ----------------------------------------------------------------


def test_nao_achei_diz_isso_sem_inventar(atender):
    dm = atender([mensagem("link coringa?")], busca=BuscaFake(Resposta(texto="", achou=False)))

    texto = dm.respostas[0][1]
    assert texto.startswith("Não achei.")
    assert "nada no vault sustenta uma resposta" in texto
    assert "Fontes" not in texto


# -- A única escrita: anotar --------------------------------------------------


@pytest.mark.parametrize(
    "pedido",
    ["anotar preciso do acesso ao Sentry", "Anotar: preciso do acesso ao Sentry", "anotar — preciso do acesso ao Sentry"],
)
def test_anotar_escreve_o_ponto_em_notas_daily_sem_passar_pelo_modelo(
    atender, busca: BuscaFake, configuracao, pedido: str
):
    dm = atender([mensagem(pedido)])

    pontos = (configuracao.vault / "notas" / "daily.md").read_text(encoding="utf-8")
    assert "- [ ] preciso do acesso ao Sentry" in pontos
    assert busca.perguntas_recebidas == []
    assert "Anotado em `notas/daily.md`" in dm.respostas[0][1]


def test_anotar_sem_texto_pede_o_texto(atender, configuracao):
    dm = atender([mensagem("anotar")])

    assert "Anotar o quê?" in dm.respostas[0][1]
    assert not (configuracao.vault / "notas" / "daily.md").exists()


def test_uma_pergunta_normal_nao_escreve_nada_no_vault(atender, configuracao):
    antes = arquivos_do_vault(configuracao.vault)

    atender([mensagem("anotaram algo sobre retenção?"), mensagem("o que ficou decidido?", ts="2.0")])

    assert arquivos_do_vault(configuracao.vault) == antes


# -- O texto no Slack -----------------------------------------------------------


def test_formatar_converte_links_e_negrito_para_o_mrkdwn_do_slack():
    resposta = Resposta(
        texto="Ficou **aprovado** na [PR #1636](https://github.com/x/y/pull/1636).",
        citacoes=(Citacao("daily/2026-09-04.md", "trecho com [link](https://a.b)"),),
    )

    texto = formatar_para_slack(resposta)

    assert "*aprovado*" in texto
    assert "<https://github.com/x/y/pull/1636|PR #1636>" in texto
    assert "• `daily/2026-09-04.md` — trecho com <https://a.b|link>" in texto


def test_formatar_sem_citacao_nao_inventa_secao_de_fontes():
    assert "Fontes" not in formatar_para_slack(Resposta(texto="x"))


# -- executar: trava, log e encerramento ------------------------------------------


def test_executar_sobe_atende_e_encerra_limpo_com_ctrl_c(configuracao, busca: BuscaFake, capsys):
    dm = DMFake([mensagem("?")])

    codigo = modulo.executar(configuracao, dm=dm, busca=busca)

    assert codigo == 0
    assert len(dm.respostas) == 1
    assert dm.encerrada
    assert "Atendente do Second Brain subindo" in capsys.readouterr().out
    log = (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")
    assert "Atendente no ar como U0BOT" in log
    assert "encerrado pelo usuário" in log


def test_o_fio_do_executar_mora_ao_lado_da_configuracao(configuracao, busca: BuscaFake):
    modulo.executar(configuracao, dm=DMFake([mensagem("?")]), busca=busca)

    assert (configuracao.origem.parent / NOME_DO_ARQUIVO).is_file()


def test_segunda_instancia_e_recusada(configuracao, busca: BuscaFake, capsys):
    with Trava(modulo.caminho_da_trava(configuracao)):
        codigo = modulo.executar(configuracao, dm=DMFake([mensagem("?")]), busca=busca)

    assert codigo == 1
    assert "um atendente" in capsys.readouterr().out


def test_a_trava_e_liberada_ao_sair(configuracao, busca: BuscaFake):
    modulo.executar(configuracao, dm=DMFake([]), busca=busca)

    assert modulo.executar(configuracao, dm=DMFake([]), busca=busca) == 0


def test_dm_que_nao_sobe_sai_um_com_o_motivo_no_log(configuracao, busca: BuscaFake):
    dm = DMFake([], erro_ao_iniciar=ErroDeDM("Socket Mode desligado na app"))

    codigo = modulo.executar(configuracao, dm=dm, busca=busca)

    assert codigo == 1
    log = (configuracao.origem.parent / "bandeja.log").read_text(encoding="utf-8")
    assert "Socket Mode desligado na app" in log
