"""As fontes ao vivo como ferramentas do agente, pelos coletores que já existem.

O que se prova aqui é a promessa da camada: nenhum caminho novo até as APIs.
Os coletores entram como fakes pela porta `PortaFonte` — ou, no caso do Slack,
como o coletor de verdade com HTTP falso, para a blocklist ser provada pela
ausência da requisição e não pela ausência do resultado. O filtro de exclusão,
a janela, o termo e a origem própria de cada evento são o comportamento que o
modelo enxerga no texto devolvido.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from fixtures.busca import configuracao_da_busca, habitar_vault
from whis import __main__ as cli
from whis import fonte_slack
from whis.busca_claude import (
    PROMPT_DAS_FONTES_AO_VIVO,
    BuscaClaude,
    FerramentasDoVault,
    ferramentas_permitidas,
    montar_opcoes,
)
from whis.configuracao import VARIAVEL_DE_AMBIENTE, carregar
from whis.fakes import FonteFake
from whis.ferramentas import Ferramentas
from whis.fontes import ErroDeFonte, Evento
from whis.fontes_ao_vivo import (
    HORAS_MAXIMAS,
    NOME_DO_SERVIDOR,
    FontesAoVivo,
    nome_da_ferramenta,
    origem_do_evento,
)
from test_fonte_slack import HISTORICOS, JANELA, TOKEN_FALSO, montar_resposta, responder_padrao

FUSO = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 9, 4, 15, 0, tzinfo=FUSO)


def ha(horas: float) -> datetime:
    return AGORA - timedelta(hours=horas)


COMMIT = Evento(
    fonte="git",
    momento=ha(1),
    titulo="`a1b2c3d` Corrige o calculo de frete no checkout",
    referencia="loja",
    pessoas=("Gabriel",),
)
COMMIT_DE_ONTEM = Evento(
    fonte="git",
    momento=ha(30),
    titulo="`0ff1ce0` Fecha a camada 01 do diario",
    referencia="whis",
    pessoas=("Gabriel",),
)
ISSUE = Evento(
    fonte="linear",
    momento=ha(2),
    titulo="FN-1610 Validar o link coringa — movida para Done",
    detalhe="Subiu em produção; falta acompanhar o gráfico de erros.",
    referencia="Plataforma",
    url="https://linear.app/exemplo/issue/FN-1610",
    pessoas=("Gabriel", "Ana"),
)
MENSAGEM = Evento(
    fonte="slack",
    momento=ha(0.5),
    titulo="Ana Prado",
    detalhe="A retenção de 180 dias ficou aprovada, pode seguir.",
    referencia="#plataforma",
    url="https://segundo-cerebro.slack.com/archives/C0PLATAFORMA/p1",
    pessoas=("Ana Prado",),
)
MENSAGEM_DE_TERAPIA = Evento(
    fonte="slack",
    momento=ha(0.25),
    titulo="Joana",
    detalhe="a sessão de terapia ficou para quinta",
    referencia="DM com Joana",
    pessoas=("Joana",),
)


def chamar(ferramenta, args: dict) -> dict:
    return asyncio.run(ferramenta.handler(args))


def texto_de(ferramenta, args: dict) -> str:
    return chamar(ferramenta, args)["content"][0]["text"]


@pytest.fixture
def fontes() -> FontesAoVivo:
    return FontesAoVivo(
        [
            FonteFake("git", (COMMIT, COMMIT_DE_ONTEM)),
            FonteFake("linear", (ISSUE,)),
            FonteFake("slack", (MENSAGEM, MENSAGEM_DE_TERAPIA)),
        ],
        relogio=lambda: AGORA,
    )


def ferramenta(fontes: FontesAoVivo, nome: str):
    return next(tool for tool in fontes.tools() if tool.name == nome_da_ferramenta(nome))


# -- Fonte desligada não vira ferramenta -------------------------------------


def test_sem_fonte_ligada_nao_ha_ferramenta_nem_servidor():
    nenhuma = FontesAoVivo([])

    assert nenhuma.tools() == []
    assert nenhuma.servidor() is None
    assert nenhuma.nomes_permitidos() == []


def test_uma_ferramenta_por_fonte_ligada_com_o_nome_do_servidor(fontes: FontesAoVivo):
    assert [tool.name for tool in fontes.tools()] == [
        "consultar_git",
        "consultar_linear",
        "consultar_slack",
    ]
    assert fontes.nomes_permitidos() == [
        f"mcp__{NOME_DO_SERVIDOR}__consultar_git",
        f"mcp__{NOME_DO_SERVIDOR}__consultar_linear",
        f"mcp__{NOME_DO_SERVIDOR}__consultar_slack",
    ]
    assert fontes.servidor() is not None


# -- O que o modelo recebe ----------------------------------------------------


def test_consultar_devolve_os_eventos_das_ultimas_horas_com_origem_propria(fontes):
    texto = texto_de(ferramenta(fontes, "git"), {})

    assert "git:loja@a1b2c3d" in texto
    assert "Corrige o calculo de frete" in texto
    assert "pessoas: Gabriel" in texto
    assert "nas últimas 24h" in texto


def test_a_janela_recorta_pelas_horas_pedidas(fontes):
    assert "0ff1ce0" not in texto_de(ferramenta(fontes, "git"), {"horas": 24})
    assert "0ff1ce0" in texto_de(ferramenta(fontes, "git"), {"horas": 48})


def test_horas_alem_do_maximo_sao_encolhidas(fontes):
    texto = texto_de(ferramenta(fontes, "git"), {"horas": 10_000})

    assert f"nas últimas {HORAS_MAXIMAS}h" in texto


def test_o_mais_recente_vem_primeiro_e_o_limite_corta(fontes):
    texto = texto_de(ferramenta(fontes, "git"), {"horas": 48, "limite": 1})

    assert "a1b2c3d" in texto
    assert "0ff1ce0" not in texto
    assert "(de 2;" in texto


def test_o_termo_filtra_sem_acento_nem_maiusculas(fontes):
    com = texto_de(ferramenta(fontes, "slack"), {"termo": "RETENCAO aprovada"})
    sem = texto_de(ferramenta(fontes, "slack"), {"termo": "rollback"})

    assert "slack:#plataforma" in com
    assert "terapia" not in com
    assert sem.startswith("Nada no slack")


def test_issue_do_linear_sai_com_identificador_detalhe_e_link(fontes):
    texto = texto_de(ferramenta(fontes, "linear"), {})

    assert "linear:FN-1610" in texto
    assert "Subiu em produção" in texto
    assert "link: https://linear.app/exemplo/issue/FN-1610" in texto


def test_nada_na_janela_diz_isso_sem_ser_erro(fontes):
    resultado = chamar(ferramenta(fontes, "linear"), {"horas": 1})

    assert resultado["content"][0]["text"].startswith("Nada no linear nas últimas 1h")
    assert not resultado.get("is_error")


def test_as_chamadas_sao_contadas(fontes):
    texto_de(ferramenta(fontes, "git"), {})
    texto_de(ferramenta(fontes, "slack"), {"termo": "x"})

    assert fontes.chamadas == 2


@pytest.mark.parametrize(
    ("evento", "origem"),
    [
        (COMMIT, "git:loja@a1b2c3d"),
        (Evento(fonte="git", momento=AGORA, titulo="sem hash", referencia="loja"), "git:loja"),
        (Evento(fonte="git", momento=AGORA, titulo="`abc1234` x"), "git:abc1234"),
        (ISSUE, "linear:FN-1610"),
        (Evento(fonte="linear", momento=AGORA, titulo="sem id", referencia="Plataforma"), "linear:Plataforma"),
        (MENSAGEM, "slack:#plataforma"),
        (Evento(fonte="slack", momento=AGORA, titulo="x"), "slack:conversa"),
    ],
)
def test_a_origem_nunca_e_um_caminho_do_vault(evento: Evento, origem: str):
    assert origem_do_evento(evento) == origem
    assert not origem.endswith(".md")


# -- As réguas continuam valendo ---------------------------------------------


def test_o_filtro_de_exclusao_vale_na_consulta_ao_vivo():
    fontes = FontesAoVivo(
        [FonteFake("slack", (MENSAGEM, MENSAGEM_DE_TERAPIA))],
        excluir=("terapia",),
        relogio=lambda: AGORA,
    )

    texto = texto_de(ferramenta(fontes, "slack"), {})

    assert "slack:#plataforma" in texto
    assert "terapia" not in texto
    assert "Joana" not in texto


def test_o_filtro_de_exclusao_conta_no_log(caplog: pytest.LogCaptureFixture):
    fontes = FontesAoVivo(
        [FonteFake("slack", (MENSAGEM, MENSAGEM_DE_TERAPIA))],
        excluir=("terapia",),
        relogio=lambda: AGORA,
    )

    with caplog.at_level("INFO", logger="whis.fontes_ao_vivo"):
        texto_de(ferramenta(fontes, "slack"), {})

    assert "1 removido(s) pelo filtro de exclusão" in caplog.text


def test_a_blocklist_do_slack_vale_de_graca_pelo_coletor_de_verdade(tmp_path: Path):
    """O coletor real, pela fábrica real, com HTTP falso: a conversa bloqueada não é sequer pedida."""
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        "\n".join(
            [
                'vault = "V"',
                'gravacoes = "G"',
                "",
                "[slack]",
                f'user_token = "{TOKEN_FALSO}"',
                'conversas_excluidas = ["#terapia"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    registro: list[httpx.Request] = []

    def responder(requisicao: httpx.Request) -> httpx.Response:
        registro.append(requisicao)
        metodo = requisicao.url.path.rsplit("/", 1)[-1]
        return montar_resposta(
            responder_padrao(metodo, dict(requisicao.url.params), HISTORICOS), requisicao
        )

    coletor = fonte_slack.de_configuracao(
        carregar(arquivo), cliente=httpx.Client(transport=httpx.MockTransport(responder))
    )
    fontes = FontesAoVivo([coletor], relogio=lambda: JANELA.fim)

    texto = texto_de(ferramenta(fontes, "slack"), {"horas": 24})

    assert "slack:#plataforma" in texto
    assert [r for r in registro if "C0TERAPIA" in str(r.url)] == []
    assert "#terapia" not in texto


def test_fonte_que_falha_vira_texto_util_e_nao_excecao():
    fontes = FontesAoVivo(
        [FonteFake("slack", erro=ErroDeFonte("token do Slack recusado (invalid_auth)."))],
        relogio=lambda: AGORA,
    )

    resultado = chamar(ferramenta(fontes, "slack"), {})

    texto = resultado["content"][0]["text"]
    assert resultado["is_error"] is True
    assert "não pôde ser lida agora" in texto
    assert "invalid_auth" in texto
    assert "Responda com o que o vault tem" in texto


# -- A costura com o adaptador -----------------------------------------------


@pytest.fixture
def vault(tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path) -> FerramentasDoVault:
    habitar_vault(caminho_do_vault)
    return FerramentasDoVault(
        Ferramentas(configuracao_da_busca(tmp_path, caminho_do_vault, caminho_das_gravacoes))
    )


def test_as_fontes_entram_nas_opcoes_como_segundo_servidor(vault, fontes):
    opcoes = montar_opcoes(vault, fontes, modelo=None, maximo_de_turnos=10)

    assert set(opcoes.mcp_servers) == {"vault", NOME_DO_SERVIDOR}
    assert opcoes.allowed_tools == ferramentas_permitidas() + fontes.nomes_permitidos()
    assert opcoes.tools == []
    assert PROMPT_DAS_FONTES_AO_VIVO in opcoes.system_prompt


def test_sem_fonte_ligada_as_opcoes_so_tem_o_vault_e_o_prompt_nao_fala_delas(vault):
    for fontes in (None, FontesAoVivo([])):
        opcoes = montar_opcoes(vault, fontes, modelo=None, maximo_de_turnos=10)

        assert list(opcoes.mcp_servers) == ["vault"]
        assert opcoes.allowed_tools == ferramentas_permitidas()
        assert "consultar_" not in opcoes.system_prompt


def test_o_prompt_manda_procurar_no_vault_antes_e_citar_com_a_origem_propria():
    assert "DEPOIS de procurar no vault" in PROMPT_DAS_FONTES_AO_VIVO
    assert "A nota é gratuita; a API não" in PROMPT_DAS_FONTES_AO_VIVO
    for origem in ("linear:FN-1610", "slack:#dev-codereview", "git:whis@a1b2c3d"):
        assert origem in PROMPT_DAS_FONTES_AO_VIVO
    assert "nunca com um caminho de nota" in PROMPT_DAS_FONTES_AO_VIVO


def test_montar_busca_liga_so_as_fontes_configuradas(
    tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, monkeypatch
):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        "\n".join(
            [
                f'vault = "{caminho_do_vault.as_posix()}"',
                f'gravacoes = "{caminho_das_gravacoes.as_posix()}"',
                "",
                "[privacidade]",
                'excluir = ["terapia"]',
                "",
                "[git]",
                f'raiz = "{tmp_path.as_posix()}"',
                "",
                "[slack]",
                f'user_token = "{TOKEN_FALSO}"',
                'conversas_excluidas = ["#terapia"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))

    busca = cli.montar_busca(carregar(arquivo))

    assert isinstance(busca, BuscaClaude)
    assert busca.fontes_ao_vivo is not None
    assert [fonte.nome for fonte in busca.fontes_ao_vivo.fontes] == ["git", "slack"]
    assert busca.fontes_ao_vivo.excluir == ("terapia",)
    assert busca.fontes_ao_vivo.nomes_permitidos() == [
        f"mcp__{NOME_DO_SERVIDOR}__consultar_git",
        f"mcp__{NOME_DO_SERVIDOR}__consultar_slack",
    ]


def test_montar_busca_sem_fonte_nenhuma_responde_so_com_o_vault(
    tmp_path: Path, caminho_do_vault: Path, caminho_das_gravacoes: Path, caplog
):
    configuracao = configuracao_da_busca(tmp_path, caminho_do_vault, caminho_das_gravacoes)

    with caplog.at_level("INFO", logger="whis"):
        busca = cli.montar_busca(configuracao)

    assert isinstance(busca, BuscaClaude)
    assert busca.fontes_ao_vivo is not None
    assert busca.fontes_ao_vivo.tools() == []
    assert "só com o vault" in caplog.text
