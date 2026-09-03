"""O adaptador de resumo do dia: da pergunta montada até `ResumoDoDia`.

Os testes daqui não tocam a rede. Eles exercitam as duas metades do adaptador
separadamente — o dia que sai e a tradução da resposta que volta —, mais o que
o diário aprendeu a exigir dele: recusar API key paga e deixar o custo no log.
A única parte que fala com o Claude de verdade é `_conversar`, substituída
aqui, e coberta pelo teste marcado `rede`, que só roda quando o usuário pede.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from second_brain.fontes import Evento
from second_brain.portas import ErroDeResumoDoDia, PortaResumoDoDia, ResumoDoDia
from second_brain.resumo_dia_claude import (
    PROMPT_DO_SISTEMA,
    VARIAVEIS_DE_API_PAGA,
    ResumoDoDiaClaude,
    interpretar_resposta,
    montar_pergunta,
    registrar_custo,
    verificar_credencial,
)

DIA = date(2026, 9, 3)


def _momento(dia: date, hora: int, minuto: int) -> datetime:
    return datetime.combine(dia, time(hora, minuto)).astimezone()


#: Um dia plausível: duas fontes entrelaçadas e um commit da madrugada seguinte.
EVENTOS = (
    Evento(
        fonte="git",
        momento=_momento(DIA, 9, 12),
        titulo="`a1b2c3d` Fecha a camada 01 do diario",
        referencia="second-brain",
        pessoas=("Gabriel",),
    ),
    Evento(
        fonte="linear",
        momento=_momento(DIA, 11, 20),
        titulo="FN-123 Corrigir o cálculo de frete — movida para Done",
        detalhe="Subiu em produção; falta acompanhar o gráfico de erros.",
        referencia="Plataforma",
        url="https://linear.app/exemplo/issue/FN-123",
        pessoas=("Gabriel", "Ana"),
    ),
    Evento(
        fonte="git",
        momento=_momento(DIA + timedelta(days=1), 1, 20),
        titulo="`d4e5f6a` Corrige o calculo de frete no checkout",
        referencia="loja",
        pessoas=("Gabriel",),
    ),
)

REUNIOES = ("reunioes/2026-09-03-1430-daily-do-time.md",)

RESPOSTA_COMPLETA = json.dumps(
    {
        "narrativa": (
            "O dia começou fechando a camada 01 do diário e virou para o "
            "checkout depois da daily.\n\nA correção do frete saiu do Linear "
            "para produção no mesmo dia."
        ),
        "destaques": ["A camada 01 do diário foi fechada."],
        "pendencias": ["Acompanhar o gráfico de erros do checkout."],
        "temas": ["fontes passivas", "checkout"],
    },
    ensure_ascii=False,
)


class ClaudeDeMentira(ResumoDoDiaClaude):
    """`ResumoDoDiaClaude` com a chamada de rede trocada por uma resposta fixa."""

    def __init__(self, resposta: str, **extras) -> None:
        super().__init__(**extras)
        self.resposta = resposta
        self.perguntas: list[str] = []

    def _conversar(self, pergunta: str) -> str:
        self.perguntas.append(pergunta)
        return self.resposta


# --- o dia que sai -----------------------------------------------------------


def test_pergunta_leva_todos_os_eventos_com_hora_e_fonte():
    pergunta = montar_pergunta(EVENTOS, REUNIOES)

    for evento in EVENTOS:
        assert evento.titulo in pergunta
    assert "09:12 [git]" in pergunta
    assert "11:20 [linear]" in pergunta


def test_pergunta_leva_referencia_detalhe_e_pessoas():
    pergunta = montar_pergunta(EVENTOS, REUNIOES)

    assert "second-brain" in pergunta
    assert "Subiu em produção; falta acompanhar o gráfico de erros." in pergunta
    assert "pessoas: Gabriel, Ana" in pergunta


def test_evento_da_madrugada_leva_o_dia_junto_da_hora():
    """A janela do diário atravessa a meia-noite; só `HH:MM` seria ambíguo."""
    pergunta = montar_pergunta(EVENTOS, REUNIOES)

    assert "03/09 09:12" in pergunta
    assert "04/09 01:20" in pergunta


def test_pergunta_apresenta_a_reuniao_de_forma_legivel():
    pergunta = montar_pergunta(EVENTOS, REUNIOES)

    assert "03/09 14:30 — daily do time" in pergunta


def test_reuniao_com_nome_fora_do_padrao_volta_como_veio():
    pergunta = montar_pergunta(EVENTOS, ("reunioes/renomeada-a-mao.md",))

    assert "reunioes/renomeada-a-mao.md" in pergunta


def test_dia_sem_reuniao_diz_que_nao_houve():
    pergunta = montar_pergunta(EVENTOS, ())

    assert "nenhuma reunião gravada" in pergunta


def test_dia_so_com_reuniao_diz_que_nao_houve_evento():
    pergunta = montar_pergunta((), REUNIOES)

    assert "nenhum evento das fontes passivas" in pergunta
    assert "daily do time" in pergunta


def test_prompt_pede_narrativa_que_liga_as_fontes_e_nao_uma_lista_reescrita():
    assert "liga" in PROMPT_DO_SISTEMA
    assert "não reescreve a lista de eventos" in PROMPT_DO_SISTEMA


def test_prompt_pede_json_em_portugues_preservando_termos_em_ingles():
    assert "português do Brasil" in PROMPT_DO_SISTEMA
    assert "JSON" in PROMPT_DO_SISTEMA
    assert "Nunca os traduza" in PROMPT_DO_SISTEMA
    for campo in ("narrativa", "destaques", "pendencias", "temas"):
        assert campo in PROMPT_DO_SISTEMA


def test_prompt_proibe_inventar_e_aceita_lista_vazia():
    assert "Não invente" in PROMPT_DO_SISTEMA
    assert "lista vazia é uma resposta válida" in PROMPT_DO_SISTEMA


def test_prompt_pede_temas_curtos_para_o_frontmatter():
    assert "uma a três palavras" in PROMPT_DO_SISTEMA
    assert "frontmatter" in PROMPT_DO_SISTEMA


# --- a resposta que volta ----------------------------------------------------


def test_resposta_json_vira_resumo_do_dia():
    resumo = interpretar_resposta(RESPOSTA_COMPLETA)

    assert "camada 01 do diário" in resumo.narrativa
    assert resumo.destaques == ("A camada 01 do diário foi fechada.",)
    assert resumo.pendencias == ("Acompanhar o gráfico de erros do checkout.",)
    assert resumo.temas == ("fontes passivas", "checkout")


def test_json_dentro_de_cerca_de_codigo_e_aceito():
    resumo = interpretar_resposta(f"```json\n{RESPOSTA_COMPLETA}\n```")

    assert resumo.temas == ("fontes passivas", "checkout")


def test_json_com_frase_em_volta_e_aceito():
    bruto = f"Claro, aqui está o diário:\n{RESPOSTA_COMPLETA}\nEspero que ajude."

    assert interpretar_resposta(bruto).temas == ("fontes passivas", "checkout")


def test_campos_ausentes_viram_vazio():
    resumo = interpretar_resposta('{"narrativa": "Um dia tranquilo."}')

    assert resumo.narrativa == "Um dia tranquilo."
    assert resumo.destaques == ()
    assert resumo.pendencias == ()
    assert resumo.temas == ()


def test_narrativa_em_paragrafos_separados_vira_texto_corrido():
    resumo = interpretar_resposta(
        '{"narrativa": ["Primeiro parágrafo.", "Segundo parágrafo."], "temas": []}'
    )

    assert resumo.narrativa == "Primeiro parágrafo.\n\nSegundo parágrafo."


def test_itens_em_branco_sao_descartados():
    resumo = interpretar_resposta(
        '{"destaques": ["  ", "Subiu o deploy.", ""], "temas": [], "pendencias": []}'
    )

    assert resumo.destaques == ("Subiu o deploy.",)


def test_item_devolvido_como_objeto_vira_frase():
    resumo = interpretar_resposta(
        '{"narrativa": "x", "pendencias": [{"pendencia": "Rodar o review",'
        ' "dono": "Ana"}]}'
    )

    assert resumo.pendencias == ("Rodar o review — Ana",)


def test_resposta_sem_json_levanta_erro_de_resumo_do_dia():
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta("Desculpe, não consegui resumir este dia.")

    assert "não devolveu um objeto JSON" in str(erro.value)


def test_json_malformado_levanta_erro_de_resumo_do_dia():
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta('{"destaques": ["sem fechar"')

    assert "malformado" in str(erro.value)


def test_json_que_nao_e_objeto_levanta_erro_de_resumo_do_dia():
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta('["um destaque", "outro"]')

    assert "não é um objeto" in str(erro.value)


def test_json_sem_nenhum_dos_campos_levanta_erro_de_resumo_do_dia():
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta('{"resumo": "foi um bom dia"}')

    assert "sem 'narrativa'" in str(erro.value)


def test_resumo_inteiramente_vazio_e_tratado_como_falha():
    """Seções vazias sem aviso fariam um diário incompleto se passar por completo."""
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta(
            '{"narrativa": "", "destaques": [], "pendencias": [], "temas": []}'
        )

    assert "inteiramente vazio" in str(erro.value)


def test_resposta_crua_fica_no_log_para_diagnostico(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("ERROR", logger="second_brain.resumo_do_dia"):
        with pytest.raises(ErroDeResumoDoDia):
            interpretar_resposta("não é json nenhum, é papo")

    assert "não é json nenhum, é papo" in caplog.text


def test_mensagem_de_erro_e_diagnosticavel_em_portugues():
    with pytest.raises(ErroDeResumoDoDia) as erro:
        interpretar_resposta("nada de json aqui")

    mensagem = str(erro.value)
    assert "nada de json aqui" in mensagem
    assert "log" in mensagem


# --- o adaptador inteiro -----------------------------------------------------


def test_resumir_dia_devolve_o_resumo_traduzido():
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    resumo = adaptador.resumir_dia(EVENTOS, REUNIOES)

    assert isinstance(resumo, ResumoDoDia)
    assert resumo.temas == ("fontes passivas", "checkout")
    assert "Fecha a camada 01 do diario" in adaptador.perguntas[0]
    assert "daily do time" in adaptador.perguntas[0]


def test_resumir_dia_propaga_a_falha_de_parse():
    adaptador = ClaudeDeMentira("o modelo divagou")

    with pytest.raises(ErroDeResumoDoDia):
        adaptador.resumir_dia(EVENTOS, REUNIOES)


def test_adaptador_atende_a_porta_de_resumo_do_dia():
    assert isinstance(ResumoDoDiaClaude(), PortaResumoDoDia)


def test_construtor_sem_argumentos_usa_o_modelo_da_conta():
    assert ResumoDoDiaClaude().modelo is None


def test_modelo_pode_ser_fixado_na_construcao():
    assert ResumoDoDiaClaude(modelo="claude-opus-5").modelo == "claude-opus-5"


def test_modelo_vazio_da_configuracao_vira_o_padrao_da_conta():
    assert ResumoDoDiaClaude(modelo="").modelo is None


def test_dia_grande_demais_e_recusado_antes_da_chamada():
    enorme = tuple(
        Evento(
            fonte="slack",
            momento=_momento(DIA, 10, 0),
            titulo="mensagem " * 100,
            referencia="#geral",
        )
        for _ in range(50)
    )
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA, limite_de_caracteres=1000)

    with pytest.raises(ErroDeResumoDoDia) as erro:
        adaptador.resumir_dia(enorme, ())

    assert "grande demais" in str(erro.value)
    assert "listas cruas" in str(erro.value)
    assert adaptador.perguntas == [], "a chamada não deveria ter saído"


# --- a credencial ------------------------------------------------------------


@pytest.mark.parametrize("variavel", VARIAVEIS_DE_API_PAGA)
def test_api_key_paga_no_ambiente_recusa_a_chamada(
    variavel: str, monkeypatch: pytest.MonkeyPatch
):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv(variavel, "chave-paga-de-teste")

    with pytest.raises(ErroDeResumoDoDia) as erro:
        verificar_credencial()

    mensagem = str(erro.value)
    assert variavel in mensagem
    assert "claude login" in mensagem
    assert "chave-paga-de-teste" not in mensagem, "a chave não pode vazar no erro"


def test_ambiente_sem_api_key_paga_deixa_a_chamada_seguir(monkeypatch: pytest.MonkeyPatch):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)

    verificar_credencial()


def test_api_key_vazia_nao_conta_como_api_key(monkeypatch: pytest.MonkeyPatch):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    verificar_credencial()


def test_adaptador_real_recusa_o_dia_antes_de_falar_com_o_claude(
    monkeypatch: pytest.MonkeyPatch,
):
    """A recusa vale para o caminho inteiro, não só para a função de checagem."""
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-paga-de-teste")

    with pytest.raises(ErroDeResumoDoDia) as erro:
        ResumoDoDiaClaude().resumir_dia(EVENTOS, REUNIOES)

    assert "OAuth" in str(erro.value)


# --- o custo da assinatura ---------------------------------------------------


def _resultado(**extras) -> ResultMessage:
    """Um `ResultMessage` como o SDK entrega ao fim de um turno."""
    campos = {
        "subtype": "success",
        "duration_ms": 8421,
        "duration_api_ms": 8100,
        "is_error": False,
        "num_turns": 1,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.0731,
        "usage": {
            "input_tokens": 4210,
            "output_tokens": 512,
            "cache_read_input_tokens": 1024,
        },
    }
    return ResultMessage(**{**campos, **extras})


def test_custo_do_dia_fica_no_log(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="second_brain.resumo_do_dia"):
        registrar_custo(_resultado())

    assert "US$ 0.0731" in caplog.text
    assert "4210" in caplog.text
    assert "512" in caplog.text


def test_custo_ausente_e_registrado_como_nao_informado(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="second_brain.resumo_do_dia"):
        registrar_custo(_resultado(total_cost_usd=None, usage=None))

    assert "não informado" in caplog.text


def test_turno_sem_resultado_nao_registra_custo(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="second_brain.resumo_do_dia"):
        registrar_custo(None)

    assert caplog.text == ""


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
def test_resumo_real_do_dia_em_portugues():
    """Fala com o Claude de verdade, pela conta do usuário. Não roda por padrão."""
    resumo = ResumoDoDiaClaude(timeout_s=180.0).resumir_dia(EVENTOS, REUNIOES)

    assert resumo.narrativa or resumo.destaques or resumo.temas, "o resumo veio vazio"
    assert all(len(tema.split()) <= 4 for tema in resumo.temas), (
        f"temas do frontmatter não deviam ser frases: {resumo.temas}"
    )
