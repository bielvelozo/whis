"""A prova na proposta: cada chance boa de freela diz qual peça do portfólio citar, com o link da lista dele."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from whis.cacada import cacar
from whis.configuracao import Configuracao
from whis.criterios_da_cacada import CAMINHO_DOS_CRITERIOS, MODELO_DOS_CRITERIOS, PecaDoPortfolio, interpretar_criterios
from whis.fakes_da_cacada import PreparoFake, coleta_fake, portas_fake
from whis.oportunidades import FREELA, Oportunidade

TEMA = "https://github.com/bielvelozo/inkly-shopify-theme"
CARRINHO = f"{TEMA}#2-cart-drawer-with-upsell-and-free-shipping-bar"
APP = "https://github.com/bielvelozo/inkly-erp-sync"

PORTFOLIO = f"""
## Portfólio

Uma peça por linha: `- Nome: link — o que ela mostra`.

- Tema Shopify Inkly: {TEMA} — tema Online Store 2.0 inteiro, com seções e páginas de produto e coleção
- Carrinho em gaveta: {CARRINHO} — cart drawer com upsell e barra de frete grátis
- App Inkly ERP Sync: {APP} — app embutido, webhook de pedido e rastreio de volta (order sync)
- Linha sem link: só texto
"""

CARRINHO_FREELA = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas · web", titulo="Shopify cart drawer with upsell",
    link="https://example.com/freelas/cart-drawer", descricao="Add a free shipping bar and upsell to the cart drawer of my Shopify store.",
)
LOJA_FREELA = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas · web", titulo="Loja Shopify do zero",
    link="https://example.com/freelas/loja-do-zero", descricao="Montar a loja com 20 produtos.",
)


def test_a_secao_portfolio_vira_a_lista_de_pecas():
    criterios = interpretar_criterios(MODELO_DOS_CRITERIOS + PORTFOLIO)

    assert criterios.portfolio == (
        PecaDoPortfolio("Tema Shopify Inkly", TEMA, "tema Online Store 2.0 inteiro, com seções e páginas de produto e coleção"),
        PecaDoPortfolio("Carrinho em gaveta", CARRINHO, "cart drawer com upsell e barra de frete grátis"),
        PecaDoPortfolio("App Inkly ERP Sync", APP, "app embutido, webhook de pedido e rastreio de volta (order sync)"),
    )
    assert any("Linha sem link" in aviso for aviso in criterios.avisos)
    assert interpretar_criterios(MODELO_DOS_CRITERIOS).portfolio == ()


class _ResumoComProva(PreparoFake):
    def __init__(self, prova: str) -> None:
        super().__init__()
        self.prova = prova
        self.procuros: list[str] = []

    def resumir(self, oportunidade, veredito, pagina, perfil, procuro, sobre_mim):
        self.procuros.append(procuro)
        return replace(super().resumir(oportunidade, veredito, pagina, perfil, procuro, sobre_mim), prova=self.prova)

    def preparar(self, oportunidade, veredito, pagina, perfil, procuro, sobre_mim):
        return replace(super().preparar(oportunidade, veredito, pagina, perfil, procuro, sobre_mim), prova=self.prova)


def _cacar(configuracao: Configuracao, tmp_path: Path, prova: str):
    vault = Path(configuracao.vault)
    (vault / CAMINHO_DOS_CRITERIOS).parent.mkdir(parents=True, exist_ok=True)
    (vault / CAMINHO_DOS_CRITERIOS).write_text(MODELO_DOS_CRITERIOS + PORTFOLIO, encoding="utf-8")

    def coletar(fontes, agora, **opcoes):
        coleta = coleta_fake(fontes, agora, **opcoes)
        coleta.por_fonte["99Freelas · web"] = (CARRINHO_FREELA, LOJA_FREELA)
        return coleta

    portas = portas_fake()
    portas.coletar = coletar
    portas.preparo = _ResumoComProva(prova)
    resultado = cacar(replace(configuracao, cacada_nicho_freela="shopify"), portas, pasta_do_estado=tmp_path / "estado", modo="freelas")
    pasta = vault / "cacada" / resultado.corrida
    return portas, {nota.name.split("-")[0]: nota.read_text(encoding="utf-8") for nota in pasta.glob("*.md")}


def test_sem_prova_valida_a_peça_que_mais_casa_entra_com_o_link(configuracao: Configuracao, tmp_path: Path):
    portas, notas = _cacar(configuracao, tmp_path, prova="Tema da loja: https://inventado.example/tema")

    assert all(TEMA in procuro and APP in procuro for procuro in portas.preparo.procuros), "a lista vai no pedido"
    carrinho = notas["shopify"].split("## Prova para citar", 1)[1]
    assert f"Carrinho em gaveta: {CARRINHO}" in carrinho and "inventado" not in carrinho
    loja = notas["loja"].split("## Prova para citar", 1)[1]
    assert f"Tema Shopify Inkly: {TEMA}" in loja, "o tema casa pela palavra Shopify"


def test_o_resumo_pede_a_peca_e_ela_chega_no_pacote():
    from claude_agent_sdk import ResultMessage

    from whis.cacada_claude import ESQUEMA_DO_PREPARO, ESQUEMA_DO_RESUMO, PreparoClaude
    from whis.oportunidades import Veredito

    class Gravado(PreparoClaude):
        async def _mensagens(self, prompt, opcoes):
            self.opcoes = opcoes
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s",
                total_cost_usd=0.01,
                structured_output={
                    "resumo": "r", "por_que_casa": "p", "ponto_fraco": "f", "salario": "s",
                    "prova": f"Carrinho em gaveta: {CARRINHO} — é o que ele pede",
                },
            )

    preparo = Gravado()
    pacote = preparo.resumir(CARRINHO_FREELA, Veredito(CARRINHO_FREELA.id, "chance_boa", "m", 80), "", portas_fake().perfil.montar("", "", ""), "", "")

    assert pacote.prova == f"Carrinho em gaveta: {CARRINHO} — é o que ele pede"
    assert "prova" in ESQUEMA_DO_RESUMO["required"] and "prova" in ESQUEMA_DO_PREPARO["required"]
    assert "Portfólio" in preparo.opcoes.system_prompt


def test_freela_que_nao_casa_com_nenhuma_peca_fica_sem_prova():
    from whis.prova_do_portfolio import conferir_prova

    scraper = Oportunidade.nova(tipo=FREELA, fonte="x", titulo="Python scraper", link="https://example.com/s", descricao="Scrape listings to CSV.")
    pecas = interpretar_criterios(PORTFOLIO).portfolio

    assert conferir_prova("", scraper, pecas) == ""
    assert conferir_prova("qualquer coisa", scraper, ()) == "qualquer coisa"


def test_a_vitrine_nao_vira_prova_no_rascunho_da_cacada():
    from whis.prova_do_portfolio import conferir_prova, sem_a_vitrine

    vitrine = PecaDoPortfolio("Site do portfólio", "https://gabrielvelozo.pages.dev", "o portfólio inteiro, carrinho e tema")
    pecas = (*interpretar_criterios(PORTFOLIO).portfolio, vitrine)

    assert vitrine not in sem_a_vitrine(pecas) and len(sem_a_vitrine(pecas)) == len(pecas) - 1
    assert conferir_prova("Site do portfólio: https://gabrielvelozo.pages.dev", CARRINHO_FREELA, pecas).startswith("Carrinho em gaveta:")
    assert conferir_prova(f"{CARRINHO} e https://gabrielvelozo.pages.dev", CARRINHO_FREELA, pecas) == f"Carrinho em gaveta: {CARRINHO} — cart drawer com upsell e barra de frete grátis"
    assert conferir_prova("https://gabrielvelozo.pages.dev", CARRINHO_FREELA, (vitrine,)) == ""


def test_a_prova_que_o_claude_escolheu_da_lista_fica(configuracao: Configuracao, tmp_path: Path):
    _, notas = _cacar(configuracao, tmp_path, prova=f"App Inkly ERP Sync: {APP} — mostra integração com webhook")

    assert f"App Inkly ERP Sync: {APP} — mostra integração com webhook" in notas["loja"]
