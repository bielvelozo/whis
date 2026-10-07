"""A leitura do banco da página, com os resultados reais que a sonda guardou."""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage

from whis.claude_cli import VARIAVEIS_DE_API_PAGA
from whis.marcacoes_claude import (
    MarcacoesClaude,
    interpretar_resultado,
    juntar_paginas,
    leituras_de,
    pedido_de_leitura,
    respostas_de,
)
from whis.portas import ErroDeMarcacoes, Marcacoes, Resposta

FIXTURES = Path(__file__).parent / "fixtures" / "jornal" / "marcacoes"
URL = "https://claude.ai/artifact/AYhYVZDhevQdWv4YaNuoge"


def fixture(nome: str) -> str:
    return (FIXTURES / nome).read_bytes().decode("utf-8")


def _resultado(**extras) -> ResultMessage:
    campos = {
        "subtype": "success",
        "duration_ms": 8000,
        "duration_api_ms": 7000,
        "is_error": False,
        "num_turns": 3,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.0107,
        "usage": {"input_tokens": 9, "output_tokens": 40},
        "result": "OK",
    }
    return ResultMessage(**{**campos, **extras})


def _chamada(texto: str, id: str) -> list:
    return [
        AssistantMessage(content=[ToolUseBlock(id=id, name="ArtifactData", input={})], model="claude-haiku-4-5-20251001"),
        UserMessage(content=[ToolResultBlock(tool_use_id=id, content=texto)]),
    ]


class MarcacoesGravada(MarcacoesClaude):
    def __init__(self, resultados: list[str], **extras) -> None:
        super().__init__(**extras)
        self.mensagens = [m for i, texto in enumerate(resultados) for m in _chamada(texto, f"t{i}")]
        self.mensagens += [AssistantMessage(content=[TextBlock(text="OK")], model="claude-haiku-4-5-20251001"), _resultado()]
        self.prompts: list[str] = []
        self.opcoes: list = []

    async def _mensagens(self, prompt, opcoes):
        self.prompts.append(prompt)
        self.opcoes.append(opcoes)
        for mensagem in self.mensagens:
            yield mensagem


@pytest.fixture(autouse=True)
def _sem_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)


def test_tres_leituras_reais_viram_documentos_sem_cursor():
    pagina = interpretar_resultado(fixture("leituras-tres.txt"))

    assert pagina.colecao == "leituras" and pagina.cursor is None
    assert [d["id"] for d in pagina.documentos] == ["2026-10-06-carros-1", "2026-10-06-carros-2", "2026-10-06-negocios"]


def test_so_a_aula_marcada_como_lida_conta():
    documentos = interpretar_resultado(fixture("leituras-tres.txt")).documentos

    assert leituras_de(documentos) == {
        "2026-10-06-carros-1": "2026-10-07T01:11:00.000Z",
        "2026-10-06-negocios": "2026-10-07T01:10:00.000Z",
    }


def test_respostas_reais_viram_resposta():
    documentos = interpretar_resultado(fixture("respostas-duas.txt")).documentos

    assert respostas_de(documentos) == {"2026-10-10-q1": Resposta(1, False), "2026-10-10-q2": Resposta(0, True)}


def test_resposta_com_formato_estranho_e_ignorada():
    assert respostas_de([{"id": "x", "data": {"escolha": "1", "certa": True}}]) == {}


def test_pagina_com_cursor_e_a_ultima_pagina():
    primeira = interpretar_resultado(fixture("leituras-com-cursor.txt"))
    ultima = interpretar_resultado(fixture("leituras-ultima-pagina.txt"))

    assert primeira.cursor and primeira.cursor.startswith("Jh6yPzoF") and len(primeira.documentos) == 2
    assert ultima.cursor is None
    juntas = juntar_paginas([primeira, ultima], ["leituras"])
    assert len(juntas["leituras"]) == 3


def test_pagina_seguinte_nao_lida_e_erro():
    with pytest.raises(ErroDeMarcacoes, match="página seguinte"):
        juntar_paginas([interpretar_resultado(fixture("leituras-com-cursor.txt"))], ["leituras"])


def test_colecao_nunca_escrita_e_banco_nao_declarado_sao_vazios():
    vazia = interpretar_resultado(fixture("colecao-vazia.txt"))
    sem_banco = interpretar_resultado(fixture("antes-de-declarar.txt"))

    assert juntar_paginas([vazia], ["leituras"]) == {"leituras": []}
    assert juntar_paginas([sem_banco], ["leituras", "respostas"]) == {"leituras": [], "respostas": []}


def test_consulta_que_nao_acha_nada_e_vazia_nao_erro():
    sem_resultado = interpretar_resultado(fixture("consulta-sem-resultado.txt"))
    nunca_escrita = interpretar_resultado(fixture("consulta-colecao-nunca-escrita.txt"))

    assert juntar_paginas([sem_resultado], ["leituras"]) == {"leituras": []}
    assert nunca_escrita.colecao == "nada" and nunca_escrita.documentos == ()


def test_permissao_negada_ou_texto_estranho_e_erro():
    for texto in (fixture("negado.txt"), "Não consegui.", ""):
        with pytest.raises(ErroDeMarcacoes, match="fora do formato"):
            interpretar_resultado(texto)


def test_colecao_pedida_sem_resultado_e_erro():
    with pytest.raises(ErroDeMarcacoes, match="respostas"):
        juntar_paginas([interpretar_resultado(fixture("leituras-tres.txt"))], ["leituras", "respostas"])


def test_o_pedido_filtra_so_o_que_interessa():
    pedido = pedido_de_leitura(URL, leituras_desde="2026-10-05", quizzes=["2026-10-10"])

    assert '"where": [["em", ">=", "2026-10-05"]]' in pedido
    assert '"where": [["quiz", "in", ["2026-10-10"]]]' in pedido
    assert "next_cursor" in pedido and "out_dir" in pedido and URL in pedido


def test_nada_a_ler_nem_chama_o_claude():
    leitor = MarcacoesGravada([])

    assert leitor.ler(URL, leituras_desde=None, quizzes=[]) == Marcacoes()
    assert leitor.prompts == []


def test_a_leitura_le_os_resultados_da_ferramenta_e_ignora_o_texto_do_modelo():
    leitor = MarcacoesGravada([fixture("consulta-leituras.txt"), fixture("respostas-duas.txt")])

    marcacoes = leitor.ler(URL, leituras_desde="2026-10-07", quizzes=["2026-10-10"])

    assert marcacoes.leituras == {"2026-10-06-carros-1": "2026-10-07T01:11:00.000Z"}
    assert marcacoes.respostas["2026-10-10-q1"] == Resposta(1, False)
    assert marcacoes.medida.custo_usd == pytest.approx(0.0107)


def test_a_leitura_usa_haiku_com_artifact_e_artifact_data():
    leitor = MarcacoesGravada([fixture("consulta-leituras.txt")])

    leitor.ler(URL, leituras_desde="2026-10-07", quizzes=[])

    opcoes = leitor.opcoes[0]
    assert opcoes.model == "haiku"
    assert opcoes.tools == ["Artifact", "ArtifactData"] and opcoes.allowed_tools == ["Artifact", "ArtifactData"]
    assert opcoes.permission_mode == "dontAsk"
    assert opcoes.env["CLAUDE_CODE_ARTIFACT"] == "1"


def test_sessao_que_nao_leu_nada_e_erro():
    leitor = MarcacoesGravada([])

    with pytest.raises(ErroDeMarcacoes, match="leituras"):
        leitor.ler(URL, leituras_desde="2026-10-07", quizzes=[])
