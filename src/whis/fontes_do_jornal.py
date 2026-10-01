"""`noticias/fontes.md`: as fontes, o time e os nomes do jornal, numa nota dele.

A nota é do usuário, como `prompts/`: o Whis cria uma vez, a partir do
modelo, e nunca mais escreve. Ele edita no Obsidian para tirar ou pôr fonte,
sem abrir TOML nem código. Por isso a leitura é tolerante: linha que não casa
o formato é ignorada com aviso no log, e o jornal sai com o que deu para ler.

Formato: uma seção por `##`, uma fonte por linha `- Nome: URL`. O título da
seção pode trazer o id interno entre parênteses e os limites de itens —
`## Tecnologia (tecnologia) · 3 a 5 itens`. `## Time` e `## Nomes` são
especiais e não viram seção do jornal. Uma página do X é `- Nome: x:seguindo`,
`- Nome: x:para-voce` ou `- Nome: x:busca <consulta>`; ela não é feed e não
conta para o jornal nascer.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import vault as _vault

_log = logging.getLogger("whis.fontes_do_jornal")

CAMINHO_DAS_FONTES = f"{_vault.PASTA_NOTICIAS}/fontes.md"

MINIMO_PADRAO = 3
MAXIMO_PADRAO = 5

MODELO_DAS_FONTES = """# Fontes do jornal

## Dev com IA (ia) · 4 a 6 itens
- X · Seguindo: x:seguindo
- X · Para você: x:para-voce
- X · Claude Code: x:busca "claude code" min_faves:100
- X · Outros harness: x:busca (codex OR cursor OR "gemini cli" OR opencode) (agent OR cli) min_faves:50
- X · Skills e hooks: x:busca (claude OR codex) (skills OR hooks OR subagents OR "slash commands" OR MCP) min_faves:50
- X · Contexto: x:busca ("context engineering" OR CLAUDE.md OR AGENTS.md OR "plan mode") min_faves:30
- X · Tokens e custo: x:busca ("prompt caching" OR "token usage" OR "context window" OR compact) (claude OR codex OR cursor) min_faves:10
- X · Fluxo de trabalho: x:busca ("agentic coding" OR "spec-driven" OR "parallel agents" OR worktrees) min_faves:30

## Tecnologia (tecnologia) · 3 a 5 itens
- Ars Technica: https://feeds.arstechnica.com/arstechnica/index
- The Verge: https://www.theverge.com/rss/index.xml
- The Register: https://www.theregister.com/headlines.atom
- Tom's Hardware: https://www.tomshardware.com/feeds/all
- Tecnoblog: https://tecnoblog.net/feed/
- Hacker News: https://news.ycombinator.com/rss

## Mundo (mundo) · 3 a 5 itens
- BBC World: https://feeds.bbci.co.uk/news/world/rss.xml
- The Guardian: https://www.theguardian.com/world/rss
- G1 Mundo: https://g1.globo.com/rss/g1/mundo/
- RFI Brasil: https://www.rfi.fr/br/rss
- Al Jazeera: https://www.aljazeera.com/xml/rss/all.xml

## Política no Brasil (brasil) · 3 a 5 itens
- G1 Política: https://g1.globo.com/rss/g1/politica/
- Estadão Política: https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/politica/?outputType=xml
- Folha Poder: https://feeds.folha.uol.com.br/poder/rss091.xml
- Agência Brasil: https://agenciabrasil.ebc.com.br/rss/politica/feed.xml
- Poder360: https://www.poder360.com.br/feed/

## Música (musica) · 3 a 6 itens
- Guitar World: https://www.guitarworld.com/feeds/all
- MusicRadar: https://www.musicradar.com/feeds/all
- Premier Guitar: https://www.premierguitar.com/feeds/feed.rss
- Gearnews: https://www.gearnews.com/feed/
- Guitar.com: https://guitar.com/feed/
- MusicTech: https://musictech.com/feed/
- Production Expert: https://www.production-expert.com/production-expert-1?format=rss
- Guitar Load: https://guitarload.com.br/feed/
- Stereogum: https://www.stereogum.com/feed/
- Consequence: https://consequence.net/feed/
- Relix: https://relix.com/feed/
- Jesus Freak Hideout: https://www.jesusfreakhideout.com/news/feed.xml
- YouTube · Nord Keyboards: https://www.youtube.com/feeds/videos.xml?channel_id=UCGrw4WarRRC66qQg8YHhrCw
- YouTube · Joe Satriani: https://www.youtube.com/feeds/videos.xml?channel_id=UCiynI3-MFYbiZ6FQqWNLh7w
- YouTube · Mateus Asato: https://www.youtube.com/feeds/videos.xml?channel_id=UCdJvnbX52LgGrmNvREvZZoQ
- YouTube · Rick Beato: https://www.youtube.com/feeds/videos.xml?channel_id=UCcp-HjtmTMeIJ-0RrSHSGLA
- YouTube · Andertons: https://www.youtube.com/feeds/videos.xml?channel_id=UCSNxIry_FPFcQDFRbi3VOAw

## Futebol (futebol) · 3 a 5 itens
- ge.globo: https://ge.globo.com/rss/ge/futebol/
- ge · internacional: https://ge.globo.com/rss/ge/futebol/futebol-internacional/
- BBC Sport: https://feeds.bbci.co.uk/sport/football/rss.xml
- Guardian Football: https://www.theguardian.com/football/rss
- Marca · Real Madrid: https://objetos.estaticos-marca.com/rss/futbol/real-madrid.xml

## Carros (carros) · 2 a 3 itens
- Autoesporte: https://autoesporte.globo.com/rss/autoesporte/
- Quatro Rodas: https://quatrorodas.abril.com.br/feed/
- Motor1 Brasil: https://motor1.uol.com.br/rss/news/all/
- Carscoops: https://www.carscoops.com/feed/
- Jalopnik: https://jalopnik.com/rss

## Time
- Corinthians: https://ge.globo.com/rss/ge/futebol/times/corinthians/

## Nomes
Joe Satriani, Steve Vai, Mateus Asato, Guthrie Govan, Cory Wong, Tim Henson, Nord, Studiologic,
Numa, Korg, Roland, Yamaha, Kemper, Neural DSP, Line 6, Fender, Gibson, PRS, Ibanez, Suhr,
Strandberg, Universal Audio, Focusrite
"""

_CABECALHO = re.compile(r"^##(?!#)\s*(?P<resto>.*?)\s*$")
_LIMITES = re.compile(r"\s*[·•|—–-]\s*(?P<minimo>\d+)\s*a\s*(?P<maximo>\d+)(?:\s*itens?)?\s*$", re.I)
_ID = re.compile(r"\s*\((?P<id>[^()]*)\)\s*$")
_LINHA_DE_FONTE = re.compile(r"^[-*+]\s+(?P<nome>.+?)\s*:\s*(?P<url>https?://\S+)\s*$", re.I)
_LINHA_DO_X = re.compile(r"^[-*+]\s+(?P<nome>.+?)\s*:\s*x:(?P<tipo>\S+)(?:\s+(?P<consulta>.+?))?\s*$", re.I)
_MARCADOR = re.compile(r"^[-*+]\s+")

TIPOS_DO_X = ("seguindo", "para-voce", "busca")

_TIME = "time"
_NOMES = "nomes"


@dataclass(frozen=True)
class Fonte:
    """Um feed: o nome que aparece no jornal e o endereço RSS ou Atom."""

    nome: str
    url: str


@dataclass(frozen=True)
class FonteDoX:
    """Uma página do X que o leitor visita: uma aba da home ou uma busca."""

    nome: str
    tipo: str
    consulta: str = ""


@dataclass(frozen=True)
class Secao:
    """Uma seção do jornal, com os limites de itens que o editor respeita."""

    id: str
    titulo: str
    minimo: int
    maximo: int
    fontes: tuple[Fonte, ...]
    x: tuple[FonteDoX, ...] = ()


@dataclass(frozen=True)
class FontesDoJornal:
    """O que `noticias/fontes.md` diz: seções na ordem do arquivo, time e nomes."""

    secoes: tuple[Secao, ...]
    time: Fonte | None
    nomes: tuple[str, ...]
    avisos: tuple[str, ...] = ()


def interpretar_fontes(texto: str) -> FontesDoJornal:
    """Lê o texto da nota. Nunca levanta: o que não casa vira aviso."""
    avisos: list[str] = []
    secoes: list[Secao] = []
    ids_vistos: set[str] = set()
    time: Fonte | None = None
    nomes: list[str] = []

    atual: dict | None = None
    especial: str | None = None
    ignorando = False

    def fechar() -> None:
        if atual is None:
            return
        if not atual["fontes"] and not atual["x"]:
            _avisar(avisos, f"Seção “{atual['titulo']}” sem nenhuma fonte válida; fica fora do jornal")
            return
        secoes.append(
            Secao(
                id=atual["id"],
                titulo=atual["titulo"],
                minimo=atual["minimo"],
                maximo=atual["maximo"],
                fontes=tuple(atual["fontes"]),
                x=tuple(atual["x"]),
            )
        )

    for numero, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta.strip()
        if not linha:
            continue

        cabecalho = _CABECALHO.match(linha)
        if cabecalho:
            fechar()
            atual, especial, ignorando = None, None, False
            titulo, id_, minimo, maximo = _ler_cabecalho(cabecalho["resto"])
            if not titulo:
                _avisar(avisos, f"Linha {numero}: seção sem título ignorada")
                ignorando = True
            elif id_ in (_TIME, _NOMES):
                especial = id_
            elif id_ in ids_vistos:
                _avisar(avisos, f"Linha {numero}: seção “{titulo}” repete o id “{id_}” e foi ignorada")
                ignorando = True
            else:
                ids_vistos.add(id_)
                atual = {"id": id_, "titulo": titulo, "minimo": minimo, "maximo": maximo, "fontes": [], "x": []}
            continue

        if linha.startswith("#") and not linha.startswith("##"):
            continue
        if ignorando:
            continue

        if especial == _NOMES:
            for nome in _MARCADOR.sub("", linha).split(","):
                nome = nome.strip()
                if nome and nome.casefold() not in {n.casefold() for n in nomes}:
                    nomes.append(nome)
            continue

        do_x = _LINHA_DO_X.match(linha)
        if do_x:
            tipo, consulta = do_x["tipo"].lower(), (do_x["consulta"] or "").strip()
            if tipo not in TIPOS_DO_X or (tipo == "busca") != bool(consulta):
                _avisar(
                    avisos,
                    f"Linha {numero} ignorada: “x:{do_x['tipo']}{' ' + consulta if consulta else ''}” "
                    f"não é x:seguindo, x:para-voce nem x:busca <consulta>",
                )
            elif especial == _TIME:
                _avisar(avisos, f"Linha {numero} ignorada: o time vem de um feed, não do X")
            elif atual is not None:
                atual["x"].append(FonteDoX(nome=do_x["nome"].strip(), tipo=tipo, consulta=consulta))
            else:
                _avisar(avisos, f"Linha {numero} ignorada: fonte do X fora de uma seção")
            continue

        fonte = _ler_fonte(linha)
        if fonte is None:
            _avisar(avisos, f"Linha {numero} ignorada (esperado “- Nome: URL”): {linha}")
        elif especial == _TIME:
            if time is None:
                time = fonte
            else:
                _avisar(avisos, f"Linha {numero} ignorada: o time é um só ({time.nome})")
        elif atual is not None:
            atual["fontes"].append(fonte)
        else:
            _avisar(avisos, f"Linha {numero} ignorada: fonte fora de uma seção")

    fechar()
    return FontesDoJornal(secoes=tuple(secoes), time=time, nomes=tuple(nomes), avisos=tuple(avisos))


def garantir_fontes(vault: Path) -> Path:
    """Cria `noticias/fontes.md` a partir do modelo, só se ainda não existir.

    Depois de criada, a nota é dele: nem uma nota vazia é reescrita.
    """
    caminho = Path(vault) / CAMINHO_DAS_FONTES
    if caminho.exists():
        return caminho
    _log.info("Criando %s a partir do modelo", CAMINHO_DAS_FONTES)
    return _vault.escrever(vault, CAMINHO_DAS_FONTES, MODELO_DAS_FONTES, zonas=_vault.ZONAS_DO_JORNAL)


def ler_fontes(vault: Path) -> FontesDoJornal:
    """Garante a nota e a interpreta."""
    caminho = garantir_fontes(vault)
    return interpretar_fontes(caminho.read_text(encoding="utf-8-sig"))


def _ler_cabecalho(resto: str) -> tuple[str, str, int, int]:
    minimo, maximo = MINIMO_PADRAO, MAXIMO_PADRAO
    limites = _LIMITES.search(resto)
    if limites:
        a, b = int(limites["minimo"]), int(limites["maximo"])
        minimo, maximo = min(a, b), max(a, b)
        resto = resto[: limites.start()]
    id_explicito = _ID.search(resto)
    if id_explicito:
        resto = resto[: id_explicito.start()]
    titulo = resto.strip()
    id_ = _slug(id_explicito["id"] if id_explicito and id_explicito["id"].strip() else titulo)
    return titulo, id_, minimo, maximo


def _ler_fonte(linha: str) -> Fonte | None:
    casou = _LINHA_DE_FONTE.match(linha)
    if not casou:
        return None
    return Fonte(nome=casou["nome"].strip(), url=casou["url"])


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _avisar(avisos: list[str], mensagem: str) -> None:
    _log.warning("%s: %s", CAMINHO_DAS_FONTES, mensagem)
    avisos.append(mensagem)
