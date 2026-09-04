"""A daily como página: o mesmo conteúdo da nota, feito para ser lido em voz alta.

A nota em `daily/YYYY-MM-DD.md` continua sendo o registro durável — é ela que o
Obsidian indexa e que a recuperação de contexto vai ler. A página ao lado existe
para o outro uso, que é o de todo dia: abrir um minuto antes de falar e ler.

Por isso as duas mostram a mesma coisa com pesos invertidos. Na página o roteiro
ocupa a tela inteira, em corpo grande; as listas cruas ficam recolhidas, porque
ninguém lê 1.400 linhas de Slack em voz alta — elas estão ali para conferir uma
afirmação, não para serem lidas.

A página é **autossuficiente**: todo o CSS vai embutido e nada é buscado na rede.
Ela é aberta como arquivo local, muitas vezes sem internet, e um estilo que não
carregasse deixaria o roteiro ilegível na hora de falar.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from . import vault as _vault
from .fontes import Evento, nome_legivel
from .portas import Daily

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from .coleta import FalhaDeFonte
    from .daily import JanelaDaDaily

#: `[rótulo](url)` no texto que o Claude devolve — o link que o roteiro carrega.
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

#: `` `trecho` `` — hash de commit e identificador vêm assim das listas cruas.
_CODIGO = re.compile(r"`([^`]+)`")

_ESTILO = """\
:root {
  color-scheme: light dark;
  --fundo: #fbfaf8;
  --papel: #ffffff;
  --tinta: #1b1a17;
  --suave: #5f5b54;
  --linha: #e5e1d9;
  --realce: #7c4dff;
  --aviso-fundo: #fff4e5;
  --aviso-tinta: #7a4b00;
  --aviso-linha: #f0c67a;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fundo: #16151a;
    --papel: #1e1d24;
    --tinta: #eceaf3;
    --suave: #a09bab;
    --linha: #322f3b;
    --realce: #b39dff;
    --aviso-fundo: #3a2c12;
    --aviso-tinta: #f5d9a8;
    --aviso-linha: #6b5320;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2.5rem 1.25rem 4rem;
  background: var(--fundo);
  color: var(--tinta);
  font: 16px/1.6 ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 46rem; margin: 0 auto; }
header { margin-bottom: 2rem; }
h1 { font-size: 1.6rem; line-height: 1.25; margin: 0 0 .4rem; letter-spacing: -.01em; }
.cobertura { color: var(--suave); margin: 0; font-size: .95rem; }
.aviso {
  background: var(--aviso-fundo);
  color: var(--aviso-tinta);
  border: 1px solid var(--aviso-linha);
  border-radius: .6rem;
  padding: .75rem 1rem;
  margin: 1.25rem 0;
  font-size: .95rem;
}
.batida {
  background: var(--papel);
  border: 1px solid var(--linha);
  border-radius: .75rem;
  padding: 1.1rem 1.35rem 1.25rem;
  margin-bottom: 1rem;
}
.batida h2 {
  font-size: .8rem;
  text-transform: uppercase;
  letter-spacing: .09em;
  color: var(--suave);
  margin: 0 0 .7rem;
  font-weight: 600;
}
.batida ul { margin: 0; padding-left: 1.15rem; }
.batida li { font-size: 1.12rem; line-height: 1.55; margin-bottom: .55rem; }
.batida li:last-child { margin-bottom: 0; }
.vazio { color: var(--suave); font-style: italic; margin: 0; }
a { color: var(--realce); }
a:hover { text-decoration: none; }
code {
  font: .9em ui-monospace, SFMono-Regular, Consolas, monospace;
  background: color-mix(in srgb, var(--linha) 55%, transparent);
  padding: .1em .35em;
  border-radius: .3rem;
}
.memoria { margin-top: 2.5rem; border-top: 1px solid var(--linha); padding-top: 1.5rem; }
.memoria > p { color: var(--suave); font-size: .9rem; margin: 0 0 1rem; }
details {
  border: 1px solid var(--linha);
  border-radius: .6rem;
  margin-bottom: .6rem;
  background: var(--papel);
}
summary {
  cursor: pointer;
  padding: .7rem 1rem;
  font-weight: 600;
  font-size: .95rem;
}
summary::marker { color: var(--suave); }
.conta { color: var(--suave); font-weight: 400; }
details .corpo { padding: 0 1rem 1rem; font-size: .92rem; }
details h3 {
  font-size: .85rem;
  color: var(--suave);
  margin: 1rem 0 .4rem;
  font-weight: 600;
}
details ul { margin: 0; padding-left: 1.1rem; }
details li { margin-bottom: .3rem; line-height: 1.5; }
.hora { color: var(--suave); font-variant-numeric: tabular-nums; }
blockquote {
  margin: .25rem 0 .5rem;
  padding-left: .7rem;
  border-left: 2px solid var(--linha);
  color: var(--suave);
}
footer { margin-top: 2rem; color: var(--suave); font-size: .85rem; }
@media print {
  body { padding: 0; background: #fff; }
  details[open] .corpo, .memoria { display: none; }
  .batida { border: none; padding: 0 0 .5rem; }
}
"""


def montar_pagina(
    *,
    janela: "JanelaDaDaily",
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
    roteiro: Daily | None,
    pontos: _vault.PontosDaDaily,
    falha_do_roteiro: str | None = None,
    calados: int = 0,
) -> str:
    """A página da daily, autossuficiente, com o roteiro em cima.

    Recebe os mesmos argumentos de `vault.montar_daily` e mais `calados`, que a
    nota não mostra: quantos eventos ficaram fora do roteiro por serem pessoais.
    Na nota isso seria ruído; na página é o que explica por que a fala é mais
    curta que a lista.
    """
    titulo = f"Daily — {_vault._data_por_extenso(janela.data)}"
    partes = [
        "<!doctype html>",
        '<html lang="pt-BR">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(titulo)}</title>",
        f"<style>{_ESTILO}</style>",
        "</head>",
        "<body>",
        "<main>",
        "<header>",
        f"<h1>{html.escape(titulo)}</h1>",
        f'<p class="cobertura">{html.escape(_vault.cobertura_da_janela(janela))}</p>',
        "</header>",
    ]

    for aviso in _vault._avisos_da_daily(fontes_com_falha, roteiro, falha_do_roteiro):
        partes.append(f'<div class="aviso">{_texto_rico(aviso)}</div>')

    for rotulo, itens in _vault.secoes_do_roteiro(roteiro, pontos):
        partes.append('<section class="batida">')
        partes.append(f"<h2>{html.escape(rotulo)}</h2>")
        if itens:
            partes.append("<ul>")
            partes.extend(f"<li>{_texto_rico(item)}</li>" for item in itens)
            partes.append("</ul>")
        else:
            partes.append('<p class="vazio">nada</p>')
        partes.append("</section>")

    partes.extend(_memoria(eventos, reunioes, fontes_lidas, fontes_com_falha))
    partes.append(f"<footer>{_rodape(eventos, fontes_lidas, calados)}</footer>")
    partes.extend(["</main>", "</body>", "</html>"])
    return "\n".join(partes) + "\n"


def _memoria(
    eventos: Sequence[Evento],
    reunioes: Sequence[str],
    fontes_lidas: Sequence[str],
    fontes_com_falha: Sequence["FalhaDeFonte"],
) -> list[str]:
    """As listas cruas, recolhidas: estão aqui para conferir, não para falar."""
    partes = [
        '<div class="memoria">',
        "<p>Abaixo, tudo que a janela trouxe — para conferir de onde veio cada "
        "afirmação. A nota em markdown, ao lado, guarda o mesmo conteúdo.</p>",
    ]

    if reunioes:
        itens = "".join(f"<li>{html.escape(_nome_da_reuniao(r))}</li>" for r in reunioes)
        partes.append(
            "<details><summary>Reuniões "
            f'<span class="conta">{len(reunioes)}</span></summary>'
            f'<div class="corpo"><ul>{itens}</ul></div></details>'
        )

    motivos = {falha.fonte: falha.motivo for falha in fontes_com_falha}
    nomes_com_falha = [falha.fonte for falha in fontes_com_falha]
    for fonte in _vault.fontes_em_ordem(fontes_lidas, nomes_com_falha):
        rotulo = html.escape(nome_legivel(fonte))
        if fonte in motivos:
            partes.append(
                f"<details><summary>{rotulo}</summary>"
                f'<div class="corpo"><p class="vazio">Não foi possível ler esta '
                f"fonte: {html.escape(motivos[fonte])}</p></div></details>"
            )
            continue

        grupos = _vault.agrupar_por_referencia(fonte, eventos)
        quantos = sum(len(do_grupo) for _, do_grupo in grupos)
        corpo: list[str] = []
        for referencia, do_grupo in grupos:
            if referencia is not None:
                corpo.append(f"<h3>{html.escape(referencia)}</h3>")
            corpo.append("<ul>")
            corpo.extend(_item_do_evento(evento) for evento in do_grupo)
            corpo.append("</ul>")
        if not grupos:
            corpo.append('<p class="vazio">nada registrado</p>')
        partes.append(
            f"<details><summary>{rotulo} "
            f'<span class="conta">{quantos}</span></summary>'
            f'<div class="corpo">{"".join(corpo)}</div></details>'
        )

    partes.append("</div>")
    return partes


def _item_do_evento(evento: Evento) -> str:
    titulo = " ".join(evento.titulo.split()) or "(sem título)"
    marcado = _texto_rico(titulo)
    if evento.url:
        marcado = f'<a href="{html.escape(evento.url, quote=True)}" target="_blank" rel="noopener">{marcado}</a>'
    item = f'<li><span class="hora">{evento.momento:%H:%M}</span> {marcado}'
    detalhe = evento.detalhe.strip()
    if detalhe:
        linhas = "<br>".join(_texto_rico(linha) for linha in detalhe.splitlines() if linha.strip())
        item += f"<blockquote>{linhas}</blockquote>"
    return item + "</li>"


def _rodape(eventos: Sequence[Evento], fontes_lidas: Sequence[str], calados: int) -> str:
    fontes = ", ".join(nome_legivel(fonte) for fonte in fontes_lidas) or "nenhuma fonte"
    texto = f"{len(eventos)} evento(s) de {fontes}."
    if calados:
        texto += (
            f" Outros {calados} ficaram só na nota, fora do roteiro, por serem "
            f"de projeto pessoal."
        )
    return html.escape(texto)


def _nome_da_reuniao(caminho: str) -> str:
    return caminho.rsplit("/", 1)[-1].removesuffix(".md")


def _texto_rico(bruto: str) -> str:
    """Escapa o texto e devolve só as duas marcações que o conteúdo usa.

    Escapar **antes** de marcar é o que impede uma mensagem do Slack de injetar
    HTML na página: nada do que veio de fora vira tag, e só o que este módulo
    escreve depois é markup.
    """
    seguro = html.escape(bruto)
    seguro = _LINK.sub(
        lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        seguro,
    )
    return _CODIGO.sub(lambda m: f"<code>{m.group(1)}</code>", seguro)
