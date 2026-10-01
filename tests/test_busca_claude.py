"""O adaptador da busca: da pergunta montada até `Resposta`, sem tocar a rede.

Os testes exercitam as três metades do adaptador separadamente — o que sai
(prompt e fio), o que o modelo tem na mão (as ferramentas do vault como tools
do SDK, com as recusas traduzidas) e o que volta (a tradução da resposta). A
única parte que fala com o Claude de verdade é `_conversar`, substituída aqui
e coberta pelo teste marcado `rede`, que só roda quando o usuário pede.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from fixtures.busca import (
    CONTEUDO_PRIVADO,
    NOTA_PRIVADA,
    NOTA_PUBLICA,
    PASTA_PRIVADA,
    configuracao_da_busca,
    habitar_vault,
)
from whis.busca import Citacao, ErroDeBusca, PortaBusca
from whis.busca_claude import (
    BUSCAR,
    LER,
    LISTAR,
    PROMPT_DA_BUSCA,
    BuscaClaude,
    FerramentasDoVault,
    ferramentas_permitidas,
    interpretar_resposta,
    montar_pergunta,
    registrar_custo,
    verificar_credencial,
)
from whis.conversa import AGENTE, USUARIO, Turno
from whis.ferramentas import Ferramentas
from whis.claude_cli import VARIAVEIS_DE_API_PAGA

FUSO = timezone(timedelta(hours=-3))
MANHA = datetime(2026, 9, 4, 9, 0, tzinfo=FUSO)

RESPOSTA_COMPLETA = json.dumps(
    {
        "resposta": "A retenção ficou em 180 dias, decidida com o Luan em 04/09.",
        "citacoes": [
            {"origem": "daily/2026-09-04.md", "trecho": "Retenção de 180 dias ficou decidida com o Luan."}
        ],
        "achou": True,
    },
    ensure_ascii=False,
)

NAO_ACHOU = json.dumps(
    {"resposta": "Não achei nada sobre o link coringa no vault.", "citacoes": [], "achou": False},
    ensure_ascii=False,
)


def _resultado(**extras) -> ResultMessage:
    campos = {
        "subtype": "success",
        "duration_ms": 12400,
        "duration_api_ms": 11000,
        "is_error": False,
        "num_turns": 5,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.0912,
        "usage": {"input_tokens": 3100, "output_tokens": 420, "cache_read_input_tokens": 900},
    }
    return ResultMessage(**{**campos, **extras})


class ClaudeDeMentira(BuscaClaude):
    """`BuscaClaude` com a rede trocada por uma resposta fixa.

    `usar_ferramentas` faz o double se comportar como o modelo se comportaria:
    busca, abre a nota e só então responde — pelo mesmo caminho que o SDK usa.
    """

    def __init__(self, resposta: str, *, resultado=None, usar_ferramentas=False, **extras) -> None:
        super().__init__(**extras)
        self.resposta = resposta
        self.resultado = resultado
        self.usar_ferramentas = usar_ferramentas
        self.prompts: list[str] = []
        self.textos_das_ferramentas: list[str] = []

    def _conversar(self, prompt: str, ferramentas: Ferramentas):
        self.prompts.append(prompt)
        if self.usar_ferramentas:
            vault = FerramentasDoVault(ferramentas)
            buscar, ler, _ = vault.tools()
            self.textos_das_ferramentas.append(chamar(buscar, {"termo": "retenção 180"}))
            self.textos_das_ferramentas.append(chamar(ler, {"caminho": NOTA_PUBLICA}))
            self.textos_das_ferramentas.append(chamar(ler, {"caminho": NOTA_PRIVADA}))
        return self.resposta, self.resultado


def chamar(ferramenta, args: dict) -> str:
    """Chama o handler de uma tool como o SDK chamaria, e devolve o texto."""
    return resultado_de(ferramenta, args)["content"][0]["text"]


def resultado_de(ferramenta, args: dict) -> dict:
    return asyncio.run(ferramenta.handler(args))


@pytest.fixture
def ferramentas(tmp_path: Path, caminho_do_vault: Path) -> Ferramentas:
    habitar_vault(caminho_do_vault)
    return Ferramentas(
        configuracao_da_busca(
            tmp_path, caminho_do_vault, pastas_privadas=(PASTA_PRIVADA,)
        )
    )


@pytest.fixture
def vault(ferramentas: Ferramentas) -> FerramentasDoVault:
    return FerramentasDoVault(ferramentas)


# --- o que sai ---------------------------------------------------------------


def test_prompt_manda_buscar_antes_citar_e_dizer_que_nao_achou():
    assert "Busque ANTES de responder" in PROMPT_DA_BUSCA
    assert "Cada afirmação precisa de uma citação" in PROMPT_DA_BUSCA
    assert '"achou": false' in PROMPT_DA_BUSCA
    assert "NUNCA complete com" in PROMPT_DA_BUSCA


def test_prompt_pede_json_em_portugues_com_os_tres_campos():
    assert "português do Brasil" in PROMPT_DA_BUSCA
    for campo in ("resposta", "citacoes", "achou", "origem", "trecho"):
        assert f'"{campo}"' in PROMPT_DA_BUSCA


def test_prompt_diz_que_caminho_inexistente_nao_existe_e_nao_e_segredo():
    assert 'Um caminho que "não existe" não existe' in PROMPT_DA_BUSCA
    assert "não especule que algo esteja escondido" in PROMPT_DA_BUSCA
    assert "privad" not in PROMPT_DA_BUSCA.lower()


def test_prompt_explica_as_pastas_do_vault_e_as_tres_ferramentas():
    for pasta in ("daily/", "diario/", "reunioes/", "transcricoes/", "notas/"):
        assert pasta in PROMPT_DA_BUSCA
    for ferramenta in (BUSCAR, LER, LISTAR):
        assert f"`{ferramenta}(" in PROMPT_DA_BUSCA


def test_pergunta_sem_fio_leva_so_a_pergunta():
    prompt = montar_pergunta("o que ficou decidido sobre a retenção?")

    assert "Pergunta de agora:" in prompt
    assert "o que ficou decidido sobre a retenção?" in prompt
    assert "Conversa até aqui" not in prompt


def test_pergunta_com_fio_leva_os_turnos_antes_da_pergunta():
    fio = (
        Turno(USUARIO, "o que ficou decidido sobre a retenção?", MANHA),
        Turno(AGENTE, "180 dias, na reunião de 03/09.", MANHA),
    )

    prompt = montar_pergunta("e quem levantou isso?", fio)

    assert "Conversa até aqui" in prompt
    assert "[usuário] o que ficou decidido sobre a retenção?" in prompt
    assert "[agente] 180 dias, na reunião de 03/09." in prompt
    assert prompt.index("[agente]") < prompt.index("Pergunta de agora:")
    assert prompt.rstrip().endswith("e quem levantou isso?")


def test_fio_longo_vai_cortado_aos_turnos_mais_recentes():
    fio = tuple(Turno(USUARIO, f"pergunta {numero}", MANHA) for numero in range(60))

    prompt = montar_pergunta("a última", fio)

    assert "pergunta 59" in prompt
    assert "pergunta 0\n" not in prompt


# --- o que o modelo tem na mão -----------------------------------------------


def test_os_nomes_permitidos_sao_os_do_servidor_mcp_em_processo(vault: FerramentasDoVault):
    nomes = [ferramenta.name for ferramenta in vault.tools()]

    assert nomes == [BUSCAR, LER, LISTAR]
    assert ferramentas_permitidas() == [f"mcp__vault__{nome}" for nome in nomes]


def test_buscar_devolve_caminho_linha_e_trecho(vault: FerramentasDoVault):
    buscar, _, _ = vault.tools()

    texto = chamar(buscar, {"termo": "retenção 180"})

    assert f"{NOTA_PUBLICA}:3: Retenção de 180 dias ficou decidida com o Luan." in texto
    assert NOTA_PRIVADA not in texto
    assert CONTEUDO_PRIVADO not in texto
    assert NOTA_PUBLICA in vault.vistos


def test_buscar_sem_achado_ensina_a_tentar_outro_termo(vault: FerramentasDoVault):
    buscar, _, _ = vault.tools()

    resultado = resultado_de(buscar, {"termo": "assunto inexistente"})

    assert "Nenhuma linha" in resultado["content"][0]["text"]
    assert "outra grafia" in resultado["content"][0]["text"]
    assert not resultado.get("is_error")


def test_buscar_respeita_o_limite_pedido(vault: FerramentasDoVault):
    buscar, _, _ = vault.tools()

    texto = chamar(buscar, {"termo": "retenção 180", "limite": 1})

    assert texto.startswith("1 linha(s)")


def test_ler_devolve_a_nota_com_o_caminho_na_frente(vault: FerramentasDoVault):
    _, ler, _ = vault.tools()

    texto = chamar(ler, {"caminho": NOTA_PUBLICA})

    assert texto.startswith(f"[{NOTA_PUBLICA}]\n")
    assert "Retenção de 180 dias ficou decidida" in texto
    assert NOTA_PUBLICA in vault.vistos


@pytest.mark.parametrize(
    "caminho", [NOTA_PRIVADA, "reunioes/../notas/pessoal/terapia.md", "../fora.md", "notas/inventada.md"]
)
def test_ler_recusado_diz_ao_modelo_que_nao_existe(vault: FerramentasDoVault, caminho: str):
    _, ler, _ = vault.tools()

    resultado = resultado_de(ler, {"caminho": caminho})

    texto = resultado["content"][0]["text"]
    assert resultado["is_error"] is True
    assert texto == f"Não existe no vault: {caminho!r}"
    assert "privad" not in texto.lower()
    assert CONTEUDO_PRIVADO not in texto
    assert caminho not in vault.vistos


def test_ler_alem_do_teto_manda_responder_com_o_que_ja_leu(
    tmp_path: Path, caminho_do_vault: Path
):
    habitar_vault(caminho_do_vault)
    ferramentas = Ferramentas(
        configuracao_da_busca(tmp_path, caminho_do_vault, maximo_de_notas=1)
    )
    _, ler, _ = FerramentasDoVault(ferramentas).tools()
    chamar(ler, {"caminho": NOTA_PUBLICA})

    resultado = resultado_de(ler, {"caminho": "daily/2026-09-01.md"})

    assert resultado["is_error"] is True
    assert "Responda com o que já leu" in resultado["content"][0]["text"]


def test_listar_a_raiz_e_uma_pasta(vault: FerramentasDoVault):
    _, _, listar = vault.tools()

    raiz = chamar(listar, {})
    notas = chamar(listar, {"pasta": "notas"})

    assert "daily/" in raiz.splitlines()
    assert f"{PASTA_PRIVADA}/" not in raiz
    assert notas.splitlines() == ["notas/ideias.md", "notas/pessoal-trabalho.md"]


def test_listar_a_pasta_privada_diz_que_nao_existe(vault: FerramentasDoVault):
    _, _, listar = vault.tools()

    resultado = resultado_de(listar, {"pasta": PASTA_PRIVADA})

    assert resultado["is_error"] is True
    assert "Não existe" in resultado["content"][0]["text"]


def test_as_chamadas_sao_contadas(vault: FerramentasDoVault):
    buscar, ler, listar = vault.tools()

    chamar(buscar, {"termo": "retenção"})
    chamar(ler, {"caminho": NOTA_PUBLICA})
    chamar(listar, {})

    assert vault.chamadas == 3


# --- o que volta ---------------------------------------------------------------


def test_resposta_json_vira_resposta_com_citacoes():
    resposta = interpretar_resposta(RESPOSTA_COMPLETA)

    assert resposta.achou
    assert "180 dias" in resposta.texto
    assert resposta.citacoes == (
        Citacao("daily/2026-09-04.md", "Retenção de 180 dias ficou decidida com o Luan."),
    )


def test_nao_achei_e_resposta_valida():
    resposta = interpretar_resposta(NAO_ACHOU)

    assert resposta.achou is False
    assert resposta.citacoes == ()
    assert "Não achei" in resposta.texto


def test_json_dentro_de_cerca_ou_com_frase_em_volta_e_aceito():
    assert interpretar_resposta(f"```json\n{RESPOSTA_COMPLETA}\n```").achou
    assert interpretar_resposta(f"Aqui está:\n{RESPOSTA_COMPLETA}\nQualquer coisa, pergunte.").achou


def test_citacao_como_texto_simples_vira_origem():
    resposta = interpretar_resposta('{"resposta": "x", "citacoes": ["diario/2026-09-03.md"]}')

    assert resposta.citacoes == (Citacao("diario/2026-09-03.md"),)


def test_citacao_com_outro_nome_de_campo_e_barra_invertida_e_normalizada():
    resposta = interpretar_resposta(
        '{"resposta": "x", "citacoes": [{"arquivo": "daily\\\\2026-09-04.md", "trecho": "t"}]}'
    )

    assert resposta.citacoes == (Citacao("daily/2026-09-04.md", "t"),)


def test_achou_ausente_e_deduzido_das_citacoes():
    assert interpretar_resposta('{"resposta": "x", "citacoes": ["a.md"]}').achou is True
    assert interpretar_resposta('{"resposta": "não sei", "citacoes": []}').achou is False


def test_resposta_sem_citacao_e_registrada_como_suspeita(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("WARNING", logger="whis.busca"):
        resposta = interpretar_resposta('{"resposta": "foi decidido", "achou": true}')

    assert resposta.citacoes == ()
    assert "sem citação" in caplog.text


@pytest.mark.parametrize(
    ("bruto", "motivo"),
    [
        ("Desculpe, não consegui responder.", "não devolveu um objeto JSON"),
        ('{"resposta": "sem fechar', "malformado"),
        ('["a", "b"]', "não é um objeto"),
        ('{"narrativa": "x"}', "sem 'resposta'"),
    ],
)
def test_resposta_ilegivel_vira_erro_de_busca_com_o_texto_no_log(
    bruto: str, motivo: str, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level("ERROR", logger="whis.busca"):
        with pytest.raises(ErroDeBusca) as erro:
            interpretar_resposta(bruto)

    assert motivo in str(erro.value)
    assert bruto[:20] in caplog.text


# --- o adaptador inteiro ------------------------------------------------------


def test_adaptador_atende_a_porta():
    assert isinstance(BuscaClaude(), PortaBusca)


def test_perguntar_devolve_a_resposta_traduzida_com_o_custo(ferramentas: Ferramentas):
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA, resultado=_resultado())

    resposta = adaptador.perguntar("o que ficou decidido sobre a retenção?", ferramentas)

    assert resposta.achou
    assert resposta.citacoes[0].origem == "daily/2026-09-04.md"
    assert resposta.custo_usd == 0.0912
    assert "o que ficou decidido sobre a retenção?" in adaptador.prompts[0]


def test_perguntar_leva_o_fio_junto(ferramentas: Ferramentas):
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)
    fio = (Turno(USUARIO, "sobre a retenção", MANHA), Turno(AGENTE, "180 dias", MANHA))

    adaptador.perguntar("e quem levantou isso?", ferramentas, historico=fio)

    assert "[usuário] sobre a retenção" in adaptador.prompts[0]
    assert "[agente] 180 dias" in adaptador.prompts[0]


def test_o_modelo_que_procura_ve_a_publica_e_nao_a_privada(ferramentas: Ferramentas):
    """O double faz o que o modelo faria, pelas mesmas tools — e a fronteira vale ali."""
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA, usar_ferramentas=True)

    resposta = adaptador.perguntar("o que ficou decidido sobre a retenção?", ferramentas)

    busca, publica, privada = adaptador.textos_das_ferramentas
    assert NOTA_PUBLICA in busca and NOTA_PRIVADA not in busca
    assert "ficou decidida com o Luan" in publica
    assert privada == f"Não existe no vault: {NOTA_PRIVADA!r}"
    assert resposta.citacoes[0].origem == NOTA_PUBLICA


def test_sem_resultado_o_custo_fica_vazio(ferramentas: Ferramentas):
    resposta = ClaudeDeMentira(NAO_ACHOU).perguntar("link coringa?", ferramentas)

    assert resposta.custo_usd is None
    assert resposta.achou is False


def test_resposta_ilegivel_sobe_como_erro_de_busca(ferramentas: Ferramentas):
    with pytest.raises(ErroDeBusca):
        ClaudeDeMentira("o modelo divagou").perguntar("?", ferramentas)


def test_modelo_vazio_vira_o_padrao_da_conta():
    assert BuscaClaude(modelo="").modelo is None
    assert BuscaClaude(modelo="claude-opus-5").modelo == "claude-opus-5"


# --- a credencial -------------------------------------------------------------


@pytest.mark.parametrize("variavel", VARIAVEIS_DE_API_PAGA)
def test_api_key_paga_no_ambiente_recusa_a_busca(variavel: str, monkeypatch: pytest.MonkeyPatch):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv(variavel, "chave-paga-de-teste")

    with pytest.raises(ErroDeBusca) as erro:
        verificar_credencial()

    assert variavel in str(erro.value)
    assert "claude login" in str(erro.value)
    assert "chave-paga-de-teste" not in str(erro.value)


def test_adaptador_recusa_antes_de_falar_com_o_claude(
    ferramentas: Ferramentas, monkeypatch: pytest.MonkeyPatch
):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-paga-de-teste")
    adaptador = ClaudeDeMentira(RESPOSTA_COMPLETA)

    with pytest.raises(ErroDeBusca) as erro:
        adaptador.perguntar("?", ferramentas)

    assert "OAuth" in str(erro.value)
    assert adaptador.prompts == []


def test_ambiente_limpo_deixa_a_busca_seguir(monkeypatch: pytest.MonkeyPatch):
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)

    verificar_credencial()


# --- o custo -----------------------------------------------------------------


def test_custo_da_pergunta_fica_no_log_com_as_chamadas(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="whis.busca"):
        registrar_custo(_resultado(), chamadas=4)

    assert "US$ 0.0912" in caplog.text
    assert "4 chamada(s) de ferramenta" in caplog.text
    assert "assinatura não cobra por token" in caplog.text


def test_turno_sem_resultado_nao_registra_custo(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="whis.busca"):
        registrar_custo(None, chamadas=0)

    assert caplog.text == ""


# --- a única conversa de verdade ---------------------------------------------


def _ha_credencial_do_claude() -> bool:
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
def test_busca_real_cita_a_nota_e_nao_ve_a_privada(ferramentas: Ferramentas):
    """Fala com o Claude de verdade, pela conta do usuário. Gasta a assinatura."""
    resposta = BuscaClaude(timeout_s=180.0).perguntar(
        "o que ficou decidido sobre a retenção de 180 dias, e com quem?", ferramentas
    )

    assert resposta.achou, resposta
    assert any(citacao.origem == NOTA_PUBLICA for citacao in resposta.citacoes), resposta
    assert all(not citacao.origem.startswith(PASTA_PRIVADA + "/") for citacao in resposta.citacoes)
    assert "terapia" not in resposta.texto.lower()
