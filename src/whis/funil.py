"""O funil das propostas de freela: a seção *Funil* do relatório da caçada.

As mandadas são as notas de `cacada/*/` com link de plataforma de freela e
`status:` de quem já mandou — os pacotes e as notas de `*-propostas/`, em que a
data vem no texto ("enviada em 2026-10-13 (R$ 50, 7 dias)"). Respondida e
fechada saem do `status:` que ele escreve; a resposta do cliente na conversa não
tem marcador conhecido nas páginas logadas, então não é lida. Das que ainda
esperam, o Chrome da caçada mostra o que o site sabe: a situação do projeto na
99Freelas e a posição da proposta no Freelancer.com.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from . import navegador_logado as _logado
from .criterios_da_cacada import PASTA_CACADA
from .fontes_da_cacada import e_da_99freelas, e_do_freelancer

PLATAFORMAS_DE_FREELA = (
    "99freelas.com.br", "freelancer.com", "freelancer.com.br", "workana.com", "vintepila.com.br",
    "peopleperhour.com", "contra.com", "upwork.com", "guru.com",
)
_MANDADA = ("enviad", "respond", "entrevista", "proposta", "fechad", "recusad", "perdid")
_RESPONDIDA = ("respond", "entrevista", "proposta", "fechad")
_FECHADA = ("fechad",)
SEMANAS_NA_LISTA = 4

_FRONTMATTER = re.compile(r"\A---\r?\n(?P<campos>.*?)\r?\n---", re.S)
_DATA = re.compile(r"(\d{4}-\d{2}-\d{2})")
_ENVIADA_EM = re.compile(r"enviad[ao] em (\d{4}-\d{2}-\d{2})", re.I)
_RANQUEADA = re.compile(r"ranqueada em (\d+) entre (\d+)", re.I)
_STATUS_DO_FREELANCER = re.compile(r'<fl-project-status\b[^>]*data-status="([^"]+)"', re.I)


@dataclass(frozen=True)
class Mandada:
    titulo: str
    link: str
    status: str
    enviada: date
    nota: str

    @property
    def respondida(self) -> bool:
        return self.status.casefold().startswith(_RESPONDIDA)

    @property
    def fechada(self) -> bool:
        return self.status.casefold().startswith(_FECHADA)

    @property
    def esperando(self) -> bool:
        return self.status.casefold().startswith("enviad")


def ler_mandadas(vault: Path) -> list[Mandada]:
    pasta = Path(vault) / PASTA_CACADA
    saida = []
    for arquivo in sorted(pasta.glob("*/*.md")) if pasta.is_dir() else ():
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        casou = _FRONTMATTER.match(texto)
        if casou is None:
            continue
        campos = {}
        for linha in casou["campos"].splitlines():
            chave, _, valor = linha.partition(":")
            campos[chave.strip()] = valor.strip().strip('"')
        link, status = campos.get("link", ""), campos.get("status", "")
        if not _de_freela(link) or not status.casefold().startswith(_MANDADA):
            continue
        saida.append(
            Mandada(
                titulo=campos.get("titulo") or arquivo.stem,
                link=link,
                status=status,
                enviada=_data_do_envio(status, campos.get("enviada", ""), arquivo),
                nota=arquivo.relative_to(vault).as_posix(),
            )
        )
    return saida


def situacao_nos_sites(mandadas: Sequence[Mandada], sessao: _logado.SessaoLogada) -> dict[str, str]:
    """Das que esperam resposta, o que a 99Freelas e o Freelancer.com logados mostram; o resto não abre."""
    saida: dict[str, str] = {}
    for mandada in mandadas:
        if not mandada.esperando:
            continue
        if e_da_99freelas(mandada.link):
            site, url, ler = _logado.NOVENTA_E_NOVE, mandada.link, _na_99freelas
        elif e_do_freelancer(mandada.link):
            site, url, ler = _logado.FREELANCER, f"{mandada.link.rstrip('/')}/proposals", _no_freelancer
        else:
            continue
        nome = _logado.NOMES[site]
        if not sessao.logado(site):
            saida[mandada.link] = f"{nome}: {sessao.motivo or 'deslogado no Chrome da caçada'}"
            continue
        try:
            saida[mandada.link] = f"{nome}: {ler(sessao.html(url))}"
        except _logado.SemNavegador as erro:
            saida[mandada.link] = f"{nome}: a página não abriu ({erro})"
    return saida


def montar_funil(mandadas: Sequence[Mandada], situacoes: Mapping[str, str], *, motivo: str = "") -> list[str]:
    linhas = [
        "## Funil",
        "",
        "Das notas de proposta em `cacada/` com o `status:` que você escreve (respondida, entrevista, proposta, "
        "fechado) e, das que ainda esperam, do que a 99Freelas e o Freelancer.com mostram logados. A resposta do "
        "cliente na conversa o Whis não lê: marque no `status:`.",
        "",
    ]
    if motivo:
        linhas += [f"_Os sites não foram lidos: {motivo}._", ""]
    semanas: dict[date, list[Mandada]] = {}
    for mandada in mandadas:
        semanas.setdefault(mandada.enviada - timedelta(days=mandada.enviada.weekday()), []).append(mandada)
    linhas += ["| Semana | Mandadas | Respondidas | Fechadas |", "|---|---|---|---|"]
    for semana in sorted(semanas, reverse=True):
        da_semana = semanas[semana]
        linhas.append(
            f"| semana de {semana:%d/%m} | {len(da_semana)} | {sum(m.respondida for m in da_semana)} "
            f"| {sum(m.fechada for m in da_semana)} |"
        )
    linhas.append("")
    recentes = sorted(semanas, reverse=True)[:SEMANAS_NA_LISTA]
    for semana in recentes:
        for mandada in sorted(semanas[semana], key=lambda m: m.enviada, reverse=True):
            site = f" · {situacoes[mandada.link]}" if mandada.link in situacoes else ""
            linhas.append(f"- [{mandada.titulo}]({mandada.link}) — {mandada.status}{site}")
    linhas.append("")
    return linhas


def _na_99freelas(pagina: str) -> str:
    lida = _logado.ler_99freelas(pagina)
    propostas = f" ({lida.propostas} propostas)" if lida.propostas is not None else ""
    return {
        _logado.JA_PROPOS: f"aberto, esperando o cliente{propostas}",
        _logado.ABERTO: f"aberto, mas sem a sua proposta (confira se ela saiu){propostas}",
        _logado.EM_ANDAMENTO: "o cliente já escolheu um freelancer (se não foi você, perdida)",
        _logado.CANCELADO: "cancelado pelo cliente",
    }.get(lida.situacao, "fechado")


def _no_freelancer(pagina: str) -> str:
    status = _STATUS_DO_FREELANCER.search(pagina)
    situacao = "aberto" if not status or status.group(1) == "open" else status.group(1)
    posicao = _RANQUEADA.search(_logado.texto_da_pagina(pagina))
    if posicao is None:
        return f"{situacao}, sem a sua proposta na lista"
    return f"{situacao}, sua proposta em {posicao.group(1)}º de {posicao.group(2)}"


def _de_freela(link: str) -> bool:
    return any(re.search(rf"(?<![\w-]){re.escape(dominio)}(?:[/:]|$)", link, re.I) for dominio in PLATAFORMAS_DE_FREELA)


def _data_do_envio(status: str, enviada: str, arquivo: Path) -> date:
    for texto in (_ENVIADA_EM.search(status), _DATA.search(enviada), _DATA.search(arquivo.parent.name)):
        if texto is not None:
            try:
                return date.fromisoformat(texto.group(1))
            except ValueError:
                continue
    return datetime.fromtimestamp(arquivo.stat().st_mtime).date()
