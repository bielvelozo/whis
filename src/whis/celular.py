r"""O aviso no celular: uma mensagem do bot do Telegram dele, ao lado do toast.

O toast só aparece com ele no PC, e na 99Freelas e no Freelancer.com quem
propõe na primeira hora é quem tem chance. O bot é dele (criado no @BotFather);
o token e o chat moram em `[celular]` no config.toml, e `whis celular` grava os
dois sem o token passar pela tela.

Como o toast, falhar em avisar nunca derruba quem chamou. O token vai na URL da
API, então nenhuma mensagem de erro daqui leva a URL ao log.
"""

from __future__ import annotations

import logging
import time

import httpx

_log = logging.getLogger("whis.celular")

API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_DO_TEXTO = 4096
TEMPO_LIMITE_S = 20.0
ESPERA_ENTRE_LEITURAS_S = 3.0

#: O transporte do httpx que `whis celular` usa; os testes trocam por um de mentira.
REDE_DO_TELEGRAM: httpx.BaseTransport | None = None


class Telegram:
    """O bot dele falando com o chat dele."""

    def __init__(self, token: str, chat: str, *, rede: httpx.BaseTransport | None = None) -> None:
        self.token = token.strip()
        self.chat = str(chat).strip()
        self._rede = rede if rede is not None else REDE_DO_TELEGRAM

    def enviar(self, texto: str) -> bool:
        corpo = {"chat_id": self.chat, "text": texto[:LIMITE_DO_TEXTO], "link_preview_options": {"is_disabled": True}}
        return self._chamar("sendMessage", corpo) is not None

    def usuario_do_bot(self) -> str:
        """O `@usuário` do bot, ou vazio quando o token não é de um bot."""
        resultado = self._chamar("getMe", {})
        return str(resultado.get("username", "")) if isinstance(resultado, dict) else ""

    def chat_da_ultima_mensagem(self) -> str:
        """O chat da última mensagem privada que alguém mandou ao bot (é ele: o bot acabou de nascer)."""
        atualizacoes = self._chamar("getUpdates", {"allowed_updates": ["message"]})
        for atualizacao in reversed(atualizacoes if isinstance(atualizacoes, list) else []):
            chat = ((atualizacao or {}).get("message") or {}).get("chat") or {}
            if chat.get("type") == "private" and chat.get("id") is not None:
                return str(chat["id"])
        return ""

    def _chamar(self, metodo: str, corpo: dict) -> object | None:
        try:
            with httpx.Client(transport=self._rede, timeout=TEMPO_LIMITE_S) as cliente:
                resposta = cliente.post(API.format(token=self.token, metodo=metodo), json=corpo)
            dados = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            _log.warning("O Telegram não respondeu a %s (%s).", metodo, type(erro).__name__)
            return None
        if not isinstance(dados, dict) or not dados.get("ok"):
            descricao = dados.get("description", "") if isinstance(dados, dict) else ""
            _log.warning("O Telegram recusou %s: %s", metodo, str(descricao)[:200] or f"HTTP {resposta.status_code}")
            return None
        return dados.get("result")


def avisar(configuracao, texto: str) -> bool:
    """Manda `texto` para o chat de `[celular]`; sem token ou sem chat, não manda e devolve False."""
    token, chat = configuracao.celular_telegram_token, configuracao.celular_telegram_chat
    if not token or not chat:
        return False
    return Telegram(token, chat).enviar(texto)


def esperar_o_chat(telegram: Telegram, *, segundos: float = 120.0) -> str:
    """Lê as mensagens do bot até aparecer uma privada, por até `segundos`."""
    limite = time.monotonic() + segundos
    while True:
        chat = telegram.chat_da_ultima_mensagem()
        if chat or time.monotonic() >= limite:
            return chat
        time.sleep(ESPERA_ENTRE_LEITURAS_S)
