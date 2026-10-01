"""A página do jornal: o HTML que vira o artifact, gerado da mesma `Edicao` que gera a nota.

O visual é o da segunda edição do protótipo, aprovado por ele no celular
depois de reprovar o primeiro: sempre claro, papel creme, manchetes em serifa,
cabeçalho de jornal com fio duplo e seções numeradas com uma faixa na cor de
cada uma. Uma coluna, sem script, sem CDN, sem fonte externa — as capas são
arquivos de apoio do próprio artifact (`img/N.jpg`), porque hotlink morre na CSP.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from datetime import timedelta, timezone
from typing import TYPE_CHECKING

from .fonte_x import e_do_x
from .portas import Aula, Janelas

if TYPE_CHECKING:
    from .jornal import DicaDoJornal, Edicao, ItemDoJornal

_BRT = timezone(timedelta(hours=-3))

DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

CORES = {
    "aprender": "#5b3fb5",
    "ia": "#0e7c86",
    "tecnologia": "#1d5fb8",
    "mundo": "#21705a",
    "brasil": "#2f7d3a",
    "musica": "#a8382f",
    "futebol": "#0f0f0f",
    "carros": "#8a5a2b",
}
COR_PADRAO = "#333333"

NADA_RELEVANTE = "Nada relevante nas últimas 24 h."

CSS = """
:root{--papel:#f7f4ee;--tinta:#17171a;--cinza:#6e6a63;--fio:#d3ccbc;--creme:#efe9dc;--serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;--sans:-apple-system,system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}html{background:var(--papel)}body{margin:0;background:var(--papel);color:var(--tinta);font:16px/1.55 var(--sans)}
main{max-width:700px;margin:0 auto;padding:12px 16px 40px}a{color:inherit;text-decoration:none}
.cabeca{text-align:center;padding:14px 0 12px;border-top:1px solid var(--tinta);border-bottom:3px double var(--tinta);margin-bottom:6px}
.cabeca h1{font:700 40px/1 var(--serif);letter-spacing:.02em;margin:6px 0 8px}
.cabeca .linha{font:12px/1.4 var(--sans);text-transform:uppercase;letter-spacing:.14em;color:var(--cinza)}
.cabeca .medida{font:12px/1.4 var(--sans);color:var(--cinza);margin-top:6px}
.avisos{font:13px/1.4 var(--sans);color:#8a2f1d;margin:10px 0 0;text-align:center}
section{margin-top:30px}
.kicker{display:flex;align-items:center;gap:10px;border-top:4px solid var(--c);padding-top:8px;margin-bottom:12px}
.kicker .n{font:700 12px/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--c)}
.kicker .t{font:700 22px/1.1 var(--serif);margin:0}
.kicker .fio{flex:1;border-top:1px solid var(--fio)}
h3.sub{font:700 12px/1.2 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--cinza);margin:18px 0 8px;padding-bottom:4px;border-bottom:1px solid var(--fio)}
.lead{margin:0 0 14px}.lead img{width:100%;height:auto;display:block;max-height:300px;object-fit:cover;border:1px solid var(--fio)}
.lead h2{font:700 24px/1.2 var(--serif);margin:10px 0 6px}.lead p{margin:0;font-size:16px}
.item{display:grid;grid-template-columns:1fr 92px;gap:12px;padding:12px 0;border-top:1px solid var(--fio)}
.item.sem{grid-template-columns:1fr}.item img{width:92px;height:72px;object-fit:cover;border:1px solid var(--fio)}
.item h2{font:700 18px/1.25 var(--serif);margin:0 0 4px}.item p{margin:0;font-size:14.5px;color:#2b2b2e}
.by{font:11px/1.3 var(--sans);text-transform:uppercase;letter-spacing:.1em;color:var(--cinza);margin-top:6px}
.by.x{text-transform:none;letter-spacing:.02em}
.vazio{color:var(--cinza);font-style:italic;font-family:var(--serif)}
.aula{background:var(--creme);border-left:4px solid var(--c);padding:14px 16px;margin:0 0 12px}
.aula h4{font:700 19px/1.2 var(--serif);margin:0 0 8px}.aula p{margin:0 0 10px;white-space:pre-line;font-size:15px}
.aula .f{font-size:12px;color:var(--cinza)}.aula .f a{text-decoration:underline;word-break:break-all}
.aula .ver{font-size:13px;color:var(--cinza)}.aula .ver a{text-decoration:underline;color:var(--tinta)}
table{width:100%;border-collapse:collapse;font-size:14px;margin:0 0 10px}td{padding:6px 4px;border-bottom:1px solid var(--fio);vertical-align:top}
td.p{white-space:nowrap;font:700 16px/1 var(--serif);text-align:center;width:64px}td.g{color:var(--cinza);font-size:12px;border-bottom:1px solid var(--fio)}
.liga{font:700 12px/1.2 var(--sans);letter-spacing:.12em;text-transform:uppercase;margin:10px 0 4px}
footer{color:var(--cinza);font-size:12px;margin-top:36px;border-top:3px double var(--tinta);padding-top:10px;text-align:center}
"""


def _e(texto: object) -> str:
    return html.escape(str(texto or ""))


def data_por_extenso(dia) -> str:
    return f"{DIAS[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def hora(momento) -> str:
    return momento.astimezone(_BRT).strftime("%H:%M") if momento else ""


def texto_do_plano(antes: Janelas | None, depois: Janelas | None) -> str:
    """`Plano: 5 h 30% → 31% · semana 61% → 61%`, ou "sem leitura do plano"."""
    if not antes or not depois:
        return "sem leitura do plano"

    def janela(rotulo: str, a: int | None, d: int | None) -> str | None:
        if a is None or d is None:
            return None
        return f"{rotulo} {a}% → {d}%"

    partes = [
        parte
        for parte in (
            janela("5 h", antes.cinco_horas, depois.cinco_horas),
            janela("semana", antes.sete_dias, depois.sete_dias),
        )
        if parte
    ]
    return "Plano: " + " · ".join(partes) if partes else "sem leitura do plano"


def texto_do_custo(custo_usd: float | None) -> str:
    return f"≈ US$ {custo_usd:.2f} equivalentes" if custo_usd is not None else ""


def dominio(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url)[:44]


def _item(item: ItemDoJornal, *, lead: bool = False) -> str:
    classe = "by x" if e_do_x(item.link) else "by"
    rodape = f'<div class="{classe}">{_e(item.fonte)}{" · " + hora(item.data) if item.data else ""}</div>'
    resumo = f"<p>{_e(item.resumo)}</p>" if item.resumo else ""
    if lead:
        capa = f'<img src="{_e(item.capa)}" alt="">' if item.capa else ""
        return (
            f'<article class="lead"><a href="{_e(item.link)}">{capa}<h2>{_e(item.titulo)}</h2></a>'
            f"{resumo}{rodape}</article>"
        )
    capa = f'<a href="{_e(item.link)}"><img src="{_e(item.capa)}" alt=""></a>' if item.capa else ""
    return (
        f'<article class="item{"" if capa else " sem"}"><div><a href="{_e(item.link)}">'
        f"<h2>{_e(item.titulo)}</h2></a>{resumo}{rodape}</div>{capa}</article>"
    )


def _lista(itens: Sequence[ItemDoJornal]) -> str:
    if not itens:
        return f'<p class="vazio">{NADA_RELEVANTE}</p>'
    podem_abrir = [item for item in itens if not e_do_x(item.link)]
    if not podem_abrir:
        return "".join(_item(item) for item in itens)
    primeiro = next((item for item in podem_abrir if item.capa), podem_abrir[0])
    return _item(primeiro, lead=True) + "".join(_item(item) for item in itens if item is not primeiro)


def _dica(dica: DicaDoJornal) -> str:
    item = dica.item
    quando = f" · {hora(item.data)}" if item.data else ""
    return (
        f'<div class="aula"><h4>Dica do dia · {_e(dica.titulo)}</h4><p>{_e(dica.como_aplicar)}</p>'
        f'<div class="ver">{_e(item.fonte)}{quando} · <a href="{_e(item.link)}">Ver no X</a></div></div>'
    )


def frase(aviso: str) -> str:
    return f"{aviso[:1].upper()}{aviso[1:]}."


def _aula(aula: Aula) -> str:
    fontes = " · ".join(f'<a href="{_e(url)}">{_e(dominio(url))}</a>' for url in aula.fontes)
    return (
        f'<div class="aula"><h4>{_e(aula.titulo)}</h4><p>{_e(aula.texto)}</p>'
        f'<div class="f">Fontes: {fontes}</div></div>'
    )


def _abre_secao(numero: int, titulo: str, cor: str) -> str:
    return (
        f'<section style="--c:{cor}"><div class="kicker"><span class="n">{numero:02d}</span>'
        f'<h2 class="t">{_e(titulo)}</h2><span class="fio"></span></div>'
    )


def _futebol(edicao: Edicao) -> list[str]:
    partes: list[str] = []
    if edicao.time:
        partes.append(f'<h3 class="sub">{_e(edicao.time_nome or "Time")}</h3>')
        partes += [_item(item) for item in edicao.time]
    if edicao.placar is not None:
        partes.append('<h3 class="sub">Placares</h3>')
        if edicao.placar.jogos:
            por_liga: dict[str, list] = {}
            for jogo in edicao.placar.jogos:
                por_liga.setdefault(jogo.liga, []).append(jogo)
            for liga, jogos in por_liga.items():
                linhas = []
                for jogo in jogos:
                    gols = "; ".join(f"{gol.minuto} {gol.autor}" for gol in jogo.gols) or "sem gols"
                    linhas.append(
                        f'<tr><td>{_e(jogo.mandante)}</td>'
                        f'<td class="p">{jogo.placar_mandante} x {jogo.placar_visitante}</td>'
                        f'<td>{_e(jogo.visitante)}</td></tr>'
                        f'<tr><td class="g" colspan="3">{_e(jogo.hora_brt)} · {_e(gols)}</td></tr>'
                    )
                partes.append(f'<div class="liga">{_e(liga)}</div><table>{"".join(linhas)}</table>')
        else:
            partes.append(f'<p class="vazio">{_e(edicao.placar.texto)}</p>')
    if edicao.efemeride is not None:
        efemeride = edicao.efemeride
        titulo = f"Em {efemeride.ano}" if efemeride.ano else "Neste dia"
        capa = f'<img src="{_e(edicao.capa_da_efemeride)}" alt="">' if edicao.capa_da_efemeride else ""
        cabeca = f'<a href="{_e(efemeride.link)}"><h2>{_e(titulo)}</h2></a>' if efemeride.link else f"<h2>{_e(titulo)}</h2>"
        partes.append(
            f'<h3 class="sub">Neste dia</h3><article class="item{"" if capa else " sem"}"><div>{cabeca}'
            f'<p>{_e(efemeride.texto)}</p><div class="by">Wikipédia · '
            f"efemérides de {edicao.data.day} de {MESES[edicao.data.month - 1]}</div></div>{capa}</article>"
        )
    partes.append('<h3 class="sub">Notícias</h3>')
    return partes


def pagina_html(edicao: Edicao) -> str:
    """A edição inteira como uma página HTML autossuficiente."""
    linha_da_data = f"{data_por_extenso(edicao.data)} · edição das {edicao.gerado_em.strftime('%H:%M')}"
    medida = " · ".join(
        parte for parte in (texto_do_plano(edicao.plano_antes, edicao.plano_depois), texto_do_custo(edicao.custo_usd)) if parte
    )
    assuntos = " · ".join(secao.titulo for secao in edicao.secoes)
    avisos = f'<p class="avisos">{_e("; ".join(edicao.avisos).capitalize())}.</p>' if edicao.avisos else ""

    partes = [
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="color-scheme" content="light"><title>Jornal do Whis</title><style>{CSS}</style></head>',
        "<body><main>",
        f'<header class="cabeca"><div class="linha">{_e(linha_da_data)}</div><h1>Jornal do Whis</h1>'
        f'<div class="linha">{_e(assuntos)}</div><div class="medida">{_e(medida)}</div>{avisos}</header>',
    ]

    numero = 0
    if edicao.aprender:
        numero += 1
        partes += [_abre_secao(numero, "Aprender hoje", CORES["aprender"]), _aula(edicao.aprender), "</section>"]
    for secao in edicao.secoes:
        numero += 1
        partes.append(_abre_secao(numero, secao.titulo, CORES.get(secao.id, COR_PADRAO)))
        if secao.id == "futebol":
            partes += _futebol(edicao)
        if secao.dica:
            partes.append(_dica(secao.dica))
        if secao.itens or not (secao.dica or secao.aviso):
            partes.append(_lista(secao.itens))
        if secao.aviso:
            partes.append(f'<p class="vazio">{_e(frase(secao.aviso))}</p>')
        if secao.id == "carros" and edicao.para_aprender:
            partes.append('<h3 class="sub">Para aprender</h3>')
            partes += [_aula(aula) for aula in edicao.para_aprender]
        partes.append("</section>")

    falhas = (
        f"Fontes que não responderam hoje: {_e(', '.join(edicao.fontes_com_falha))}<br>"
        if edicao.fontes_com_falha
        else ""
    )
    partes.append(
        f"<footer>{falhas}Gerado pelo Whis a partir de feeds públicos. "
        "Cada item leva à fonte original.</footer></main></body></html>"
    )
    return "".join(partes)
