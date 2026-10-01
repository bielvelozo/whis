"""Sonda da camada 0 da daily em slides: o tipo Slides publica headless?

Da raiz do repositório, com o Python do projeto:

    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py criar
    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v1
    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v2

Cada passo grava o que a sessão do CLI devolveu em sonda-<passo>.txt, ao lado.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from whis.jornal_claude import (
    AMBIENTE_DA_PUBLICACAO,
    FERRAMENTAS_DA_PUBLICACAO,
    MODELO_DA_PUBLICACAO,
    SISTEMA_PUBLICACAO,
    TIMEOUT_DA_PUBLICACAO_S,
    TURNOS_DA_PUBLICACAO,
    _AdaptadorDoJornal,
)
from whis.portas import ErroDePublicacao

TIPO_SLIDES = "https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL"
AQUI = Path(__file__).resolve().parent
ESTILO = (
    "background:#16171c;color:#ecebe6;font-family:Inter, 'Segoe UI', sans-serif;"
    "padding:128px 128px 160px;display:flex;flex-direction:column;gap:48px"
)


def secao(id_: str, titulo: str, corpo: str) -> str:
    return (
        f'<section id="{id_}" style="{ESTILO}">\n'
        f'<h2 style="font-size:72px;font-weight:700;line-height:1.1">{titulo}</h2>\n'
        f"{corpo}\n"
        f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:24px;'
        f'color:#8b8a99">Sonda · {id_}</p>\n'
        "</section>\n"
    )


V1 = {
    "aninhado": secao(
        "aninhado",
        "Lista aninhada",
        '<ul style="font-size:40px;line-height:1.35"><li>pai<ul style="font-size:32px">'
        "<li>filho dentro do li</li></ul></li><li>outro pai</li></ul>",
    ),
    "irmao": secao(
        "irmao",
        "Lista irmã recuada",
        '<div style="display:flex;flex-direction:column;gap:16px">'
        '<ul style="padding:0 0 0 48px;font-size:40px;line-height:1.35;color:#ecebe6"><li>pai</li></ul>'
        '<ul style="padding:0 0 0 96px;font-size:32px;line-height:1.35;color:#b9b7c6">'
        "<li>filho como lista irmã</li></ul></div>",
    ),
    "inline": secao(
        "inline",
        "Marcas inline",
        '<ul style="font-size:40px;line-height:1.35">'
        "<li><b>negrito</b> e <i>itálico</i></li>"
        '<li><span style="color:#8b7cf6">código em cor</span></li>'
        '<li><span style="font-family:Consolas, monospace">código monoespaçado</span></li>'
        '<li><a href="https://github.com">link</a></li></ul>',
    ),
}
V2 = {
    "aninhado": V1["aninhado"].replace("filho dentro do li", "filho dentro do li (v2)"),
    "inline": V1["inline"],
}


def indice(ids: list[str]) -> str:
    return json.dumps(
        {
            "v": 4,
            "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "lists": "css",
            "title": "Daily",
            "order": ids,
            "sections": {ids[0]: {"description": "Sonda", "start": ids[0]}},
            "cover": ids[0],
            "faces": {
                "inter": {
                    "family": "Inter",
                    "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
                }
            },
            "designSystems": [],
        },
        ensure_ascii=False,
        indent=2,
    )


def pedido_de_criacao() -> str:
    return (
        f"Crie um deck novo com a ferramenta Artifact: action publish, type_url={TIPO_SLIDES}, "
        "title 'Daily', sem file_path e sem files. Não leia, não edite nem crie arquivos. "
        "Responda SOMENTE com a URL do deck criado."
    )


def pedido_de_preenchimento(raiz: Path, arquivos: tuple[str, ...], url: str) -> str:
    base = raiz.as_posix()
    mapa = json.dumps({c: c for c in sorted(arquivos) if c != "project/deck.json"}, ensure_ascii=False)
    locais = ", ".join(f"{base}/{c}" for c in sorted(arquivos))
    return (
        f"O deck {url} recebe os slides de hoje no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url}. Espere o resultado.\n"
        "Passo 2 (só depois do resultado do passo 1): ferramenta Artifact, action list com scope files "
        f"(se a ferramenta chamar essa ação de list_files, use list_files), url={url}; e leia com a "
        f"ferramenta Read cada um destes arquivos: {locais}. Espere os resultados.\n"
        f"Passo 3 (só depois dos resultados do passo 2): ferramenta Artifact, action publish, url={url}, "
        f"root={base}, file_path={base}/project/deck.json, label 'daily de hoje', e files com este mapa "
        f"{mapa} mais uma entrada com valor null para cada caminho project/slides/* que a listagem do "
        "passo 2 mostrou e que não está nesse mapa; overwrite_unread com a lista de todos os caminhos "
        "project/* que a listagem do passo 2 mostrou. SEM force, sem capabilities, sem contract, sem "
        "type_url.\nNão edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


class Sonda(_AdaptadorDoJornal):
    etapa = "sonda do deck"
    erro = ErroDePublicacao

    def __init__(self) -> None:
        super().__init__(modelo=MODELO_DA_PUBLICACAO, cli=None, timeout_s=TIMEOUT_DA_PUBLICACAO_S)

    def rodar(self, passo: str, pedido: str, cwd: Path) -> None:
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_PUBLICACAO,
            max_turns=TURNOS_DA_PUBLICACAO,
            cwd=cwd,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        saida = AQUI / f"sonda-{passo}.txt"
        try:
            conversa = self._conversar(pedido, opcoes)
        except ErroDePublicacao as erro:
            saida.write_text(f"PEDIDO:\n{pedido}\n\nERRO: {erro}\n", encoding="utf-8")
            raise
        relato = [
            f"PEDIDO:\n{pedido}\n",
            f"FERRAMENTAS: {conversa.ferramentas}",
            "RESULTADOS DE FERRAMENTA:",
            *conversa.resultados_de_ferramenta,
            f"TEXTO FINAL: {conversa.texto_final()}",
            f"CUSTO: {conversa.medida.custo_usd} USD em {conversa.medida.segundos} s",
        ]
        saida.write_text("\n".join(relato), encoding="utf-8")
        print("\n".join(relato))


def escrever(versao: str) -> tuple[Path, tuple[str, ...]]:
    slides = V1 if versao == "v1" else V2
    raiz = AQUI / f"sonda-deck-{versao}"
    for id_, html in slides.items():
        destino = raiz / "project" / "slides" / f"{id_}.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8", newline="\n")
    (raiz / "project" / "deck.json").write_text(indice(list(slides)), encoding="utf-8", newline="\n")
    return raiz, ("project/deck.json", *(f"project/slides/{i}.html" for i in slides))


if __name__ == "__main__":
    sonda = Sonda()
    if sys.argv[1] == "criar":
        sonda.rodar("criar", pedido_de_criacao(), AQUI)
    else:
        url, versao = sys.argv[2], sys.argv[3]
        raiz, arquivos = escrever(versao)
        sonda.rodar(f"preencher-{versao}", pedido_de_preenchimento(raiz, arquivos, url), raiz)
