"""O adaptador da Granola: o MCP oficial, a leitura do que ele devolve e o login.

O MCP (`https://mcp.granola.ai/mcp`) não devolve JSON: `list_meetings` e
`get_meetings` mandam texto com marcação parecida com XML — um
`<meetings_data>` com um `<meeting id=… title=… date=… url=…>` por reunião e,
dentro dele, `<known_participants>` e `<summary>` (medido em 2026-09-30, plano
Basic). A leitura é por expressão regular, elemento a elemento: o markdown do
resumo não garante XML válido, e tag desconhecida é ignorada. Um texto sem
`<meetings_data>` é formato novo, e falha alto em vez de devolver nada.

O login é OAuth com registro dinâmico de cliente e PKCE, pelo SDK `mcp`; o
retorno chega num servidor local que só vive durante o login. Quem não pode
abrir o navegador (a tarefa agendada) recebe `LoginNecessario`.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientMetadata

from .granola_login import URL_DO_MCP, vez_da_granola
from .portas import ErroDaGranola, LoginNecessario, Reuniao, ReuniaoListada

_log = logging.getLogger("whis.granola")

#: Fixa porque o cliente registrado na Granola guarda este endereço de retorno.
PORTA_DO_RETORNO = 33418
REDIRECT = f"http://127.0.0.1:{PORTA_DO_RETORNO}/callback"
ESPERA_DO_LOGIN_S = 300.0

MENSAGEM_DE_LOGIN = "A Granola pediu login: rode meetings na palheta."
PAGINA_DO_RETORNO = "<p>Whis: login na Granola recebido. Pode fechar esta aba.</p>"

_MESES = {
    nome: numero
    for numero, nome in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1
    )
}
_DATA = re.compile(
    r"^\s*(?P<mes>[A-Z][a-z]{2})[a-z]*\.? (?P<dia>\d{1,2}), (?P<ano>\d{4}) "
    r"(?P<hora>\d{1,2}):(?P<minuto>\d{2}) (?P<periodo>AM|PM) "
    r"GMT(?:(?P<sinal>[+-])(?P<horas>\d{1,2})(?::(?P<minutos>\d{2}))?)?\s*$"
)
_DADOS = re.compile(r"<meetings_data\b([^>]*)>")
_REUNIAO = re.compile(r"<meeting\b([^>]*)>(.*?)</meeting>", re.S)
_ATRIBUTO = re.compile(r'(\w+)="([^"]*)"')
_PARTICIPANTES = re.compile(r"<known_participants>(.*?)</known_participants>", re.S)
_RESUMO = re.compile(r"<summary>(.*?)</summary>", re.S)
#: O que a Granola põe no `<summary>` enquanto o resumo não ficou pronto (visto em 14/10/2026):
#: vale como resumo vazio, senão a nota nasce só com isso e nunca é reescrita.
_SEM_RESUMO = re.compile(r"\s*no summary\.?\s*", re.I)


# -- a leitura -----------------------------------------------------------------------


def ler_lista(texto: str) -> tuple[ReuniaoListada, ...]:
    return tuple(
        ReuniaoListada(id=atributos["id"], titulo=atributos.get("title", ""), inicio=ler_data(atributos["date"]))
        for atributos, _corpo in _reunioes_do_texto(texto)
    )


def ler_reunioes(texto: str) -> tuple[Reuniao, ...]:
    reunioes = []
    for atributos, corpo in _reunioes_do_texto(texto):
        participantes = _PARTICIPANTES.search(corpo)
        resumo = _RESUMO.search(corpo)
        reunioes.append(
            Reuniao(
                id=atributos["id"],
                titulo=atributos.get("title", ""),
                inicio=ler_data(atributos["date"]),
                participantes=ler_participantes(participantes[1]) if participantes else (),
                resumo=_ler_resumo(resumo[1]) if resumo else "",
                url=atributos.get("url", ""),
            )
        )
    return tuple(reunioes)


def _ler_resumo(texto: str) -> str:
    resumo = html.unescape(texto).strip()
    return "" if _SEM_RESUMO.fullmatch(resumo) else resumo


def ler_data(texto: str) -> datetime:
    """`Sep 1, 2026 2:00 PM GMT-3` na hora local, sem depender do locale da máquina."""
    partes = _DATA.match(texto)
    if partes is None or partes["mes"] not in _MESES:
        raise ErroDaGranola(f"A Granola mandou uma data que não sei ler: {texto!r}.")
    hora = int(partes["hora"]) % 12 + (12 if partes["periodo"] == "PM" else 0)
    deslocamento = timedelta(hours=int(partes["horas"] or 0), minutes=int(partes["minutos"] or 0))
    if partes["sinal"] == "-":
        deslocamento = -deslocamento
    try:
        momento = datetime(
            int(partes["ano"]), _MESES[partes["mes"]], int(partes["dia"]), hora, int(partes["minuto"]),
            tzinfo=timezone(deslocamento),
        )
    except ValueError as erro:
        raise ErroDaGranola(f"A Granola mandou uma data que não sei ler: {texto!r}.") from erro
    return momento.astimezone()


def ler_participantes(texto: str) -> tuple[str, ...]:
    """Os nomes, sem o criador da nota (que é sempre o usuário), sem e-mail e sem empresa."""
    limpo = " ".join(html.unescape(texto).split())
    nomes = []
    for entrada in re.split(r"(?<=>),\s*", limpo) if limpo else ():
        if "(note creator)" in entrada:
            continue
        nome = re.split(r"\s+from\s+", re.sub(r"<[^>]*>", "", entrada), maxsplit=1)[0].strip(" ,")
        if nome:
            nomes.append(nome)
    return tuple(nomes)


def _reunioes_do_texto(texto: str) -> list[tuple[dict[str, str], str]]:
    dados = _DADOS.search(texto)
    if dados is None:
        raise ErroDaGranola(
            f"A Granola respondeu num formato inesperado: {' '.join(texto.split())[:200]!r}."
        )
    reunioes = []
    for achado in _REUNIAO.finditer(texto):
        atributos = {nome: html.unescape(valor) for nome, valor in _ATRIBUTO.findall(achado[1])}
        if "id" not in atributos or "date" not in atributos:
            raise ErroDaGranola(f"A Granola mandou uma reunião sem id ou sem data: {achado[1][:200]!r}.")
        reunioes.append((atributos, achado[2]))
    declarado = dict(_ATRIBUTO.findall(dados[1])).get("count", "")
    if declarado.isdigit() and int(declarado) != len(reunioes):
        raise ErroDaGranola(
            f"A Granola declarou {declarado} reunião(ões) e só {len(reunioes)} deu para ler: o formato mudou?"
        )
    return reunioes


# -- o adaptador ---------------------------------------------------------------------


class GranolaMCP:
    """A `PortaReunioes` de verdade: uma sessão MCP por chamada, uma chamada por vez.

    `sessao(adaptador)` abre a sessão já inicializada — injetável para o teste
    trocar a Granola por um dublê. `pode_logar` decide se falta de login abre o
    navegador (palheta, terminal) ou vira `LoginNecessario` (tarefa agendada).
    """

    def __init__(
        self,
        guarda,
        *,
        pasta: Path | str,
        pode_logar: bool,
        abrir_navegador: Callable[[str], object] = webbrowser.open,
        sessao: Callable[["GranolaMCP"], object] | None = None,
    ) -> None:
        self._guarda = guarda
        self._pasta = Path(pasta)
        self._pode_logar = pode_logar
        self._abrir_navegador = abrir_navegador
        self._sessao = sessao or _sessao_real
        self._retorno: _Retorno | None = None

    def listar(self) -> tuple[ReuniaoListada, ...]:
        return ler_lista(self._chamar("list_meetings", {}))

    def detalhar(self, ids: Sequence[str]) -> tuple[Reuniao, ...]:
        return ler_reunioes(self._chamar("get_meetings", {"meeting_ids": list(ids)}))

    def _chamar(self, ferramenta: str, argumentos: dict) -> str:
        with vez_da_granola(self._pasta):
            try:
                return asyncio.run(self._chamar_na_sessao(ferramenta, argumentos))
            except ErroDaGranola:
                raise
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as erro:  # noqa: BLE001 — o SDK embrulha erros em grupos
                for tipo in (LoginNecessario, ErroDaGranola):
                    achado = _achar(erro, tipo)
                    if achado is not None:
                        raise achado from None
                raise ErroDaGranola(f"A Granola não respondeu ({type(erro).__name__}): {erro}") from erro

    async def _chamar_na_sessao(self, ferramenta: str, argumentos: dict) -> str:
        if not self._pode_logar and await self._guarda.get_tokens() is None:
            raise LoginNecessario(MENSAGEM_DE_LOGIN)
        async with self._sessao(self) as sessao:
            resultado = await sessao.call_tool(ferramenta, argumentos)
        texto = "\n".join(
            parte for parte in (getattr(c, "text", None) for c in (resultado.content or [])) if parte
        )
        if getattr(resultado, "is_error", False):
            raise ErroDaGranola(f"A Granola recusou {ferramenta}: {texto or 'sem mensagem'}")
        return texto

    async def _redirecionar(self, url: str) -> None:
        """O `redirect_handler` do SDK: abre o login, ou recusa quando não pode."""
        if not self._pode_logar:
            raise LoginNecessario(MENSAGEM_DE_LOGIN)
        self._parar_retorno()
        self._retorno = _Retorno()
        _log.info("Abrindo o login da Granola no navegador.")
        self._abrir_navegador(url)

    async def _esperar_retorno(self) -> AuthorizationCodeResult:
        """O `callback_handler` do SDK: espera o navegador voltar com o código."""
        retorno = self._retorno
        if retorno is None:
            raise ErroDaGranola("O login da Granola não chegou a começar.")
        limite = time.monotonic() + ESPERA_DO_LOGIN_S
        try:
            while "code" not in retorno.recebido and "error" not in retorno.recebido:
                if time.monotonic() >= limite:
                    raise ErroDaGranola("Ninguém entrou na Granola em 5 minutos; o login foi cancelado.")
                await asyncio.sleep(0.25)
        finally:
            self._parar_retorno()
        if "error" in retorno.recebido:
            motivo = retorno.recebido.get("error_description") or retorno.recebido["error"]
            raise ErroDaGranola(f"A Granola recusou o login: {motivo}")
        _log.info("Login na Granola recebido.")
        return AuthorizationCodeResult(
            code=retorno.recebido["code"],
            state=retorno.recebido.get("state"),
            iss=retorno.recebido.get("iss"),
        )

    def _parar_retorno(self) -> None:
        if self._retorno is not None:
            self._retorno.parar()
            self._retorno = None


@asynccontextmanager
async def _sessao_real(adaptador: GranolaMCP):
    provedor = OAuthClientProvider(
        server_url=URL_DO_MCP,
        client_metadata=OAuthClientMetadata(
            client_name="Whis",
            redirect_uris=[REDIRECT],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        ),
        storage=adaptador._guarda,
        redirect_handler=adaptador._redirecionar,
        callback_handler=adaptador._esperar_retorno,
    )
    try:
        async with create_mcp_http_client(auth=provedor) as cliente:
            async with streamable_http_client(URL_DO_MCP, http_client=cliente) as (ler, escrever):
                async with ClientSession(ler, escrever) as sessao:
                    await sessao.initialize()
                    yield sessao
    finally:
        adaptador._parar_retorno()


class _Retorno:
    """O servidor local que recebe o navegador de volta do login, e só ele."""

    def __init__(self) -> None:
        self.recebido: dict[str, str] = {}
        recebido = self.recebido

        class _Pagina(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 — nome do http.server
                consulta = parse_qs(urlparse(self.path).query)
                if "code" in consulta or "error" in consulta:
                    recebido.update({chave: valores[0] for chave, valores in consulta.items()})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(PAGINA_DO_RETORNO.encode("utf-8"))

            def log_message(self, *_argumentos) -> None:
                pass

        try:
            self._servidor = HTTPServer(("127.0.0.1", PORTA_DO_RETORNO), _Pagina)
        except OSError as erro:
            raise ErroDaGranola(
                f"A porta {PORTA_DO_RETORNO}, do retorno do login da Granola, está ocupada: {erro}"
            ) from erro
        threading.Thread(target=self._servidor.serve_forever, name="whis-granola-login", daemon=True).start()

    def parar(self) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()


def _achar(erro: BaseException, tipo: type[BaseException]) -> BaseException | None:
    vistos: set[int] = set()
    pendentes = [erro]
    while pendentes:
        atual = pendentes.pop()
        if id(atual) in vistos:
            continue
        vistos.add(id(atual))
        if isinstance(atual, tipo):
            return atual
        if isinstance(atual, BaseExceptionGroup):
            pendentes.extend(atual.exceptions)
        for ligado in (atual.__cause__, atual.__context__):
            if ligado is not None:
                pendentes.append(ligado)
    return None
