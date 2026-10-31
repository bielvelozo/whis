r"""A vigia do X: quem posta que precisa de alguém para a loja Shopify vira rascunho de resposta no celular.

Em 30/10 ele abriu uma conta do X para a velozo.dev, em inglês, e pediu que o Whis achasse quem está
contratando, como já faz no Discord e na 99Freelas. A cada 3 horas, das 9 às 22, dentro da rodada da vigia
de freelas, o Whis abre as buscas de `cacada/x/buscas.md` (aba Mais recentes) no Chrome do jornal, que lê
o X logado na conta principal dele (ADR 0003, só leitura). Sai quem oferece serviço, o post com mais de
48 h, o que já foi visto e o autor que já recebeu rascunho na semana; o Claude decide quais posts são de
quem contrata e escreve a resposta na voz dele. Cada rascunho chega no Telegram com o link do post e o
texto num bloco que copia num toque.

Ele responde à mão, da conta da velozo.dev. O Whis nunca responde, menciona, manda mensagem, segue nem
curte no X: automatizar isso derruba a conta e é contra as regras de automação do X. A API também não
deixa: desde 23/02/2026 ela só aceita resposta quando o autor do post marcou ou citou a conta. A resposta
chega com o botão "Responder no X", um link de intent do X (`x.com/intent/tweet` com `in_reply_to` e o
texto), que abre o X com a resposta pronta na conta ativa do app; quem aperta Post é ele. O texto continua no
bloco que copia num toque, para quando o app abrir sem ele. `[cacada].x_botao_responder` desliga o botão.
A DM fica só no copiar e colar: o link de DM pede o id numérico do autor, e o leitor guarda o @.

O estado fica em `%LOCALAPPDATA%\whis\cacada\x.json`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode

from .criterios_da_cacada import PASTA_CACADA
from .fonte_x import ErroDoX, LoginDoXVenceu, PortaDoX, PostDoX
from .fontes_do_jornal import FonteDoX
from .propostas_auto import Contexto

_log = logging.getLogger("whis.vigia_do_x")

CAMINHO_DAS_BUSCAS = f"{PASTA_CACADA}/x/buscas.md"
NOME_DO_ESTADO = "x.json"

RESPOSTA = "resposta"
DM = "dm"

INTERVALO = timedelta(hours=3)
#: A rodada da vigia de freelas chega aqui alguns minutos depois da hora cheia, e nunca no mesmo minuto.
FOLGA_DO_INTERVALO = timedelta(minutes=20)
PRIMEIRA_HORA = 9
ULTIMA_HORA = 22

IDADE_MAXIMA = timedelta(hours=48)
AUTOR_DESCANSA = timedelta(days=7)
GUARDA_POR = timedelta(days=30)
MENOR_POST = 30
POSTS_POR_RODADA = 25
#: O X corta em 280 caracteres a resposta de quem não assina o Premium.
LIMITE_DA_RESPOSTA = 280
LIMITE_DA_DM = 600
TAMANHO_DO_POST_NO_CELULAR = 400
ROTULO_DO_BOTAO = "Responder no X"
INTENT_DO_X = "https://x.com/intent/tweet"

_LINHA_DA_BUSCA = re.compile(r"^\s*[-*]\s*(?P<nome>[^:`]+?)\s*:\s*`?(?P<consulta>.+?)`?\s*$")

#: Inspirado no filtro do fórum da Shopify (`fontes_da_cacada.QUEM_OFERECE`), mas sem o "available" solto:
#: no X, "budget available" e "role available" são de quem contrata.
QUEM_OFERECE = re.compile(
    r"\bI help\b|\bwe help\b|what I offer|\bhire me\b|\bmy services\b|\bour services\b|\bI can help\b"
    r"|\bI(?:['’]m| am) (?:an? )?(?:experienced |expert |certified |professional |freelance )*"
    r"(?:shopify|e-?commerce|web|wordpress|frontend|full[ -]?stack|ux|ui) ?(?:developer|dev|expert|designer|freelancer|specialist)"
    r"|\b(?:I|we) (?:build|design|develop|create) (?:shopify|custom|high[- ]converting|stunning|stores|websites|sites|landing)"
    r"|\bI will (?:build|design|create|develop|set ?up|fix|redesign)\b"
    r"|\bopen (?:for|to) (?:work|projects|new (?:clients|projects))"
    r"|#opentowork|available for (?:new )?(?:work|projects|hire|freelance)|\bI['’]?m available\b|look no further"
    r"|^\W*(?:are you )?(?:looking for|need|searching for) (?:an? )?[\w -]{0,30}shopify[^?.!\n]{0,40}\?"
    r"|free trial task|side hustle|\bfiverr\.com|\b(?:my|our) (?:course|mentorship)\b"
    r"|posso (?:te |lhe )?ajudar|\bfaço (?:sua|seu|lojas?|sites?)\b|\bcrio (?:sua|seu|lojas?|sites?)\b"
    r"|or[cç]amento sem compromisso",
    re.IGNORECASE | re.MULTILINE,
)
_AUTOR_QUE_OFERECE = re.compile(r"shopify|webdesign|freelanc", re.IGNORECASE)


@dataclass(frozen=True)
class Busca:
    nome: str
    consulta: str


def ler_buscas(vault: Path) -> tuple[Busca, ...]:
    """As buscas de `cacada/x/buscas.md`, uma por linha: `- Nome: consulta do X`."""
    arquivo = Path(vault) / CAMINHO_DAS_BUSCAS
    if not arquivo.is_file():
        return ()
    buscas = []
    for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
        casou = _LINHA_DA_BUSCA.match(linha)
        if casou is not None:
            buscas.append(Busca(casou["nome"].strip(), casou["consulta"].strip()))
    return tuple(buscas)


def oferece_servico(post: PostDoX) -> bool:
    return bool(QUEM_OFERECE.search(post.texto)) or bool(_AUTOR_QUE_OFERECE.search(post.autor))


def id_do_post(post: PostDoX) -> str:
    return post.link.rstrip("/").rsplit("/", 1)[-1]


def na_hora(estado: Path, agora: datetime | None = None) -> bool:
    """Das 9 às 22, e 3 horas depois da última leitura que deu certo."""
    agora = (agora or datetime.now()).astimezone()
    if not PRIMEIRA_HORA <= agora.hour <= ULTIMA_HORA:
        return False
    ultima = _Estado.ler(estado).ultima_leitura
    return ultima is None or agora - ultima >= INTERVALO - FOLGA_DO_INTERVALO


# -- o rascunho --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rascunho:
    post: str
    tipo: str
    texto: str
    motivo: str = ""


class Escritor(Protocol):
    def escrever(self, posts: Sequence[PostDoX], contexto: Contexto, voz: str) -> Sequence[Rascunho]: ...


_IA = re.compile(r"\b(?:AI|A\.I\.|IA|GPT|LLMs?|ChatGPT|Claude|Copilot|OpenAI|Gemini)\b|artificial intelligence|intelig[êe]ncia artificial", re.I)
_LINK = re.compile(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:com|dev|io|br|net|app|co|me|store|shop)\b", re.I)
_CONTATO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+\d{1,3}\s?\(?\d{2,3}\)?\s?\d{4,5}[-\s]?\d{4}")
_PRECO = re.compile(
    r"[$€£]\s*\d|R\$|\d\s*(?:usd|brl|reais|dollars|bucks)\b|\bper hour\b|/\s*h(?:ou)?r\b|\bpor hora\b|\bhourly rate\b", re.I
)
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")
_HASHTAG = re.compile(r"(?<![\w&])#\w")
_CALL = re.compile(r"\bcall\b|\bzoom\b|\bmeeting\b|reuni[ãa]o|\bligação\b", re.I)
_NUNCA = re.compile(r"faz sentido|make sense\?|makes sense\?", re.I)


def problemas(rascunho: Rascunho, post: PostDoX) -> list[str]:
    """O que barra o rascunho antes do celular: tamanho do X, link, preço, IA, contato, emoji, call e o fim sem pergunta."""
    texto = rascunho.texto.strip()
    if not texto:
        return ["texto vazio"]
    achados = []
    if rascunho.tipo not in (RESPOSTA, DM):
        achados.append(f"tipo desconhecido ({rascunho.tipo})")
    limite = LIMITE_DA_RESPOSTA if rascunho.tipo == RESPOSTA else LIMITE_DA_DM
    if len(texto) > limite:
        achados.append(f"passa de {limite} caracteres")
    if _LINK.search(texto):
        achados.append("tem link (o velozo.dev fica no perfil)")
    if _PRECO.search(texto):
        achados.append("fala de preço")
    if _IA.search(texto) and not _IA.search(post.texto):
        achados.append("cita IA sem o post falar de IA")
    if _CONTATO.search(texto):
        achados.append("e-mail ou telefone no texto")
    if _EMOJI.search(texto):
        achados.append("tem emoji")
    if _HASHTAG.search(texto):
        achados.append("tem hashtag")
    if _CALL.search(texto):
        achados.append("pede call")
    if _NUNCA.search(texto):
        achados.append('usa "faz sentido"')
    if not texto.endswith("?"):
        achados.append("não termina em pergunta")
    return achados


# -- o estado ----------------------------------------------------------------------------------------


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


@dataclass
class _Estado:
    arquivo: Path
    ultima_leitura: datetime | None = None
    vistos: dict[str, str] = field(default_factory=dict)
    autores: dict[str, str] = field(default_factory=dict)
    rascunhos: dict[str, dict] = field(default_factory=dict)
    avisos: dict[str, str] = field(default_factory=dict)

    @classmethod
    def ler(cls, arquivo: Path) -> _Estado:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
        except (OSError, ValueError) as erro:
            _log.warning("X: o estado %s não abriu (%s); começando sem nada.", arquivo, erro)
            dados = {}
        if not isinstance(dados, dict):
            dados = {}
        try:
            ultima = datetime.fromisoformat(dados["ultima_leitura"]) if dados.get("ultima_leitura") else None
        except (TypeError, ValueError):
            ultima = None
        return cls(
            arquivo,
            ultima,
            {str(k): str(v) for k, v in (dados.get("vistos") or {}).items()},
            {str(k): str(v) for k, v in (dados.get("autores") or {}).items()},
            {str(k): v for k, v in (dados.get("rascunhos") or {}).items() if isinstance(v, dict)},
            {str(k): str(v) for k, v in (dados.get("avisos") or {}).items()},
        )

    def guardar(self, agora: datetime) -> None:
        limite = (agora - GUARDA_POR).isoformat()
        dados = {
            "ultima_leitura": self.ultima_leitura.isoformat() if self.ultima_leitura else None,
            "vistos": {chave: quando for chave, quando in self.vistos.items() if quando >= limite},
            "autores": {chave: quando for chave, quando in self.autores.items() if quando >= limite},
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

    def autor_descansando(self, autor: str, agora: datetime) -> bool:
        quando = self.autores.get(autor.casefold())
        return quando is not None and quando >= (agora - AUTOR_DESCANSA).isoformat()

    def avisar_uma_vez(self, chave: str, agora: datetime) -> bool:
        dia = agora.date().isoformat()
        if self.avisos.get(chave) == dia:
            return False
        self.avisos[chave] = dia
        return True


# -- a rodada -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rodada:
    lidos: int = 0
    candidatos: int = 0
    rascunhos: tuple[dict, ...] = ()
    falhas: tuple[str, ...] = ()
    parou: str = ""


def rodar(
    buscas: Sequence[Busca],
    *,
    leitor: PortaDoX,
    escritor: Escritor,
    contexto: Contexto,
    voz: str,
    estado: Path,
    celular: Callable[..., bool],
    por_dia: int,
    agora: datetime | None = None,
    botao: bool = True,
) -> Rodada:
    """Lê as buscas, tira o que não serve e manda ao celular os rascunhos que passam, até `por_dia` no dia.

    `botao` põe "Responder no X" embaixo da resposta; a DM nunca tem botão (o link de DM pede o id do autor).
    """
    agora = (agora or datetime.now()).astimezone()
    memoria = _Estado.ler(estado)
    if memoria.do_dia(agora) >= por_dia:
        return Rodada(parou=f"os {por_dia} rascunhos de hoje já saíram")
    fontes = [FonteDoX(busca.nome, "recentes", busca.consulta) for busca in buscas]
    try:
        leitura = leitor.ler(fontes, agora.date())
    except LoginDoXVenceu:
        memoria.ultima_leitura = agora
        if memoria.avisar_uma_vez("login", agora):
            celular("X: o login do Chrome do jornal caiu. Rode <code>python -m whis x-login</code> no note; a vigia do X parou até lá.")
        memoria.guardar(agora)
        return Rodada(parou="o X pediu login")
    except ErroDoX as erro:
        return Rodada(parou=str(erro))
    memoria.ultima_leitura = agora
    if leitura.falhas and not leitura.posts and memoria.avisar_uma_vez("falha", agora):
        celular("X: nenhuma busca da vigia abriu hoje (a página do X pode ter mudado). Os detalhes ficam no log do Whis.")
    lidos = _unicos(post for posts in leitura.posts.values() for post in posts)
    candidatos = [post for post in lidos if _vale_ler(post, memoria, agora)]
    candidatos.sort(key=lambda post: post.data, reverse=True)
    candidatos = candidatos[:POSTS_POR_RODADA]
    feitos: list[dict] = []
    if candidatos:
        por_id = {id_do_post(post): post for post in candidatos}
        for rascunho in escritor.escrever(candidatos, contexto, voz):
            post = por_id.pop(rascunho.post, None)
            if post is None or memoria.do_dia(agora) >= por_dia:
                continue
            achados = problemas(rascunho, post)
            if achados:
                _log.info("X: rascunho para %s barrado: %s", post.link, "; ".join(achados))
                continue
            dados = _guardar_rascunho(memoria, post, rascunho, agora)
            botoes = ((ROTULO_DO_BOTAO, link_da_resposta(dados)),) if botao and dados["tipo"] == RESPOSTA else ()
            if not celular(mensagem_no_celular(dados, agora), botoes=botoes):
                _log.warning("X: o rascunho para %s não chegou ao celular.", post.link)
            feitos.append(dados)
    for post in lidos:
        memoria.vistos[id_do_post(post)] = agora.isoformat()
    memoria.guardar(agora)
    return Rodada(
        lidos=len(lidos), candidatos=len(candidatos), rascunhos=tuple(feitos), falhas=tuple(f"{nome}: {motivo}" for nome, motivo in leitura.falhas.items())
    )


def _unicos(posts: Iterable[PostDoX]) -> list[PostDoX]:
    por_id: dict[str, PostDoX] = {}
    for post in posts:
        por_id.setdefault(id_do_post(post), post)
    return list(por_id.values())


def _vale_ler(post: PostDoX, memoria: _Estado, agora: datetime) -> bool:
    if id_do_post(post) in memoria.vistos or len(post.texto) < MENOR_POST:
        return False
    if not agora - IDADE_MAXIMA <= post.data <= agora + timedelta(hours=1):
        return False
    return not oferece_servico(post) and not memoria.autor_descansando(post.autor, agora)


def _guardar_rascunho(memoria: _Estado, post: PostDoX, rascunho: Rascunho, agora: datetime) -> dict:
    dados = {
        "link": post.link,
        "autor": post.autor,
        "post": post.texto[:1500],
        "postado": post.data.isoformat(),
        "tipo": rascunho.tipo,
        "texto": rascunho.texto.strip(),
        "motivo": rascunho.motivo,
        "quando": agora.isoformat(),
    }
    memoria.rascunhos[id_do_post(post)] = dados
    memoria.autores[post.autor.casefold()] = agora.isoformat()
    return dados


def link_da_resposta(dados: dict) -> str:
    """O intent do X que abre a caixa de resposta ao post com o texto já escrito."""
    numero = dados["link"].rstrip("/").rsplit("/", 1)[-1]
    return f"{INTENT_DO_X}?{urlencode({'in_reply_to': numero, 'text': dados['texto']}, quote_via=quote)}"


def mensagem_no_celular(dados: dict, agora: datetime) -> str:
    horas = max(0, int((agora - datetime.fromisoformat(dados["postado"])).total_seconds() // 3600))
    idade = "agora há pouco" if horas == 0 else f"há {horas} h"
    como = "responder no post" if dados["tipo"] == RESPOSTA else "mandar por DM"
    post = dados["post"] if len(dados["post"]) <= TAMANHO_DO_POST_NO_CELULAR else dados["post"][:TAMANHO_DO_POST_NO_CELULAR].rstrip() + "…"
    linhas = [
        f"<b>X</b> · @{escape(dados['autor'])} · {idade} · {como}",
        f"“{escape(post, quote=False)}”",
        escape(dados["link"]),
        "",
        f"<pre>{escape(dados['texto'], quote=False)}</pre>",
    ]
    if dados.get("motivo"):
        linhas.append(f"<i>{escape(dados['motivo'])}</i>")
    return "\n".join(linhas)
