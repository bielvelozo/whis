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


# -- o botão Enviar e quem ouve o toque -------------------------------------------------------------

BOTAO = ("Enviar esta proposta", "enviar:0123456789ab")


def _toque(update_id: int = 5, *, de: int = 777, dados: str = BOTAO[1], mensagem: int = 42) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"toque-{update_id}",
            "from": {"id": de, "is_bot": False},
            "message": {"message_id": mensagem, "chat": {"id": de, "type": "private"}},
            "data": dados,
        },
    }


def _metodos(pedidos: list[httpx.Request]) -> list[str]:
    return [pedido.url.path.rsplit("/", 1)[-1] for pedido in pedidos]


def _ouvinte(pedidos, atualizacoes, ao_tocar, *, chat: str = "777", token: str = TOKEN) -> celular.Ouvinte:
    configuracao = replace(Configuracao(vault=Path(".")), celular_telegram_token=token, celular_telegram_chat=chat)
    rede = _rede({"getUpdates": {"ok": True, "result": atualizacoes}}, pedidos)
    return celular.Ouvinte(lambda: configuracao, ao_tocar, rede=rede, dormir=lambda _segundos: None)


def test_o_botao_vai_no_teclado_embaixo_da_mensagem():
    pedidos: list[httpx.Request] = []

    celular.Telegram(TOKEN, "777", rede=_rede({}, pedidos)).enviar("Para você aprovar", botoes=(BOTAO,))

    corpo = json.loads(pedidos[0].content)
    assert corpo["reply_markup"] == {"inline_keyboard": [[{"text": BOTAO[0], "callback_data": BOTAO[1]}]]}


def test_o_aviso_leva_o_botao_ate_o_telegram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pedidos: list[httpx.Request] = []
    monkeypatch.setattr(celular, "REDE_DO_TELEGRAM", _rede({}, pedidos))
    configuracao = replace(Configuracao(vault=tmp_path), celular_telegram_token=TOKEN, celular_telegram_chat="777")

    assert CELULAR_DE_VERDADE(configuracao, "oi", botoes=(BOTAO,)) is True

    assert json.loads(pedidos[0].content)["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == BOTAO[1]


def test_os_toques_esperam_na_api_so_pelos_botoes_e_o_tempo_da_rede_cobre_a_espera():
    pedidos: list[httpx.Request] = []

    celular.Telegram(TOKEN, "777", rede=_rede({"getUpdates": {"ok": True, "result": []}}, pedidos)).toques(10, espera=50)

    [pedido] = pedidos
    assert json.loads(pedido.content) == {"offset": 10, "timeout": 50, "allowed_updates": ["callback_query"]}
    assert pedido.extensions["timeout"]["read"] > 50


def test_o_toque_dele_e_respondido_na_hora_atendido_e_o_botao_sai():
    pedidos: list[httpx.Request] = []
    tocados: list[str] = []

    def ao_tocar(dados: str) -> celular.Resposta:
        assert _metodos(pedidos)[-1] == "answerCallbackQuery"
        tocados.append(dados)
        return celular.Resposta("Enviada na 99Freelas", tirar_botao=True)

    ouvinte = _ouvinte(pedidos, [_toque()], ao_tocar)

    assert ouvinte.uma_vez() == 1

    assert tocados == [BOTAO[1]]
    assert _metodos(pedidos) == ["getUpdates", "answerCallbackQuery", "sendMessage", "editMessageReplyMarkup"]
    assert json.loads(pedidos[1].content)["callback_query_id"] == "toque-5"
    resposta = json.loads(pedidos[2].content)
    assert resposta["text"] == "Enviada na 99Freelas" and resposta["reply_parameters"]["message_id"] == 42
    assert json.loads(pedidos[3].content) == {"chat_id": "777", "message_id": 42, "reply_markup": {"inline_keyboard": []}}

    ouvinte.uma_vez()
    assert json.loads(pedidos[4].content)["offset"] == 6


def test_o_botao_fica_quando_a_resposta_pede_para_tocar_de_novo():
    pedidos: list[httpx.Request] = []

    _ouvinte(pedidos, [_toque()], lambda _dados: celular.Resposta("O Chrome está ocupado; toque de novo.")).uma_vez()

    assert "editMessageReplyMarkup" not in _metodos(pedidos)


def test_toque_de_outra_pessoa_nao_faz_nada():
    pedidos: list[httpx.Request] = []
    tocados: list[str] = []

    _ouvinte(pedidos, [_toque(de=999)], lambda dados: tocados.append(dados)).uma_vez()

    assert tocados == []
    assert _metodos(pedidos) == ["getUpdates", "answerCallbackQuery"]


def test_erro_de_quem_atende_vira_resposta_e_o_ouvinte_segue(caplog: pytest.LogCaptureFixture):
    pedidos: list[httpx.Request] = []

    def quebrar(_dados: str):
        raise RuntimeError("o Chrome caiu")

    with caplog.at_level(logging.ERROR):
        assert _ouvinte(pedidos, [_toque(), _toque(6)], quebrar).uma_vez() == 2

    respostas = [json.loads(p.content)["text"] for p in pedidos if p.url.path.endswith("/sendMessage")]
    assert len(respostas) == 2 and all("bandeja.log" in texto for texto in respostas)
    assert "editMessageReplyMarkup" not in _metodos(pedidos)
    assert "o Chrome caiu" in caplog.text and "segredo-do-bot" not in caplog.text


def test_sem_token_o_ouvinte_nao_vai_a_rede():
    pedidos: list[httpx.Request] = []

    assert _ouvinte(pedidos, [_toque()], lambda _dados: None, token="").uma_vez() == 0

    assert pedidos == []


def test_o_ouvinte_roda_numa_thread_e_para_quando_pedem():
    pedidos: list[httpx.Request] = []
    ouvinte = _ouvinte(pedidos, [], lambda _dados: None)

    ouvinte.iniciar()
    ouvinte.parar()

    assert ouvinte.esperar(5) is True


# -- o ouvinte na bandeja e as que esperam o toque ----------------------------------------------------


def _com_bot(arquivo: Path) -> None:
    arquivo.write_text(arquivo.read_text(encoding="utf-8") + f'\n[celular]\ntelegram_token = "{TOKEN}"\ntelegram_chat = "777"\n', encoding="utf-8")


def test_a_bandeja_ouve_os_botoes_so_com_o_bot_ligado_e_fora_dos_fakes(
    arquivo_de_configuracao: Path, monkeypatch: pytest.MonkeyPatch
):
    from whis import bandeja as _bandeja

    chamadas: list[dict] = []
    monkeypatch.setattr(_bandeja, "executar", lambda _configuracao, **extras: chamadas.append(extras) or 0)

    assert main(["bandeja"]) == 0
    _com_bot(arquivo_de_configuracao)
    assert main(["bandeja", "--fakes"]) == 0
    assert main(["bandeja"]) == 0

    sem_bot, com_fakes, ligada = (extras["ouvinte"] for extras in chamadas)
    assert sem_bot is None and com_fakes is None and isinstance(ligada, celular.Ouvinte)


def test_o_toque_que_chega_na_bandeja_vai_para_a_proposta_automatica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import propostas_auto
    from whis.__main__ import _tocou_no_celular

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    configuracao = Configuracao(vault=tmp_path / "vault")

    desconhecido = _tocou_no_celular(configuracao, propostas_auto.PREFIXO_DO_TOQUE + "000000000000")
    alheio = _tocou_no_celular(configuracao, "outra-coisa")

    assert desconhecido.texto == propostas_auto.NAO_ACHEI and desconhecido.tirar_botao is True
    assert alheio.tirar_botao is True


def test_whis_celular_pendentes_manda_de_novo_as_que_esperam_o_toque(
    arquivo_de_configuracao: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import propostas_auto

    _com_bot(arquivo_de_configuracao)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    chamadas: list[dict] = []
    monkeypatch.setattr(propostas_auto, "oferecer_pendentes", lambda **opcoes: chamadas.append(opcoes) or 2)

    assert main(["celular", "--pendentes"]) == 0

    [opcoes] = chamadas
    assert opcoes["estado"] == propostas_auto.caminho_do_estado()
    assert "2 propostas esperando o seu toque" in capsys.readouterr().out



def test_o_toque_em_enviar_email_vai_para_o_email_das_agencias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from whis import agencias_email
    from whis.__main__ import _tocou_no_celular

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    resposta = _tocou_no_celular(Configuracao(vault=tmp_path / "vault"), agencias_email.chave_do_toque("contato@exemplo.com.br"))

    assert resposta.texto == agencias_email.NAO_ACHEI and resposta.tirar_botao is True
