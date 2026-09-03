"""Escrita no vault: estrutura de pastas, nota de reunião, transcrição e diário.

A zona de propriedade é uma invariante deste módulo, não só dos testes — e ela
é **por coletor**: `escrever` recebe as zonas que aquela chamada permite. O
coletor de reunião escreve em `reunioes/` e `transcricoes/`; o do diário, só em
`diario/`. Nenhum dos dois alcança a zona do outro, e `notas/` (a zona do
usuário) é recusada para ambos: ela é criada na primeira execução e nunca mais
tocada.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .fontes import ORDEM_DAS_FONTES, Evento, Janela, nome_legivel
from .portas import Resumo, ResumoDoDia, Transcricao

if TYPE_CHECKING:  # `diario` importa este módulo em tempo de execução
    from .diario import FalhaDeFonte

_log = logging.getLogger("second_brain.vault")

PASTA_REUNIOES = "reunioes"
PASTA_TRANSCRICOES = "transcricoes"
PASTA_DIARIO = "diario"
PASTA_NOTAS = "notas"

#: Todas as pastas criadas na primeira execução.
ESTRUTURA = (PASTA_REUNIOES, PASTA_TRANSCRICOES, PASTA_DIARIO, PASTA_NOTAS)

#: As únicas pastas em que o coletor de reunião pode escrever.
ZONAS_DE_ESCRITA = (PASTA_REUNIOES, PASTA_TRANSCRICOES)

#: A única pasta em que o coletor de diário pode escrever.
ZONAS_DO_DIARIO = (PASTA_DIARIO,)

#: Valor do campo `tipo` no frontmatter de cada artefato.
TIPO_REUNIAO = "reuniao"
TIPO_TRANSCRICAO = "transcricao"
TIPO_DIARIO = "diario"

_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_DIAS_DA_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

#: O `YYYY-MM-DD-HHMM` com que a nota de reunião começa, pelo contrato da pasta.
_PREFIXO_DA_REUNIAO = re.compile(r"^(?P<data>\d{4}-\d{2}-\d{2})-(?P<hora>\d{4})(?:-.*)?$")


class ForaDaZonaDePropriedade(RuntimeError):
    """Tentativa de escrever fora das zonas permitidas àquela chamada."""


def preparar(vault: Path) -> Path:
    """Cria o vault e sua estrutura se ainda não existirem. Idempotente."""
    vault = Path(vault)
    if not vault.exists():
        _log.info("Criando o vault em %s", vault)
    vault.mkdir(parents=True, exist_ok=True)
    for pasta in ESTRUTURA:
        alvo = vault / pasta
        if not alvo.exists():
            _log.info("Criando a pasta %s/ no vault", pasta)
        alvo.mkdir(exist_ok=True)
    return vault


def escrever(
    vault: Path,
    relativo: str,
    conteudo: str,
    *,
    zonas: Sequence[str] = ZONAS_DE_ESCRITA,
) -> Path:
    """Escreve um arquivo no vault, recusando caminhos fora de `zonas`.

    As zonas são parâmetro porque a propriedade é de cada coletor: o de
    reunião nunca escreve em `diario/`, o do diário nunca escreve em
    `reunioes/`, e `notas/` fica fora do alcance dos dois.

    A checagem é feita no caminho **resolvido**: não basta começar com o nome
    de uma zona, o arquivo precisa terminar dentro dela. Assim `..` no meio do
    caminho não escapa para `notas/` nem para fora do vault.
    """
    raiz = Path(vault)
    caminho_relativo = Path(relativo)
    if not relativo or caminho_relativo.is_absolute() or not caminho_relativo.parts:
        raise ForaDaZonaDePropriedade(_recusa(relativo, zonas))

    zona = caminho_relativo.parts[0]
    if zona not in zonas:
        raise ForaDaZonaDePropriedade(_recusa(relativo, zonas))

    pasta_da_zona = (raiz / zona).resolve()
    alvo = (raiz / caminho_relativo).resolve()
    if alvo == pasta_da_zona or not alvo.is_relative_to(pasta_da_zona):
        raise ForaDaZonaDePropriedade(_recusa(relativo, zonas))

    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    _log.info("Escrito no vault: %s", relativo)
    return alvo


def _recusa(relativo: str, zonas: Sequence[str]) -> str:
    permitidas = ", ".join(f"{zona}/" for zona in zonas) or "nenhuma pasta"
    return f"Esta escrita só alcança {permitidas} — recusado: {relativo!r}"


def caminho_da_nota(basename: str) -> str:
    """Caminho relativo da nota de reunião, no formato do contrato."""
    return f"{PASTA_REUNIOES}/{basename}.md"


def caminho_da_transcricao(basename: str) -> str:
    """Caminho relativo da transcrição, com o mesmo basename da nota."""
    return f"{PASTA_TRANSCRICOES}/{basename}.md"


def wikilink(caminho_relativo: str) -> str:
    """Wikilink do Obsidian para um caminho do vault, sem a extensão.

    Usa o caminho e não só o nome porque nota e transcrição compartilham o
    basename — o link curto seria ambíguo dentro do vault.
    """
    return f"[[{caminho_relativo.removesuffix('.md')}]]"


def montar_nota(
    *,
    basename: str,
    data: str,
    titulo: str,
    participantes: tuple[str, ...],
    resumo: Resumo,
) -> str:
    """Monta o markdown da nota de reunião: frontmatter mínimo + resumo."""
    frontmatter = _frontmatter(
        {
            "data": data,
            "tipo": TIPO_REUNIAO,
            "participantes": list(participantes),
            "transcricao": wikilink(caminho_da_transcricao(basename)),
        }
    )
    corpo = [
        f"# {titulo}",
        "",
        "## Decisões",
        "",
        _lista(resumo.decisoes),
        "",
        "## Ações e pendências",
        "",
        _lista(resumo.acoes),
        "",
        "## Tópicos",
        "",
        _lista(resumo.topicos),
        "",
        "---",
        "",
        f"Transcrição completa: {wikilink(caminho_da_transcricao(basename))}",
        "",
    ]
    return frontmatter + "\n".join(corpo)


def montar_transcricao(
    *,
    basename: str,
    data: str,
    titulo: str,
    transcricao: Transcricao,
) -> str:
    """Monta o markdown da transcrição bruta, uma fala por parágrafo."""
    frontmatter = _frontmatter(
        {
            "data": data,
            "tipo": TIPO_TRANSCRICAO,
            "idioma": transcricao.idioma,
            "reuniao": wikilink(caminho_da_nota(basename)),
        }
    )
    corpo = [f"# Transcrição — {titulo}", ""]
    for fala in transcricao.falas:
        corpo.append(f"**{fala.falante}:** {fala.texto}")
        corpo.append("")
    return frontmatter + "\n".join(corpo)


def caminho_do_diario(data: date) -> str:
    """Caminho relativo do diário: um arquivo por dia, sem hora no nome."""
    return f"{PASTA_DIARIO}/{data.isoformat()}.md"


def reunioes_na_janela(vault: Path, janela: Janela) -> tuple[str, ...]:
    """As notas de reunião cujo horário cai na janela, em ordem cronológica.

    O horário vem do prefixo `YYYY-MM-DD-HHMM` do nome do arquivo, fixado pelo
    contrato da pasta de gravação. É o que faz a reunião da meia-noite e meia
    aparecer no diário do dia anterior, igual aos commits.

    Arquivo com nome fora do padrão é ignorado em silêncio: o diário não pode
    quebrar por causa de uma nota renomeada à mão.
    """
    pasta = Path(vault) / PASTA_REUNIOES
    if not pasta.is_dir():
        return ()

    encontradas: list[tuple[datetime, str]] = []
    for arquivo in pasta.glob("*.md"):
        momento = _momento_da_reuniao(arquivo.stem)
        if momento is not None and janela.contem(momento):
            encontradas.append((momento, f"{PASTA_REUNIOES}/{arquivo.name}"))
    return tuple(caminho for _, caminho in sorted(encontradas))


def montar_diario(
    *,
    data: date,
    janela: Janela,
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
    resumo: ResumoDoDia | None,
    falha_do_resumo: str | None = None,
) -> str:
    """Monta o markdown do diário: frontmatter, avisos, resumo e listas cruas.

    O que falhou aparece: no frontmatter, num aviso logo abaixo do título e na
    seção da fonte. Um diário incompleto que se passa por completo é pior que
    um diário ausente.
    """
    frontmatter = _frontmatter(
        {
            "data": data.isoformat(),
            "tipo": TIPO_DIARIO,
            "janela": janela.como_texto(),
            "fontes": list(fontes_lidas),
            "fontes_com_falha": [falha.fonte for falha in fontes_com_falha],
            "temas": list(resumo.temas) if resumo else [],
            "reunioes": [wikilink(reuniao) for reuniao in reunioes],
        }
    )

    corpo = [f"# Diário — {_data_por_extenso(data)}", ""]
    for aviso in _avisos(fontes_com_falha, resumo, falha_do_resumo):
        corpo.extend([f"> {aviso}", ""])

    if resumo is not None and resumo.narrativa.strip():
        corpo.extend([resumo.narrativa.strip(), ""])
    if resumo is not None:
        corpo.extend(["## Destaques", "", _lista(tuple(resumo.destaques)), ""])
        corpo.extend(["## Pendências", "", _lista(tuple(resumo.pendencias)), ""])

    corpo.extend(["## Reuniões", ""])
    corpo.append(_lista(tuple(wikilink(reuniao) for reuniao in reunioes)))
    corpo.append("")

    motivos = {falha.fonte: falha.motivo for falha in fontes_com_falha}
    for fonte in _fontes_em_ordem(fontes_lidas, [falha.fonte for falha in fontes_com_falha]):
        corpo.extend([f"## {nome_legivel(fonte)}", ""])
        if fonte in motivos:
            corpo.extend([f"_Não foi possível ler esta fonte: {motivos[fonte]}_", ""])
            continue
        corpo.extend(_secao_da_fonte(fonte, eventos))

    return frontmatter + "\n".join(corpo)


def _avisos(
    fontes_com_falha: Sequence["FalhaDeFonte"],
    resumo: ResumoDoDia | None,
    falha_do_resumo: str | None,
) -> list[str]:
    avisos = [
        f"{nome_legivel(falha.fonte)} não entrou neste diário: {falha.motivo}"
        for falha in fontes_com_falha
    ]
    if resumo is None:
        motivo = falha_do_resumo or "o resumo do dia não está configurado."
        avisos.append(
            f"Este diário não tem narrativa nem destaques: {motivo} "
            "As listas cruas abaixo continuam completas."
        )
    return avisos


def _fontes_em_ordem(lidas: Sequence[str], com_falha: Sequence[str]) -> list[str]:
    """As fontes que aparecem na nota, sempre na ordem git, Linear, Slack.

    Fonte não configurada não entra em nenhuma das duas listas e por isso não
    aparece — é o que distingue "não houve nada" de "não está ligada".
    """
    presentes = list(dict.fromkeys([*lidas, *com_falha]))
    conhecidas = [fonte for fonte in ORDEM_DAS_FONTES if fonte in presentes]
    return conhecidas + [fonte for fonte in presentes if fonte not in ORDEM_DAS_FONTES]


def _secao_da_fonte(fonte: str, eventos: Sequence[Evento]) -> list[str]:
    da_fonte = [evento for evento in eventos if evento.fonte == fonte]
    if not da_fonte:
        return ["_(nada registrado)_", ""]

    linhas: list[str] = []
    for evento in da_fonte:
        if not evento.referencia:
            linhas.extend(_linhas_do_evento(evento))
    if linhas:
        linhas.append("")

    for referencia in dict.fromkeys(
        evento.referencia for evento in da_fonte if evento.referencia
    ):
        linhas.extend([f"### {referencia}", ""])
        for evento in da_fonte:
            if evento.referencia == referencia:
                linhas.extend(_linhas_do_evento(evento))
        linhas.append("")
    return linhas


def _linhas_do_evento(evento: Evento) -> list[str]:
    titulo = " ".join(evento.titulo.split()) or "(sem título)"
    if evento.url:
        titulo = f"[{titulo}]({evento.url})"
    linhas = [f"- {evento.momento:%H:%M} {titulo}"]
    for linha in evento.detalhe.strip().splitlines():
        linhas.append(f"  > {linha}".rstrip())
    return linhas


def _momento_da_reuniao(nome: str) -> datetime | None:
    partes = _PREFIXO_DA_REUNIAO.match(nome)
    if partes is None:
        return None
    try:
        return datetime.strptime(
            f"{partes['data']}-{partes['hora']}", "%Y-%m-%d-%H%M"
        ).astimezone()
    except ValueError:
        return None


def _data_por_extenso(data: date) -> str:
    """`3 de setembro de 2026 (quinta-feira)` — sem depender do locale da máquina."""
    return (
        f"{data.day} de {_MESES[data.month - 1]} de {data.year} "
        f"({_DIAS_DA_SEMANA[data.weekday()]})"
    )


def _frontmatter(campos: dict[str, object]) -> str:
    linhas = ["---"]
    for chave, valor in campos.items():
        linhas.append(f"{chave}: {_valor_yaml(valor)}")
    linhas.extend(["---", ""])
    return "\n".join(linhas) + "\n"


def _valor_yaml(valor: object) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(_texto_yaml(str(item)) for item in valor) + "]"
    return _texto_yaml(str(valor))


def _texto_yaml(texto: str) -> str:
    """Datas simples ficam sem aspas; o resto é sempre citado.

    Wikilinks precisam de aspas: `[[x]]` sem elas seria lista aninhada em YAML.
    """
    if texto and all(c.isalnum() or c in "-_" for c in texto) and not texto[0].isdigit():
        return texto
    if _parece_data(texto):
        return texto
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parece_data(texto: str) -> bool:
    partes = texto.split("-")
    return len(partes) == 3 and all(parte.isdigit() for parte in partes)


def _lista(itens: tuple[str, ...]) -> str:
    if not itens:
        return "_(nada registrado)_"
    return "\n".join(f"- {item}" for item in itens)
