r"""O aviso no celular: uma mensagem do bot do Telegram dele, ao lado do toast.

O toast só aparece com ele no PC, e na 99Freelas e no Freelancer.com quem
propõe na primeira hora é quem tem chance. O bot é dele (criado no @BotFather);
o token e o chat moram em `[celular]` no config.toml, e `whis celular` grava os
dois sem o token passar pela tela.

Como o toast, falhar em avisar nunca derruba quem chamou. O token vai na URL da
API, então nenhuma mensagem de erro daqui leva a URL ao log.

A mensagem pode levar botões. O `Ouvinte` mora na bandeja, espera os toques
do chat dele na API e passa cada um a quem atende. A proposta que não saiu
sozinha chega com "Enviar esta proposta", e o toque dele faz o envio.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

_log = logging.getLogger("whis.celular")

API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_DO_TEXTO = 4096
TEMPO_LIMITE_S = 20.0
ESPERA_ENTRE_LEITURAS_S = 3.0
#: Quanto cada leitura dos toques espera na API antes de voltar vazia.
ESPERA_DO_TOQUE_S = 50
PAUSA_DEPOIS_DE_FALHA_S = 30.0
PAUSA_SEM_BOT_S = 300.0
RECEBIDO = "Recebido: o Whis já está cuidando disso."
FALHOU = "Não deu certo: erro inesperado no Whis (veja o bandeja.log). Toque de novo daqui a pouco."

#: O transporte do httpx que `whis celular` usa; os testes trocam por um de mentira.
REDE_DO_TELEGRAM: httpx.BaseTransport | None = None


class Telegram:
    """O bot dele falando com o chat dele."""

    def __init__(self, token: str, chat: str, *, rede: httpx.BaseTransport | None = None) -> None:
        self.token = token.strip()
        self.chat = str(chat).strip()
        self._rede = rede if rede is not None else REDE_DO_TELEGRAM

    def enviar(
        self, texto: str, *, botoes: Sequence[tuple[str, str]] = (), responder_a: int | None = None, html: bool = False
    ) -> bool:
        """`botoes` são pares (rótulo, dados do toque ou link https), um por linha embaixo da mensagem; `html` liga o `<pre>` que copia num toque.

        O botão com link abre o endereço no celular sem passar pelo Whis.
        """
        corpo: dict = {"chat_id": self.chat, "text": texto[:LIMITE_DO_TEXTO], "link_preview_options": {"is_disabled": True}}
        if html:
            corpo["parse_mode"] = "HTML"
        if botoes:
            corpo["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": rotulo, ("url" if dados.startswith("https://") else "callback_data"): dados}] for rotulo, dados in botoes
                ]
            }
        if responder_a is not None:
            corpo["reply_parameters"] = {"message_id": responder_a, "allow_sending_without_reply": True}
        return self._chamar("sendMessage", corpo) is not None

    def toques(self, offset: int | None, *, espera: int = ESPERA_DO_TOQUE_S) -> list | None:
        """Os toques nos botões depois de `offset`, esperando até `espera` s; None quando a API falhou."""
        corpo: dict = {"timeout": espera, "allowed_updates": ["callback_query"]}
        if offset is not None:
            corpo = {"offset": offset, **corpo}
        resultado = self._chamar("getUpdates", corpo, tempo=espera + TEMPO_LIMITE_S)
        return resultado if isinstance(resultado, list) else None

    def responder_toque(self, toque: str, texto: str = "") -> None:
        """Sem esta resposta o botão fica girando no celular."""
        self._chamar("answerCallbackQuery", {"callback_query_id": toque, "text": texto} if texto else {"callback_query_id": toque})

    def tirar_botoes(self, mensagem: int) -> None:
        self._chamar("editMessageReplyMarkup", {"chat_id": self.chat, "message_id": mensagem, "reply_markup": {"inline_keyboard": []}})

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

    def _chamar(self, metodo: str, corpo: dict, *, tempo: float = TEMPO_LIMITE_S) -> object | None:
        try:
            with httpx.Client(transport=self._rede, timeout=tempo) as cliente:
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


def avisar(configuracao, texto: str, *, botoes: Sequence[tuple[str, str]] = (), html: bool = False) -> bool:
    """Manda `texto` para o chat de `[celular]`; sem token ou sem chat, não manda e devolve False."""
    token, chat = configuracao.celular_telegram_token, configuracao.celular_telegram_chat
    if not token or not chat:
        return False
    return Telegram(token, chat).enviar(texto, botoes=botoes, html=html)


def esperar_o_chat(telegram: Telegram, *, segundos: float = 120.0) -> str:
    """Lê as mensagens do bot até aparecer uma privada, por até `segundos`."""
    limite = time.monotonic() + segundos
    while True:
        chat = telegram.chat_da_ultima_mensagem()
        if chat or time.monotonic() >= limite:
            return chat
        time.sleep(ESPERA_ENTRE_LEITURAS_S)


@dataclass(frozen=True)
class Resposta:
    """O que o Whis responde ao toque; `tirar_botao` quando tocar de novo não faria mais nada."""

    texto: str
    tirar_botao: bool = False


class Ouvinte:
    """Espera os toques nos botões, numa thread da bandeja, e responde cada um na conversa.

    Só o chat de `[celular]` é atendido. `configuracao` é lida a cada volta, então o
    token trocado no painel vale sem reiniciar. Os toques chegam em ordem e um de
    cada vez: quem atende pode demorar (abre o Chrome da caçada).
    """

    def __init__(
        self,
        configuracao: Callable[[], object],
        ao_tocar: Callable[[str], Resposta],
        *,
        rede: httpx.BaseTransport | None = None,
        espera_s: int = ESPERA_DO_TOQUE_S,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._configuracao = configuracao
        self._ao_tocar = ao_tocar
        self._rede = rede
        self._espera_s = espera_s
        self._dormir = dormir
        self._offset: int | None = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def uma_vez(self) -> int:
        """Uma leitura da API e o atendimento do que veio; devolve quantos toques chegaram."""
        configuracao = self._configuracao()
        token, chat = configuracao.celular_telegram_token, str(configuracao.celular_telegram_chat)
        if not token or not chat:
            self._dormir(PAUSA_SEM_BOT_S)
            return 0
        telegram = Telegram(token, chat, rede=self._rede)
        atualizacoes = telegram.toques(self._offset, espera=self._espera_s)
        if atualizacoes is None:
            self._dormir(PAUSA_DEPOIS_DE_FALHA_S)
            return 0
        toques = 0
        for atualizacao in atualizacoes:
            if isinstance(atualizacao.get("update_id"), int):
                self._offset = atualizacao["update_id"] + 1
            toque = atualizacao.get("callback_query")
            if not isinstance(toque, dict):
                continue
            toques += 1
            self._atender(telegram, chat, toque)
        return toques

    def _atender(self, telegram: Telegram, chat: str, toque: dict) -> None:
        mensagem = toque.get("message") or {}
        de_quem = str((toque.get("from") or {}).get("id", ""))
        onde = str((mensagem.get("chat") or {}).get("id", ""))
        if de_quem != chat or onde != chat:
            _log.warning("Celular: toque de outro chat ignorado.")
            telegram.responder_toque(str(toque.get("id", "")))
            return
        telegram.responder_toque(str(toque.get("id", "")), RECEBIDO)
        try:
            resposta = self._ao_tocar(str(toque.get("data", "")))
        except Exception:  # noqa: BLE001 — um toque que quebra não derruba quem ouve os próximos
            _log.exception("Celular: o toque %r quebrou.", toque.get("data"))
            resposta = Resposta(FALHOU)
        numero = mensagem.get("message_id") if isinstance(mensagem.get("message_id"), int) else None
        telegram.enviar(resposta.texto, responder_a=numero)
        if resposta.tirar_botao and numero is not None:
            telegram.tirar_botoes(numero)

    def iniciar(self) -> None:
        self._thread = threading.Thread(target=self._rodar, name="whis-celular", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    def esperar(self, segundos: float) -> bool:
        """Espera a thread acabar; True quando acabou."""
        if self._thread is None:
            return True
        self._thread.join(segundos)
        return not self._thread.is_alive()

    def _rodar(self) -> None:
        _log.info("Celular: ouvindo os botões do Telegram.")
        while not self._parar.is_set():
            try:
                self.uma_vez()
            except Exception:  # noqa: BLE001 — a bandeja segue; a próxima volta tenta de novo
                _log.exception("Celular: a leitura dos toques falhou.")
                self._dormir(PAUSA_DEPOIS_DE_FALHA_S)
