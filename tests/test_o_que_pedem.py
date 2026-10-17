"""O que os clientes pedem: os freelas do nicho de todas as caçadas, contados por pedido, com o orçamento."""

from __future__ import annotations

from pathlib import Path

import pytest

from whis.o_que_pedem import contar, ler_anuncios, teto_em_dolar

CACADA_1 = """\
---
tipo: cacada
---

# Caçada de freelas rápidos de 10 de outubro de 2026

## Chances boas

### 1. Build My Shopify Store — Loja de roupas

Freela · Freelancer.com · Shopify · USD 250 – 750 por projeto · encaixe 70 · [Abrir](https://www.freelancer.com/projects/shopify/Build-My-Shopify-Store)

Montar a loja do zero com 30 produtos e frete.

## Tentar a sorte

### Shopify Setup for SKU and Shipping

Freela · Freelancer.com · Shopify · INR 12.500 – 37.500 por projeto · encaixe 50 · [Abrir](https://www.freelancer.com/projects/shipping/Shopify-Setup-for-SKU-Shipping)

Configurar SKUs e frete expresso no checkout.

### Python scraper

Freela · Freelancer.com · Python · USD 30 – 250 por projeto · encaixe 60 · [Abrir](https://www.freelancer.com/projects/python/scraper)

Scraping de três sites.

## Descartadas

> [!note]- 2 descartadas ou sem triagem (clique para ver)
> - [Shopify ERP order sync app](https://www.freelancer.com/projects/api/Shopify-ERP-sync) — Freelancer.com · Shopify — App de integração que manda o pedido ao ERP por webhook.
> - [Vaga full stack](https://example.com/vaga) — Himalayas · full stack — vaga de emprego.
> - [Shopify product listings upload](https://www.freelancer.com/projects/data-entry/Shopify-listings) — Freelancer.com · Shopify — Cadastrar 200 produtos, perto do checkout e das seções do tema que ele já mexe.
> - [Shopify help needed](https://www.freelancer.com/projects/shopify/help) — Freelancer.com · Shopify — Preciso de ajuda, perto do checkout que ele já mexe.
"""

CACADA_2 = """\
---
tipo: cacada
---

# Caçada de freelas rápidos de 12 de outubro de 2026

## Chances boas

### 1. Build My Shopify Store — Loja de roupas

Freela · Freelancer.com · Shopify · USD 250 – 750 por projeto · encaixe 70 · [Abrir](https://www.freelancer.com/projects/shopify/Build-My-Shopify-Store)

O mesmo anúncio de antes.

### 2. Speed up my Shopify store

Freela · Freelancer.com · Shopify · £100–300 GBP · encaixe 75 · [Abrir](https://www.freelancer.com/projects/shopify/speed-up)

Melhorar o PageSpeed e o LCP da loja.
"""


def _vault(tmp_path: Path) -> Path:
    pasta = tmp_path / "cacada"
    pasta.mkdir(parents=True)
    (pasta / "2026-10-10-0114.md").write_text(CACADA_1, encoding="utf-8")
    (pasta / "2026-10-12-1832.md").write_text(CACADA_2, encoding="utf-8")
    (pasta / "criterios.md").write_text("## Fontes\n- [Shopify falso](https://x.com/shopify) — não é caçada\n", encoding="utf-8")
    return tmp_path


def test_junta_os_anuncios_do_nicho_de_todas_as_cacadas_sem_repetir(tmp_path: Path):
    anuncios = ler_anuncios(_vault(tmp_path), "shopify")

    assert sorted(a.titulo for a in anuncios) == [
        "Build My Shopify Store", "Shopify ERP order sync app", "Shopify Setup for SKU and Shipping",
        "Shopify help needed", "Shopify product listings upload", "Speed up my Shopify store",
    ]
    loja = next(a for a in anuncios if a.titulo == "Build My Shopify Store")
    assert loja.faixa == "USD 250 – 750 por projeto" and "Montar a loja" in loja.texto


def test_o_mesmo_anuncio_com_sufixo_no_titulo_e_link_em_outra_caixa_fica_um_so(tmp_path: Path):
    pasta = tmp_path / "cacada"
    pasta.mkdir(parents=True)
    bloco = (
        "---\ntipo: cacada\n---\n\n## Tentar a sorte\n\n### {titulo}\n\n"
        "Freela · Freelancer.com · Shopify · {faixa} · encaixe 50 · [Abrir]({link})\n\nLigar a loja Shopify ao Faire.\n"
    )
    (pasta / "2026-10-10-0114.md").write_text(bloco.format(
        titulo="Shopify Store Linkage and Optimization for Wholesale Sales", faixa="USD 22 – 45 por projeto",
        link="https://www.freelancer.com/projects/ecommerce/Shopify-Store-Linkage-Optimization-for",
    ), encoding="utf-8")
    (pasta / "2026-10-17-0104.md").write_text(bloco.format(
        titulo="Shopify Store Linkage and Optimization for Wholesale Sales (Faire + Shopify)",
        faixa="US$ 22,50–45 (média dos lances ~US$ 49)",
        link="https://www.freelancer.com/projects/ecommerce/shopify-store-linkage-optimization-for",
    ), encoding="utf-8")

    [anuncio] = ler_anuncios(tmp_path, "shopify")

    assert teto_em_dolar(anuncio.faixa) == 45


def test_loja_completa_que_cita_seo_nao_e_cadastro_nem_marketing():
    from whis.o_que_pedem import Anuncio

    loja = Anuncio("Modern Shopify Store Build", "https://x.com/1", "", "Loja Shopify completa (tema, apps, SEO)", "c")
    cadastro = Anuncio("24-Hour Shopify Product Upload", "https://x.com/2", "", "Cadastro de 35 produtos", "c")

    linhas = {linha.pedido: linha.anuncios for linha in contar([loja, cadastro])}

    assert linhas["Cadastro, gestão e marketing da loja (não é dev)"] == 1


def test_o_teto_do_orcamento_vira_dolar():
    assert teto_em_dolar("US$ 22,50–45 (média dos lances ~US$ 49)") == 45, "a média dos lances não é o orçamento"
    assert teto_em_dolar("USD 250 – 750 por projeto") == 750
    assert teto_em_dolar("INR 12.500 – 37.500 por projeto") == pytest.approx(37_500 * 0.065 / 5.4)
    assert teto_em_dolar("£100–300 GBP") == pytest.approx(300 * 7.0 / 5.4)
    assert teto_em_dolar("R$ 500 - 1.000") == pytest.approx(1000 / 5.4)
    assert teto_em_dolar("orçamento não informado") is None


def test_conta_por_pedido_com_a_faixa_do_orcamento(tmp_path: Path):
    linhas = {linha.pedido: linha for linha in contar(ler_anuncios(_vault(tmp_path), "shopify"))}

    assert linhas["Montar ou configurar a loja"].anuncios == 2
    assert linhas["App, integração ou sync com outro sistema"].anuncios == 1
    assert linhas["Checkout, pagamento e frete"].anuncios == 1, "frete na lista de montar a loja e o checkout que ele já mexe não contam"
    assert linhas["Cadastro, gestão e marketing da loja (não é dev)"].anuncios == 1
    assert "Ajuste de tema ou seção" not in linhas
    assert linhas["Velocidade e acessibilidade"].anuncios == 1
    assert linhas["Velocidade e acessibilidade"].mediana == pytest.approx(300 * 7.0 / 5.4)
    assert linhas["Montar ou configurar a loja"].mediana == pytest.approx((750 + 37_500 * 0.065 / 5.4) / 2)


def test_o_comando_escreve_a_nota_e_mostra_a_tabela(arquivo_de_configuracao: Path, caminho_do_vault: Path, capsys):
    from whis.__main__ import main

    _vault(caminho_do_vault.parent / "v")
    arquivo_de_configuracao.write_text(
        f'vault = "{(caminho_do_vault.parent / "v").as_posix()}"\n[cacada]\nnicho_freela = "shopify"\n', encoding="utf-8"
    )

    assert main(["o-que-pedem"]) == 0

    nota = (caminho_do_vault.parent / "v" / "cacada" / "o-que-pedem.md").read_text(encoding="utf-8")
    assert "| Montar ou configurar a loja | 2 | 33% |" in nota
    assert "1 sem pedido reconhecido" in nota
    assert "6 anúncios de shopify em 2 caçadas" in capsys.readouterr().out
