"""A coleta do jornal, sem rede.

As amostras em `fixtures/jornal/` são feeds reais baixados em 2026-09-25 e
cortados a poucos itens: RSS 2.0 do G1, RSS 0.91 da Folha (ISO-8859-1
declarado no XML), Atom do YouTube e do Verge, UOL Carros (`pubDate` em
português e charset só no cabeçalho HTTP) e Motor1 (`enclosure`). O HTTP é
interceptado com `httpx.MockTransport`; os comportamentos de corte usam RSS
montado aqui, para cada teste dizer só o que importa.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import httpx

from whis.feeds import (
    ITENS_LIDOS_POR_FEED,
    TETO_DO_TIME,
    TETO_POR_SECAO,
    UA_LEITOR,
    UA_NAVEGADOR,
    Coleta,
    coletar,
)
from whis.fontes_do_jornal import Fonte, FontesDoJornal, Secao

AMOSTRAS = Path(__file__).parent / "fixtures" / "jornal"

#: Pouco depois das amostras: 2026-09-24 21:00 em Brasília.
AGORA = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)


def amostra(nome: str, tipo: str = "application/xml; charset=UTF-8") -> httpx.Response:
    return httpx.Response(200, content=(AMOSTRAS / nome).read_bytes(), headers={"content-type": tipo})


def rss(*itens: dict) -> httpx.Response:
    """Um RSS 2.0 mínimo; cada item é `{titulo, link, data, resumo?, imagem?}`."""
    corpo = []
    for item in itens:
        extra = ""
        if item.get("imagem"):
            extra = f'<media:content url="{escape(item["imagem"])}" medium="image"/>'
        corpo.append(
            "<item>"
            f"<title>{escape(item['titulo'])}</title>"
            f"<link>{escape(item['link'])}</link>"
            f"<description>{escape(item.get('resumo', ''))}</description>"
            f"<pubDate>{format_datetime(item['data'])}</pubDate>{extra}"
            "</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>t</title>'
        + "".join(corpo)
        + "</channel></rss>"
    )
    return httpx.Response(200, content=xml.encode("utf-8"), headers={"content-type": "application/rss+xml"})


def item(titulo: str, horas_atras: float = 1, link: str | None = None, **extra) -> dict:
    return {
        "titulo": titulo,
        "link": link or f"https://exemplo.com/{abs(hash(titulo))}",
        "data": AGORA - timedelta(hours=horas_atras),
        **extra,
    }


def jornal(
    secoes: dict[str, list[tuple[str, str]]],
    *,
    time: tuple[str, str] | None = None,
    nomes: tuple[str, ...] = (),
) -> FontesDoJornal:
    return FontesDoJornal(
        secoes=tuple(
            Secao(id=id_, titulo=id_.title(), minimo=3, maximo=5, fontes=tuple(Fonte(n, u) for n, u in fontes))
            for id_, fontes in secoes.items()
        ),
        time=Fonte(*time) if time else None,
        nomes=nomes,
    )


def transporte(
    respostas: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]],
    registro: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(pedido)
        resposta = respostas.get(str(pedido.url))
        if resposta is None:
            return httpx.Response(404)
        return resposta(pedido) if callable(resposta) else resposta

    return httpx.MockTransport(responder)


def coletar_de(fontes: FontesDoJornal, respostas: dict, **extra) -> Coleta:
    return coletar(
        fontes,
        extra.pop("agora", AGORA),
        transporte=transporte(respostas, extra.pop("registro", None)),
        espera_da_segunda_rodada_s=0,
        **extra,
    )


# --- parser, com as amostras reais -------------------------------------------------


def test_rss_20_do_g1_traz_titulo_link_data_com_fuso_resumo_e_imagem():
    url = "https://g1.globo.com/rss/g1/politica/"
    coleta = coletar_de(jornal({"brasil": [("G1 Política", url)]}), {url: amostra("g1_politica.xml")})

    primeiro = coleta.candidatos["brasil"][0]
    assert primeiro.id == "brasil-1"
    assert primeiro.secao == "brasil"
    assert primeiro.fonte == "G1 Política"
    assert primeiro.titulo.startswith("Quaest para o Senado em RO: Máximo, 18%")
    assert primeiro.link.startswith("https://g1.globo.com/ro/rondonia/eleicoes/2026/noticia/")
    assert primeiro.data == datetime(2026, 9, 24, 23, 13, 4, tzinfo=UTC)
    assert primeiro.data.tzinfo is not None
    assert primeiro.imagem.startswith("https://s2-g1.glbimg.com/")
    assert "<" not in primeiro.resumo and primeiro.resumo


def test_rss_091_da_folha_desembrulha_o_redir_e_le_iso_8859_1_declarado():
    url = "https://feeds.folha.uol.com.br/poder/rss091.xml"
    coleta = coletar_de(
        jornal({"brasil": [("Folha Poder", url)]}),
        {url: amostra("folha_poder_rss091.xml", "text/xml")},
        agora=datetime(2026, 9, 25, 3, 0, tzinfo=UTC),
    )

    primeiro = coleta.candidatos["brasil"][0]
    assert primeiro.link == (
        "https://www1.folha.uol.com.br/poder/2026/09/"
        "jose-sarney-e-internado-em-sp-para-dar-continuidade-a-tratamento-de-pneumonia.shtml"
    )
    assert primeiro.titulo == "José Sarney é internado em SP para dar continuidade a tratamento de pneumonia"
    assert primeiro.data == datetime(2026, 9, 25, 2, 43, tzinfo=UTC)
    assert primeiro.imagem is None
    assert primeiro.resumo.startswith("O ex-presidente José Sarney , 96,")
    assert all("redir.folha" not in c.link for c in coleta.candidatos["brasil"])


def test_atom_do_youtube_pega_a_miniatura_do_media_group():
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCSNxIry_FPFcQDFRbi3VOAw"
    coleta = coletar_de(
        jornal({"musica": [("YouTube · Andertons", url)]}),
        {url: amostra("youtube_andertons_atom.xml", "text/xml; charset=UTF-8")},
    )

    videos = coleta.candidatos["musica"]
    assert len(videos) == 1
    assert videos[0].link == "https://www.youtube.com/watch?v=-NnMlp07e8E"
    assert videos[0].imagem == "https://i2.ytimg.com/vi/-NnMlp07e8E/hqdefault.jpg"
    assert videos[0].data == datetime(2026, 9, 24, 14, 0, 23, tzinfo=UTC)
    assert videos[0].resumo.startswith("Lee and Phil X")


def test_atom_do_verge_pega_o_link_alternate_e_o_primeiro_img_do_conteudo():
    url = "https://www.theverge.com/rss/index.xml"
    coleta = coletar_de(
        jornal({"tecnologia": [("The Verge", url)]}),
        {url: amostra("verge_atom.xml")},
        agora=datetime(2026, 9, 25, 3, 0, tzinfo=UTC),
    )

    primeiro = coleta.candidatos["tecnologia"][0]
    assert primeiro.titulo == "Here’s the Tesla Semi… again"
    assert primeiro.link.startswith("https://www.theverge.com/transportation/1000317/")
    assert primeiro.data == datetime(2026, 9, 25, 2, 12, 57, tzinfo=UTC)
    assert primeiro.imagem.startswith("https://platform.theverge.com/wp-content/uploads/sites/2/2026/09/Semi_77.jpg")
    assert "&#038;" not in primeiro.imagem
    assert len(coleta.candidatos["tecnologia"]) == 3


def test_uol_com_pubdate_em_portugues_e_charset_so_no_cabecalho():
    url = "https://rss.uol.com.br/feed/carros.xml"
    coleta = coletar_de(
        jornal({"carros": [("UOL Carros", url)]}),
        {url: amostra("uol_carros_pubdate_pt.xml", "text/xml;charset=ISO-8859-1")},
    )

    titulos = [c.titulo for c in coleta.candidatos["carros"]]
    assert titulos == ["Geely começa a produzir o EX5 EM-i no Brasil"]
    geely = coleta.candidatos["carros"][0]
    assert geely.data == datetime(2026, 9, 24, 19, 25, 8, tzinfo=UTC)
    assert geely.imagem.startswith("https://conteudo.imguol.com.br/")


def test_enclosure_de_imagem_do_motor1_vira_capa():
    url = "https://motor1.uol.com.br/rss/news/all/"
    coleta = coletar_de(jornal({"carros": [("Motor1 Brasil", url)]}), {url: amostra("motor1_enclosure.xml")})

    assert [c.imagem for c in coleta.candidatos["carros"]] == [
        "https://cdn.motor1.com/images/mgl/1ZPK2W/s3/f1-russell-voa-no-tl2-e-crava-antonelli-em-baku-bortoleto-e-14o.jpg",
        "https://cdn.motor1.com/images/mgl/6Z8vZZ/s3/chevrolet-onix-eco-tem-motor-turbo-rodando-apenas-com-etanol.jpg",
    ]


def test_svg_nunca_vira_imagem():
    url = "https://a.example/feed"
    coleta = coletar_de(
        jornal({"brasil": [("A", url)]}),
        {
            url: rss(
                item("Com logo em SVG", imagem="https://agenciabrasil.ebc.com.br/logo.svg"),
                item("Com SVG no corpo", resumo='<img src="https://x.example/a.svg?v=1"> texto'),
            )
        },
    )

    assert [c.imagem for c in coleta.candidatos["brasil"]] == [None, None]


def test_resumo_sai_sem_html_e_com_no_maximo_220_caracteres():
    url = "https://a.example/feed"
    longo = "<p>Uma <b>frase</b> &amp; outra.</p> " + "palavra " * 60
    coleta = coletar_de(jornal({"mundo": [("A", url)]}), {url: rss(item("Longo", resumo=longo))})

    resumo = coleta.candidatos["mundo"][0].resumo
    assert resumo.startswith("Uma frase & outra. palavra")
    assert len(resumo) <= 220
    assert resumo.endswith("…")


# --- cortes ------------------------------------------------------------------------


def test_janela_de_24_horas_antes_de_agora():
    url = "https://a.example/feed"
    coleta = coletar_de(
        jornal({"mundo": [("A", url)]}),
        {url: rss(item("Recente", 23.5), item("Velho", 24.5), item("Do futuro distante", -3))},
    )

    assert [c.titulo for c in coleta.candidatos["mundo"]] == ["Recente"]


def test_a_amostra_do_g1_perde_o_item_de_anteontem():
    url = "https://g1.globo.com/rss/g1/politica/"
    coleta = coletar_de(jornal({"brasil": [("G1", url)]}), {url: amostra("g1_politica.xml")})

    assert len(coleta.candidatos["brasil"]) == 3
    assert all(c.data >= AGORA - timedelta(hours=24) for c in coleta.candidatos["brasil"])


def test_no_maximo_40_itens_lidos_por_feed():
    url = "https://a.example/feed"
    itens = [item(f"Notícia número {n}", horas_atras=n * 0.1) for n in range(1, 51)]
    coleta = coletar_de(jornal({"mundo": [("A", url)]}), {url: rss(*itens)})

    assert ITENS_LIDOS_POR_FEED == 40
    assert len(coleta.candidatos["mundo"]) == TETO_POR_SECAO
    assert "Notícia número 41" not in {c.titulo for c in coleta.candidatos["mundo"]}


def test_no_maximo_40_itens_lidos_mesmo_quando_os_primeiros_sao_velhos():
    url = "https://a.example/feed"
    itens = [item(f"Velho {n}", horas_atras=48) for n in range(40)] + [item("Novo além do 40º", 1)]
    coleta = coletar_de(jornal({"mundo": [("A", url)]}), {url: rss(*itens)})

    assert coleta.candidatos["mundo"] == ()


def test_dedupe_por_titulo_normalizado_entre_fontes_fica_o_mais_novo():
    a, b = "https://a.example/feed", "https://b.example/feed"
    coleta = coletar_de(
        jornal({"mundo": [("A", a), ("B", b)]}),
        {
            a: rss(item("Cúpula do G20 termina sem acordo!", 3, link="https://a.example/1")),
            b: rss(item("cúpula do G20 termina — sem acordo", 1, link="https://b.example/1")),
        },
    )

    assert [(c.fonte, c.link) for c in coleta.candidatos["mundo"]] == [("B", "https://b.example/1")]


def test_dedupe_por_link():
    a, b = "https://a.example/feed", "https://b.example/feed"
    mesmo = "https://noticia.example/x"
    coleta = coletar_de(
        jornal({"mundo": [("A", a), ("B", b)]}),
        {a: rss(item("Título um", 2, link=mesmo)), b: rss(item("Outro título", 1, link=mesmo))},
    )

    assert [c.titulo for c in coleta.candidatos["mundo"]] == ["Outro título"]


def test_opiniao_cortada_pela_url_em_qualquer_secao():
    url = "https://a.example/feed"
    caminhos = ["colunas", "coluna", "opiniao", "blogs", "blog", "podcast", "artigo"]
    itens = [item(f"Opinião {c}", link=f"https://a.example/{c}/texto") for c in caminhos]
    itens.append(item("Notícia de verdade", link="https://a.example/noticia/fato"))
    coleta = coletar_de(jornal({"tecnologia": [("A", url)], "musica": [("A", url)]}), {url: rss(*itens)})

    for secao in ("tecnologia", "musica"):
        assert [c.titulo for c in coleta.candidatos[secao]] == ["Notícia de verdade"]


def test_opiniao_da_folha_real_sai_pela_url_desembrulhada():
    url = "https://feeds.folha.uol.com.br/poder/rss091.xml"
    coleta = coletar_de(
        jornal({"brasil": [("Folha Poder", url)]}),
        {url: amostra("folha_poder_rss091.xml", "text/xml")},
        agora=datetime(2026, 9, 25, 3, 0, tzinfo=UTC),
    )

    assert len(coleta.candidatos["brasil"]) == 3
    assert all("/colunas/" not in c.link for c in coleta.candidatos["brasil"])


def test_destaque_por_nome_em_palavra_inteira_sem_caixa_e_no_topo():
    url = "https://a.example/feed"
    coleta = coletar_de(
        jornal({"tecnologia": [("A", url)]}, nomes=("Nord", "Line 6")),
        {
            url: rss(
                item("Notícia mais nova", 1),
                item("Nordic countries ban something", 2),
                item("Pedal novo", 3, resumo="A line 6 lançou um modelador."),
                item("NORD Stage 5 anunciado", 4),
            )
        },
    )

    candidatos = coleta.candidatos["tecnologia"]
    assert [(c.titulo, c.destaque) for c in candidatos] == [
        ("Pedal novo", True),
        ("NORD Stage 5 anunciado", True),
        ("Notícia mais nova", False),
        ("Nordic countries ban something", False),
    ]
    assert [c.id for c in candidatos] == ["tecnologia-1", "tecnologia-2", "tecnologia-3", "tecnologia-4"]


def test_ja_publicado_sai_dos_candidatos():
    url = "https://a.example/feed"
    coleta = coletar_de(
        jornal({"mundo": [("A", url)]}),
        {url: rss(item("Já saiu", link="https://a.example/velho"), item("Inédita", link="https://a.example/novo"))},
        ja_publicados=frozenset({"https://a.example/velho"}),
    )

    assert [c.titulo for c in coleta.candidatos["mundo"]] == ["Inédita"]


def test_teto_de_30_por_secao_com_destaques_primeiro_e_depois_os_mais_novos():
    a, b = "https://a.example/feed", "https://b.example/feed"
    coleta = coletar_de(
        jornal({"musica": [("A", a), ("B", b)]}, nomes=("Satriani",)),
        {
            a: rss(*[item(f"Notícia A{n}", horas_atras=n * 0.5) for n in range(1, 21)]),
            b: rss(
                *[item(f"Notícia B{n}", horas_atras=n * 0.5 + 0.25) for n in range(1, 20)],
                item("Satriani anuncia turnê", horas_atras=23),
            ),
        },
    )

    candidatos = coleta.candidatos["musica"]
    assert len(candidatos) == TETO_POR_SECAO == 30
    assert candidatos[0].titulo == "Satriani anuncia turnê"
    datas = [c.data for c in candidatos[1:]]
    assert datas == sorted(datas, reverse=True)
    assert candidatos[-1].id == "musica-30"


def test_fonte_pequena_entra_mesmo_com_fonte_grande_de_40_itens_mais_novos():
    grande, pequena = "https://grande.example/feed", "https://pequena.example/feed"
    coleta = coletar_de(
        jornal({"brasil": [("Grande", grande), ("Pequena", pequena)]}, nomes=("STF",)),
        {
            grande: rss(*[item(f"Grande {n}", horas_atras=n * 0.1) for n in range(1, 41)]),
            pequena: rss(
                item("Pequena 1", horas_atras=10),
                item("Pequena 2", horas_atras=12),
                item("STF julga caso antigo", horas_atras=20),
            ),
        },
    )

    candidatos = coleta.candidatos["brasil"]
    assert len(candidatos) == TETO_POR_SECAO
    assert [c.titulo for c in candidatos[:5]] == [
        "STF julga caso antigo",
        "Grande 1",
        "Pequena 1",
        "Grande 2",
        "Pequena 2",
    ]
    assert [c.titulo for c in candidatos[5:]] == [f"Grande {n}" for n in range(3, 28)]


def test_time_no_maximo_8_mais_novos_primeiro_com_ids_proprios():
    url = "https://ge.globo.com/rss/ge/futebol/times/corinthians/"
    coleta = coletar_de(
        jornal({"futebol": [("ge", "https://ge.example/feed")]}, time=("Corinthians", url)),
        {url: rss(*[item(f"Timão {n}", horas_atras=n) for n in range(12, 0, -1)])},
    )

    assert TETO_DO_TIME == 8
    assert [c.titulo for c in coleta.time] == [f"Timão {n}" for n in range(1, 9)]
    assert [c.id for c in coleta.time][:2] == ["time-1", "time-2"]
    assert all(c.secao == "time" for c in coleta.time)


def test_toda_secao_aparece_mesmo_vazia_e_sem_time_a_tupla_e_vazia():
    coleta = coletar_de(
        jornal({"mundo": [("A", "https://a.example/feed")], "carros": [("B", "https://b.example/feed")]}),
        {"https://a.example/feed": rss(), "https://b.example/feed": rss()},
    )

    assert coleta.candidatos == {"mundo": (), "carros": ()}
    assert coleta.time == ()
    assert coleta.fontes_com_falha == ()


# --- rede ----------------------------------------------------------------------------


def test_ua_de_leitor_na_segunda_tentativa_depois_de_403():
    url = "https://a.example/feed"
    agentes: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        agentes.append(pedido.headers["User-Agent"])
        if pedido.headers["User-Agent"] == UA_NAVEGADOR:
            return httpx.Response(403)
        return rss(item("Liberado para leitor"))

    coleta = coletar_de(jornal({"mundo": [("A", url)]}), {url: responder})

    assert agentes == [UA_NAVEGADOR, UA_LEITOR]
    assert [c.titulo for c in coleta.candidatos["mundo"]] == ["Liberado para leitor"]
    assert coleta.fontes_com_falha == ()


def test_ua_de_leitor_tambem_depois_de_202_e_de_corpo_vazio():
    for primeira in (httpx.Response(202, content=b"<rss/>"), httpx.Response(200, content=b"  ")):
        url = "https://a.example/feed"
        agentes: list[str] = []

        def responder(pedido: httpx.Request, primeira=primeira) -> httpx.Response:
            agentes.append(pedido.headers["User-Agent"])
            return primeira if pedido.headers["User-Agent"] == UA_NAVEGADOR else rss(item("Ok"))

        coleta = coletar_de(jornal({"mundo": [("A", url)]}), {url: responder})

        assert agentes == [UA_NAVEGADOR, UA_LEITOR]
        assert len(coleta.candidatos["mundo"]) == 1


def test_404_nao_troca_de_ua_na_mesma_rodada():
    url = "https://a.example/feed"
    registro: list[httpx.Request] = []

    coleta = coletar_de(jornal({"mundo": [("A", url)]}), {}, registro=registro)

    assert [p.headers["User-Agent"] for p in registro] == [UA_NAVEGADOR, UA_NAVEGADOR]
    assert coleta.fontes_com_falha == ("A (HTTP 404)",)


def test_segunda_rodada_recupera_feed_que_falhou_na_primeira():
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCSNxIry_FPFcQDFRbi3VOAw"
    chamadas = []

    def intermitente(pedido: httpx.Request) -> httpx.Response:
        chamadas.append(pedido)
        if len(chamadas) == 1:
            return httpx.Response(404)
        return amostra("youtube_andertons_atom.xml")

    coleta = coletar_de(jornal({"musica": [("YouTube · Andertons", url)]}), {url: intermitente})

    assert len(chamadas) == 2
    assert len(coleta.candidatos["musica"]) == 1
    assert coleta.fontes_com_falha == ()


def test_quem_falha_nas_duas_rodadas_vai_para_fontes_com_falha_com_o_codigo():
    ok, fora, sem_rede, quebrado = (f"https://{n}.example/feed" for n in ("ok", "fora", "rede", "html"))

    def sem_conexao(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    coleta = coletar_de(
        jornal(
            {"mundo": [("Ok", ok), ("Fora", fora), ("Sem rede", sem_rede)], "carros": [("Quebrado", quebrado)]}
        ),
        {
            ok: rss(item("Chegou")),
            fora: httpx.Response(503),
            sem_rede: sem_conexao,
            quebrado: httpx.Response(200, content=b"<html><body>captcha</body>"),
        },
    )

    assert coleta.fontes_com_falha == ("Fora (HTTP 503)", "Sem rede (ConnectError)", "Quebrado (ParseError)")
    assert [c.titulo for c in coleta.candidatos["mundo"]] == ["Chegou"]
    assert coleta.candidatos["carros"] == ()


def test_todos_os_feeds_sao_pedidos_e_os_com_falha_pedidos_de_novo():
    urls = [f"https://f{n}.example/feed" for n in range(15)]
    registro: list[httpx.Request] = []
    respostas = {u: rss(item(f"Item {n}")) for n, u in enumerate(urls[:12])}

    coletar_de(jornal({"mundo": [(f"F{n}", u) for n, u in enumerate(urls)]}), respostas, registro=registro)

    pedidos = [str(p.url) for p in registro]
    assert sorted(set(pedidos)) == sorted(urls)
    assert all(pedidos.count(u) == 1 for u in urls[:12])
    assert all(pedidos.count(u) == 2 for u in urls[12:])
