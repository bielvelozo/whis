"""O adaptador da Granola: a leitura do texto do MCP e a sessão por dublê.

As amostras em `fixtures/granola/` seguem o formato que o MCP devolveu em
2026-09-30, no plano Basic, com conteúdo inventado. Nenhum teste fala com a
Granola: a sessão MCP entra por dublê.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from whis.granola import GranolaMCP, ler_data, ler_lista, ler_participantes, ler_reunioes
from whis.portas import ErroDaGranola, LoginNecessario

AMOSTRAS = Path(__file__).parent / "fixtures" / "granola"
MENOS_TRES = timezone(timedelta(hours=-3))


def amostra(nome: str) -> str:
    return (AMOSTRAS / nome).read_text(encoding="utf-8")


# -- a leitura -------------------------------------------------------------------


def test_a_lista_traz_id_titulo_e_inicio_local():
    reunioes = ler_lista(amostra("lista.txt"))

    assert [r.id[:8] for r in reunioes] == ["11111111", "22222222", "33333333"]
    assert reunioes[0].titulo == "Daily - Engenharia"
    assert reunioes[0].inicio == datetime(2026, 9, 2, 14, 0, tzinfo=MENOS_TRES)
    assert reunioes[0].inicio.utcoffset() == datetime(2026, 9, 2, 14, 0).astimezone().utcoffset()


def test_entidades_viram_texto():
    [_, retrospectiva, _] = ler_lista(amostra("lista.txt"))

    assert retrospectiva.titulo == 'P&D: retrospectiva "Q3"'


def test_lista_vazia_e_tupla_vazia():
    assert ler_lista(amostra("vazia.txt")) == ()
    assert ler_reunioes(amostra("vazia.txt")) == ()


def test_formato_inesperado_falha_alto():
    with pytest.raises(ErroDaGranola, match="formato"):
        ler_lista('{"meetings": []}')


def test_contagem_que_nao_bate_falha_alto():
    """Um formato novo que a leitura não reconhece não pode virar "nada novo" calado."""
    texto = amostra("lista.txt").replace('count="3"', 'count="4"')

    with pytest.raises(ErroDaGranola, match="declarou 4"):
        ler_lista(texto)


def test_detalhes_trazem_resumo_participantes_e_link():
    daily, _ = ler_reunioes(amostra("detalhes.txt"))

    assert daily.titulo == "Daily - Engenharia"
    assert daily.participantes == ("Ana Lima", "Carlos Souza")
    assert daily.url == "https://notes.granola.ai/d/11111111-1111-4111-8111-111111111111"
    assert daily.resumo.startswith("# Ana: entregas\n\n- Deploy do checkout")
    assert "preto & branco" in daily.resumo
    assert daily.resumo.endswith("- Fotos quadradas ficam para a próxima sprint")


def test_reuniao_sem_resumo_vem_com_resumo_vazio():
    _, retrospectiva = ler_reunioes(amostra("detalhes.txt"))

    assert retrospectiva.resumo == ""
    assert retrospectiva.participantes == ()


@pytest.mark.parametrize("marcador", ["No summary", "  no summary.  "])
def test_no_summary_da_granola_e_resumo_vazio(marcador: str):
    texto = (
        '<meetings_data from="Oct 14, 2026" to="Oct 14, 2026" count="1">\n'
        '<meeting id="22222222-2222-4222-8222-222222222222" title="Daily" date="Oct 14, 2026 10:30 AM GMT-3">\n'
        f"  <summary>\n{marcador}\n  </summary>\n"
        "</meeting>\n"
        "</meetings_data>"
    )

    (daily,) = ler_reunioes(texto)

    assert daily.resumo == ""


def test_tag_desconhecida_e_ignorada():
    daily, _ = ler_reunioes(amostra("detalhes.txt"))

    assert "lembrar de falar" not in daily.resumo


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Sep 1, 2026 2:00 PM GMT-3", datetime(2026, 9, 1, 14, 0, tzinfo=MENOS_TRES)),
        ("Sep 1, 2026 12:05 AM GMT-3", datetime(2026, 9, 1, 0, 5, tzinfo=MENOS_TRES)),
        ("Sep 1, 2026 12:30 PM GMT-3", datetime(2026, 9, 1, 12, 30, tzinfo=MENOS_TRES)),
        ("Dec 31, 2026 11:59 PM GMT+5:30", datetime(2026, 12, 31, 23, 59, tzinfo=timezone(timedelta(hours=5, minutes=30)))),
        ("Jan 5, 2027 9:00 AM GMT", datetime(2027, 1, 5, 9, 0, tzinfo=timezone.utc)),
    ],
)
def test_data_com_fuso(texto: str, esperado: datetime):
    assert ler_data(texto) == esperado


def test_data_ilegivel_e_erro_da_granola():
    with pytest.raises(ErroDaGranola, match="data"):
        ler_data("amanhã de manhã")


def test_participantes_sem_criador_email_nem_empresa():
    texto = (
        "Voce Mesmo (note creator) from Acme &lt;voce@example.com&gt;, "
        "Ana Lima from Acme &lt;ana@example.com&gt;, Bruno Costa &lt;bruno@example.com&gt;"
    )

    assert ler_participantes(texto) == ("Ana Lima", "Bruno Costa")


# -- o adaptador, com a sessão dublê ------------------------------------------------


class Texto:
    def __init__(self, text: str) -> None:
        self.text = text


class ResultadoDaFerramenta:
    def __init__(self, texto: str, *, erro: bool = False) -> None:
        self.is_error = erro
        self.content = [Texto(texto)]


class SessaoDublê:
    def __init__(self, respostas: dict[str, ResultadoDaFerramenta]) -> None:
        self.respostas = respostas
        self.chamadas: list[tuple[str, dict]] = []

    async def call_tool(self, nome: str, argumentos: dict):
        self.chamadas.append((nome, argumentos))
        return self.respostas[nome]


class GuardaDublê:
    def __init__(self, tokens=object()) -> None:
        self.tokens = tokens

    async def get_tokens(self):
        return self.tokens


def adaptador(tmp_path: Path, sessao: SessaoDublê, *, tokens=object(), pode_logar=True, abertos=None):
    @asynccontextmanager
    async def abrir(_adaptador):
        yield sessao

    return GranolaMCP(
        GuardaDublê(tokens),
        pasta=tmp_path,
        pode_logar=pode_logar,
        abrir_navegador=(abertos if abertos is not None else []).append,
        sessao=abrir,
    )


def test_listar_e_detalhar_leem_o_texto_da_ferramenta(tmp_path: Path):
    sessao = SessaoDublê(
        {
            "list_meetings": ResultadoDaFerramenta(amostra("lista.txt")),
            "get_meetings": ResultadoDaFerramenta(amostra("detalhes.txt")),
        }
    )
    granola = adaptador(tmp_path, sessao)

    assert len(granola.listar()) == 3
    assert [r.titulo for r in granola.detalhar(["11111111-1111-4111-8111-111111111111"])][0] == "Daily - Engenharia"


def test_detalhar_manda_os_ids(tmp_path: Path):
    sessao = SessaoDublê({"get_meetings": ResultadoDaFerramenta(amostra("vazia.txt"))})

    adaptador(tmp_path, sessao).detalhar(["a", "b"])

    assert sessao.chamadas == [("get_meetings", {"meeting_ids": ["a", "b"]})]


def test_is_error_vira_erro_da_granola(tmp_path: Path):
    sessao = SessaoDublê({"list_meetings": ResultadoDaFerramenta("Rate limit exceeded", erro=True)})

    with pytest.raises(ErroDaGranola, match="Rate limit exceeded"):
        adaptador(tmp_path, sessao).listar()


def test_sem_login_e_sem_permissao_nao_abre_navegador_nem_sessao(tmp_path: Path):
    sessao = SessaoDublê({})
    abertos: list[str] = []

    with pytest.raises(LoginNecessario):
        adaptador(tmp_path, sessao, tokens=None, pode_logar=False, abertos=abertos).listar()

    assert sessao.chamadas == [] and abertos == []


def test_redirecionar_sem_permissao_levanta_login_necessario(tmp_path: Path):
    import asyncio

    abertos: list[str] = []
    granola = adaptador(tmp_path, SessaoDublê({}), pode_logar=False, abertos=abertos)

    with pytest.raises(LoginNecessario):
        asyncio.run(granola._redirecionar("https://mcp-auth.granola.ai/oauth2/authorize?x=1"))

    assert abertos == []


def test_login_necessario_aninhado_e_desembrulhado(tmp_path: Path):
    class SessaoQueExplode(SessaoDublê):
        async def call_tool(self, nome, argumentos):
            raise ExceptionGroup("grupo", [RuntimeError("ruído"), LoginNecessario("a Granola pediu login")])

    with pytest.raises(LoginNecessario, match="pediu login"):
        adaptador(tmp_path, SessaoQueExplode({})).listar()


def test_outra_excecao_vira_erro_da_granola(tmp_path: Path):
    class SessaoSemRede(SessaoDublê):
        async def call_tool(self, nome, argumentos):
            raise OSError("getaddrinfo failed")

    with pytest.raises(ErroDaGranola, match="getaddrinfo failed"):
        adaptador(tmp_path, SessaoSemRede({})).listar()


# -- o transporte de verdade do SDK, sem rede -------------------------------------
#
# O anyio embrulha em `ExceptionGroup` o que cai dentro do task group do
# `streamable_http_client`: estes passam pelo SDK real com um `httpx2` falso.


def _sessao_sem_rede(responder, auth=None):
    import httpx2

    @asynccontextmanager
    async def abrir(_adaptador):
        cliente = httpx2.AsyncClient(transport=httpx2.MockTransport(responder), auth=auth)
        async with cliente:
            async with streamable_http_client("https://mcp.granola.ai/mcp", http_client=cliente) as (ler, escrever):
                async with ClientSession(ler, escrever) as sessao:
                    await sessao.initialize()
                    yield sessao

    return abrir


def test_login_necessario_atravessa_o_sdk_desembrulhado(tmp_path: Path):
    import httpx2

    alvo: dict[str, GranolaMCP] = {}

    class PedeLoginNo401(httpx2.Auth):
        async def async_auth_flow(self, request):
            resposta = yield request
            if resposta.status_code == 401:
                await alvo["granola"]._redirecionar("https://mcp-auth.granola.ai/oauth2/authorize")

    abertos: list[str] = []
    granola = GranolaMCP(
        GuardaDublê(),
        pasta=tmp_path,
        pode_logar=False,
        abrir_navegador=abertos.append,
        sessao=_sessao_sem_rede(lambda _r: httpx2.Response(401, json={"error": "unauthorized"}), PedeLoginNo401()),
    )
    alvo["granola"] = granola

    with pytest.raises(LoginNecessario):
        granola.listar()
    assert abertos == []


def test_sem_rede_no_sdk_vira_erro_da_granola(tmp_path: Path):
    import httpx2

    def recusar(request):
        raise httpx2.ConnectError("sem rede", request=request)

    granola = GranolaMCP(GuardaDublê(), pasta=tmp_path, pode_logar=True, sessao=_sessao_sem_rede(recusar))

    with pytest.raises(ErroDaGranola) as erro:
        granola.listar()
    assert not isinstance(erro.value, LoginNecessario)
