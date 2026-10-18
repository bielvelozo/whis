"""O aviso no celular: a mensagem do bot do Telegram dele, sem rede de verdade."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from conftest import CELULAR_DE_VERDADE

from whis import celular
from whis.__main__ import main
from whis.configuracao import Configuracao, carregar

TOKEN = "123456:segredo-do-bot"


def _rede(respostas: dict[str, dict], pedidos: list[httpx.Request]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        metodo = pedido.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=respostas.get(metodo, {"ok": True, "result": True}))

    return httpx.MockTransport(responder)


def test_manda_a_mensagem_para_o_chat_dele_sem_previa_de_link():
    pedidos: list[httpx.Request] = []

    enviado = celular.Telegram(TOKEN, "987", rede=_rede({}, pedidos)).enviar("Proposta enviada\nhttps://www.99freelas.com.br/project/x-1")

    assert enviado is True
    [pedido] = pedidos
    assert pedido.url.path == f"/bot{TOKEN}/sendMessage"
    corpo = json.loads(pedido.content)
    assert corpo["chat_id"] == "987" and corpo["text"].startswith("Proposta enviada")
    assert corpo["link_preview_options"] == {"is_disabled": True}


def test_texto_comprido_e_cortado_no_limite_do_telegram():
    pedidos: list[httpx.Request] = []

    celular.Telegram(TOKEN, "987", rede=_rede({}, pedidos)).enviar("a" * 5000)

    assert len(json.loads(pedidos[0].content)["text"]) == celular.LIMITE_DO_TEXTO


def test_falha_de_rede_nao_derruba_e_o_token_nao_vai_ao_log(caplog: pytest.LogCaptureFixture):
    def cair(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"sem rede para {pedido.url}")

    with caplog.at_level(logging.DEBUG):
        enviado = celular.Telegram(TOKEN, "987", rede=httpx.MockTransport(cair)).enviar("oi")

    assert enviado is False
    assert "segredo-do-bot" not in caplog.text
    assert "Telegram" in caplog.text


def test_resposta_de_erro_da_api_vira_falso():
    pedidos: list[httpx.Request] = []
    rede = _rede({"sendMessage": {"ok": False, "description": "Bad Request: chat not found"}}, pedidos)

    assert celular.Telegram(TOKEN, "987", rede=rede).enviar("oi") is False


def test_o_chat_e_o_da_ultima_mensagem_privada_mandada_ao_bot():
    pedidos: list[httpx.Request] = []
    atualizacoes = {
        "ok": True,
        "result": [
            {"update_id": 1, "message": {"chat": {"id": -100, "type": "group"}, "text": "oi"}},
            {"update_id": 2, "message": {"chat": {"id": 555, "type": "private", "first_name": "Gabriel"}, "text": "/start"}},
        ],
    }

    chat = celular.Telegram(TOKEN, "", rede=_rede({"getUpdates": atualizacoes}, pedidos)).chat_da_ultima_mensagem()

    assert chat == "555"


def test_sem_token_ou_sem_chat_nao_avisa_nem_reclama(tmp_path: Path):
    configuracao = Configuracao(vault=tmp_path)

    assert CELULAR_DE_VERDADE(configuracao, "oi") is False


def test_whis_celular_pede_o_token_descobre_o_chat_e_grava_no_config(
    arquivo_de_configuracao: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    pedidos: list[httpx.Request] = []
    respostas = {
        "getMe": {"ok": True, "result": {"username": "whis_do_gabriel_bot"}},
        "getUpdates": {"ok": True, "result": [{"update_id": 9, "message": {"chat": {"id": 777, "type": "private"}}}]},
    }
    monkeypatch.setattr(celular, "REDE_DO_TELEGRAM", _rede(respostas, pedidos))
    monkeypatch.setattr(celular, "ESPERA_ENTRE_LEITURAS_S", 0)
    monkeypatch.setattr("getpass.getpass", lambda _pergunta="": f"  {TOKEN}  ")

    assert main(["celular"]) == 0

    configuracao = carregar(arquivo_de_configuracao)
    assert (configuracao.celular_telegram_token, configuracao.celular_telegram_chat) == (TOKEN, "777")
    saida = capsys.readouterr().out
    assert "@whis_do_gabriel_bot" in saida and TOKEN not in saida
    assert pedidos[-1].url.path.endswith("/sendMessage")


def test_whis_celular_com_token_que_nao_e_de_bot_nao_grava(
    arquivo_de_configuracao: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    pedidos: list[httpx.Request] = []
    monkeypatch.setattr(celular, "REDE_DO_TELEGRAM", _rede({"getMe": {"ok": False, "description": "Unauthorized"}}, pedidos))
    monkeypatch.setattr("getpass.getpass", lambda _pergunta="": "errado")

    assert main(["celular"]) != 0

    assert carregar(arquivo_de_configuracao).celular_telegram_token == ""
    assert "não é de um bot" in capsys.readouterr().out


def test_whis_celular_teste_manda_uma_mensagem_com_o_que_ja_esta_no_config(
    arquivo_de_configuracao: Path, monkeypatch: pytest.MonkeyPatch
):
    arquivo_de_configuracao.write_text(
        arquivo_de_configuracao.read_text(encoding="utf-8") + f'\n[celular]\ntelegram_token = "{TOKEN}"\ntelegram_chat = "777"\n',
        encoding="utf-8",
    )
    pedidos: list[httpx.Request] = []
    monkeypatch.setattr(celular, "REDE_DO_TELEGRAM", _rede({}, pedidos))

    assert main(["celular", "--teste"]) == 0

    [pedido] = pedidos
    assert json.loads(pedido.content)["chat_id"] == "777"


def test_a_suite_nunca_fala_com_o_telegram_de_verdade(mensagens_no_celular, tmp_path: Path):
    configuracao = replace(Configuracao(vault=tmp_path), celular_telegram_token=TOKEN, celular_telegram_chat="1")

    assert celular.avisar(configuracao, "oi") is True
    assert mensagens_no_celular == ["oi"]
