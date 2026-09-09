"""`[slack].so_com_mencao`: num canal barulhento, só o que cita o usuário.

Nasceu de um caso real. O canal de code review recebe uma mensagem de bot por
rodada de review de **todo mundo**, e num dia isso encheu a daily com dezenas de
linhas sobre PRs de outras pessoas. Bloquear o canal inteiro perderia junto as
mensagens que são dele.

Diferente da blocklist, esta régua age **depois** da leitura: o canal é lido
inteiro e a maior parte é descartada. Não dá para saber quem uma mensagem cita
sem lê-la, e é isso que os testes daqui fixam — inclusive que o canal continua
sendo consultado.

O harness vem de `test_fonte_slack`: mesmo workspace de fixtures, mesma janela.
"""

from __future__ import annotations

import pytest
from test_fonte_slack import DA_ANA, DO_BOT, DO_GABRIEL, JANELA, fonte

CANAL = "plataforma"


def titulos(eventos) -> list[str]:
    return [evento.titulo for evento in eventos]


def do_canal(eventos) -> list:
    return [e for e in eventos if e.referencia == f"#{CANAL}"]


# -- o que sobra e o que sai --------------------------------------------------


def test_mensagem_que_nao_me_cita_e_descartada():
    """A do bot de deploy não cita ninguém: é o ruído que motivou a chave."""
    eventos = fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    assert DO_BOT not in titulos(do_canal(eventos))


def test_mensagem_que_me_cita_sobrevive():
    eventos = fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    da_ana = [e for e in do_canal(eventos) if e.titulo == DA_ANA]
    assert da_ana, "a mensagem em que a Ana me pede review sumiu"
    assert DO_GABRIEL in da_ana[0].pessoas


def test_a_minha_propria_mensagem_sobrevive():
    """O que ele escreveu no canal é trabalho dele, e ele não se auto-cita."""
    eventos = fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    assert DO_GABRIEL in titulos(do_canal(eventos))


def test_resposta_de_thread_que_me_cita_sobrevive():
    eventos = fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    assert any("em thread" in titulo for titulo in titulos(do_canal(eventos)))


def test_sem_a_chave_nada_e_descartado():
    """O comportamento de quem não configurou nada não pode mudar."""
    com = do_canal(fonte(so_com_mencao=(CANAL,)).coletar(JANELA))
    sem = do_canal(fonte().coletar(JANELA))

    assert len(sem) > len(com), "a chave devia ter descartado alguma coisa"
    assert DO_BOT in titulos(sem)


def test_a_chave_nao_alcanca_as_outras_conversas():
    """A régua é por conversa: a DM com a Ana não é tocada."""
    eventos = fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    de_fora = [e for e in eventos if e.referencia != f"#{CANAL}"]
    assert de_fora, "as outras conversas sumiram junto"


# -- a diferença para a blocklist ---------------------------------------------


def test_o_canal_continua_sendo_consultado():
    """Não é blocklist: para saber quem a mensagem cita é preciso lê-la.

    Quem quer privacidade usa `conversas_excluidas`, que impede a requisição.
    """
    registro: list = []
    fonte(so_com_mencao=(CANAL,), registro=registro).coletar(JANELA)

    consultados = [
        req.url.params.get("channel")
        for req in registro
        if req.url.path.endswith("conversations.history")
    ]
    assert "C0PLATAFORMA" in consultados


def test_o_log_conta_o_que_foi_descartado(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO", logger="whis.fonte_slack"):
        fonte(so_com_mencao=(CANAL,)).coletar(JANELA)

    assert "so_com_mencao" in caplog.text
    assert "não citarem você" in caplog.text


def test_o_log_nao_fala_disso_quando_nada_foi_descartado(
    caplog: pytest.LogCaptureFixture
):
    with caplog.at_level("INFO", logger="whis.fonte_slack"):
        fonte().coletar(JANELA)

    assert "so_com_mencao" not in caplog.text


# -- casamento do nome da conversa --------------------------------------------


def test_casa_por_pedaco_do_nome_sem_diferenciar_maiusculas():
    eventos = fonte(so_com_mencao=("PLATAFOR",)).coletar(JANELA)

    assert DO_BOT not in titulos(do_canal(eventos))


def test_o_cerquilha_do_canal_e_ignorado_no_padrao():
    eventos = fonte(so_com_mencao=("#plataforma",)).coletar(JANELA)

    assert DO_BOT not in titulos(do_canal(eventos))


def test_padrao_em_branco_nao_liga_a_regua():
    eventos = fonte(so_com_mencao=("   ",)).coletar(JANELA)

    assert DO_BOT in titulos(do_canal(eventos))


def test_canal_que_nao_casa_fica_inteiro():
    eventos = fonte(so_com_mencao=("canal-que-nao-existe",)).coletar(JANELA)

    assert DO_BOT in titulos(do_canal(eventos))


# -- a configuração chega ao coletor ------------------------------------------


def test_a_chave_do_toml_chega_ao_coletor(tmp_path, monkeypatch):
    from whis.configuracao import VARIAVEL_DE_AMBIENTE, carregar
    from whis.fonte_slack import de_configuracao

    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        "\n".join(
            [
                f'vault = "{(tmp_path / "v").as_posix()}"',
                f'gravacoes = "{(tmp_path / "g").as_posix()}"',
                "",
                "[slack]",
                'user_token = "xoxp-EXEMPLO"',
                'so_com_mencao = ["dev-codereview"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
    configuracao = carregar(arquivo)

    assert configuracao.slack_so_com_mencao == ("dev-codereview",)
    assert de_configuracao(configuracao)._so_com_mencao == ("dev-codereview",)


def test_configuracao_sem_a_chave_continua_carregando(tmp_path):
    from whis.configuracao import carregar

    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        f'vault = "{(tmp_path / "v").as_posix()}"\n'
        f'gravacoes = "{(tmp_path / "g").as_posix()}"\n',
        encoding="utf-8",
    )

    assert carregar(arquivo).slack_so_com_mencao == ()
