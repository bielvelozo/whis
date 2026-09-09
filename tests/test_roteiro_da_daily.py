"""O adaptador do roteiro da daily: da pergunta montada até `Daily`.

Os testes daqui não tocam a rede — `_conversar` é substituído, como no irmão
`test_resumo_dia_claude.py`. O que se exercita é o que a camada 07 exige do
adaptador: a janela que sai, o prompt que separa o trabalho dele do contexto do
time, e a tradução da resposta que volta.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from whis.fontes import Evento
from whis.portas import Daily, ErroDeDaily, PortaDaily
from whis.resumo_dia_claude import (
    PROMPT_DA_DAILY,
    VARIAVEIS_DE_API_PAGA,
    ResumoDoDiaClaude,
    interpretar_daily,
    montar_pergunta_da_daily,
)

SEXTA = date(2026, 9, 4)


def _momento(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime.combine(dia, time(hora, minuto)).astimezone()


#: Uma janela plausível de fim de semana: sexta à tarde, sábado e segunda cedo.
EVENTOS = (
    Evento(
        fonte="git",
        momento=_momento(SEXTA, 17, 45),
        titulo="`a1b2c3d` Fecha a validacao do link coringa",
        referencia="whis",
        pessoas=("Gabriel",),
    ),
    Evento(
        fonte="linear",
        momento=_momento(SEXTA + timedelta(days=1), 11, 20),
        titulo="FN-1610 Validar o link coringa — movida para Done",
        detalhe="Subiu em produção.",
        referencia="Plataforma",
        url="https://linear.app/exemplo/issue/FN-1610",
        pessoas=("Gabriel", "Ana"),
    ),
    Evento(
        fonte="git",
        momento=_momento(SEXTA + timedelta(days=3), 8, 30),
        titulo="`d4e5f6a` Abre o PR #1623",
        referencia="loja",
        pessoas=("Gabriel",),
    ),
)

REUNIOES = ("reunioes/2026-09-04-1430-planejamento.md",)

RESPOSTA_COMPLETA = json.dumps(
    {
        "entreguei": ["Subi a validação do link coringa e fechei a FN-1610."],
        "sigo_em": ["Sigo nas FN-1617, FN-1618 e FN-1619, que ficaram em In Progress."],
        "preciso_de": ["Os PRs #1623 e #1628 estão aguardando merge."],
        "duvidas": ["O link coringa muda para todo mundo ou só para novos pedidos?"],
    },
    ensure_ascii=False,
)


class ClaudeDeMentira(ResumoDoDiaClaude):
    """`ResumoDoDiaClaude` com a chamada de rede trocada por uma resposta fixa."""

    def __init__(self, resposta: str, **extras) -> None:
        super().__init__(**extras)
        self.resposta = resposta
        self.perguntas: list[str] = []
        self.sistemas: list[str] = []

    def _conversar(self, pergunta: str, sistema: str = "") -> str:
        self.perguntas.append(pergunta)
        self.sistemas.append(sistema)
        return self.resposta


# --- a janela que sai --------------------------------------------------------


def test_pergunta_leva_todos_os_eventos_com_dia_hora_e_fonte():
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES)

    for evento in EVENTOS:
        assert evento.titulo in pergunta
    assert "04/09 17:45 [git]" in pergunta
    assert "05/09 11:20 [linear]" in pergunta
    assert "07/09 08:30 [git]" in pergunta


def test_pergunta_diz_que_o_periodo_e_desde_a_ultima_daily():
    """Sem isso o Claude escreveria "hoje" numa daily que cobre o fim de semana."""
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES)

    assert "desde a última daily" in pergunta


def test_pergunta_leva_referencia_detalhe_e_pessoas():
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES)

    assert "whis" in pergunta
    assert "Subiu em produção." in pergunta
    assert "pessoas: Gabriel, Ana" in pergunta


def test_pergunta_apresenta_a_reuniao_de_forma_legivel():
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES)

    assert "04/09 14:30 — planejamento" in pergunta


def test_periodo_sem_evento_ou_sem_reuniao_diz_que_nao_houve():
    assert "nenhum evento das fontes passivas" in montar_pergunta_da_daily((), REUNIOES)
    assert "nenhuma reunião gravada" in montar_pergunta_da_daily(EVENTOS, ())


# --- o prompt ----------------------------------------------------------------


def test_prompt_separa_o_trabalho_dele_do_contexto_do_time():
    """A regra que mais importa: o git é dele, o Linear é do time inteiro."""
    assert "a fonte já filtra por autor" in PROMPT_DA_DAILY
    assert "time INTEIRO" in PROMPT_DA_DAILY
    assert '"entreguei" e "sigo_em" são só o trabalho DELE' in PROMPT_DA_DAILY


def test_prompt_restringe_preciso_de_ao_que_espera_outra_pessoa():
    assert "SÓ o que depende de OUTRA PESSOA" in PROMPT_DA_DAILY
    # O exemplo era "os PRs #1623 e #1628 estão aguardando merge... porque quem
    # faz o merge é outra pessoa". A camada 08 o trocou: no time deste usuário o
    # merge é dele, e o exemplo empurrava o modelo a inventar um bloqueio.
    assert "esperando o review da Ana" in PROMPT_DA_DAILY
    assert "estado expirado" in PROMPT_DA_DAILY
    assert "dependem só dele" in PROMPT_DA_DAILY


def test_prompt_pede_roteiro_falado_e_nao_narrativa():
    assert "FALAR" in PROMPT_DA_DAILY
    assert "primeira pessoa" in PROMPT_DA_DAILY
    assert "sessenta segundos" in PROMPT_DA_DAILY


def test_prompt_avisa_que_o_periodo_pode_ter_varios_dias():
    assert "fim de semana inteiro" in PROMPT_DA_DAILY
    assert 'Não diga "hoje"' in PROMPT_DA_DAILY


def test_prompt_pede_json_em_portugues_preservando_termos_em_ingles():
    assert "português do Brasil" in PROMPT_DA_DAILY
    assert "JSON" in PROMPT_DA_DAILY
    assert "Nunca os traduza" in PROMPT_DA_DAILY
    for campo in ("entreguei", "sigo_em", "preciso_de", "duvidas"):
        assert campo in PROMPT_DA_DAILY


def test_prompt_proibe_inventar_e_aceita_lista_vazia():
    assert "Não invente" in PROMPT_DA_DAILY
    assert "lista vazia é uma resposta válida" in PROMPT_DA_DAILY


# --- a resposta que volta ----------------------------------------------------


def test_resposta_json_vira_daily():
    roteiro = interpretar_daily(RESPOSTA_COMPLETA)

    assert roteiro.entreguei == ("Subi a validação do link coringa e fechei a FN-1610.",)
    assert roteiro.sigo_em[0].startswith("Sigo nas FN-1617")
    assert roteiro.preciso_de == ("Os PRs #1623 e #1628 estão aguardando merge.",)
    assert roteiro.duvidas[0].startswith("O link coringa muda")


def test_json_dentro_de_cerca_de_codigo_e_aceito():
    roteiro = interpretar_daily(f"```json\n{RESPOSTA_COMPLETA}\n```")

    assert roteiro.entreguei


def test_batidas_ausentes_viram_vazio():
    roteiro = interpretar_daily('{"entreguei": ["fechei a camada 07"]}')

    assert roteiro.entreguei == ("fechei a camada 07",)
    assert roteiro.sigo_em == () and roteiro.preciso_de == () and roteiro.duvidas == ()


def test_preciso_de_vazio_e_uma_resposta_valida():
    """Dizer que não está bloqueado é melhor do que inventar um bloqueio."""
    roteiro = interpretar_daily('{"entreguei": ["subi o deploy"], "preciso_de": []}')

    assert roteiro.preciso_de == ()


def test_itens_em_branco_sao_descartados():
    roteiro = interpretar_daily('{"entreguei": ["  ", "Subi o deploy.", ""]}')

    assert roteiro.entreguei == ("Subi o deploy.",)


def test_resposta_sem_json_levanta_erro_de_daily():
    with pytest.raises(ErroDeDaily) as erro:
        interpretar_daily("Desculpe, não consegui montar a daily.")

    assert "não devolveu um objeto JSON" in str(erro.value)


def test_json_sem_nenhuma_batida_levanta_erro_de_daily():
    with pytest.raises(ErroDeDaily) as erro:
        interpretar_daily('{"resumo": "foi um bom período"}')

    assert "sem 'entreguei'" in str(erro.value)


def test_roteiro_inteiramente_vazio_e_tratado_como_falha():
    """Quatro rótulos sem nada embaixo não são um roteiro para falar em voz alta."""
    with pytest.raises(ErroDeDaily) as erro:
        interpretar_daily(
            '{"entreguei": [], "sigo_em": [], "preciso_de": [], "duvidas": []}'
        )

    assert "inteiramente vazio" in str(erro.value)


def test_resposta_crua_fica_no_log_para_diagnostico(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("ERROR", logger="whis.resumo_do_dia"):
        with pytest.raises(ErroDeDaily):
            interpretar_daily("não é json nenhum, é papo")

    assert "não é json nenhum, é papo" in caplog.text


# --- o adaptador inteiro -----------------------------------------------------


def test_resumir_daily_devolve_o_roteiro_traduzido():
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    roteiro = adaptador.resumir_daily(EVENTOS, REUNIOES)

    assert isinstance(roteiro, Daily)
    assert roteiro.preciso_de
    assert "Fecha a validacao do link coringa" in adaptador.perguntas[0]
    assert "planejamento" in adaptador.perguntas[0]


def test_a_daily_usa_o_prompt_da_daily_e_nao_o_do_diario():
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    adaptador.resumir_daily(EVENTOS, REUNIOES)

    assert adaptador.sistemas == [PROMPT_DA_DAILY]


def test_resumir_daily_propaga_a_falha_de_parse():
    adaptador = ClaudeDeMentira("o modelo divagou")

    with pytest.raises(ErroDeDaily):
        adaptador.resumir_daily(EVENTOS, REUNIOES)


def test_adaptador_atende_a_porta_da_daily():
    assert isinstance(ResumoDoDiaClaude(), PortaDaily)


def test_periodo_grande_demais_e_recusado_antes_da_chamada():
    enorme = tuple(
        Evento(
            fonte="slack",
            momento=_momento(SEXTA, 10, 0),
            titulo="mensagem " * 100,
            referencia="#geral",
        )
        for _ in range(50)
    )
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA, limite_de_caracteres=1000)

    with pytest.raises(ErroDeDaily) as erro:
        adaptador.resumir_daily(enorme, ())

    assert "grande demais" in str(erro.value)
    assert "listas cruas" in str(erro.value)
    assert adaptador.perguntas == [], "a chamada não deveria ter saído"


def test_api_key_paga_no_ambiente_recusa_a_daily(monkeypatch: pytest.MonkeyPatch):
    """A recusa do adaptador do dia vale igual para o roteiro da daily."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-paga-de-teste")

    with pytest.raises(ErroDeDaily) as erro:
        ResumoDoDiaClaude().resumir_daily(EVENTOS, REUNIOES)

    assert "OAuth" in str(erro.value)
    assert "chave-paga-de-teste" not in str(erro.value)


# --- a única conversa de verdade ---------------------------------------------


def _ha_credencial_do_claude() -> bool:
    """Há uma conta Claude logada nesta máquina, sem API key paga por perto?"""
    if any(os.environ.get(nome) for nome in VARIAVEIS_DE_API_PAGA):
        return False
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    return (Path.home() / ".claude" / ".credentials.json").is_file()


@pytest.mark.rede
@pytest.mark.skipif(
    not _ha_credencial_do_claude(),
    reason="sem conta Claude logada nesta máquina (rode `claude login`)",
)
def test_roteiro_real_separa_o_trabalho_dele_do_contexto_do_time():
    """Fala com o Claude de verdade, pela conta do usuário. Não roda por padrão.

    É o único jeito de saber se o prompt segura a regra que mais importa: o
    commit do git é dele, e a issue que outra pessoa moveu não vira "entreguei".
    """
    da_outra_pessoa = Evento(
        fonte="linear",
        momento=_momento(SEXTA, 16, 0),
        titulo="FN-1702 Refatorar o carrinho — movida para Done por Ana",
        referencia="Plataforma",
        pessoas=("Ana",),
    )

    roteiro = ResumoDoDiaClaude(timeout_s=180.0).resumir_daily(
        (*EVENTOS, da_outra_pessoa), REUNIOES
    )

    assert roteiro.entreguei or roteiro.sigo_em, "o roteiro veio sem trabalho nenhum"
    falado = " ".join((*roteiro.entreguei, *roteiro.sigo_em)).casefold()
    assert "fn-1702" not in falado, (
        f"o trabalho da Ana entrou como se fosse dele: {roteiro.entreguei}"
    )
