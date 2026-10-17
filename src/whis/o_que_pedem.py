"""O que os clientes pedem (`whis o-que-pedem`): os freelas do nicho de todas as caçadas, contados por pedido.

Lê os relatórios de `cacada/` — os blocos de chance boa e de tentar a sorte (título,
faixa e o parágrafo do motivo) e as linhas das descartadas (título e motivo) —,
fica com os freelas do nicho, junta o mesmo anúncio que voltou noutra caçada (pelo
link ou pelo título) e conta quantos pedem cada coisa, com o teto do orçamento em
dólar. Serve para escolher a próxima peça do portfólio; a seção 3 de
`cacada/agencias-shopify.md` fez a mesma conta à mão em 14/10.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from . import vault as _vault
from .criterios_da_cacada import PASTA_CACADA
from .freelas_rapidos import do_nicho
from .funil import de_plataforma_de_freela
from .oportunidades import FREELA, Oportunidade, link_canonico
from .precos import EM_REAIS, numero_do_texto

CAMINHO_DA_NOTA = f"{PASTA_CACADA}/o-que-pedem.md"
DOLAR_EM_REAIS = EM_REAIS["USD"]

MONTAR = "Montar ou configurar a loja"

#: Cada pedido, o que no título ou no motivo diz que o anúncio pede isso (forte) e o que só conta quando o anúncio
#: não é de montar a loja (fraco: "tema, pagamentos e frete" na lista de quem monta a loja não é pedido de checkout).
#: Um anúncio pode pedir mais de uma coisa.
PEDIDOS = (
    (
        MONTAR,
        r"build|set ?up|configur|montar|monte\b|criar|create|cria[cç]|do zero|from scratch|new store|nova loja|dropship|"
        r"launch|lan[cç]ar|complet|inteir|development|desenvolv|store design|design de loja|finaliz|terminar|colocar no ar",
        "",
    ),
    ("App, integração ou sync com outro sistema", r"aplicativo|integra|api\b|sync|webhook|erp\b|whatsapp|conect|connect|faire\b", r"app\b|apps\b"),
    ("Checkout, pagamento e frete", r"checkout|gateway|carrinho|cart\b|sku|pix\b", r"pagamento|payment|frete|shipping"),
    ("Ajuste de tema ou seção", r"section|se[cç][aã]o|se[cç][oõ]es|liquid|menu\b|footer|rodap|header|cabe[cç]alho|landing|banner", r"theme|tema\b"),
    ("Revamp, UX e conversão", r"redesign|revamp|\bux\b|convers|\bcro\b|refazer|reformula", r"improve|melhor|layout"),
    ("Rastreamento (Pixel, GA4, Merchant Center)", r"pixel|capi\b|ga4|merchant center|tag manager|\bgtm\b|rastreamento|tracking", r"analytics"),
    ("Velocidade e acessibilidade", r"speed|pagespeed|lcp\b|velocidade|web vitals|lighthouse|acessibilidade|accessibility", r"performance"),
    ("Migração para a plataforma", r"migra|move from|transfer", ""),
    (
        "Cadastro, gestão e marketing da loja (não é dev)",
        "",
        r"cadastr|upload|listing|cat[aá]logo de produtos|gest[aã]o|management|operations|opera[cç][oõ]es|marketing|meta ads|an[uú]ncios|ads\b|seo\b",
    ),
)

#: Onde o motivo da triagem deixa de dizer o que o cliente pede e passa a falar dele ("igual às seções que ele
#: já fez", "perto do checkout que ele já mexe", o preço e as horas): dali em diante não conta como pedido.
_FALA_DELE = re.compile(
    r",?\s*(?:\bque ele\b|\bdele\b|\bele j[aá]\b|\bcasa com\b|\bigual\b|\bparecid|\bperto d|\bcomo o que\b|\bmas\b|"
    r"\bleva\b|\bcom ia\b|\bpedir\b|\bpe[cç]a\b|\bmarque\b|\bmarcar\b)",
    re.I,
)
_FRONTMATTER = re.compile(r"\A---\r?\n(?P<campos>.*?)\r?\n---", re.S)
_ABRIR = re.compile(r"\[Abrir\]\((?P<link>https?://[^)\s]+)\)")
_DESCARTADA = re.compile(r"^>\s*-\s*\[(?P<titulo>.+?)\]\((?P<link>https?://[^)\s]+)\)\s*—\s*(?P<resto>.*)$")
_ENTRE_PARENTESES = re.compile(r"\([^)]*\)")
_MOEDA = re.compile(r"R\$|US\$|BRL|USD|EUR|GBP|INR|AUD|CAD|NZD|SGD|[$€£₹]")


@dataclass(frozen=True)
class Anuncio:
    titulo: str
    link: str
    faixa: str
    texto: str
    cacada: str


@dataclass(frozen=True)
class LinhaDoPedido:
    pedido: str
    anuncios: int
    parte: float
    q1: float | None
    q3: float | None
    mediana: float | None
    exemplos: tuple[Anuncio, ...] = ()


def ler_anuncios(vault: Path, nicho: str) -> list[Anuncio]:
    pasta = Path(vault) / PASTA_CACADA
    por_chave: dict[str, Anuncio] = {}
    titulos: dict[str, str] = {}
    for arquivo in sorted(pasta.glob("*.md")) if pasta.is_dir() else ():
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        casou = _FRONTMATTER.match(texto)
        if casou is None or not re.search(r"^tipo:\s*cacada\s*$", casou["campos"], re.M):
            continue
        for anuncio in _anuncios_do_relatorio(texto, arquivo.stem):
            oportunidade = Oportunidade.nova(tipo=FREELA, fonte="", titulo=anuncio.titulo, link=anuncio.link, descricao=anuncio.texto)
            if not do_nicho(oportunidade, nicho):
                continue
            chave = link_canonico(anuncio.link).casefold()
            mesma = titulos.get(_normalizado(anuncio.titulo))
            chave = mesma or chave
            if chave in por_chave:
                antes = por_chave[chave]
                if not antes.faixa and anuncio.faixa:
                    por_chave[chave] = replace(antes, faixa=anuncio.faixa)
                continue
            por_chave[chave] = anuncio
            titulos[_normalizado(anuncio.titulo)] = chave
    return list(por_chave.values())


def teto_em_dolar(faixa: str) -> float | None:
    """O fim da faixa, em dólar; o que vem entre parênteses (a média dos lances) não é orçamento."""
    faixa = _ENTRE_PARENTESES.sub(" ", faixa)
    moeda = _MOEDA.search(faixa)
    if moeda is None:
        return None
    numeros = [n for n in (numero_do_texto(t) for t in re.findall(r"\d[\d.,]*\d|\d", faixa)) if n is not None]
    if not numeros:
        return None
    return max(numeros) * EM_REAIS[moeda.group(0)] / DOLAR_EM_REAIS


def contar(anuncios: Sequence[Anuncio]) -> list[LinhaDoPedido]:
    def casa(padrao: str, anuncio: Anuncio) -> bool:
        return bool(padrao) and re.search(rf"(?<![a-z0-9])(?:{padrao})", _sem_acento(f"{anuncio.titulo} {anuncio.texto}")) is not None

    montar = {a.link for a in anuncios if casa(PEDIDOS[0][1], a)}
    linhas = []
    for pedido, forte, fraco in PEDIDOS:
        deste = [a for a in anuncios if casa(forte, a) or (a.link not in montar and casa(fraco, a))]
        if not deste:
            continue
        tetos = sorted(t for t in (teto_em_dolar(a.faixa) for a in deste) if t is not None)
        q1 = q3 = mediana = None
        if tetos:
            mediana = statistics.median(tetos)
            q1, _, q3 = statistics.quantiles(tetos, n=4, method="inclusive") if len(tetos) > 1 else (tetos[0],) * 3
        linhas.append(LinhaDoPedido(pedido, len(deste), len(deste) / len(anuncios), q1, q3, mediana, tuple(deste)))
    return sorted(linhas, key=lambda linha: linha.anuncios, reverse=True)


def montar_nota(anuncios: Sequence[Anuncio], linhas: Sequence[LinhaDoPedido], nicho: str, agora: datetime) -> str:
    cacadas = sorted({a.cacada for a in anuncios})
    com_orcamento = sum(teto_em_dolar(a.faixa) is not None for a in anuncios)
    saida = [
        "---",
        "tipo: o-que-pedem",
        f'nicho: "{nicho}"',
        f"gerada: {agora:%Y-%m-%dT%H:%M}",
        "---",
        "",
        f"# O que os clientes de {nicho.title()} pedem",
        "",
        f"{len(anuncios)} anúncios de {nicho} em {len(cacadas)} caçadas ({', '.join(cacadas)}), sem repetir o mesmo "
        f"anúncio; {com_orcamento} com orçamento. Um anúncio pode pedir mais de uma coisa, então as partes somam mais "
        "de 100%. O teto é o fim da faixa do anúncio, em dólar pelo câmbio de bom senso. Refeita por `whis o-que-pedem`.",
        "",
        "| Pedido | Anúncios | Parte | Teto (25% a 75%) | Mediana do teto |",
        "|---|---|---|---|---|",
    ]
    for linha in linhas:
        faixa = f"US$ {linha.q1:,.0f} a {linha.q3:,.0f}" if linha.q1 is not None else "—"
        mediana = f"US$ {linha.mediana:,.0f}" if linha.mediana is not None else "—"
        saida.append(f"| {linha.pedido} | {linha.anuncios} | {linha.parte:.0%} | {faixa} | {mediana} |")
    reconhecidos = {a.link for linha in linhas for a in linha.exemplos}
    sem_pedido = [a for a in anuncios if a.link not in reconhecidos]
    saida += ["", f"{len(sem_pedido)} sem pedido reconhecido pelo título e pelo motivo (lista no fim).", ""]
    for linha in linhas:
        saida += [f"## {linha.pedido}", ""]
        saida += [f"- [{a.titulo}]({a.link}) — {a.faixa or 'orçamento não informado'}" for a in linha.exemplos[:8]]
        saida.append("")
    if sem_pedido:
        saida += ["## Sem pedido reconhecido", ""]
        saida += [f"- [{a.titulo}]({a.link}) — {a.texto or a.faixa or '—'}" for a in sem_pedido]
        saida.append("")
    return "\n".join(saida)


def atualizar(vault: Path, nicho: str, agora: datetime | None = None) -> tuple[list[Anuncio], list[LinhaDoPedido], str]:
    agora = agora or datetime.now().astimezone()
    anuncios = ler_anuncios(vault, nicho)
    linhas = contar(anuncios)
    _vault.escrever(Path(vault), CAMINHO_DA_NOTA, montar_nota(anuncios, linhas, nicho, agora), zonas=(PASTA_CACADA,))
    return anuncios, linhas, CAMINHO_DA_NOTA


def _anuncios_do_relatorio(texto: str, cacada: str) -> list[Anuncio]:
    linhas = texto.splitlines()
    saida = []
    for indice, linha in enumerate(linhas):
        if linha.startswith("### "):
            anuncio = _do_bloco(linhas, indice, cacada)
            if anuncio is not None:
                saida.append(anuncio)
            continue
        casou = _DESCARTADA.match(linha.strip())
        if casou and de_plataforma_de_freela(casou["link"]):
            motivo = casou["resto"].split(" — ", 1)[-1]
            saida.append(Anuncio(casou["titulo"].strip(), casou["link"], "", _o_que_pedem(motivo), cacada))
    return saida


def _o_que_pedem(motivo: str) -> str:
    """O começo do motivo, antes de ele falar do Gabriel."""
    corte = _FALA_DELE.search(motivo)
    return (motivo[: corte.start()] if corte else motivo).strip()


def _do_bloco(linhas: list[str], indice: int, cacada: str) -> Anuncio | None:
    titulo = re.sub(r"^\d+\.\s*", "", linhas[indice][4:]).split(" — ", 1)[0].strip()
    seguintes = [linha.strip() for linha in linhas[indice + 1 : indice + 8] if linha.strip()]
    if not seguintes or not seguintes[0].startswith("Freela ·"):
        return None
    cabecalho = seguintes[0]
    abrir = _ABRIR.search(cabecalho)
    if abrir is None:
        return None
    partes = [p.strip() for p in cabecalho.split(" · ")]
    antes_do_encaixe = partes[: next((i for i, p in enumerate(partes) if p.startswith("encaixe")), len(partes))]
    faixa = next((p for p in reversed(antes_do_encaixe) if _MOEDA.search(p) and re.search(r"\d", p)), "")
    motivo = next((s for s in seguintes[1:] if not s.startswith(("#", "→", ">"))), "")
    return Anuncio(titulo, abrir["link"], faixa, _o_que_pedem(motivo), cacada)


def _normalizado(titulo: str) -> str:
    """O título sem acento, sem caixa e sem o que vem entre parênteses, que a caçada às vezes acrescenta."""
    return " ".join(re.findall(r"[a-z0-9]+", _sem_acento(_ENTRE_PARENTESES.sub(" ", titulo))))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))
