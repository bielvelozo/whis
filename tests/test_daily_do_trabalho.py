"""A camada 08: o que o roteiro sabe do mundo, e o que ele cala.

Três coisas que a primeira daily real cobrou. Que projeto pessoal não seja
falado na frente do time — **mas continue no vault**, porque a memória é do
usuário. Que o processo do time chegue ao Claude em vez de ser deduzido do nome
de um estado do Linear. E que o link venha junto do que a daily cobra.

O corte trabalho/pessoal é provado pelo que o `DailyFake` guardou, do mesmo
jeito que o teste do filtro de exclusão prova que o conteúdo excluído não sai da
máquina: o fake é a única testemunha do que chegou ao serviço externo.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fixtures.leitura import corpo
from second_brain.configuracao import VARIAVEL_DE_AMBIENTE, carregar
from second_brain.daily import do_trabalho, gerar_daily
from second_brain.fakes import DailyFake, FonteFake
from second_brain.fontes import Evento
from second_brain.resumo_dia_claude import PROMPT_DA_DAILY, montar_pergunta_da_daily

TRABALHO = "flavianasser-monorepo"
PESSOAL = "renovo-hub"


def _evento(referencia: str | None, titulo: str, quando: datetime) -> Evento:
    return Evento(fonte="git", momento=quando, titulo=titulo, referencia=referencia)


@pytest.fixture
def agora() -> datetime:
    return datetime.now().astimezone()


@pytest.fixture
def configuracao_da_daily(
    tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, monkeypatch
):
    """Fábrica da configuração desta camada: referências e contexto do time."""

    def montar(*, pessoais: tuple[str, ...] = (), contexto: str = ""):
        linhas = [
            f'vault = "{caminho_do_vault.as_posix()}"',
            f'gravacoes = "{caminho_das_gravacoes.as_posix()}"',
            "",
            "[daily]",
            "referencias_pessoais = ["
            + ", ".join(f'"{r}"' for r in pessoais)
            + "]",
            f'contexto_do_time = "{contexto}"',
            "",
        ]
        arquivo = tmp_path / "config-da-daily.toml"
        arquivo.write_text("\n".join(linhas), encoding="utf-8")
        monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
        return carregar(arquivo)

    return montar


@pytest.fixture
def gerar(configuracao_da_daily, agora: datetime):
    """Roda a costura com fontes fake: `gerar(referencias=..., eventos=...)`."""

    def executar(
        *,
        pessoais: tuple[str, ...] = (),
        contexto: str = "",
        eventos: tuple[Evento, ...] = (),
        roteiro: DailyFake | None = None,
    ):
        configuracao = configuracao_da_daily(pessoais=pessoais, contexto=contexto)
        porta = roteiro if roteiro is not None else DailyFake()
        resultado = gerar_daily(
            agora,
            configuracao=configuracao,
            fontes=[FonteFake("git", eventos=eventos)],
            roteiro=porta,
        )
        return resultado, porta

    return executar


@pytest.fixture
def dois_eventos(agora: datetime) -> tuple[Evento, ...]:
    ontem = agora - timedelta(hours=3)
    return (
        _evento(TRABALHO, "`a1b2c3d` Corrige o calculo de frete", ontem),
        _evento(PESSOAL, "`d4e5f6a` Wayfinder: mapa do v1", ontem),
    )


# -- o que se fala e o que se guarda ------------------------------------------


def test_projeto_pessoal_nao_chega_ao_claude(gerar, dois_eventos):
    """A prova que interessa: o time não ouve o que é do usuário."""
    _, roteiro = gerar(pessoais=(PESSOAL,), eventos=dois_eventos)

    referencias = {evento.referencia for evento in roteiro.eventos_recebidos}
    assert referencias == {TRABALHO}


def test_o_que_foi_calado_continua_nas_listas_cruas(
    gerar, dois_eventos, caminho_do_vault: Path
):
    """A decisão que faz a daily existir: ela é o registro durável do vault."""
    resultado, _ = gerar(pessoais=(PESSOAL,), eventos=dois_eventos)

    texto = corpo(resultado.nota)
    assert "Wayfinder: mapa do v1" in texto
    assert f"### {PESSOAL}" in texto
    assert "Corrige o calculo de frete" in texto


def test_sem_configurar_nada_tudo_e_trabalho(gerar, dois_eventos):
    """O comportamento de quem nunca abriu o arquivo não pode mudar."""
    _, roteiro = gerar(eventos=dois_eventos)

    referencias = {evento.referencia for evento in roteiro.eventos_recebidos}
    assert referencias == {TRABALHO, PESSOAL}


def test_lista_so_com_espaco_nao_emudece_a_daily(gerar, dois_eventos):
    """Um padrão em branco não pode calar o roteiro inteiro em silêncio."""
    _, roteiro = gerar(pessoais=("   ",), eventos=dois_eventos)

    assert len(roteiro.eventos_recebidos) == 2


def test_evento_sem_referencia_e_falado(gerar, agora: datetime):
    """Calar o que não se sabe classificar esconderia trabalho de verdade."""
    solto = _evento(None, "`0f0f0f0` Commit sem repositório", agora - timedelta(hours=2))

    _, roteiro = gerar(pessoais=(PESSOAL,), eventos=(solto,))

    assert roteiro.eventos_recebidos == (solto,)


def test_a_referencia_casa_por_substring_sem_diferenciar_maiusculas(
    gerar, dois_eventos
):
    """`RENOVO` cala `renovo-hub`: substring, sem diferenciar maiúsculas."""
    _, roteiro = gerar(pessoais=("RENOVO",), eventos=dois_eventos)

    assert {e.referencia for e in roteiro.eventos_recebidos} == {TRABALHO}


def test_periodo_so_de_projeto_pessoal_ainda_vira_nota(
    gerar, agora: datetime, caminho_do_vault: Path
):
    """O dia existiu; o vault tem que guardá-lo mesmo sem nada a falar."""
    pessoal = _evento(PESSOAL, "`d4e5f6a` Research: push em PWA", agora - timedelta(hours=1))

    resultado, roteiro = gerar(pessoais=(PESSOAL,), eventos=(pessoal,))

    assert resultado.vazio is False
    assert resultado.nota is not None
    assert roteiro.eventos_recebidos == ()
    assert "Research: push em PWA" in corpo(resultado.nota)


def test_o_log_diz_quantos_ficaram_fora_do_roteiro(
    gerar, dois_eventos, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level("INFO", logger="second_brain.daily"):
        gerar(pessoais=(PESSOAL,), eventos=dois_eventos)

    assert "1 evento(s) de [daily].referencias_pessoais" in caplog.text
    assert "continuam nas listas cruas" in caplog.text


# -- a função do corte, direto -------------------------------------------------


def test_do_trabalho_devolve_tudo_quando_nao_ha_referencia(dois_eventos):
    falados, calados = do_trabalho(dois_eventos, ())

    assert falados == dois_eventos and calados == ()


def test_do_trabalho_separa_os_dois_lados(dois_eventos):
    falados, calados = do_trabalho(dois_eventos, (PESSOAL,))

    assert [e.referencia for e in falados] == [TRABALHO]
    assert [e.referencia for e in calados] == [PESSOAL]


# -- o diário não é tocado ----------------------------------------------------


def test_o_diario_continua_levando_o_projeto_pessoal_ao_claude(
    configuracao_do_diario, caminho_do_vault: Path
):
    """O diário é o retrato do dia DELE: calar metade seria mentir sobre o dia."""
    from datetime import date

    from second_brain.diario import gerar_diario
    from second_brain.fakes import ResumoDoDiaFake

    dia = date(2026, 9, 3)
    quando = datetime.combine(dia, datetime.min.time()).astimezone().replace(hour=10)
    resumo = ResumoDoDiaFake()

    gerar_diario(
        dia,
        configuracao=configuracao_do_diario(),
        fontes=[
            FonteFake(
                "git",
                eventos=(_evento(PESSOAL, "`d4e5f6a` Projeto pessoal", quando),),
            )
        ],
        resumo=resumo,
    )

    assert [e.referencia for e in resumo.eventos_recebidos] == [PESSOAL]


# -- o processo do time -------------------------------------------------------


def test_o_contexto_do_time_entra_na_pergunta():
    pergunta = montar_pergunta_da_daily(
        (), (), contexto_do_time="O merge é meu. Zeno aprovando já libera."
    )

    assert "Como este time funciona:" in pergunta
    assert "O merge é meu. Zeno aprovando já libera." in pergunta


def test_sem_contexto_nenhum_bloco_aparece():
    assert "Como este time funciona" not in montar_pergunta_da_daily((), ())


def test_o_adaptador_leva_o_contexto_da_configuracao():
    from second_brain.resumo_dia_claude import ResumoDoDiaClaude

    adaptador = ResumoDoDiaClaude(contexto_do_time="  O merge é meu.  ")

    assert adaptador.contexto_do_time == "O merge é meu."


def test_a_cli_monta_o_roteiro_com_o_contexto_da_configuracao(configuracao_da_daily):
    """A chave só serve se o comando de verdade a entregar ao adaptador."""
    from second_brain.__main__ import montar_roteiro_da_daily

    configuracao = configuracao_da_daily(contexto="Zeno aprovando ja libera.")

    adaptador = montar_roteiro_da_daily(configuracao)

    assert adaptador.contexto_do_time == "Zeno aprovando ja libera."


def test_a_porta_da_daily_nao_mudou_de_assinatura():
    """O corte é da costura; o adaptador não conhece trabalho nem pessoal."""
    from second_brain.portas import PortaDaily
    from second_brain.resumo_dia_claude import ResumoDoDiaClaude

    assert isinstance(ResumoDoDiaClaude(contexto_do_time="qualquer"), PortaDaily)


# -- o prompt -----------------------------------------------------------------


def test_o_prompt_nao_afirma_mais_de_quem_e_o_merge():
    """Era o que fazia a daily real inventar uma revisão humana inexistente."""
    assert "faz o merge é outra pessoa" not in PROMPT_DA_DAILY
    assert "aguardando merge" not in PROMPT_DA_DAILY


def test_o_prompt_proibe_deduzir_a_dependencia_pelo_nome_do_estado():
    assert "NÃO deduza de quem é uma etapa pelo nome do estado" in PROMPT_DA_DAILY
    assert "In Review" in PROMPT_DA_DAILY


def test_o_prompt_manda_trazer_o_link_com_rotulo_curto():
    assert "[#1636](https://...)" in PROMPT_DA_DAILY
    assert "Nunca cole a URL crua" in PROMPT_DA_DAILY
    assert "nunca invente um link" in PROMPT_DA_DAILY


def test_o_prompt_ainda_pede_item_curto_de_falar():
    """O link é exceção à marcação, não licença para escrever parágrafo."""
    assert "sessenta segundos" in PROMPT_DA_DAILY
    assert "Sem título e sem parágrafo dentro do item" in PROMPT_DA_DAILY


def test_o_prompt_manda_seguir_o_contexto_do_time():
    assert "Como este time funciona" in PROMPT_DA_DAILY
    assert "vale mais que qualquer dedução sua" in PROMPT_DA_DAILY


# -- conferir sem pagar uma chamada -------------------------------------------


def test_a_simulacao_marca_o_que_nao_seria_falado(
    configuracao_da_daily, dois_eventos, capsys: pytest.CaptureFixture, agora: datetime
):
    """É pelo `--simular` que o usuário confere a configuração de graça."""
    from second_brain.__main__ import main

    configuracao_da_daily(pessoais=(PESSOAL,))
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "second_brain.__main__.montar_fontes_da_daily",
        lambda configuracao, *, fakes=False: [FonteFake("git", eventos=dois_eventos)],
    )

    codigo = main(["daily", "--simular"])
    monkey.undo()

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "← só no vault" in saida
    assert "1 evento(s) ficam só no vault" in saida
    linha_pessoal = next(l for l in saida.splitlines() if PESSOAL in l)
    linha_trabalho = next(l for l in saida.splitlines() if TRABALHO in l)
    assert "← só no vault" in linha_pessoal
    assert "← só no vault" not in linha_trabalho


def test_sem_configurar_nada_a_simulacao_nao_marca_ninguem(
    configuracao_da_daily, dois_eventos, capsys: pytest.CaptureFixture
):
    from second_brain.__main__ import main

    configuracao_da_daily()
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "second_brain.__main__.montar_fontes_da_daily",
        lambda configuracao, *, fakes=False: [FonteFake("git", eventos=dois_eventos)],
    )

    main(["daily", "--simular"])
    monkey.undo()

    assert "só no vault" not in capsys.readouterr().out


def test_referencia_nova_e_falada_sem_ninguem_configurar_nada(gerar, agora: datetime):
    """A razão de listar o pessoal: projeto de trabalho novo entra sozinho.

    Se a lista fosse do que é do trabalho, todo projeto novo do Linear nasceria
    mudo na daily — e trabalho que sumiu é mais difícil de notar do que projeto
    pessoal que sobrou.
    """
    novo = _evento(
        "FN Projeto Que Nasceu Hoje", "FN-9001 Alguma coisa nova — criada", agora - timedelta(hours=1)
    )

    _, roteiro = gerar(pessoais=(PESSOAL,), eventos=(novo,))

    assert roteiro.eventos_recebidos == (novo,)


def test_periodo_so_pessoal_nao_gasta_chamada_e_diz_a_verdade(
    gerar, agora: datetime
):
    """Pedir roteiro sobre nada custaria dinheiro e voltaria como se fosse falha."""
    pessoal = _evento(PESSOAL, "`d4e5f6a` Research: push em PWA", agora - timedelta(hours=1))
    roteiro = DailyFake()

    resultado, _ = gerar(pessoais=(PESSOAL,), eventos=(pessoal,), roteiro=roteiro)

    assert roteiro.eventos_recebidos == (), "o Claude não devia ter sido chamado"
    assert resultado.roteiro is None
    assert "nada do trabalho neste período" in resultado.falha_do_roteiro
    texto = corpo(resultado.nota)
    assert "Research: push em PWA" in texto, "o vault guarda o período mesmo assim"
    assert "referencias_pessoais" in texto
