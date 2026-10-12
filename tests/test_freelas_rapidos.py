"""O modo freelas rápidos da caçada: só freela, fontes de freela e a web vasculhada a fundo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from whis.configuracao import Configuracao
from whis.corrida import Checkpoint
from whis.criterios_da_cacada import Criterios, FonteDaCacada
from whis.fakes_da_cacada import coleta_fake, portas_fake
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
