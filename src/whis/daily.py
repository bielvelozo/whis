"""A costura da daily: `daily/atual.md` → deck no Claude Slides + cópia em `daily/`.

Ele escreve a nota pelo Obsidian; o Whis não escreve nada nela além dos
títulos das seções do deck que faltarem. A geração lê as seções, monta o deck
(`deck.py`), escreve os arquivos do tipo Slides numa pasta de trabalho
(`slides_do_deck.py`), publica sempre no mesmo endereço e grava
`daily/YYYY-MM-DD.md` com o que foi para o deck e o link. O endereço mora no
frontmatter dessa cópia: o vault é a fonte da verdade, como no jornal.

Falhar na publicação não custa a cópia: ela nasce com o aviso e com o endereço
que já existia (ou o recém-criado), para a geração seguinte republicar no
mesmo link.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import vault as _vault
from .configuracao import Configuracao
from .deck import SECOES_DO_DECK, Deck, montar_deck
from .portas import ErroDePublicacao, Medida, PortaPublicacaoDoDeck
from .slides_do_deck import slides_do_deck

_log = logging.getLogger("whis.daily")


@dataclass(frozen=True)
class ResultadoDaDaily:
    data: date
    deck: Deck
    url: str | None = None
    publicado: bool = False
    copia: Path | None = None
    falha_da_publicacao: str | None = None
    medida: Medida | None = None
    vazio: bool = False
    simulado: bool = False


def gerar_daily(
    agora: datetime,
    *,
    configuracao: Configuracao,
    publicacao: PortaPublicacaoDoDeck | None,
    simular: bool = False,
    pasta: Path | None = None,
) -> ResultadoDaDaily:
    """Publica o deck da nota e grava a cópia; `simular` só monta o deck.

    Gerar de novo no mesmo dia republica no mesmo endereço e reescreve a cópia
    daquele dia. Nota vazia não publica nem grava cópia.
    """
    hoje = agora.date()
    nota = _vault.ler_nota_viva(configuracao.vault)
    deck = montar_deck(nota)
    _log.info("Daily de %s: %d slide(s) da nota.", hoje.isoformat(), len(deck.slides))

    if simular:
        _log.info("Simulação — nada publicado nem gravado.")
        return ResultadoDaDaily(data=hoje, deck=deck, vazio=deck.vazio(), simulado=True)
    if publicacao is None:
        raise ValueError("Fora da simulação, gerar_daily precisa da publicação do deck.")

    raiz = _vault.preparar(configuracao.vault)
    existia = (raiz / _vault.CAMINHO_DA_NOTA_VIVA).is_file()
    abertas = [titulo for titulo, _id in SECOES_DO_DECK if nota.garantir_secao(titulo)]
    if abertas or not existia:
        _vault.escrever_nota_viva(raiz, nota)
        _log.info("Nota viva gravada; títulos abertos: %s.", ", ".join(abertas) or "nenhum")

    if deck.vazio():
        _log.info("A nota da daily está vazia — nada publicado.")
        return ResultadoDaDaily(data=hoje, deck=deck, vazio=True)

    trabalho = Path(pasta) if pasta else Path(tempfile.mkdtemp(prefix=f"whis-daily-{hoje.isoformat()}-"))
    arquivos = slides_do_deck(deck, hoje, agora=agora)
    for caminho, conteudo in arquivos.items():
        destino = trabalho / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8", newline="\n")

    url_atual = _vault.ultimo_deck(raiz)
    url, publicado, falha, medida = url_atual, False, None, None
    try:
        feita = publicacao.publicar(trabalho, tuple(sorted(arquivos)), url_atual)
        url, publicado, medida = feita.url, True, feita.medida
        _log.info("Slides publicados em %s.", url)
    except ErroDePublicacao as erro:
        falha = str(erro)
        url = erro.url or url_atual
        _log.error("Os slides não saíram: %s", erro)

    copia = _vault.escrever(
        raiz,
        _vault.caminho_da_daily(hoje),
        _vault.montar_copia_da_daily(
            gerada=agora,
            deck=url,
            secoes=[(secao.titulo, secao.linhas) for secao in deck.secoes],
            aviso=f"Os slides não saíram nesta geração: {falha}" if falha else None,
        ),
        zonas=_vault.ZONAS_DA_DAILY,
    )
    return ResultadoDaDaily(
        data=hoje,
        deck=deck,
        url=url,
        publicado=publicado,
        copia=copia,
        falha_da_publicacao=falha,
        medida=medida,
    )
