"""O adaptador da DM: do envelope do Socket Mode até `Mensagem`, sem websocket.

O cliente de Socket Mode e o Web client entram injetados: o que se prova é a
tradução do evento, a confirmação do envelope (o Slack reenvia o que não é
confirmado) e as mensagens de erro em português — nunca com o token dentro.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode.request import SocketModeRequest

from second_brain.atendente import ErroDeDM, Mensagem
from second_brain.configuracao import carregar
from second_brain.dm_slack import (
    SCOPES_DO_BOT,
    DMSlack,
    de_configuracao,
    mensagem_do_evento,
)

APP_TOKEN = "xapp-EXEMPLO"
BOT_TOKEN = "xoxb-EXEMPLO"

EVENTO_DE_DM = {
    "type": "message",
    "channel": "D0GABRIEL",
    "channel_type": "im",
    "user": "U0GABRIEL",
    "text": "o que ficou decidido sobre a retenção?",
    "ts": "1788440520.000100",
}


class WebFalso:
    def __init__(self, *, erro_ao_reagir: Exception | None = None) -> None:
        self.reacoes: list[dict] = []
        self.publicadas: list[dict] = []
        self._erro_ao_reagir = erro_ao_reagir

    def auth_test(self) -> dict:
        return {"ok": True, "user_id": "U0BOT", "user": "second-brain"}

    def reactions_add(self, **campos) -> dict:
        if self._erro_ao_reagir is not None:
            raise self._erro_ao_reagir
        self.reacoes.append(campos)
        return {"ok": True}

    def chat_postMessage(self, **campos) -> dict:
        self.publicadas.append(campos)
        return {"ok": True}


class SocketFalso:
    def __init__(self) -> None:
        self.socket_mode_request_listeners: list = []
        self.confirmados: list[str] = []
        self.conectado = False
        self.fechado = False

    def connect(self) -> None:
        self.conectado = True

    def close(self) -> None:
        self.fechado = True

    def send_socket_mode_response(self, resposta) -> None:
        self.confirmados.append(resposta.envelope_id)


def envelope(payload_event: dict, *, tipo: str = "events_api", envelope_id: str = "env-1") -> SocketModeRequest:
    return SocketModeRequest(type=tipo, envelope_id=envelope_id, payload={"event": payload_event})


def erro_do_slack(codigo: str) -> SlackApiError:
    return SlackApiError(f"The request to the Slack API failed. ({codigo})", {"ok": False, "error": codigo})


@pytest.fixture
def dm() -> DMSlack:
    return DMSlack(APP_TOKEN, BOT_TOKEN, web=WebFalso(), socket=SocketFalso())


# -- A tradução do evento --------------------------------------------------------


def test_mensagem_de_dm_vira_mensagem():
    assert mensagem_do_evento(EVENTO_DE_DM) == Mensagem(
        canal="D0GABRIEL",
        usuario="U0GABRIEL",
        texto="o que ficou decidido sobre a retenção?",
        ts="1788440520.000100",
        tipo_de_canal="im",
    )


def test_mensagem_de_canal_traz_o_tipo_para_o_atendente_ignorar():
    assert mensagem_do_evento({**EVENTO_DE_DM, "channel_type": "channel"}).tipo_de_canal == "channel"


def test_mensagem_de_bot_e_marcada():
    assert mensagem_do_evento({**EVENTO_DE_DM, "bot_id": "B0OUTRO"}).do_bot is True


def test_subtipo_e_preservado():
    assert mensagem_do_evento({**EVENTO_DE_DM, "subtype": "message_changed"}).subtipo == "message_changed"


def test_evento_que_nao_e_mensagem_nao_vira_nada():
    assert mensagem_do_evento({"type": "reaction_added", "user": "U0GABRIEL"}) is None


# -- O envelope: confirmar e enfileirar -----------------------------------------


def test_iniciar_conecta_e_devolve_quem_e_o_bot(dm: DMSlack):
    assert dm.iniciar() == "U0BOT"
    assert dm._socket.conectado
    assert dm._receber in dm._socket.socket_mode_request_listeners


def test_envelope_de_mensagem_e_confirmado_e_enfileirado(dm: DMSlack):
    dm.iniciar()

    dm._receber(dm._socket, envelope(EVENTO_DE_DM))

    assert dm._socket.confirmados == ["env-1"]
    assert dm.proxima(0.01) == mensagem_do_evento(EVENTO_DE_DM)
    assert dm.proxima(0.01) is None


def test_envelope_que_nao_e_evento_e_confirmado_mas_nao_enfileirado(dm: DMSlack):
    dm.iniciar()

    dm._receber(dm._socket, envelope({}, tipo="slash_commands", envelope_id="env-2"))

    assert dm._socket.confirmados == ["env-2"]
    assert dm.proxima(0.01) is None


def test_evento_que_nao_e_mensagem_e_confirmado_mas_nao_enfileirado(dm: DMSlack):
    dm.iniciar()

    dm._receber(dm._socket, envelope({"type": "reaction_added"}, envelope_id="env-3"))

    assert dm._socket.confirmados == ["env-3"]
    assert dm.proxima(0.01) is None


def test_encerrar_fecha_o_socket(dm: DMSlack):
    dm.iniciar()

    dm.encerrar()

    assert dm._socket.fechado


# -- Reagir e responder ---------------------------------------------------------


def test_reagir_e_responder_vao_ao_canal_certo(dm: DMSlack):
    dm.iniciar()
    mensagem = mensagem_do_evento(EVENTO_DE_DM)

    dm.reagir(mensagem, "eyes")
    dm.responder(mensagem, "180 dias.")

    assert dm._web.reacoes == [{"channel": "D0GABRIEL", "name": "eyes", "timestamp": "1788440520.000100"}]
    assert dm._web.publicadas == [{"channel": "D0GABRIEL", "text": "180 dias."}]


def test_reacao_repetida_nao_e_erro():
    dm = DMSlack(APP_TOKEN, BOT_TOKEN, web=WebFalso(erro_ao_reagir=erro_do_slack("already_reacted")), socket=SocketFalso())
    dm.iniciar()

    dm.reagir(mensagem_do_evento(EVENTO_DE_DM), "eyes")


def test_scope_faltando_ao_reagir_vira_erro_de_dm_com_os_scopes():
    dm = DMSlack(APP_TOKEN, BOT_TOKEN, web=WebFalso(erro_ao_reagir=erro_do_slack("missing_scope")), socket=SocketFalso())
    dm.iniciar()

    with pytest.raises(ErroDeDM) as erro:
        dm.reagir(mensagem_do_evento(EVENTO_DE_DM), "eyes")

    for scope in SCOPES_DO_BOT:
        assert scope in str(erro.value)


def test_token_recusado_ao_iniciar_vira_erro_de_dm_sem_ecoar_o_token():
    class WebQueRecusa(WebFalso):
        def auth_test(self):
            raise erro_do_slack("invalid_auth")

    dm = DMSlack(APP_TOKEN, "xoxb-SEGREDO-QUE-NAO-PODE-VAZAR", web=WebQueRecusa(), socket=SocketFalso())

    with pytest.raises(ErroDeDM) as erro:
        dm.iniciar()

    assert "invalid_auth" in str(erro.value)
    assert "reinstale" in str(erro.value)
    assert "SEGREDO" not in str(erro.value)


# -- A fábrica -------------------------------------------------------------------


def test_de_configuracao_sem_os_tokens_diz_quais_faltam_e_onde_esta_o_roteiro(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text('vault = "V"\ngravacoes = "G"\n', encoding="utf-8")

    with pytest.raises(ErroDeDM) as erro:
        de_configuracao(carregar(arquivo))

    assert "[slack].bot_token" in str(erro.value)
    assert "[slack].app_token" in str(erro.value)
    assert "docs/smoke-atendente.md" in str(erro.value)


def test_de_configuracao_com_os_dois_tokens_monta_a_dm(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(
        f'vault = "V"\ngravacoes = "G"\n\n[slack]\nbot_token = "{BOT_TOKEN}"\napp_token = "{APP_TOKEN}"\n',
        encoding="utf-8",
    )

    assert isinstance(de_configuracao(carregar(arquivo)), DMSlack)
