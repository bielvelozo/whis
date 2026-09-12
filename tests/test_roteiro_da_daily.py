"""O adaptador da daily: da pergunta montada até `Daily`.

Os testes daqui não tocam a rede — `_conversar` é substituído, como no irmão
`test_resumo_dia_claude.py`. O que se exercita é o que a nota viva exige do
adaptador: a janela e a nota que saem, o prompt que separa o trabalho dele do
contexto do time e manda não repetir, e a tradução da resposta que volta.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from whis.fontes import Evento
from whis.nota_viva import SECAO_FAZENDO, NotaViva
from whis.portas import Daily, ErroDeDaily, ItemNovo, PortaDaily
from whis.resumo_dia_claude import (
    PROMPT_DA_DAILY,
    VARIAVEIS_DE_API_PAGA,
    ResumoDoDiaClaude,
    interpretar_daily,
    montar_pergunta_da_daily,
)

SEXTA = date(2026, 9, 4)

NOTA = NotaViva.de_texto(
    "---\ntipo: daily-atual\n---\n\n"
    "## O que eu fiz\n\n- fechei a FN-1610\n\n"
    "## O que estou fazendo\n\n1. Correções que o Ribeiro apontou\n\t1. FN-1786, a foto extra \n\n"
    "## Dúvidas\n\n- o link coringa muda para todo mundo?\n\n"
    "## Falar\n\n- avisar da folga de sexta\n"
)


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
        "fiz": [{"texto": "FN-1773, o aviso amarelo do envio virou toast", "sob": "a1b2c3"}],
        "fazendo": [
            {"texto": "Correções que o Lucas pediu no flow de pix", "sob": None},
            {"texto": "FN-1790, o pix pendente não expira", "sob": "Correções que o Lucas pediu no flow de pix"},
        ],
        "mover": ["d4e5f6"],
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


def test_pergunta_leva_a_nota_viva_com_um_id_por_item_do_agente():
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES, nota=NOTA)

    grupo, foto = NOTA.itens(SECAO_FAZENDO)
    assert f"1. Correções que o Ribeiro apontou (id {grupo.id})" in pergunta
    assert f"\t1. FN-1786, a foto extra (id {foto.id})" in pergunta
    assert "- fechei a FN-1610 (id " in pergunta
    assert pergunta.index("## O que eu fiz") < pergunta.index("Tudo que aconteceu desde a última daily")


def test_pergunta_leva_duvidas_e_falar_como_contexto_sem_id():
    pergunta = montar_pergunta_da_daily(EVENTOS, REUNIOES, nota=NOTA)

    assert "## Dúvidas\n\n- o link coringa muda para todo mundo?\n" in pergunta
    assert "## Falar\n\n- avisar da folga de sexta\n" in pergunta
    assert "para você não repetir o que ele já anotou" in pergunta


def test_sem_nota_a_pergunta_nao_fala_dela():
    assert "A nota viva como está agora" not in montar_pergunta_da_daily(EVENTOS, REUNIOES)


# --- o prompt ----------------------------------------------------------------


def test_prompt_separa_o_trabalho_dele_do_contexto_do_time():
    """A regra que mais importa: o git é dele, o Linear é do time inteiro."""
    assert "a fonte já filtra por autor" in PROMPT_DA_DAILY
    assert "time INTEIRO" in PROMPT_DA_DAILY
    assert '"fiz" e "fazendo" são só o trabalho DELE' in PROMPT_DA_DAILY


def test_prompt_manda_acrescentar_e_apontar_sem_reescrever():
    assert "Nunca reescrever" in PROMPT_DA_DAILY
    assert "nunca repetir o que já está na nota" in PROMPT_DA_DAILY
    assert "Você nunca devolve o texto de um item que já existe" in PROMPT_DA_DAILY
    assert "(id a1b2c3)" in PROMPT_DA_DAILY


def test_prompt_manda_mover_so_com_sinal_forte():
    assert "PR mergeada, issue movida para Done" in PROMPT_DA_DAILY
    assert 'Na dúvida, deixe em "O que estou fazendo"' in PROMPT_DA_DAILY


def test_prompt_segue_a_regua_das_dailies_a_mao():
    assert "Agrupe por quem pediu" in PROMPT_DA_DAILY
    assert "Ancore no sintoma, não no commit" in PROMPT_DA_DAILY
    assert "Carregue o id da issue inline" in PROMPT_DA_DAILY
    assert "roteiro seco, sem personalidade" in PROMPT_DA_DAILY


def test_prompt_diz_que_duvidas_e_falar_sao_do_usuario():
    assert '"Dúvidas" e "Falar" são do usuário' in PROMPT_DA_DAILY
    assert "você nunca escreve nelas" in PROMPT_DA_DAILY


def test_prompt_poe_o_que_espera_outra_pessoa_dentro_do_item():
    assert 'diga isso dentro do item de "fazendo", nomeando de quem depende' in PROMPT_DA_DAILY
    assert "NÃO deduza de quem é uma etapa pelo nome do estado" in PROMPT_DA_DAILY


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
    for campo in ('"fiz"', '"fazendo"', '"mover"', '"sob"'):
        assert campo in PROMPT_DA_DAILY


def test_prompt_proibe_inventar_e_aceita_lista_vazia():
    assert "Não invente" in PROMPT_DA_DAILY
    assert "lista vazia é uma resposta válida" in PROMPT_DA_DAILY


# --- a resposta que volta ----------------------------------------------------


def test_resposta_json_vira_daily():
    roteiro = interpretar_daily(RESPOSTA_COMPLETA)

    assert roteiro.fiz == (ItemNovo("FN-1773, o aviso amarelo do envio virou toast", sob="a1b2c3"),)
    assert roteiro.fazendo == (
        ItemNovo("Correções que o Lucas pediu no flow de pix"),
        ItemNovo("FN-1790, o pix pendente não expira", sob="Correções que o Lucas pediu no flow de pix"),
    )
    assert roteiro.mover == ("d4e5f6",)


def test_json_dentro_de_cerca_de_codigo_e_aceito():
    roteiro = interpretar_daily(f"```json\n{RESPOSTA_COMPLETA}\n```")

    assert roteiro.fiz


def test_listas_ausentes_viram_vazio():
    roteiro = interpretar_daily('{"fiz": [{"texto": "fechei a camada 07"}]}')

    assert roteiro.fiz == (ItemNovo("fechei a camada 07"),)
    assert roteiro.fazendo == () and roteiro.mover == ()


def test_item_como_string_solta_vale_como_item_sem_pai():
    roteiro = interpretar_daily('{"fiz": ["fechei a camada 07"]}')

    assert roteiro.fiz == (ItemNovo("fechei a camada 07"),)


def test_tres_listas_vazias_sao_uma_resposta_valida():
    """Numa segunda execução do dia, "a nota já diz tudo" é a resposta certa."""
    roteiro = interpretar_daily('{"fiz": [], "fazendo": [], "mover": []}')

    assert roteiro == Daily()


def test_itens_em_branco_sao_descartados():
    roteiro = interpretar_daily('{"fiz": [{"texto": "  "}, "Subi o deploy.", ""]}')

    assert roteiro.fiz == (ItemNovo("Subi o deploy."),)


def test_resposta_sem_json_levanta_erro_de_daily():
    with pytest.raises(ErroDeDaily) as erro:
        interpretar_daily("Desculpe, não consegui montar a daily.")

    assert "não devolveu um objeto JSON" in str(erro.value)


def test_json_sem_nenhuma_das_listas_levanta_erro_de_daily():
    with pytest.raises(ErroDeDaily) as erro:
        interpretar_daily('{"resumo": "foi um bom período"}')

    assert "sem 'fiz'" in str(erro.value)


def test_json_vazio_levanta_erro_de_daily():
    with pytest.raises(ErroDeDaily):
        interpretar_daily("{}")


def test_resposta_crua_fica_no_log_para_diagnostico(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("ERROR", logger="whis.resumo_do_dia"):
        with pytest.raises(ErroDeDaily):
            interpretar_daily("não é json nenhum, é papo")

    assert "não é json nenhum, é papo" in caplog.text


# --- o adaptador inteiro -----------------------------------------------------


def test_resumir_daily_devolve_a_resposta_traduzida():
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    roteiro = adaptador.resumir_daily(EVENTOS, REUNIOES, NOTA)

    assert isinstance(roteiro, Daily)
    assert roteiro.mover == ("d4e5f6",)
    assert "Fecha a validacao do link coringa" in adaptador.perguntas[0]
    assert "planejamento" in adaptador.perguntas[0]
    assert "Correções que o Ribeiro apontou (id " in adaptador.perguntas[0]


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
    commit do git é dele, e a issue que outra pessoa moveu não vira item de "fiz".
    """
    da_outra_pessoa = Evento(
        fonte="linear",
        momento=_momento(SEXTA, 16, 0),
        titulo="FN-1702 Refatorar o carrinho — movida para Done por Ana",
        referencia="Plataforma",
        pessoas=("Ana",),
    )

    roteiro = ResumoDoDiaClaude(timeout_s=180.0).resumir_daily(
        (*EVENTOS, da_outra_pessoa), REUNIOES, NotaViva.do_modelo()
    )

    assert roteiro.fiz or roteiro.fazendo, "a resposta veio sem trabalho nenhum"
    falado = " ".join(item.texto for item in (*roteiro.fiz, *roteiro.fazendo)).casefold()
    assert "fn-1702" not in falado, f"o trabalho da Ana entrou como se fosse dele: {roteiro.fiz}"
