"""A publicação do deck da daily: um Haiku que só opera a ferramenta Artifact.

Mesmo adaptador do jornal (`_AdaptadorDoJornal`: OAuth da conta, CLI do npm,
ambiente neutro, custo no log), com duas diferenças que só o deck tem:

- o deck nasce do tipo **Slides** numa sessão do CLI e é preenchido na
  seguinte; se a segunda falhar, o erro leva o endereço criado, para a cópia
  datada guardá-lo e o link continuar o mesmo;
- publicado é **só** o que a ferramenta confirma: a URL já vai no pedido, e um
  Haiku que a repete sem publicar não pode contar como sucesso.

As frases da ferramenta são as que a sonda registrou em
`.scratch/daily-slides/research/01-slides-headless.md`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from .jornal_claude import (
    AMBIENTE_DA_PUBLICACAO,
    FERRAMENTAS_DA_PUBLICACAO,
    MODELO_DA_PUBLICACAO,
    SISTEMA_PUBLICACAO,
    TIMEOUT_DA_PUBLICACAO_S,
    TURNOS_DA_PUBLICACAO,
    Conversa,
    _AdaptadorDoJornal,
)
from .portas import ErroDePublicacao, Publicacao
from .slides_do_deck import CAMINHO_DO_INDICE, PASTA_DOS_SLIDES, TITULO_DO_DECK

_log = logging.getLogger("whis.daily")

TIPO_SLIDES = "https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL"
TURNOS_DA_CRIACAO = 4

_URL = r"(https://claude\.ai/(?:code/)?artifact/[\w-]+)"
#: Num artifact tipado a ferramenta diz `Updated the Artifact at`; no comum, `Published … at`.
_PADRAO_DO_DECK_PUBLICADO = re.compile(rf"\bUpdated the Artifact at {_URL}|\bPublished (?!files\b)[^\n]*? at {_URL}")
#: A frase da criação traz depois a URL do tipo: casar a frase, nunca pegar a última URL.
_PADRAO_DO_DECK_CRIADO = re.compile(rf"\bCreated a new Artifact at {_URL}")
_PADRAO_DE_QUALQUER_URL = re.compile(_URL)


class PublicacaoDoDeckClaude(_AdaptadorDoJornal):
    etapa = "publicação da daily"
    erro = ErroDePublicacao

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_DA_PUBLICACAO,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_PUBLICACAO_S,
    ) -> None:
        super().__init__(modelo=modelo or MODELO_DA_PUBLICACAO, cli=cli, timeout_s=timeout_s)

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        url = url_atual or self._criar(raiz)
        try:
            conversa = self._conversar(
                pedido_de_preenchimento(raiz, arquivos, url), self._opcoes_do_deck(raiz, TURNOS_DA_PUBLICACAO)
            )
        except ErroDePublicacao as erro:
            raise ErroDePublicacao(str(erro), url=url) from erro
        publicada = url_do_deck_publicado(conversa)
        if publicada is None:
            raise ErroDePublicacao(
                "A ferramenta Artifact não confirmou a publicação dos slides. "
                f"Começo da resposta: {conversa.texto_final()[:300]!r}",
                url=url,
            )
        return Publicacao(url=publicada, medida=conversa.medida)

    def _criar(self, raiz: Path) -> str:
        conversa = self._conversar(pedido_de_criacao(), self._opcoes_do_deck(raiz, TURNOS_DA_CRIACAO))
        criada = url_do_deck_criado(conversa)
        if criada is None:
            raise ErroDePublicacao(
                "O deck da daily não foi criado: nenhuma URL veio da ferramenta. "
                f"Começo da resposta: {conversa.texto_final()[:300]!r}"
            )
        _log.info("Deck da daily criado em %s.", criada)
        return criada

    def _opcoes_do_deck(self, raiz: Path, turnos: int) -> ClaudeAgentOptions:
        return self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_PUBLICACAO,
            max_turns=turnos,
            cwd=raiz,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )


def pedido_de_criacao() -> str:
    return (
        f"Crie um deck novo com a ferramenta Artifact: action publish, type_url={TIPO_SLIDES}, "
        f"title '{TITULO_DO_DECK}', sem file_path e sem files. Não leia, não edite nem crie arquivos. "
        "Responda SOMENTE com a URL do deck criado."
    )


def pedido_de_preenchimento(raiz: Path, arquivos: tuple[str, ...], url: str) -> str:
    """Três passos em turnos separados, na ordem que o jornal provou no ticket 09."""
    base = raiz.as_posix()
    mapa = json.dumps(
        {caminho: caminho for caminho in sorted(arquivos) if caminho != CAMINHO_DO_INDICE}, ensure_ascii=False
    )
    locais = ", ".join(f"{base}/{caminho}" for caminho in sorted(arquivos))
    return (
        f"O deck {url} recebe os slides de hoje no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url}. Espere o resultado.\n"
        "Passo 2 (só depois do resultado do passo 1): ferramenta Artifact, action list com scope files "
        f"(se a ferramenta chamar essa ação de list_files, use list_files), url={url}; e leia com a "
        f"ferramenta Read cada um destes arquivos: {locais}. Espere os resultados.\n"
        f"Passo 3 (só depois dos resultados do passo 2): ferramenta Artifact, action publish, url={url}, "
        f"root={base}, file_path={base}/{CAMINHO_DO_INDICE}, label 'daily de hoje', e files com este mapa "
        f"{mapa} mais uma entrada com valor null para cada caminho {PASTA_DOS_SLIDES}/* que a listagem do "
        "passo 2 mostrou e que não está nesse mapa; overwrite_unread com a lista de todos os caminhos "
        "project/* que a listagem do passo 2 mostrou. SEM force, sem capabilities, sem contract, sem "
        "type_url.\nNão edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


def url_do_deck_publicado(conversa: Conversa) -> str | None:
    for resultado in reversed(conversa.resultados_de_ferramenta):
        achada = _PADRAO_DO_DECK_PUBLICADO.search(resultado)
        if achada:
            return achada.group(1) or achada.group(2)
    return None


def url_do_deck_criado(conversa: Conversa) -> str | None:
    """A URL que a ferramenta deu ao deck novo; nunca a do tipo, nem a do texto do modelo."""
    for resultado in reversed(conversa.resultados_de_ferramenta):
        achada = _PADRAO_DO_DECK_CRIADO.search(resultado)
        if achada:
            return achada.group(1)
    for resultado in reversed(conversa.resultados_de_ferramenta):
        for url in _PADRAO_DE_QUALQUER_URL.findall(resultado):
            if url != TIPO_SLIDES:
                return url
    return None
