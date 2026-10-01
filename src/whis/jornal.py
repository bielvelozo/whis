"""A costura do jornal: `gerar_jornal(agora) → noticias/YYYY-MM-DD.md + artifact publicado`.

A ordem é a do protótipo que publicou as primeiras edições: coleta dos feeds →
placar e efeméride → o editor escolhe e resume → a formação pesquisa → capas →
nota → página → publicação. Cada etapa falha sozinha e a edição sai com o que
deu, dizendo o que faltou: só não nasce quando nenhum feed respondeu, porque
aí "nada relevante nas últimas 24 h" seria mentira.

**Nenhum estado fora do vault.** O endereço do artifact mora no frontmatter
de cada edição (`artifact:`) e a próxima edição republica nele; o que já saiu
é o conjunto dos links das últimas edições, lido das próprias notas; a trilha
da formação é `noticias/trilha.md`. A nota é o dado, a página é a
renderização dela — as duas saem do mesmo objeto `Edicao`.
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
import time as _relogio
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image

from . import vault as _vault
from .configuracao import Configuracao
from .efemeride import Efemeride, buscar_efemeride
from .feeds import Coleta, coletar
from .fonte_x import ErroDoX, LoginDoXVenceu, PortaDoX, candidatos_do_x
from .fontes_do_jornal import (
    CAMINHO_DAS_FONTES,
    MODELO_DAS_FONTES,
    FontesDoJornal,
    interpretar_fontes,
    ler_fontes,
)
from .pagina_do_jornal import pagina_html
from .placar_espn import Placar, buscar_placar
from .portas import (
    Aula,
    Candidato,
    ErroDeEditor,
    ErroDeFormacao,
    ErroDePublicacao,
    Escolha,
    Formacao,
    ItemEscolhido,
    Janelas,
    Medida,
    PortaEditor,
    PortaFormacao,
    PortaPublicacao,
)

_log = logging.getLogger("whis.jornal")

BRT = timezone(timedelta(hours=-3))

SECAO_DO_FUTEBOL = "futebol"
SECAO_DOS_CARROS = "carros"
CAMINHO_DA_TRILHA = f"{_vault.PASTA_NOTICIAS}/trilha.md"
CABECALHO_DA_TRILHA = "# Trilha da formação\n\nO que o jornal já ensinou, uma linha por assunto por dia.\n\n"

#: Quantas edições anteriores contam como "já publicado".
EDICOES_LEMBRADAS = 7

MAXIMO_POR_FONTE = 2
MAXIMO_DO_TIME = 2
LARGURA_DA_CAPA = 900
QUALIDADE_DA_CAPA = 80
UA_DAS_CAPAS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

AVISO_DA_ESCOLHA = "seleção automática indisponível; itens por ordem de chegada"
AVISO_DA_FORMACAO = "formação indisponível hoje"
AVISO_DA_PUBLICACAO = "a página não foi publicada; esta nota existe"
AVISO_DO_LOGIN_DO_X = "o login do X venceu: rode python -m whis x-login"
INICIO_DO_X_INDISPONIVEL = "X indisponível hoje"

_NOTA_DA_EDICAO = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
_LINK_DA_NOTA = re.compile(r"(?<!!)\[[^\]]*\]\((https?://[^)\s]+)\)")
_ARTIFACT_NO_FRONTMATTER = re.compile(r"^artifact:\s*\"?(https://[^\s\"]+)\"?\s*$", re.M)


@dataclass(frozen=True)
class ItemDoJornal:
    """Uma notícia da edição: o texto do editor e o que veio do feed."""

    titulo: str
    resumo: str
    link: str
    fonte: str
    data: datetime | None = None
    imagem: str | None = None
    capa: str | None = None


@dataclass(frozen=True)
class DicaDoJornal:
    """A Dica do dia: o post e o que o editor escreveu sobre como aplicá-lo."""

    item: ItemDoJornal
    titulo: str
    como_aplicar: str


@dataclass(frozen=True)
class SecaoDoJornal:
    id: str
    titulo: str
    itens: tuple[ItemDoJornal, ...] = ()
    dica: DicaDoJornal | None = None
    #: Por que o X não entrou na seção hoje; também está em `Edicao.avisos`.
    aviso: str | None = None


@dataclass(frozen=True)
class Edicao:
    """Tudo que a nota e a página mostram. As duas são geradas deste objeto."""

    data: date
    gerado_em: datetime
    secoes: tuple[SecaoDoJornal, ...]
    time_nome: str | None = None
    time: tuple[ItemDoJornal, ...] = ()
    placar: Placar | None = None
    efemeride: Efemeride | None = None
    capa_da_efemeride: str | None = None
    aprender: Aula | None = None
    para_aprender: tuple[Aula, ...] = ()
    avisos: tuple[str, ...] = ()
    fontes_com_falha: tuple[str, ...] = ()
    plano_antes: Janelas | None = None
    plano_depois: Janelas | None = None
    custo_usd: float | None = None
    segundos: float = 0.0
    artifact: str | None = None

    def links(self) -> tuple[str, ...]:
        return (
            tuple(item.link for secao in self.secoes for item in secao.itens)
            + tuple(secao.dica.item.link for secao in self.secoes if secao.dica)
            + tuple(item.link for item in self.time)
        )


@dataclass(frozen=True)
class ResultadoDoJornal:
    """O que a geração produziu — o suficiente para o toast e o terminal."""

    edicao: Edicao
    nota: Path | None
    pagina: Path | None
    url: str | None
    parcial: bool
    simulado: bool = False
    falha_da_publicacao: str | None = None


@dataclass(frozen=True)
class PortasDoJornal:
    """As portas que uma edição usa, montadas juntas pela casca: as três do Claude e o leitor do X."""

    editor: PortaEditor
    formacao: PortaFormacao
    publicacao: PortaPublicacao
    leitor_do_x: PortaDoX | None = None


class JornalNaoNasceu(RuntimeError):
    """Nenhum feed respondeu: a edição não é escrita nem publicada."""


def gerar_jornal(
    agora: datetime,
    configuracao: Configuracao,
    *,
    editor: PortaEditor,
    formacao: PortaFormacao,
    publicacao: PortaPublicacao,
    rede: httpx.BaseTransport | None = None,
    leitor_do_x: PortaDoX | None = None,
    simular: bool = False,
    pasta_da_edicao: Path | None = None,
    espera_sem_rede_s: float = 60.0,
    tentativas_sem_rede: int = 2,
    espera_da_segunda_rodada_s: float = 3.0,
    dormir: Callable[[float], None] = _relogio.sleep,
) -> ResultadoDoJornal:
    """Gera a edição de hoje, escreve a nota e publica a página.

    `simular=True` coleta, chama o Claude e monta nota e página numa pasta
    temporária, mas não publica nem escreve no vault.

    Levanta `JornalNaoNasceu` quando nenhum feed respondeu mesmo depois de
    esperar a rede — o caso do PC que acabou de ligar.
    """
    inicio = _relogio.monotonic()
    agora = _com_fuso(agora)
    hoje = agora.astimezone(BRT).date()
    vault = Path(configuracao.vault)

    fontes = ler_fontes(vault) if not simular else _ler_fontes_sem_criar(vault)
    ja_publicados = links_publicados(vault, hoje)
    coleta = _coletar_esperando_a_rede(
        fontes,
        agora,
        ja_publicados=ja_publicados,
        rede=rede,
        espera_sem_rede_s=espera_sem_rede_s,
        tentativas=tentativas_sem_rede,
        espera_da_segunda_rodada_s=espera_da_segunda_rodada_s,
        dormir=dormir,
    )
    coleta, avisos_do_x = _ler_o_x(leitor_do_x, fontes, coleta, agora, ja_publicados)

    tem_futebol = any(secao.id == SECAO_DO_FUTEBOL for secao in fontes.secoes)
    placar = _placar(agora, rede) if tem_futebol else None
    efemeride = _efemeride(agora, rede) if tem_futebol else None

    avisos: list[str] = list(dict.fromkeys(avisos_do_x.values()))
    limites = {secao.id: (secao.minimo, secao.maximo) for secao in fontes.secoes}
    escolha = _escolher(editor, coleta, limites, avisos)
    trilha = ler_trilha(vault)
    aulas = _ensinar(formacao, hoje, trilha, avisos)

    pasta = Path(pasta_da_edicao) if pasta_da_edicao else Path(
        tempfile.mkdtemp(prefix=f"whis-jornal-{hoje.isoformat()}-")
    )
    edicao = _montar_edicao(
        hoje,
        agora,
        fontes,
        coleta,
        escolha,
        aulas,
        placar,
        efemeride,
        avisos,
        avisos_do_x,
    )
    capas = baixar_capas(edicao, pasta, rede=rede)
    edicao = _com_capas(edicao, capas)

    medidas = [escolha.medida, aulas.medida]
    edicao = _com_medidas(edicao, medidas, inicio, artifact=ultima_url(vault))

    pagina = pasta / "jornal.html"
    pagina.write_text(pagina_html(edicao), encoding="utf-8")
    arquivos_das_capas = {relativo: pasta / relativo for relativo in sorted(set(capas.values()))}

    if simular:
        (pasta / f"{hoje.isoformat()}.md").write_text(_vault.montar_jornal(edicao), encoding="utf-8")
        _log.info("Simulação — nota e página em %s; nada publicado nem escrito no vault.", pasta)
        return ResultadoDoJornal(
            edicao=edicao,
            nota=pasta / f"{hoje.isoformat()}.md",
            pagina=pagina,
            url=None,
            parcial=bool(edicao.avisos),
            simulado=True,
        )

    raiz = _vault.preparar(vault)
    caminho = caminho_da_edicao(hoje)
    nota = _vault.escrever(raiz, caminho, _vault.montar_jornal(edicao), zonas=_vault.ZONAS_DO_JORNAL)
    acrescentar_trilha(raiz, hoje, aulas)

    url_atual = edicao.artifact
    falha: str | None = None
    try:
        publicada = publicacao.publicar(pagina, arquivos_das_capas, url_atual)
    except ErroDePublicacao as erro:
        _log.error("A página do jornal não saiu: %s", erro)
        falha = str(erro)
        edicao = replace(edicao, avisos=edicao.avisos + (AVISO_DA_PUBLICACAO,))
        edicao = _com_medidas(edicao, medidas, inicio, artifact=url_atual)
    else:
        medidas.append(publicada.medida)
        edicao = _com_medidas(edicao, medidas, inicio, artifact=publicada.url)
        _log.info("Jornal publicado em %s", publicada.url)

    nota = _vault.escrever(raiz, caminho, _vault.montar_jornal(edicao), zonas=_vault.ZONAS_DO_JORNAL)
    return ResultadoDoJornal(
        edicao=edicao,
        nota=nota,
        pagina=pagina,
        url=None if falha else edicao.artifact,
        parcial=bool(edicao.avisos),
        falha_da_publicacao=falha,
    )


def caminho_da_edicao(dia: date) -> str:
    return f"{_vault.PASTA_NOTICIAS}/{dia.isoformat()}.md"


def _edicoes(vault: Path) -> list[tuple[date, Path]]:
    pasta = Path(vault) / _vault.PASTA_NOTICIAS
    if not pasta.is_dir():
        return []
    edicoes = []
    for arquivo in pasta.iterdir():
        casou = _NOTA_DA_EDICAO.match(arquivo.name)
        if casou and arquivo.is_file():
            try:
                edicoes.append((date.fromisoformat(casou.group(1)), arquivo))
            except ValueError:
                continue
    return sorted(edicoes, reverse=True)


def ultima_url(vault: Path) -> str | None:
    """O `artifact:` da edição mais recente que tem um — onde a próxima republica."""
    for _dia, arquivo in _edicoes(vault):
        casou = _ARTIFACT_NO_FRONTMATTER.search(_cabecalho(arquivo))
        if casou:
            return casou.group(1)
    return None


def links_publicados(vault: Path, hoje: date) -> frozenset[str]:
    """Os links das últimas edições anteriores a `hoje`: não voltam amanhã.

    A edição de hoje não conta — rodar de novo no mesmo dia refaz a mesma
    edição, não uma com os restos.
    """
    links: set[str] = set()
    anteriores = [arquivo for dia, arquivo in _edicoes(vault) if dia < hoje]
    for arquivo in anteriores[:EDICOES_LEMBRADAS]:
        links.update(_LINK_DA_NOTA.findall(arquivo.read_text(encoding="utf-8", errors="replace")))
    return frozenset(links)


def _cabecalho(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    if not texto.startswith("---"):
        return ""
    fim = texto.find("\n---", 3)
    return texto[: fim if fim != -1 else 0]


def ler_trilha(vault: Path) -> str:
    arquivo = Path(vault) / CAMINHO_DA_TRILHA
    return arquivo.read_bytes().decode("utf-8") if arquivo.is_file() else ""


def acrescentar_trilha(vault: Path, dia: date, formacao: Formacao) -> Path | None:
    """Acrescenta ao fim da trilha as linhas das aulas aceitas; nunca reescreve o que havia."""
    linhas = [_linha_da_trilha(dia, aula.trilha) for aula in formacao.aulas() if aula.trilha.strip()]
    if not linhas:
        return None
    atual = ler_trilha(vault) or CABECALHO_DA_TRILHA
    if not atual.endswith("\n"):
        atual += "\n"
    return _vault.escrever(
        vault, CAMINHO_DA_TRILHA, atual + "\n".join(linhas) + "\n", zonas=_vault.ZONAS_DO_JORNAL, literal=True
    )


def _linha_da_trilha(dia: date, trilha: str) -> str:
    linha = trilha.strip()
    return linha if linha.startswith("- ") else f"- {dia.isoformat()} · {linha}"


def _ler_fontes_sem_criar(vault: Path) -> FontesDoJornal:
    arquivo = Path(vault) / CAMINHO_DAS_FONTES
    texto = arquivo.read_text(encoding="utf-8") if arquivo.is_file() else MODELO_DAS_FONTES
    return interpretar_fontes(texto)


def _com_fuso(agora: datetime) -> datetime:
    return agora.replace(tzinfo=BRT) if agora.tzinfo is None else agora


def _total_de_feeds(fontes: FontesDoJornal) -> int:
    return sum(len(secao.fontes) for secao in fontes.secoes) + (1 if fontes.time else 0)


def _coletar_esperando_a_rede(
    fontes: FontesDoJornal,
    agora: datetime,
    *,
    ja_publicados: frozenset[str],
    rede: httpx.BaseTransport | None,
    espera_sem_rede_s: float,
    tentativas: int,
    espera_da_segunda_rodada_s: float,
    dormir: Callable[[float], None],
) -> Coleta:
    total = _total_de_feeds(fontes)
    if total == 0:
        raise JornalNaoNasceu("noticias/fontes.md não tem nenhum feed.")
    for tentativa in range(tentativas + 1):
        coleta = coletar(
            fontes,
            agora,
            ja_publicados=ja_publicados,
            transporte=rede,
            espera_da_segunda_rodada_s=espera_da_segunda_rodada_s,
        )
        if len(coleta.fontes_com_falha) < total:
            return coleta
        if tentativa < tentativas:
            _log.warning(
                "Nenhum dos %d feeds respondeu — esperando a rede %.0f s (tentativa %d de %d).",
                total,
                espera_sem_rede_s,
                tentativa + 1,
                tentativas,
            )
            dormir(espera_sem_rede_s)
    raise JornalNaoNasceu(f"nenhum dos {total} feeds respondeu — sem rede?")


def _ler_o_x(
    leitor: PortaDoX | None,
    fontes: FontesDoJornal,
    coleta: Coleta,
    agora: datetime,
    ja_publicados: frozenset[str],
) -> tuple[Coleta, dict[str, str]]:
    """Uma leitura do X por edição, somada às seções das linhas `x:`.

    Devolve a coleta com os posts e as páginas que falharam sozinhas no
    rodapé, e `{seção: aviso}` quando o X inteiro ficou de fora.
    """
    do_x = [(secao.id, fonte) for secao in fontes.secoes for fonte in secao.x]
    if leitor is None or not do_x:
        return coleta, {}
    secoes = list(dict.fromkeys(secao for secao, _fonte in do_x))
    try:
        leitura = leitor.ler(tuple(fonte for _secao, fonte in do_x), agora.astimezone(BRT).date())
    except LoginDoXVenceu as erro:
        _log.error("O X ficou fora da edição: %s", erro)
        return coleta, dict.fromkeys(secoes, AVISO_DO_LOGIN_DO_X)
    except ErroDoX as erro:
        _log.error("O X ficou fora da edição: %s", erro)
        return coleta, dict.fromkeys(secoes, f"{INICIO_DO_X_INDISPONIVEL}: {erro}")
    if len(leitura.falhas) >= len(do_x):
        motivo = next(iter(leitura.falhas.values()))
        _log.error("Nenhuma página do X respondeu: %s", motivo)
        return coleta, dict.fromkeys(secoes, f"{INICIO_DO_X_INDISPONIVEL}: {motivo}")

    candidatos = dict(coleta.candidatos)
    for secao in secoes:
        posts = [post for id_, fonte in do_x if id_ == secao for post in leitura.posts.get(fonte.nome, ())]
        candidatos[secao] = candidatos.get(secao, ()) + candidatos_do_x(secao, posts, agora, ja_publicados)
    falhas = tuple(f"{nome} ({motivo})" for nome, motivo in leitura.falhas.items())
    return replace(coleta, candidatos=candidatos, fontes_com_falha=coleta.fontes_com_falha + falhas), {}


def _placar(agora: datetime, rede: httpx.BaseTransport | None) -> Placar:
    try:
        return buscar_placar(agora, transporte=rede)
    except Exception as erro:  # noqa: BLE001 — placar é uma parte, não a edição
        _log.error("O placar falhou: %s", erro)
        return Placar(jogos=(), situacao="indisponivel", texto="Placar indisponível hoje")


def _efemeride(agora: datetime, rede: httpx.BaseTransport | None) -> Efemeride | None:
    try:
        return buscar_efemeride(agora, transporte=rede)
    except Exception as erro:  # noqa: BLE001
        _log.error("A efeméride falhou: %s", erro)
        return None


def _escolher(
    editor: PortaEditor, coleta: Coleta, limites: dict[str, tuple[int, int]], avisos: list[str]
) -> Escolha:
    candidatos = {secao: tuple(itens) for secao, itens in coleta.candidatos.items()}
    if not any(candidatos.values()) and not coleta.time:
        return Escolha(secoes={secao: () for secao in candidatos})
    try:
        return editor.escolher(candidatos, limites, coleta.time)
    except ErroDeEditor as erro:
        _log.error("A escolha falhou; itens por ordem de chegada: %s", erro)
        avisos.append(AVISO_DA_ESCOLHA)
        return escolha_automatica(candidatos, limites, coleta.time)


def escolha_automatica(
    candidatos: dict[str, tuple[Candidato, ...]],
    limites: dict[str, tuple[int, int]],
    time: tuple[Candidato, ...],
) -> Escolha:
    """Sem o editor: os `minimo` mais novos de cada seção, no máximo 2 por fonte, sem resumo."""

    def mais_novos(itens: Sequence[Candidato], quantos: int) -> tuple[ItemEscolhido, ...]:
        ordenados = sorted(itens, key=lambda c: c.data or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        por_fonte: dict[str, int] = {}
        escolhidos: list[ItemEscolhido] = []
        for candidato in ordenados:
            if len(escolhidos) >= quantos:
                break
            if por_fonte.get(candidato.fonte, 0) >= MAXIMO_POR_FONTE:
                continue
            por_fonte[candidato.fonte] = por_fonte.get(candidato.fonte, 0) + 1
            escolhidos.append(ItemEscolhido(candidato=candidato, titulo=candidato.titulo, resumo=""))
        return tuple(escolhidos)

    return Escolha(
        secoes={secao: mais_novos(itens, limites.get(secao, (3, 5))[0]) for secao, itens in candidatos.items()},
        time=mais_novos(time, MAXIMO_DO_TIME),
    )


def _ensinar(formacao: PortaFormacao, hoje: date, trilha: str, avisos: list[str]) -> Formacao:
    try:
        return formacao.ensinar(hoje, trilha)
    except ErroDeFormacao as erro:
        _log.error("A formação falhou: %s", erro)
        avisos.append(AVISO_DA_FORMACAO)
        return Formacao()


def _item(escolhido: ItemEscolhido) -> ItemDoJornal:
    candidato = escolhido.candidato
    return ItemDoJornal(
        titulo=escolhido.titulo or candidato.titulo,
        resumo=escolhido.resumo,
        link=candidato.link,
        fonte=candidato.fonte,
        data=candidato.data,
        imagem=candidato.imagem,
    )


def _montar_edicao(
    hoje: date,
    agora: datetime,
    fontes: FontesDoJornal,
    coleta: Coleta,
    escolha: Escolha,
    aulas: Formacao,
    placar: Placar | None,
    efemeride: Efemeride | None,
    avisos: list[str],
    avisos_do_x: dict[str, str],
) -> Edicao:
    def dica_da(secao: str) -> DicaDoJornal | None:
        dica = escolha.dica
        if dica is None or dica.candidato.secao != secao:
            return None
        item = _item(ItemEscolhido(dica.candidato, dica.titulo, ""))
        return DicaDoJornal(item=item, titulo=dica.titulo, como_aplicar=dica.como_aplicar)

    secoes = tuple(
        SecaoDoJornal(
            id=secao.id,
            titulo=secao.titulo,
            itens=tuple(_item(escolhido) for escolhido in escolha.secoes.get(secao.id, ())),
            dica=dica_da(secao.id),
            aviso=avisos_do_x.get(secao.id),
        )
        for secao in fontes.secoes
    )
    return Edicao(
        data=hoje,
        gerado_em=agora.astimezone(BRT),
        secoes=secoes,
        time_nome=fontes.time.nome if fontes.time else None,
        time=tuple(_item(escolhido) for escolhido in escolha.time),
        placar=placar,
        efemeride=efemeride,
        aprender=aulas.software,
        para_aprender=aulas.carros,
        avisos=tuple(avisos),
        fontes_com_falha=coleta.fontes_com_falha,
    )


def baixar_capas(
    edicao: Edicao, pasta: Path, *, rede: httpx.BaseTransport | None = None
) -> dict[str, str]:
    """Baixa e reduz as capas dos itens escolhidos e da efeméride: `{url original: "img/N.jpg"}`.

    Capa que não baixa, não é imagem ou não abre fica de fora — o item sai sem capa.
    """
    urls: list[str] = []
    for item in [*(i for s in edicao.secoes for i in s.itens), *edicao.time]:
        if item.imagem and item.imagem not in urls:
            urls.append(item.imagem)
    if edicao.efemeride and edicao.efemeride.imagem and edicao.efemeride.imagem not in urls:
        urls.append(edicao.efemeride.imagem)
    if not urls:
        return {}

    pasta_das_capas = Path(pasta) / "img"
    pasta_das_capas.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        transport=rede, follow_redirects=True, timeout=15, headers={"User-Agent": UA_DAS_CAPAS}
    ) as cliente:
        with ThreadPoolExecutor(max_workers=8) as grupo:
            imagens = list(grupo.map(lambda url: _baixar_imagem(cliente, url), urls))

    capas: dict[str, str] = {}
    for url, imagem in zip(urls, imagens):
        if imagem is None:
            continue
        relativo = f"img/{len(capas) + 1}.jpg"
        (Path(pasta) / relativo).write_bytes(imagem)
        capas[url] = relativo
    _log.info("%d de %d capas baixadas.", len(capas), len(urls))
    return capas


def _baixar_imagem(cliente: httpx.Client, url: str) -> bytes | None:
    try:
        resposta = cliente.get(url)
        if resposta.status_code != 200 or "image" not in resposta.headers.get("content-type", ""):
            return None
        if "svg" in resposta.headers.get("content-type", ""):
            return None
        imagem = Image.open(io.BytesIO(resposta.content)).convert("RGB")
        if imagem.width > LARGURA_DA_CAPA:
            imagem = imagem.resize((LARGURA_DA_CAPA, int(imagem.height * LARGURA_DA_CAPA / imagem.width)))
        saida = io.BytesIO()
        imagem.save(saida, "JPEG", quality=QUALIDADE_DA_CAPA, optimize=True)
        return saida.getvalue()
    except Exception as erro:  # noqa: BLE001 — capa é enfeite, nunca derruba a edição
        _log.debug("Capa %s não serviu: %s", url, erro)
        return None


def _com_capas(edicao: Edicao, capas: dict[str, str]) -> Edicao:
    def com_capa(item: ItemDoJornal) -> ItemDoJornal:
        return replace(item, capa=capas.get(item.imagem)) if item.imagem else item

    return replace(
        edicao,
        secoes=tuple(replace(s, itens=tuple(com_capa(i) for i in s.itens)) for s in edicao.secoes),
        time=tuple(com_capa(i) for i in edicao.time),
        capa_da_efemeride=capas.get(edicao.efemeride.imagem) if edicao.efemeride and edicao.efemeride.imagem else None,
    )


def _com_medidas(
    edicao: Edicao, medidas: Sequence[Medida], inicio: float, *, artifact: str | None
) -> Edicao:
    antes = next((m.plano_primeiro for m in medidas if m.plano_primeiro), None)
    depois = next((m.plano_ultimo for m in reversed(medidas) if m.plano_ultimo), None)
    custos = [m.custo_usd for m in medidas if m.custo_usd is not None]
    return replace(
        edicao,
        plano_antes=antes,
        plano_depois=depois,
        custo_usd=round(sum(custos), 4) if custos else None,
        segundos=round(_relogio.monotonic() - inicio, 1),
        artifact=artifact,
    )
