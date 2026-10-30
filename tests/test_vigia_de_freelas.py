"""A vigia de freelas: o projeto novo do nicho vira toast nas primeiras horas, sem Claude."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis import automacao
from whis.__main__ import main
from whis.configuracao import PLATAFORMAS_PAGAS, Configuracao
from whis.oportunidades import FREELA, Oportunidade
from whis.vigia_de_freelas import vigiar

AGORA = datetime(2026, 10, 17, 14, 0, tzinfo=timezone(timedelta(hours=-3)))


def _freela(titulo: str, link: str, *, horas: float = 1, faixa: str = "R$ 300 - 600", detalhes: str = "Propostas: 3") -> Oportunidade:
    return Oportunidade.nova(
        tipo=FREELA, fonte="99Freelas", titulo=titulo, link=link, faixa=faixa,
        publicada=AGORA - timedelta(hours=horas), descricao="Loja Shopify com tema Dawn.", detalhes=detalhes,
    )


TEMA = _freela("Ajuste no tema Shopify", "https://www.99freelas.com.br/project/tema-1")
CHECKOUT = _freela(
    "Checkout Shopify com frete", "https://www.freelancer.com/projects/shopify/checkout-2", faixa="USD 100 - 250",
    detalhes="Propostas: 3 | Média: 140.00 USD",
)
VELHO = _freela("Seção nova no tema Shopify", "https://www.99freelas.com.br/project/secao-3", horas=40)
REACT = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas", titulo="Painel em React", link="https://www.99freelas.com.br/project/painel-4",
    publicada=AGORA - timedelta(hours=1), descricao="Dashboard com gráficos.",
)


def _rodar(estado: Path, oportunidades, nicho: str = "shopify", celular: list[str] | None = None):
    avisos: list[tuple[str, str, tuple[str, str] | None]] = []

    def avisar(titulo, texto, *, botao=None):
        avisos.append((titulo, texto, botao))
        return True

    no_celular = (lambda texto: celular.append(texto) or True) if celular is not None else None
    rodada = vigiar(nicho, ler=lambda _nicho: list(oportunidades), estado=estado, avisar=avisar, celular=no_celular, agora=AGORA)
    return rodada, avisos


def test_o_projeto_novo_do_freelancer_vai_tambem_para_o_celular_e_o_da_99freelas_nao(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    celular: list[str] = []

    _, avisos = _rodar(estado, [TEMA, CHECKOUT], celular=celular)

    assert len(avisos) == 2
    [mensagem] = celular
    assert mensagem.splitlines()[0] == "Freela de Shopify novo no Freelancer.com"
    assert "Checkout Shopify com frete" in mensagem and "USD 100 - 250" in mensagem and "Propostas: 3" in mensagem
    assert "Média: 140.00 USD" in mensagem
    assert mensagem.splitlines()[-1] == CHECKOUT.link


def test_no_celular_nao_ha_corte_de_poucos_por_rodada(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    novos = [
        _freela(f"Tema Shopify {n}", f"https://www.freelancer.com/projects/shopify/tema-{n}", faixa="USD 30 - 250") for n in range(5)
    ]
    celular: list[str] = []

    _rodar(estado, novos, celular=celular)

    assert len(celular) == 5


def test_a_primeira_rodada_so_guarda_o_que_ja_esta_la(tmp_path: Path):
    estado = tmp_path / "vigia.json"

    rodada, avisos = _rodar(estado, [TEMA, REACT])

    assert avisos == [] and rodada.avisados == () and rodada.guardados == 1
    assert TEMA.link in json.loads(estado.read_text(encoding="utf-8"))


def test_avisa_so_o_projeto_novo_e_recente_do_nicho_com_o_link(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    _rodar(estado, [TEMA])

    rodada, avisos = _rodar(estado, [TEMA, CHECKOUT, VELHO, REACT])

    assert [o.link for o in rodada.avisados] == [CHECKOUT.link]
    [(titulo, texto, botao)] = avisos
    assert titulo == "Freela de Shopify novo: Checkout Shopify com frete"
    assert "USD 100 - 250" in texto and "Propostas: 3" in texto and "Freelancer.com" in texto
    assert botao == ("Abrir o projeto", CHECKOUT.link)
    _, de_novo = _rodar(estado, [TEMA, CHECKOUT])
    assert de_novo == []


def test_o_exclusivo_da_99freelas_diz_quando_abre(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    exclusivo = _freela(
        "Loja Shopify do zero", "https://www.99freelas.com.br/project/loja-5",
        detalhes="Projeto exclusivo para assinantes da 99Freelas: abre para quem não assina em 18/10 às 09:10 | Propostas: 0",
    )

    _, [(_, texto, _)] = _rodar(estado, [exclusivo])

    assert "abre para quem não assina em 18/10 às 09:10" in texto


def test_muitos_novos_viram_poucos_toasts(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    novos = [_freela(f"Tema Shopify {n}", f"https://www.99freelas.com.br/project/tema-{n}0") for n in range(6)]

    rodada, avisos = _rodar(estado, novos)

    assert len(rodada.avisados) == 6
    assert len(avisos) == 4
    assert avisos[-1][0] == "Mais 3 freelas de Shopify novos"
    assert "Tema Shopify 3" in avisos[-1][1] and "Tema Shopify 5" in avisos[-1][1]


def test_sem_nicho_a_vigia_nao_roda(arquivo_de_configuracao: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["vigia-freelas"]) != 0
    assert "[cacada].nicho_freela" in capsys.readouterr().out


def test_no_modo_de_teste_avisa_um_projeto_falso(
    arquivo_de_configuracao: Path, toasts, mensagens_no_celular, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert main(["vigia-freelas", "--fakes"]) == 0

    [ensaio] = mensagens_no_celular
    assert ensaio.startswith("Ensaio: esta proposta sairia agora na 99Freelas") and "(teste)" in ensaio

    [(titulo, texto, botao)] = toasts
    assert titulo.startswith("Freela de Shopify novo:") and "(teste)" in titulo
    assert botao is not None and botao[1].startswith("https://")
    assert not (tmp_path / "local" / "whis" / "cacada" / "vigia-de-freelas.json").exists()


def test_whis_windows_liga_e_desliga_a_vigia_de_freelas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    chamadas: list[str] = []
    monkeypatch.setattr(automacao, "instalar_inicializacao", lambda: Path("Whis.lnk"))
    monkeypatch.setattr(automacao, "remover_inicializacao", lambda: None)
    monkeypatch.setattr(automacao, "agendar_vigia_de_freelas", lambda configuracao: chamadas.append("agendar") or "Whis-Vigia-Freelas")
    monkeypatch.setattr(automacao, "desagendar_vigia_de_freelas", lambda: chamadas.append("desagendar") or True)
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{tmp_path.as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n', encoding="utf-8")

    assert main(["windows", "--vigia-freelas", "--config", str(arquivo)]) == 0
    assert "Vigia de freelas agendada como 'Whis-Vigia-Freelas': todo dia às 07:00, 08:00, 09:00" in capsys.readouterr().out
    assert main(["windows", "--remover", "--vigia-freelas"]) == 0
    assert "Tarefa 'Whis-Vigia-Freelas' removida do Agendador." in capsys.readouterr().out
    assert chamadas == ["agendar", "desagendar"]


def test_windows_vigia_freelas_agenda_a_tarefa_nos_horarios(tmp_path: Path):
    comandos: list[list[str]] = []

    def executar(comando):
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 0, "", "")

    configuracao = Configuracao(
        vault=tmp_path, origem=tmp_path / "config.toml", cacada_horarios_da_vigia_de_freelas=("08:00", "12:30")
    )
    nome = automacao.agendar_vigia_de_freelas(configuracao, executar=executar)

    texto = " ".join(comandos[-1])
    assert nome == "Whis-Vigia-Freelas" != automacao.NOME_DA_TAREFA_DO_VIGIA
    assert "vigia-freelas --agendada" in texto and "Daily=08:00,Daily=12:30" in texto


def _config_da_vigia(tmp_path: Path, extra: str = "") -> Path:
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{(tmp_path / "vault").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n{extra}', encoding="utf-8")
    return arquivo


def test_com_o_envio_desligado_a_vigia_nao_chama_a_proposta_automatica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import propostas_auto, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA,))
    monkeypatch.setattr(propostas_auto, "rodar", lambda *_a, **_k: pytest.fail("a proposta automática rodou desligada"))

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path))]) == 0


def test_no_ensaio_a_vigia_passa_a_mesma_leitura_para_a_proposta_automatica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import propostas_auto, vigia_de_freelas

    chamadas: list[dict] = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA, REACT))
    monkeypatch.setattr(propostas_auto, "rodar", lambda lidas, **opcoes: chamadas.append({"lidas": lidas, **opcoes}) or propostas_auto.Rodada())

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ensaio"\n'))]) == 0

    [chamada] = chamadas
    assert chamada["lidas"] == (TEMA, REACT) and chamada["modo"] == "ensaio"
    assert "nenhum projeto novo da 99Freelas passou nas travas" in capsys.readouterr().out


def test_falha_da_proposta_automatica_nao_derruba_a_vigia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import propostas_auto, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA,))

    def quebrar(*_a, **_k):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(propostas_auto, "rodar", quebrar)

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ensaio"\n'))]) == 3


def test_com_o_toque_do_celular_no_chrome_a_proposta_fica_para_a_proxima_hora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import propostas_auto, vigia_de_freelas
    from whis.corrida import pasta_da_cacada
    from whis.instancia import Trava

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA,))
    monkeypatch.setattr(propostas_auto, "rodar", lambda *_a, **_k: pytest.fail("a proposta automática rodou com o Chrome ocupado"))
    toque = Trava(pasta_da_cacada() / propostas_auto.NOME_DA_TRAVA).adquirir()
    try:
        assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'propostas_auto = "ligado"\n'))]) == 0
    finally:
        toque.liberar()

    assert "o envio pelo celular está usando o Chrome da caçada" in capsys.readouterr().out


def test_a_vigia_prepara_o_email_do_dia_das_agencias_e_a_falha_nao_derruba(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import agencias_email, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA,))
    chamadas: list[dict] = []

    def preparar(vault, **opcoes):
        chamadas.append(opcoes)
        return [agencias_email.Preparado("contato@exemplo.com.br", "Estúdio Exemplo", "cacada/agencias-emails/estudio-exemplo.md")]

    monkeypatch.setattr(agencias_email, "preparar", preparar)

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, "agencias_por_dia = 2\n"))]) == 0

    [opcoes] = chamadas
    assert opcoes["por_dia"] == 2 and opcoes["estado"] == agencias_email.caminho_do_estado()
    assert "Estúdio Exemplo" in capsys.readouterr().out

    def quebrar(vault, **opcoes):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(agencias_email, "preparar", quebrar)
    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path))]) == 3


def test_sem_agencias_por_dia_a_vigia_nem_chama_o_email(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import agencias_email, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (TEMA,))
    monkeypatch.setattr(agencias_email, "preparar", lambda *_a, **_k: pytest.fail("o e-mail das agências rodou desligado"))

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, "agencias_por_dia = 0\n"))]) == 0


# -- o Job Listings da Shopify Community e o Freelancer.com lotado ----------------------------------

VAGA_DO_FORUM = Oportunidade.nova(
    tipo=FREELA, fonte="Shopify Community", titulo="Shopify Expert Developer – Ongoing Overflow Work",
    link="https://community.shopify.com/t/shopify-expert-developer-ongoing-overflow-work/659089",
    publicada=AGORA - timedelta(hours=2),
    descricao="I'm a CRO specialist looking for a developer for OS 2.0 sections, Functions and metafields.",
    detalhes="Respostas: 0",
)


def test_a_vaga_nova_do_job_listings_vai_ao_celular_com_as_regras_do_forum(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    celular: list[str] = []
    sem_shopify_no_texto = Oportunidade.nova(
        tipo=FREELA, fonte="Shopify Community", titulo="[HIRING] Technical Digital Marketer",
        link="https://community.shopify.com/t/hiring-technical-digital-marketer/652438",
        publicada=AGORA - timedelta(hours=3), descricao="Part-time, remote, US hours.",
    )

    rodada, avisos = _rodar(estado, [VAGA_DO_FORUM, sem_shopify_no_texto], celular=celular)

    assert [o.link for o in rodada.avisados] == [VAGA_DO_FORUM.link, sem_shopify_no_texto.link]
    assert len(avisos) == 2 and "Shopify Community" in avisos[0][1]
    primeira = celular[0].splitlines()
    assert primeira[0] == "Vaga nova no Job Listings da Shopify Community"
    assert primeira[1] == VAGA_DO_FORUM.titulo and "Functions and metafields" in celular[0]
    assert VAGA_DO_FORUM.link in primeira
    assert "sem oferecer serviço" in celular[0] and "DM" in celular[0]


def test_o_freelancer_com_propostas_demais_nao_vai_ao_celular_nem_vira_toast(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    lotado = _freela("Shopify theme fix", "https://www.freelancer.com/projects/shopify/fix-9", faixa="USD 30 - 250", detalhes="Propostas: 30")
    quase = _freela("Shopify app setup", "https://www.freelancer.com/projects/shopify/app-8", faixa="USD 30 - 250", detalhes="Propostas: 29")
    sem_contagem = _freela("Shopify speed", "https://www.freelancer.com/projects/shopify/speed-7", faixa="USD 30 - 250", detalhes="")
    celular: list[str] = []

    avisos: list = []
    rodada = vigiar(
        "shopify", ler=lambda _nicho: [lotado, quase, sem_contagem, TEMA], estado=estado,
        avisar=lambda titulo, texto, *, botao=None: avisos.append(titulo) or True,
        celular=lambda texto: celular.append(texto) or True, agora=AGORA, max_propostas_freelancer=30,
    )

    assert [o.link for o in rodada.avisados] == [quase.link, sem_contagem.link, TEMA.link]
    assert [m.splitlines()[1] for m in celular] == ["Shopify app setup", "Shopify speed"]
    assert len(avisos) == 3
    assert lotado.link in json.loads(estado.read_text(encoding="utf-8"))


def test_sem_lances_no_freelancer_o_projeto_de_la_nao_vai_ao_celular_nem_vira_toast(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    celular: list[str] = []
    avisos: list = []

    rodada = vigiar(
        "shopify", ler=lambda _nicho: [CHECKOUT, TEMA], estado=estado,
        avisar=lambda titulo, texto, *, botao=None: avisos.append(titulo) or True,
        celular=lambda texto: celular.append(texto) or True, agora=AGORA, sem_lances_no_freelancer=True,
    )

    assert [o.link for o in rodada.avisados] == [TEMA.link]
    assert celular == [] and len(avisos) == 1
    assert CHECKOUT.link in json.loads(estado.read_text(encoding="utf-8"))


def test_sem_limite_de_propostas_o_freelancer_lotado_tambem_avisa(tmp_path: Path):
    estado = tmp_path / "vigia.json"
    estado.write_text("{}", encoding="utf-8")
    lotado = _freela("Shopify theme fix", "https://www.freelancer.com/projects/shopify/fix-9", detalhes="Propostas: 90")
    celular: list[str] = []

    vigiar(
        "shopify", ler=lambda _nicho: [lotado], estado=estado, avisar=lambda *_a, **_k: True,
        celular=lambda texto: celular.append(texto) or True, agora=AGORA, max_propostas_freelancer=0,
    )

    assert len(celular) == 1


def test_o_job_listings_e_lido_pela_api_do_forum_sem_o_fixado_e_o_fechado():
    import httpx

    from whis.criterios_da_cacada import FonteDaCacada
    from whis.fontes_da_cacada import coletar

    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        return httpx.Response(200, json={"topic_list": {"topics": [
            {"id": 651715, "slug": "job-posting-guidelines", "title": "Job posting guidelines", "pinned": True, "closed": True,
             "created_at": "2026-10-15T15:30:51.819Z", "excerpt": "Growing your team", "posts_count": 2},
            {"id": 690032, "slug": "hiring-bark-uk-online-shopify-seo", "title": "[HIRING] Bark UK Online - Shopify SEO",
             "pinned": False, "closed": False, "visible": True, "created_at": "2026-10-17T11:55:41.668Z",
             "excerpt": "Job Title: UK-Based Shopify SEO Specialist &ndash; landscaping &hellip;", "posts_count": 3},
            {"id": 659089, "slug": "shopify-expert-developer-ongoing-overflow-work", "title": "Shopify Expert Developer",
             "pinned": False, "closed": True, "created_at": "2026-10-16T06:43:52.578Z", "excerpt": "overflow", "posts_count": 8},
        ]}})

    coleta = coletar(
        (FonteDaCacada("Shopify Community", "shopify_community", "job-listings/334"),), AGORA, rede=httpx.MockTransport(responder)
    )

    assert pedidos == ["https://community.shopify.com/c/job-listings/334.json"]
    [vaga] = coleta.por_fonte["Shopify Community"]
    assert vaga.link == "https://community.shopify.com/t/hiring-bark-uk-online-shopify-seo/690032"
    assert vaga.titulo == "[HIRING] Bark UK Online - Shopify SEO"
    assert vaga.descricao.startswith("Job Title: UK-Based Shopify SEO Specialist – landscaping")
    assert vaga.publicada.startswith("2026-10-17T11:55") and vaga.detalhes == "Respostas: 2"


def test_o_job_listings_descarta_quem_oferece_servico():
    import httpx

    from whis.criterios_da_cacada import FonteDaCacada
    from whis.fontes_da_cacada import coletar

    posts = [
        (707251, "Shopify VA | Inventory, Listings, Product Sourcing, Customer Support, Email Marketing & SEO",
         "I help Shopify store owners save time and keep their stores running smoothly. What I offer: Inventory"),
        (700605, "Looking for a Shopify Store Owner to Collaborate on a Free SEO Audit",
         "Hi Shopify community! I’m currently building my practical experience in international SEO"),
        (684547, "Shopify Development & Store Management Team Available",
         "We’re a Shopify development team with a strong portfolio of custom Shopify apps"),
        (654703, "Simple Online Remote Side Hustle Job for Women and Men",
         "Hello, I am a freelance Senior Software Engineer. I am looking for a long-term online partner"),
        (662174, "Je suis actuellement à la recherche d'une collaboration à long terme",
         "Vous avez une boutique Shopify, mais vous manquez de temps ? Je peux vous aider à gérer"),
        (659089, "Shopify Expert Developer — Ongoing Overflow Work",
         "I’m a Shopify CRO specialist and project lead working with DTC brands. I’m looking for a skilled developer"),
        (652438, "Hiring: Technical Digital Marketer",
         "We’re a new, fast growing e-commerce brand. We’re scaling our online store and email marketing"),
        (679387, "HIRING! Fractional Shopify E-commerce Manager | MAXLER",
         "MAXLER is looking for a strong Shopify E-commerce Manager. I help with onboarding."),
    ]

    def responder(_pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"topic_list": {"topics": [
            {"id": numero, "slug": f"post-{numero}", "title": titulo, "excerpt": resumo, "created_at": "2026-10-30T22:45:00Z"}
            for numero, titulo, resumo in posts
        ]}})

    coleta = coletar(
        (FonteDaCacada("Shopify Community", "shopify_community", "job-listings/334"),), AGORA, rede=httpx.MockTransport(responder)
    )

    assert [vaga.link.rsplit("/", 1)[1] for vaga in coleta.por_fonte["Shopify Community"]] == ["659089", "652438", "679387"]


def test_a_vigia_le_o_forum_da_shopify_so_no_nicho_shopify(monkeypatch: pytest.MonkeyPatch):
    from whis import fontes_da_cacada, vigia_de_freelas

    lidas: list[tuple[str, ...]] = []

    def coletar(fontes, agora, rede=None):
        lidas.append(tuple(fonte.tipo for fonte in fontes))
        return fontes_da_cacada.ColetaDaCacada()

    monkeypatch.setattr(fontes_da_cacada, "coletar", coletar)

    vigia_de_freelas.ler_do_nicho("shopify", agora=AGORA)
    vigia_de_freelas.ler_do_nicho("wordpress", agora=AGORA)

    assert lidas == [("99freelas", "freelancer", "shopify_community"), ("99freelas", "freelancer")]


def test_o_limite_de_propostas_do_freelancer_nasce_em_30_e_zero_desliga(tmp_path: Path):
    from whis.configuracao import ConfiguracaoInvalida, carregar_texto

    def ler(extra: str = ""):
        return carregar_texto(f'vault = "{tmp_path.as_posix()}"\n[cacada]\n{extra}', origem=tmp_path / "config.toml")

    assert ler().cacada_max_propostas_freelancer == 30
    assert ler("max_propostas_freelancer = 0\n").cacada_max_propostas_freelancer == 0
    with pytest.raises(ConfiguracaoInvalida, match="max_propostas_freelancer"):
        ler("max_propostas_freelancer = -1\n")


def test_a_vigia_passa_o_limite_do_config_e_roda_a_sequencia_fria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import sequencia_fria, vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    lotado = _freela("Shopify theme fix", "https://www.freelancer.com/projects/shopify/fix-9", detalhes="Propostas: 12")
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **_opcoes: (lotado,))
    chamadas: list[dict] = []

    def rodada(vault, **opcoes):
        chamadas.append(opcoes)
        return sequencia_fria.Rodada(respostas=["contato@aloftagencia.com"], preparados=["contato@econverse.com.br"])

    monkeypatch.setattr(sequencia_fria, "rodada", rodada)
    estado = tmp_path / "local" / "whis" / "cacada" / "vigia-de-freelas.json"
    estado.parent.mkdir(parents=True)
    estado.write_text("{}", encoding="utf-8")

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, "max_propostas_freelancer = 10\nagencias_por_dia = 0\n"))]) == 0

    saida = capsys.readouterr().out
    assert "Nada novo de shopify" in saida
    [opcoes] = chamadas
    assert opcoes["estado"] == sequencia_fria.caminho_do_estado() and opcoes["por_dia"] == 10
    assert "E-mail frio: contato@aloftagencia.com respondeu; a sequência parou." in saida
    assert "E-mail frio: o próximo de contato@econverse.com.br está no celular, esperando o toque." in saida

    def quebrar(vault, **opcoes):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(sequencia_fria, "rodada", quebrar)
    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, "agencias_por_dia = 0\n"))]) == 3


def test_depois_de_6_h_parada_a_vigia_le_mais_paginas_da_99freelas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import vigia_de_freelas

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    chamadas: list[dict] = []
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **opcoes: chamadas.append(opcoes) or ())
    rodada = vigia_de_freelas.caminho_da_ultima_rodada()
    rodada.parent.mkdir(parents=True)
    (rodada.parent / "vigia-de-freelas.json").write_text("{}", encoding="utf-8")
    config = str(_config_da_vigia(tmp_path, "agencias_por_dia = 0\n"))

    assert main(["vigia-freelas", "--config", config]) == 0
    vigia_de_freelas.marcar_rodada(rodada, datetime.now().astimezone() - timedelta(hours=7))
    assert main(["vigia-freelas", "--config", config]) == 0
    assert main(["vigia-freelas", "--config", config]) == 0

    pagas = {"plataformas_pagas": PLATAFORMAS_PAGAS}
    assert chamadas == [pagas, {"paginas_da_99freelas": vigia_de_freelas.PAGINAS_NA_VOLTA, **pagas}, pagas]


def test_com_a_proposta_ligada_a_vigia_le_a_99freelas_ate_a_janela_dela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import vigia_de_freelas
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    chamadas: list[dict] = []
    monkeypatch.setattr(vigia_de_freelas, "ler_do_nicho", lambda _nicho, **opcoes: chamadas.append(opcoes) or ())
    rodada = vigia_de_freelas.caminho_da_ultima_rodada()
    rodada.parent.mkdir(parents=True)
    (rodada.parent / "vigia-de-freelas.json").write_text("{}", encoding="utf-8")

    assert main(["vigia-freelas", "--config", str(_config_da_vigia(tmp_path, 'agencias_por_dia = 0\npropostas_auto = "ensaio"\n'))]) == 0

    assert chamadas[0]["paginas_da_99freelas"] == vigia_de_freelas.PAGINAS_DA_PROPOSTA
    assert chamadas[0]["ate_idade_da_99freelas"] == timedelta(hours=48)


def test_a_coleta_le_as_paginas_da_99freelas_que_pedirem():
    import httpx

    from whis import fontes_da_cacada
    from whis.criterios_da_cacada import FonteDaCacada

    listagem = (Path(__file__).parent / "fixtures" / "cacada_logada" / "99freelas_listagem.html").read_text(encoding="utf-8")
    paginas: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        paginas.append(pedido.url.params.get("page"))
        return httpx.Response(200, text=listagem)

    fonte = FonteDaCacada("99Freelas", "99freelas", "web-mobile-e-software")
    rede = httpx.MockTransport(responder)
    fontes_da_cacada.coletar((fonte,), AGORA, rede=rede, dormir=lambda _s: None, paginas_da_99freelas=6)
    seis = list(paginas)
    paginas.clear()
    fontes_da_cacada.coletar((fonte,), AGORA, rede=rede, dormir=lambda _s: None)

    assert seis == ["1", "2", "3", "4", "5", "6"] and paginas == ["1", "2"]
