"""Comportamento do coletor do Linear, sem rede.

As respostas vêm de fixtures JSON no formato que a API GraphQL devolve —
`{"data": {"issues": {"pageInfo": ..., "nodes": [...]}}}` —, montadas a partir
do schema público do Linear
(https://github.com/linear/linear/blob/master/packages/sdk/src/schema.graphql),
com os campos que a consulta pede: `identifier`, `title`, `url`, `createdAt`,
`updatedAt`, `state`, `team`, `project`, `creator`, `assignee` e o `history`
com `fromState`/`toState`/`actor`.

O HTTP é interceptado com `httpx.MockTransport`, então o código que monta a
requisição (URL, cabeçalhos, consulta e variáveis) é exatamente o de produção.

A janela dos testes é declarada em **UTC** de propósito: assim as fixtures
caem sempre no mesmo lugar dela, rode a suíte na máquina que rodar. A conversão
para o fuso local — que o contrato exige de `momento` — tem teste próprio.

Nenhuma fixture contém chave: a chave dos testes é `lin_api_EXEMPLO`.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from whis.__main__ import montar_fontes
from whis.configuracao import Configuracao, ConfiguracaoInvalida, carregar
from whis.fontes import ErroDeFonte, Evento, Janela, janela_do_dia
from whis.fonte_linear import (
    CONSULTA_DE_COMENTARIOS,
    CONSULTA_DE_ISSUES,
    ENDPOINT,
    HISTORICO_POR_ISSUE,
    TAMANHO_DA_PAGINA,
    FonteLinear,
    de_configuracao,
)

CHAVE_FALSA = "lin_api_EXEMPLO"
FIXTURES = Path(__file__).parent / "fixtures"

#: A janela dos testes: 3 de setembro de 2026, das 04:00 de Brasília às 04:00
#: do dia seguinte, escrita em UTC para não depender do relógio da máquina.
JANELA = Janela(
    data=date(2026, 9, 3),
    inicio=datetime(2026, 9, 3, 7, 0, tzinfo=UTC),
    fim=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
)

FIM_DA_PAGINACAO = {"hasNextPage": False, "endCursor": None}
PAGINA_VAZIA = {
    "issues": {"data": {"issues": {"pageInfo": FIM_DA_PAGINACAO, "nodes": []}}},
    "comentarios": {"data": {"comments": {"pageInfo": FIM_DA_PAGINACAO, "nodes": []}}},
}

#: Os títulos que as fixtures produzem — é por eles que a nota é lida.
MOVIDA = "FN-123 Corrigir o cálculo de frete — movida de In Progress para Done"
COMENTADA = "FN-123 Corrigir o cálculo de frete — comentário de Ana Prado"
CRIADA = "FN-124 Escrever o roteiro de smoke do Linear — criada"
ATUALIZADA = "FN-125 Revisar o contrato de fonte passiva — atualizada (em In Review)"
MOVIDA_SEM_ORIGEM = "FN-130 Ajustar o rate limit do coletor — movida para In Progress"
COMENTADA_NO_PROJETO = "Fontes passivas — comentário de Gabriel Velozo"


def carregar_fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def fonte(
    respostas: dict | None = None,
    *,
    registro: list[httpx.Request] | None = None,
    chave: str = CHAVE_FALSA,
    **extras,
) -> FonteLinear:
    """Coletor com transporte falso.

    `respostas` mapeia `"issues"` e `"comentarios"` ao que responder àquela
    consulta: um dicionário, uma lista de páginas na ordem das chamadas, um
    `httpx.Response` ou um callable. Consulta sem resposta declarada volta
    vazia — é assim que um teste de issues não precisa inventar comentários.
    """
    filas = {
        alvo: list(valor) if isinstance(valor, list) else [valor]
        for alvo, valor in (respostas or {}).items()
    }

    def responder(requisicao: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(requisicao)
        corpo = json.loads(requisicao.content)
        alvo = "issues" if "DiarioIssues" in corpo["query"] else "comentarios"
        fila = filas.get(alvo) or [PAGINA_VAZIA[alvo]]
        atual = fila.pop(0) if len(fila) > 1 else fila[0]
        if callable(atual):
            return atual(requisicao)
        if isinstance(atual, httpx.Response):
            return atual
        return httpx.Response(200, json=atual)

    return FonteLinear(
        chave,
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
        **extras,
    )


def fonte_do_dia_cheio(registro: list[httpx.Request] | None = None) -> FonteLinear:
    """O dia completo das fixtures: duas páginas de issues e os comentários."""
    return fonte(
        {
            "issues": [
                carregar_fixture("resposta_linear_issues.json"),
                carregar_fixture("resposta_linear_issues_pagina_2.json"),
            ],
            "comentarios": carregar_fixture("resposta_linear_comentarios.json"),
        },
        registro=registro,
    )


def coletar_o_dia_cheio() -> dict[str, Evento]:
    """Os eventos do dia cheio, indexados pelo título — o que a nota mostra."""
    return {evento.titulo: evento for evento in fonte_do_dia_cheio().coletar(JANELA)}


def variaveis(requisicao: httpx.Request) -> dict:
    return json.loads(requisicao.content)["variables"]


def requisicoes_de(registro: list[httpx.Request], consulta: str) -> list[httpx.Request]:
    """As requisições do registro que carregam aquela consulta nomeada."""
    return [r for r in registro if consulta in r.content.decode("utf-8")]


# -- A requisição -----------------------------------------------------------


def test_consulta_o_endpoint_graphql_do_linear_por_post():
    registro: list[httpx.Request] = []

    fonte_do_dia_cheio(registro).coletar(JANELA)

    assert registro, "alguma requisição foi feita"
    for requisicao in registro:
        assert requisicao.method == "POST"
        assert str(requisicao.url) == ENDPOINT == "https://api.linear.app/graphql"


def test_autentica_com_a_chave_crua_sem_o_prefixo_bearer():
    registro: list[httpx.Request] = []

    fonte_do_dia_cheio(registro).coletar(JANELA)

    cabecalho = registro[0].headers["authorization"]
    assert cabecalho == CHAVE_FALSA
    assert "Bearer" not in cabecalho, "Bearer é do OAuth; a Personal API Key vai crua"


def test_recorta_pelos_dois_lados_da_janela_em_utc():
    registro: list[httpx.Request] = []

    fonte_do_dia_cheio(registro).coletar(JANELA)

    enviadas = variaveis(registro[0])
    assert enviadas["inicio"] == "2026-09-03T07:00:00Z"
    assert enviadas["fim"] == "2026-09-04T07:00:00Z"


def test_o_fim_da_janela_vai_junto_para_o_diario_de_uma_data_passada():
    # Sem o `fim`, gerar o diário de uma segunda-feira traria o trabalho da
    # semana inteira.
    registro: list[httpx.Request] = []
    janela = janela_do_dia(date(2026, 8, 17), "04:00")

    fonte_do_dia_cheio(registro).coletar(janela)

    enviadas = variaveis(registro[0])
    assert enviadas["inicio"] == janela.inicio.astimezone(UTC).isoformat().replace(
        "+00:00", "Z"
    )
    assert enviadas["fim"] == janela.fim.astimezone(UTC).isoformat().replace(
        "+00:00", "Z"
    )


def test_a_consulta_de_issues_filtra_por_updated_at_e_pede_a_pagina_seguinte():
    assert "updatedAt: { gte: $inicio, lt: $fim }" in CONSULTA_DE_ISSUES
    assert "pageInfo { hasNextPage endCursor }" in CONSULTA_DE_ISSUES
    assert "first: $pagina" in CONSULTA_DE_ISSUES
    assert "after: $cursor" in CONSULTA_DE_ISSUES


def test_a_consulta_pede_o_fim_da_trilha_de_atividade_e_nao_o_comeco():
    # `first` traria a criação da issue, de meses atrás; `last` traz o que
    # mudou hoje, que é o que o diário registra.
    assert "history(last: $historico)" in CONSULTA_DE_ISSUES


def test_a_consulta_de_comentarios_filtra_pela_hora_em_que_foram_escritos():
    # `createdAt`, não `updatedAt`: um comentário editado hoje aconteceu no dia
    # em que foi escrito, e o contrato proíbe devolver evento fora da janela.
    assert "createdAt: { gte: $inicio, lt: $fim }" in CONSULTA_DE_COMENTARIOS


def test_manda_o_tamanho_de_pagina_e_o_historico_configurados():
    registro: list[httpx.Request] = []

    fonte_do_dia_cheio(registro).coletar(JANELA)

    enviadas = variaveis(registro[0])
    assert enviadas["pagina"] == TAMANHO_DA_PAGINA == 50
    assert enviadas["historico"] == HISTORICO_POR_ISSUE
    assert enviadas["cursor"] is None, "a primeira página não tem cursor"


# -- A tradução para Evento -------------------------------------------------


def test_mudanca_de_estado_vira_um_evento_legivel_sozinho():
    eventos = coletar_o_dia_cheio()

    movida = eventos[MOVIDA]
    assert movida.fonte == "linear"
    assert movida.momento == datetime(2026, 9, 3, 14, 20, tzinfo=UTC)
    assert movida.referencia == "Frete v2"
    assert movida.url == (
        "https://linear.app/segundo-cerebro/issue/FN-123/corrigir-o-calculo-de-frete"
    )
    assert movida.pessoas == ("Ana Prado",), "quem agiu foi o ator da mudança"


def test_mudanca_sem_estado_de_origem_diz_so_para_onde_foi():
    eventos = coletar_o_dia_cheio()

    movida = eventos[MOVIDA_SEM_ORIGEM]
    assert movida.momento == datetime(2026, 9, 3, 20, 5, tzinfo=UTC)
    assert movida.pessoas == ("Bruno Lima",)


def test_issue_aberta_na_janela_vira_evento_de_criacao():
    eventos = coletar_o_dia_cheio()

    criada = eventos[CRIADA]
    assert criada.momento == datetime(2026, 9, 3, 18, 12, tzinfo=UTC)
    assert criada.referencia == "Plataforma", "sem projeto, a referência é o time"
    assert criada.pessoas == ("Gabriel Velozo",)


def test_issue_que_so_foi_mexida_ainda_aparece_com_o_estado_atual():
    eventos = coletar_o_dia_cheio()

    atualizada = eventos[ATUALIZADA]
    assert atualizada.momento == datetime(2026, 9, 4, 1, 35, tzinfo=UTC)
    assert atualizada.referencia == "Fontes passivas"
    assert atualizada.pessoas == ("Gabriel Velozo",)


def test_issue_que_mudou_de_estado_nao_aparece_tambem_como_atualizada():
    titulos = [evento.titulo for evento in fonte_do_dia_cheio().coletar(JANELA)]

    da_issue = [titulo for titulo in titulos if titulo.startswith("FN-123 ")]
    assert da_issue == [MOVIDA, COMENTADA]


def test_mudanca_de_estado_de_outro_dia_nao_entra_neste_diario():
    # A trilha da FN-123 traz a passagem para "In Progress" de 1º de setembro:
    # o `history` do Linear não aceita filtro de data, quem recorta é o coletor.
    titulos = [evento.titulo for evento in fonte_do_dia_cheio().coletar(JANELA)]

    assert not any(
        "para In Progress" in titulo and titulo.startswith("FN-123 ")
        for titulo in titulos
    )


def test_mudanca_que_nao_e_de_estado_nao_vira_evento():
    # A FN-123 tem uma entrada de histórico sem `toState` (mudança de título).
    eventos = fonte_do_dia_cheio().coletar(JANELA)

    mudanca_de_titulo = datetime(2026, 9, 3, 13, 40, tzinfo=UTC)
    assert not any(evento.momento == mudanca_de_titulo for evento in eventos)


def test_comentario_vira_evento_com_o_texto_no_detalhe():
    eventos = coletar_o_dia_cheio()

    comentario = eventos[COMENTADA]
    assert comentario.momento == datetime(2026, 9, 3, 15, 2, tzinfo=UTC)
    assert comentario.detalhe.startswith("Confirmei com o financeiro")
    assert comentario.referencia == "Frete v2"
    assert comentario.url.endswith("#comment-9a1b2c3d"), "o link aponta o comentário"
    assert comentario.pessoas == ("Ana Prado",)


def test_comentario_de_projeto_sem_issue_ainda_vira_evento():
    eventos = coletar_o_dia_cheio()

    comentario = eventos[COMENTADA_NO_PROJETO]
    assert comentario.referencia == "Fontes passivas"
    assert comentario.detalhe.startswith("Subi o resumo da pesquisa")


def test_comentario_fora_da_janela_e_descartado_mesmo_vindo_da_api():
    eventos = fonte_do_dia_cheio().coletar(JANELA)

    assert all(JANELA.contem(evento.momento) for evento in eventos)
    assert not any("não deveria ter devolvido" in evento.detalhe for evento in eventos)


def test_todo_evento_sai_marcado_como_da_fonte_linear():
    eventos = fonte_do_dia_cheio().coletar(JANELA)

    assert eventos, "o dia cheio rende eventos"
    assert {evento.fonte for evento in eventos} == {"linear"}
    assert FonteLinear(CHAVE_FALSA).nome == "linear"


def test_momento_vem_aware_no_fuso_local_e_nao_em_utc():
    # A API devolve UTC com sufixo Z; o agrupamento por dia e o HH:MM da nota
    # dependem da conversão para o relógio do usuário.
    esperado = datetime(2026, 9, 3, 14, 20, tzinfo=UTC)

    eventos = coletar_o_dia_cheio()

    momento = eventos[MOVIDA].momento
    assert momento == esperado
    assert momento.utcoffset() == esperado.astimezone().utcoffset()


def test_dia_sem_movimento_no_linear_devolve_tupla_vazia_e_nao_falha():
    assert fonte().coletar(JANELA) == ()


# -- Paginação --------------------------------------------------------------


def test_segunda_pagina_de_issues_e_lida_com_o_cursor_da_primeira():
    registro: list[httpx.Request] = []

    eventos = fonte_do_dia_cheio(registro).coletar(JANELA)

    das_issues = requisicoes_de(registro, "DiarioIssues")
    assert len(das_issues) == 2, "a primeira página disse hasNextPage"
    assert variaveis(das_issues[1])["cursor"] == "cursor-da-pagina-2"
    assert any(evento.titulo.startswith("FN-130 ") for evento in eventos), (
        "o evento da segunda página entrou no dia"
    )


def test_paginacao_para_quando_o_cursor_nao_avanca():
    """Um cursor repetido giraria para sempre e queimaria a cota do usuário."""
    registro: list[httpx.Request] = []
    teimosa = {
        "data": {
            "issues": {
                "pageInfo": {"hasNextPage": True, "endCursor": "sempre-o-mesmo"},
                "nodes": [],
            }
        }
    }

    fonte({"issues": teimosa}, registro=registro).coletar(JANELA)

    das_issues = requisicoes_de(registro, "DiarioIssues")
    assert len(das_issues) == 2


def test_comentarios_tambem_paginam():
    registro: list[httpx.Request] = []
    primeira = {
        "data": {
            "comments": {
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-dos-comentarios"},
                "nodes": [],
            }
        }
    }

    fonte(
        {"comentarios": [primeira, carregar_fixture("resposta_linear_comentarios.json")]},
        registro=registro,
    ).coletar(JANELA)

    dos_comentarios = requisicoes_de(registro, "DiarioComentarios")
    assert len(dos_comentarios) == 2
    assert variaveis(dos_comentarios[1])["cursor"] == "cursor-dos-comentarios"


# -- Falhas -----------------------------------------------------------------


def test_chave_ausente_vira_erro_de_fonte_dizendo_onde_preencher():
    with pytest.raises(ErroDeFonte) as erro:
        fonte(chave="   ").coletar(JANELA)

    assert "[linear].api_key" in str(erro.value)
    assert "Read" in str(erro.value), "a mensagem diz qual permissão a chave precisa"


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        (400, "recusou a consulta"),
        (401, "inválida ou revogada"),
        (403, "não tem permissão de leitura"),
        (429, "limitou a taxa"),
        (500, "fora do ar"),
        (503, "fora do ar"),
        (418, "recusou a requisição"),
    ],
)
def test_cada_status_http_vira_um_conselho_diferente(codigo: int, esperado: str):
    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": httpx.Response(codigo, json={})}).coletar(JANELA)

    mensagem = str(erro.value)
    assert f"HTTP {codigo}" in mensagem
    assert esperado in mensagem


def test_erro_do_graphql_dentro_de_um_200_vira_erro_de_fonte():
    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": carregar_fixture("resposta_linear_erro.json")}).coletar(JANELA)

    mensagem = str(erro.value)
    assert "Authentication required, not authenticated" in mensagem
    assert "[linear].api_key" in mensagem


def test_mensagem_do_linear_no_corpo_do_erro_http_entra_no_diagnostico():
    corpo = {"errors": [{"message": "Entity not found: Team"}]}

    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": httpx.Response(400, json=corpo)}).coletar(JANELA)

    assert "Entity not found: Team" in str(erro.value)


def test_rede_caida_vira_erro_de_fonte_falando_em_conexao():
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host", request=requisicao)

    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": cair}).coletar(JANELA)

    assert "Falha de rede" in str(erro.value)
    assert "Confira a conexão" in str(erro.value)


def test_tempo_esgotado_vira_erro_de_fonte():
    def demorar(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou demais", request=requisicao)

    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": demorar}).coletar(JANELA)

    assert "não respondeu a tempo" in str(erro.value)


def test_corpo_que_nao_e_json_vira_erro_de_fonte():
    with pytest.raises(ErroDeFonte, match="não é JSON"):
        fonte({"issues": httpx.Response(200, text="<html>oops</html>")}).coletar(JANELA)


def test_resposta_sem_data_e_sem_errors_vira_erro_de_fonte():
    with pytest.raises(ErroDeFonte, match="sem 'data' e sem 'errors'"):
        fonte({"issues": {"extensions": {}}}).coletar(JANELA)


def test_nenhum_erro_httpx_escapa_para_a_costura():
    # A costura só conhece `ErroDeFonte`; um `httpx.HTTPError` vazando mataria
    # o diário inteiro em vez de marcar só o Linear.
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("nada responde", request=requisicao)

    with pytest.raises(ErroDeFonte):
        fonte({"issues": cair}).coletar(JANELA)


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(401, json={"errors": [{"message": "Authentication required"}]}),
        httpx.Response(429, json={}),
        httpx.Response(500, text="oops"),
    ],
)
def test_a_chave_nunca_aparece_na_mensagem_de_erro(resposta: httpx.Response):
    segredo = "lin_api_segredo_do_usuario"

    with pytest.raises(ErroDeFonte) as erro:
        fonte({"issues": resposta}, chave=segredo).coletar(JANELA)

    assert segredo not in str(erro.value)


# -- Configuração e CLI -----------------------------------------------------


def configuracao_com_linear(chave: str, tmp_path: Path) -> Configuracao:
    return Configuracao(
        vault=tmp_path / "vault",
        gravacoes=tmp_path / "gravacoes",
        linear_api_key=chave,
        origem=tmp_path / "config.toml",
    )


def test_de_configuracao_le_a_chave_do_arquivo_local(tmp_path: Path):
    registro: list[httpx.Request] = []

    def responder(requisicao: httpx.Request) -> httpx.Response:
        registro.append(requisicao)
        return httpx.Response(200, json=PAGINA_VAZIA["issues"])

    coletor = de_configuracao(
        configuracao_com_linear(CHAVE_FALSA, tmp_path),
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
    )
    coletor.coletar(JANELA)

    assert coletor.nome == "linear"
    assert registro[0].headers["authorization"] == CHAVE_FALSA


def test_montar_fontes_liga_o_linear_quando_a_chave_esta_preenchida(tmp_path: Path):
    fontes = montar_fontes(configuracao_com_linear(CHAVE_FALSA, tmp_path))

    assert [fonte_.nome for fonte_ in fontes] == ["linear"]
    assert isinstance(fontes[0], FonteLinear)


# -- Contra a API de verdade ------------------------------------------------
#
# Só roda na máquina do usuário, com a Personal API Key read-only preenchida.
# Sem chave, pula — e é isso que se espera hoje. O roteiro para criar a chave
# está em `docs/smoke-linear.md`.


def chave_configurada() -> str:
    """A chave da configuração local de verdade — vazio quando não houver."""
    try:
        return carregar().linear_api_key
    except ConfiguracaoInvalida:
        return ""


@pytest.mark.rede
def test_rede_le_a_movimentacao_de_ontem_no_linear_de_verdade():
    """Prova ponta a ponta que chave, endpoint, consulta e tradução batem.

    Lê a janela de ontem, que é o caso real do diário. Um dia sem movimento
    devolve tupla vazia — isso não é falha, e o teste continua provando que a
    consulta foi aceita.
    """
    chave = chave_configurada()
    if not chave:
        pytest.skip("sem [linear].api_key na configuração local")

    ontem = date.fromordinal(date.today().toordinal() - 1)
    eventos = FonteLinear(chave).coletar(janela_do_dia(ontem))

    janela = janela_do_dia(ontem)
    for evento in eventos:
        assert evento.fonte == "linear"
        assert evento.momento.tzinfo is not None
        assert janela.contem(evento.momento), "a fonte recorta pela janela"
        assert evento.titulo.strip()
