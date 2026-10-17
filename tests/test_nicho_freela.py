"""A caçada de freela com nicho: chance boa só do nicho, perfil por modo, piso de preço."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from whis.cacada import cacar
from whis.configuracao import Configuracao
from whis.corrida import NOME_DO_CHECKPOINT
from whis.criterios_da_cacada import Criterios, FonteDaCacada
from whis.fakes_da_cacada import PerfilFake, PreparoFake, TriagemFake, coleta_fake, portas_fake
from whis.fontes_da_cacada import ColetaDaCacada
from whis.freelas_rapidos import PEDIDO_DE_FREELAS_RAPIDOS, criterios_de_freelas, do_nicho
from whis.oportunidades import CHANCE_BOA, FREELA, TENTAR_A_SORTE, Oportunidade

TEMA_SHOPIFY = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas · web", titulo="Ajuste no tema da loja Shopify",
    link="https://example.com/freelas/ajuste-tema-shopify", faixa="R$ 300 - 600",
    descricao="Preciso mudar a seção do carrinho e o rodapé do tema Dawn.",
)
LOJA_WOOCOMMERCE = Oportunidade.nova(
    tipo=FREELA, fonte="99Freelas · web", titulo="Corrigir checkout da loja virtual",
    link="https://example.com/freelas/checkout-woocommerce", faixa="R$ 400",
    descricao="Minha loja virtual em WooCommerce não fecha o pedido com PIX.",
)
SCRAPER = Oportunidade.nova(
    tipo=FREELA, fonte="Freelancer.com · Python", titulo="Python scraper for real estate listings",
    link="https://example.com/freelas/scraper-imoveis", faixa="USD 100 - 200",
    descricao="Scrape three listing sites into a CSV every day.",
)


def _criterios() -> Criterios:
    return Criterios(
        procuro="- Quero mais dinheiro.",
        sobre_mim="",
        fontes=(
            FonteDaCacada("99Freelas · web", "99freelas", "web-mobile-e-software"),
            FonteDaCacada("Freelancer.com · React", "freelancer", "react"),
        ),
    )


def test_com_nicho_o_pedido_so_chama_de_chance_boa_o_nicho_e_as_buscas_do_freelancer_ficam_nele():
    com_nicho = criterios_de_freelas(_criterios(), nicho="shopify")
    sem_nicho = criterios_de_freelas(_criterios())

    buscas = [f.argumento for f in com_nicho.fontes if f.tipo == "freelancer"]
    assert buscas == ["react", "shopify"], "a dele fica; as do modo fora do nicho saem"
    assert {"python", "automation", "bug fix", "api integration"} <= {f.argumento for f in sem_nicho.fontes}
    assert '"chance_boa" é só o freela rápido de Shopify' in com_nicho.procuro
    assert "fora do nicho nunca é \"chance_boa\"" in com_nicho.procuro
    assert "scraping" not in com_nicho.procuro.split('"tentar_a_sorte"', 1)[0]
    assert sem_nicho.procuro.startswith(PEDIDO_DE_FREELAS_RAPIDOS) and "nicho" not in PEDIDO_DE_FREELAS_RAPIDOS
    assert com_nicho.procuro.endswith("- Quero mais dinheiro.")


def _coleta(fontes, agora, **opcoes) -> ColetaDaCacada:
    coleta = coleta_fake(fontes, agora, **opcoes)
    coleta.por_fonte["99Freelas · web"] = (TEMA_SHOPIFY, LOJA_WOOCOMMERCE)
    coleta.por_fonte["Freelancer.com · Python"] = (SCRAPER,)
    return coleta


def _cacar(configuracao: Configuracao, tmp_path: Path, **chaves):
    portas = portas_fake()
    portas.coletar = _coleta
    resultado = cacar(replace(configuracao, **chaves), portas, pasta_do_estado=tmp_path / "estado", modo="freelas")
    checkpoint = json.loads((tmp_path / "estado" / NOME_DO_CHECKPOINT).read_text(encoding="utf-8"))
    vereditos = {v["id"]: v for v in checkpoint.get("vereditos") or []}
    return resultado, portas, vereditos


def test_com_nicho_a_chance_boa_fora_dele_vira_tentar_a_sorte(configuracao: Configuracao, tmp_path: Path):
    _, _, vereditos = _cacar(configuracao, tmp_path, cacada_nicho_freela="shopify")

    assert vereditos[TEMA_SHOPIFY.id]["classe"] == CHANCE_BOA
    assert vereditos[LOJA_WOOCOMMERCE.id]["classe"] == CHANCE_BOA, "e-commerce muito perto do nicho"
    assert vereditos[SCRAPER.id]["classe"] == TENTAR_A_SORTE
    assert "fora do nicho (shopify)" in vereditos[SCRAPER.id]["motivo"]
    landing = Oportunidade.nova(tipo=FREELA, fonte="Workana · TI e programação", titulo="Landing page para clínica odontológica", link="https://example.com/freelas/landing-clinica")
    assert vereditos[landing.id]["classe"] == TENTAR_A_SORTE


def test_e_commerce_citado_de_passagem_na_descricao_nao_e_do_nicho():
    def freela(titulo: str, descricao: str) -> Oportunidade:
        return Oportunidade.nova(tipo=FREELA, fonte="Freelancer.com · Shopify", titulo=titulo, link=f"https://example.com/{titulo}", descricao=descricao)

    assert not do_nicho(freela("Real Estate Investment Website", "Listings, a blog and maybe e-commerce later."), "shopify")
    assert not do_nicho(freela("B2B Lead Generation Specialist", "We sell to ecommerce brands."), "shopify")
    assert do_nicho(freela("Tag filter setup", "Collection filters on our Shopify store."), "shopify")
    assert do_nicho(freela("Loja virtual com frete grátis", "Barra de frete no carrinho."), "shopify")
    assert do_nicho(freela("Qualquer coisa", "Sem nicho, tudo passa."), "")


def test_a_caçada_com_nicho_le_so_a_busca_do_nicho_no_freelancer(configuracao: Configuracao, tmp_path: Path):
    lidas: list[FonteDaCacada] = []

    def coletar(fontes, agora, **opcoes):
        lidas.extend(fontes)
        return _coleta(fontes, agora, **opcoes)

    portas = portas_fake()
    portas.coletar = coletar
    cacar(replace(configuracao, cacada_nicho_freela="shopify"), portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    buscas = {f.argumento for f in lidas if f.tipo == "freelancer"}
    assert "shopify" in buscas
    assert buscas.isdisjoint({"python", "nodejs", "nextjs", "landing page", "bug fix", "api integration", "automation"})


def test_a_simulacao_com_nicho_diz_o_que_pode_ser_chance_boa(
    arquivo_de_configuracao: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    from whis import fontes_da_cacada
    from whis.__main__ import main

    arquivo_de_configuracao.write_text(
        arquivo_de_configuracao.read_text(encoding="utf-8") + '\n[cacada]\nnicho_freela = "Shopify"\n', encoding="utf-8"
    )
    lidas: list[str] = []

    def coletar(fontes, agora, **opcoes):
        lidas.extend(f.argumento for f in fontes if f.tipo == "freelancer")
        coleta = ColetaDaCacada()
        coleta.por_fonte["99Freelas · web"] = (TEMA_SHOPIFY, LOJA_WOOCOMMERCE)
        coleta.por_fonte["Freelancer.com · Shopify"] = (SCRAPER,)
        return coleta

    monkeypatch.setattr(fontes_da_cacada, "coletar", coletar)

    assert main(["hunt", "--simular", "--freelas"]) == 0

    saida = capsys.readouterr().out
    assert "python" not in lidas and "shopify" in lidas
    assert "Nicho: shopify" in saida
    assert "Fora do nicho, saíram do Freelancer.com: Freelancer.com · Next.js" in saida
    assert "99Freelas · web: 2 (2 do nicho)" in saida and "Freelancer.com · Shopify: 1 (0 do nicho)" in saida
    podem = saida.split("Podem ser chance boa", 1)[1]
    assert TEMA_SHOPIFY.titulo in podem and LOJA_WOOCOMMERCE.titulo in podem and SCRAPER.titulo not in podem


class _PerfilGravado(PerfilFake):
    def montar(self, evidencias, procuro, sobre_mim):
        self.procuro = procuro
        return super().montar(evidencias, procuro, sobre_mim)


def test_o_perfil_do_modo_freelas_puxa_o_nicho_e_nao_apaga_o_de_vaga(configuracao: Configuracao, tmp_path: Path):
    vault = Path(configuracao.vault)
    vaga = portas_fake()
    vaga.perfil = _PerfilGravado()
    cacar(configuracao, vaga, pasta_do_estado=tmp_path / "vaga")
    do_vaga = (vault / "cacada" / "perfil.md").read_text(encoding="utf-8")

    freelas = portas_fake()
    freelas.perfil = _PerfilGravado()
    cacar(replace(configuracao, cacada_nicho_freela="shopify"), freelas, pasta_do_estado=tmp_path / "freelas", modo="freelas")

    assert "Shopify" not in vaga.perfil.procuro
    assert "o resumo e a stack abrem pelo que ele já fez em Shopify" in freelas.perfil.procuro
    assert "o porquê casa começa pelo trabalho dele em Shopify" in freelas.perfil.procuro
    assert (vault / "cacada" / "perfil.md").read_text(encoding="utf-8") == do_vaga
    nota = (vault / "cacada" / "perfil-freelas.md").read_text(encoding="utf-8")
    assert "\n# O perfil da caçada de freela de Shopify\n" in nota


class _TriagemGravada(TriagemFake):
    def triar(self, oportunidades, perfil, procuro, sobre_mim):
        self.procuro = procuro
        return super().triar(oportunidades, perfil, procuro, sobre_mim)


class _ResumoBarato(PreparoFake):
    BARATO = "Orçamento R$ 300 - 600; pedir R$ 150 (2 h com IA)."

    def resumir(self, oportunidade, veredito, pagina, perfil, procuro, sobre_mim):
        return replace(super().resumir(oportunidade, veredito, pagina, perfil, procuro, sobre_mim), preco=self.BARATO)

    def preparar(self, oportunidade, veredito, pagina, perfil, procuro, sobre_mim):
        return replace(super().preparar(oportunidade, veredito, pagina, perfil, procuro, sobre_mim), preco=self.BARATO)


def test_com_piso_a_caçada_nunca_sugere_preco_abaixo_dele(configuracao: Configuracao, tmp_path: Path):
    portas = portas_fake()
    portas.coletar = _coleta
    portas.triagem = _TriagemGravada()
    portas.preparo = _ResumoBarato()

    resultado = cacar(
        replace(configuracao, cacada_nicho_freela="shopify", cacada_piso_freela=250),
        portas,
        pasta_do_estado=tmp_path / "estado",
        modo="freelas",
    )

    assert "nunca sugira preço de freela abaixo de R$ 250" in portas.triagem.procuro
    pacote = next((Path(configuracao.vault) / "cacada" / resultado.corrida).glob("ajuste-no-tema*.md")).read_text(encoding="utf-8")
    assert "pedir R$ 150 (2 h com IA). Abaixo do seu piso: peça pelo menos R$ 250." in pacote


def test_o_preco_do_orcamento_nao_e_confundido_com_a_sugestao():
    from whis.precos import conferir_piso

    assert conferir_piso("Orçamento R$ 100 - 200; pedir R$ 300.", "R$ 100 - 200", 250) == "Orçamento R$ 100 - 200; pedir R$ 300."
    assert conferir_piso("Orçamento USD 30; ask USD 40.", "USD 30", 250).endswith("Abaixo do seu piso: peça pelo menos R$ 250.")
    assert conferir_piso("Pedir R$ 1.500,00 pelo projeto.", "", 250) == "Pedir R$ 1.500,00 pelo projeto."
    assert conferir_piso("Pedir US$ 60 (R$ 324).", "", 250) == "Pedir US$ 60 (R$ 324)."
    assert conferir_piso("Pedir R$ 80.", "", 0) == "Pedir R$ 80."
    assert conferir_piso("Pedir US$ 1.250.50 ou R$ 6.000.", "", 250) == "Pedir US$ 1.250.50 ou R$ 6.000.", "número torto não derruba"


def test_sem_nicho_a_triagem_fica_como_esta(configuracao: Configuracao, tmp_path: Path):
    _, _, vereditos = _cacar(configuracao, tmp_path)

    assert vereditos[SCRAPER.id]["classe"] == CHANCE_BOA
