"""O Freelancer.com fora de todas as estratégias e a 99Freelas lida até a idade da proposta automática (28/10)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from whis import fontes_da_cacada
from whis.criterios_da_cacada import Criterios, FonteDaCacada
from whis.oportunidades import FREELA, Oportunidade

PAGAS = ("freelancer.com.br", "freelancer.com")


def _paginas_com_idades(monkeypatch, idades_por_pagina: list[list[float]]) -> list[str]:
    pedidas: list[str] = []
    agora = datetime.now().astimezone()

    def texto(_cliente, url: str) -> str:
        pedidas.append(url)
        return url

    def interpretar(url: str, nome: str = "99Freelas", _agora=None):
        pagina = int(url.rsplit("page=", 1)[1])
        return tuple(
            Oportunidade.nova(
                tipo=FREELA, fonte=nome, titulo=f"p{pagina}-{i}", link=f"https://www.99freelas.com.br/project/p{pagina}-{i}",
                publicada=agora - timedelta(hours=horas),
            )
            for i, horas in enumerate(idades_por_pagina[pagina - 1])
        )

    monkeypatch.setattr(fontes_da_cacada, "_texto", texto)
    monkeypatch.setattr(fontes_da_cacada, "interpretar_99freelas", interpretar)
    return pedidas


def test_a_99freelas_para_na_pagina_em_que_tudo_ja_passou_da_idade(monkeypatch):
    idades = [[0.2, 100.6], [5.7, 24.0], [24.3, 35.4], [35.6, 47.0], [54.7, 71.1], [72.0], [124.0], [148.0]]
    pedidas = _paginas_com_idades(monkeypatch, idades)
    fonte = FonteDaCacada("99Freelas", "99freelas", "web-mobile-e-software")

    lidas = fontes_da_cacada.ler_99freelas(None, fonte, lambda _s: None, paginas=8, ate_idade=timedelta(hours=48))

    assert len(pedidas) == 5, "a página 5 é a primeira toda acima de 48 h"
    assert {o.titulo for o in lidas} >= {"p3-0", "p4-1"}


def test_sem_idade_le_so_as_paginas_pedidas(monkeypatch):
    pedidas = _paginas_com_idades(monkeypatch, [[1.0], [2.0], [30.0]])

    fontes_da_cacada.ler_99freelas(None, FonteDaCacada("99Freelas", "99freelas", ""), lambda _s: None)

    assert len(pedidas) == 2


def test_o_freelancer_com_nas_pagas_tira_a_fonte_dele_e_nao_a_do_br():
    freelancer = FonteDaCacada("Freelancer.com · Shopify", "freelancer", "shopify")

    assert fontes_da_cacada.fonte_paga(freelancer, PAGAS)
    assert not fontes_da_cacada.fonte_paga(freelancer, ("freelancer.com.br",))
    assert fontes_da_cacada.tipos_pagos(PAGAS) == {"freelancer"}


def test_o_padrao_do_config_ja_deixa_o_freelancer_com_de_fora(tmp_path: Path):
    from whis.configuracao import carregar

    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{tmp_path.as_posix()}"\n', encoding="utf-8")

    assert "freelancer.com" in carregar(arquivo).cacada_plataformas_pagas


def test_o_modo_freelas_nao_tem_fonte_do_freelancer_com():
    from whis.freelas_rapidos import criterios_de_freelas

    dele = Criterios("", "", (FonteDaCacada("Freelancer · meu", "freelancer", "shopify"), FonteDaCacada("99", "99freelas", "")))

    fontes = criterios_de_freelas(dele, (), plataformas_pagas=PAGAS, nicho="shopify").fontes

    assert fontes and not any(f.tipo == "freelancer" for f in fontes)
    assert any(f.tipo == "99freelas" for f in fontes)


def test_a_vigia_nao_le_o_freelancer_com_quando_ele_e_pago(monkeypatch):
    from whis import vigia_de_freelas
    from whis.fontes_da_cacada import ColetaDaCacada

    lidas: list[str] = []

    def coletar(fontes, _agora, **_opcoes):
        lidas.extend(f.tipo for f in fontes)
        return ColetaDaCacada()

    monkeypatch.setattr(fontes_da_cacada, "coletar", coletar)

    vigia_de_freelas.ler_do_nicho("shopify", plataformas_pagas=PAGAS)

    assert lidas == ["99freelas", "shopify_community"]


def test_a_janela_da_proposta_soma_as_24_h_do_exclusivo(tmp_path: Path):
    from whis.__main__ import _janela_da_proposta
    from whis.configuracao import carregar

    def janela(linhas: str):
        arquivo = tmp_path / "config.toml"
        arquivo.write_text(f'vault = "{tmp_path.as_posix()}"\n[cacada]\n{linhas}\n', encoding="utf-8")
        return _janela_da_proposta(carregar(arquivo))

    assert janela('propostas_auto = "ligado"\npropostas_auto_horas = 24') == timedelta(hours=48)
    assert janela('propostas_auto = "ensaio"\npropostas_auto_horas = 6\npropostas_auto_exclusivos = true') == timedelta(hours=6)
    assert janela('propostas_auto = "desligado"') is None
