"""A coleta da caçada: cada linha de *Fontes* vira oportunidades, em Python puro.

Nenhuma fonte aqui precisa de conta nem de navegador (research 02a, 02b e 08):
as APIs públicas de vaga remota (Himalayas, Remotive, RemoteOK, Jobicy, HN pela
Algolia, issues do GitHub), o JSON do portal da Gupy, o RSS do We Work
Remotely, as listagens públicas da Workana e da 99Freelas, e a busca *guest*
do LinkedIn — a mesma que a página pública usa, nunca a conta dele.

Uma fonte que falha não derruba as outras: vai para `falhas` com o motivo, e o
relatório diz qual não respondeu. Os leitores do HTML são tolerantes de
propósito: página que mudou devolve zero itens e um motivo, nunca exceção.
O tipo `web` não mora aqui — é o explorador, que é o Claude.

A exceção é o que só se vê logado: com uma sessão do Chrome da caçada
(`navegador_logado`), a VintePila é lida pela listagem logada e a conferência
do Freelancer.com e da 99Freelas passa pela página logada.
"""

from __future__ import annotations

import html as _html
import json
import logging
import random
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlencode, urlsplit

import httpx

from . import navegador_logado
from .criterios_da_cacada import FonteDaCacada
from .navegador_logado import SessaoLogada
from .feeds import interpretar_feed
from .oportunidades import FREELA, VAGA, Oportunidade, texto_limpo

_log = logging.getLogger("whis.fontes_da_cacada")

UA_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
CABECALHOS = {"User-Agent": UA_NAVEGADOR, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
TEMPO_LIMITE_S = 25.0

#: Oportunidade mais velha que isto não entra: a vaga de dois meses já foi preenchida.
IDADE_MAXIMA = timedelta(days=21)

PAGINAS_DA_WORKANA = 3
PAGINAS_DA_99FREELAS = 2
PAGINAS_DO_LINKEDIN = 2
PAUSA_ENTRE_PAGINAS_S = (2.0, 5.0)
TETO_DO_HN = 120

#: Os tipos que esta coleta lê; `web` é do explorador.
TIPOS_LIDOS_AQUI = frozenset(
    {
        "himalayas", "remotive", "remoteok", "jobicy", "rss", "github", "hn", "gupy", "workana", "99freelas", "linkedin",
        "getonbrd", "freelancer", "shopify_community",
    }
)


class FonteSemResposta(RuntimeError):
    """A fonte respondeu erro, nada, ou algo que não se lê."""


@dataclass
class ColetaDaCacada:
    """As oportunidades de cada fonte, pelo nome, e as que falharam com o motivo."""

    por_fonte: dict[str, tuple[Oportunidade, ...]] = field(default_factory=dict)
    falhas: dict[str, str] = field(default_factory=dict)

    def todas(self) -> tuple[Oportunidade, ...]:
        vistas: dict[str, Oportunidade] = {}
        for lista in self.por_fonte.values():
            for oportunidade in lista:
                vistas.setdefault(oportunidade.id, oportunidade)
        return tuple(vistas.values())


Leitor = Callable[[httpx.Client, FonteDaCacada], tuple[Oportunidade, ...]]


def coletar(
    fontes: Sequence[FonteDaCacada],
    agora: datetime,
    *,
    rede: httpx.BaseTransport | None = None,
    dormir: Callable[[float], None] = time.sleep,
    ao_ler: Callable[[str], None] | None = None,
    paginas_da_99freelas: int = PAGINAS_DA_99FREELAS,
    ate_idade_da_99freelas: timedelta | None = None,
) -> ColetaDaCacada:
    """Lê cada fonte que é desta coleta, uma de cada vez, e corta o que é velho demais."""
    coleta = ColetaDaCacada()
    limite = agora - IDADE_MAXIMA
    with httpx.Client(
        transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS
    ) as cliente:
        for fonte in fontes:
            if fonte.tipo not in TIPOS_LIDOS_AQUI:
                continue
            if ao_ler is not None:
                ao_ler(fonte.nome)
            leitor = _LEITORES[fonte.tipo]
            try:
                if fonte.tipo == "99freelas" and (paginas_da_99freelas != PAGINAS_DA_99FREELAS or ate_idade_da_99freelas):
                    lidas = leitor(cliente, fonte, dormir, paginas=paginas_da_99freelas, ate_idade=ate_idade_da_99freelas)
                elif fonte.tipo in _PAGINADOS:
                    lidas = leitor(cliente, fonte, dormir)
                else:
                    lidas = leitor(cliente, fonte)
            except Exception as erro:  # noqa: BLE001 — uma fonte não derruba as outras
                coleta.falhas[fonte.nome] = _motivo(erro)
                _log.warning("Caçada: %s não respondeu: %s", fonte.nome, coleta.falhas[fonte.nome])
                continue
            recentes = tuple(o for o in lidas if not _velha(o, limite))
            coleta.por_fonte[fonte.nome] = recentes
            _log.info(
                "Caçada: %s — %d oportunidade(s)%s.",
                fonte.nome,
                len(recentes),
                f", {len(lidas) - len(recentes)} velha(s) demais" if len(lidas) != len(recentes) else "",
            )
    return coleta


# -- APIs de vaga remota ------------------------------------------------------------


def ler_himalayas(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    url = "https://himalayas.app/jobs/api/search?" + urlencode({"q": fonte.argumento or "developer", "sort": "recent"})
    dados = _json(cliente, url)
    vagas = _lista(dados, "jobs", "data", "results")
    return tuple(o for o in (_vaga_do_himalayas(fonte, item) for item in vagas) if o is not None)


def _vaga_do_himalayas(fonte: FonteDaCacada, item: dict) -> Oportunidade | None:
    link = _primeiro(item, "applicationLink", "guid", "url", "link")
    titulo = _primeiro(item, "title")
    if not link or not titulo:
        return None
    paises = item.get("locationRestrictions") or []
    local = "Remoto" + (f" ({', '.join(map(str, paises))})" if paises else " (qualquer país)")
    return Oportunidade.nova(
        tipo=VAGA,
        fonte=fonte.nome,
        titulo=titulo,
        link=link,
        empresa=_primeiro(item, "companyName", "company"),
        local=local,
        regime=_primeiro(item, "employmentType"),
        faixa=_faixa(item.get("minSalary"), item.get("maxSalary"), _primeiro(item, "currency", "salaryCurrency") or "USD", "ano"),
        publicada=_data(item.get("pubDate") or item.get("publishedDate")),
        descricao=_primeiro(item, "description", "excerpt"),
        detalhes=_primeiro(item, "seniority") if isinstance(item.get("seniority"), str) else ", ".join(map(str, item.get("seniority") or [])),
    )


def ler_remotive(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    url = "https://remotive.com/api/remote-jobs?" + urlencode(
        {"category": "software-dev", "search": fonte.argumento or "developer", "limit": 100}
    )
    vagas = _lista(_json(cliente, url), "jobs")
    saida = []
    for item in vagas:
        link, titulo = _primeiro(item, "url"), _primeiro(item, "title")
        if not link or not titulo:
            continue
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                empresa=_primeiro(item, "company_name"),
                local="Remoto (" + (_primeiro(item, "candidate_required_location") or "?") + ")",
                regime=_primeiro(item, "job_type"),
                faixa=_primeiro(item, "salary"),
                publicada=_data(item.get("publication_date")),
                descricao=_primeiro(item, "description"),
            )
        )
    return tuple(saida)


def ler_remoteok(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    url = "https://remoteok.com/api" + (f"?tag={quote_plus(fonte.argumento)}" if fonte.argumento else "")
    dados = _json(cliente, url)
    saida = []
    for item in dados if isinstance(dados, list) else ():
        if not isinstance(item, dict) or "legal" in item:
            continue
        link = _primeiro(item, "url", "apply_url")
        titulo = _primeiro(item, "position", "title")
        if not link or not titulo:
            continue
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                empresa=_primeiro(item, "company"),
                local="Remoto (" + (_primeiro(item, "location") or "qualquer país") + ")",
                faixa=_faixa(item.get("salary_min"), item.get("salary_max"), "USD", "ano"),
                publicada=_data(item.get("epoch") or item.get("date")),
                descricao=_primeiro(item, "description"),
                detalhes="tags: " + ", ".join(map(str, item.get("tags") or [])),
            )
        )
    return tuple(saida)


def ler_jobicy(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    parametros = {"count": 50, "tag": "developer"}
    if fonte.argumento:
        parametros["geo"] = fonte.argumento
    vagas = _lista(_json(cliente, "https://jobicy.com/api/v2/remote-jobs?" + urlencode(parametros)), "jobs")
    saida = []
    for item in vagas:
        link, titulo = _primeiro(item, "url"), _primeiro(item, "jobTitle", "title")
        if not link or not titulo:
            continue
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                empresa=_primeiro(item, "companyName"),
                local="Remoto (" + (_primeiro(item, "jobGeo") or "?") + ")",
                regime=", ".join(map(str, item.get("jobType") or [])) if isinstance(item.get("jobType"), list) else _primeiro(item, "jobType"),
                faixa=_faixa(item.get("annualSalaryMin"), item.get("annualSalaryMax"), _primeiro(item, "salaryCurrency") or "USD", "ano"),
                publicada=_data(item.get("pubDate")),
                descricao=_primeiro(item, "jobDescription", "jobExcerpt"),
                detalhes=_primeiro(item, "jobLevel"),
            )
        )
    return tuple(saida)


def ler_rss(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    resposta = cliente.get(fonte.argumento)
    _conferir(resposta)
    saida = []
    for item in interpretar_feed(resposta.content):
        empresa, _, titulo = item.titulo.partition(": ")
        if not titulo:
            empresa, titulo = "", item.titulo
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=item.link,
                empresa=empresa,
                local="Remoto",
                publicada=item.data,
                descricao=item.resumo,
            )
        )
    return tuple(saida)


def ler_github(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    repositorio = fonte.argumento.strip().strip("/")
    if repositorio.count("/") != 1:
        raise FonteSemResposta(f"'{fonte.argumento}' não é dono/repositório")
    url = f"https://api.github.com/repos/{repositorio}/issues?" + urlencode(
        {"state": "open", "sort": "created", "direction": "desc", "per_page": 40}
    )
    issues = _json(cliente, url, cabecalhos={"Accept": "application/vnd.github+json"})
    saida = []
    for item in issues if isinstance(issues, list) else ():
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        link, titulo = _primeiro(item, "html_url"), _primeiro(item, "title")
        if not link or not titulo:
            continue
        etiquetas = ", ".join(str(e.get("name", "")) for e in item.get("labels") or [] if isinstance(e, dict))
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                local=etiquetas,
                publicada=_data(item.get("created_at")),
                descricao=_primeiro(item, "body"),
                detalhes=f"etiquetas: {etiquetas}" if etiquetas else "",
            )
        )
    return tuple(saida)


def ler_hn(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    """Os comentários de topo do *Who is hiring?* mais recente que citam os termos.

    O primeiro termo é obrigatório (por padrão `remote`); dos outros, basta um.
    """
    historias = _lista(
        _json(cliente, "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10"),
        "hits",
    )
    alvo = next((h for h in historias if "who is hiring" in str(h.get("title", "")).lower()), None)
    if alvo is None:
        raise FonteSemResposta("nenhum 'Who is hiring?' recente")
    historia = str(alvo.get("objectID") or alvo.get("story_id") or "")
    comentarios = _lista(
        _json(cliente, f"https://hn.algolia.com/api/v1/search?tags=comment,story_{historia}&hitsPerPage=1000"),
        "hits",
    )
    termos = [termo.strip().lower() for termo in (fonte.argumento or "remote").split(",") if termo.strip()]
    obrigatorio, opcionais = termos[0], termos[1:]
    saida = []
    for item in comentarios:
        if str(item.get("parent_id", historia)) != historia:
            continue
        texto = texto_limpo(_primeiro(item, "comment_text"))
        minusculo = texto.lower()
        if obrigatorio not in minusculo or (opcionais and not any(t in minusculo for t in opcionais)):
            continue
        primeira = texto.splitlines()[0] if texto else ""
        empresa = primeira.split("|")[0].strip()
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=primeira[:160] or "Vaga no Who is hiring",
                link=f"https://news.ycombinator.com/item?id={item.get('objectID')}",
                empresa=empresa[:80],
                local="ver texto",
                publicada=_data(item.get("created_at")),
                descricao=texto,
            )
        )
        if len(saida) >= TETO_DO_HN:
            break
    return tuple(saida)


def ler_gupy(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    url = "https://portal.api.gupy.io/api/v1/jobs?" + urlencode(
        {"jobName": fonte.argumento or "desenvolvedor", "limit": 100, "offset": 0}
    )
    vagas = _lista(_json(cliente, url), "data", "jobs", "results")
    saida = []
    for item in vagas:
        link, titulo = _primeiro(item, "jobUrl", "url"), _primeiro(item, "name", "title")
        if not link or not titulo:
            continue
        modelo = _primeiro(item, "workplaceType") or ("remote" if item.get("isRemoteWork") else "")
        cidade = ", ".join(p for p in (_primeiro(item, "city"), _primeiro(item, "state")) if p)
        local = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}.get(modelo, modelo or "?")
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                empresa=_primeiro(item, "careerPageName", "companyName"),
                local=f"{local}{f' — {cidade}' if cidade else ''}",
                regime=_primeiro(item, "type"),
                publicada=_data(item.get("publishedDate")),
                descricao=_primeiro(item, "description"),
            )
        )
    return tuple(saida)


def ler_getonbrd(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    """A API pública do Get on Board (vagas tech na América Latina, faixa em USD quase sempre)."""
    url = "https://www.getonbrd.com/api/v0/search/jobs?" + urlencode(
        {"query": fonte.argumento or "developer", "per_page": 50, "expand": '["company"]'}
    )
    saida = []
    for item in _lista(_json(cliente, url), "data"):
        atributos = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        titulo = _primeiro(atributos, "title")
        link = _primeiro(item.get("links") or {}, "public_url") or (
            f"https://www.getonbrd.com/jobs/{item.get('id')}" if item.get("id") else ""
        )
        if not titulo or not link:
            continue
        empresa = ((atributos.get("company") or {}).get("data") or {}).get("attributes") or {}
        paises = ", ".join(map(str, atributos.get("countries") or []))
        remoto = atributos.get("remote") or atributos.get("remote_modality") in ("fully_remote", "remote_local")
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=fonte.nome,
                titulo=titulo,
                link=link,
                empresa=_primeiro(empresa, "name") if isinstance(empresa, dict) else "",
                local=("Remoto" if remoto else "Presencial") + (f" ({paises})" if paises else ""),
                regime=_primeiro(atributos, "modality") if isinstance(atributos.get("modality"), str) else "",
                faixa=_faixa(atributos.get("min_salary") or atributos.get("salary_min"), atributos.get("max_salary") or atributos.get("salary_max"), "USD", "mês"),
                publicada=_data(atributos.get("published_at")),
                descricao=_primeiro(atributos, "description", "projects", "functions"),
                detalhes=_primeiro(atributos, "seniority") if isinstance(atributos.get("seniority"), str) else "",
            )
        )
    return tuple(saida)


def ler_freelancer(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    """A API pública de projetos ativos do Freelancer.com; projeto por hora fica de fora (regra dele)."""
    url = "https://www.freelancer.com/api/projects/0.1/projects/active/?" + urlencode(
        {"query": fonte.argumento or "website", "limit": 50, "full_description": "true", "sort_field": "time_updated"}
    )
    dados = _json(cliente, url)
    projetos = _lista((dados.get("result") or {}) if isinstance(dados, dict) else {}, "projects")
    saida = []
    for item in projetos:
        if str(item.get("type", "")).lower() == "hourly":
            continue
        titulo, slug = _primeiro(item, "title"), _primeiro(item, "seo_url")
        if not titulo or not slug:
            continue
        orcamento = item.get("budget") if isinstance(item.get("budget"), dict) else {}
        moeda = ((item.get("currency") or {}) if isinstance(item.get("currency"), dict) else {}).get("code") or "USD"
        estatisticas = item.get("bid_stats") if isinstance(item.get("bid_stats"), dict) else {}
        lances, media = estatisticas.get("bid_count"), estatisticas.get("bid_avg")
        detalhes = [f"Propostas: {lances}" if lances is not None else ""]
        if isinstance(media, (int, float)) and not isinstance(media, bool) and media > 0:
            detalhes.append(f"Média: {media:.2f} {moeda}")
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=fonte.nome,
                titulo=titulo,
                link=f"https://www.freelancer.com/projects/{slug}",
                faixa=_faixa(orcamento.get("minimum"), orcamento.get("maximum"), str(moeda), "projeto"),
                publicada=_data(item.get("time_submitted")),
                descricao=_primeiro(item, "description", "preview_description"),
                detalhes=" | ".join(parte for parte in detalhes if parte),
            )
        )
    return tuple(saida)


FORUM_DA_SHOPIFY = "https://community.shopify.com"


def ler_shopify_community(cliente: httpx.Client, fonte: FonteDaCacada) -> tuple[Oportunidade, ...]:
    """Uma categoria do fórum da Shopify (Discourse) pelo JSON público; o tópico fixado e o fechado ficam de fora.

    O Job Listings (`job-listings/334`) é onde lojistas postam vagas da loja desde jul/2026; o
    fórum fecha cada post em 30 dias.
    """
    dados = _json(cliente, f"{FORUM_DA_SHOPIFY}/c/{(fonte.argumento or 'job-listings/334').strip('/')}.json")
    topicos = _lista((dados.get("topic_list") or {}) if isinstance(dados, dict) else {}, "topics")
    saida = []
    for topico in topicos:
        if topico.get("pinned") or topico.get("closed") or topico.get("archived") or topico.get("visible") is False:
            continue
        titulo, slug, numero = _primeiro(topico, "title"), _primeiro(topico, "slug"), topico.get("id")
        if not titulo or not slug or not numero:
            continue
        respostas = topico.get("posts_count")
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=fonte.nome,
                titulo=titulo,
                link=f"{FORUM_DA_SHOPIFY}/t/{slug}/{numero}",
                publicada=_data(topico.get("created_at")),
                descricao=_primeiro(topico, "excerpt"),
                detalhes=f"Respostas: {max(0, int(respostas) - 1)}" if isinstance(respostas, int) else "",
            )
        )
    return tuple(saida)


# -- listagens públicas de freela ------------------------------------------------------


def ler_workana(
    cliente: httpx.Client, fonte: FonteDaCacada, dormir: Callable[[float], None] = time.sleep
) -> tuple[Oportunidade, ...]:
    categoria = fonte.argumento or "it-programming"
    saida: list[Oportunidade] = []
    for pagina in range(1, PAGINAS_DA_WORKANA + 1):
        if pagina > 1:
            dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
        url = "https://www.workana.com/jobs?" + urlencode({"category": categoria, "language": "pt", "page": pagina})
        lidas = interpretar_workana(_texto(cliente, url), fonte.nome)
        if not lidas and pagina == 1:
            raise FonteSemResposta("a página da Workana não trouxe projetos (a estrutura mudou?)")
        saida += lidas
    return tuple(saida)


def interpretar_workana(pagina: str, nome: str = "Workana") -> tuple[Oportunidade, ...]:
    """Os projetos que a Workana guarda em JSON no atributo `:results-initials` da tag `<search>`."""
    leitor = _AtributoDaTag("search", ":results-initials")
    leitor.feed(pagina)
    if not leitor.valor:
        return ()
    try:
        dados = json.loads(leitor.valor)
    except ValueError:
        return ()
    saida = []
    for item in _lista(dados, "results"):
        slug = _primeiro(item, "slug")
        if not slug:
            continue
        titulo_html = str(item.get("title") or "")
        completo = re.search(r'title="([^"]+)"', titulo_html) or re.search(r"title=\\?\"([^\"\\]+)", titulo_html)
        titulo = _html.unescape(completo.group(1)) if completo else texto_limpo(titulo_html)
        habilidades = ", ".join(
            str(s.get("anchorText", "")) for s in item.get("skills") or [] if isinstance(s, dict)
        )
        detalhes = " | ".join(
            parte
            for parte in (
                texto_limpo(str(item.get("publishedDate") or "")),
                texto_limpo(str(item.get("totalBids") or "")),
                f"habilidades: {habilidades}" if habilidades else "",
            )
            if parte
        )
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=nome,
                titulo=titulo,
                link=f"https://www.workana.com/job/{slug}",
                faixa=texto_limpo(str(item.get("budget") or "")),
                descricao=str(item.get("description") or ""),
                detalhes=detalhes,
            )
        )
    return tuple(saida)


def ler_99freelas(
    cliente: httpx.Client,
    fonte: FonteDaCacada,
    dormir: Callable[[float], None] = time.sleep,
    *,
    paginas: int = PAGINAS_DA_99FREELAS,
    ate_idade: timedelta | None = None,
) -> tuple[Oportunidade, ...]:
    """As `paginas` primeiras da listagem; com `ate_idade`, para antes na página em que o projeto mais novo já passou dessa idade."""
    categoria = fonte.argumento or "web-mobile-e-software"
    saida: list[Oportunidade] = []
    for pagina in range(1, paginas + 1):
        if pagina > 1:
            dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
        url = "https://www.99freelas.com.br/projects?" + urlencode({"categoria": categoria, "page": pagina})
        agora = datetime.now().astimezone()
        lidas = interpretar_99freelas(_texto(cliente, url), fonte.nome, agora)
        if not lidas and pagina == 1:
            raise FonteSemResposta("a página da 99Freelas não trouxe projetos (a estrutura mudou?)")
        saida += lidas
        if ate_idade is not None and _todas_mais_velhas(lidas, agora - ate_idade):
            break
    return tuple(saida)


def _todas_mais_velhas(oportunidades: Sequence[Oportunidade], limite: datetime) -> bool:
    datas = [_publicada_em(o.publicada) for o in oportunidades]
    return bool(datas) and all(data is not None and data < limite for data in datas)


def _publicada_em(texto: str) -> datetime | None:
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return data if data.tzinfo else data.astimezone()


_ITEM_DA_99FREELAS = re.compile(r'<li\b[^>]*class="[^"]*\bresult-item\b[^"]*"[^>]*>', re.I)


_ABRE_EM = re.compile(r"dispon\S*vel para todos os profissionais em\s*(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?", re.I)


def interpretar_99freelas(pagina: str, nome: str = "99Freelas", agora: datetime | None = None) -> tuple[Oportunidade, ...]:
    """Os `li.result-item` da listagem: título e link, a linha de informação e a descrição.

    Projeto com a bandeira de exclusivo só aceita proposta de assinante nas
    primeiras 24 h; a listagem diz quanto falta para abrir, e o detalhe leva a
    hora em que ele, que não assina, já pode propor.
    """
    agora = (agora or datetime.now()).astimezone()
    inicios = [casou.start() for casou in _ITEM_DA_99FREELAS.finditer(pagina)]
    saida = []
    for indice, inicio in enumerate(inicios):
        fim = inicios[indice + 1] if indice + 1 < len(inicios) else len(pagina)
        bloco = pagina[inicio:fim]
        titulo = re.search(r'<h1[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S | re.I)
        if not titulo:
            continue
        href = _html.unescape(titulo.group(1)).split("?")[0]
        info = re.search(r'class="[^"]*\binformation\b[^"]*"[^>]*>(.*?)</p>', bloco, re.S | re.I)
        descricao = re.search(r'class="[^"]*\bdescription\b[^"]*"[^>]*>(.*?)</div>', bloco, re.S | re.I)
        texto_da_info = _info_da_99freelas(info.group(1)) if info else ""
        publicada = re.search(r'class="datetime"[^>]*cp-datetime="(\d+)"', bloco)
        habilidades = ", ".join(texto_limpo(h) for h in re.findall(r'class="habilidade"[^>]*>(.*?)</a>', bloco, re.S))
        exclusivo = _exclusivo_da_99freelas(bloco, agora)
        descricao_limpa = texto_limpo(re.sub(r'<a[^>]*class="(?:more|less)-link"[^>]*>.*?</a>', "", descricao.group(1), flags=re.S)) if descricao else ""
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=nome,
                titulo=texto_limpo(titulo.group(2)),
                link=href if href.startswith("http") else f"https://www.99freelas.com.br{href}",
                publicada=_data(int(publicada.group(1)) / 1000) if publicada else None,
                descricao=descricao_limpa.replace(" …", "").replace("…", ""),
                detalhes=" | ".join(
                    p for p in (exclusivo, texto_da_info, f"habilidades: {habilidades}" if habilidades else "") if p
                ),
            )
        )
    return tuple(saida)


def _exclusivo_da_99freelas(bloco: str, agora: datetime) -> str:
    if "flat_project_exclusive" not in bloco:
        return ""
    falta = _ABRE_EM.search(_html.unescape(bloco))
    if not falta:
        return "Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina até 24 h depois de publicado"
    dias, horas, minutos = (int(parte or 0) for parte in falta.groups())
    abre = agora + timedelta(days=dias, hours=horas, minutes=minutos)
    return f"Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina em {abre:%d/%m às %H:%M}"


def _info_da_99freelas(trecho: str) -> str:
    """A linha de informação sem as datas em milissegundos, que o navegador preencheria."""

    def data(casou: re.Match[str]) -> str:
        momento = datetime.fromtimestamp(int(casou.group(2)) / 1000, UTC)
        if "restante" in casou.group(1):
            dias = (momento - datetime.now(UTC)).days
            return f"{dias} dias" if dias > 0 else "menos de 1 dia"
        return momento.strftime("%d/%m/%Y")

    trecho = re.sub(r'<b[^>]*class="([^"]*datetime[^"]*)"[^>]*cp-datetime="(\d+)"[^>]*>\s*</b>', data, trecho)
    return " ".join(texto_limpo(trecho).split())


# -- o que ele não consegue propor: travado na conta grátis ou já fechado ------------------------

_PROJETO_DO_FREELANCER = re.compile(r"freelancer\.com/projects/([^?#]+?)/?(?:[?#]|$)", re.I)
_PROJETO_DA_99FREELAS = re.compile(r"99freelas\.com\.br/project/[^/?#]+", re.I)
_SO_PARA_QUEM_PAGA = ("pf_only",)
_EXCLUSIVO = "Projeto exclusivo para assinantes da 99Freelas"
#: O cliente pode exigir saldo de US$ 20 na conta de quem propõe, e só a sessão logada dele
#: diz isso (`freelancerCanBidOnProject.php`); ele decidiu não depositar.
AVISO_DE_SALDO_MINIMO = (
    "Se a página disser que o projeto está aberto apenas a freelancers selecionados, pule: pede saldo de US$ 20"
)


@dataclass(frozen=True)
class Filtrado:
    """O que ficou depois do filtro e quantos saíram por cada motivo."""

    ficam: tuple[Oportunidade, ...]
    sem_skill: int = 0
    so_para_quem_paga: int = 0
    fechadas: int = 0
    sem_conta: int = 0
    com_malware: int = 0
    conta_recente: int = 0
    so_para_selecionados: int = 0
    repetidos: int = 0
    ja_propostas: int = 0
    pagas: int = 0
    lotados: int = 0
    lances: tuple[int, int] | None = None
    conexoes: int | None = None

    def somar(self, outro: Filtrado) -> Filtrado:
        """Os contadores somam; o que é leitura do site (lances, conexões) fica com a mais nova."""
        somados = {}
        for campo in fields(self):
            if campo.name == "ficam":
                continue
            meu, dele = getattr(self, campo.name), getattr(outro, campo.name)
            somados[campo.name] = meu + dele if isinstance(meu, int) and isinstance(dele, int) else (dele if dele is not None else meu)
        return Filtrado(outro.ficam, **somados)


def filtrar_o_que_da(
    oportunidades: Sequence[Oportunidade],
    usuario_freelancer: str,
    *,
    plataformas_sem_conta: Sequence[str] = (),
    plataformas_pagas: Sequence[str] = (),
    rede: httpx.BaseTransport | None = None,
    dormir: Callable[[float], None] = time.sleep,
    agora: datetime | None = None,
    sessao: SessaoLogada | None = None,
    max_propostas_freelancer: int = 0,
) -> Filtrado:
    """As organizações com malware, as contas do GitHub recentes, as plataformas sem conta ativa, o
    Freelancer.com pela API (e logado, com `sessao`) e a 99Freelas pela página, nessa ordem."""
    com_malware = barrar_organizacoes_bloqueadas(oportunidades)
    recentes = com_malware.somar(barrar_contas_recentes(com_malware.ficam, rede=rede, agora=agora))
    sem_conta = recentes.somar(barrar_sem_conta(recentes.ficam, plataformas_sem_conta))
    sem_conta = sem_conta.somar(barrar_pagas(sem_conta.ficam, plataformas_pagas))
    freelancer = sem_conta.somar(
        barrar_freelancer(sem_conta.ficam, usuario_freelancer, rede=rede, max_propostas=max_propostas_freelancer)
    )
    if sessao is not None and any(_PROJETO_DO_FREELANCER.search(o.link) for o in freelancer.ficam):
        if sessao.logado(navegador_logado.FREELANCER):
            freelancer = freelancer.somar(conferir_freelancer_logado(freelancer.ficam, sessao))
    return freelancer.somar(conferir_99freelas(freelancer.ficam, rede=rede, dormir=dormir, agora=agora, sessao=sessao))


ORGANIZACOES_BLOQUEADAS = ("SUSU-LABS",)


def barrar_organizacoes_bloqueadas(
    oportunidades: Sequence[Oportunidade], organizacoes: Sequence[str] = ORGANIZACOES_BLOQUEADAS
) -> Filtrado:
    """Tira os links do GitHub de organização cujos repositórios trazem malware.

    Os da SUSU-LABS escondem no `eslint.config.js` um loader que roda via
    `child_process` assim que a config carrega.
    """
    nomes = {o.casefold() for o in organizacoes}
    ficam = tuple(o for o in oportunidades if _organizacao_no_github(o.link) not in nomes)
    if saiu := len(oportunidades) - len(ficam):
        _log.info("Caçada: %d oportunidade(s) de organização com malware conhecido ficaram de fora.", saiu)
    return Filtrado(ficam, com_malware=saiu)


IDADE_MINIMA_DA_CONTA = timedelta(days=90)
REPOSITORIOS_DE_CONTA_VAZIA = 2


def barrar_contas_recentes(
    oportunidades: Sequence[Oportunidade],
    *,
    rede: httpx.BaseTransport | None = None,
    agora: datetime | None = None,
) -> Filtrado:
    """Tira o bounty do GitHub cuja conta dona (organização ou usuário) é recente ou não tem histórico.

    É o jeito das iscas com malware: conta criada há menos de 90 dias, ou com
    até 2 repositórios públicos e nenhum seguidor. Só freela (vaga em repositório
    do GitHub é quadro de vagas, não bounty). Cada conta é consultada uma vez na
    API pública (`/users/<login>`); conta que a API não responde, ou responde
    sem esses campos, fica.
    """
    agora = (agora or datetime.now()).astimezone()
    logins = {o.id: login for o in oportunidades if o.tipo == FREELA and (login := _organizacao_no_github(o.link))}
    if not logins:
        return Filtrado(tuple(oportunidades))
    barrados: set[str] = set()
    try:
        with httpx.Client(transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
            for login in sorted(set(logins.values())):
                try:
                    conta = _json(cliente, f"https://api.github.com/users/{quote_plus(login)}")
                except Exception as erro:  # noqa: BLE001 — sem a conta, o bounty fica
                    _log.info("Caçada: a conta %s do GitHub não respondeu (%s); fica como está.", login, _motivo(erro))
                    continue
                if isinstance(conta, dict) and _conta_suspeita(conta, agora):
                    barrados.add(login)
    except Exception as erro:  # noqa: BLE001 — sem o filtro, a caçada segue com tudo
        _log.warning("Caçada: o filtro de contas do GitHub não rodou: %s", _motivo(erro))
        return Filtrado(tuple(oportunidades))
    ficam = tuple(o for o in oportunidades if logins.get(o.id) not in barrados)
    if saiu := len(oportunidades) - len(ficam):
        _log.info("Caçada: %d bounty(s) de conta do GitHub recente ou sem histórico ficaram de fora.", saiu)
    return Filtrado(ficam, conta_recente=saiu)


def _conta_suspeita(conta: dict, agora: datetime) -> bool:
    criada = _data(conta.get("created_at"))
    if criada is not None and agora - criada < IDADE_MINIMA_DA_CONTA:
        return True
    repositorios, seguidores = conta.get("public_repos"), conta.get("followers")
    if isinstance(repositorios, int) and isinstance(seguidores, int):
        return repositorios <= REPOSITORIOS_DE_CONTA_VAZIA and seguidores == 0
    return False


def _organizacao_no_github(link: str) -> str:
    partes = urlsplit(link)
    if (partes.hostname or "").casefold() not in {"github.com", "www.github.com"}:
        return ""
    return partes.path.strip("/").split("/", 1)[0].casefold()


#: A plataforma paga que tem leitor próprio, pelo tipo da fonte: com o domínio em `[cacada].plataformas_pagas`, a fonte nem é lida.
TIPO_DA_PLATAFORMA_PAGA = {"freelancer.com": "freelancer"}


def tipos_pagos(plataformas: Sequence[str]) -> set[str]:
    """Os tipos de fonte (e os sites do Chrome da caçada) das plataformas de `[cacada].plataformas_pagas`."""
    return {TIPO_DA_PLATAFORMA_PAGA[p] for p in (p.strip().casefold() for p in plataformas) if p in TIPO_DA_PLATAFORMA_PAGA}


def fonte_paga(fonte: FonteDaCacada, plataformas: Sequence[str]) -> bool:
    return fonte.tipo.casefold() in tipos_pagos(plataformas)


def fonte_sem_conta(fonte: FonteDaCacada, plataformas: Sequence[str]) -> bool:
    """A fonte de *Fontes* é de um site em que a conta dele não está ativa (`[cacada].plataformas_sem_conta`)."""
    return fonte.tipo.casefold() in {p.strip().casefold() for p in plataformas}


def barrar_sem_conta(oportunidades: Sequence[Oportunidade], plataformas: Sequence[str]) -> Filtrado:
    """Tira o que vem de site em que a conta dele não está ativa (`[cacada].plataformas_sem_conta`).

    O nome casa com um pedaço do domínio do link (`peopleperhour` pega
    `www.peopleperhour.com`); um domínio inteiro também serve.
    """
    nomes = {p.strip().casefold() for p in plataformas if p.strip()}
    if not nomes:
        return Filtrado(tuple(oportunidades))
    ficam = tuple(o for o in oportunidades if not _de_plataforma(o.link, nomes))
    if saiu := len(oportunidades) - len(ficam):
        _log.info("Caçada: %d oportunidade(s) de %s ficaram de fora (conta não ativa).", saiu, ", ".join(sorted(nomes)))
    return Filtrado(ficam, sem_conta=saiu)


def barrar_pagas(oportunidades: Sequence[Oportunidade], plataformas: Sequence[str]) -> Filtrado:
    """Tira o que vem de site em que responder pede plano pago que ele não assinou (`[cacada].plataformas_pagas`)."""
    nomes = {p.strip().casefold() for p in plataformas if p.strip()}
    if not nomes:
        return Filtrado(tuple(oportunidades))
    ficam = tuple(o for o in oportunidades if not _de_plataforma(o.link, nomes))
    if saiu := len(oportunidades) - len(ficam):
        _log.info("Caçada: %d oportunidade(s) de %s ficaram de fora (responder pede plano pago).", saiu, ", ".join(sorted(nomes)))
    return Filtrado(ficam, pagas=saiu)


def _de_plataforma(link: str, nomes: set[str]) -> bool:
    dominio = (urlsplit(link).hostname or "").casefold()
    return any(nome in dominio.split(".") or dominio == nome or dominio.endswith("." + nome) for nome in nomes)


def barrar_freelancer(
    oportunidades: Sequence[Oportunidade], usuario: str, *, rede: httpx.BaseTransport | None = None, max_propostas: int = 0
) -> Filtrado:
    """Tira os projetos do Freelancer.com em que a conta grátis dele não consegue propor.

    Para propor, o Freelancer.com pede uma skill do projeto que esteja no perfil;
    projeto só para Preferred Freelancer e projeto que já não está aberto também
    saem, e o mesmo projeto com o link em outra caixa fica uma vez só, como o
    mesmo anúncio repostado com outro título (`_anuncio`). Projeto que
    a API não acha e erro na rede deixam tudo como está: o filtro nunca derruba a
    caçada. Sem usuário, só o que já fechou sai.

    Com `max_propostas`, sai também o que já tem tantas propostas pela contagem da API na hora: lá
    um projeto de Shopify passa de 50 em uma hora, e com 6 lances por mês não vale entrar na fila.
    """
    links = {o.id: casou.group(1) for o in oportunidades if (casou := _PROJETO_DO_FREELANCER.search(o.link))}
    if not links:
        return Filtrado(tuple(oportunidades))
    try:
        with httpx.Client(transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
            skills = _skills_do_perfil(cliente, usuario) if usuario else set()
            projetos = _projetos_do_freelancer(cliente, sorted(set(links.values())))
    except Exception as erro:  # noqa: BLE001 — sem o filtro, a caçada segue com tudo
        _log.warning("Caçada: o filtro do Freelancer.com não rodou: %s", _motivo(erro))
        return Filtrado(tuple(oportunidades))
    if usuario and not skills:
        _log.warning("Caçada: o perfil %s do Freelancer.com não tem skills; só o que fechou sai.", usuario)
    ficam: list[Oportunidade] = []
    vistos: set[str] = set()
    anuncios: set[tuple[str, ...]] = set()
    sem_skill = so_para_quem_paga = fechadas = repetidos = lotados = 0
    for oportunidade in oportunidades:
        slug = links.get(oportunidade.id, "").casefold()
        projeto = projetos.get(slug)
        if projeto is None:
            ficam.append(oportunidade)
            continue
        if slug in vistos:
            continue
        vistos.add(slug)
        anuncio = _anuncio(projeto, oportunidade)
        if anuncio is not None:
            if anuncio in anuncios:
                repetidos += 1
                continue
            anuncios.add(anuncio)
        if not _aberto_no_freelancer(projeto):
            fechadas += 1
            continue
        if max_propostas and _lances(projeto) >= max_propostas:
            lotados += 1
            continue
        travas = projeto.get("upgrades") if isinstance(projeto.get("upgrades"), dict) else {}
        if any(travas.get(trava) is True for trava in _SO_PARA_QUEM_PAGA):
            so_para_quem_paga += 1
            continue
        pedidas = {j.get("id"): str(j.get("name", "")) for j in projeto.get("jobs") or [] if isinstance(j, dict)}
        casam = [nome for id_, nome in pedidas.items() if id_ in skills]
        if skills and pedidas and not casam:
            sem_skill += 1
            continue
        if casam and "escolha a skill" not in oportunidade.detalhes:
            aviso = f"Freelancer.com: na proposta, escolha a skill {', '.join(casam)}. {AVISO_DE_SALDO_MINIMO}"
            oportunidade = replace(oportunidade, detalhes=" | ".join(p for p in (oportunidade.detalhes, aviso) if p))
        ficam.append(oportunidade)
    _log.info(
        "Caçada: Freelancer.com — %d sem skill do perfil, %d só para Preferred Freelancer, %d já fechados e %d com "
        "propostas demais ficaram de fora.",
        sem_skill,
        so_para_quem_paga,
        fechadas,
        lotados,
    )
    return Filtrado(tuple(ficam), sem_skill, so_para_quem_paga, fechadas, repetidos=repetidos, lotados=lotados)


def _lances(projeto: dict) -> int:
    estatisticas = projeto.get("bid_stats") if isinstance(projeto.get("bid_stats"), dict) else {}
    contagem = estatisticas.get("bid_count")
    return contagem if isinstance(contagem, int) and not isinstance(contagem, bool) else 0


DESCRICAO_DO_REPETIDO = 300


def _anuncio(projeto: dict, oportunidade: Oportunidade) -> tuple[str, ...] | None:
    """O que faz dois projetos do Freelancer.com serem o mesmo anúncio repostado.

    A API pública devolve `owner_id` nulo e o cliente que reposta muda o título
    (põe a data no fim), mas a descrição vem igual: o começo dela, com a moeda e
    a faixa do orçamento, é a chave. O dono entra quando vem preenchido.
    """
    descricao = str(projeto.get("description") or projeto.get("preview_description") or oportunidade.descricao or "")
    descricao = " ".join(descricao.casefold().split())[:DESCRICAO_DO_REPETIDO]
    dono = "" if projeto.get("owner_id") is None else str(projeto["owner_id"])
    if not descricao:
        return (dono, _titulo_normalizado(projeto)) if dono else None
    orcamento = projeto.get("budget") if isinstance(projeto.get("budget"), dict) else {}
    moeda = projeto.get("currency") if isinstance(projeto.get("currency"), dict) else {}
    return (dono, descricao, str(moeda.get("code") or ""), str(orcamento.get("minimum") or ""), str(orcamento.get("maximum") or ""))


def _titulo_normalizado(projeto: dict) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(projeto.get("title") or "").casefold()).split())


def conferir_freelancer_logado(oportunidades: Sequence[Oportunidade], sessao: SessaoLogada) -> Filtrado:
    """Abre logado cada projeto do Freelancer.com que passou pela API.

    Sai o "aberto apenas a freelancers selecionados" (pede saldo de US$ 20); o
    número de propostas vira o visto logado (o da API anda atrasado); os lances
    restantes da conta vêm da primeira página que os mostrar. Página que não
    abre deixa o projeto como estava, com o aviso do saldo.
    """
    ficam: list[Oportunidade] = []
    selecionados = 0
    lances: tuple[int, int] | None = None
    for oportunidade in oportunidades:
        if not _PROJETO_DO_FREELANCER.search(oportunidade.link):
            ficam.append(oportunidade)
            continue
        try:
            pagina = navegador_logado.ler_freelancer(sessao.html(oportunidade.link))
        except navegador_logado.SemNavegador as erro:
            _log.info("Caçada: %s não abriu logado (%s); fica como está.", oportunidade.link, erro)
            ficam.append(oportunidade)
            continue
        if not pagina.logado:
            ficam.append(oportunidade)
            continue
        lances = lances or pagina.lances
        if pagina.selecionados:
            selecionados += 1
            continue
        partes = [p for p in oportunidade.detalhes.split(" | ") if p and not p.startswith("Propostas:")]
        partes = [p.replace(f" {AVISO_DE_SALDO_MINIMO}", "") for p in partes]
        if pagina.ofertas is not None:
            partes.insert(0, f"Propostas: {pagina.ofertas} (visto logado)")
        ficam.append(replace(oportunidade, detalhes=" | ".join(partes)))
    _log.info("Caçada: Freelancer.com logado — %d só para selecionados ficaram de fora.", selecionados)
    return Filtrado(tuple(ficam), so_para_selecionados=selecionados, lances=lances)


def _aberto_no_freelancer(projeto: dict) -> bool:
    situacao = str(projeto.get("frontend_project_status") or "open").casefold()
    return situacao == "open" and str(projeto.get("status") or "active").casefold() == "active"


def conferir_99freelas(
    oportunidades: Sequence[Oportunidade],
    *,
    rede: httpx.BaseTransport | None = None,
    dormir: Callable[[float], None] = time.sleep,
    agora: datetime | None = None,
    sessao: SessaoLogada | None = None,
) -> Filtrado:
    """Abre a página de cada projeto da 99Freelas: o fechado sai, o exclusivo diz quando abre.

    Projeto aberto tem o botão de enviar proposta (`/project/bid/`); o fechado ou
    em andamento não tem. Página que não abre deixa o projeto como está. Com ele
    logado no Chrome da caçada, a conferência é a logada (`conferir_99freelas_logada`).
    """
    agora = (agora or datetime.now()).astimezone()
    if sessao is not None and any(_PROJETO_DA_99FREELAS.search(o.link) for o in oportunidades):
        if sessao.logado(navegador_logado.NOVENTA_E_NOVE):
            return conferir_99freelas_logada(oportunidades, sessao, dormir=dormir, agora=agora)
    ficam: list[Oportunidade] = []
    fechadas = 0
    lidas = 0
    with httpx.Client(transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
        for oportunidade in oportunidades:
            if not _PROJETO_DA_99FREELAS.search(oportunidade.link):
                ficam.append(oportunidade)
                continue
            if lidas:
                dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
            lidas += 1
            try:
                pagina = _texto(cliente, oportunidade.link)
            except Exception as erro:  # noqa: BLE001 — sem a página, o projeto fica
                _log.info("Caçada: a página de %s não abriu (%s); fica como está.", oportunidade.link, _motivo(erro))
                ficam.append(oportunidade)
                continue
            if "/project/bid/" not in pagina:
                fechadas += 1
                continue
            exclusivo = _exclusivo_da_99freelas(pagina, agora)
            if exclusivo:
                resto = [p for p in oportunidade.detalhes.split(" | ") if p and not p.startswith(_EXCLUSIVO)]
                oportunidade = replace(oportunidade, detalhes=" | ".join([exclusivo, *resto]))
            ficam.append(oportunidade)
    if lidas:
        _log.info("Caçada: 99Freelas — %d de %d projeto(s) já estavam fechados.", fechadas, lidas)
    return Filtrado(tuple(ficam), fechadas=fechadas)


def conferir_99freelas_logada(
    oportunidades: Sequence[Oportunidade],
    sessao: SessaoLogada,
    *,
    dormir: Callable[[float], None] = time.sleep,
    agora: datetime | None = None,
) -> Filtrado:
    """A 99Freelas pela página logada: sai o cancelado, o em andamento (freelancer escolhido), o
    fechado e o que ele já propôs; do aberto, o formulário de proposta diz quantas conexões custa.

    O exclusivo de assinante segue a regra de sempre: fica, com a hora em que abre para ele.
    """
    agora = (agora or datetime.now()).astimezone()
    ficam: list[Oportunidade] = []
    fechadas = ja_propostas = lidas = 0
    conexoes: int | None = None
    for oportunidade in oportunidades:
        casou = _PROJETO_DA_99FREELAS.search(oportunidade.link)
        if not casou:
            ficam.append(oportunidade)
            continue
        if lidas:
            dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
        lidas += 1
        try:
            html = sessao.html(oportunidade.link)
        except navegador_logado.SemNavegador as erro:
            _log.info("Caçada: %s não abriu logado (%s); fica como está.", oportunidade.link, erro)
            ficam.append(oportunidade)
            continue
        pagina = navegador_logado.ler_99freelas(html)
        if pagina.situacao == navegador_logado.JA_PROPOS:
            ja_propostas += 1
            continue
        if pagina.situacao != navegador_logado.ABERTO:
            fechadas += 1
            continue
        resto = [p for p in oportunidade.detalhes.split(" | ") if p and not p.startswith((_EXCLUSIVO, "99Freelas: custa"))]
        exclusivo = _exclusivo_da_99freelas(html, agora)
        try:
            proposta = navegador_logado.ler_proposta_da_99freelas(sessao.html(_link_da_proposta(casou.group(0))))
        except navegador_logado.SemNavegador:
            proposta = navegador_logado.PropostaDa99Freelas()
        if proposta.exclusivo and not exclusivo:
            exclusivo = f"{_EXCLUSIVO}: abre para quem não assina até 24 h depois de publicado"
        custo = ""
        if proposta.custo is not None and proposta.saldo is not None:
            conexoes = proposta.saldo
            custo = f"99Freelas: custa {proposta.custo} {'conexão' if proposta.custo == 1 else 'conexões'}; sobram {proposta.saldo}"
        ficam.append(replace(oportunidade, detalhes=" | ".join(p for p in (exclusivo, custo, *resto) if p)))
    _log.info(
        "Caçada: 99Freelas logada — de %d projeto(s), %d fechado(s) ou com freelancer e %d já proposto(s).",
        lidas,
        fechadas,
        ja_propostas,
    )
    return Filtrado(tuple(ficam), fechadas=fechadas, ja_propostas=ja_propostas, conexoes=conexoes)


def _link_da_proposta(projeto: str) -> str:
    return "https://www." + projeto.replace("/project/", "/project/bid/", 1)


def e_do_freelancer(link: str) -> bool:
    return bool(_PROJETO_DO_FREELANCER.search(link)) and ".com.br" not in (urlsplit(link).hostname or "")


def e_da_99freelas(link: str) -> bool:
    return bool(_PROJETO_DA_99FREELAS.search(link))


def custo_em_conexoes(oportunidade: Oportunidade) -> int | None:
    casou = re.search(r"99Freelas: custa (\d+) conex", oportunidade.detalhes)
    return int(casou.group(1)) if casou else None


def _skills_do_perfil(cliente: httpx.Client, usuario: str) -> set[int]:
    url = "https://www.freelancer.com/api/users/0.1/users/?" + urlencode({"usernames[]": usuario, "jobs": "true"})
    dados = _json(cliente, url)
    usuarios = ((dados.get("result") or {}) if isinstance(dados, dict) else {}).get("users") or {}
    lista = usuarios.values() if isinstance(usuarios, dict) else usuarios
    return {j["id"] for u in lista if isinstance(u, dict) for j in u.get("jobs") or [] if isinstance(j, dict) and "id" in j}


def _projetos_do_freelancer(cliente: httpx.Client, seo_urls: Sequence[str]) -> dict[str, dict]:
    projetos: dict[str, dict] = {}
    for inicio in range(0, len(seo_urls), 20):
        consulta = [("seo_urls[]", s) for s in seo_urls[inicio : inicio + 20]]
        consulta += [("job_details", "true"), ("upgrade_details", "true"), ("full_description", "true")]
        dados = _json(cliente, "https://www.freelancer.com/api/projects/0.1/projects/?" + urlencode(consulta))
        for projeto in _lista((dados.get("result") or {}) if isinstance(dados, dict) else {}, "projects"):
            if projeto.get("seo_url"):
                projetos[str(projeto["seo_url"]).casefold()] = projeto
    return projetos


# -- VintePila, pela listagem logada ------------------------------------------------------

PAGINAS_DA_VINTEPILA = 3
#: A VintePila não filtra por categoria: o que fica é o que cita uma destas (ou a stack do perfil).
PALAVRAS_DA_VINTEPILA = (
    "site", "sites", "landing page", "loja virtual", "e-commerce", "ecommerce", "shopify", "wordpress", "woocommerce",
    "react", "next", "nextjs", "node", "nodejs", "javascript", "typescript", "python", "api", "integração",
    "automação", "script", "scraping", "bot", "sistema", "aplicativo", "app", "web", "html", "css", "php",
    "banco de dados", "planilha", "n8n", "chatbot", "programador", "programação", "desenvolvedor",
)
AVISO_DA_VINTEPILA_SEM_SERVICO = (
    "crie um serviço ativo na VintePila para poder propor (sem ele, todo projeto aparece como Inelegível)"
)


@dataclass(frozen=True)
class ColetaDaVintePila:
    oportunidades: tuple[Oportunidade, ...] = ()
    cheios: int = 0
    aviso: str = ""


def coletar_vintepila(
    sessao: SessaoLogada,
    palavras: Sequence[str] = (),
    *,
    paginas: int = PAGINAS_DA_VINTEPILA,
    nome: str = "VintePila (logado)",
) -> ColetaDaVintePila:
    """A listagem logada da VintePila, com o que casa com as palavras e ainda tem vaga de candidato.

    O "Inelegível" da conta sem serviço ativo aparece em todo projeto (até no
    0/5): uma página de projeto é aberta sempre (a primeira que fica, ou a
    primeira da listagem), e com o aviso a VintePila inteira fica de fora.
    Quem chama confere o login antes.
    """
    termos = tuple(dict.fromkeys((*PALAVRAS_DA_VINTEPILA, *palavras)))
    cartoes: dict[str, Oportunidade] = {}
    for numero in range(1, paginas + 1):
        try:
            html = sessao.html(navegador_logado.LISTAGEM_DA_VINTEPILA.format(pagina=numero))
        except navegador_logado.SemNavegador as erro:
            _log.info("Caçada: a página %d da VintePila não abriu (%s).", numero, erro)
            break
        lidos = navegador_logado.ler_listagem_da_vintepila(html, nome)
        if not lidos:
            break
        for cartao in lidos:
            cartoes.setdefault(cartao.link, cartao)
    casam = [c for c in cartoes.values() if navegador_logado.casa_com_palavras(c, termos)]
    ficam = [c for c in casam if not navegador_logado.candidatos_cheios(c)]
    cheios = len(casam) - len(ficam)
    sonda = ficam[0] if ficam else next(iter(cartoes.values()), None)
    if sonda is not None:
        try:
            primeiro = navegador_logado.ler_projeto_da_vintepila(sessao.html(sonda.link))
        except navegador_logado.SemNavegador:
            primeiro = None
        if primeiro is not None and primeiro.sem_servico_ativo:
            _log.info("Caçada: a VintePila diz que a conta não tem serviço ativo; nada de lá.")
            return ColetaDaVintePila(aviso=AVISO_DA_VINTEPILA_SEM_SERVICO)
        if ficam and primeiro is not None and primeiro.candidatos and primeiro.candidatos[0] >= primeiro.candidatos[1]:
            ficam, cheios = ficam[1:], cheios + 1
    _log.info("Caçada: VintePila logada — %d de %d projeto(s) casam e ainda aceitam candidato.", len(ficam), len(cartoes))
    return ColetaDaVintePila(tuple(ficam), cheios)


# -- LinkedIn, pela busca pública ---------------------------------------------------------


def ler_linkedin(
    cliente: httpx.Client, fonte: FonteDaCacada, dormir: Callable[[float], None] = time.sleep
) -> tuple[Oportunidade, ...]:
    """A busca *guest*: 25 cartões por página, sem login, com pausa — o 429 vem por volta da 10ª."""
    partes = [parte.strip() for parte in fonte.argumento.split("|")]
    termos = partes[0] if partes else "desenvolvedor web"
    local = partes[1] if len(partes) > 1 and partes[1] else "Brasil"
    modo = partes[2].casefold() if len(partes) > 2 else "remoto"
    parametros = {"keywords": termos, "location": local, "f_TPR": "r604800"}
    parametros["f_WT"] = "2" if modo.startswith("remot") else "1,3"
    saida: list[Oportunidade] = []
    for pagina in range(PAGINAS_DO_LINKEDIN):
        if pagina:
            dormir(random.uniform(3.0, 7.0))
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
            + urlencode({**parametros, "start": pagina * 25})
        )
        resposta = cliente.get(url)
        if resposta.status_code == 429 and saida:
            _log.info("LinkedIn pediu pausa (429) na página %d: fico com o que veio.", pagina + 1)
            break
        _conferir(resposta)
        lidas = interpretar_linkedin(resposta.text, fonte.nome, modo)
        if not lidas:
            break
        saida += lidas
    return tuple(saida)


_CARTAO_DO_LINKEDIN = re.compile(r'<div\b[^>]*class="[^"]*\bbase-search-card\b[^"]*"', re.I)


def interpretar_linkedin(pagina: str, nome: str = "LinkedIn", modo: str = "remoto") -> tuple[Oportunidade, ...]:
    inicios = [casou.start() for casou in _CARTAO_DO_LINKEDIN.finditer(pagina)]
    saida = []
    for indice, inicio in enumerate(inicios):
        fim = inicios[indice + 1] if indice + 1 < len(inicios) else len(pagina)
        bloco = pagina[inicio:fim]
        link = re.search(r'<a[^>]*class="[^"]*\bbase-card__full-link\b[^"]*"[^>]*href="([^"]+)"', bloco, re.I) or re.search(
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*\bbase-card__full-link\b', bloco, re.I
        )
        titulo = re.search(r'class="[^"]*\bbase-search-card__title\b[^"]*"[^>]*>(.*?)</h3>', bloco, re.S | re.I)
        if not link or not titulo:
            continue
        empresa = re.search(r'class="[^"]*\bbase-search-card__subtitle\b[^"]*"[^>]*>(.*?)</h4>', bloco, re.S | re.I)
        local = re.search(r'class="[^"]*\bjob-search-card__location\b[^"]*"[^>]*>(.*?)</span>', bloco, re.S | re.I)
        quando = re.search(r'<time[^>]*datetime="([\d-]+)"', bloco)
        salario = re.search(r'class="[^"]*\bjob-search-card__salary-info\b[^"]*"[^>]*>(.*?)</span>', bloco, re.S | re.I)
        endereco = _html.unescape(link.group(1)).split("?")[0]
        lugar = texto_limpo(local.group(1)) if local else ""
        saida.append(
            Oportunidade.nova(
                tipo=VAGA,
                fonte=nome,
                titulo=texto_limpo(titulo.group(1)),
                link=endereco,
                empresa=texto_limpo(empresa.group(1)) if empresa else "",
                local=f"{'Remoto' if modo.startswith('remot') else 'Presencial/híbrido'} — {lugar}" if lugar else "",
                faixa=texto_limpo(salario.group(1)) if salario else "",
                publicada=quando.group(1) if quando else None,
                detalhes="LinkedIn: candidatura só por ele, nunca automática",
            )
        )
    return tuple(saida)


# -- o texto inteiro de uma oportunidade -------------------------------------------------


def ler_detalhe(oportunidade: Oportunidade, *, rede: httpx.BaseTransport | None = None, limite: int = 12_000) -> str:
    """O texto da página da oportunidade, para o preparo ler a vaga inteira.

    No LinkedIn, a página *guest* do anúncio (`jobPosting/<id>`) tem a descrição
    sem login. Falhar aqui não é erro: o preparo trabalha com o que a coleta já
    trouxe.
    """
    url = oportunidade.link
    casou = re.search(r"linkedin\.com/jobs/view/(?:[^/]*-)?(\d+)", url)
    if casou:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{casou.group(1)}"
    try:
        with httpx.Client(transport=rede, timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
            resposta = cliente.get(url)
    except httpx.HTTPError as erro:
        _log.info("Detalhe de %s não veio: %s", oportunidade.link, _motivo(erro))
        return ""
    if resposta.status_code >= 400 or "html" not in resposta.headers.get("content-type", "html"):
        return ""
    corpo = re.sub(r"<(nav|header|footer|svg|noscript)\b.*?</\1>", " ", resposta.text, flags=re.S | re.I)
    return texto_limpo(corpo)[:limite]


# -- bastidores ---------------------------------------------------------------------------


_LEITORES: dict[str, Callable[..., tuple[Oportunidade, ...]]] = {
    "himalayas": ler_himalayas,
    "remotive": ler_remotive,
    "remoteok": ler_remoteok,
    "jobicy": ler_jobicy,
    "rss": ler_rss,
    "github": ler_github,
    "hn": ler_hn,
    "gupy": ler_gupy,
    "workana": ler_workana,
    "99freelas": ler_99freelas,
    "linkedin": ler_linkedin,
    "getonbrd": ler_getonbrd,
    "freelancer": ler_freelancer,
    "shopify_community": ler_shopify_community,
}
_PAGINADOS = frozenset({"workana", "99freelas", "linkedin"})


class _AtributoDaTag(HTMLParser):
    """O valor de um atributo na primeira ocorrência de uma tag — com as entidades já resolvidas."""

    def __init__(self, tag: str, atributo: str) -> None:
        super().__init__(convert_charrefs=True)
        self._tag, self._atributo = tag, atributo.lower()
        self.valor: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.valor is None and tag == self._tag:
            for nome, valor in attrs:
                if nome.lower() == self._atributo and valor:
                    self.valor = valor
                    return


def _json(cliente: httpx.Client, url: str, *, cabecalhos: dict[str, str] | None = None) -> object:
    resposta = cliente.get(url, headers={"Accept": "application/json", **(cabecalhos or {})})
    _conferir(resposta)
    try:
        return resposta.json()
    except ValueError as erro:
        raise FonteSemResposta("a resposta não é JSON (a fonte mudou ou pediu verificação)") from erro


def _texto(cliente: httpx.Client, url: str) -> str:
    resposta = cliente.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
    _conferir(resposta)
    return resposta.text


def _conferir(resposta: httpx.Response) -> None:
    if resposta.status_code >= 400:
        raise FonteSemResposta(f"HTTP {resposta.status_code}")
    if not resposta.content.strip():
        raise FonteSemResposta("resposta vazia")


def _lista(dados: object, *chaves: str) -> list[dict]:
    if isinstance(dados, list):
        return [item for item in dados if isinstance(item, dict)]
    if isinstance(dados, dict):
        for chave in chaves:
            valor = dados.get(chave)
            if isinstance(valor, list):
                return [item for item in valor if isinstance(item, dict)]
    return []


def _primeiro(item: dict, *chaves: str) -> str:
    for chave in chaves:
        valor = item.get(chave)
        if isinstance(valor, (str, int, float)) and not isinstance(valor, bool) and str(valor).strip():
            return str(valor).strip()
    return ""


def _faixa(minimo: object, maximo: object, moeda: str, periodo: str) -> str:
    def numero(valor: object) -> float | None:
        try:
            convertido = float(valor)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return convertido if convertido > 0 else None

    baixo, alto = numero(minimo), numero(maximo)
    if baixo is None and alto is None:
        return ""
    partes = " – ".join(f"{valor:,.0f}".replace(",", ".") for valor in (baixo, alto) if valor is not None)
    return f"{moeda} {partes} por {periodo}"


def _data(valor: object) -> datetime | None:
    if valor in (None, "", 0):
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        segundos = valor / 1000 if valor > 10_000_000_000 else valor
        try:
            return datetime.fromtimestamp(segundos, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    texto = str(valor).strip()
    if texto.isdigit():
        return _data(int(texto))
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _velha(oportunidade: Oportunidade, limite: datetime) -> bool:
    momento = _data(oportunidade.publicada)
    return momento is not None and momento < limite


def _motivo(erro: BaseException) -> str:
    if isinstance(erro, httpx.TimeoutException):
        return "tempo esgotado"
    if isinstance(erro, httpx.HTTPError):
        return f"rede: {type(erro).__name__}"
    texto = str(erro).strip().splitlines()[0] if str(erro).strip() else ""
    return texto[:160] or type(erro).__name__


def nomes_das_fontes(fontes: Iterable[FonteDaCacada]) -> list[str]:
    return [fonte.nome for fonte in fontes if fonte.tipo in TIPOS_LIDOS_AQUI]
