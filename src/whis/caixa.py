"""A caixa do Gmail dedicado: só leitura, por IMAP com senha de app (research 02c).

Duas coisas saem dela. **Confirmação de conta**: o link de um e-mail cujo
remetente e cujo link são do domínio de um site onde o próprio Whis registrou
a intenção de criar conta é seguido sozinho — e só esse. **O resto vira lista**
no relatório da caçada (resposta de cliente, de recrutador, entrevista): ler é
com ele, responder também.

`EXAMINE` e `BODY.PEEK[]`: nada é marcado como lido, nada é apagado, nada é
enviado. O texto dos e-mails é de terceiros: aqui não há modelo nenhum, e um
link só é seguido pela regra acima, escrita em código.
"""

from __future__ import annotations

import email
import imaplib
import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

import httpx

from .oportunidades import texto_limpo
from .politica import casa, dominio

_log = logging.getLogger("whis.caixa")

SERVIDOR = "imap.gmail.com"
DIAS_LIDOS = 14
MAXIMO_DE_MENSAGENS = 200
_CONFIRMACAO = re.compile(r"confirm|verif|ativ|activate|valide|validar", re.I)
_LINK = re.compile(r"https?://[^\s\"'<>)]+")


@dataclass(frozen=True)
class Mensagem:
    remetente: str
    assunto: str
    quando: str
    texto: str
    links: tuple[str, ...] = ()

    @property
    def dominio(self) -> str:
        return self.remetente.rsplit("@", 1)[-1].lower() if "@" in self.remetente else ""


class ErroDaCaixa(RuntimeError):
    """A caixa não abriu: sem senha de app, senha recusada, IMAP desligado, sem rede."""


def ler_caixa(
    endereco: str,
    senha_de_app: str,
    *,
    desde: datetime | None = None,
    conectar: Callable[[str], imaplib.IMAP4] | None = None,
) -> tuple[Mensagem, ...]:
    if not endereco or not senha_de_app:
        raise ErroDaCaixa("preencha [cacada].email e [cacada].senha_de_app (senha de app do Google)")
    desde = desde or datetime.now() - timedelta(days=DIAS_LIDOS)
    try:
        imap = (conectar or (lambda servidor: imaplib.IMAP4_SSL(servidor)))(SERVIDOR)
        imap.login(endereco, senha_de_app)
    except (imaplib.IMAP4.error, OSError) as erro:
        raise ErroDaCaixa(f"o Gmail recusou a entrada: {erro}") from erro
    try:
        imap.select("INBOX", readonly=True)
        _, dados = imap.search(None, "SINCE", desde.strftime("%d-%b-%Y"))
        numeros = (dados[0] or b"").split()[-MAXIMO_DE_MENSAGENS:]
        mensagens = []
        for numero in numeros:
            _, partes = imap.fetch(numero, "(BODY.PEEK[])")
            bruto = next((p[1] for p in partes if isinstance(p, tuple)), None)
            if bruto:
                mensagens.append(interpretar(bruto))
        return tuple(mensagens)
    except imaplib.IMAP4.error as erro:
        raise ErroDaCaixa(f"a leitura da caixa falhou: {erro}") from erro
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


def interpretar(bruto: bytes) -> Mensagem:
    mensagem = email.message_from_bytes(bruto)
    texto, html = "", ""
    for parte in mensagem.walk() if mensagem.is_multipart() else [mensagem]:
        tipo = parte.get_content_type()
        if parte.get_content_maintype() == "multipart":
            continue
        carga = parte.get_payload(decode=True) or b""
        conteudo = carga.decode(parte.get_content_charset() or "utf-8", errors="replace")
        if tipo == "text/plain" and not texto:
            texto = conteudo
        elif tipo == "text/html" and not html:
            html = conteudo
    links = tuple(dict.fromkeys(_LINK.findall(html or texto)))
    try:
        quando = parsedate_to_datetime(mensagem.get("Date", "")).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        quando = ""
    return Mensagem(
        remetente=parseaddr(mensagem.get("From", ""))[1].lower(),
        assunto=str(make_header(decode_header(mensagem.get("Subject", "")))),
        quando=quando,
        texto=(texto or texto_limpo(html))[:2000],
        links=tuple(link.rstrip(".,;") for link in links),
    )


def confirmacoes_seguras(mensagens: Iterable[Mensagem], dominios_com_intencao: Iterable[str]) -> list[tuple[Mensagem, str]]:
    """Os (e-mail, link) de confirmação que podem ser seguidos sozinhos.

    Só quando o assunto ou o texto falam de confirmar/verificar, o remetente é
    do domínio de um site onde o Whis registrou a intenção de criar conta, e o
    link é do mesmo domínio. Um por e-mail: o primeiro que casa.
    """
    dominios = tuple(d.lower().removeprefix("www.") for d in dominios_com_intencao if d)
    seguras = []
    for mensagem in mensagens:
        if not _CONFIRMACAO.search(f"{mensagem.assunto} {mensagem.texto[:500]}"):
            continue
        if not casa(mensagem.dominio, dominios):
            continue
        link = next((l for l in mensagem.links if casa(dominio(l), dominios) and _CONFIRMACAO.search(l)), None)
        link = link or next((l for l in mensagem.links if casa(dominio(l), dominios)), None)
        if link:
            seguras.append((mensagem, link))
    return seguras


def seguir(link: str, *, rede: httpx.BaseTransport | None = None) -> bool:
    try:
        with httpx.Client(transport=rede, timeout=30, follow_redirects=True) as cliente:
            resposta = cliente.get(link)
    except httpx.HTTPError as erro:
        _log.warning("A confirmação %s não abriu: %s", dominio(link), erro)
        return False
    return resposta.status_code < 400
