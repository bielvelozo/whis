"""A caçada logada: o Chrome da caçada lido em Python, com as páginas reais de tests/fixtures/cacada_logada/."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from whis import navegador_logado
from whis.__main__ import main
from whis.cacada import GuardaDoPlano, _Estado, cacar, montar_relatorio, tentar_a_sorte
from whis.configuracao import Configuracao, carregar
from whis.corrida import Checkpoint
from whis.criterios_da_cacada import Criterios
from whis.fakes_da_cacada import NavegadorLogadoFake, coleta_fake, portas_fake
from whis.fontes_da_cacada import (
    AVISO_DA_VINTEPILA_SEM_SERVICO,
    AVISO_DE_SALDO_MINIMO,
    barrar_freelancer,
    barrar_pagas,
    coletar_vintepila,
    conferir_99freelas,
    conferir_freelancer_logado,
    custo_em_conexoes,
    filtrar_o_que_da,
)
from whis.navegador_logado import (
    ABERTO,
    CANCELADO,
    DESLOGADO,
    EM_ANDAMENTO,
    FECHADO,
    FREELANCER,
    FREELANCER_BR,
    JA_PROPOS,
    LOGADO,
    NOVENTA_E_NOVE,
    PAGINAS_DE_CONFERENCIA,
    PAGINAS_DE_LOGIN,
    PERFIL_EM_USO,
    SEM_CHROME,
    VINTEPILA,
    NavegadorLogado,
    SemNavegador,
    candidatos_cheios,
    casa_com_palavras,
    estado_do_site,
    frase_do_estado,
    ler_99freelas,
    ler_freelancer,
    ler_listagem_da_vintepila,
    ler_projeto_da_vintepila,
    ler_proposta_da_99freelas,
    logado_no_html,
    motivo_do_chrome,
)
from whis.freelas_rapidos import criterios_de_freelas
from whis.oportunidades import FREELA, TENTAR_A_SORTE, Oportunidade, Veredito


@pytest.fixture
def configuracao(configuracao: Configuracao) -> Configuracao:
    """Estes são do Freelancer.com ativo: desde 28/10 o padrão de [cacada].plataformas_pagas o deixa de fora."""
    return replace(configuracao, cacada_plataformas_pagas=("freelancer.com.br",))


FIXTURES = Path(__file__).parent / "fixtures" / "cacada_logada"


def fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("site", "logada", "deslogada"),
    [
        (FREELANCER, "freelancer_aberto.html", "freelancer_deslogado.html"),
        (NOVENTA_E_NOVE, "99freelas_aberto.html", "99freelas_deslogado.html"),
        (VINTEPILA, "vintepila_listagem.html", "vintepila_deslogado.html"),
    ],
)
def test_o_login_de_cada_site_sai_do_cabecalho(site, logada, deslogada):
    assert logado_no_html(site, fixture(logada))
    assert not logado_no_html(site, fixture(deslogada))


def test_freelancer_com_br_deslogado():
    assert not logado_no_html(FREELANCER_BR, fixture("freelancerbr_projeto_deslogado.html"))
    assert not logado_no_html(FREELANCER_BR, fixture("freelancerbr_listagem_deslogado.html"))


def test_projeto_do_freelancer_logado():
    aberto = ler_freelancer(fixture("freelancer_aberto.html"))
    selecionados = ler_freelancer(fixture("freelancer_selecionados.html"))
    deslogado = ler_freelancer(fixture("freelancer_deslogado.html"))

    assert (aberto.logado, aberto.selecionados, aberto.ofertas, aberto.lances) == (True, False, 113, (0, 6))
    assert (selecionados.selecionados, selecionados.ofertas) == (True, 103)
    assert (deslogado.logado, deslogado.ofertas, deslogado.lances) == (False, 114, None)


@pytest.mark.parametrize(
    ("nome", "situacao"),
    [
        ("99freelas_aberto.html", ABERTO),
        ("99freelas_deslogado.html", ABERTO),
        ("99freelas_cancelado.html", CANCELADO),
        ("99freelas_escolhido.html", EM_ANDAMENTO),
        ("99freelas_ja_propos.html", JA_PROPOS),
        ("99freelas_bid_exclusivo.html", FECHADO),
    ],
)
def test_situacao_do_projeto_da_99freelas(nome, situacao):
    assert ler_99freelas(fixture(nome)).situacao == situacao


def test_propostas_do_projeto_da_99freelas():
    assert ler_99freelas(fixture("99freelas_aberto.html")).propostas == 200


def test_formulario_de_proposta_da_99freelas():
    proposta = ler_proposta_da_99freelas(fixture("99freelas_bid.html"))
    exclusivo = ler_proposta_da_99freelas(fixture("99freelas_bid_exclusivo.html"))

    assert (proposta.custo, proposta.restantes, proposta.saldo, proposta.exclusivo) == (1, 14, 15, False)
    assert (exclusivo.custo, exclusivo.exclusivo) == (None, True)


def test_projeto_da_vintepila():
    cheio = ler_projeto_da_vintepila(fixture("vintepila_inelegivel.html"))
    vazio = ler_projeto_da_vintepila(fixture("vintepila_inelegivel_0de5.html"))

    assert (cheio.logado, cheio.sem_servico_ativo, cheio.candidatos) == (True, True, (5, 5))
    assert (vazio.sem_servico_ativo, vazio.candidatos) == (True, (0, 5)), "inelegível pela conta, não pelo limite"
    assert not ler_projeto_da_vintepila(fixture("vintepila_listagem.html")).sem_servico_ativo


def test_listagem_da_vintepila():
    cartoes = ler_listagem_da_vintepila(fixture("vintepila_listagem.html"))

    assert len(cartoes) == 10
    primeiro = cartoes[0]
    assert primeiro.link == "https://www.vintepila.com.br/trabalhos-freelance/profissional-diagramacao-de-uma-revista-de-medicina"
    assert primeiro.faixa == "R$ 50,00 - R$ 180,00"
    assert "Candidatos: 5/sem limite" in primeiro.detalhes, "o rótulo PRO tira o teto de 5"
    assert "prazo: 1 dias" in primeiro.detalhes
    assert all(c.descricao and c.titulo for c in cartoes)
    assert any(candidatos_cheios(c) for c in cartoes)
    assert not candidatos_cheios(primeiro)


def test_palavras_casam_sem_acento_e_por_palavra_inteira():
    cartao = ler_listagem_da_vintepila(fixture("vintepila_listagem.html"))[0]

    assert casa_com_palavras(cartao, ["diagramação"])
    assert not casa_com_palavras(cartao, ["diagrama"])
    assert not casa_com_palavras(cartao, ["react", "shopify"])


def test_os_motivos_do_chrome_que_nao_abre():
    assert motivo_do_chrome("Chromium distribution 'chrome' is not found at C:\\...") == SEM_CHROME
    assert motivo_do_chrome("Failed to create a ProcessSingleton for your profile directory") == PERFIL_EM_USO
    assert motivo_do_chrome("boom\nmais").startswith("o Chrome não abriu: boom")


def test_o_fake_confere_o_login_uma_vez_por_sessao_e_o_estado_vira_frase():
    fake = NavegadorLogadoFake(
        {
            PAGINAS_DE_CONFERENCIA[FREELANCER]: fixture("freelancer_aberto.html"),
            PAGINAS_DE_CONFERENCIA[VINTEPILA]: fixture("vintepila_deslogado.html"),
        }
    )
    sessao = fake.abrir()

    assert estado_do_site(sessao, FREELANCER) == LOGADO
    assert sessao.logado(FREELANCER)
    assert estado_do_site(sessao, VINTEPILA) == DESLOGADO
    assert not sessao.logado(NOVENTA_E_NOVE), "página que não abre é deslogado"
    assert fake.visitadas.count(PAGINAS_DE_CONFERENCIA[FREELANCER]) == 1
    assert "entre de novo pelo `whis navegador`" in frase_do_estado(VINTEPILA, DESLOGADO)
    assert estado_do_site(None, FREELANCER) == ""


def test_perfil_em_uso_vira_estado_e_ninguem_abre_pagina():
    fake = NavegadorLogadoFake({}, motivo=PERFIL_EM_USO)
    sessao = fake.abrir()

    assert estado_do_site(sessao, FREELANCER) == PERFIL_EM_USO
    with pytest.raises(SemNavegador):
        sessao.html("https://www.freelancer.com/x")
    assert "feche-o para a caçada usar o login" in frase_do_estado(FREELANCER, PERFIL_EM_USO)
    assert "sem Chrome" in frase_do_estado(FREELANCER, SEM_CHROME)


def test_o_navegador_de_verdade_sem_playwright_vira_motivo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def sem_playwright():
        raise ImportError("No module named 'playwright'")

    monkeypatch.setattr(navegador_logado, "_playwright", sem_playwright)
    sessao = NavegadorLogado(perfil=tmp_path / "perfil").abrir()

    with pytest.raises(SemNavegador):
        sessao.html("https://www.freelancer.com/x")
    assert sessao.motivo.startswith("o Playwright não abriu")
    assert not sessao.logado(FREELANCER)
    sessao.fechar()


def test_o_navegador_de_verdade_abre_fora_da_tela_no_perfil_da_cacada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    lancados: list[tuple] = []

    class Pagina:
        url = ""

        def goto(self, url, **_):
            self.url = url

        def wait_for_load_state(self, *_a, **_k):
            return None

        def content(self):
            return f"<html>{self.url}</html>"

    class Contexto:
        pages = [Pagina()]
        fechado = False

        def close(self):
            Contexto.fechado = True

    class Chromium:
        def launch_persistent_context(self, perfil, **opcoes):
            lancados.append((perfil, opcoes))
            return Contexto()

    class Gerente:
        chromium = Chromium()

        def start(self):
            return self

        def stop(self):
            return None

    monkeypatch.setattr(navegador_logado, "_playwright", Gerente)
    with NavegadorLogado(perfil=tmp_path / "perfil").abrir() as sessao:
        assert sessao.html("https://a.b/c") == "<html>https://a.b/c</html>"
        sessao.html("https://a.b/d")

    [(perfil, opcoes)] = lancados
    assert perfil == str(tmp_path / "perfil")
    assert opcoes["channel"] == "chrome" and opcoes["headless"] is False
    assert "--window-position=-32000,-32000" in opcoes["args"]
    assert Contexto.fechado


# -- 02: Freelancer.com logado --------------------------------------------------------------------------


def _rede(respostas: dict[str, httpx.Response]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        for trecho, resposta in respostas.items():
            if trecho in str(pedido.url):
                return resposta
        return httpx.Response(404)

    return httpx.MockTransport(responder)


def _do_freelancer(slug: str, detalhes: str = "") -> Oportunidade:
    return Oportunidade.nova(
        tipo=FREELA, fonte="Freelancer.com", titulo=slug, link=f"https://www.freelancer.com/projects/{slug}", detalhes=detalhes
    )


def _logado_no_freelancer(**paginas: str) -> NavegadorLogadoFake:
    return NavegadorLogadoFake(
        {PAGINAS_DE_CONFERENCIA[FREELANCER]: fixture("freelancer_aberto.html")}
        | {f"https://www.freelancer.com/projects/{slug.replace('__', '/')}": html for slug, html in paginas.items()}
    )


def test_logado_sai_o_so_para_selecionados_e_as_propostas_sao_as_da_pagina():
    aviso = f"Freelancer.com: na proposta, escolha a skill React.js. {AVISO_DE_SALDO_MINIMO}"
    oportunidades = [
        _do_freelancer("typescript/aberto", f"Propostas: 282 | {aviso}"),
        _do_freelancer("python/selecionados", "Propostas: 30"),
        _do_freelancer("php/nao-abre", f"Propostas: 7 | {aviso}"),
        Oportunidade.nova(tipo=FREELA, fonte="Workana", titulo="Site", link="https://www.workana.com/job/site"),
    ]
    fake = _logado_no_freelancer(
        typescript__aberto=fixture("freelancer_aberto.html"), python__selecionados=fixture("freelancer_selecionados.html")
    )

    filtrado = conferir_freelancer_logado(oportunidades, fake.abrir())

    assert [o.titulo for o in filtrado.ficam] == ["typescript/aberto", "php/nao-abre", "Site"]
    assert filtrado.ficam[0].detalhes == "Propostas: 113 (visto logado) | Freelancer.com: na proposta, escolha a skill React.js."
    assert filtrado.ficam[1].detalhes == oportunidades[2].detalhes, "a página que não abre deixa tudo como estava"
    assert (filtrado.so_para_selecionados, filtrado.lances) == (1, (0, 6))


LOJA_SHOPIFY = "I need an e-commerce website built on Shopify from the ground up. The store should be clean and modern."


def _projeto_da_api(id_: int, slug: str, titulo: str, descricao: str = LOJA_SHOPIFY, **resto) -> dict:
    return {
        "id": id_, "seo_url": slug, "title": titulo, "description": descricao, "owner_id": None, "owner_id_new": None,
        "currency": {"code": "USD"}, "budget": {"minimum": 30, "maximum": 250}, **resto,
    }


def test_o_mesmo_anuncio_repostado_com_outro_titulo_vira_um():
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        return httpx.Response(200, json={"result": {"projects": [
            _projeto_da_api(40761844, "shopify/Build-My-Shopify-Store-40761844", "Build My Shopify Store"),
            _projeto_da_api(40761877, "shopify/Build-My-Shopify-Store-40761877", "Build My Shopify Store - 11/10/2026 05:35 EDT"),
            _projeto_da_api(40761900, "shopify/Build-My-Shopify-Store-40761900", "Build My Shopify Store", budget={"minimum": 250, "maximum": 750}),
            _projeto_da_api(40761901, "shopify/Outra-Loja-40761901", "Build My Shopify Store", descricao="Need a Shopify theme fix."),
        ]}})

    oportunidades = [
        _do_freelancer("shopify/Build-My-Shopify-Store-40761844"),
        _do_freelancer("shopify/Build-My-Shopify-Store-40761877"),
        _do_freelancer("shopify/Build-My-Shopify-Store-40761900"),
        _do_freelancer("shopify/Outra-Loja-40761901"),
    ]

    filtrado = barrar_freelancer(oportunidades, "", rede=httpx.MockTransport(responder))

    assert [o.titulo for o in filtrado.ficam] == [
        "shopify/Build-My-Shopify-Store-40761844", "shopify/Build-My-Shopify-Store-40761900", "shopify/Outra-Loja-40761901"
    ], "a faixa de orçamento diferente e a descrição diferente não são repetidos"
    assert filtrado.repetidos == 1
    assert all("full_description=true" in url for url in pedidos if "/projects/" in url)


def test_com_o_dono_preenchido_ele_tambem_conta():
    rede = _rede({"/projects/?": httpx.Response(200, json={"result": {"projects": [
        _projeto_da_api(1, "a/um", "Loja", owner_id=77),
        _projeto_da_api(2, "a/dois", "Loja de novo", owner_id=78),
    ]}})})

    filtrado = barrar_freelancer([_do_freelancer("a/um"), _do_freelancer("a/dois")], "", rede=rede)

    assert len(filtrado.ficam) == 2 and filtrado.repetidos == 0


def test_sem_login_no_freelancer_fica_o_caminho_da_api_com_o_aviso_do_saldo():
    aviso = f"Freelancer.com: na proposta, escolha a skill React.js. {AVISO_DE_SALDO_MINIMO}"
    oportunidades = [_do_freelancer("python/selecionados", aviso)]
    fake = NavegadorLogadoFake(
        {
            PAGINAS_DE_CONFERENCIA[FREELANCER]: fixture("freelancer_deslogado.html"),
            "https://www.freelancer.com/projects/python/selecionados": fixture("freelancer_selecionados.html"),
        }
    )

    filtrado = filtrar_o_que_da(oportunidades, "", rede=_rede({}), sessao=fake.abrir())

    assert filtrado.ficam == tuple(oportunidades)
    assert fake.visitadas == [PAGINAS_DE_CONFERENCIA[FREELANCER]]


def test_a_caçada_logada_conta_os_selecionados_e_os_lances_em_fontes(configuracao: Configuracao, tmp_path: Path):
    selecionado = _do_freelancer("python/selecionados", "Propostas: 30")
    aberto = _do_freelancer("typescript/aberto", "Propostas: 282")

    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["Freelancer.com · Python"] = (selecionado, aberto)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar
    portas.rede = _rede({})
    portas.navegador_logado = _logado_no_freelancer(
        typescript__aberto=fixture("freelancer_aberto.html"), python__selecionados=fixture("freelancer_selecionados.html")
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "python/selecionados" not in relatorio
    dados = json.loads((tmp_path / "estado" / "checkpoint.json").read_text(encoding="utf-8"))
    [visto] = [o for o in dados["oportunidades"] if o["link"] == aberto.link]
    assert visto["detalhes"] == "Propostas: 113 (visto logado)"
    assert "- 1 do Freelancer.com ficaram de fora porque, logado, a página diz que são só para freelancers selecionados" in relatorio
    assert "- Freelancer.com: 0 de 6 lances restantes este mês (visto logado)." in relatorio


def test_a_caçada_tira_o_freelancer_com_propostas_demais_e_conta_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    lotado = _do_freelancer("shopify/lotado", "Propostas: 4")
    cedo = _do_freelancer("shopify/cedo", "Propostas: 2")

    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["Freelancer.com · Shopify"] = (lotado, cedo)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar
    portas.rede = _rede({"/projects/?": httpx.Response(200, json={"result": {"projects": [
        {"seo_url": "shopify/lotado", "bid_stats": {"bid_count": 45}},
        {"seo_url": "shopify/cedo", "bid_stats": {"bid_count": 3}},
    ]}})})

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    dados = json.loads((tmp_path / "estado" / "checkpoint.json").read_text(encoding="utf-8"))
    assert lotado.link not in {o["link"] for o in dados["oportunidades"]}
    assert cedo.link in {o["link"] for o in dados["oportunidades"]}
    assert "- 1 do Freelancer.com ficaram de fora porque já tinham 30 propostas ou mais ([cacada].max_propostas_freelancer)." in relatorio


# -- 03: 99Freelas logada -------------------------------------------------------------------------------

NOVENTA = "https://www.99freelas.com.br/project/"


def _da_99freelas(slug: str, detalhes: str = "") -> Oportunidade:
    return Oportunidade.nova(tipo=FREELA, fonte="99Freelas", titulo=slug, link=f"{NOVENTA}{slug}", detalhes=detalhes)


def _logado_na_99freelas(paginas: dict[str, str]) -> NavegadorLogadoFake:
    return NavegadorLogadoFake({PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: fixture("99freelas_listagem.html")} | paginas)


def test_99freelas_logada_tira_cancelado_escolhido_e_ja_proposto_e_diz_o_custo():
    oportunidades = [
        _da_99freelas("aberto-1", "Propostas: 12"),
        _da_99freelas("cancelado-2"),
        _da_99freelas("escolhido-3"),
        _da_99freelas("ja-propos-4"),
        _da_99freelas("exclusivo-5"),
        _da_99freelas("nao-abre-6", "Propostas: 1"),
    ]
    fake = _logado_na_99freelas(
        {
            f"{NOVENTA}aberto-1": fixture("99freelas_aberto.html"),
            f"{NOVENTA}bid/aberto-1": fixture("99freelas_bid.html"),
            f"{NOVENTA}cancelado-2": fixture("99freelas_cancelado.html"),
            f"{NOVENTA}escolhido-3": fixture("99freelas_escolhido.html"),
            f"{NOVENTA}ja-propos-4": fixture("99freelas_ja_propos.html"),
            f"{NOVENTA}exclusivo-5": fixture("99freelas_aberto.html"),
            f"{NOVENTA}bid/exclusivo-5": fixture("99freelas_bid_exclusivo.html"),
        }
    )

    filtrado = conferir_99freelas(oportunidades, rede=_rede({}), sessao=fake.abrir(), dormir=lambda _s: None)

    assert [o.titulo for o in filtrado.ficam] == ["aberto-1", "exclusivo-5", "nao-abre-6"]
    assert filtrado.ficam[0].detalhes == "99Freelas: custa 1 conexão; sobram 15 | Propostas: 12"
    assert filtrado.ficam[1].detalhes.startswith("Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina")
    assert filtrado.ficam[2].detalhes == "Propostas: 1"
    assert (filtrado.fechadas, filtrado.ja_propostas, filtrado.conexoes) == (2, 1, 15)
    assert custo_em_conexoes(filtrado.ficam[0]) == 1 and custo_em_conexoes(filtrado.ficam[2]) is None


def test_sem_login_na_99freelas_fica_a_conferencia_publica():
    fake = NavegadorLogadoFake({PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: fixture("99freelas_deslogado.html")})
    rede = _rede({"/project/cancelado-2": httpx.Response(200, text=fixture("99freelas_cancelado.html"))})

    filtrado = conferir_99freelas([_da_99freelas("cancelado-2")], rede=rede, sessao=fake.abrir(), dormir=lambda _s: None)

    assert filtrado.ficam == () and filtrado.fechadas == 1
    assert fake.visitadas == [PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]]


def test_a_caçada_logada_conta_os_ja_propostos_e_as_conexoes(configuracao: Configuracao, tmp_path: Path):
    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["99Freelas · web"] = (_da_99freelas("ja-propos-4"), _da_99freelas("aberto-1"))
        return coleta

    portas = portas_fake()
    portas.coletar = coletar
    portas.rede = _rede({})
    portas.navegador_logado = _logado_na_99freelas(
        {
            f"{NOVENTA}aberto-1": fixture("99freelas_aberto.html"),
            f"{NOVENTA}bid/aberto-1": fixture("99freelas_bid.html"),
            f"{NOVENTA}ja-propos-4": fixture("99freelas_ja_propos.html"),
        }
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "- 1 da 99Freelas ficaram de fora porque você já mandou proposta neles." in relatorio
    assert "- 99Freelas: 15 conexões no estoque (visto logado)." in relatorio


# -- 04: VintePila e freelancer.com.br ------------------------------------------------------------------

VINTEPILA_1 = "https://www.vintepila.com.br/trabalhos-freelance/?page=1"
FANPAGE = "https://www.vintepila.com.br/trabalhos-freelance/cadastrar-fanpage-no-gerenciador-de-anuncios-e-instagram-na-fan-page"
DIAGRAMACAO = "https://www.vintepila.com.br/trabalhos-freelance/profissional-diagramacao-de-uma-revista-de-medicina"


def test_vintepila_sem_servico_ativo_fica_de_fora_inteira_com_o_aviso():
    fake = NavegadorLogadoFake({VINTEPILA_1: fixture("vintepila_listagem.html"), FANPAGE: fixture("vintepila_inelegivel_0de5.html")})

    coleta = coletar_vintepila(fake.abrir(), ["anúncios"])

    assert coleta.oportunidades == ()
    assert coleta.aviso == AVISO_DA_VINTEPILA_SEM_SERVICO
    assert "https://www.vintepila.com.br/trabalhos-freelance/?page=2" in fake.visitadas, "a página que falta encerra a listagem"


def test_vintepila_com_servico_traz_o_que_casa_e_ainda_aceita_candidato():
    sem_aviso = fixture("vintepila_inelegivel_0de5.html").replace("pelo menos um serviço ativo", "")
    fake = NavegadorLogadoFake({VINTEPILA_1: fixture("vintepila_listagem.html"), FANPAGE: sem_aviso})

    coleta = coletar_vintepila(fake.abrir(), ["anúncios", "logotipo"])

    assert [o.link for o in coleta.oportunidades] == [FANPAGE]
    assert coleta.oportunidades[0].fonte == "VintePila (logado)"
    assert coleta.cheios >= 1 and not coleta.aviso


def test_freelancer_com_br_pago_sai_e_o_freelancer_com_fica():
    br = Oportunidade.nova(tipo=FREELA, fonte="Web", titulo="NFe", link="https://freelancer.com.br/projetos/outro/outro/emissor-nfe-6ENKC270")
    com = _do_freelancer("python/x")

    filtrado = barrar_pagas([br, com], ["freelancer.com.br"])

    assert filtrado.ficam == (com,) and filtrado.pagas == 1
    assert barrar_pagas([br], []).ficam == (br,)


def test_as_buscas_web_deixam_os_sites_cobertos_pelo_login_e_os_pagos():
    criterios = Criterios(procuro="", sobre_mim="", fontes=())

    antes = {f.nome: f.argumento for f in criterios_de_freelas(criterios, ()).fontes}
    logado = {
        f.nome: f.argumento
        for f in criterios_de_freelas(
            criterios, (), cobertos=[NOVENTA_E_NOVE, VINTEPILA], plataformas_pagas=["freelancer.com.br"]
        ).fontes
    }
    sem_workana = {f.nome for f in criterios_de_freelas(criterios, ("workana",), cobertos=[NOVENTA_E_NOVE]).fontes}

    assert "Web · Workana e 99Freelas recentes" in antes and "Web · Workana e 99Freelas recentes" not in logado
    assert logado["Web · Workana recentes"].startswith("projetos de preço fechado na Workana (nada da 99Freelas")
    fora = logado["Web · freelas no Brasil fora das plataformas grandes"]
    assert "Não traga nada da VintePila (ela é lida logada à parte) nem do freelancer.com.br" in fora
    assert "VintePila" not in antes["Web · freelas no Brasil fora das plataformas grandes"]
    assert not any("recentes" in nome for nome in sem_workana), "sem Workana e com a 99Freelas logada, a linha sai"


def test_a_caçada_de_freelas_logada_diz_o_login_e_nao_manda_o_explorador_na_99freelas(
    configuracao: Configuracao, tmp_path: Path
):
    portas = portas_fake()
    portas.rede = _rede({})
    pedidos: list[str] = []
    original = portas.explorador.explorar

    def explorar(pedido, perfil, procuro, sobre_mim, ja_vistas, nome):
        pedidos.append(nome)
        return original(pedido, perfil, procuro, sobre_mim, ja_vistas, nome)

    portas.explorador.explorar = explorar
    portas.navegador_logado = NavegadorLogadoFake(
        {
            PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: fixture("99freelas_listagem.html"),
            PAGINAS_DE_CONFERENCIA[VINTEPILA]: fixture("vintepila_listagem.html"),
            PAGINAS_DE_CONFERENCIA[FREELANCER_BR]: fixture("freelancerbr_listagem_deslogado.html"),
            VINTEPILA_1: fixture("vintepila_listagem.html"),
            DIAGRAMACAO: fixture("vintepila_inelegivel.html"),
        }
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert f"- VintePila: nada de lá nesta caçada — {AVISO_DA_VINTEPILA_SEM_SERVICO}." in relatorio
    assert pedidos and not any("99Freelas recentes" in nome for nome in pedidos)
    dados = json.loads((tmp_path / "estado" / "checkpoint.json").read_text(encoding="utf-8"))
    assert dados["logins"] == {FREELANCER: DESLOGADO, NOVENTA_E_NOVE: LOGADO, VINTEPILA: LOGADO}
    assert PAGINAS_DE_CONFERENCIA[FREELANCER_BR] not in portas.navegador_logado.visitadas, "site pago nem é aberto"
    assert "- freelancer.com.br: responder lá pede plano pago ([cacada].plataformas_pagas); nada de lá" in relatorio
    assert "- VintePila (logado): 0 lida(s)" not in relatorio, "sem serviço ativo a VintePila não é lida"
    assert dados["cobertos"] == [NOVENTA_E_NOVE, VINTEPILA]


def test_sem_login_as_buscas_web_voltam_a_99freelas(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    pedidos: list[str] = []
    original = portas.explorador.explorar
    portas.explorador.explorar = lambda pedido, *resto: pedidos.append(resto[-1]) or original(pedido, *resto)
    portas.navegador_logado = NavegadorLogadoFake({}, motivo=PERFIL_EM_USO)

    cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", dormir=lambda _s: None)

    assert "Web · 99Freelas recentes" in pedidos


# -- 05: orçamento de lances e conexões -----------------------------------------------------------------


def _estado_com_tentar_a_sorte(configuracao: Configuracao, tmp_path: Path, pares, **checkpoint) -> _Estado:
    ponto = Checkpoint.abrir(tmp_path / "estado")
    ponto.guardar(
        oportunidades=[o.para_json() for o, _ in pares],
        vereditos=[Veredito(o.id, TENTAR_A_SORTE, "médio", encaixe).para_json() for o, encaixe in pares],
        **checkpoint,
    )
    return _Estado(configuracao, tmp_path, Criterios(procuro="", sobre_mim="", fontes=()), ponto, tmp_path / "estado")


def test_tentar_a_sorte_fica_no_que_os_lances_e_as_conexoes_pagam(configuracao: Configuracao, tmp_path: Path):
    pares = [
        (_do_freelancer("a/f1"), 80),
        (_do_freelancer("a/f2"), 70),
        (_do_freelancer("a/f3"), 60),
        (_da_99freelas("n1", "99Freelas: custa 2 conexões; sobram 3"), 75),
        (_da_99freelas("n2", "99Freelas: custa 2 conexões; sobram 3"), 65),
        (_da_99freelas("n3"), 55),
        (Oportunidade.nova(tipo=FREELA, fonte="Workana", titulo="w", link="https://www.workana.com/job/w"), 50),
        (Oportunidade.nova(tipo=FREELA, fonte="Workana", titulo="baixo", link="https://www.workana.com/job/b"), 39),
    ]
    estado = _estado_com_tentar_a_sorte(configuracao, tmp_path, pares, lances_freelancer=[2, 6], conexoes_99freelas=3)

    sorte = tentar_a_sorte(estado)

    assert [o.titulo for o, _ in sorte.ficam] == ["a/f1", "n1", "a/f2", "n3", "w"]
    assert {site: [o.titulo for o, _ in fora] for site, fora in sorte.sem_orcamento.items()} == {
        "Freelancer.com": ["a/f3"], "99Freelas": ["n2"]
    }
    assert [o.titulo for o, _ in sorte.abaixo] == ["baixo"] and not sorte.sem_lances


def test_sem_leitura_logada_nao_ha_corte_e_o_minimo_vem_do_config(configuracao: Configuracao, tmp_path: Path):
    pares = [(_do_freelancer("a/f1"), 80), (_da_99freelas("n1"), 45)]
    estado = _estado_com_tentar_a_sorte(replace(configuracao, cacada_encaixe_minimo_tentar=50), tmp_path, pares)

    sorte = tentar_a_sorte(estado)

    assert [o.titulo for o, _ in sorte.ficam] == ["a/f1"] and [o.titulo for o, _ in sorte.abaixo] == ["n1"]
    assert sorte.sem_orcamento == {}


def test_freelancer_sem_lances_vira_uma_linha_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    pares = [(_do_freelancer("a/f1"), 80), (_do_freelancer("a/f2"), 70), (_da_99freelas("n1"), 30)]
    estado = _estado_com_tentar_a_sorte(configuracao, tmp_path, pares, lances_freelancer=[0, 6])
    guarda = GuardaDoPlano(100, relogio=lambda: datetime(2026, 10, 14, tzinfo=UTC), dormir=lambda _s: None)

    relatorio = montar_relatorio(estado, guarda, parada="")

    secao = relatorio.split("## Tentar a sorte", 1)[1].split("## Descartadas", 1)[0]
    assert "- **Freelancer.com: sem lances este mês; 2 projetos ficaram de fora até a renovação.**" in secao
    assert "a/f1" not in secao and "_Nenhuma nesta caçada._" in secao
    assert "tentar a sorte com encaixe 30, abaixo do mínimo" in relatorio
    assert "- 1 de tentar a sorte com encaixe abaixo de 40 ficaram de fora ([cacada].encaixe_minimo_tentar)." in relatorio
    assert "tentar_a_sorte: 0" in relatorio


def test_a_chave_do_encaixe_minimo(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text('vault = "/v"\n[cacada]\nencaixe_minimo_tentar = 55\n', encoding="utf-8")
    assert carregar(arquivo).cacada_encaixe_minimo_tentar == 55
    arquivo.write_text('vault = "/v"\n', encoding="utf-8")
    assert carregar(arquivo).cacada_encaixe_minimo_tentar == 40


# -- 07: relatório e whis navegador ---------------------------------------------------------------------


def test_fontes_diz_onde_a_caçada_estava_logada(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    portas.rede = _rede({})
    portas.navegador_logado = NavegadorLogadoFake(
        {
            PAGINAS_DE_CONFERENCIA[FREELANCER]: fixture("freelancer_aberto.html"),
            PAGINAS_DE_CONFERENCIA[NOVENTA_E_NOVE]: fixture("99freelas_deslogado.html"),
        }
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    fontes = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8").split("## Fontes", 1)[1]
    assert "- Freelancer.com: logado no Chrome da caçada" in fontes
    assert "- 99Freelas: deslogado — entre de novo pelo `whis navegador`" in fontes
    assert "- VintePila: deslogado — entre de novo pelo `whis navegador`" in fontes
    assert "freelancer.com.br: deslogado" not in fontes


def test_com_o_chrome_da_caçada_aberto_fontes_pede_para_fechar(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    portas.navegador_logado = NavegadorLogadoFake({}, motivo=PERFIL_EM_USO)

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert resultado.completa
    assert "- 99Freelas: o Chrome da caçada estava aberto — feche-o para a caçada usar o login" in relatorio


def test_sem_porta_de_navegador_fontes_nao_fala_de_login(configuracao: Configuracao, tmp_path: Path):
    resultado = cacar(configuracao, portas_fake(), pasta_do_estado=tmp_path / "estado")

    assert "Chrome da caçada" not in (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")


@pytest.fixture
def chrome_aberto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[str]]:
    import subprocess

    from whis import fonte_x

    abertos: list[list[str]] = []
    monkeypatch.setattr(fonte_x, "caminho_do_chrome", lambda: tmp_path / "chrome.exe")
    monkeypatch.setattr(subprocess, "Popen", lambda argumentos, **_: abertos.append(argumentos))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return abertos


def test_whis_navegador_sem_url_abre_as_abas_dos_sites_logados(arquivo_de_configuracao: Path, chrome_aberto):
    assert main(["navegador"]) == 0

    [argumentos] = chrome_aberto
    assert argumentos[-len(PAGINAS_DE_LOGIN) :] == list(PAGINAS_DE_LOGIN)
    assert any(a.startswith("--user-data-dir=") and a.endswith("navegador-cacada") for a in argumentos)
    assert "--window-name=Chrome da caçada (Whis)" in argumentos


def test_whis_navegador_com_url_abre_so_ela(arquivo_de_configuracao: Path, chrome_aberto):
    assert main(["navegador", "https://portal.gupy.io"]) == 0

    assert chrome_aberto[0][-1] == "https://portal.gupy.io"
    assert not set(PAGINAS_DE_LOGIN) & set(chrome_aberto[0])


def test_a_vintepila_lida_logada_aparece_em_fontes(configuracao: Configuracao, tmp_path: Path):
    sem_aviso = fixture("vintepila_inelegivel_0de5.html").replace("pelo menos um serviço ativo", "")
    portas = portas_fake()
    portas.rede = _rede({})
    portas.navegador_logado = NavegadorLogadoFake(
        {
            PAGINAS_DE_CONFERENCIA[VINTEPILA]: fixture("vintepila_listagem.html"),
            VINTEPILA_1: fixture("vintepila_listagem.html"),
            DIAGRAMACAO: sem_aviso,
            FANPAGE: sem_aviso,
        }
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", dormir=lambda _s: None)

    fontes = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8").split("## Fontes", 1)[1]
    assert "- VintePila (logado): 0 lida(s)" in fontes
    assert "da VintePila ficaram de fora porque já têm todos os candidatos (5 de 5)." in fontes
