"""O modo freelas rápidos da caçada: só freela, fontes de freela e a web vasculhada a fundo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from claude_agent_sdk import ResultMessage

from whis.cacada import cacar
from whis.cacada_claude import (
    SISTEMA_DO_EXPLORADOR,
    TURNOS_DO_EXPLORADOR,
    TURNOS_DO_EXPLORADOR_A_FUNDO,
    ExploradorClaude,
    LimiteDoPlano,
    Plano,
    _oportunidade_no_pedido,
)
from whis.configuracao import Configuracao, carregar
from whis.corrida import Checkpoint
from whis.criterios_da_cacada import Criterios, FonteDaCacada
from whis.fakes_da_cacada import coleta_fake, portas_fake
from whis.fontes_da_cacada import barrar_contas_recentes, barrar_organizacoes_bloqueadas, barrar_sem_conta
from whis.oportunidades import FREELA, Oportunidade
from whis.freelas_rapidos import FONTES_DE_FREELA_RAPIDO, PEDIDO_DE_FREELAS_RAPIDOS, criterios_de_freelas


def _criterios() -> Criterios:
    return Criterios(
        procuro="- Quero mais dinheiro.",
        sobre_mim="- Inglês: intermediário",
        fontes=(
            FonteDaCacada("Himalayas · full stack", "himalayas", "full stack developer"),
            FonteDaCacada("Workana · TI e programação", "workana", "it-programming"),
            FonteDaCacada("99Freelas · web", "99freelas", "web-mobile-e-software"),
            FonteDaCacada("Freelancer.com · React", "freelancer", "react"),
            FonteDaCacada("Gupy · desenvolvedor", "gupy", "desenvolvedor"),
            FonteDaCacada("Web · vagas e freelas", "web", "vagas remotas e freelas"),
        ),
    )


def test_o_modo_fica_so_com_as_fontes_de_freela_e_acrescenta_as_dele():
    criterios = criterios_de_freelas(_criterios())

    nomes = [f.nome for f in criterios.fontes]
    assert nomes[:3] == ["Workana · TI e programação", "99Freelas · web", "Freelancer.com · React"]
    assert not {"Himalayas · full stack", "Gupy · desenvolvedor", "Web · vagas e freelas"} & set(nomes)
    assert {f.nome for f in FONTES_DE_FREELA_RAPIDO} <= set(nomes)
    assert len(nomes) == len(set(nomes))
    assert sum(f.tipo == "web" for f in criterios.fontes) >= 5, "a web vasculhada por vários lados"
    assert criterios.procuro.startswith(PEDIDO_DE_FREELAS_RAPIDOS) and criterios.procuro.endswith("- Quero mais dinheiro.")
    assert criterios.sobre_mim == "- Inglês: intermediário"


def test_a_caçada_de_freelas_le_so_as_fontes_do_modo_e_diz_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    lidas: list[str] = []

    def coletar(fontes, agora, **opcoes):
        lidas.extend(f.nome for f in fontes)
        return coleta_fake(fontes, agora, **opcoes)

    portas = portas_fake()
    portas.coletar = coletar

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    assert resultado.completa
    assert lidas and all(not n.startswith(("Himalayas", "Gupy", "LinkedIn", "Remotive")) for n in lidas)
    linhas_web = sum(f.tipo == "web" for f in FONTES_DE_FREELA_RAPIDO)
    assert portas.explorador.chamadas == 4 * linhas_web, "três rodadas extras no mínimo, e para quando nada novo aparece"
    assert resultado.sobrou_plano, "o trabalho acabou antes do plano"
    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "freelas rápidos" in relatorio.splitlines()[relatorio.splitlines().index("---", 1) + 2]


def test_com_janela_sobrando_ela_capricha_nos_freelas_achados(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    assert resultado.completa
    assert portas.preparo.chamadas == 2 * resultado.chances_boas + resultado.tentar_a_sorte, (
        "o resumo e o pacote completo das chances boas, e depois o pacote das de tentar a sorte"
    )
    notas = list((Path(configuracao.vault) / "cacada" / resultado.corrida).glob("*.md"))
    assert notas and all("## Proposta pronta" in n.read_text(encoding="utf-8") for n in notas)
    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "Abrir o pacote" in relatorio and "Abrir o resumo" not in relatorio
    secao_da_sorte = relatorio.split("## Tentar a sorte", 1)[1].split("## Descartadas", 1)[0]
    assert "Abrir o pacote" in secao_da_sorte


def test_a_janela_de_5_h_batendo_no_capricho_encerra_sem_pausar(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()

    def sem_janela(*_argumentos):
        raise LimiteDoPlano("a janela bateu", tipo="five_hour", retoma_em=datetime.now(UTC) + timedelta(hours=30))

    portas.preparo.preparar = sem_janela
    dormidas: list[float] = []

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", dormir=dormidas.append)

    assert resultado.completa and not resultado.parada and dormidas == []
    notas = list((Path(configuracao.vault) / "cacada" / resultado.corrida).glob("*.md"))
    assert notas and all("## Salário" in n.read_text(encoding="utf-8") for n in notas), "ficam os resumos"


def _plano_em(portas, plano: Plano) -> None:
    for porta in portas.todas():
        porta.ultimo_plano = plano


def test_se_a_semana_vira_no_meio_do_principal_ela_espera_continua_e_nao_faz_extra(configuracao: Configuracao, tmp_path: Path):
    relogio = [datetime(2026, 10, 10, 7, 58, tzinfo=UTC)]
    virada = relogio[0] + timedelta(minutes=2)
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=30, sete_dias=90, vira_sete_dias=virada))
    dormidas: list[float] = []

    def dormir(segundos: float) -> None:
        dormidas.append(segundos)
        relogio[0] += timedelta(seconds=segundos)
        _plano_em(portas, Plano(cinco_horas=0, sete_dias=0, vira_sete_dias=virada + timedelta(days=7)))

    resultado = cacar(
        configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", relogio=lambda: relogio[0], dormir=dormir
    )

    assert resultado.completa and not resultado.parada
    assert len(dormidas) == 1, "esperou a virada uma vez e seguiu o principal"
    assert portas.preparo.chamadas == resultado.chances_boas, "depois da virada não há extra"
    assert portas.explorador.chamadas == sum(f.tipo == "web" for f in FONTES_DE_FREELA_RAPIDO)


def test_fora_do_modo_freelas_a_virada_continua_parando(configuracao: Configuracao, tmp_path: Path):
    agora = datetime(2026, 10, 10, 7, 58, tzinfo=UTC)
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=30, sete_dias=90, vira_sete_dias=agora + timedelta(minutes=2)))

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", relogio=lambda: agora, dormir=lambda _s: None)

    assert resultado.parada and "virar" in resultado.parada


def test_o_extra_para_quando_o_plano_da_semana_acaba(configuracao: Configuracao, tmp_path: Path):
    agora = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=30, sete_dias=90, vira_sete_dias=agora + timedelta(hours=6)))
    quase_no_fim = Plano(cinco_horas=30, sete_dias=100, vira_sete_dias=agora + timedelta(hours=6))
    original = portas.preparo.preparar

    def gasta_tudo(*argumentos):
        portas.preparo.ultimo_plano = quase_no_fim
        return original(*argumentos)

    portas.preparo.preparar = gasta_tudo
    dormidas: list[float] = []

    resultado = cacar(
        configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", relogio=lambda: agora, dormir=dormidas.append
    )

    assert resultado.completa and not resultado.parada and dormidas == []
    notas = list((Path(configuracao.vault) / "cacada" / resultado.corrida).glob("*.md"))
    completas = [n for n in notas if "## Proposta pronta" in n.read_text(encoding="utf-8")]
    assert len(completas) == 1, "o primeiro pacote completo gastou o resto; os outros ficam no resumo"


def test_fora_do_modo_freelas_nao_ha_extra(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado")

    assert portas.preparo.chamadas == resultado.chances_boas


def test_trocar_de_modo_comeca_uma_caçada_nova_em_vez_de_retomar(configuracao: Configuracao, tmp_path: Path):
    pasta = tmp_path / "estado"
    inacabada = Checkpoint.abrir(pasta)
    inacabada.guardar(
        inicio=datetime.now().astimezone().isoformat(timespec="seconds"), corrida="2000-01-01-0000", etapa="perfil", modo="freelas"
    )

    resultado = cacar(configuracao, portas_fake(), pasta_do_estado=pasta)

    assert resultado.corrida != "2000-01-01-0000"


def test_o_explorador_a_fundo_tem_mais_turnos():
    assert ExploradorClaude().turnos == TURNOS_DO_EXPLORADOR
    assert ExploradorClaude(a_fundo=True).turnos == TURNOS_DO_EXPLORADOR_A_FUNDO > TURNOS_DO_EXPLORADOR


def test_a_concorrencia_que_o_explorador_ve_chega_na_triagem():
    class Gravado(ExploradorClaude):
        async def _mensagens(self, prompt, opcoes):
            self.opcoes = opcoes
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s",
                total_cost_usd=0.05,
                structured_output={"oportunidades": [{
                    "tipo": "freela", "titulo": "Bounty: label do GPS", "link": "https://github.com/Expensify/App/issues/103488",
                    "descricao": "d", "fonte": "GitHub", "detalhes": "4 propostas postadas, 23 comentários, sem responsável",
                }]},
            )

    explorador = Gravado()
    [achada] = explorador.explorar("bounties", portas_fake().perfil.montar("", "", ""), "", "", [], "Web · bounties pagos")

    assert achada.detalhes == "4 propostas postadas, 23 comentários, sem responsável"
    assert _oportunidade_no_pedido(achada)["detalhes"] == achada.detalhes
    esquema = explorador.opcoes.output_format["schema"]["properties"]["oportunidades"]["items"]
    assert "detalhes" in esquema["properties"] and "detalhes" not in esquema["required"]
    assert "propostas" in SISTEMA_DO_EXPLORADOR and "comentários" in SISTEMA_DO_EXPLORADOR


def test_bounty_ja_disputado_nao_e_freela_rapido():
    regra = PEDIDO_DE_FREELAS_RAPIDOS.casefold()
    assert "bounty" in regra and "proposta" in regra and "responsável" in regra
    [bounties] = [f for f in FONTES_DE_FREELA_RAPIDO if "bount" in f.nome.casefold()]
    assert "detalhes" in bounties.argumento and "comentários" in bounties.argumento


def _web_internacional(criterios: Criterios) -> str:
    [fonte] = [f for f in criterios.fontes if f.nome.startswith("Web · Contra")]
    return fonte.argumento


def test_com_a_conta_do_peopleperhour_em_analise_a_busca_web_nao_procura_la():
    em_analise = _web_internacional(criterios_de_freelas(_criterios(), ("PeoplePerHour",)))
    aprovada = _web_internacional(criterios_de_freelas(_criterios(), ()))

    assert "then Guru;" in em_analise and "PeoplePerHour (his account there is still under review)" in em_analise
    assert "then Guru and PeoplePerHour;" in aprovada and "under review" not in aprovada


def test_o_que_vem_de_plataforma_sem_conta_sai_e_o_resto_fica():
    def freela(link: str) -> Oportunidade:
        return Oportunidade.nova(tipo=FREELA, fonte="Web", titulo=link, link=link)

    oportunidades = [
        freela("https://www.peopleperhour.com/freelance-jobs/technology/landing-123"),
        freela("https://peopleperhour.com/job/456"),
        freela("https://www.workana.com/job/site"),
        freela("https://blog.naopeopleperhour.com/post"),
    ]

    filtrado = barrar_sem_conta(oportunidades, ["peopleperhour"])

    assert [o.titulo for o in filtrado.ficam] == [oportunidades[2].link, oportunidades[3].link]
    assert filtrado.sem_conta == 2
    assert barrar_sem_conta(oportunidades, []).ficam == tuple(oportunidades)


def test_por_padrao_a_caçada_tira_peopleperhour_e_workana_e_conta_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    assert configuracao.cacada_plataformas_sem_conta == ("peopleperhour", "workana")
    pph = Oportunidade.nova(
        tipo=FREELA, fonte="Web · PPH", titulo="Fix Shopify theme", link="https://www.peopleperhour.com/freelance-jobs/x-1"
    )
    workana = Oportunidade.nova(
        tipo=FREELA, fonte="Web · BR", titulo="Site para padaria", link="https://www.workana.com/job/site-para-padaria"
    )
    lidas: list[str] = []

    def coletar(fontes, agora, **opcoes):
        lidas.extend(f.nome for f in fontes)
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["Web · PPH"] = (pph, workana)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "Fix Shopify theme" not in relatorio and "Site para padaria" not in relatorio
    assert "- 2 ficaram de fora porque vêm de site em que sua conta não está ativa (peopleperhour, workana)" in relatorio
    assert lidas and not any(n.startswith("Workana") for n in lidas)
    assert "- Workana · TI e programação: pulada, sua conta nesse site não está ativa" in relatorio
    assert "Web · 99Freelas recentes" in relatorio and "Web · Workana e 99Freelas recentes" not in relatorio


def test_a_chave_vazia_libera_o_peopleperhour(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{tmp_path.as_posix()}"\n\n[cacada]\nplataformas_sem_conta = []\n', encoding="utf-8")

    assert carregar(arquivo).cacada_plataformas_sem_conta == ()


def test_com_a_workana_sem_conta_as_buscas_web_nao_mandam_procurar_la():
    sem_conta = {f.nome: f.argumento for f in criterios_de_freelas(_criterios(), ("Workana",)).fontes}
    com_conta = {f.nome: f.argumento for f in criterios_de_freelas(_criterios(), ()).fontes}

    assert "Web · Workana e 99Freelas recentes" not in sem_conta
    assert sem_conta["Web · 99Freelas recentes"].startswith("projetos de preço fechado na 99Freelas (nada da Workana")
    fora = sem_conta["Web · freelas no Brasil fora das plataformas grandes"]
    assert "fora da 99Freelas e sem nada da Workana" in fora
    assert "Web · 99Freelas recentes" not in com_conta
    assert "na Workana e na 99Freelas" in com_conta["Web · Workana e 99Freelas recentes"]
    assert "fora da Workana e da 99Freelas (" in com_conta["Web · freelas no Brasil fora das plataformas grandes"]


def test_bounty_da_susu_labs_sai_e_o_resto_do_github_fica():
    def bounty(link: str) -> Oportunidade:
        return Oportunidade.nova(tipo=FREELA, fonte="Web · bounties pagos", titulo=link, link=link)

    oportunidades = [
        bounty("https://github.com/SUSU-LABS/dashboard/issues/12"),
        bounty("https://www.github.com/susu-labs/app/issues/3"),
        bounty("https://github.com/outra-org/SUSU-LABS/issues/1"),
        bounty("https://algora.io/SUSU-LABS-fa/bounties"),
    ]

    filtrado = barrar_organizacoes_bloqueadas(oportunidades)

    assert [o.link for o in filtrado.ficam] == [oportunidades[2].link, oportunidades[3].link]
    assert filtrado.com_malware == 2


def test_a_caçada_conta_os_bounties_da_susu_labs_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    perigoso = Oportunidade.nova(
        tipo=FREELA, fonte="Web · bounties pagos", titulo="Fix login bug ($200 bounty)",
        link="https://github.com/SUSU-LABS/painel/issues/7",
    )

    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["Web · bounties pagos"] = (perigoso,)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "Fix login bug" not in relatorio
    assert "- 1 bounties de organização com malware conhecido (SUSU-LABS) ficaram de fora." in relatorio
    [bounties] = [f for f in FONTES_DE_FREELA_RAPIDO if "bount" in f.nome.casefold()]
    assert "SUSU-LABS" in bounties.argumento


def _contas_do_github(contas: dict[str, object], pedidos: list[str]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host != "api.github.com" or not pedido.url.path.startswith("/users/"):
            return httpx.Response(404)
        login = pedido.url.path.removeprefix("/users/")
        pedidos.append(login)
        conta = contas.get(login)
        if isinstance(conta, int):
            return httpx.Response(conta)
        return httpx.Response(200, json=conta) if conta is not None else httpx.Response(404)

    return httpx.MockTransport(responder)


AGORA_DAS_CONTAS = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_bounty_de_conta_do_github_recente_ou_sem_historico_sai():
    """Recente: criada há menos de 90 dias. Sem histórico: até 2 repositórios públicos e nenhum seguidor."""

    def bounty(link: str, tipo: str = FREELA) -> Oportunidade:
        return Oportunidade.nova(tipo=tipo, fonte="Web · bounties pagos", titulo=link, link=link)

    contas = {
        "nova-org": {"created_at": "2026-09-01T00:00:00Z", "public_repos": 12, "followers": 30},
        "vazia": {"created_at": "2023-01-01T00:00:00Z", "public_repos": 2, "followers": 0},
        "expensify": {"created_at": "2011-06-01T00:00:00Z", "public_repos": 150, "followers": 900},
        "pouca-mas-seguida": {"created_at": "2020-01-01T00:00:00Z", "public_repos": 1, "followers": 4},
        "fora-do-ar": 500,
        "estranha": ["não", "é", "conta"],
    }
    oportunidades = [
        bounty("https://github.com/nova-org/app/issues/1"),
        bounty("https://github.com/nova-org/api/issues/9"),
        bounty("https://github.com/vazia/site/issues/2"),
        bounty("https://github.com/Expensify/App/issues/103488"),
        bounty("https://github.com/pouca-mas-seguida/lib/issues/3"),
        bounty("https://github.com/fora-do-ar/x/issues/4"),
        bounty("https://github.com/estranha/y/issues/5"),
        bounty("https://github.com/nova-org/vagas/issues/7", tipo="vaga"),
        bounty("https://algora.io/nova-org/bounties"),
    ]
    pedidos: list[str] = []

    filtrado = barrar_contas_recentes(oportunidades, rede=_contas_do_github(contas, pedidos), agora=AGORA_DAS_CONTAS)

    assert filtrado.conta_recente == 3
    assert [o.link for o in filtrado.ficam] == [o.link for o in oportunidades[3:]]
    assert sorted(pedidos) == sorted(["nova-org", "vazia", "expensify", "pouca-mas-seguida", "fora-do-ar", "estranha"])


def test_sem_rede_o_bounty_do_github_fica():
    def sem_rede(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    oportunidades = [Oportunidade.nova(tipo=FREELA, fonte="Web", titulo="b", link="https://github.com/nova-org/app/issues/1")]

    filtrado = barrar_contas_recentes(oportunidades, rede=httpx.MockTransport(sem_rede), agora=AGORA_DAS_CONTAS)

    assert filtrado.ficam == tuple(oportunidades) and filtrado.conta_recente == 0


def test_a_caçada_conta_os_bounties_de_conta_recente_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    isca = Oportunidade.nova(
        tipo=FREELA, fonte="Web · bounties pagos", titulo="Fix wallet connect ($300 bounty)",
        link="https://github.com/nova-org/painel/issues/7",
    )

    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["Web · bounties pagos"] = (isca,)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar
    pedidos: list[str] = []
    portas.rede = _contas_do_github(
        {"nova-org": {"created_at": datetime.now(UTC).isoformat(), "public_repos": 3, "followers": 1}}, pedidos
    )

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas", dormir=lambda _s: None)

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "Fix wallet connect" not in relatorio
    assert "- 1 bounties de conta do GitHub recente ou sem histórico ficaram de fora." in relatorio
    assert pedidos == ["nova-org"]
