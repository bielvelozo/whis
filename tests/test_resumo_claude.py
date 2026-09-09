"""O adaptador de resumo do Claude: da resposta crua até `Resumo`.

Os testes daqui não tocam a rede. Eles exercitam as duas metades do adaptador
separadamente: a pergunta que sai e a tradução da resposta que volta. A única
parte que fala com o Claude de verdade é `_conversar`, substituída aqui — e
coberta pelo teste marcado `rede`, que só roda quando o usuário pede.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from whis.portas import EU, OUTROS, ErroDeResumo, Fala, PortaResumo, Resumo, Transcricao
from whis.resumo_claude import (
    PROMPT_DO_SISTEMA,
    VARIAVEIS_DE_API_PAGA,
    ResumoClaude,
    interpretar_resposta,
    montar_pergunta,
    verificar_credencial,
)

TRANSCRICAO = Transcricao(
    falas=(
        Fala(EU, "Bom dia. Vamos fechar o rollback hoje?", 0.0),
        Fala(OUTROS, "Aqui é a Ana. Eu faço o deploy depois do review.", 4.5),
    ),
)

RESPOSTA_COMPLETA = json.dumps(
    {
        "titulo": "daily do time",
        "participantes": ["Gabriel", "Ana"],
        "decisoes": ["O rollback fica para depois do review."],
        "acoes": ["Ana faz o deploy depois do review."],
        "topicos": ["Rollback", "Deploy"],
    },
    ensure_ascii=False,
)


class ClaudeDeMentira(ResumoClaude):
    """`ResumoClaude` com a chamada de rede trocada por uma resposta fixa."""

    def __init__(self, resposta: str, **extras) -> None:
        super().__init__(**extras)
        self.resposta = resposta
        self.perguntas: list[str] = []

    def _conversar(self, pergunta: str) -> str:
        self.perguntas.append(pergunta)
        return self.resposta


# --- a pergunta que sai ------------------------------------------------------


def test_pergunta_leva_a_transcricao_inteira():
    pergunta = montar_pergunta(TRANSCRICAO)

    for fala in TRANSCRICAO.falas:
        assert fala.texto in pergunta
    assert "eu:" in pergunta
    assert "outros:" in pergunta


def test_pergunta_leva_o_titulo_da_gravacao():
    assert "daily do time" in montar_pergunta(TRANSCRICAO, "daily do time")


def test_pergunta_sem_titulo_diz_que_nao_ha_titulo():
    pergunta = montar_pergunta(TRANSCRICAO, None)

    assert "não tem título" in pergunta


def test_prompt_pede_json_em_portugues_preservando_termos_em_ingles():
    assert "português do Brasil" in PROMPT_DO_SISTEMA
    assert "JSON" in PROMPT_DO_SISTEMA
    assert "Nunca os traduza" in PROMPT_DO_SISTEMA
    for campo in ("decisoes", "acoes", "topicos", "participantes"):
        assert campo in PROMPT_DO_SISTEMA


# --- a resposta que volta ----------------------------------------------------


def test_resposta_json_vira_resumo():
    resumo = interpretar_resposta(RESPOSTA_COMPLETA)

    assert resumo.decisoes == ("O rollback fica para depois do review.",)
    assert resumo.acoes == ("Ana faz o deploy depois do review.",)
    assert resumo.topicos == ("Rollback", "Deploy")
    assert resumo.participantes == ("Gabriel", "Ana")
    assert resumo.titulo == "daily do time"


def test_json_dentro_de_cerca_de_codigo_e_aceito():
    resumo = interpretar_resposta(f"```json\n{RESPOSTA_COMPLETA}\n```")

    assert resumo.decisoes == ("O rollback fica para depois do review.",)


def test_json_com_frase_em_volta_e_aceito():
    bruto = f"Claro, aqui está o resumo:\n{RESPOSTA_COMPLETA}\nEspero que ajude."

    assert interpretar_resposta(bruto).topicos == ("Rollback", "Deploy")


def test_campos_opcionais_ausentes_viram_vazio():
    resumo = interpretar_resposta('{"decisoes": [], "acoes": [], "topicos": ["Retro"]}')

    assert resumo.participantes == ()
    assert resumo.titulo is None
    assert resumo.decisoes == ()


def test_participantes_vazios_deixam_o_pipeline_cair_para_os_falantes():
    resumo = interpretar_resposta(
        '{"participantes": [], "titulo": null, "decisoes": ["x"], "acoes": [], "topicos": []}'
    )

    assert resumo.participantes == ()
    assert resumo.titulo is None


def test_itens_em_branco_sao_descartados():
    resumo = interpretar_resposta(
        '{"decisoes": ["  ", "Decidido.", ""], "acoes": [], "topicos": []}'
    )

    assert resumo.decisoes == ("Decidido.",)


def test_acao_devolvida_como_objeto_vira_frase():
    resumo = interpretar_resposta(
        '{"decisoes": [], "topicos": [],'
        ' "acoes": [{"acao": "Abrir a issue", "responsavel": "Ana"}]}'
    )

    assert resumo.acoes == ("Abrir a issue — Ana",)


def test_resposta_sem_json_levanta_erro_de_resumo():
    with pytest.raises(ErroDeResumo) as erro:
        interpretar_resposta("Desculpe, não consegui resumir esta reunião.")

    assert "não devolveu um objeto JSON" in str(erro.value)


def test_json_malformado_levanta_erro_de_resumo():
    with pytest.raises(ErroDeResumo) as erro:
        interpretar_resposta('{"decisoes": ["sem fechar"')

    assert "malformado" in str(erro.value)


def test_json_que_nao_e_objeto_levanta_erro_de_resumo():
    with pytest.raises(ErroDeResumo) as erro:
        interpretar_resposta('["decisao um", "decisao dois"]')

    assert "não é um objeto" in str(erro.value)


def test_json_sem_nenhuma_das_tres_listas_levanta_erro_de_resumo():
    with pytest.raises(ErroDeResumo) as erro:
        interpretar_resposta('{"resumo": "foi uma boa reunião"}')

    assert "sem 'decisoes'" in str(erro.value)


def test_resposta_crua_fica_no_log_para_diagnostico(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("ERROR", logger="whis.resumo"):
        with pytest.raises(ErroDeResumo):
            interpretar_resposta("não é json nenhum, é papo")

    assert "não é json nenhum, é papo" in caplog.text


def test_mensagem_de_erro_e_diagnosticavel_em_portugues():
    with pytest.raises(ErroDeResumo) as erro:
        interpretar_resposta("nada de json aqui")

    mensagem = str(erro.value)
    assert "nada de json aqui" in mensagem
    assert "log" in mensagem


# --- o adaptador inteiro -----------------------------------------------------


def test_resumir_devolve_o_resumo_traduzido():
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    resumo = adaptador.resumir(TRANSCRICAO, "daily do time")

    assert isinstance(resumo, Resumo)
    assert resumo.decisoes == ("O rollback fica para depois do review.",)
    assert "daily do time" in adaptador.perguntas[0]


def test_resumir_propaga_a_falha_de_parse():
    adaptador = ClaudeDeMentira("o modelo divagou")

    with pytest.raises(ErroDeResumo):
        adaptador.resumir(TRANSCRICAO)


def test_adaptador_atende_a_porta_de_resumo():
    assert isinstance(ResumoClaude(), PortaResumo)


def test_construtor_sem_argumentos_usa_o_modelo_da_conta():
    adaptador = ResumoClaude()

    assert adaptador.modelo is None


def test_modelo_pode_ser_fixado_na_construcao():
    assert ResumoClaude(modelo="claude-opus-5").modelo == "claude-opus-5"


def test_modelo_vazio_da_configuracao_vira_o_padrao_da_conta():
    assert ResumoClaude(modelo="").modelo is None


def test_transcricao_grande_demais_e_recusada_antes_da_chamada():
    enorme = Transcricao(falas=tuple(Fala(EU, "palavra " * 100) for _ in range(200)))
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA, limite_de_caracteres=1000)

    with pytest.raises(ErroDeResumo) as erro:
        adaptador.resumir(enorme)

    assert "grande demais" in str(erro.value)
    assert "preservada" in str(erro.value)
    assert adaptador.perguntas == [], "a chamada não deveria ter saído"


# --- a credencial ------------------------------------------------------------


@pytest.mark.parametrize("variavel", VARIAVEIS_DE_API_PAGA)
def test_api_key_paga_no_ambiente_recusa_a_chamada(
    variavel: str, monkeypatch: pytest.MonkeyPatch
):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv(variavel, "chave-paga-de-teste")

    with pytest.raises(ErroDeResumo) as erro:
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


# --- a única conversa de verdade ---------------------------------------------


#: Ligar esta variável é o que faz o teste de rede rodar.
#:
#: O marcador `rede` sozinho não segura nada: o `addopts` do `pyproject.toml`
#: é só `-q`, sem `-m "not rede"`, então um teste marcado roda na suíte
#: normal. Enquanto o `addopts` não desselecionar o marcador, o gate é este.
VARIAVEL_DE_OPT_IN = "WHIS_TESTES_DE_REDE"


def _ha_credencial_do_claude() -> bool:
    """Há uma conta Claude logada nesta máquina, sem API key paga por perto?"""
    if any(os.environ.get(nome) for nome in VARIAVEIS_DE_API_PAGA):
        return False
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    return (Path.home() / ".claude" / ".credentials.json").is_file()


def _motivo_para_pular() -> str:
    if not os.environ.get(VARIAVEL_DE_OPT_IN):
        return f"teste de rede: ligue {VARIAVEL_DE_OPT_IN}=1 para rodar"
    if not _ha_credencial_do_claude():
        return "sem conta Claude logada nesta máquina (rode `claude login`)"
    return ""


@pytest.mark.rede
@pytest.mark.skipif(bool(_motivo_para_pular()), reason=_motivo_para_pular() or "roda")
def test_resumo_real_do_claude_em_portugues():
    """Fala com o Claude de verdade, pela conta do usuário. Não roda por padrão."""
    transcricao = Transcricao(
        falas=(
            Fala(EU, "Bom dia. A gente sobe o deploy hoje ou espera o review?", 0.0),
            Fala(
                OUTROS,
                "Aqui é a Ana. Melhor esperar o review; eu abro a issue do rollback hoje.",
                5.0,
            ),
            Fala(EU, "Fechado, fica decidido assim então.", 12.0),
        ),
    )

    resumo = ResumoClaude(timeout_s=180.0).resumir(transcricao, "daily do time")

    assert resumo.decisoes or resumo.acoes or resumo.topicos, "o resumo veio vazio"
    texto = " ".join(resumo.decisoes + resumo.acoes + resumo.topicos)
    assert texto.strip()
