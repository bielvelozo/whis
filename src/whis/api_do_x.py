"""A API oficial do X, na conta da velozo.dev: subir imagem e postar, um pedido por toque dele.

Em 31/10 ele escolheu publicar o post do dia por um botão no Telegram, pela API paga por uso, com o app
dele no console.x.com (OAuth 1.0a com Read and Write; as quatro chaves ficam em `[x]` no config.toml). O
preço é por pedido: US$ 0,015 o post e US$ 0,20 o post com link (docs.x.com, 31/10/2026).

A resposta a post de outra pessoa não passa por aqui: desde 23/02/2026 a API só aceita resposta quando o
autor do post marcou ou citou a conta. Responder ao próprio post (a thread) continua valendo.

Nenhuma mensagem daqui leva as chaves ou o cabeçalho de assinatura ao log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import mimetypes
import secrets
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

API = "https://api.x.com/2"
TEMPO_LIMITE_S = 30.0

#: O transporte do httpx que o cliente usa; os testes trocam por um de mentira.
REDE_DO_X: httpx.BaseTransport | None = None


class NaoSaiu(Exception):
    """O pedido não chegou ao X, ou o X respondeu que recusou: nada foi publicado."""


class SemConfirmacao(Exception):
    """O pedido pode ter sido publicado, mas o X não confirmou (rede caiu no meio, erro 5xx)."""


@dataclass(frozen=True)
class ChavesDoX:
    api_key: str = ""
    api_key_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""

    @classmethod
    def da_configuracao(cls, configuracao) -> ChavesDoX:
        return cls(
            configuracao.x_api_key, configuracao.x_api_key_secret, configuracao.x_access_token, configuracao.x_access_token_secret
        )

    @property
    def completas(self) -> bool:
        return all((self.api_key, self.api_key_secret, self.access_token, self.access_token_secret))


class Publicador(Protocol):
    def subir_imagem(self, arquivo: Path) -> str: ...

    def postar(self, texto: str, *, responder_a: str | None = None, imagens: Sequence[str] = ()) -> str: ...


def _cod(valor: str) -> str:
    return quote(str(valor), safe="")


def cabecalho_oauth(
    metodo: str,
    url: str,
    chaves: ChavesDoX,
    *,
    parametros: Mapping[str, str] | None = None,
    nonce: str | None = None,
    timestamp: int | None = None,
) -> str:
    """O `Authorization` do OAuth 1.0a (HMAC-SHA1). Corpo em JSON ou multipart fica fora da assinatura."""
    oauth = {
        "oauth_consumer_key": chaves.api_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time()) if timestamp is None else timestamp),
        "oauth_token": chaves.access_token,
        "oauth_version": "1.0",
    }
    pares = sorted((_cod(k), _cod(v)) for k, v in {**(parametros or {}), **oauth}.items())
    base = "&".join((metodo.upper(), _cod(url), _cod("&".join(f"{k}={v}" for k, v in pares))))
    chave = f"{_cod(chaves.api_key_secret)}&{_cod(chaves.access_token_secret)}"
    oauth["oauth_signature"] = base64.b64encode(hmac.new(chave.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_cod(k)}="{_cod(v)}"' for k, v in sorted(oauth.items()))


class ClienteDoX:
    def __init__(self, chaves: ChavesDoX, *, rede: httpx.BaseTransport | None = None) -> None:
        self.chaves = chaves
        self._rede = rede if rede is not None else REDE_DO_X

    def subir_imagem(self, arquivo: Path) -> str:
        """Sobe a imagem para o próximo post e devolve o `media_id`; subir sozinho não publica nada."""
        arquivo = Path(arquivo)
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        return self._postar_em(
            f"{API}/media/upload",
            files={"media": (arquivo.name, arquivo.read_bytes(), tipo)},
            data={"media_category": "tweet_image"},
        )

    def postar(self, texto: str, *, responder_a: str | None = None, imagens: Sequence[str] = ()) -> str:
        """Publica e devolve o id do post; `responder_a` só vale para post da própria conta."""
        corpo: dict = {"text": texto}
        if responder_a:
            corpo["reply"] = {"in_reply_to_tweet_id": str(responder_a)}
        if imagens:
            corpo["media"] = {"media_ids": [str(imagem) for imagem in imagens]}
        return self._postar_em(f"{API}/tweets", json=corpo)

    def _postar_em(self, url: str, **opcoes) -> str:
        cabecalhos = {"Authorization": cabecalho_oauth("POST", url, self.chaves)}
        try:
            with httpx.Client(transport=self._rede, timeout=TEMPO_LIMITE_S) as cliente:
                resposta = cliente.post(url, headers=cabecalhos, **opcoes)
        except (httpx.ConnectError, httpx.ConnectTimeout) as erro:
            raise NaoSaiu(f"sem conexão com o X ({type(erro).__name__})") from erro
        except httpx.HTTPError as erro:
            raise SemConfirmacao(f"a conexão caiu no meio ({type(erro).__name__})") from erro
        try:
            dados = resposta.json()
        except ValueError:
            dados = {}
        if 400 <= resposta.status_code < 500:
            raise NaoSaiu(_motivo(resposta.status_code, dados))
        identificador = ((dados.get("data") or {}) if isinstance(dados, dict) else {}).get("id")
        if resposta.status_code >= 300 or not identificador:
            raise SemConfirmacao(_motivo(resposta.status_code, dados))
        return str(identificador)


def _motivo(status: int, dados: object) -> str:
    if not isinstance(dados, dict):
        return f"HTTP {status}"
    erros = dados.get("errors") if isinstance(dados.get("errors"), list) else []
    primeiro = erros[0] if erros and isinstance(erros[0], dict) else {}
    texto = dados.get("detail") or dados.get("title") or primeiro.get("message") or primeiro.get("detail") or ""
    return f"HTTP {status}: {str(texto)[:200]}" if texto else f"HTTP {status}"


def link_do_post(identificador: str) -> str:
    return f"https://x.com/i/web/status/{identificador}"
