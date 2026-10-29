r"""A vigia do Discord: pedido de trabalho e dúvida que ele sabe resolver viram rascunho no celular.

Em 28/10 ele entrou com a conta velozo_dev em servidores de lojistas e de vagas
(cacada/discord-comunidades-shopify.md) e pediu que o Whis lesse esses grupos e
montasse a proposta para o que cabe no que ele sabe fazer: Shopify, sites,
sistemas, design, bot de WhatsApp, servidor. A cada rodada da vigia de freelas,
o Whis abre no Chrome da caçada os canais listados em `cacada/discord.md`, lê as
mensagens novas e o Claude decide, para cada uma, se vale uma proposta (pedido de
trabalho pago), uma resposta (dúvida técnica num canal de conversa, que mostra
ele ativo sem se oferecer) ou nada. Cada rascunho chega no Telegram com o botão
"Enviar no Discord".

Nada sai sem o toque dele. A proposta vai por mensagem privada ao autor, porque os
canais de vaga proíbem responder no próprio canal (Devs For Hire bane); a resposta
vai como resposta à mensagem, no canal. Os termos do Discord não permitem
automatizar conta de usuário: ele sabe e escolheu o toque por mensagem (28/10),
então a leitura é de hora em hora no ritmo de gente e a escrita é sempre uma por toque.

Na primeira vez que um canal é lido, o que já está lá fica guardado como visto,
sem rascunho: só o que chega depois vira proposta. O estado fica em
`%LOCALAPPDATA%\whis\cacada\discord.json`.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import logging
import os
import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from . import navegador_logado as _logado
from .celular import Resposta
from .criterios_da_cacada import PASTA_CACADA
from .propostas_auto import Contexto

_log = logging.getLogger("whis.vigia_do_discord")

CAMINHO_DOS_CANAIS = f"{PASTA_CACADA}/discord.md"
NOME_DO_ESTADO = "discord.json"

PEDIDOS = "pedidos"
CONVERSA = "conversa"
TIPOS_DE_CANAL = (PEDIDOS, CONVERSA)

PROPOSTA = "proposta"
RESPOSTA = "resposta"

ESPERANDO = "esperando"
ENVIADA = "enviada"
INCERTA = "incerta"

PREFIXO_DO_TOQUE = "discord:"
ROTULO_DO_BOTAO = "Enviar no Discord"
NAO_ACHEI = "Não achei esse rascunho no Whis (ele guarda 30 dias); não mandei nada."

MENOR_MENSAGEM = 30
MENSAGENS_POR_CANAL = 20
IDADE_MAXIMA = timedelta(hours=48)
GUARDA_POR = timedelta(days=30)
LIMITE_DA_PROPOSTA = 1200
LIMITE_DA_RESPOSTA = 900
PAUSA_ENTRE_CANAIS_S = (3.0, 8.0)

_LINK_DO_CANAL = re.compile(r"https://discord\.com/channels/(\d+)/(\d+)/?")
_LINHA_DO_CANAL = re.compile(r"^\s*[-*]\s*(?P<nome>[^:]+?)\s*:\s*(?P<link>https://discord\.com/channels/\d+/\d+/?)\s+(?P<tipo>\w+)\s*$")


# -- os canais e as mensagens ---------------------------------------------------------------------


@dataclass(frozen=True)
class Canal:
    nome: str
    servidor: str
    id: str
    tipo: str

    @property
    def url(self) -> str:
        return f"https://discord.com/channels/{self.servidor}/{self.id}"


def ler_canais(vault: Path) -> tuple[Canal, ...]:
    """Os canais de `cacada/discord.md`, uma linha cada: `- Nome: https://discord.com/channels/<servidor>/<canal> pedidos`."""
    arquivo = Path(vault) / CAMINHO_DOS_CANAIS
    if not arquivo.is_file():
        return ()
    canais = []
    for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
        casou = _LINHA_DO_CANAL.match(linha)
        if casou is None or casou["tipo"].casefold() not in TIPOS_DE_CANAL:
            continue
        servidor, canal = _LINK_DO_CANAL.match(casou["link"]).groups()
        canais.append(Canal(casou["nome"].strip(), servidor, canal, casou["tipo"].casefold()))
    return tuple(canais)


@dataclass(frozen=True)
class Mensagem:
    id: str
    canal: str
    autor: str
    quando: datetime | None
    texto: str
    bot: bool = False


_ITEM = re.compile(r'<li\b[^>]*\bid="chat-messages-(\d+)-(\d+)"', re.I)
_AUTOR = re.compile(r'id="message-username-\d+".*?\bdata-text="([^"]*)"', re.S)
_HORA = re.compile(r'<time\b[^>]*\bdatetime="([^"]+)"')
_CONTEUDO = re.compile(r'<div\b[^>]*\bid="message-content-\d+"[^>]*>')
_DIV = re.compile(r"<(/?)div\b[^>]*>", re.I)
_APP = re.compile(r'aria-label="(?:App Verificado|Verified App)"|>APP</span>')
_QUEBRA = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")


def ler_mensagens(pagina: str) -> tuple[Mensagem, ...]:
    """As mensagens de um canal de texto, na ordem da tela; a que vem colada na anterior herda o autor dela."""
    itens = list(_ITEM.finditer(pagina))
    mensagens = []
    autor = ""
    bot = False
    for posicao, item in enumerate(itens):
        fim = itens[posicao + 1].start() if posicao + 1 < len(itens) else len(pagina)
        trecho = pagina[item.start() : fim]
        casou = _AUTOR.search(trecho)
        if casou is not None:
            autor = _html.unescape(casou[1]).strip()
            bot = _APP.search(trecho) is not None
        conteudo = _CONTEUDO.search(trecho)
        hora = _HORA.search(trecho)
        mensagens.append(
            Mensagem(
                id=item[2],
                canal=item[1],
                autor=autor,
                quando=_quando(hora[1]) if hora else None,
                texto=_texto(_dentro_da_div(trecho, conteudo.end())) if conteudo else "",
                bot=bot,
            )
        )
    return tuple(mensagens)


def _dentro_da_div(trecho: str, inicio: int) -> str:
    """O que vai de `inicio` até o `</div>` que fecha a div aberta logo antes; o resto do item fica de fora."""
    profundidade = 1
    for tag in _DIV.finditer(trecho, inicio):
        profundidade += -1 if tag[1] else 1
        if profundidade == 0:
            return trecho[inicio : tag.start()]
    return trecho[inicio:]


def _quando(valor: str) -> datetime | None:
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def _texto(corpo: str) -> str:
    texto = _html.unescape(_TAG.sub("", _QUEBRA.sub("\n", corpo))).replace("⁠", "")
    return "\n".join(linha.rstrip() for linha in texto.strip().splitlines())


def link_da_mensagem(canal: Canal, mensagem: Mensagem) -> str:
    return f"{canal.url}/{mensagem.id}"


# -- o Claude --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rascunho:
    mensagem: str
    tipo: str
    texto: str
    motivo: str = ""


class Escritor(Protocol):
    def escrever(self, canal: Canal, mensagens: Sequence[Mensagem], contexto: Contexto) -> Sequence[Rascunho]: ...


_IA = re.compile(r"\b(?:AI|A\.I\.|IA|GPT|LLMs?|ChatGPT|Claude|Copilot|OpenAI|Gemini)\b|artificial intelligence|intelig[êe]ncia artificial", re.I)
_LINK = re.compile(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:com|dev|io|br|net|app)\b", re.I)
_CONTATO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+\d{2}\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")


def problemas(rascunho: Rascunho, canal: Canal, mensagem: Mensagem) -> list[str]:
    """O que barra o rascunho antes do celular: tipo que o canal não aceita, IA citada, link ou contato onde não cabe."""
    achados = []
    texto = rascunho.texto.strip()
    if not texto:
        achados.append("texto vazio")
    if rascunho.tipo not in (PROPOSTA, RESPOSTA):
        achados.append(f"tipo desconhecido ({rascunho.tipo})")
    if canal.tipo == PEDIDOS and rascunho.tipo == RESPOSTA:
        achados.append("canal de pedidos não aceita resposta no canal")
    if rascunho.tipo == PROPOSTA and not mensagem.autor:
        achados.append("a mensagem não mostra o autor, e a proposta vai por mensagem privada")
    if _IA.search(texto) and not _IA.search(mensagem.texto):
        achados.append("cita IA sem o pedido falar de IA")
    limite = LIMITE_DA_PROPOSTA if rascunho.tipo == PROPOSTA else LIMITE_DA_RESPOSTA
    if len(texto) > limite:
        achados.append(f"passa de {limite} caracteres")
    if rascunho.tipo == RESPOSTA and _LINK.search(texto):
        achados.append("resposta no canal com link (os servidores tratam como autopromoção)")
    if _CONTATO.search(texto):
        achados.append("e-mail ou telefone no texto")
    return achados


# -- o estado ----------------------------------------------------------------------------------------


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


@dataclass
class _Estado:
    arquivo: Path
    canais: dict[str, str] = field(default_factory=dict)
    vistas: dict[str, str] = field(default_factory=dict)
    rascunhos: dict[str, dict] = field(default_factory=dict)
    avisos: dict[str, str] = field(default_factory=dict)

    @classmethod
    def ler(cls, arquivo: Path) -> _Estado:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
        except (OSError, ValueError) as erro:
            _log.warning("Discord: o estado %s não abriu (%s); começando sem nada.", arquivo, erro)
            dados = {}
        if not isinstance(dados, dict):
            dados = {}
        return cls(
            arquivo,
            {str(k): str(v) for k, v in (dados.get("canais") or {}).items()},
            {str(k): str(v) for k, v in (dados.get("vistas") or {}).items()},
            {str(k): v for k, v in (dados.get("rascunhos") or {}).items() if isinstance(v, dict)},
            {str(k): str(v) for k, v in (dados.get("avisos") or {}).items()},
        )

    def guardar(self, agora: datetime) -> None:
        limite = (agora - GUARDA_POR).isoformat()
        dados = {
            "canais": self.canais,
            "vistas": {chave: quando for chave, quando in self.vistas.items() if quando >= limite},
            "rascunhos": {chave: r for chave, r in self.rascunhos.items() if str(r.get("quando", "")) >= limite},
            "avisos": self.avisos,
        }
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_name(self.arquivo.name + ".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, self.arquivo)

    def do_dia(self, agora: datetime) -> int:
        dia = agora.date().isoformat()
        return sum(1 for r in self.rascunhos.values() if str(r.get("quando", ""))[:10] == dia)

    def avisar_uma_vez(self, chave: str, agora: datetime) -> bool:
        dia = agora.date().isoformat()
        if self.avisos.get(chave) == dia:
            return False
        self.avisos[chave] = dia
        return True


def chave_do_toque(mensagem: str) -> str:
    return PREFIXO_DO_TOQUE + hashlib.sha1(mensagem.encode()).hexdigest()[:12]


# -- a rodada -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rodada:
    rascunhos: tuple[dict, ...] = ()
    novos_canais: tuple[str, ...] = ()
    parou: str = ""


def rodar(
    canais: Sequence[Canal],
    *,
    sessao: _logado.SessaoLogada,
    escritor: Escritor,
    contexto: Contexto,
    estado: Path,
    celular: Callable[..., bool],
    por_dia: int,
    agora: datetime | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> Rodada:
    """Lê cada canal, guarda o que é novo e manda ao celular os rascunhos que passam, até `por_dia` no dia."""
    agora = (agora or datetime.now()).astimezone()
    memoria = _Estado.ler(estado)
    if not sessao.logado(_logado.DISCORD):
        motivo = sessao.motivo or _logado.DESLOGADO
        if memoria.avisar_uma_vez("login", agora):
            celular(f"Discord: {_logado.frase_do_estado(_logado.DISCORD, motivo)}. A vigia do Discord parou até lá.")
        memoria.guardar(agora)
        return Rodada(parou=f"Discord {motivo}")
    feitos: list[dict] = []
    novos: list[str] = []
    for posicao, canal in enumerate(canais):
        if posicao:
            dormir(random.uniform(*PAUSA_ENTRE_CANAIS_S))
        try:
            mensagens = ler_mensagens(sessao.html_do_discord(canal.url))
        except _logado.SemNavegador as erro:
            _log.info("Discord: o canal %s não abriu: %s", canal.nome, erro)
            continue
        if canal.id not in memoria.canais:
            memoria.canais[canal.id] = agora.isoformat()
            for mensagem in mensagens:
                memoria.vistas[mensagem.id] = agora.isoformat()
            novos.append(canal.nome)
            continue
        frescas = [m for m in mensagens if m.id not in memoria.vistas]
        for mensagem in frescas:
            memoria.vistas[mensagem.id] = agora.isoformat()
        candidatas = [m for m in frescas if _vale_ler(m, agora)][-MENSAGENS_POR_CANAL:]
        if not candidatas or memoria.do_dia(agora) >= por_dia:
            continue
        por_id = {m.id: m for m in candidatas}
        for rascunho in escritor.escrever(canal, candidatas, contexto):
            mensagem = por_id.get(rascunho.mensagem)
            if mensagem is None or memoria.do_dia(agora) >= por_dia:
                continue
            achados = problemas(rascunho, canal, mensagem)
            if achados:
                _log.info("Discord: rascunho para %s barrado: %s", link_da_mensagem(canal, mensagem), "; ".join(achados))
                continue
            dados = _guardar_rascunho(memoria, canal, mensagem, rascunho, agora)
            celular(_mensagem_do_celular(dados), botoes=((ROTULO_DO_BOTAO, chave_do_toque(mensagem.id)),))
            feitos.append(dados)
    memoria.guardar(agora)
    return Rodada(rascunhos=tuple(feitos), novos_canais=tuple(novos))


def _vale_ler(mensagem: Mensagem, agora: datetime) -> bool:
    if mensagem.bot or len(mensagem.texto) < MENOR_MENSAGEM:
        return False
    return mensagem.quando is None or agora - mensagem.quando <= IDADE_MAXIMA


def _guardar_rascunho(memoria: _Estado, canal: Canal, mensagem: Mensagem, rascunho: Rascunho, agora: datetime) -> dict:
    dados = {
        "mensagem": mensagem.id,
        "canal": canal.id,
        "servidor": canal.servidor,
        "nome_do_canal": canal.nome,
        "autor": mensagem.autor,
        "pedido": mensagem.texto[:1500],
        "tipo": rascunho.tipo,
        "texto": rascunho.texto.strip(),
        "motivo": rascunho.motivo,
        "situacao": ESPERANDO,
        "quando": agora.isoformat(),
    }
    memoria.rascunhos[mensagem.id] = dados
    return dados


def _mensagem_do_celular(dados: dict) -> str:
    como = f"proposta por mensagem privada a {dados['autor']}" if dados["tipo"] == PROPOSTA else f"resposta a {dados['autor']} no canal"
    pedido = dados["pedido"] if len(dados["pedido"]) <= 400 else dados["pedido"][:400].rstrip() + "…"
    link = f"https://discord.com/channels/{dados['servidor']}/{dados['canal']}/{dados['mensagem']}"
    partes = [f"Discord · {dados['nome_do_canal']} · {como}", f"“{pedido}”", f"Rascunho:\n{dados['texto']}"]
    if dados.get("motivo"):
        partes.append(f"Por quê: {dados['motivo']}")
    partes.append(link)
    return "\n\n".join(partes)


# -- o toque ----------------------------------------------------------------------------------------------


def tocou_enviar(dados: str, *, abrir_sessao: Callable[[], _logado.SessaoLogada], estado: Path, agora: datetime | None = None) -> Resposta:
    """O toque em "Enviar no Discord": posta aquele rascunho pelo Chrome da caçada e diz como foi.

    Quem chama segura a trava do Chrome da caçada. Um envio que o Discord não confirmou vira `incerta`
    e nunca é repetido: ele confere no Discord.
    """
    agora = (agora or datetime.now()).astimezone()
    memoria = _Estado.ler(estado)
    chave = next((mensagem for mensagem in memoria.rascunhos if chave_do_toque(mensagem) == dados), None)
    if chave is None:
        return Resposta(NAO_ACHEI, tirar_botao=True)
    rascunho = memoria.rascunhos[chave]
    situacao = rascunho.get("situacao")
    if situacao == ENVIADA:
        return Resposta("Esse já foi para o Discord; não mandei de novo.", tirar_botao=True)
    if situacao == INCERTA:
        return Resposta("Esse já teve um envio que o Discord não confirmou: confira lá. Não mandei de novo.", tirar_botao=True)
    canal_url = f"https://discord.com/channels/{rascunho['servidor']}/{rascunho['canal']}"
    privado = rascunho.get("tipo") == PROPOSTA
    try:
        with abrir_sessao() as sessao:
            if not sessao.logado(_logado.DISCORD):
                motivo = sessao.motivo or _logado.DESLOGADO
                return Resposta(f"Não mandei: {_logado.frase_do_estado(_logado.DISCORD, motivo)}.")
            confirmada = sessao.postar_no_discord(canal_url, rascunho["mensagem"], rascunho["texto"], privado=privado)
    except _logado.SemNavegador as erro:
        return Resposta(f"Não mandei: {erro}. Toque de novo depois, ou responda à mão pelo link.")
    rascunho["situacao"] = ENVIADA if confirmada else INCERTA
    rascunho["enviada"] = agora.isoformat()
    memoria.guardar(agora)
    onde = f"por mensagem privada a {rascunho.get('autor')}" if privado else f"no canal {rascunho.get('nome_do_canal')}"
    if confirmada:
        return Resposta(f"Mandei {onde}.", tirar_botao=True)
    return Resposta(f"Escrevi e apertei Enter {onde}, mas não vi a mensagem na tela: confira no Discord.", tirar_botao=True)
