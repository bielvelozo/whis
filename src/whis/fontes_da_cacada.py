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
"""

from __future__ import annotations

import html as _html
import json
import logging
import random
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlencode, urlsplit

import httpx

from .criterios_da_cacada import FonteDaCacada
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
        "getonbrd", "freelancer",
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
                lidas = leitor(cliente, fonte, dormir) if fonte.tipo in _PAGINADOS else leitor(cliente, fonte)
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
        lances = ((item.get("bid_stats") or {}) if isinstance(item.get("bid_stats"), dict) else {}).get("bid_count")
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=fonte.nome,
                titulo=titulo,
                link=f"https://www.freelancer.com/projects/{slug}",
                faixa=_faixa(orcamento.get("minimum"), orcamento.get("maximum"), str(moeda), "projeto"),
                publicada=_data(item.get("time_submitted")),
                descricao=_primeiro(item, "description", "preview_description"),
                detalhes=f"Propostas: {lances}" if lances is not None else "",
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
    cliente: httpx.Client, fonte: FonteDaCacada, dormir: Callable[[float], None] = time.sleep
) -> tuple[Oportunidade, ...]:
    categoria = fonte.argumento or "web-mobile-e-software"
    saida: list[Oportunidade] = []
    for pagina in range(1, PAGINAS_DA_99FREELAS + 1):
        if pagina > 1:
            dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
        url = "https://www.99freelas.com.br/projects?" + urlencode({"categoria": categoria, "page": pagina})
        lidas = interpretar_99freelas(_texto(cliente, url), fonte.nome)
        if not lidas and pagina == 1:
            raise FonteSemResposta("a página da 99Freelas não trouxe projetos (a estrutura mudou?)")
        saida += lidas
    return tuple(saida)


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

    def somar(self, outro: Filtrado) -> Filtrado:
        return Filtrado(
            outro.ficam,
            self.sem_skill + outro.sem_skill,
            self.so_para_quem_paga + outro.so_para_quem_paga,
            self.fechadas + outro.fechadas,
            self.sem_conta + outro.sem_conta,
            self.com_malware + outro.com_malware,
            self.conta_recente + outro.conta_recente,
        )


def filtrar_o_que_da(
    oportunidades: Sequence[Oportunidade],
    usuario_freelancer: str,
    *,
    plataformas_sem_conta: Sequence[str] = (),
    rede: httpx.BaseTransport | None = None,
    dormir: Callable[[float], None] = time.sleep,
    agora: datetime | None = None,
) -> Filtrado:
    """As organizações com malware, as contas do GitHub recentes, as plataformas sem conta ativa, o Freelancer.com pela API e a 99Freelas pela página, nessa ordem."""
    com_malware = barrar_organizacoes_bloqueadas(oportunidades)
    recentes = com_malware.somar(barrar_contas_recentes(com_malware.ficam, rede=rede, agora=agora))
    sem_conta = recentes.somar(barrar_sem_conta(recentes.ficam, plataformas_sem_conta))
    freelancer = sem_conta.somar(barrar_freelancer(sem_conta.ficam, usuario_freelancer, rede=rede))
    return freelancer.somar(conferir_99freelas(freelancer.ficam, rede=rede, dormir=dormir, agora=agora))


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


def _de_plataforma(link: str, nomes: set[str]) -> bool:
    dominio = (urlsplit(link).hostname or "").casefold()
    return any(nome in dominio.split(".") or dominio == nome or dominio.endswith("." + nome) for nome in nomes)


def barrar_freelancer(
    oportunidades: Sequence[Oportunidade], usuario: str, *, rede: httpx.BaseTransport | None = None
) -> Filtrado:
    """Tira os projetos do Freelancer.com em que a conta grátis dele não consegue propor.

    Para propor, o Freelancer.com pede uma skill do projeto que esteja no perfil;
    projeto só para Preferred Freelancer e projeto que já não está aberto também
    saem, e o mesmo projeto com o link em outra caixa fica uma vez só. Projeto que
    a API não acha e erro na rede deixam tudo como está: o filtro nunca derruba a
    caçada. Sem usuário, só o que já fechou sai.
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
    sem_skill = so_para_quem_paga = fechadas = 0
    for oportunidade in oportunidades:
        slug = links.get(oportunidade.id, "").casefold()
        projeto = projetos.get(slug)
        if projeto is None:
            ficam.append(oportunidade)
            continue
        if slug in vistos:
            continue
        vistos.add(slug)
        if not _aberto_no_freelancer(projeto):
            fechadas += 1
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
        "Caçada: Freelancer.com — %d sem skill do perfil, %d só para Preferred Freelancer e %d já fechados ficaram de fora.",
        sem_skill,
        so_para_quem_paga,
        fechadas,
    )
    return Filtrado(tuple(ficam), sem_skill, so_para_quem_paga, fechadas)


def _aberto_no_freelancer(projeto: dict) -> bool:
    situacao = str(projeto.get("frontend_project_status") or "open").casefold()
    return situacao == "open" and str(projeto.get("status") or "active").casefold() == "active"


def conferir_99freelas(
    oportunidades: Sequence[Oportunidade],
    *,
    rede: httpx.BaseTransport | None = None,
    dormir: Callable[[float], None] = time.sleep,
    agora: datetime | None = None,
) -> Filtrado:
    """Abre a página de cada projeto da 99Freelas: o fechado sai, o exclusivo diz quando abre.

    Projeto aberto tem o botão de enviar proposta (`/project/bid/`); o fechado ou
    em andamento não tem. Página que não abre deixa o projeto como está.
    """
    agora = (agora or datetime.now()).astimezone()
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
        consulta += [("job_details", "true"), ("upgrade_details", "true")]
        dados = _json(cliente, "https://www.freelancer.com/api/projects/0.1/projects/?" + urlencode(consulta))
        for projeto in _lista((dados.get("result") or {}) if isinstance(dados, dict) else {}, "projects"):
            if projeto.get("seo_url"):
                projetos[str(projeto["seo_url"]).casefold()] = projeto
    return projetos


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
