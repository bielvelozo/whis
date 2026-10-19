"""A página inicial de uma loja medida como num celular em 4G, para a procura dizer um número de verdade.

O PageSpeed Insights sem chave vive sem cota (429) e o Lighthouse não está
instalado, então o Whis abre a página no Chrome dele, sem o perfil da caçada e
sem janela, emulando um celular (Moto G4) com a rede lenta e o processador 4x
mais lento, como o teste de celular do Lighthouse. Mede quando a maior imagem
ou bloco de texto apareceu (LCP), quanto a página baixou e em quantos pedidos.

Em 18/10, cinco lojas Shopify brasileiras deram LCP de 6,5 s a 36 s assim; o
Google chama de ruim acima de 4 s. Uma medida por vez leva de 20 s a 1 min.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

_log = logging.getLogger("whis.medida_no_celular")

TEMPO_LIMITE_MS = 60_000
ESPERA_DEPOIS_DO_LOAD_MS = 2_000
LCP_RUIM_S = 4.0
APARELHO = "Moto G4"
REDE_4G = {
    "offline": False,
    "latency": 150,
    "downloadThroughput": 1.6 * 1024 * 1024 / 8 * 0.9,
    "uploadThroughput": 750 * 1024 / 8 * 0.9,
}
PROCESSADOR_MAIS_LENTO = 4

_LCP = """() => new Promise(fim => {
  let valor = 0;
  try {
    new PerformanceObserver(lista => { for (const e of lista.getEntries()) valor = e.startTime; })
      .observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) {}
  setTimeout(() => fim(valor), 300);
})"""


@dataclass(frozen=True)
class MedidaNoCelular:
    """O que a página inicial levou e baixou no celular emulado: só isso pode ir no e-mail."""

    lcp_s: float
    mb: float
    pedidos: int

    @property
    def lenta(self) -> bool:
        return self.lcp_s > LCP_RUIM_S

    def segundos(self) -> str:
        return f"{round(self.lcp_s)} segundos"

    def como_texto(self) -> str:
        mb = f"{self.mb:.1f}".replace(".", ",")
        lcp = f"{self.lcp_s:.1f}".replace(".", ",")
        return (
            f"- no celular em 4G (Moto G4 emulado, rede lenta e processador 4x mais lento), a maior imagem ou bloco "
            f"de texto da página inicial apareceu em {lcp} s (LCP; o Google chama de ruim acima de 4 s)\n"
            f"- a página inicial baixou {mb} MB em {self.pedidos} pedidos"
        )


def medir(url: str) -> MedidaNoCelular | None:
    """Abre `url` uma vez no celular emulado; None quando o Chrome não abre ou a página não mostrou nada."""
    try:
        from playwright.sync_api import Error as ErroDoPlaywright
        from playwright.sync_api import sync_playwright
    except ImportError:
        _log.warning("Medida no celular: o Playwright não está instalado.")
        return None
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                return _medir(playwright, navegador, url, ErroDoPlaywright)
            finally:
                navegador.close()
    except ErroDoPlaywright as erro:
        _log.info("Medida no celular: o Chrome não abriu %s (%s).", url, erro)
        return None


def _medir(playwright, navegador, url: str, erro_do_playwright) -> MedidaNoCelular | None:
    contexto = navegador.new_context(**playwright.devices[APARELHO], locale="pt-BR")
    try:
        pagina = contexto.new_page()
        cdp = contexto.new_cdp_session(pagina)
        baixado = {"bytes": 0, "pedidos": 0}

        def terminou(evento: dict) -> None:
            baixado["bytes"] += evento.get("encodedDataLength", 0)
            baixado["pedidos"] += 1

        cdp.on("Network.loadingFinished", terminou)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", REDE_4G)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": PROCESSADOR_MAIS_LENTO})
        inicio = time.perf_counter()
        try:
            resposta = pagina.goto(url, wait_until="load", timeout=TEMPO_LIMITE_MS)
        except erro_do_playwright as erro:
            _log.info("Medida no celular: %s não terminou de carregar em %d s (%s).", url, TEMPO_LIMITE_MS // 1000, type(erro).__name__)
            resposta = None
        if resposta is not None and resposta.status >= 400:
            _log.info("Medida no celular: %s respondeu %s.", url, resposta.status)
            return None
        pagina.wait_for_timeout(ESPERA_DEPOIS_DO_LOAD_MS)
        lcp_ms = float(pagina.evaluate(_LCP) or 0)
        if lcp_ms <= 0:
            _log.info("Medida no celular: %s não mostrou LCP (%.0f s abertos).", url, time.perf_counter() - inicio)
            return None
        return MedidaNoCelular(lcp_s=round(lcp_ms / 1000, 1), mb=round(baixado["bytes"] / 1_000_000, 1), pedidos=baixado["pedidos"])
    finally:
        contexto.close()
