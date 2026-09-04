"""A daily como página: o mesmo conteúdo da nota, com os pesos invertidos.

O que se prova aqui é o que o usuário faz com ela: abrir um minuto antes de
falar, ler o roteiro em voz alta, e às vezes clicar num link. As listas cruas
existem para conferir uma afirmação, e por isso nascem recolhidas.

Duas invariantes valem mais que o resto. A página é **autossuficiente** — nada
buscado na rede, porque ela abre como arquivo local e às vezes sem internet. E
todo texto de fora é **escapado** antes de virar markup, porque uma mensagem de
Slack não pode injetar HTML na página que o usuário abre.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from second_brain.coleta import FalhaDeFonte
from second_brain.daily import JanelaDaDaily, gerar_daily
from second_brain.fakes import DailyFake, FonteFake
from second_brain.fontes import ErroDeFonte, Evento
from second_brain.pagina_da_daily import montar_pagina
from second_brain.portas import Daily
from second_brain.vault import PontosDaDaily

AGORA = datetime.now().astimezone()


def _janela(**extras) -> JanelaDaDaily:
    desde = AGORA - timedelta(hours=6)
    campos = {"data": AGORA.date(), "desde": desde, "ate": AGORA}
    return JanelaDaDaily(**{**campos, **extras})


def _evento(**extras) -> Evento:
    campos = {
        "fonte": "git",
        "momento": AGORA - timedelta(hours=1),
        "titulo": "`a1b2c3d` Corrige o frete",
        "referencia": "loja",
    }
    return Evento(**{**campos, **extras})


def pagina(**extras) -> str:
    campos = {
        "janela": _janela(),
        "eventos": (_evento(),),
        "reunioes": (),
        "fontes_lidas": ("git",),
        "fontes_com_falha": (),
        "roteiro": Daily(entreguei=("Subi o frete.",)),
        "pontos": PontosDaDaily(),
    }
    return montar_pagina(**{**campos, **extras})


# -- autossuficiente ----------------------------------------------------------


def test_a_pagina_nao_busca_nada_na_rede():
    """Ela abre como arquivo local, às vezes sem internet, na hora de falar."""
    html = pagina()

    assert "<style>" in html, "o estilo vai embutido"
    for proibido in ("<link", "<script", "src=", "@import", "cdn"):
        assert proibido not in html.casefold(), f"a página buscaria algo: {proibido}"


def test_a_pagina_declara_idioma_e_viewport():
    html = pagina()

    assert '<html lang="pt-BR">' in html
    assert "viewport" in html
    assert "<!doctype html>" in html


def test_o_titulo_traz_a_data_por_extenso():
    html = pagina()

    assert "<title>Daily — " in html
    assert "<h1>Daily — " in html


# -- o roteiro é o que se lê --------------------------------------------------


def test_as_batidas_aparecem_na_ordem_de_falar():
    html = pagina(
        roteiro=Daily(
            entreguei=("Subi o frete.",),
            sigo_em=("Sigo no coletor.",),
            preciso_de=("Espero o review da Ana.",),
            duvidas=("Vale mesmo?",),
        ),
        pontos=PontosDaDaily(pontos=("puxar a retenção",), off_topic=("staging caiu",)),
    )

    ordem = [
        html.index(f">{rotulo}</h2>")
        for rotulo in ("Entreguei", "Sigo em", "Preciso de", "Dúvidas", "Meus pontos", "Off-topic")
    ]
    assert ordem == sorted(ordem), "as batidas saíram fora da ordem de falar"


def test_batida_vazia_aparece_dizendo_nada():
    """Um rótulo sem nada embaixo seria um buraco para o usuário pular falando."""
    html = pagina(roteiro=Daily(entreguei=("Subi o frete.",)))

    assert "Preciso de" in html
    assert 'class="vazio">nada<' in html


def test_secao_do_usuario_vazia_nao_aparece():
    html = pagina(pontos=PontosDaDaily())

    assert "Meus pontos" not in html
    assert "Off-topic" not in html


def test_a_linha_de_cobertura_esta_no_alto():
    html = pagina()

    assert "Cobre de" in html
    assert html.index("Cobre de") < html.index("Entreguei")


# -- o link, que é o motivo de a página existir -------------------------------


def test_o_link_do_roteiro_vira_ancora_clicavel():
    html = pagina(
        roteiro=Daily(preciso_de=("A [#1636](https://github.com/x/y/pull/1636) espera merge.",))
    )

    assert '<a href="https://github.com/x/y/pull/1636"' in html
    assert ">#1636</a>" in html
    assert "[#1636]" not in html, "a marcação crua não devia sobrar"


def test_o_link_abre_em_outra_aba_sem_vazar_a_origem():
    html = pagina(roteiro=Daily(duvidas=("veja [a issue](https://linear.app/x)",)))

    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html


def test_o_trecho_em_crase_vira_codigo():
    html = pagina(roteiro=Daily(entreguei=("subi o `a1b2c3d`",)))

    assert "<code>a1b2c3d</code>" in html


# -- nada de fora vira markup -------------------------------------------------


def test_mensagem_com_html_e_escapada():
    """Uma mensagem de Slack não pode injetar tag na página que o usuário abre."""
    html = pagina(
        eventos=(_evento(titulo="<script>alert(1)</script>", detalhe="<b>oi</b>"),),
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>oi</b>" not in html


def test_titulo_de_evento_com_aspas_nao_quebra_o_atributo():
    html = pagina(eventos=(_evento(titulo='ele disse "oi"', url='https://x/"aspas'),))

    assert 'href="https://x/&quot;aspas"' in html


def test_ponto_do_usuario_tambem_e_escapado():
    html = pagina(pontos=PontosDaDaily(pontos=("falar de <coisas> & outras",)))

    assert "&lt;coisas&gt;" in html and "&amp;" in html


# -- as listas cruas ficam recolhidas -----------------------------------------


def test_as_listas_cruas_nascem_recolhidas():
    """Ninguém lê 1.400 linhas de Slack em voz alta."""
    html = pagina()

    assert "<details>" in html
    assert "<details open" not in html


def test_a_fonte_mostra_quantos_eventos_traz():
    html = pagina(eventos=(_evento(), _evento(titulo="outro")))

    assert ">Git " in html
    assert '<span class="conta">2</span>' in html


def test_os_eventos_ficam_agrupados_por_referencia():
    html = pagina(
        eventos=(_evento(referencia="loja"), _evento(referencia="hub", titulo="outro")),
    )

    assert "<h3>loja</h3>" in html and "<h3>hub</h3>" in html
    assert html.index("<h3>loja</h3>") < html.index("<h3>hub</h3>"), "ordem de aparição"


def test_o_detalhe_do_evento_vira_citacao():
    html = pagina(eventos=(_evento(detalhe="subiu em produção"),))

    assert "<blockquote>subiu em produção</blockquote>" in html


def test_fonte_que_falhou_diz_o_motivo_na_propria_secao():
    html = pagina(
        fontes_lidas=("git",),
        fontes_com_falha=(FalhaDeFonte(fonte="slack", motivo="token ausente"),),
    )

    assert "token ausente" in html
    assert 'class="aviso"' in html, "e também no aviso do topo"


def test_sem_roteiro_a_pagina_avisa_e_mantem_as_listas():
    html = pagina(roteiro=None, falha_do_roteiro="o Claude não respondeu")

    assert 'class="aviso"' in html
    assert "o Claude não respondeu" in html
    assert "<details>" in html


# -- o rodapé explica a fala curta --------------------------------------------


def test_o_rodape_conta_os_eventos_e_as_fontes():
    html = pagina(eventos=(_evento(), _evento(titulo="outro")))

    assert "2 evento(s) de Git" in html


def test_o_rodape_explica_o_que_ficou_so_na_nota():
    """Sem isso, a fala curta ao lado de uma lista longa parece defeito."""
    html = pagina(calados=34)

    assert "Outros 34 ficaram só na nota" in html
    assert "projeto pessoal" in html


def test_sem_nada_calado_o_rodape_nao_fala_disso():
    assert "ficaram só na nota" not in pagina(calados=0)


# -- pela costura, que é o que escreve de verdade -----------------------------


@pytest.fixture
def gerar(configuracao_do_diario):
    def executar(**extras):
        return gerar_daily(
            datetime.now().astimezone(),
            configuracao=configuracao_do_diario(),
            fontes=[FonteFake("git", eventos=extras.pop("eventos", (_evento(),)))],
            roteiro=extras.pop("roteiro", DailyFake()),
            **extras,
        )

    return executar


def test_a_costura_escreve_a_pagina_ao_lado_da_nota(gerar, caminho_do_vault: Path):
    resultado = gerar()

    assert resultado.nota.suffix == ".md"
    assert resultado.pagina.suffix == ".html"
    assert resultado.pagina.parent == resultado.nota.parent
    assert resultado.pagina.stem == resultado.nota.stem


def test_a_pagina_escrita_abre_com_doctype(gerar):
    resultado = gerar()

    assert resultado.pagina.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_a_pagina_nao_confunde_a_ancora_da_janela_seguinte(gerar, caminho_do_vault: Path):
    """`ate_da_daily_anterior` varre `daily/*.md`: o HTML não pode virar âncora."""
    from second_brain.vault import ate_da_daily_anterior

    resultado = gerar()
    depois = resultado.janela.data + timedelta(days=1)

    ancora = ate_da_daily_anterior(caminho_do_vault, depois)

    assert ancora is not None
    assert len(list((caminho_do_vault / "daily").glob("*.html"))) == 1


def test_simulacao_nao_escreve_pagina(gerar, caminho_do_vault: Path):
    resultado = gerar(simular=True)

    assert resultado.pagina is None
    assert list((caminho_do_vault / "daily").glob("*.html")) == []


def test_todas_as_fontes_falhando_nao_deixa_pagina_orfa(
    configuracao_do_diario, caminho_do_vault: Path
):
    """Uma página sem nota seria um roteiro que o vault não registra."""
    from second_brain.coleta import TodasAsFontesFalharam

    with pytest.raises(TodasAsFontesFalharam):
        gerar_daily(
            datetime.now().astimezone(),
            configuracao=configuracao_do_diario(),
            fontes=[FonteFake("git", erro=ErroDeFonte("caiu"))],
            roteiro=DailyFake(),
        )

    assert not (caminho_do_vault / "daily").exists() or list(
        (caminho_do_vault / "daily").glob("*")
    ) == []


def test_a_pagina_so_pode_nascer_na_zona_da_daily(caminho_do_vault: Path):
    from second_brain.vault import ZONAS_DA_DAILY, ForaDaZonaDePropriedade, escrever, preparar

    raiz = preparar(caminho_do_vault)

    with pytest.raises(ForaDaZonaDePropriedade):
        escrever(raiz, "notas/2026-09-04.html", "<html>", zonas=ZONAS_DA_DAILY)
