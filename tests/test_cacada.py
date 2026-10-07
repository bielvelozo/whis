"""A caçada de vagas e freelas, sem rede e sem Claude.

Os leitores das fontes são provados com páginas e JSON montados no formato que
cada fonte publica (research 02a, 02b e 08) e servidos por `httpx.MockTransport`;
a corrida inteira, com as portas fake de `fakes_da_cacada` — inclusive a pausa
da janela de 5 h e a parada da semanal, sem esperar ninguém.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from claude_agent_sdk import AssistantMessage, RateLimitEvent, RateLimitInfo, ResultMessage, TextBlock

from whis import corrida
from whis.__main__ import main
from whis.amostras import AVISO, gravar, publicar, projeto_cloudflare
from whis.cacada import (
    CAMINHO_DO_PERFIL,
    GuardaDoPlano,
    Parada,
    cacar,
    links_ja_vistos,
)
from whis.cacada_claude import (
    ErroDaCacada,
    LimiteDoPlano,
    Plano,
    TriagemClaude,
    interpretar_triagem,
    ler_plano,
)
from whis.configuracao import Configuracao, ConfiguracaoInvalida, carregar
from whis.criterios_da_cacada import (
    CAMINHO_DOS_CRITERIOS,
    MODELO_DOS_CRITERIOS,
    TIPOS_DE_FONTE,
    FonteDaCacada,
    interpretar_criterios,
)
from whis.fakes_da_cacada import TriagemFake, oportunidades_de_exemplo, portas_fake
from whis.fontes_da_cacada import (
    coletar,
    interpretar_99freelas,
    interpretar_linkedin,
    interpretar_workana,
)
from whis.oportunidades import CHANCE_BOA, DESCARTADA, FREELA, Oportunidade, id_do_link, link_canonico
from whis.palheta import NOME_DA_CACADA, Palheta, comandos_padrao, resultado_da_cacada

AGORA = datetime(2026, 10, 2, 22, 0, tzinfo=UTC)


# -- critérios ---------------------------------------------------------------------------------


def test_o_modelo_dos_criterios_le_inteiro_sem_aviso():
    criterios = interpretar_criterios(MODELO_DOS_CRITERIOS)

    assert criterios.avisos == ()
    assert {fonte.tipo for fonte in criterios.fontes} == set(TIPOS_DE_FONTE)
    assert "R$ 5.000" in criterios.procuro and "Ribeirão Preto" in criterios.procuro
    assert "Inglês (básico, intermediário, avançado, fluente)" in criterios.respostas_em_branco()


def test_fonte_de_tipo_desconhecido_vira_aviso_e_repetida_e_ignorada():
    texto = "## Fontes\n- Boa: workana it-programming\n- Ruim: indeed dev\n- Boa: remotive dev\n"

    criterios = interpretar_criterios(texto)

    assert criterios.fontes == (FonteDaCacada("Boa", "workana", "it-programming"),)
    assert len(criterios.avisos) == 2


def test_sobre_mim_respondido_nao_volta_como_pergunta():
    criterios = interpretar_criterios("## Sobre mim\n- Inglês: intermediário\n- GitHub público:\n")

    assert criterios.respostas_em_branco() == ("GitHub público",)


# -- oportunidades ------------------------------------------------------------------------------


def test_o_link_perde_o_rastreio_e_o_id_e_estavel():
    sujo = "https://Example.com/vaga/123/?utm_source=x&ref=y&fs=t&keep=1#topo"

    assert link_canonico(sujo) == "https://example.com/vaga/123?keep=1"
    assert id_do_link(sujo) == id_do_link("https://example.com/vaga/123?keep=1")


def test_a_descricao_chega_sem_html():
    oportunidade = Oportunidade.nova(
        tipo=FREELA, fonte="X", titulo="<b>Site</b>", link="https://a.b/c", descricao="<p>Um <strong>site</strong></p><script>x()</script>"
    )

    assert oportunidade.titulo == "Site"
    assert oportunidade.descricao == "Um site"


# -- os leitores das páginas ----------------------------------------------------------------------

PAGINA_DA_WORKANA = """<html><body>
<search :results-initials="{&quot;results&quot;: [
 {&quot;slug&quot;: &quot;landing-page-clinica&quot;,
  &quot;title&quot;: &quot;&lt;span title=\\&quot;Landing page para clínica odontológica em Araraquara\\&quot;&gt;Landing page para clín...&lt;/span&gt;&quot;,
  &quot;description&quot;: &quot;&lt;p&gt;Preciso de uma &lt;strong&gt;landing page&lt;/strong&gt;.&lt;/p&gt;&quot;,
  &quot;budget&quot;: &quot;R$ 500 - 1.000&quot;,
  &quot;publishedDate&quot;: &quot;Publicado: &lt;span&gt;há 2 horas&lt;/span&gt;&quot;,
  &quot;totalBids&quot;: &quot;Propostas: &lt;span&gt;4&lt;/span&gt;&quot;,
  &quot;skills&quot;: [{&quot;anchorText&quot;: &quot;HTML&quot;}, {&quot;anchorText&quot;: &quot;CSS&quot;}]},
 {&quot;title&quot;: &quot;sem slug, fica de fora&quot;}
]}"></search></body></html>"""

PAGINA_DA_99FREELAS = """<ul class="result-list">
  <li class="result-item" data-id="111">
    <h1 class="title"><a href="/project/sistema-de-agendamento-111?fs=t">Sistema de agendamento web</a></h1>
    <p class="item-text information">
      Desenvolvimento Web | Intermediário |
      Publicado: <b class="datetime" cp-datetime="1790000000000"></b> |
      Tempo restante: <b class="datetime-restante" cp-datetime="4102444800000"></b> |
      Propostas: <b>3</b>
    </p>
    <div class="item-text description">Preciso de um sistema em React … <a class="more-link" href="#">Expandir</a></div>
    <p class="habilidades"><a class="habilidade" href="#">React</a><a class="habilidade" href="#">Node.js</a></p>
  </li>
  <li class="result-item" data-id="333"><!-- sem título --></li>
</ul>"""

PAGINA_DO_LINKEDIN = """
<li><div class="base-card relative w-full base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:4012">
  <a class="base-card__full-link absolute" href="https://br.linkedin.com/jobs/view/desenvolvedor-web-at-acme-4012?position=1&amp;trk=public_jobs">
    <span class="sr-only">Desenvolvedor Web</span></a>
  <div class="base-search-card__info">
    <h3 class="base-search-card__title">
          Desenvolvedor Web Pleno
    </h3>
    <h4 class="base-search-card__subtitle"><a href="https://br.linkedin.com/company/acme">Acme</a></h4>
    <div class="base-search-card__metadata">
      <span class="job-search-card__location">São Paulo, SP</span>
      <time class="job-search-card__listdate" datetime="2026-09-30">2 days ago</time>
    </div>
  </div>
</div></li>"""


def test_workana_le_o_json_do_atributo_com_o_titulo_inteiro():
    lidas = interpretar_workana(PAGINA_DA_WORKANA, "Workana · TI")

    assert len(lidas) == 1
    projeto = lidas[0]
    assert projeto.titulo == "Landing page para clínica odontológica em Araraquara"
    assert projeto.link == "https://www.workana.com/job/landing-page-clinica"
    assert projeto.faixa == "R$ 500 - 1.000"
    assert projeto.tipo == FREELA
    assert "Propostas: 4" in projeto.detalhes and "HTML, CSS" in projeto.detalhes


def test_99freelas_le_os_itens_e_ignora_o_sem_titulo():
    lidas = interpretar_99freelas(PAGINA_DA_99FREELAS)

    assert len(lidas) == 1
    projeto = lidas[0]
    assert projeto.link == "https://www.99freelas.com.br/project/sistema-de-agendamento-111"
    assert "Propostas: 3" in projeto.detalhes and "React, Node.js" in projeto.detalhes
    assert "Expandir" not in projeto.descricao
    assert projeto.publicada.startswith("2026-09-21")


def test_linkedin_le_o_cartao_da_busca_publica():
    lidas = interpretar_linkedin(PAGINA_DO_LINKEDIN, "LinkedIn", "remoto")

    assert len(lidas) == 1
    vaga = lidas[0]
    assert vaga.titulo == "Desenvolvedor Web Pleno"
    assert vaga.empresa == "Acme"
    assert vaga.link == "https://br.linkedin.com/jobs/view/desenvolvedor-web-at-acme-4012"
    assert vaga.publicada == "2026-09-30"
    assert "nunca automática" in vaga.detalhes


def test_pagina_mudada_devolve_nada_sem_erro():
    assert interpretar_workana("<html>outra coisa</html>") == ()
    assert interpretar_99freelas("<html>outra coisa</html>") == ()
    assert interpretar_linkedin("<html>outra coisa</html>") == ()


# -- a coleta pela rede de mentira -----------------------------------------------------------------


def _rede(respostas: dict[str, httpx.Response]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        for trecho, resposta in respostas.items():
            if trecho in str(pedido.url):
                return resposta
        return httpx.Response(404)

    return httpx.MockTransport(responder)


def test_as_apis_viram_oportunidades_e_a_fonte_que_falha_nao_derruba_as_outras():
    recente = int((AGORA - timedelta(days=1)).timestamp())
    velha = int((AGORA - timedelta(days=60)).timestamp())
    rede = _rede(
        {
            "himalayas.app": httpx.Response(200, json={"jobs": [
                {"title": "Full Stack Dev", "companyName": "H", "applicationLink": "https://h.co/1", "pubDate": recente,
                 "locationRestrictions": ["Brazil"], "minSalary": 40000, "maxSalary": 60000, "currency": "USD"},
                {"title": "Velha", "applicationLink": "https://h.co/2", "pubDate": velha},
            ]}),
            "remotive.com": httpx.Response(200, json={"jobs": [
                {"title": "React Dev", "url": "https://r.co/1", "company_name": "R", "publication_date": "2026-10-01T10:00:00",
                 "candidate_required_location": "LATAM", "salary": "$4k/mo"},
            ]}),
            "remoteok.com": httpx.Response(200, json=[{"legal": "aviso"}, {"position": "Node Dev", "url": "https://ok.co/1", "epoch": recente}]),
            "jobicy.com": httpx.Response(200, json={"jobs": [{"jobTitle": "Dev", "url": "https://j.co/1", "jobGeo": "LATAM"}]}),
            "api.github.com": httpx.Response(200, json=[
                {"title": "[Remoto] Dev Front-end na X", "html_url": "https://github.com/frontendbr/vagas/issues/1",
                 "created_at": "2026-10-01T00:00:00Z", "labels": [{"name": "Remoto"}], "body": "React"},
                {"title": "PR", "html_url": "https://github.com/x/pull/2", "pull_request": {}},
            ]),
            "portal.api.gupy.io": httpx.Response(200, json={"data": [
                {"name": "Dev Full Stack", "jobUrl": "https://x.gupy.io/jobs/9", "careerPageName": "Empresa",
                 "workplaceType": "remote", "publishedDate": "2026-09-30T12:00:00.000Z"},
            ]}),
            "weworkremotely.com": httpx.Response(500),
        }
    )
    fontes = (
        FonteDaCacada("Himalayas", "himalayas", "full stack"),
        FonteDaCacada("Remotive", "remotive", "developer"),
        FonteDaCacada("RemoteOK", "remoteok", "dev"),
        FonteDaCacada("Jobicy", "jobicy", "latam"),
        FonteDaCacada("frontendbr", "github", "frontendbr/vagas"),
        FonteDaCacada("Gupy", "gupy", "full stack"),
        FonteDaCacada("WWR", "rss", "https://weworkremotely.com/feed.rss"),
        FonteDaCacada("Web", "web", "qualquer coisa"),
    )

    coleta = coletar(fontes, AGORA, rede=rede, dormir=lambda _s: None)

    assert {nome: len(lista) for nome, lista in coleta.por_fonte.items()} == {
        "Himalayas": 1, "Remotive": 1, "RemoteOK": 1, "Jobicy": 1, "frontendbr": 1, "Gupy": 1,
    }
    assert coleta.falhas == {"WWR": "HTTP 500"}
    himalayas = coleta.por_fonte["Himalayas"][0]
    assert himalayas.local == "Remoto (Brazil)" and himalayas.faixa == "USD 40.000 – 60.000 por ano"
    assert coleta.por_fonte["Gupy"][0].local == "Remoto"


def test_hn_traz_so_comentarios_de_topo_que_citam_os_termos():
    rede = _rede(
        {
            "search_by_date": httpx.Response(200, json={"hits": [{"title": "Ask HN: Who is hiring? (October 2026)", "objectID": "500"}]}),
            "story_500": httpx.Response(200, json={"hits": [
                {"objectID": "1", "parent_id": 500, "comment_text": "Acme | Full Stack | REMOTE | React<p>Details", "created_at": "2026-10-01T00:00:00Z"},
                {"objectID": "2", "parent_id": 500, "comment_text": "Beta | Java | ONSITE NYC", "created_at": "2026-10-01T00:00:00Z"},
                {"objectID": "3", "parent_id": 1, "comment_text": "remote react reply", "created_at": "2026-10-01T00:00:00Z"},
            ]}),
        }
    )

    coleta = coletar((FonteDaCacada("HN", "hn", "remote, react"),), AGORA, rede=rede)

    vagas = coleta.por_fonte["HN"]
    assert [v.empresa for v in vagas] == ["Acme"]
    assert vagas[0].link == "https://news.ycombinator.com/item?id=1"


# -- a triagem e o plano ------------------------------------------------------------------------------


def test_triagem_so_aceita_ids_recebidos_e_golpe_e_sempre_descartada():
    a, b = oportunidades_de_exemplo()[:2]
    dados = {"vereditos": [
        {"id": a.id, "classe": "chance_boa", "motivo": "ok", "encaixe": 150, "golpe": False},
        {"id": a.id, "classe": "descartada", "motivo": "repetido", "encaixe": 0, "golpe": False},
        {"id": b.id, "classe": "chance_boa", "motivo": "parece bom", "encaixe": 90, "golpe": True},
        {"id": "inventado", "classe": "chance_boa", "motivo": "x", "encaixe": 1, "golpe": False},
    ]}

    vereditos = interpretar_triagem(dados, [a, b])

    assert [(v.id, v.classe, v.encaixe) for v in vereditos] == [(a.id, CHANCE_BOA, 100), (b.id, DESCARTADA, 90)]
    assert vereditos[1].motivo.startswith("sinal de golpe")


def _evento(status: str, raw: dict, tipo: str | None = None, resets_at: int | None = None) -> RateLimitEvent:
    return RateLimitEvent(
        rate_limit_info=RateLimitInfo(status=status, rate_limit_type=tipo, resets_at=resets_at, raw=raw),
        uuid="u",
        session_id="s",
    )


def test_o_plano_le_as_duas_janelas_e_a_virada():
    plano = ler_plano(_evento("allowed", {"unifiedWindows": {
        "five_hour": {"utilization": 0.42, "resetsAt": 1790308200},
        "seven_day": {"utilization": 0.9, "resetsAt": 1790420400},
    }}))

    assert (plano.cinco_horas, plano.sete_dias) == (42, 90)
    assert plano.vira_sete_dias == datetime.fromtimestamp(1790420400, UTC)


class TriagemGravada(TriagemClaude):
    def __init__(self, mensagens) -> None:
        super().__init__()
        self._gravadas = mensagens

    async def _mensagens(self, prompt, opcoes):
        for mensagem in self._gravadas:
            yield mensagem


def _resultado(**extras) -> ResultMessage:
    campos = {
        "subtype": "success", "duration_ms": 1, "duration_api_ms": 1, "is_error": False, "num_turns": 1,
        "session_id": "s", "total_cost_usd": 0.05,
    }
    return ResultMessage(**{**campos, **extras})


def test_janela_rejeitada_vira_limite_do_plano_com_a_hora_de_voltar():
    triagem = TriagemGravada([
        _evento("rejected", {}, "five_hour", 1790308200),
        AssistantMessage(content=[TextBlock("You've hit your session limit")], model="m", error="rate_limit"),
        _resultado(is_error=True, result="You've hit your session limit"),
    ])

    with pytest.raises(LimiteDoPlano) as erro:
        triagem.triar(oportunidades_de_exemplo()[:1], portas_fake().perfil.montar("", "", ""), "", "")

    assert erro.value.tipo == "five_hour" and not erro.value.semanal
    assert erro.value.retoma_em == datetime.fromtimestamp(1790308200, UTC)


def test_sem_saida_estruturada_e_erro_da_cacada():
    triagem = TriagemGravada([_resultado(result="texto solto")])

    with pytest.raises(ErroDaCacada):
        triagem.triar(oportunidades_de_exemplo()[:1], portas_fake().perfil.montar("", "", ""), "", "")


def test_a_guarda_para_acima_do_teto_e_perto_da_virada():
    agora = lambda: AGORA  # noqa: E731
    guarda = GuardaDoPlano(95, relogio=agora, dormir=lambda _s: None)

    guarda.plano = Plano(sete_dias=80, vira_sete_dias=AGORA + timedelta(hours=10))
    guarda.conferir()
    guarda.plano = Plano(sete_dias=96, vira_sete_dias=AGORA + timedelta(hours=10))
    with pytest.raises(Parada):
        guarda.conferir()
    guarda.plano = Plano(sete_dias=10, vira_sete_dias=AGORA + timedelta(minutes=4))
    with pytest.raises(Parada):
        guarda.conferir()


def test_fora_da_vespera_o_teto_cai_para_70():
    guarda = GuardaDoPlano(95, relogio=lambda: AGORA, dormir=lambda _s: None)
    guarda.plano = Plano(sete_dias=72, vira_sete_dias=AGORA + timedelta(days=4))

    with pytest.raises(Parada, match="70%"):
        guarda.conferir()


# -- a corrida inteira com as portas fake ---------------------------------------------------------------


@pytest.fixture
def pasta_do_estado(tmp_path: Path) -> Path:
    return tmp_path / "estado"


def test_a_cacada_deixa_relatorio_pacotes_e_nunca_toca_os_criterios(configuracao: Configuracao, pasta_do_estado: Path):
    raiz = Path(configuracao.vault)
    (raiz / "cacada").mkdir(parents=True)
    (raiz / CAMINHO_DOS_CRITERIOS).write_text(MODELO_DOS_CRITERIOS + "\n<!-- meu -->\n", encoding="utf-8")

    resultado = cacar(configuracao, portas_fake(), pasta_do_estado=pasta_do_estado)

    assert resultado.completa
    assert (resultado.chances_boas, resultado.tentar_a_sorte, resultado.descartadas) == (3, 1, 2)
    relatorio = (raiz / resultado.relatorio).read_text(encoding="utf-8")
    assert "Nada foi enviado a ninguém" in relatorio
    assert "sinal de golpe" in relatorio
    assert "Mensagem pronta" in relatorio
    assert (raiz / CAMINHO_DOS_CRITERIOS).read_text(encoding="utf-8").endswith("<!-- meu -->\n")
    assert (raiz / CAMINHO_DO_PERFIL).is_file()
    pacotes = list((raiz / "cacada" / resultado.corrida).glob("*.md"))
    assert len(pacotes) == 3
    landing = next(p for p in pacotes if "landing" in p.name)
    texto = landing.read_text(encoding="utf-8")
    assert "## Proposta pronta" in texto and "```text" in texto and "## Amostra" in texto
    html = (landing.with_name(landing.stem + "-amostra") / "index.html").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex"' in html and AVISO in html


def test_a_segunda_cacada_nao_repete_o_que_ja_apareceu(configuracao: Configuracao, pasta_do_estado: Path):
    cacar(configuracao, portas_fake(), pasta_do_estado=pasta_do_estado, relogio=lambda: AGORA)

    segunda = cacar(
        configuracao, portas_fake(), pasta_do_estado=pasta_do_estado, relogio=lambda: AGORA + timedelta(hours=1)
    )

    assert segunda.chances_boas == segunda.tentar_a_sorte == segunda.descartadas == 0
    assert len(links_ja_vistos(Path(configuracao.vault))) == 6


def test_a_janela_de_5h_pausa_e_a_corrida_segue(configuracao: Configuracao, pasta_do_estado: Path):
    portas = portas_fake(limite_em=1)
    dormidas: list[float] = []

    resultado = cacar(configuracao, portas, pasta_do_estado=pasta_do_estado, dormir=dormidas.append)

    assert resultado.completa and resultado.chances_boas == 3
    assert len(dormidas) == 1 and 60 <= dormidas[0] <= 13 * 60


def test_o_limite_semanal_para_e_a_proxima_chamada_retoma(configuracao: Configuracao, pasta_do_estado: Path):
    parada = cacar(configuracao, portas_fake(limite_em=1, semanal=True), pasta_do_estado=pasta_do_estado)

    assert not parada.completa and "semanal" in parada.parada
    relatorio = (Path(configuracao.vault) / parada.relatorio).read_text(encoding="utf-8")
    assert "parou antes do fim" in relatorio

    portas = portas_fake()
    retomada = cacar(configuracao, portas, pasta_do_estado=pasta_do_estado)

    assert retomada.completa and retomada.corrida == parada.corrida
    assert portas.perfil.chamadas == 0, "o perfil já estava no checkpoint"
    assert retomada.chances_boas == 3


def test_checkpoint_velho_comeca_do_zero(configuracao: Configuracao, pasta_do_estado: Path):
    cacar(configuracao, portas_fake(limite_em=1, semanal=True), pasta_do_estado=pasta_do_estado, relogio=lambda: AGORA)
    portas = portas_fake()

    nova = cacar(configuracao, portas, pasta_do_estado=pasta_do_estado, relogio=lambda: AGORA + timedelta(days=6))

    assert portas.perfil.chamadas == 1
    assert nova.corrida != f"{AGORA:%Y-%m-%d-%H%M}"


# -- o estado da corrida ------------------------------------------------------------------------------


def test_uma_cacada_por_vez(tmp_path: Path):
    with corrida.TravaDaCacada(tmp_path):
        assert corrida.cacada_correndo(tmp_path)
        with pytest.raises(corrida.CacadaEmAndamento):
            with corrida.TravaDaCacada(tmp_path):
                pass
    assert not corrida.cacada_correndo(tmp_path)


def test_manter_acordado_pede_ao_windows_e_recusa_vira_falso():
    pedidos: list[int] = []

    assert corrida.manter_acordado(pedir=lambda f: pedidos.append(f) or 1)
    assert pedidos == [corrida.ES_CONTINUOUS | corrida.ES_SYSTEM_REQUIRED]
    assert not corrida.manter_acordado(pedir=lambda f: 0)


def test_checkpoint_terminado_nao_e_retomado(tmp_path: Path):
    checkpoint = corrida.Checkpoint.abrir(tmp_path)
    checkpoint.guardar(inicio="2026-10-02T00:00:00+00:00", etapa="triagem")
    assert corrida.Checkpoint.abrir(tmp_path).retomada
    checkpoint.terminar()
    assert not corrida.Checkpoint.abrir(tmp_path).retomada


# -- as amostras -------------------------------------------------------------------------------------


def test_publicar_sem_chaves_fica_so_no_vault(tmp_path: Path):
    arquivo = gravar(tmp_path, "a", "<html><head></head><body>x</body></html>")

    assert publicar(Configuracao(vault=tmp_path), arquivo, "a") == (
        "sem [cacada].cloudflare_token e [cacada].cloudflare_conta: a amostra ficou só no vault"
    )


def test_publicar_pelo_wrangler_devolve_o_link_neutro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("whis.amostras.shutil.which", lambda _nome: "npx")
    configuracao = Configuracao(vault=tmp_path, cacada_cloudflare_token="t", cacada_cloudflare_conta="c")
    arquivo = gravar(tmp_path, "landing", "<html><body>x</body></html>")
    comandos: list[list[str]] = []

    def executar(comando, ambiente):
        comandos.append(comando)
        assert ambiente == {"CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "c"}
        return subprocess.CompletedProcess(comando, 0, "ok", "")

    pronta = publicar(configuracao, arquivo, "landing", executar=executar, pasta=tmp_path / "estado")

    projeto = projeto_cloudflare(configuracao, tmp_path / "estado")
    assert projeto.startswith("conceitos-")
    assert pronta.url == f"https://{projeto}.pages.dev/landing/"
    assert any("deploy" in comando for comando in comandos)
    assert (tmp_path / "estado" / "amostras-no-ar" / "landing" / "index.html").is_file()


# -- a casca: config, palheta e CLI ------------------------------------------------------------------


def test_cacada_no_config_tem_padrao_e_valida(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text('vault = "/v"\n', encoding="utf-8")
    padrao = carregar(arquivo)
    assert (padrao.cacada_teto_semanal, padrao.cacada_maximo_de_pacotes, padrao.cacada_email) == (100, 20, "")

    arquivo.write_text('vault = "/v"\n[cacada]\nteto_semanal = 120\n', encoding="utf-8")
    with pytest.raises(ConfiguracaoInvalida, match="entre 1 e 100"):
        carregar(arquivo)
    arquivo.write_text('vault = "/v"\n[cacada]\ncloudflare_projeto = "Meu Projeto"\n', encoding="utf-8")
    with pytest.raises(ConfiguracaoInvalida, match="pages.dev"):
        carregar(arquivo)


def test_hunt_na_palheta_solta_a_cacada_e_some(configuracao: Configuracao):
    chamadas: list[Configuracao] = []
    comandos = comandos_padrao(
        publicacao_do_deck=lambda c: None,
        busca=lambda c: None,
        iniciar_cacada=lambda c: chamadas.append(c) or None,
    )
    avisos: list[tuple] = []
    palheta = Palheta(comandos, configuracao, avisar=lambda *a, **k: avisos.append(a) or True, iniciar_thread=lambda f: f())

    assert NOME_DA_CACADA in [comando.nome for comando in palheta.acoes()]
    palheta.despachar("hunt")

    assert chamadas == [configuracao] and avisos == []


def test_toast_da_cacada_abre_o_relatorio_e_diz_que_nada_foi_enviado():
    class R:
        chances_boas, tentar_a_sorte, descartadas = 2, 5, 40
        plano_antes, plano_depois = 30, 90
        parada, relatorio, fontes_com_falha = "", "cacada/2026-10-02-2200.md", {"Workana": "HTTP 403"}

    resultado = resultado_da_cacada(R())

    assert resultado.titulo == "A caçada terminou"
    assert resultado.nota == "cacada/2026-10-02-2200.md"
    assert "2 chances boas" in resultado.texto and "Nada foi enviado" in resultado.texto and "Workana" in resultado.texto


def test_whis_hunt_fakes_corre_inteiro_num_vault_temporario(arquivo_de_configuracao: Path, capsys, toasts):
    codigo = main(["hunt", "--fakes"])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "3 chances boas (3 com pacote)" in saida
    assert toasts == [], "--fakes não mostra toast"


# -- os adaptadores com mensagens gravadas ------------------------------------------------------------


def _gravado(classe, mensagens, *seguintes):
    roteiro = [mensagens, *seguintes]

    class Gravado(classe):
        async def _mensagens(self, prompt, opcoes):
            self.pedidos = [*getattr(self, "pedidos", []), (prompt, opcoes)]
            self.prompt, self.opcoes = prompt, opcoes
            for mensagem in roteiro[min(len(self.pedidos), len(roteiro)) - 1]:
                yield mensagem

    return Gravado()


SAIDA_DO_PREPARO = {
    "resumo": "Landing page.", "por_que_casa": "Web.", "o_que_estica": "", "alertas": "prazo\n\n- **escopo** vago",
    "preco": "R$ 700", "prazo": "7 dias", "proposta": "Olá", "plano": "1. a\n2. b", "perguntas": "",
    "como_enviar": "Workana, sem link.", "amostra_titulo": "Conceito da landing",
}


def _preparar(preparo, oportunidade):
    veredito = TriagemFake().triar([oportunidade], None, "", "")[0]
    return preparo.preparar(oportunidade, veredito, "texto", portas_fake().perfil.montar("", "", ""), "regras", "")


def test_o_preparo_le_a_saida_estruturada_e_so_o_explorador_tem_ferramenta():
    from whis.cacada_claude import TURNOS_DO_PREPARO, ExploradorClaude, PreparoClaude

    oportunidade = oportunidades_de_exemplo()[1]
    html = "<!doctype html><html><body>oi</body></html>"
    preparo = _gravado(
        PreparoClaude,
        [_resultado(structured_output=SAIDA_DO_PREPARO)],
        [AssistantMessage(content=[TextBlock(f"Segue:\n```html\n{html}\n```")], model="m"), _resultado()],
    )

    pacote = _preparar(preparo, oportunidade)

    assert pacote.id == oportunidade.id and pacote.amostra_html == html
    assert pacote.alertas == ("prazo", "**escopo** vago") and pacote.plano == ("a", "b") and pacote.perguntas == ()
    (prompt, opcoes), (prompt_da_amostra, opcoes_da_amostra) = preparo.pedidos
    assert opcoes.tools == [] and opcoes.allowed_tools == []
    assert opcoes.max_turns == TURNOS_DO_PREPARO > 2, "a saída estruturada recusada volta como turno novo"
    assert "amostra_html" not in opcoes.output_format["schema"]["properties"], "o HTML não vai dentro do JSON"
    assert "TEXTO DA PÁGINA" in prompt and "regras" in prompt
    assert opcoes_da_amostra.output_format is None and opcoes_da_amostra.tools == []
    assert "Conceito da landing" in prompt_da_amostra and "TEXTO DA PÁGINA" in prompt_da_amostra
    assert "regras" not in prompt_da_amostra, "a amostra não leva o perfil dele"

    explorador = _gravado(ExploradorClaude, [_resultado(structured_output={"oportunidades": [
        {"tipo": "freela", "titulo": "Site", "link": "https://ex.com/1", "descricao": "d", "fonte": "Contra"},
        {"tipo": "vaga", "titulo": "Sem link", "link": "javascript:alert(1)", "descricao": "d", "fonte": "x"},
    ]})])
    achadas = explorador.explorar("sites", portas_fake().perfil.montar("", "", ""), "", "", ["https://visto.com"], "Web")

    assert [o.link for o in achadas] == ["https://ex.com/1"] and achadas[0].fonte == "Web (Contra)"
    assert explorador.opcoes.tools == ["WebSearch", "WebFetch"]
    assert "https://visto.com" in explorador.prompt


def test_a_amostra_que_falha_nao_derruba_o_pacote_e_a_vaga_nao_pede_amostra():
    from whis.cacada_claude import PreparoClaude

    freela, vaga = oportunidades_de_exemplo()[1], oportunidades_de_exemplo()[0]
    caiu = _gravado(
        PreparoClaude,
        [_resultado(structured_output=SAIDA_DO_PREPARO)],
        [_resultado(is_error=True, subtype="error_during_execution", result="caiu")],
    )
    sem_html = _gravado(
        PreparoClaude,
        [_resultado(structured_output=SAIDA_DO_PREPARO)],
        [AssistantMessage(content=[TextBlock("Não consigo fazer a página.")], model="m"), _resultado()],
    )
    so_pacote = _gravado(PreparoClaude, [_resultado(structured_output={**SAIDA_DO_PREPARO, "amostra_titulo": ""})])

    for preparo in (caiu, sem_html):
        pacote = _preparar(preparo, freela)
        assert pacote.proposta == "Olá" and pacote.amostra_html == "" and len(preparo.pedidos) == 2
    assert _preparar(so_pacote, vaga).amostra_html == "" and len(so_pacote.pedidos) == 1


def test_api_key_paga_no_ambiente_e_recusada(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-paga")
    triagem = TriagemGravada([_resultado(structured_output={"vereditos": []})])

    with pytest.raises(ErroDaCacada, match="API key paga"):
        triagem.triar(oportunidades_de_exemplo()[:1], portas_fake().perfil.montar("", "", ""), "", "")


def test_as_evidencias_leem_linguagens_dependencias_e_o_diario(tmp_path: Path):
    repositorio = tmp_path / "dev" / "loja"
    (repositorio / "src").mkdir(parents=True)
    (repositorio / "src" / "App.tsx").write_text("export {}", encoding="utf-8")
    (repositorio / "package.json").write_text(json.dumps({"dependencies": {"react": "19", "next": "15"}}), encoding="utf-8")
    git = ["git", "-C", str(repositorio)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "eu@exemplo.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Eu"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "primeiro"], check=True)
    vault = tmp_path / "vault"
    (vault / "diario").mkdir(parents=True)
    (vault / "diario" / "2026-10-01.md").write_text("---\ntipo: diario\n---\n# Dia\nMigrei o checkout.", encoding="utf-8")
    from whis.evidencias import montar_evidencias

    texto = montar_evidencias(Configuracao(vault=vault, git_raiz=tmp_path / "dev"), claude_code=tmp_path / "sem-claude")

    assert "TypeScript (React) 100%" in texto
    assert "react, next" in texto and "1 commit(s) dele" in texto
    assert "Migrei o checkout." in texto and "tipo: diario" not in texto


def test_do_claude_code_saem_so_contagens(tmp_path: Path):
    from whis.evidencias import _do_claude_code

    projeto = tmp_path / "C--Users-gabri-development-empresa-secreta"
    projeto.mkdir()
    linhas = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "C:/empresa/src/Checkout.tsx", "old_string": "segredo"}},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "anthropic-skills:code-review"}},
            {"type": "tool_use", "name": "mcp__linear__get_issue", "input": {"id": "FN-1"}},
        ]}},
        {"type": "user", "message": {"content": "o código do cliente X"}},
    ]
    (projeto / "sessao.jsonl").write_text("\n".join(json.dumps(l) for l in linhas), encoding="utf-8")

    texto = _do_claude_code(tmp_path)

    assert "1 sessão(ões) em 1 projeto(s)" in texto and ".tsx 1" in texto and "code-review 1" in texto and "MCP 1" in texto
    assert "empresa" not in texto and "segredo" not in texto and "cliente" not in texto and "Checkout" not in texto


def test_get_on_board_e_freelancer_pelas_apis_publicas():
    rede = _rede(
        {
            "getonbrd.com": httpx.Response(200, json={"data": [
                {"id": "dev-react-acme", "type": "job", "attributes": {
                    "title": "React Developer", "remote": True, "countries": ["Brasil"], "min_salary": 2500, "max_salary": 3500,
                    "published_at": int((AGORA - timedelta(days=2)).timestamp()), "description": "<p>React</p>",
                    "company": {"data": {"attributes": {"name": "Acme LatAm"}}}},
                 "links": {"public_url": "https://www.getonbrd.com/jobs/programming/dev-react-acme"}},
            ]}),
            "freelancer.com": httpx.Response(200, json={"result": {"projects": [
                {"title": "Landing page", "seo_url": "website-design/landing-page-1", "type": "fixed",
                 "budget": {"minimum": 100, "maximum": 300}, "currency": {"code": "USD"}, "bid_stats": {"bid_count": 12},
                 "time_submitted": int((AGORA - timedelta(hours=5)).timestamp()), "preview_description": "Landing"},
                {"title": "Suporte por hora", "seo_url": "x/hora", "type": "hourly"},
            ]}}),
        }
    )
    fontes = (FonteDaCacada("GoB", "getonbrd", "react"), FonteDaCacada("Freelancer", "freelancer", "website"))

    coleta = coletar(fontes, AGORA, rede=rede)

    vaga = coleta.por_fonte["GoB"][0]
    assert (vaga.empresa, vaga.local, vaga.faixa) == ("Acme LatAm", "Remoto (Brasil)", "USD 2.500 – 3.500 por mês")
    [projeto] = coleta.por_fonte["Freelancer"]
    assert projeto.link == "https://www.freelancer.com/projects/website-design/landing-page-1"
    assert projeto.faixa == "USD 100 – 300 por projeto" and projeto.detalhes == "Propostas: 12"
