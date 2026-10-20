r"""O tema de fábrica: a loja Shopify que usa um tema da loja de temas quase como ele vem.

Pedido dele em 19/10: além das lojas lentas, achar lojas com "um tema padrão, um tema
comprado sem personalização, por exemplo o Horizon", e oferecer um redesenho com a cara da
marca. "Sem a cara da marca" não se mede a olho, então o Whis compara a página inicial da
loja com a demonstração oficial do mesmo tema, que a loja de temas da Shopify mostra
(`data-demo-store-iframe-url-value` em themes.shopify.com/themes/<tema>):

- as fontes (as variáveis `--font-…family` e os `@font-face`);
- as cores (as variáveis `--color-…` de fundo, texto, botão e destaque, nome e valor);
- os tipos de seção da página inicial, na ordem.

É de fábrica o tema que veio da loja de temas (`theme_store_id`, ou um nome de tema público)
e bate com a demonstração nas cores e em mais uma das três: as cores são a primeira coisa que
uma marca troca, e o e-mail diz que a marca aparece pouco. O e-mail só cita o que bateu. A
demonstração muda pouco: a impressão dela fica guardada por 30 dias em
`%LOCALAPPDATA%\whis\cacada\temas-de-fabrica.json`. Um tema com várias predefinições é
comparado só com a demonstração principal; a loja que partiu de outra fica de fora (perde-se
uma, nunca se acusa à toa).
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_log = logging.getLogger("whis.tema_de_fabrica")

NOME_DO_ESTADO = "temas-de-fabrica.json"
VALIDADE_DA_DEMONSTRACAO = timedelta(days=30)
LOJA_DE_TEMAS = "https://themes.shopify.com/themes/{slug}"
IGUAIS_PARA_SER_DE_FABRICA = 2
SEMELHANCA_MINIMA = 0.8
FONTES = "fontes"
CORES = "cores"
SECOES = "secoes"

#: Temas da loja de temas da Shopify; um tema feito sob medida não traz `theme_store_id` nem um destes nomes.
TEMAS_DA_LOJA = frozenset({
    "dawn", "horizon", "sense", "craft", "refresh", "studio", "origin", "taste", "ride", "crave", "colorblock",
    "spotlight", "publisher", "trade", "fabric", "atelier", "tide", "savor", "heritage", "vessel", "dwell", "pitch",
    "impulse", "prestige", "impact", "turbo", "flow", "pipeline", "symmetry", "motion", "warehouse", "empire", "focal",
    "broadcast", "stiletto", "local", "expanse", "palo alto", "mojave", "be yours", "enterprise", "minimog", "kalles",
    "ella", "shrine", "wokiee", "debut", "brooklyn", "streamline", "release", "editions", "minimal", "supply",
})

_TEMA = re.compile(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", re.S)
_DEMONSTRACAO = re.compile(r'data-demo-store-iframe-url-value="(https://[^"]+)"')
_VAR_DE_FONTE = re.compile(r"--font-[\w-]*?family\s*:\s*([^;{}]+)[;}]", re.I)
_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*?font-family\s*:\s*([^;}]+)", re.I)
_VAR_DE_COR = re.compile(r"(--[\w-]*?(?:background|foreground|button|accent|text|link)[\w-]*)\s*:\s*([^;{}\"]+)", re.I)
_COR = re.compile(
    r"^(?:#[0-9a-f]{3,8}|(?:rgba?|hsla?)\([^)]*\)|\d{1,3}[ ,]+\d{1,3}[ ,]+\d{1,3}(?:\s*/\s*[\d.]+)?)$", re.I
)
_SECAO = re.compile(r'id="shopify-section-template--\d+__([\w-]+)"')
_SUFIXO_DA_SECAO = re.compile(r"_[A-Za-z0-9]{6}$")
_APP = re.compile(r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-|\d{6,}|[0-9a-f]{16,})", re.I)
_GENERICAS = frozenset({
    "sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui", "inherit", "initial", "unset", "-apple-system",
    "blinkmacsystemfont", "arial", "helvetica", "helvetica neue", "segoe ui", "roboto", "ui-sans-serif", "ui-serif",
})


@dataclass(frozen=True)
class DadosDoTema:
    """O que a loja diz do próprio tema em `Shopify.theme`."""

    nome: str
    tema: str
    versao: str
    da_loja_de_temas: bool

    @property
    def renomeado(self) -> bool:
        resto = re.sub(r"\b(c[oó]pia|copy|updated|atualizad[ao]|of|de|do|da)\b|[\d.()-]", " ", _sem_acento(self.nome))
        return " ".join(resto.split()) != _sem_acento(self.tema)


@dataclass(frozen=True)
class Impressao:
    """As fontes, as cores e as seções de uma página inicial, para comparar com a demonstração."""

    fontes: frozenset[str] = frozenset()
    cores: frozenset[str] = frozenset()
    secoes: tuple[str, ...] = ()

    def para_json(self) -> dict:
        return {"fontes": sorted(self.fontes), "cores": sorted(self.cores), "secoes": list(self.secoes)}

    @classmethod
    def de_json(cls, dados: dict) -> Impressao:
        return cls(frozenset(dados.get("fontes") or ()), frozenset(dados.get("cores") or ()), tuple(dados.get("secoes") or ()))


@dataclass(frozen=True)
class TemaDeFabrica:
    """A comparação da loja com a demonstração do tema: só isso pode ir no e-mail."""

    tema: str
    versao: str
    demonstracao: str
    iguais: tuple[str, ...]
    fontes: tuple[str, ...] = ()
    renomeado: bool = True

    @property
    def de_fabrica(self) -> bool:
        return CORES in self.iguais and len(self.iguais) >= IGUAIS_PARA_SER_DE_FABRICA

    def frases(self) -> list[str]:
        """O que bateu, em português, do jeito que o e-mail pode dizer."""
        saida = []
        if FONTES in self.iguais:
            fontes = f" ({', '.join(self.fontes)})" if self.fontes else ""
            saida.append(f"as mesmas fontes da demonstração do {self.tema}{fontes}")
        if CORES in self.iguais:
            saida.append(f"as mesmas cores da demonstração do {self.tema}")
        if SECOES in self.iguais:
            saida.append(f"as mesmas seções, na mesma ordem, da página inicial da demonstração do {self.tema}")
        return saida

    def como_linha(self) -> str:
        """A linha da lista do vault (`- Tema de fábrica: …`), que o e-mail lê de volta."""
        versao = f" {self.versao}" if self.versao else ""
        return f"{self.tema}{versao}; igual à demonstração em: {', '.join(self.frases())}"

    def como_texto(self) -> str:
        linhas = [f"- tema Shopify: {self.tema}{f' {self.versao}' if self.versao else ''}, da loja de temas da Shopify"]
        linhas += [f"- comparada com a demonstração oficial do tema ({self.demonstracao}): {frase}" for frase in self.frases()]
        if not self.renomeado:
            linhas.append("- o tema publicado ainda tem o nome de fábrica")
        return "\n".join(linhas)


AbrirHtml = Callable[[str], "str | None"]


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


def dados_do_tema(html: str) -> DadosDoTema | None:
    casou = _TEMA.search(html or "")
    if casou is None:
        return None
    try:
        dados = json.loads(casou.group(1))
    except ValueError:
        return None
    if not isinstance(dados, dict):
        return None
    tema = str(dados.get("schema_name") or "").strip()
    if not tema:
        return None
    da_loja = dados.get("theme_store_id") not in (None, "", 0) or _sem_acento(tema) in TEMAS_DA_LOJA
    return DadosDoTema(str(dados.get("name") or "").strip(), tema, str(dados.get("schema_version") or "").strip(), da_loja)


def impressao(html: str) -> Impressao:
    fontes = {_fonte(bruta) for bruta in [*_VAR_DE_FONTE.findall(html), *_FONT_FACE.findall(html)]}
    cores = {
        f"{nome.casefold()}={_valor_da_cor(valor)}"
        for nome, valor in _VAR_DE_COR.findall(html)
        if _COR.match(valor.strip())
    }
    secoes = []
    for chave in _SECAO.findall(html):
        tipo = _SUFIXO_DA_SECAO.sub("", chave)
        if not _APP.match(tipo):
            secoes.append(tipo.replace("-", "_"))
    return Impressao(frozenset(f for f in fontes if f and f not in _GENERICAS), frozenset(cores), tuple(secoes))


def comparar(loja: Impressao, demonstracao: Impressao) -> tuple[str, ...]:
    iguais = []
    if loja.fontes and loja.fontes <= demonstracao.fontes:
        iguais.append(FONTES)
    if len(loja.cores) >= 3 and _jaccard(Counter(loja.cores), Counter(demonstracao.cores)) >= SEMELHANCA_MINIMA:
        iguais.append(CORES)
    if len(loja.secoes) >= 2 and (
        loja.secoes == demonstracao.secoes or _jaccard(Counter(loja.secoes), Counter(demonstracao.secoes)) >= SEMELHANCA_MINIMA
    ):
        iguais.append(SECOES)
    return tuple(iguais)


def conferir(html: str, *, abrir: AbrirHtml, estado: Path, agora: datetime | None = None) -> TemaDeFabrica | None:
    """A loja comparada com a demonstração do tema dela; None quando o tema não é da loja de temas ou a demonstração não abre."""
    dados = dados_do_tema(html)
    if dados is None or not dados.da_loja_de_temas:
        return None
    demonstracao = _demonstracao(dados.tema, abrir=abrir, estado=estado, agora=agora or datetime.now().astimezone())
    if demonstracao is None:
        return None
    url, da_demonstracao = demonstracao
    da_loja = impressao(html)
    iguais = comparar(da_loja, da_demonstracao)
    fontes = tuple(sorted(f.title() for f in da_loja.fontes)) if FONTES in iguais else ()
    return TemaDeFabrica(dados.tema, dados.versao, url, iguais, fontes, dados.renomeado)


def _demonstracao(tema: str, *, abrir: AbrirHtml, estado: Path, agora: datetime) -> tuple[str, Impressao] | None:
    chave = _sem_acento(tema)
    memoria = _ler_estado(estado)
    guardada = memoria.get(chave)
    if isinstance(guardada, dict):
        try:
            quando = datetime.fromisoformat(str(guardada.get("quando")))
        except ValueError:
            quando = None
        if quando is not None and agora - quando < VALIDADE_DA_DEMONSTRACAO:
            if not guardada.get("demonstracao"):
                return None
            return str(guardada["demonstracao"]), Impressao.de_json(guardada.get("impressao") or {})
    pagina_do_tema = abrir(LOJA_DE_TEMAS.format(slug=_slug(tema)))
    casou = _DEMONSTRACAO.search(pagina_do_tema or "")
    html = abrir(casou.group(1)) if casou else None
    resultado = (casou.group(1), impressao(html)) if casou and html else None
    if resultado is None:
        _log.info("Tema de fábrica: a demonstração do tema %s não abriu.", tema)
    memoria[chave] = {
        "quando": agora.isoformat(timespec="minutes"),
        "demonstracao": resultado[0] if resultado else "",
        "impressao": resultado[1].para_json() if resultado else {},
    }
    _gravar_estado(estado, memoria)
    return resultado


def _fonte(bruta: str) -> str:
    primeira = bruta.split(",")[0].strip().strip("\"'").strip()
    return "" if primeira.startswith("var(") else primeira.casefold()


def _valor_da_cor(valor: str) -> str:
    return " ".join(re.findall(r"#[0-9a-f]{3,8}|\d+(?:\.\d+)?", valor.casefold()))


def _jaccard(a: Counter, b: Counter) -> float:
    uniao = sum((a | b).values())
    return sum((a & b).values()) / uniao if uniao else 0.0


def _slug(tema: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _sem_acento(tema)).strip("-")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c)).strip()


def _ler_estado(estado: Path) -> dict:
    try:
        dados = json.loads(estado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_estado(estado: Path, memoria: dict) -> None:
    estado.parent.mkdir(parents=True, exist_ok=True)
    temporario = estado.with_name(estado.name + ".tmp")
    temporario.write_text(json.dumps(memoria, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, estado)
