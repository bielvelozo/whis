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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlencode

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
    {"himalayas", "remotive", "remoteok", "jobicy", "rss", "github", "hn", "gupy", "workana", "99freelas", "linkedin"}
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


def interpretar_99freelas(pagina: str, nome: str = "99Freelas") -> tuple[Oportunidade, ...]:
    """Os `li.result-item` da listagem: título e link, a linha de informação e a descrição."""
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
        descricao_limpa = texto_limpo(re.sub(r'<a[^>]*class="(?:more|less)-link"[^>]*>.*?</a>', "", descricao.group(1), flags=re.S)) if descricao else ""
        saida.append(
            Oportunidade.nova(
                tipo=FREELA,
                fonte=nome,
                titulo=texto_limpo(titulo.group(2)),
                link=href if href.startswith("http") else f"https://www.99freelas.com.br{href}",
                publicada=_data(int(publicada.group(1)) / 1000) if publicada else None,
                descricao=descricao_limpa.replace(" …", "").replace("…", ""),
                detalhes=" | ".join(p for p in (texto_da_info, f"habilidades: {habilidades}" if habilidades else "") if p),
            )
        )
    return tuple(saida)


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
