r"""A vigia de freelas (`whis vigia-freelas`, tarefa `Whis-Vigia-Freelas`): o projeto novo do nicho vira toast.

A caçada roda uma vez por semana e chega quando o projeto já tem 80 propostas;
freela pequeno quem ganha é quem propõe nas primeiras horas. A vigia lê a
listagem da 99Freelas e a API pública do Freelancer.com com a busca do nicho,
filtra em Python (sem Claude e sem o Chrome da caçada) e avisa só o que ainda
não viu. Ele escreve a proposta à mão na hora.

No nicho Shopify ela lê também o Job Listings do fórum da Shopify (Shopify
Community), onde lojistas postam vagas da loja desde jul/2026. Lá o Whis só
avisa: as regras do fórum proíbem oferecer serviço e mandar contato ou DM
que o post não pediu, e ele responde à mão pelo caminho que o post dá.

O que já foi visto fica em `%LOCALAPPDATA%\whis\cacada\vigia-de-freelas.json`.
Sem esse arquivo, a rodada só guarda o que já está lá: avisar tudo de uma vez
seriam dezenas de toasts.

Não é o vigia (`Whis-Vigia`, `vigia.ps1`), que confere se as tarefas do Whis subiram.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import avisos
from .criterios_da_cacada import FonteDaCacada
from .freelas_rapidos import do_nicho
from .oportunidades import FREELA, Oportunidade, link_canonico

_log = logging.getLogger("whis.vigia_de_freelas")

NOME_DO_ESTADO = "vigia-de-freelas.json"
NOME_DA_ULTIMA_RODADA = "vigia-de-freelas-rodada.json"
#: Parada mais que isto (a noite, ou o PC desligado), a rodada lê mais páginas da 99Freelas: duas
#: páginas cobriram umas 50 h de projetos num domingo (18/10), menos num dia útil movimentado.
PARADA_HA = timedelta(hours=6)
PAGINAS_NA_VOLTA = 6
RECENTE = timedelta(hours=24)
TOASTS_POR_RODADA = 3
GUARDA_POR = timedelta(days=30)
#: Acima disto o projeto do Freelancer.com não vira aviso: lá um projeto de Shopify passa de 50 propostas em uma hora.
MAX_PROPOSTAS_DO_FREELANCER = 30
JOB_LISTINGS = "job-listings/334"
FREELANCER = "Freelancer.com"
FORUM = "Shopify Community"
REGRAS_DO_FORUM = (
    "Candidate-se pelo caminho que o post pede. No fórum, sem oferecer serviço, sem contato e sem DM que o post "
    "não pediu (regras da Shopify Community)."
)

Avisar = Callable[..., bool]
Ler = Callable[[str], Sequence[Oportunidade]]


@dataclass(frozen=True)
class Rodada:
    """O que esta rodada avisou e, na primeira, quantos guardou sem avisar."""

    avisados: tuple[Oportunidade, ...] = ()
    guardados: int = 0


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


def caminho_da_ultima_rodada() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DA_ULTIMA_RODADA


def voltou_de_parada(arquivo: Path, agora: datetime) -> bool:
    """A rodada anterior foi há mais de `PARADA_HA`: a da manhã, ou a primeira depois de o PC ligar."""
    try:
        anterior = datetime.fromisoformat(json.loads(arquivo.read_text(encoding="utf-8"))["rodada"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return agora - anterior.astimezone() > PARADA_HA


def marcar_rodada(arquivo: Path, agora: datetime) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    temporario.write_text(json.dumps({"rodada": agora.isoformat(timespec="minutes")}), encoding="utf-8")
    os.replace(temporario, arquivo)


def ler_do_nicho(
    nicho: str, *, rede=None, agora: datetime | None = None, paginas_da_99freelas: int | None = None
) -> tuple[Oportunidade, ...]:
    """A listagem da 99Freelas (web, mobile e software), a busca do nicho na API do Freelancer.com e, no
    nicho Shopify, o Job Listings do fórum da Shopify."""
    from . import fontes_da_cacada

    fontes = (
        FonteDaCacada("99Freelas", "99freelas", "web-mobile-e-software"),
        FonteDaCacada(FREELANCER, "freelancer", nicho),
    )
    if nicho.strip().casefold() == "shopify":
        fontes += (FonteDaCacada(FORUM, "shopify_community", JOB_LISTINGS),)
    paginas = {"paginas_da_99freelas": paginas_da_99freelas} if paginas_da_99freelas else {}
    coleta = fontes_da_cacada.coletar(fontes, agora or datetime.now().astimezone(), rede=rede, **paginas)
    for nome, motivo in coleta.falhas.items():
        _log.warning("Vigia de freelas: %s não respondeu: %s", nome, motivo)
    return coleta.todas()


def vigiar(
    nicho: str,
    *,
    ler: Ler = ler_do_nicho,
    estado: Path | None = None,
    avisar: Avisar | None = None,
    celular: Callable[[str], bool] | None = None,
    agora: datetime | None = None,
    max_propostas_freelancer: int = MAX_PROPOSTAS_DO_FREELANCER,
    sem_lances_no_freelancer: bool = False,
) -> Rodada:
    """Uma rodada: lê, fica com o nicho, avisa o novo e recente, e guarda o que viu.

    O do Freelancer.com vai também para o `celular`, um por mensagem: lá não há
    proposta automática (o User Agreement proíbe), e ele propõe à mão na hora.
    O de lá com `max_propostas_freelancer` propostas ou mais não vira aviso (0 =
    sem limite), e nenhum de lá vira aviso com `sem_lances_no_freelancer`: sem
    lance, ele não tem como propor (pedido dele em 18/10). A vaga do fórum da
    Shopify é do nicho por ser de lá, e vai ao celular com as regras do fórum.
    """
    agora = agora or datetime.now().astimezone()
    estado = estado or caminho_do_estado()
    avisar = avisar or avisos.avisar
    primeira = not estado.is_file()
    vistos = {} if primeira else _ler_estado(estado)
    do_nicho_agora: dict[str, Oportunidade] = {}
    for oportunidade in ler(nicho):
        if _site(oportunidade) == FORUM or do_nicho(oportunidade, nicho):
            do_nicho_agora.setdefault(link_canonico(oportunidade.link), oportunidade)
    novos = [o for link, o in do_nicho_agora.items() if link not in vistos]
    for link in do_nicho_agora:
        vistos.setdefault(link, agora.isoformat(timespec="minutes"))
    _gravar_estado(estado, vistos, agora)
    if primeira:
        _log.info("Vigia de freelas: primeira rodada, %d projeto(s) guardado(s) sem avisar.", len(novos))
        return Rodada(guardados=len(novos))
    recentes = [o for o in novos if _recente(o, agora)]
    lotados = [o for o in recentes if _lotado(o, max_propostas_freelancer)]
    if lotados:
        _log.info(
            "Vigia de freelas: %d projeto(s) do Freelancer.com com %d propostas ou mais ficaram sem aviso.",
            len(lotados),
            max_propostas_freelancer,
        )
    recentes = [o for o in recentes if o not in lotados]
    if sem_lances_no_freelancer:
        sem_lance = [o for o in recentes if _site(o) == FREELANCER]
        if sem_lance:
            _log.info("Vigia de freelas: %d projeto(s) do Freelancer.com sem aviso: não sobra lance lá.", len(sem_lance))
        recentes = [o for o in recentes if o not in sem_lance]
    _avisar(recentes, nicho, avisar)
    if celular is not None:
        for oportunidade in recentes:
            if _site(oportunidade) in (FREELANCER, FORUM):
                celular(_texto_do_celular(oportunidade, nicho))
    _log.info("Vigia de freelas: %d projeto(s) novo(s) de %s avisado(s).", len(recentes), nicho)
    return Rodada(avisados=tuple(recentes))


def projeto_de_teste(agora: datetime | None = None) -> Oportunidade:
    """O projeto falso do `--fakes`: passa pelo filtro do nicho e vira um toast de verdade."""
    agora = agora or datetime.now().astimezone()
    return Oportunidade.nova(
        tipo=FREELA,
        fonte="99Freelas",
        titulo="Ajuste no tema da loja Shopify (teste)",
        link="https://www.99freelas.com.br/projects?categoria=web-mobile-e-software",
        faixa="R$ 300 - 600",
        publicada=agora - timedelta(minutes=20),
        descricao="Projeto falso da vigia de freelas: mudar a seção do carrinho do tema Dawn de uma loja Shopify.",
        detalhes="Propostas: 0",
    )


def _avisar(oportunidades: Sequence[Oportunidade], nicho: str, avisar: Avisar) -> None:
    nome = nicho.strip().title()
    for oportunidade in oportunidades[:TOASTS_POR_RODADA]:
        avisar(
            f"Freela de {nome} novo: {oportunidade.titulo}",
            _texto_do_toast(oportunidade),
            botao=("Abrir o projeto", oportunidade.link),
        )
    resto = oportunidades[TOASTS_POR_RODADA:]
    if resto:
        avisar(
            f"Mais {len(resto)} freelas de {nome} novos",
            "; ".join(o.titulo for o in resto)[:300],
            botao=("Abrir o primeiro", resto[0].link),
        )


def _site(oportunidade: Oportunidade) -> str:
    if "community.shopify.com" in oportunidade.link:
        return FORUM
    return FREELANCER if "freelancer.com" in oportunidade.link else "99Freelas"


def _lotado(oportunidade: Oportunidade, maximo: int) -> bool:
    if not maximo or _site(oportunidade) != FREELANCER:
        return False
    casou = re.search(r"Propostas:\s*(\d+)", oportunidade.detalhes)
    return casou is not None and int(casou.group(1)) >= maximo


def _texto_do_celular(oportunidade: Oportunidade, nicho: str) -> str:
    if _site(oportunidade) == FORUM:
        resumo = " ".join(oportunidade.descricao.split())
        resumo = resumo if len(resumo) <= 280 else resumo[:279].rstrip() + "…"
        partes = (f"Vaga nova no Job Listings da {FORUM}", oportunidade.titulo, resumo, oportunidade.link, REGRAS_DO_FORUM)
        return "\n".join(p for p in partes if p)
    propostas = re.search(r"Propostas:\s*\d+", oportunidade.detalhes)
    media = re.search(r"Média:\s*[\d.]+\s*\w+", oportunidade.detalhes)
    linha = " · ".join(p for p in (oportunidade.faixa, propostas.group(0) if propostas else "", media.group(0) if media else "") if p)
    partes = (f"Freela de {nicho.strip().title()} novo no {_site(oportunidade)}", oportunidade.titulo, linha, oportunidade.link)
    return "\n".join(p for p in partes if p)


def _texto_do_toast(oportunidade: Oportunidade) -> str:
    propostas = re.search(r"Propostas:\s*\d+", oportunidade.detalhes)
    site = _site(oportunidade)
    linha = " · ".join(p for p in (oportunidade.faixa, propostas.group(0) if propostas else "", site) if p)
    exclusivo = re.search(r"abre para quem não assina[^|]*", oportunidade.detalhes)
    return f"{linha}\nExclusivo para assinantes: {exclusivo.group(0).strip()}" if exclusivo else linha


def _recente(oportunidade: Oportunidade, agora: datetime) -> bool:
    try:
        publicada = datetime.fromisoformat(oportunidade.publicada)
    except ValueError:
        return True
    if publicada.tzinfo is None:
        publicada = publicada.astimezone()
    return agora - publicada <= RECENTE


def _ler_estado(arquivo: Path) -> dict[str, str]:
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        _log.warning("Vigia de freelas: o estado %s não abriu (%s); começando sem nada visto.", arquivo, erro)
        return {}
    return {str(link): str(quando) for link, quando in dados.items()} if isinstance(dados, dict) else {}


def _gravar_estado(arquivo: Path, vistos: dict[str, str], agora: datetime) -> None:
    limite = agora - GUARDA_POR

    def fica(quando: str) -> bool:
        try:
            return datetime.fromisoformat(quando) >= limite
        except ValueError:
            return False

    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    temporario.write_text(
        json.dumps({link: quando for link, quando in vistos.items() if fica(quando)}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    os.replace(temporario, arquivo)
