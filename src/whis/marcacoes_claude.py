"""A porta das marcações: o que ele marcou na página como lido e o que respondeu no quiz.

O banco da página só se lê por uma sessão do CLI com a ferramenta `ArtifactData`,
que em `dontAsk` lê mas não grava nem salva em disco (`out_dir` é negado; ver
`.scratch/jornal-formacao/research/00-banco-e-fotos.md`). Por isso o Python lê o
texto que a ferramenta devolveu — uma linha JSON por documento entre os
marcadores — e nunca o que o modelo escreveu: só com `ArtifactData` a sessão
nasce sem ferramenta e o modelo responde "OK" sem ter lido nada.

A leitura pede só o que interessa (`where`), para o custo não crescer com as
coleções, e segue o `next_cursor` até a última página. Página seguinte não lida,
permissão negada ou texto fora do formato viram `ErroDeMarcacoes`: perder uma
marcação calado faria a trilha andar sem ele ter lido, ou parar sem motivo.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from .jornal_claude import AMBIENTE_DA_PUBLICACAO, SISTEMA_PUBLICACAO, _AdaptadorDoJornal
from .portas import ErroDeMarcacoes, Marcacoes, Resposta

_log = logging.getLogger("whis.jornal")

MODELO_DA_LEITURA = "haiku"
TIMEOUT_DA_LEITURA_S = 180.0
TURNOS_DA_LEITURA = 12
FERRAMENTAS_DA_LEITURA = ["Artifact", "ArtifactData"]
LIMITE_POR_PAGINA = 1000

COLECAO_DAS_LEITURAS = "leituras"
COLECAO_DAS_RESPOSTAS = "respostas"

#: Linhas, não começo do texto: quando foi a página quem gravou (o toque dele), a ferramenta põe
#: antes `<artifact-content-authored-by-others/>` e um aviso de conteúdo de terceiros.
_VAZIA = re.compile(r'^No documents matched in collection "(?P<colecao>[^"]+)"\.\s*\Z', re.M)
_SEM_BANCO = re.compile(
    r"^db read failed \(invalid-argument\): this artifact's current published version does not "
    r"declare the database capability",
    re.M,
)
_CABECALHO = re.compile(r'^\d+ documents? from collection "(?P<colecao>[^"]+)":', re.M)
_INICIO = "=== BEGIN ARTIFACT DB"
_FIM = "=== END ARTIFACT DB"
_CURSOR = re.compile(r'^next_cursor: "(?P<cursor>[^"]+)"', re.M)


@dataclass(frozen=True)
class PaginaDoBanco:
    """Um resultado de leitura: a coleção, os documentos e o cursor da página seguinte.

    `colecao` é `None` quando a página ainda não declarou o banco: aí toda
    coleção está vazia.
    """

    colecao: str | None
    documentos: tuple[dict, ...] = ()
    cursor: str | None = None


def interpretar_resultado(texto: str) -> PaginaDoBanco:
    """Lê um resultado da `ArtifactData`. Levanta `ErroDeMarcacoes` fora do formato."""
    texto = (texto or "").strip()
    if _SEM_BANCO.search(texto):
        return PaginaDoBanco(None)
    vazia = _VAZIA.search(texto)
    if vazia:
        return PaginaDoBanco(vazia["colecao"])
    cabecalho = _CABECALHO.search(texto)
    if not cabecalho or _INICIO not in texto[cabecalho.end():] or _FIM not in texto:
        raise ErroDeMarcacoes(f"A leitura do banco voltou fora do formato: {texto[:200]!r}")
    miolo = texto.split(_INICIO, 1)[1].split("\n", 1)[1].split(_FIM, 1)[0]
    documentos = []
    for linha in miolo.splitlines():
        if not linha.strip():
            continue
        try:
            documento = json.loads(linha)
        except json.JSONDecodeError as erro:
            raise ErroDeMarcacoes(f"Documento ilegível na leitura do banco: {linha[:200]!r}") from erro
        if not isinstance(documento, dict) or not isinstance(documento.get("id"), str):
            raise ErroDeMarcacoes(f"Documento sem id na leitura do banco: {linha[:200]!r}")
        documentos.append(documento)
    cursor = _CURSOR.search(texto.split(_FIM, 1)[1])
    return PaginaDoBanco(cabecalho["colecao"], tuple(documentos), cursor["cursor"] if cursor else None)


def juntar_paginas(paginas: Sequence[PaginaDoBanco], pedidas: Sequence[str]) -> dict[str, list[dict]]:
    """Os documentos de cada coleção pedida, conferindo que a última página de cada uma foi lida."""
    if any(p.colecao is None for p in paginas):
        return {colecao: [] for colecao in pedidas}
    por_colecao: dict[str, list[dict]] = {}
    for colecao in pedidas:
        dela = [p for p in paginas if p.colecao == colecao]
        if not dela:
            raise ErroDeMarcacoes(f"A leitura do banco não trouxe a coleção {colecao}.")
        if dela[-1].cursor:
            raise ErroDeMarcacoes(f"A leitura de {colecao} parou com página seguinte não lida.")
        vistos: dict[str, dict] = {}
        for pagina in dela:
            for documento in pagina.documentos:
                vistos[documento["id"]] = documento
        por_colecao[colecao] = list(vistos.values())
    return por_colecao


def leituras_de(documentos: Sequence[dict]) -> dict[str, str]:
    """`id → em` das aulas com `lida: true`; desmarcada não conta."""
    saida = {}
    for documento in documentos:
        dados = documento.get("data")
        if isinstance(dados, dict) and dados.get("lida") is True:
            saida[documento["id"]] = str(dados.get("em") or "")
    return saida


def respostas_de(documentos: Sequence[dict]) -> dict[str, Resposta]:
    saida = {}
    for documento in documentos:
        dados = documento.get("data")
        if not isinstance(dados, dict):
            continue
        escolha, certa = dados.get("escolha"), dados.get("certa")
        if isinstance(escolha, bool) or not isinstance(escolha, int) or not isinstance(certa, bool):
            _log.warning("Resposta %s com formato estranho no banco, ignorada.", documento["id"])
            continue
        saida[documento["id"]] = Resposta(escolha=escolha, certa=certa)
    return saida


def pedido_de_leitura(url: str, *, leituras_desde: str | None, quizzes: Sequence[str]) -> str:
    consultas = []
    if leituras_desde:
        consultas.append((COLECAO_DAS_LEITURAS, [["em", ">=", leituras_desde]]))
    if quizzes:
        consultas.append((COLECAO_DAS_RESPOSTAS, [["quiz", "in", list(quizzes)]]))
    linhas = [
        f"Consulta {n}: action query, collection {colecao}, query "
        f"{json.dumps({'where': onde, 'limit': LIMITE_POR_PAGINA}, ensure_ascii=False)}."
        for n, (colecao, onde) in enumerate(consultas, start=1)
    ]
    return (
        f"Ferramenta ArtifactData, url={url}. Só leitura: não grave nada e não use out_dir.\n"
        + "\n".join(linhas)
        + "\nSe um resultado trouxer next_cursor, repita a mesma consulta com query.cursor igual a ele, "
        "até vir um resultado sem next_cursor.\nResponda SOMENTE OK."
    )


class MarcacoesClaude(_AdaptadorDoJornal):
    """Um Haiku que só consulta o banco da página; quem lê o resultado é o Python."""

    etapa = "leitura das marcações"
    erro = ErroDeMarcacoes

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_DA_LEITURA,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_LEITURA_S,
    ) -> None:
        super().__init__(modelo=modelo or MODELO_DA_LEITURA, cli=cli, timeout_s=timeout_s)

    def ler(self, url: str, *, leituras_desde: str | None, quizzes: Sequence[str]) -> Marcacoes:
        if not leituras_desde and not quizzes:
            return Marcacoes()
        pedidas = [c for c, sim in ((COLECAO_DAS_LEITURAS, leituras_desde), (COLECAO_DAS_RESPOSTAS, quizzes)) if sim]
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_LEITURA,
            max_turns=TURNOS_DA_LEITURA,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        _log.info("Lendo o que foi marcado na página (%s)...", ", ".join(pedidas))
        conversa = self._conversar(pedido_de_leitura(url, leituras_desde=leituras_desde, quizzes=quizzes), opcoes)
        paginas = [interpretar_resultado(texto) for texto in conversa.resultados_de_ferramenta]
        documentos = juntar_paginas(paginas, pedidas)
        marcacoes = Marcacoes(
            leituras=leituras_de(documentos.get(COLECAO_DAS_LEITURAS, [])),
            respostas=respostas_de(documentos.get(COLECAO_DAS_RESPOSTAS, [])),
        )
        return replace(marcacoes, medida=conversa.medida)
