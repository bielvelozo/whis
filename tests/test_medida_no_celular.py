"""A medida do e-mail de velocidade sai do teste do velozo.dev, para o número bater com o que a loja vê no link."""

from __future__ import annotations

from whis import medida_no_celular
from whis.medida_no_celular import MedidaNoCelular

DA_AYTU = {
    "endereco": "https://aytu.com.br",
    "lab": {"nota": 71, "metricas": {"lcp": 8101}, "peso_total": 9644786, "pesos": {"total": {"bytes": 9644786, "n": 272}}},
    "sem_lab": None,
}


def test_a_medida_pelo_site_le_o_lcp_e_o_peso_do_pagespeed():
    pedidos: list[str] = []

    def abrir(endereco: str, tempo_limite: float):
        pedidos.append(endereco)
        return DA_AYTU

    medida = medida_no_celular.medir_pelo_site("https://aytu.com.br/", abrir=abrir)

    assert medida == MedidaNoCelular(8.1, 9.6, 272, do_site=True)
    assert pedidos == ["https://velozo.dev/api/velocidade?v=4&lang=pt&url=aytu.com.br"]
    assert "teste do velozo.dev" in medida.como_texto() and "8,1 s" in medida.como_texto()


def test_sem_o_pagespeed_ou_sem_rede_a_medida_pelo_site_nao_vem():
    def sem_lab(endereco, tempo_limite):
        return {"lab": None, "sem_lab": "psi-429"}

    def sem_rede(endereco, tempo_limite):
        raise OSError("sem rede")

    assert medida_no_celular.medir_pelo_site("aytu.com.br", abrir=sem_lab) is None
    assert medida_no_celular.medir_pelo_site("aytu.com.br", abrir=sem_rede) is None


def test_para_o_email_o_chrome_so_entra_quando_o_site_falha(monkeypatch):
    do_chrome = MedidaNoCelular(9.0, 3.0, 100)
    monkeypatch.setattr(medida_no_celular, "medir", lambda url: do_chrome)

    monkeypatch.setattr(medida_no_celular, "medir_pelo_site", lambda url: None)
    assert medida_no_celular.medir_para_o_email("https://aytu.com.br") is do_chrome

    do_site = MedidaNoCelular(8.1, 9.6, 272, do_site=True)
    monkeypatch.setattr(medida_no_celular, "medir_pelo_site", lambda url: do_site)
    assert medida_no_celular.medir_para_o_email("https://aytu.com.br") is do_site
