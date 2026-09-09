"""Adaptador real da DM: Socket Mode do Slack, pelo SDK oficial.

Socket Mode é uma conexão **de dentro para fora**: o processo abre um
websocket até o Slack e recebe os eventos por ele. Sem servidor, sem porta
aberta, sem URL pública — é o que mantém o ADR 0001 de pé numa máquina
doméstica. Exige dois tokens da mesma app: o **app-level token** (`xapp-`,
scope `connections:write`) para a conexão, e o **bot token** (`xoxb-`) para
reagir e responder. O user token `xoxp` do coletor não serve: ele não recebe
mensagem.

O SDK reconecta sozinho quando a conexão cai (`auto_reconnect_enabled`), e
exige que cada envelope seja confirmado em poucos segundos — a confirmação
sai na hora, antes de a mensagem entrar na fila, para o Slack não reenviar.

`web` e `socket` são injetáveis para os testes provarem a tradução do
envelope e a confirmação sem abrir websocket nenhum.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

from slack_sdk.errors import SlackApiError, SlackClientError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web import WebClient

from .atendente import ErroDeDM, Mensagem
from .configuracao import Configuracao

_log = logging.getLogger("whis.dm_slack")

#: Os scopes de bot que o atendente precisa — e nenhum outro.
SCOPES_DO_BOT = ("im:history", "im:read", "chat:write", "reactions:write")

#: O scope do app-level token.
SCOPE_DO_APP = "connections:write"

#: O evento que precisa estar assinado em *Event Subscriptions*.
EVENTO_ASSINADO = "message.im"

_CONSELHOS = {
    "invalid_auth": "o token foi recusado: reinstale a app e cole o token novo.",
    "account_inactive": "o token foi revogado: reinstale a app e cole o token novo.",
    "token_revoked": "o token foi revogado: reinstale a app e cole o token novo.",
    "not_allowed_token_type": "este token não é do tipo certo: confira se [slack].bot_token "
    "é o Bot User OAuth Token (xoxb-) e [slack].app_token é o App-Level Token (xapp-).",
    "missing_scope": "falta um scope de bot: confira se a app tem "
    + ", ".join(SCOPES_DO_BOT)
    + " e reinstale-a.",
    "channel_not_found": "a DM não foi encontrada — a app precisa ter *Messages Tab* ligada.",
}


class DMSlack:
    """A DM do bot por Socket Mode. Implementa `atendente.PortaDM`."""

    def __init__(
        self,
        app_token: str,
        bot_token: str,
        *,
        web: Any | None = None,
        socket: Any | None = None,
    ) -> None:
        self._app_token = app_token.strip()
        self._bot_token = bot_token.strip()
        self._web = web
        self._socket = socket
        self._fila: queue.Queue[Mensagem] = queue.Queue()
        self.eu = ""

    def iniciar(self) -> str:
        if self._web is None:
            self._web = WebClient(token=self._bot_token)
        try:
            auth = self._web.auth_test()
        except (SlackApiError, SlackClientError) as erro:
            raise ErroDeDM(f"O Slack recusou o bot token: {_traduzir(erro)}") from erro
        self.eu = str(auth["user_id"])

        if self._socket is None:
            self._socket = SocketModeClient(app_token=self._app_token, web_client=self._web)
        self._socket.socket_mode_request_listeners.append(self._receber)
        try:
            self._socket.connect()
        except (SlackApiError, SlackClientError, OSError) as erro:
            raise ErroDeDM(
                f"Não consegui abrir o Socket Mode: {_traduzir(erro)} Confira se o Socket "
                f"Mode está ligado na app e se [slack].app_token tem o scope {SCOPE_DO_APP}."
            ) from erro
        _log.info("Socket Mode conectado; o bot é %s.", self.eu)
        return self.eu

    def proxima(self, timeout_s: float) -> Mensagem | None:
        try:
            return self._fila.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def reagir(self, mensagem: Mensagem, emoji: str) -> None:
        try:
            self._web.reactions_add(channel=mensagem.canal, name=emoji, timestamp=mensagem.ts)
        except SlackApiError as erro:
            if _codigo(erro) == "already_reacted":
                return
            raise ErroDeDM(f"Não consegui reagir: {_traduzir(erro)}") from erro
        except SlackClientError as erro:
            raise ErroDeDM(f"Não consegui reagir: {_traduzir(erro)}") from erro

    def responder(self, mensagem: Mensagem, texto: str) -> None:
        try:
            self._web.chat_postMessage(channel=mensagem.canal, text=texto)
        except (SlackApiError, SlackClientError) as erro:
            raise ErroDeDM(f"Não consegui publicar na DM: {_traduzir(erro)}") from erro

    def encerrar(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception as erro:  # noqa: BLE001 — fechar nunca pode falhar alto
                _log.debug("Ao fechar o Socket Mode: %s", erro)

    def _receber(self, cliente: Any, requisicao: SocketModeRequest) -> None:
        """O listener do SDK: confirma o envelope e enfileira a mensagem."""
        if requisicao.envelope_id:
            cliente.send_socket_mode_response(SocketModeResponse(envelope_id=requisicao.envelope_id))
        if requisicao.type != "events_api":
            return
        evento = (requisicao.payload or {}).get("event") or {}
        mensagem = mensagem_do_evento(evento)
        if mensagem is not None:
            self._fila.put(mensagem)


def mensagem_do_evento(evento: dict[str, Any]) -> Mensagem | None:
    """Traduz o `event` de um envelope `events_api` em `Mensagem`, ou nada."""
    if evento.get("type") != "message":
        return None
    return Mensagem(
        canal=str(evento.get("channel") or ""),
        usuario=str(evento.get("user") or ""),
        texto=str(evento.get("text") or ""),
        ts=str(evento.get("ts") or ""),
        tipo_de_canal=str(evento.get("channel_type") or ""),
        subtipo=evento.get("subtype"),
        do_bot=bool(evento.get("bot_id")),
    )


def de_configuracao(configuracao: Configuracao) -> DMSlack:
    """Monta a DM a partir da configuração local — o atalho da CLI."""
    faltando = [
        chave
        for chave, valor in (
            ("[slack].bot_token", configuracao.slack_bot_token),
            ("[slack].app_token", configuracao.slack_app_token),
        )
        if not valor
    ]
    if faltando:
        raise ErroDeDM(
            f"O atendente precisa de {' e '.join(faltando)} na configuração"
            f"{f' ({configuracao.origem})' if configuracao.origem else ''}: o Bot User OAuth "
            f"Token (xoxb-) e o App-Level Token (xapp-) da app, com Socket Mode ligado. "
            f"O roteiro está em docs/smoke-atendente.md."
        )
    return DMSlack(configuracao.slack_app_token, configuracao.slack_bot_token)


def _codigo(erro: SlackApiError) -> str:
    resposta = getattr(erro, "response", None)
    try:
        return str(resposta["error"]) if resposta is not None else ""
    except (KeyError, TypeError):
        return ""


def _traduzir(erro: Exception) -> str:
    """A mensagem em português, sem nunca ecoar o token."""
    if isinstance(erro, SlackApiError):
        codigo = _codigo(erro)
        conselho = _CONSELHOS.get(codigo, "confira o token e os scopes da app.")
        return f"'{codigo or 'erro desconhecido'}' — {conselho}"
    return f"{type(erro).__name__}: {erro}"
