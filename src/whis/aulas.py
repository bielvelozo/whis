"""As aulas da formação como notas do vault: `noticias/aulas/<id>.md`.

Cada aula que nasce vira uma nota `pendente`; ela só vira `lida` quando ele a
marca (na página, que o Whis copia para cá, ou trocando o `status:` no
Obsidian). Uma área só ganha aula nova depois de a anterior ser lida, e é daqui
que o jornal tira as vagas do dia e as aulas que voltam. O que `montar_nota`
escreve, `ler_nota` lê igual; o esquema SVG não vai na nota, fica no `.svg` ao
lado, que `ler_aulas` valida de novo.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from . import vault as _vault
from .esquema import validar_esquema
from .portas import Aula, Formacao

PASTA_DAS_AULAS = "noticias/aulas"

NEGOCIOS = "negocios"
CARROS = "carros"
PENDENTE = "pendente"
LIDA = "lida"

AULAS_POR_AREA = {NEGOCIOS: 1, CARROS: 2}

_ROTULO_DA_AREA = {NEGOCIOS: "negócios", CARROS: CARROS}
_ABRE_O_TEXTO = "<!-- texto -->\n"
_FECHA_O_TEXTO = "\n<!-- /texto -->"
_FRONTMATTER = re.compile(r"\A---\n(?P<campos>.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_ID = re.compile(r"[\w-]+")
_BARRA_E_ASPAS = re.compile(r'\\(["\\])')


@dataclass(frozen=True)
class NotaDeAula:
    """Uma aula e o que se sabe dela: de que dia é, se ele a leu e em que quiz entrou."""

    id: str
    area: str
    data: date
    status: str
    aula: Aula
    lida_em: str = ""
    quiz: str = ""


def id_da_aula(data: date, area: str, n: int = 1) -> str:
    """`AAAA-MM-DD-negocios` ou `AAAA-MM-DD-carros-<n>`: a data em que a aula nasceu."""
    return f"{data.isoformat()}-negocios" if area == NEGOCIOS else f"{data.isoformat()}-{area}-{n}"


def montar_nota(nota: NotaDeAula) -> str:
    aula = nota.aula
    campos = {
        "tipo": "aula",
        "id": nota.id,
        "area": _ROTULO_DA_AREA.get(nota.area, nota.area),
        "data": nota.data.isoformat(),
        "status": nota.status,
        "lida_em": nota.lida_em,
        "visual": aula.visual,
        "imagem": aula.imagem,
        "trilha": _uma_linha(aula.trilha),
        "quiz": nota.quiz,
    }
    cabeca = [f"# {_uma_linha(aula.titulo)}"]
    if aula.imagem:
        cabeca.append(f"![]({aula.imagem})")
    if aula.visual == "esquema":
        cabeca.append(f"![[{nota.id}.svg]]")
    texto = aula.texto.replace("\r\n", "\n")
    fontes = "\n".join(["Fontes:", *(f"- {url}" for url in aula.fontes)])
    corpo = "\n\n".join(cabeca) + f"\n\n{_ABRE_O_TEXTO}{texto}{_FECHA_O_TEXTO}\n\n{fontes}\n"
    return _vault._frontmatter(campos) + corpo


def ler_nota(texto: str) -> NotaDeAula | None:
    """A nota de aula escrita por `montar_nota`, ou editada à mão; `None` se não for uma."""
    texto = texto.removeprefix("﻿").replace("\r\n", "\n")
    cabecalho = _FRONTMATTER.match(texto)
    if cabecalho is None:
        return None
    campos = _campos(cabecalho["campos"])
    if campos.get("tipo") != "aula":
        return None

    corpo = texto[cabecalho.end():]
    abertura = corpo.find(_ABRE_O_TEXTO)
    fechamento = corpo.rfind(_FECHA_O_TEXTO)
    if abertura < 0 or fechamento < abertura + len(_ABRE_O_TEXTO):
        return None
    titulo = next((linha[2:] for linha in corpo[:abertura].splitlines() if linha.startswith("# ")), None)
    id_ = campos.get("id", "")
    area = _area(campos.get("area", ""))
    try:
        data = date.fromisoformat(campos.get("data", ""))
    except ValueError:
        return None
    if titulo is None or area is None or not _ID.fullmatch(id_):
        return None

    aula = Aula(
        titulo=titulo,
        texto=corpo[abertura + len(_ABRE_O_TEXTO):fechamento],
        fontes=_fontes(corpo[fechamento + len(_FECHA_O_TEXTO):]),
        trilha=campos.get("trilha", ""),
        visual=campos.get("visual", ""),
        imagem=campos.get("imagem", ""),
        id=id_,
    )
    return NotaDeAula(
        id=id_,
        area=area,
        data=data,
        status=LIDA if campos.get("status", "").casefold() == LIDA else PENDENTE,
        aula=aula,
        lida_em=campos.get("lida_em", ""),
        quiz=campos.get("quiz", ""),
    )


def ler_aulas(vault: Path) -> list[NotaDeAula]:
    """Todas as notas de aula do vault, por id, com o esquema lido do `.svg` ao lado."""
    pasta = Path(vault) / PASTA_DAS_AULAS
    notas = []
    for arquivo in pasta.glob("*.md") if pasta.is_dir() else ():
        try:
            texto = arquivo.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        nota = ler_nota(texto)
        if nota is not None:
            notas.append(_com_o_esquema(pasta, nota))
    return sorted(notas, key=lambda nota: nota.id)


def escrever_aula(vault: Path, nota: NotaDeAula) -> Path:
    caminho = _vault.escrever(
        vault, f"{PASTA_DAS_AULAS}/{nota.id}.md", montar_nota(nota), zonas=_vault.ZONAS_DO_JORNAL
    )
    if nota.aula.esquema:
        _vault.escrever(
            vault,
            f"{PASTA_DAS_AULAS}/{nota.id}.svg",
            nota.aula.esquema,
            zonas=_vault.ZONAS_DO_JORNAL,
            literal=True,
        )
    return caminho


def aplicar_leituras(notas: Sequence[NotaDeAula], lidas: Mapping[str, str]) -> list[NotaDeAula]:
    """Só `pendente` vira `lida` (com o momento da marcação); o resto volta a mesma nota."""
    return [
        replace(nota, status=LIDA, lida_em=lidas[nota.id])
        if nota.status == PENDENTE and nota.id in lidas
        else nota
        for nota in notas
    ]


def vagas(notas: Sequence[NotaDeAula], hoje: date, *, sabado: bool) -> dict[str, int]:
    """Quantas aulas novas cada área pode ganhar hoje.

    Cada pendente de dia anterior ocupa uma vaga da área. A formação roda uma
    vez por dia (já nasceu aula hoje, não há vaga) e no sábado vem o quiz no
    lugar das aulas.
    """
    if sabado or any(nota.data == hoje for nota in notas):
        return {area: 0 for area in AULAS_POR_AREA}
    antigas = _pendentes_de_antes(notas, hoje)
    return {
        area: max(0, limite - sum(1 for nota in antigas if nota.area == area))
        for area, limite in AULAS_POR_AREA.items()
    }


def nascer(formacao: Formacao, hoje: date, notas: Sequence[NotaDeAula]) -> tuple[NotaDeAula, ...]:
    """Uma nota `pendente` por aula da formação; carro ganha o menor número livre do dia."""
    usados = {nota.id for nota in notas}
    nascidas = []

    def nasce(id_: str, area: str, aula: Aula) -> None:
        usados.add(id_)
        nascidas.append(
            NotaDeAula(id=id_, area=area, data=hoje, status=PENDENTE, aula=replace(aula, id=id_))
        )

    if formacao.negocios is not None:
        nasce(id_da_aula(hoje, NEGOCIOS), NEGOCIOS, formacao.negocios)
    for aula in formacao.carros:
        n = 1
        while id_da_aula(hoje, CARROS, n) in usados:
            n += 1
        nasce(id_da_aula(hoje, CARROS, n), CARROS, aula)
    return tuple(nascidas)


def em_cena(notas: Sequence[NotaDeAula], hoje: date) -> Formacao:
    """As aulas da edição: por área, as pendentes de antes (mais antigas primeiro) e depois as de hoje."""

    def da_area(area: str) -> tuple[Aula, ...]:
        antigas = sorted(
            (nota for nota in _pendentes_de_antes(notas, hoje) if nota.area == area),
            key=lambda nota: (nota.data, nota.id),
        )
        de_hoje = sorted((nota for nota in notas if nota.area == area and nota.data == hoje), key=lambda nota: nota.id)
        aulas = [replace(nota.aula, id=nota.id, pendente_desde=nota.data) for nota in antigas]
        aulas += [replace(nota.aula, id=nota.id, pendente_desde=None) for nota in de_hoje]
        return tuple(aulas[: AULAS_POR_AREA[area]])

    negocios = da_area(NEGOCIOS)
    return Formacao(negocios=negocios[0] if negocios else None, carros=da_area(CARROS))


def _pendentes_de_antes(notas: Sequence[NotaDeAula], hoje: date) -> list[NotaDeAula]:
    return [nota for nota in notas if nota.status == PENDENTE and nota.data < hoje]


def _com_o_esquema(pasta: Path, nota: NotaDeAula) -> NotaDeAula:
    if nota.aula.visual != "esquema":
        return nota
    try:
        bruto = (pasta / f"{nota.id}.svg").read_text(encoding="utf-8-sig")
    except OSError:
        bruto = ""
    esquema = validar_esquema(bruto)
    if esquema:
        return replace(nota, aula=replace(nota.aula, esquema=esquema))
    return replace(nota, aula=replace(nota.aula, visual="", esquema=""))


def _campos(bloco: str) -> dict[str, str]:
    campos = {}
    for linha in bloco.splitlines():
        chave, separador, valor = linha.partition(":")
        if separador:
            campos[chave.strip()] = _sem_aspas(valor.strip())
    return campos


def _sem_aspas(valor: str) -> str:
    """Desfaz o que `vault._texto_yaml` fez: aspas duplas com `\\` e `"` escapados."""
    if len(valor) >= 2 and valor[0] == valor[-1] == '"':
        return _BARRA_E_ASPAS.sub(r"\1", valor[1:-1])
    if len(valor) >= 2 and valor[0] == valor[-1] == "'":
        return valor[1:-1].replace("''", "'")
    return valor


def _area(rotulo: str) -> str | None:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", rotulo.strip().casefold()) if not unicodedata.combining(c)
    )
    return sem_acento if sem_acento in AULAS_POR_AREA else None


def _fontes(depois_do_texto: str) -> tuple[str, ...]:
    fontes: list[str] = []
    na_lista = False
    for linha in depois_do_texto.splitlines():
        if linha.strip() == "Fontes:":
            na_lista = True
        elif na_lista and linha.startswith("- ") and linha[2:].strip():
            fontes.append(linha[2:].strip())
    return tuple(fontes)


def _uma_linha(texto: str) -> str:
    return texto.replace("\r\n", "\n").replace("\n", " ")
