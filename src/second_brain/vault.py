"""Escrita no vault: pastas, nota de reunião, transcrição, diário e daily.

A zona de propriedade é uma invariante deste módulo, não só dos testes — e ela
é **por coletor**: `escrever` recebe as zonas que aquela chamada permite. O
coletor de reunião escreve em `reunioes/` e `transcricoes/`; o do diário, só em
`diario/`; o da daily, só em `daily/`. Nenhum alcança a zona do outro.

`notas/` é a zona do usuário e é recusada para todos eles. A única exceção é
`notas/daily.md`, e só pelo pedido explícito de `daily --anotar`: ali o agente
lê os pontos que o usuário escreveu e, quando mandado, **acrescenta** um — sem
nunca reescrever o que já estava lá nem marcar checkbox nenhum.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .fontes import ORDEM_DAS_FONTES, Evento, Janela, nome_legivel
from .portas import Daily, Resumo, ResumoDoDia, Transcricao

if TYPE_CHECKING:  # ambos importam este módulo em tempo de execução
    from .coleta import FalhaDeFonte
    from .daily import JanelaDaDaily

_log = logging.getLogger("second_brain.vault")

PASTA_REUNIOES = "reunioes"
PASTA_TRANSCRICOES = "transcricoes"
PASTA_DIARIO = "diario"
PASTA_DAILY = "daily"
PASTA_NOTAS = "notas"

#: Todas as pastas criadas na primeira execução.
ESTRUTURA = (PASTA_REUNIOES, PASTA_TRANSCRICOES, PASTA_DIARIO, PASTA_DAILY, PASTA_NOTAS)

#: As únicas pastas em que o coletor de reunião pode escrever.
ZONAS_DE_ESCRITA = (PASTA_REUNIOES, PASTA_TRANSCRICOES)

#: A única pasta em que o coletor de diário pode escrever.
ZONAS_DO_DIARIO = (PASTA_DIARIO,)

#: A única pasta em que o coletor de daily pode escrever.
ZONAS_DA_DAILY = (PASTA_DAILY,)

#: Onde o usuário escreve o que quer levantar na daily — a zona dele.
ARQUIVO_DE_PONTOS = f"{PASTA_NOTAS}/daily.md"

#: Valor do campo `tipo` no frontmatter de cada artefato.
TIPO_REUNIAO = "reuniao"
TIPO_TRANSCRICAO = "transcricao"
TIPO_DIARIO = "diario"
TIPO_DAILY = "daily"

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

#: `- [ ] texto` — o item que o usuário ainda não falou. `- [x]` fica de fora.
_ITEM_DESMARCADO = re.compile(r"^\s*[-*]\s+\[ \]\s+(?P<texto>.+?)\s*$")

#: Os títulos que `notas/daily.md` pode ter, e o campo de `PontosDaDaily` de cada um.
_SECOES_DOS_PONTOS = {
    "dúvidas": "duvidas",
    "duvidas": "duvidas",
    "off-topic": "off_topic",
    "off topic": "off_topic",
    "pontos": "pontos",
}

#: O arquivo que `--anotar` cria quando o usuário ainda não tem um.
MODELO_DOS_PONTOS = """\
# Daily — meus pontos

Marque o checkbox depois de falar: o que estiver marcado não aparece na próxima daily.

## Dúvidas

## Off-topic

## Pontos
"""


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

    corpo.extend(_listas_cruas(eventos, reunioes, fontes_lidas, fontes_com_falha))

    return frontmatter + "\n".join(corpo)


def _listas_cruas(
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
) -> list[str]:
    """As reuniões e uma seção por fonte — a memória durável de diário e daily."""
    linhas = [
        "## Reuniões",
        "",
        _lista(tuple(wikilink(reuniao) for reuniao in reunioes)),
        "",
    ]

    motivos = {falha.fonte: falha.motivo for falha in fontes_com_falha}
    for fonte in _fontes_em_ordem(fontes_lidas, [falha.fonte for falha in fontes_com_falha]):
        linhas.extend([f"## {nome_legivel(fonte)}", ""])
        if fonte in motivos:
            linhas.extend([f"_Não foi possível ler esta fonte: {motivos[fonte]}_", ""])
            continue
        linhas.extend(_secao_da_fonte(fonte, eventos))
    return linhas


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


def agrupar_por_referencia(
    fonte: str, eventos: Sequence[Evento]
) -> list[tuple[str | None, list[Evento]]]:
    """Os eventos de uma fonte, por referência, na ordem da primeira aparição.

    Devolve dados, não markdown, porque a nota e a página HTML mostram o mesmo
    agrupamento de jeitos diferentes — e a regra de agrupar é do contrato, não
    de um formato. `None` é o grupo dos eventos sem referência, que vem primeiro.
    """
    da_fonte = [evento for evento in eventos if evento.fonte == fonte]
    grupos: list[tuple[str | None, list[Evento]]] = []

    soltos = [evento for evento in da_fonte if not evento.referencia]
    if soltos:
        grupos.append((None, soltos))

    for referencia in dict.fromkeys(
        evento.referencia for evento in da_fonte if evento.referencia
    ):
        grupos.append(
            (referencia, [e for e in da_fonte if e.referencia == referencia])
        )
    return grupos


def _secao_da_fonte(fonte: str, eventos: Sequence[Evento]) -> list[str]:
    grupos = agrupar_por_referencia(fonte, eventos)
    if not grupos:
        return ["_(nada registrado)_", ""]

    linhas: list[str] = []
    for referencia, do_grupo in grupos:
        if referencia is not None:
            linhas.extend([f"### {referencia}", ""])
        for evento in do_grupo:
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


@dataclass(frozen=True)
class PontosDaDaily:
    """O que o usuário escreveu em `notas/daily.md` e ainda não falou."""

    duvidas: tuple[str, ...] = ()
    off_topic: tuple[str, ...] = ()
    pontos: tuple[str, ...] = ()

    def tem_algo(self) -> bool:
        """Há alguma coisa dele para levar à daily?"""
        return bool(self.duvidas or self.off_topic or self.pontos)


def caminho_da_daily(data: date) -> str:
    """Caminho relativo da daily: um arquivo por dia, sem hora no nome."""
    return f"{PASTA_DAILY}/{data.isoformat()}.md"


def ate_da_daily_anterior(vault: Path, antes_de: date) -> datetime | None:
    """O campo `ate` da daily mais recente **de um dia anterior** a `antes_de`.

    É a âncora da janela da próxima daily, e ela mora no frontmatter da nota
    porque o vault é a fonte da verdade: o usuário audita a janela lendo o
    próprio arquivo, sem estado escondido em lugar nenhum.

    A daily de hoje fica de fora de propósito: ancorar nela faria a segunda
    execução do dia começar onde a primeira terminou, e cobrir uma janela
    vazia. Quem preserva a janela numa reexecução é `desde_da_daily_de`.

    Nota com nome ou frontmatter fora do padrão é pulada em silêncio, e a
    próxima nota mais antiga vale como âncora: a daily não pode deixar de
    nascer por causa de um arquivo editado à mão.
    """
    pasta = Path(vault) / PASTA_DAILY
    if not pasta.is_dir():
        return None

    anteriores: list[tuple[date, Path]] = []
    for arquivo in pasta.glob("*.md"):
        dia = _data_do_nome(arquivo.stem)
        if dia is not None and dia < antes_de:
            anteriores.append((dia, arquivo))

    for _, arquivo in sorted(anteriores, key=lambda par: par[0], reverse=True):
        momento = _momento_do_frontmatter(arquivo, "ate")
        if momento is not None:
            return momento
    return None


def desde_da_daily_de(vault: Path, dia: date) -> datetime | None:
    """O campo `desde` da daily daquele dia, se ela já existe.

    Rodar o comando de novo no mesmo dia tem que manter a mesma janela e só
    estender o `ate`. Recalcular o `desde` faria a janela escorregar para
    frente pelo tempo entre as duas execuções — e o que ficasse nesse sobejo
    não apareceria em daily nenhuma.
    """
    return _momento_do_frontmatter(Path(vault) / caminho_da_daily(dia), "desde")


def pontos_da_daily(vault: Path) -> PontosDaDaily:
    """Os itens ainda não falados de `notas/daily.md`, separados por seção.

    Só entram os **desmarcados** (`- [ ]`): quem marca é o usuário, no
    Obsidian, depois de falar. O agente lê e nunca escreve por iniciativa
    própria. Arquivo ausente, seção ausente ou lista vazia não é erro — a daily
    apenas não mostra aquela seção.
    """
    arquivo = Path(vault) / ARQUIVO_DE_PONTOS
    if not arquivo.is_file():
        return PontosDaDaily()

    colhidos: dict[str, list[str]] = {"duvidas": [], "off_topic": [], "pontos": []}
    secao: str | None = None
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if linha.lstrip().startswith("#"):
            secao = _SECOES_DOS_PONTOS.get(linha.lstrip("# ").strip().casefold())
            continue
        item = _ITEM_DESMARCADO.match(linha)
        if secao is not None and item is not None:
            colhidos[secao].append(item["texto"])

    _log.info(
        "notas/daily.md: %d dúvida(s), %d off-topic e %d ponto(s) por falar.",
        len(colhidos["duvidas"]),
        len(colhidos["off_topic"]),
        len(colhidos["pontos"]),
    )
    return PontosDaDaily(
        duvidas=tuple(colhidos["duvidas"]),
        off_topic=tuple(colhidos["off_topic"]),
        pontos=tuple(colhidos["pontos"]),
    )


def anotar_ponto(vault: Path, texto: str) -> Path:
    """Acrescenta um ponto desmarcado em `## Pontos` de `notas/daily.md`.

    A única escrita do agente na zona do usuário, e só a pedido explícito
    (`daily --anotar`). O arquivo é tratado como **append-only**: cada linha que
    já estava lá continua onde estava, porque tudo ali foi digitado à mão e um
    bug que reescrevesse o arquivo apagaria texto do usuário.
    """
    arquivo = Path(vault) / ARQUIVO_DE_PONTOS
    existente = arquivo.read_text(encoding="utf-8") if arquivo.is_file() else None
    linhas = (existente if existente is not None else MODELO_DOS_PONTOS).splitlines()

    escrito = escrever(
        vault,
        ARQUIVO_DE_PONTOS,
        "\n".join(_com_o_ponto(linhas, f"- [ ] {texto.strip()}")) + "\n",
        zonas=(PASTA_NOTAS,),
    )
    _log.info("Ponto anotado em %s", ARQUIVO_DE_PONTOS)
    return escrito


def montar_daily(
    *,
    janela: "JanelaDaDaily",
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
    roteiro: Daily | None,
    pontos: PontosDaDaily,
    falha_do_roteiro: str | None = None,
) -> str:
    """Monta o markdown da daily: o roteiro em cima, as listas cruas embaixo.

    As seções do usuário só aparecem quando têm conteúdo: um rótulo vazio no
    roteiro é um buraco que ele pularia em voz alta.
    """
    frontmatter = _frontmatter(
        {
            "tipo": TIPO_DAILY,
            "data": janela.data.isoformat(),
            "desde": janela.desde.isoformat(),
            "ate": janela.ate.isoformat(),
            "fontes": list(fontes_lidas),
            "fontes_com_falha": [falha.fonte for falha in fontes_com_falha],
            "temas": list(_temas_dos_eventos(eventos)),
            "reunioes": [wikilink(reuniao) for reuniao in reunioes],
        }
    )

    corpo = [
        f"# Daily — {_data_por_extenso(janela.data)}",
        "",
        cobertura_da_janela(janela),
        "",
    ]
    for aviso in _avisos_da_daily(fontes_com_falha, roteiro, falha_do_roteiro):
        corpo.extend([f"> {aviso}", ""])

    for titulo, itens in secoes_do_roteiro(roteiro, pontos):
        corpo.extend([f"## {titulo}", "", _lista(itens), ""])

    corpo.extend(_listas_cruas(eventos, reunioes, fontes_lidas, fontes_com_falha))

    return frontmatter + "\n".join(corpo)


def secoes_do_roteiro(
    roteiro: Daily | None, pontos: PontosDaDaily
) -> list[tuple[str, tuple[str, ...]]]:
    """As seções faladas, na ordem de falar — nota e terminal usam as mesmas.

    As quatro do Claude aparecem mesmo vazias, porque "nada esperando ninguém"
    é uma daily boa de ouvir; as duas que são só do usuário desaparecem quando
    ele não escreveu nada.
    """
    duvidas = (*(roteiro.duvidas if roteiro else ()), *pontos.duvidas)
    secoes: list[tuple[str, tuple[str, ...]]] = []
    if roteiro is not None:
        secoes.append(("Entreguei", roteiro.entreguei))
        secoes.append(("Sigo em", roteiro.sigo_em))
        secoes.append(("Preciso de", roteiro.preciso_de))
    if roteiro is not None or duvidas:
        secoes.append(("Dúvidas", duvidas))
    if pontos.pontos:
        secoes.append(("Meus pontos", pontos.pontos))
    if pontos.off_topic:
        secoes.append(("Off-topic", pontos.off_topic))
    return secoes


def cobertura_da_janela(janela: "JanelaDaDaily") -> str:
    """A linha "Cobre de ... até agora" — obrigatória na nota e no terminal.

    Sem ela o usuário lê a daily de sexta numa segunda achando que é de ontem.

    A frase da primeira daily não afirma que o período tem 24 horas: rodar de
    novo no mesmo dia mantém o início e estende o fim, e a janela passa disso.
    O que ela explica é de onde veio a âncora.
    """
    quando = f"{_dia_curto(janela.desde)}, {janela.desde:%d/%m %H:%M}"
    if janela.primeira:
        return (
            f"Cobre de {quando}, até agora — esta é a primeira daily, e sem nota "
            f"anterior para ancorar a janela ela começa 24 horas antes da primeira "
            f"execução."
        )
    return f"Cobre de {quando}, até agora."


def _avisos_da_daily(
    fontes_com_falha: Sequence["FalhaDeFonte"],
    roteiro: Daily | None,
    falha_do_roteiro: str | None,
) -> list[str]:
    avisos = [
        f"{nome_legivel(falha.fonte)} não entrou nesta daily: {falha.motivo}"
        for falha in fontes_com_falha
    ]
    if roteiro is None:
        motivo = falha_do_roteiro or "o roteiro da daily não está configurado."
        avisos.append(
            f"Esta daily não tem roteiro: {motivo} "
            "As listas cruas abaixo continuam completas."
        )
    return avisos


def _temas_dos_eventos(eventos: Sequence[Evento]) -> tuple[str, ...]:
    """As referências distintas da janela — repositórios, projetos, canais.

    O roteiro da daily não tem campo de temas, e inventar um custaria outra
    pergunta ao Claude. As referências já são exatamente o que o frontmatter
    quer: os nomes por onde o usuário vai procurar este período meses depois.
    """
    return tuple(
        dict.fromkeys(evento.referencia for evento in eventos if evento.referencia)
    )


def _com_o_ponto(linhas: list[str], item: str) -> list[str]:
    """As linhas do arquivo com o item novo no fim da seção `## Pontos`."""
    inicio = _indice_da_secao(linhas, "pontos")
    if inicio is None:
        return [*linhas, "", "## Pontos", "", item]

    fim = _fim_da_secao(linhas, inicio)
    while fim > inicio + 1 and not linhas[fim - 1].strip():
        fim -= 1
    return [*linhas[:fim], item, *linhas[fim:]]


def _indice_da_secao(linhas: Sequence[str], chave: str) -> int | None:
    for indice, linha in enumerate(linhas):
        if linha.lstrip().startswith("#") and (
            _SECOES_DOS_PONTOS.get(linha.lstrip("# ").strip().casefold()) == chave
        ):
            return indice
    return None


def _fim_da_secao(linhas: Sequence[str], inicio: int) -> int:
    for indice in range(inicio + 1, len(linhas)):
        if linhas[indice].lstrip().startswith("#"):
            return indice
    return len(linhas)


def _data_do_nome(nome: str) -> date | None:
    """`2026-09-04` do nome de uma daily; `None` se o arquivo foi renomeado."""
    try:
        return datetime.strptime(nome, "%Y-%m-%d").date()
    except ValueError:
        return None


def _momento_do_frontmatter(arquivo: Path, chave: str) -> datetime | None:
    """Lê um campo de data-hora do frontmatter, sempre devolvendo algo aware."""
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not linhas or linhas[0].strip() != "---":
        return None

    for linha in linhas[1:]:
        if linha.strip() == "---":
            return None
        nome, separador, valor = linha.partition(":")
        if not separador or nome.strip() != chave:
            continue
        try:
            momento = datetime.fromisoformat(valor.strip().strip('"').strip("'"))
        except ValueError:
            return None
        return momento if momento.tzinfo else momento.astimezone()
    return None


def _dia_curto(momento: datetime) -> str:
    """`quinta`, `sábado` — o dia da semana como se diz em voz alta."""
    return _DIAS_DA_SEMANA[momento.weekday()].removesuffix("-feira")


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
