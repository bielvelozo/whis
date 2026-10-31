"""A API do X: a assinatura OAuth 1.0a, o post, a imagem e o que conta como publicado, sem rede de verdade."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from whis.api_do_x import ChavesDoX, ClienteDoX, NaoSaiu, SemConfirmacao, cabecalho_oauth, link_do_post
from whis.configuracao import Configuracao, carregar_texto

#: O exemplo de "Creating a signature" da documentação do X; não são chaves de ninguém.
EXEMPLO = ChavesDoX(
    "xvz1evFS4wEEPTGEFPHBog",
    "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
    "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
    "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
)
CHAVES = ChavesDoX("chave-do-app", "SEGREDO-DO-APP", "token-da-conta", "SEGREDO-DO-TOKEN")


def _rede(pedidos: list[httpx.Request], *respostas: httpx.Response) -> httpx.MockTransport:
    fila = list(respostas)

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return fila.pop(0)

    return httpx.MockTransport(responder)


def test_a_assinatura_bate_com_o_exemplo_da_documentacao_do_x() -> None:
    cabecalho = cabecalho_oauth(
        "post",
        "https://api.twitter.com/1.1/statuses/update.json",
        EXEMPLO,
        parametros={"status": "Hello Ladies + Gentlemen, a signed OAuth request!", "include_entities": "true"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg",
        timestamp=1318622958,
    )

    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in cabecalho
    assert cabecalho.startswith('OAuth oauth_consumer_key="xvz1evFS4wEEPTGEFPHBog", oauth_nonce=')


def test_o_post_responde_ao_anterior_com_a_imagem_e_devolve_o_id() -> None:
    pedidos: list[httpx.Request] = []
    cliente = ClienteDoX(CHAVES, rede=_rede(pedidos, httpx.Response(201, json={"data": {"id": "1855", "text": "oi"}})))

    assert cliente.postar("Two.", responder_a="1854", imagens=("m1",)) == "1855"

    [pedido] = pedidos
    assert str(pedido.url) == "https://api.x.com/2/tweets"
    assert json.loads(pedido.content) == {"text": "Two.", "reply": {"in_reply_to_tweet_id": "1854"}, "media": {"media_ids": ["m1"]}}
    assert pedido.headers["Authorization"].startswith("OAuth ") and 'oauth_token="token-da-conta"' in pedido.headers["Authorization"]
    assert "SEGREDO" not in pedido.headers["Authorization"]


def test_o_primeiro_post_vai_sem_reply_nem_media() -> None:
    pedidos: list[httpx.Request] = []
    ClienteDoX(CHAVES, rede=_rede(pedidos, httpx.Response(201, json={"data": {"id": "1"}}))).postar("One.")

    assert json.loads(pedidos[0].content) == {"text": "One."}


def test_a_imagem_sobe_em_multipart_para_o_post(tmp_path: Path) -> None:
    arte = tmp_path / "peso.png"
    arte.write_bytes(b"\x89PNG fake")
    pedidos: list[httpx.Request] = []
    cliente = ClienteDoX(CHAVES, rede=_rede(pedidos, httpx.Response(200, json={"data": {"id": "77", "media_key": "3_77"}})))

    assert cliente.subir_imagem(arte) == "77"

    [pedido] = pedidos
    assert str(pedido.url) == "https://api.x.com/2/media/upload"
    assert pedido.headers["Content-Type"].startswith("multipart/form-data")
    corpo = pedido.read()
    assert b'name="media_category"' in corpo and b"tweet_image" in corpo
    assert b'filename="peso.png"' in corpo and b"\x89PNG fake" in corpo and b"image/png" in corpo


def test_recusa_do_x_e_falta_de_conexao_nao_publicaram(caplog: pytest.LogCaptureFixture) -> None:
    pedidos: list[httpx.Request] = []
    recusa = httpx.Response(403, json={"title": "Forbidden", "detail": "You are not permitted to perform this action.", "status": 403})
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(NaoSaiu, match="HTTP 403: You are not permitted"):
            ClienteDoX(CHAVES, rede=_rede(pedidos, recusa)).postar("x")
        with pytest.raises(NaoSaiu, match="HTTP 402: Your credits are depleted"):
            ClienteDoX(CHAVES, rede=_rede(pedidos, httpx.Response(402, json={"errors": [{"message": "Your credits are depleted"}]}))).postar("x")

        def sem_rede(pedido: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("sem rede")

        with pytest.raises(NaoSaiu, match="sem conexão"):
            ClienteDoX(CHAVES, rede=httpx.MockTransport(sem_rede)).postar("x")
    assert "SEGREDO" not in caplog.text


def test_queda_no_meio_erro_do_servidor_e_resposta_sem_id_ficam_sem_confirmacao() -> None:
    def caiu_no_meio(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou")

    with pytest.raises(SemConfirmacao, match="caiu no meio"):
        ClienteDoX(CHAVES, rede=httpx.MockTransport(caiu_no_meio)).postar("x")
    with pytest.raises(SemConfirmacao, match="HTTP 503"):
        ClienteDoX(CHAVES, rede=_rede([], httpx.Response(503, text="Service Unavailable"))).postar("x")
    with pytest.raises(SemConfirmacao, match="HTTP 201"):
        ClienteDoX(CHAVES, rede=_rede([], httpx.Response(201, json={"data": {}}))).postar("x")


def test_as_quatro_chaves_saem_de_x_no_config(tmp_path: Path) -> None:
    vault = f'vault = "{(tmp_path / "vault").as_posix()}"\n'
    configuracao = carregar_texto(
        vault + '[x]\napi_key = " a "\napi_key_secret = "b"\naccess_token = "c"\naccess_token_secret = "d"\n', origem=tmp_path / "config.toml"
    )

    assert ChavesDoX.da_configuracao(configuracao) == ChavesDoX("a", "b", "c", "d")
    assert ChavesDoX.da_configuracao(configuracao).completas
    assert not ChavesDoX.da_configuracao(replace(configuracao, x_access_token_secret="")).completas
    assert not ChavesDoX.da_configuracao(Configuracao(vault=tmp_path)).completas


def test_o_link_do_post_abre_sem_saber_o_usuario() -> None:
    assert link_do_post("1855") == "https://x.com/i/web/status/1855"
