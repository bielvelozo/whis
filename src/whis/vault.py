"""Escrita no vault: pastas, diário, daily, nota viva, respostas e jornal.

A zona de propriedade é uma invariante deste módulo, não só dos testes — e ela
é **por coletor**: `escrever` recebe as zonas que aquela chamada permite. O
do diário escreve só em `diario/`; o da daily, só em `daily/`. Nenhum alcança
a zona do outro. `reunioes/` e `transcricoes/` só são lidas: nenhum coletor
escreve nelas desde que a gravação saiu do Whis.

`notas/` é a zona do usuário e é recusada para todos eles. A nota viva
`daily/atual.md` é a terceira zona: mora em `daily/`, mas o que o agente pode
fazer nela é decidido seção a seção em `nota_viva.py` — aqui só se lê e se
grava o arquivo, **sem traduzir quebra de linha**, porque cada byte que o
usuário escreveu ali precisa voltar igual.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from . import obsidian as _obsidian
from .configuracao import Configuracao
from .fontes import ORDEM_DAS_FONTES, Evento, Janela, nome_legivel
from .nota_viva import (
    SECAO_DUVIDAS,
    SECAO_FALAR,
    SECAO_FAZENDO,
    SECAO_FIZ,
    SECAO_PONTOS,
    Mudancas,
    NotaViva,
    sem_brancos_nas_pontas,
)
from .portas import ResumoDoDia

if TYPE_CHECKING:  # ambos importam este módulo em tempo de execução
    from .busca import Resposta
    from .coleta import FalhaDeFonte
    from .daily import JanelaDaDaily
    from .jornal import Edicao

_log = logging.getLogger("whis.vault")

PASTA_REUNIOES = "reunioes"
PASTA_TRANSCRICOES = "transcricoes"
PASTA_DIARIO = "diario"
PASTA_DAILY = "daily"
PASTA_RESPOSTAS = "respostas"
PASTA_NOTAS = "notas"
PASTA_NOTICIAS = "noticias"

#: Todas as pastas criadas na primeira execução.
ESTRUTURA = (
    PASTA_REUNIOES,
    PASTA_TRANSCRICOES,
    PASTA_DIARIO,
    PASTA_DAILY,
    PASTA_RESPOSTAS,
    PASTA_NOTAS,
    PASTA_NOTICIAS,
)

#: A única pasta em que o coletor de diário pode escrever.
ZONAS_DO_DIARIO = (PASTA_DIARIO,)

#: A única pasta em que o coletor de daily pode escrever.
ZONAS_DA_DAILY = (PASTA_DAILY,)

#: A única pasta em que `perguntar` da palheta pode escrever.
ZONAS_DAS_RESPOSTAS = (PASTA_RESPOSTAS,)

#: A única pasta em que o jornal escreve; `noticias/fontes.md` ali é do usuário.
ZONAS_DO_JORNAL = (PASTA_NOTICIAS,)

#: A nota viva: a única nota que agente e usuário mantêm juntos.
CAMINHO_DA_NOTA_VIVA = f"{PASTA_DAILY}/atual.md"

#: As duas seções da nota datada que falam da nota viva.
SECAO_MUDANCAS = "Mudanças na nota viva"
SECAO_ARQUIVO = "O que eu fiz na daily anterior"

#: O que abre as listas cruas numa nota, abaixo do que foi escrito sobre elas.
_SEPARADOR = "---"

_NADA_REGISTRADO = "_(nada registrado)_"

#: Valor do campo `tipo` no frontmatter de cada artefato.
TIPO_DIARIO = "diario"
TIPO_DAILY = "daily"
TIPO_RESPOSTA = "resposta"

#: O callout recolhido com as fontes de uma resposta: a spec diz que a fonte
#: não aparece por padrão — recolhida, ela não aparece e continua na nota
#: para o "de onde?".
CALLOUT_DAS_FONTES = "> [!info]- Fontes"

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

_DECK_NO_FRONTMATTER = re.compile(r'^deck:\s*"?(https://[^\s"]+)"?\s*$', re.M)

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
    zonas: Sequence[str],
    literal: bool = False,
) -> Path:
    """Escreve um arquivo no vault, recusando caminhos fora de `zonas`.

    As zonas são parâmetro porque a propriedade é de cada coletor: o do
    diário nunca escreve em `daily/`, o da daily nunca escreve em `diario/`,
    e `notas/` fica fora do alcance de todos.

    A checagem é feita no caminho **resolvido**: não basta começar com o nome
    de uma zona, o arquivo precisa terminar dentro dela. Assim `..` no meio do
    caminho não escapa para `notas/` nem para fora do vault.

    `literal=True` grava o texto como está, sem trocar a quebra de linha pela
    do sistema — é o que a nota viva exige para voltar byte a byte.
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
    alvo.write_text(conteudo, encoding="utf-8", newline="" if literal else None)
    _log.info("Escrito no vault: %s", relativo)
    return alvo


def _recusa(relativo: str, zonas: Sequence[str]) -> str:
    permitidas = ", ".join(f"{zona}/" for zona in zonas) or "nenhuma pasta"
    return f"Esta escrita só alcança {permitidas} — recusado: {relativo!r}"


def uri_do_obsidian(configuracao: Configuracao, caminho_relativo: str) -> str:
    """A URI `obsidian://open` de uma nota do vault — ver `whis.obsidian`.

    Vive lá, e não aqui, porque a bandeja também precisa dela e não pode
    importar este módulo.
    """
    return _obsidian.uri_da_nota(configuracao, caminho_relativo)


def wikilink(caminho_relativo: str) -> str:
    """Wikilink do Obsidian para um caminho do vault, sem a extensão.

    Usa o caminho e não só o nome porque nota e transcrição compartilham o
    basename — o link curto seria ambíguo dentro do vault.
    """
    return f"[[{caminho_relativo.removesuffix('.md')}]]"


def caminho_do_diario(data: date) -> str:
    """Caminho relativo do diário: um arquivo por dia, sem hora no nome."""
    return f"{PASTA_DIARIO}/{data.isoformat()}.md"


def reunioes_na_janela(vault: Path, janela: Janela) -> tuple[str, ...]:
    """As notas de reunião cujo horário cai na janela, em ordem cronológica.

    O horário vem do prefixo `YYYY-MM-DD-HHMM` do nome do arquivo. É o que faz
    a reunião da meia-noite e meia aparecer no diário do dia anterior, igual
    aos commits.

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
        corpo.extend([f"> [!warning] {aviso}", ""])

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
        _SEPARADOR,
        "",
        "*Daqui para baixo, tudo que a janela trouxe, para conferir de onde veio "
        "cada afirmação. Recolha um cabeçalho para tirá-lo da tela.*",
        "",
        "## Reuniões",
        "",
        _lista(tuple(wikilink(reuniao) for reuniao in reunioes)),
        "",
    ]

    motivos = {falha.fonte: falha.motivo for falha in fontes_com_falha}
    for fonte in _fontes_em_ordem(fontes_lidas, [falha.fonte for falha in fontes_com_falha]):
        # A contagem só entra quando há o que contar: uma fonte muda fica com o
        # título limpo, e é ele que precede o `_(nada registrado)_`.
        quantos = sum(1 for evento in eventos if evento.fonte == fonte)
        rotulo = f"{nome_legivel(fonte)} ({quantos})" if quantos else nome_legivel(fonte)
        linhas.extend([f"## {rotulo}", ""])
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


def caminho_da_daily(data: date) -> str:
    """Caminho relativo da daily: um arquivo por dia, sem hora no nome."""
    return f"{PASTA_DAILY}/{data.isoformat()}.md"


def montar_copia_da_daily(
    *,
    gerada: datetime,
    deck: str | None,
    secoes: Sequence[tuple[str, Sequence[str]]],
    aviso: str | None = None,
) -> str:
    """A cópia do que foi para o deck, com o link no frontmatter.

    Sem campo `data`: a Daily notes do Obsidian o transformaria em link para
    uma nota que não existe (passo 8 de `docs/smoke-interface.md`).
    """
    campos: dict[str, object] = {"tipo": TIPO_DAILY}
    if deck:
        campos["deck"] = deck
    campos["gerada"] = gerada.isoformat(timespec="seconds")

    linhas = [f"# Daily — {_data_por_extenso(gerada.date())}", ""]
    if deck:
        linhas.extend([f"> [!info] [Abrir os slides]({deck})", ""])
    if aviso:
        linhas.extend([f"> [!warning] {aviso}", ""])
    for titulo, conteudo in secoes:
        linhas.extend([f"## {titulo}", "", *conteudo, ""])
    return _frontmatter(campos) + "\n".join(linhas)


def ultimo_deck(vault: Path) -> str | None:
    """O `deck:` da nota datada mais recente de `daily/` que tem um."""
    pasta = Path(vault) / PASTA_DAILY
    if not pasta.is_dir():
        return None
    datadas = sorted(
        ((dia, arquivo) for arquivo in pasta.glob("*.md") if (dia := _data_do_nome(arquivo.stem)) is not None),
        reverse=True,
    )
    for _dia, arquivo in datadas:
        casou = _DECK_NO_FRONTMATTER.search(_frontmatter_cru(arquivo))
        if casou:
            return casou.group(1)
    return None


def _frontmatter_cru(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    if not texto.startswith("---"):
        return ""
    fim = texto.find("\n---", 3)
    return texto[: fim if fim != -1 else 0]


def caminho_da_resposta(momento: datetime, pergunta: str) -> str:
    """`respostas/YYYY-MM-DD-HHMM-<slug>.md`, o slug tirado da pergunta."""
    return f"{PASTA_RESPOSTAS}/{momento:%Y-%m-%d-%H%M}-{_slug(pergunta)}.md"


def _slug(texto: str) -> str:
    """Só `a-z`, `0-9` e hífen, até 60 caracteres; sem nada aproveitável, `resposta`."""
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-").lower()
    return slug[:60].strip("-") or TIPO_RESPOSTA


def montar_resposta(*, pergunta: str, resposta: "Resposta") -> str:
    """Monta a nota de uma resposta da palheta: a pergunta, a resposta e as fontes recolhidas.

    Sem campo `data`: a Daily notes do Obsidian o transformaria em link para
    uma nota inexistente na raiz (armadilha achada no ticket 04).
    """
    frontmatter = _frontmatter(
        {
            "tipo": TIPO_RESPOSTA,
            "pergunta": " ".join(pergunta.split()),
            "achou": "true" if resposta.achou else "false",
        }
    )
    texto = resposta.texto.strip() or (
        "Não achei nada no vault que responda a isso."
        if not resposta.achou
        else "_(a resposta veio vazia)_"
    )
    corpo = [f"# {' '.join(pergunta.split())}", "", texto, "", CALLOUT_DAS_FONTES]
    if resposta.citacoes:
        for citacao in resposta.citacoes:
            trecho = f" — {citacao.trecho}" if citacao.trecho else ""
            corpo.append(f"> - `{citacao.origem}`{trecho}")
    elif resposta.achou:
        corpo.append("> _(a resposta não cita nota nenhuma)_")
    else:
        corpo.append("> _(nenhuma: nenhuma nota do vault sustenta uma resposta)_")
    corpo.append("")
    return frontmatter + "\n".join(corpo)


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


def ler_nota_viva(vault: Path) -> NotaViva:
    """A nota viva como está no vault — ou a do modelo, se ainda não existe.

    Lê os bytes, não o texto: `read_text` traduziria `\\r\\n`, e a nota precisa
    voltar ao disco exatamente como o usuário a deixou.
    """
    arquivo = Path(vault) / CAMINHO_DA_NOTA_VIVA
    if not arquivo.is_file():
        return NotaViva.do_modelo()
    return NotaViva.de_texto(arquivo.read_bytes().decode("utf-8"))


def escrever_nota_viva(vault: Path, nota: NotaViva) -> Path:
    """Grava a nota viva, literalmente, e só em `daily/`."""
    return escrever(vault, CAMINHO_DA_NOTA_VIVA, nota.texto(), zonas=ZONAS_DA_DAILY, literal=True)


def anotar_ponto(vault: Path, texto: str, secao: str = SECAO_PONTOS) -> Path:
    """Acrescenta uma linha no fim de `## Pontos`, `## Dúvidas` ou `## Fazer` da nota viva.

    O único gesto do agente numa seção do usuário, e só a pedido explícito
    (`daily --anotar`, `note`/`doubt`/`do` na palheta, `anotar` na DM). Em
    *Fazer* a linha nasce `- [ ] texto`, e quem marca é ele. É
    **append-only**: todo byte fora da linha nova continua onde estava, porque
    o que há ali foi digitado à mão.
    """
    nota = ler_nota_viva(vault)
    nota.anotar(texto, secao)
    escrito = escrever_nota_viva(vault, nota)
    _log.info("Ponto anotado em '%s' de %s", secao, CAMINHO_DA_NOTA_VIVA)
    return escrito


def arquivo_da_nota_viva(vault: Path, dia: date) -> tuple[str, ...] | None:
    """O bloco de *O que eu fiz* que a daily de hoje já arquivou.

    `None` diz que a nota viva ainda não foi arquivada nesta janela: não há
    daily de hoje, ou ela nasceu sem a seção — o roteiro falhou antes de a
    nota viva ser tocada. É esse sinal que faz a segunda execução do dia não
    arquivar de novo, e a reexecução depois de uma falha arquivar enfim.

    A seção vai até o separador das listas cruas, que não é um título: é a
    mesma régua que `montar_daily` usa para escrever.
    """
    arquivo = Path(vault) / caminho_da_daily(dia)
    if not arquivo.is_file():
        return None
    nota = NotaViva.de_texto(arquivo.read_bytes().decode("utf-8"))
    if not nota.tem_secao(SECAO_ARQUIVO):
        return None
    secao = nota.conteudo(SECAO_ARQUIVO)
    fim = next((i for i, linha in enumerate(secao) if linha.strip() == _SEPARADOR), len(secao))
    bloco = sem_brancos_nas_pontas(secao[:fim])
    return () if bloco == (_NADA_REGISTRADO,) else bloco


def montar_daily(
    *,
    janela: "JanelaDaDaily",
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
    mudancas: Mudancas | None,
    arquivado: Sequence[str] | None,
    falha_do_roteiro: str | None = None,
) -> str:
    """Monta o markdown da nota datada: o que mudou na nota viva, e as listas cruas.

    O roteiro não mora mais aqui — ele é a nota viva. O que esta nota guarda é
    a janela, o que esta execução acrescentou e moveu, o bloco de *O que eu
    fiz* arquivado ao abrir a janela, e tudo que as fontes trouxeram.
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
        f"> [!info] {cobertura_da_janela(janela)}",
        "",
    ]
    for aviso in _avisos_da_daily(fontes_com_falha, mudancas, falha_do_roteiro):
        corpo.extend([f"> [!warning] {aviso}", ""])

    if mudancas is not None:
        corpo.extend([f"## {SECAO_MUDANCAS}", "", *_secao_das_mudancas(mudancas), ""])
    if arquivado is not None:
        corpo.extend([f"## {SECAO_ARQUIVO}", "", *(arquivado or [_NADA_REGISTRADO]), ""])

    corpo.extend(_listas_cruas(eventos, reunioes, fontes_lidas, fontes_com_falha))

    return frontmatter + "\n".join(corpo)


def _secao_das_mudancas(mudancas: Mudancas) -> list[str]:
    """Os blocos que entraram na nota viva, literais, alinhados à esquerda."""
    if mudancas.vazia():
        return ["_(nada)_"]
    linhas: list[str] = []
    if mudancas.acrescentadas:
        linhas.extend(["**Acrescentado:**", ""])
        for bloco in mudancas.acrescentadas:
            linhas.extend(_alinhado(bloco))
        linhas.append("")
    if mudancas.movidas:
        linhas.extend([f"**Movido de _{SECAO_FAZENDO}_ para _{SECAO_FIZ}_:**", ""])
        for bloco in mudancas.movidas:
            linhas.extend(_alinhado(bloco))
        linhas.append("")
    return linhas[:-1]


def _alinhado(bloco: Sequence[str]) -> list[str]:
    """Um bloco de linhas literais sem a indentação da primeira, para não virar código."""
    if not bloco:
        return []
    recuo = len(bloco[0]) - len(bloco[0].lstrip(" \t"))
    return [linha[recuo:] if linha[:recuo].strip() == "" else linha for linha in bloco]


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
    mudancas: Mudancas | None,
    falha_do_roteiro: str | None,
) -> list[str]:
    avisos = [
        f"{nome_legivel(falha.fonte)} não entrou nesta daily: {falha.motivo}"
        for falha in fontes_com_falha
    ]
    if mudancas is None:
        motivo = falha_do_roteiro or "o roteiro da daily não está configurado."
        avisos.append(
            f"A nota viva ficou como estava: {motivo} "
            "As listas cruas abaixo continuam completas."
        )
    elif falha_do_roteiro:
        avisos.append(f"Nada novo entrou na nota viva: {falha_do_roteiro}")
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
        return _NADA_REGISTRADO
    return "\n".join(f"- {item}" for item in itens)


def montar_jornal(edicao: "Edicao") -> str:
    """A nota `noticias/YYYY-MM-DD.md`: o dado da edição, do mesmo objeto que gera a página.

    A imagem aponta a capa original da fonte: as reduzidas (`img/N.jpg`) só
    existem no artifact, não no vault.
    """
    from .pagina_do_jornal import NADA_RELEVANTE, data_por_extenso, hora, texto_do_custo, texto_do_plano

    def janelas(janela) -> str:
        if janela is None:
            return ""
        return f"5h={_ou_vazio(janela.cinco_horas)} 7d={_ou_vazio(janela.sete_dias)}"

    campos: dict[str, object] = {
        "tipo": "jornal",
        "data": edicao.data.isoformat(),
        "gerado_em": edicao.gerado_em.isoformat(timespec="seconds"),
        "artifact": edicao.artifact or "",
        "plano_antes": janelas(edicao.plano_antes),
        "plano_depois": janelas(edicao.plano_depois),
        "custo_usd": "" if edicao.custo_usd is None else f"{edicao.custo_usd:.4f}",
        "segundos": f"{edicao.segundos:.0f}",
        "fontes_com_falha": list(edicao.fontes_com_falha),
    }
    medida = " · ".join(
        parte
        for parte in (
            f"gerado às {edicao.gerado_em.strftime('%H:%M')}",
            texto_do_plano(edicao.plano_antes, edicao.plano_depois),
            texto_do_custo(edicao.custo_usd),
        )
        if parte
    )
    linhas = [f"# Jornal do Whis — {data_por_extenso(edicao.data)}", "", f"_{medida}_", ""]
    if edicao.artifact:
        linhas += [f"[Abrir a página]({edicao.artifact})", ""]
    for aviso in edicao.avisos:
        linhas += [f"> {aviso[:1].upper()}{aviso[1:]}.", ""]

    def aula(a, nivel: str) -> list[str]:
        fontes = ", ".join(f"[{_dominio(url)}]({url})" for url in a.fontes)
        return [f"{nivel} {a.titulo}", "", a.texto, "", f"Fontes: {fontes}", ""]

    def item(i) -> list[str]:
        bloco = [f"### [{i.titulo}]({i.link})", ""]
        if i.imagem:
            bloco += [f"![]({i.imagem})", ""]
        if i.resumo:
            bloco += [i.resumo, ""]
        rodape = i.fonte + (f" · {hora(i.data)}" if i.data else "")
        return bloco + [f"_{rodape}_", ""]

    if edicao.aprender:
        linhas += ["## Aprender hoje", "", *aula(edicao.aprender, "###")]
    for secao in edicao.secoes:
        linhas += [f"## {secao.titulo}", ""]
        if secao.id == "futebol":
            if edicao.time:
                linhas += [f"### {edicao.time_nome or 'Time'}", ""]
                for i in edicao.time:
                    resumo = f" {i.resumo}" if i.resumo else ""
                    linhas.append(f"- **[{i.titulo}]({i.link})** — {i.fonte}, {hora(i.data)}.{resumo}")
                linhas.append("")
            if edicao.placar is not None:
                linhas += ["### Placares", ""]
                if edicao.placar.jogos:
                    ligas: dict[str, list] = {}
                    for jogo in edicao.placar.jogos:
                        ligas.setdefault(jogo.liga, []).append(jogo)
                    for liga, jogos in ligas.items():
                        linhas += [f"**{liga}**", ""]
                        for jogo in jogos:
                            gols = "; ".join(f"{g.minuto} {g.autor}" for g in jogo.gols) or "sem gols"
                            linhas.append(
                                f"- {jogo.mandante} **{jogo.placar_mandante} x {jogo.placar_visitante}** "
                                f"{jogo.visitante} ({jogo.hora_brt}) — {gols}"
                            )
                        linhas.append("")
                else:
                    linhas += [f"_{edicao.placar.texto}_", ""]
            if edicao.efemeride is not None:
                e = edicao.efemeride
                prefixo = f"{e.ano}: " if e.ano else ""
                fonte = f" ([Wikipédia]({e.link}))" if e.link else ""
                linhas += ["### Curiosidade do dia", "", f"{prefixo}{e.texto}{fonte}", ""]
        if secao.itens:
            for i in secao.itens:
                linhas += item(i)
        else:
            linhas += [f"_{NADA_RELEVANTE}_", ""]
        if secao.id == "carros" and edicao.para_aprender:
            linhas += ["### Para aprender", ""]
            for a in edicao.para_aprender:
                linhas += aula(a, "####")
    if edicao.fontes_com_falha:
        linhas += ["---", "", "Fontes que não responderam hoje: " + ", ".join(edicao.fontes_com_falha), ""]
    return _frontmatter(campos) + "\n".join(linhas).rstrip() + "\n"


def _ou_vazio(valor: int | None) -> str:
    return "?" if valor is None else f"{valor}%"


def _dominio(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
