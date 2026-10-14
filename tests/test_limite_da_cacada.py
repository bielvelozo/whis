"""O limite da caçada: fora da véspera da virada do plano, ela para no tempo ou no plano gasto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from whis import cacada as _cacada
from whis.__main__ import main
from whis.cacada import GuardaDoPlano, LimiteBatido, LimiteDaCacada, ResultadoDaCacada, cacar
from whis.cacada_claude import Plano
from whis.configuracao import Configuracao, ConfiguracaoInvalida, carregar
from whis.corrida import Checkpoint, guardar_virada
from whis.fakes_da_cacada import portas_fake
from whis.freelas_rapidos import FONTES_DE_FREELA_RAPIDO

AGORA = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
LONGE = AGORA + timedelta(days=3, hours=22)
PERTO = AGORA + timedelta(hours=20)
AUTOMATICO = LimiteDaCacada(minutos=90, plano=15, automatico=True)


def _plano_em(portas, plano: Plano) -> None:
    for porta in portas.todas():
        porta.ultimo_plano = plano


def _relatorio(configuracao: Configuracao, resultado) -> str:
    return (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")


def test_o_padrao_vem_do_config_e_qualquer_opcao_desliga_o_automatico(configuracao: Configuracao):
    assert (configuracao.cacada_limite_minutos, configuracao.cacada_limite_plano) == (90, 15)
    assert LimiteDaCacada.escolher(configuracao) == AUTOMATICO
    assert LimiteDaCacada.escolher(configuracao, minutos=30) == LimiteDaCacada(30, 15)
    assert LimiteDaCacada.escolher(configuracao, plano=0) == LimiteDaCacada(90, 0)
    assert LimiteDaCacada.escolher(configuracao, minutos=30, sem_limite=True) == LimiteDaCacada()
    assert not LimiteDaCacada().algum


def test_as_chaves_aceitam_zero_e_recusam_fora_da_faixa(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text('vault = "/v"\n[cacada]\nlimite_minutos = 0\nlimite_plano = 0\n', encoding="utf-8")
    assert (carregar(arquivo).cacada_limite_minutos, carregar(arquivo).cacada_limite_plano) == (0, 0)

    arquivo.write_text('vault = "/v"\n[cacada]\nlimite_plano = 101\n', encoding="utf-8")
    with pytest.raises(ConfiguracaoInvalida, match="limite_plano"):
        carregar(arquivo)


def test_automatico_perto_da_virada_vai_sem_limite():
    relogio = [AGORA]
    guarda = GuardaDoPlano(100, relogio=lambda: relogio[0], dormir=lambda _s: None, limite=AUTOMATICO, virada_conhecida=PERTO)
    guarda.primeiro = Plano(sete_dias=10)
    guarda.plano = Plano(sete_dias=60, vira_sete_dias=PERTO)
    relogio[0] += timedelta(hours=5)

    guarda.conferir()

    assert not guarda.limitada()


def test_automatico_longe_da_virada_para_no_tempo():
    relogio = [AGORA]
    guarda = GuardaDoPlano(100, relogio=lambda: relogio[0], dormir=lambda _s: None, limite=AUTOMATICO, virada_conhecida=LONGE)
    relogio[0] += timedelta(minutes=89)
    guarda.conferir()

    relogio[0] += timedelta(minutes=2)
    with pytest.raises(LimiteBatido, match="correu 91 min"):
        guarda.conferir()
    assert guarda.limitada() and "tempo" in guarda.limite_batido


def test_sem_virada_guardada_o_automatico_decide_pelo_primeiro_plano_e_nao_muda_mais():
    relogio = [AGORA]
    guarda = GuardaDoPlano(100, relogio=lambda: relogio[0], dormir=lambda _s: None, limite=AUTOMATICO)
    assert guarda.limitada(), "sem saber da virada, o limite vale"

    guarda.plano = Plano(sete_dias=40, vira_sete_dias=PERTO)
    assert not guarda.limitada()
    guarda.plano = Plano(sete_dias=0, vira_sete_dias=PERTO + timedelta(days=7))
    relogio[0] += timedelta(hours=3)
    assert not guarda.limitada(), "a decisão é uma só por corrida"


def test_o_limite_de_plano_conta_os_pontos_gastos_nesta_corrida():
    guarda = GuardaDoPlano(100, relogio=lambda: AGORA, dormir=lambda _s: None, limite=LimiteDaCacada(plano=15))
    guarda.primeiro = Plano(sete_dias=20, vira_sete_dias=LONGE)
    guarda.plano = Plano(sete_dias=34, vira_sete_dias=LONGE)
    guarda.conferir()

    guarda.plano = Plano(sete_dias=35, vira_sete_dias=LONGE)
    with pytest.raises(LimiteBatido, match="gastou 15 pontos do plano semanal, de 20% a 35%"):
        guarda.conferir()


def test_a_caçada_para_no_tempo_entre_chamadas_escreve_o_relatorio_e_fica_retomavel(
    configuracao: Configuracao, tmp_path: Path
):
    pasta = tmp_path / "estado"
    guardar_virada(pasta, LONGE - timedelta(days=7))
    relogio = [AGORA]
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=10, sete_dias=20, vira_sete_dias=LONGE))
    original = portas.triagem.triar

    def triagem_demorada(*argumentos):
        relogio[0] += timedelta(minutes=95)
        return original(*argumentos)

    portas.triagem.triar = triagem_demorada

    resultado = cacar(configuracao, portas, pasta_do_estado=pasta, relogio=lambda: relogio[0], limite=AUTOMATICO)

    assert resultado.parada.startswith("o limite de tempo desta caçada bateu: correu 95 min")
    assert resultado.com_limite and not resultado.completa
    assert portas.triagem.chamadas == 1 and portas.preparo.chamadas == 0, "a chamada em curso termina; nada novo começa"
    relatorio = _relatorio(configuracao, resultado)
    assert "> [!warning] A caçada parou no limite desta corrida" in relatorio
    assert "> o limite de tempo desta caçada bateu: correu 95 min (o limite é 90 min)." in relatorio
    assert "- Limite desta corrida: 90 min ou 15 pontos do plano semanal (a semana do plano não vira" in relatorio
    assert Checkpoint.abrir(pasta).retomada, "parar no limite deixa a corrida para continuar"


def test_a_caçada_para_no_plano_gasto(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=10, sete_dias=20, vira_sete_dias=LONGE))
    original_explorar = portas.explorador.explorar

    def explorar_caro(*argumentos):
        portas.explorador.ultimo_plano = Plano(cinco_horas=50, sete_dias=26, vira_sete_dias=LONGE)
        return original_explorar(*argumentos)

    portas.explorador.explorar = explorar_caro

    resultado = cacar(
        configuracao, portas, pasta_do_estado=tmp_path / "estado", relogio=lambda: AGORA, limite=LimiteDaCacada(0, 5)
    )

    assert "o limite de plano desta caçada bateu: gastou 6 pontos" in resultado.parada
    assert portas.triagem.chamadas == 0
    assert "> [!warning] A caçada parou no limite desta corrida" in _relatorio(configuracao, resultado)


def test_sem_limite_a_caçada_corre_como_antes(configuracao: Configuracao, tmp_path: Path):
    relogio = [AGORA]
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=10, sete_dias=20, vira_sete_dias=LONGE))
    original = portas.triagem.triar

    def triagem_demorada(*argumentos):
        relogio[0] += timedelta(minutes=95)
        return original(*argumentos)

    portas.triagem.triar = triagem_demorada

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", relogio=lambda: relogio[0], limite=LimiteDaCacada())

    assert resultado.completa and not resultado.com_limite
    assert "Limite desta corrida" not in _relatorio(configuracao, resultado)


def test_no_modo_freelas_com_limite_ela_nao_atravessa_a_virada(configuracao: Configuracao, tmp_path: Path):
    agora = datetime(2026, 10, 10, 7, 58, tzinfo=UTC)
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=30, sete_dias=90, vira_sete_dias=agora + timedelta(minutes=2)))
    dormidas: list[float] = []

    resultado = cacar(
        configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas",
        relogio=lambda: agora, dormir=dormidas.append, limite=LimiteDaCacada(minutos=600),
    )

    assert resultado.parada and "virar" in resultado.parada
    assert dormidas == []


def test_no_modo_freelas_o_extra_para_no_limite_de_tempo_e_a_corrida_termina(configuracao: Configuracao, tmp_path: Path):
    relogio = [AGORA]
    portas = portas_fake()
    _plano_em(portas, Plano(cinco_horas=10, sete_dias=20, vira_sete_dias=LONGE))
    original = portas.explorador.explorar

    def explorar_demorado(*argumentos):
        relogio[0] += timedelta(minutes=10)
        return original(*argumentos)

    portas.explorador.explorar = explorar_demorado
    linhas_web = sum(f.tipo == "web" for f in FONTES_DE_FREELA_RAPIDO)
    minutos = linhas_web * 10 + 15

    resultado = cacar(
        configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas",
        relogio=lambda: relogio[0], limite=LimiteDaCacada(minutos=minutos),
    )

    assert resultado.completa and not resultado.sobrou_plano
    assert resultado.limite_batido.startswith("o limite de tempo desta caçada bateu")
    assert linhas_web < portas.explorador.chamadas < 2 * linhas_web
    relatorio = _relatorio(configuracao, resultado)
    assert "> [!info] O extra parou no limite desta corrida" in relatorio


# -- a linha de comando ---------------------------------------------------------------------------------


@pytest.fixture
def cacadas(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    chamadas: list[dict] = []

    def cacar_fake(configuracao, portas, **opcoes):
        chamadas.append(opcoes)
        limite = opcoes.get("limite") or LimiteDaCacada()
        return ResultadoDaCacada(relatorio="cacada/x.md", corrida="x", sobrou_plano=True, com_limite=limite.algum)

    monkeypatch.setattr(_cacada, "cacar", cacar_fake)
    return chamadas


@pytest.mark.parametrize(
    ("opcoes", "esperado"),
    [
        ([], LimiteDaCacada(90, 15, automatico=True)),
        (["--limite-minutos", "30"], LimiteDaCacada(30, 15)),
        (["--limite-plano", "0"], LimiteDaCacada(90, 0)),
        (["--limite-minutos", "45", "--limite-plano", "5"], LimiteDaCacada(45, 5)),
        (["--sem-limite"], LimiteDaCacada()),
    ],
)
def test_as_opcoes_do_hunt_escolhem_o_limite(arquivo_de_configuracao: Path, cacadas, opcoes, esperado):
    assert main(["hunt", "--fakes", *opcoes]) == 0

    assert cacadas[0]["limite"] == esperado


def test_sem_limite_junto_de_limite_e_erro_de_uso(arquivo_de_configuracao: Path, cacadas, capsys):
    assert main(["hunt", "--fakes", "--sem-limite", "--limite-minutos", "10"]) == 2
    assert cacadas == []


def test_limite_de_plano_acima_de_100_e_recusado(arquivo_de_configuracao: Path, cacadas, capsys):
    with pytest.raises(SystemExit) as saida:
        main(["hunt", "--limite-plano", "120"])
    assert saida.value.code == 2


def test_freelas_com_limite_nao_emenda_a_caçada_de_vagas(arquivo_de_configuracao: Path, cacadas):
    main(["hunt", "--fakes", "--freelas", "--limite-minutos", "30"])
    assert len(cacadas) == 1

    cacadas.clear()
    main(["hunt", "--fakes", "--freelas", "--sem-limite"])
    assert len(cacadas) == 2, "sem limite e com plano sobrando, emenda como antes"
