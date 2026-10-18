"""A loja do cliente: o endereço que o anúncio traz e o que o Whis mede nela antes da proposta."""

from __future__ import annotations

import httpx

from whis.loja_do_cliente import Loja, achar, medir, medir_do_texto

HOME = (
    "<html><head><script src='https://cdn.shopify.com/s/files/vendor.js'></script>"
    "<script src=\"https://apps.example.com/reviews.js\" defer></script><script>var Shopify = Shopify || {};"
    'Shopify.theme = {"name":"Cópia de Dawn","id":1,"schema_name":"Dawn","schema_version":"9.0.0","role":"main"};</script>'
    "<script async src='/checkouts/internal.js'></script></head><body>" + "x" * 40_000 + "</body></html>"
)


def _relogio(*momentos: float):
    fila = list(momentos)
    return lambda: fila.pop(0)


def test_acha_a_loja_no_anuncio_e_ignora_rede_social_email_e_a_propria_99freelas():
    assert achar("Minha loja é https://www.lojadamaria.com.br/collections/all e preciso de ajuda") == "https://www.lojadamaria.com.br/"
    assert achar("A loja: lojadamaria.com.br, tema Dawn.") == "https://lojadamaria.com.br/"
    assert achar("Loja em teste: minha-loja.myshopify.com") == "https://minha-loja.myshopify.com/"
    assert achar("We run barkukonline.co.uk, a niche store") == "https://barkukonline.co.uk/"
    assert achar("Store: www.example-shop.de or shop.example.xyz") is None
    assert achar("Me chama em contato@lojadamaria.com.br ou no instagram.com/lojadamaria") is None
    assert achar("Vi na 99freelas.com.br e no https://www.youtube.com/watch?v=1 um exemplo") is None
    assert achar("Sistema personalizado.O funcionamento é simples.Com isso basta") is None
    assert achar("Teste em http://192.168.0.10/admin ou http://localhost:3000") is None


def test_mede_a_home_o_tempo_o_peso_os_scripts_e_o_tema():
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=HOME)

    loja = medir("https://www.lojadamaria.com.br/", rede=httpx.MockTransport(responder), relogio=_relogio(10.0, 12.84))

    assert pedidos == ["https://www.lojadamaria.com.br/"]
    assert loja == Loja(endereco="lojadamaria.com.br", segundos=2.8, kb=40, scripts=3, tema="Dawn 9.0.0", com_senha=False)
    texto = loja.como_texto()
    assert "lojadamaria.com.br" in texto and "2,8 s" in texto and "40 KB" in texto and "3 scripts" in texto
    assert "Dawn 9.0.0" in texto and "senha" not in texto


def test_loja_fechada_com_senha_e_dito_e_pagina_que_nao_abre_nao_vira_medida():
    def senha(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/password":
            return httpx.Response(200, text="<html><body>Opening soon</body></html>")
        return httpx.Response(302, headers={"Location": "https://lojadamaria.com.br/password"})

    fechada = medir("https://lojadamaria.com.br/", rede=httpx.MockTransport(senha), relogio=_relogio(0.0, 0.4))

    assert fechada is not None and fechada.com_senha and "fechada com senha" in fechada.como_texto()
    assert medir("https://lojadamaria.com.br/", rede=httpx.MockTransport(lambda _p: httpx.Response(403)), relogio=_relogio(0.0, 1.0)) is None

    def caiu(_pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    assert medir("https://lojadamaria.com.br/", rede=httpx.MockTransport(caiu), relogio=_relogio(0.0, 1.0)) is None


def test_sem_endereco_no_texto_nada_e_aberto():
    def nao_pode(_pedido: httpx.Request) -> httpx.Response:
        raise AssertionError("abriu a rede sem loja no anúncio")

    assert medir_do_texto("Preciso de um sistema de numerologia.", rede=httpx.MockTransport(nao_pode)) is None
