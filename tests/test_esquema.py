"""O esquema de uma aula: só passa SVG que é desenho."""

from __future__ import annotations

import pytest

from whis.esquema import LIMITE_DO_ESQUEMA, validar_esquema

BOM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 120">'
    '<defs><marker id="seta" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">'
    '<path d="M0,0 L8,4 L0,8 z" fill="currentColor"/></marker></defs>'
    '<rect x="10" y="10" width="100" height="40" fill="none" stroke="currentColor"/>'
    '<line x1="110" y1="30" x2="190" y2="30" stroke="currentColor" marker-end="url(#seta)"/>'
    '<text x="60" y="35" text-anchor="middle" font-size="12">Custo</text></svg>'
)


def test_esquema_bom_passa_igual():
    assert validar_esquema(BOM) == BOM


def test_espaco_em_volta_e_tirado():
    assert validar_esquema(f"  \n{BOM}\n") == BOM


def test_svg_sem_namespace_passa():
    svg = '<svg viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8"/></svg>'
    assert validar_esquema(svg) == svg


def test_acento_e_texto_em_portugues_passam():
    svg = '<svg viewBox="0 0 10 10"><text x="1" y="5">Margem de lucro — preço × volume</text></svg>'
    assert validar_esquema(svg) == svg


@pytest.mark.parametrize(
    "ruim",
    [
        "",
        "<div>oi</div>",
        BOM.replace("<rect", "<script>alert(1)</script><rect"),
        BOM.replace('<rect x="10"', '<rect onload="x()" x="10"'),
        BOM.replace("<rect", '<image href="https://x.com/a.png"/><rect'),
        BOM.replace("<rect", '<a href="https://x.com"><rect/></a><rect'),
        BOM.replace("<rect", '<foreignObject><div/></foreignObject><rect'),
        BOM.replace('fill="none"', 'fill="url(https://x.com/a)"'),
        BOM.replace('fill="none"', 'style="fill:red"'),
        BOM.replace("<rect", '<style>rect{fill:red}</style><rect'),
        BOM.replace('fill="none"', 'fill="javascript:alert(1)"'),
        BOM.replace("<rect", '<use href="#seta"/><rect'),
        '<!DOCTYPE svg [<!ENTITY a "b">]>' + BOM,
        BOM.replace("<rect", "<!-- oculto --><rect"),
        BOM.replace("Custo", "<![CDATA[Custo]]>"),
        '<?xml version="1.0"?>' + BOM,
        "<svg><rect",
        BOM + "<svg/>",
    ],
)
def test_esquema_ruim_e_recusado(ruim):
    assert validar_esquema(ruim) == ""


def test_atributo_de_outro_namespace_e_recusado():
    svg = BOM.replace(
        '<rect x="10"', '<rect xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://x.com" x="10"'
    )
    assert validar_esquema(svg) == ""


def test_elemento_de_outro_namespace_e_recusado():
    svg = BOM.replace("<rect ", '<rect xmlns="http://www.w3.org/1999/xhtml" ')
    assert validar_esquema(svg) == ""


def test_esquema_grande_demais_e_recusado():
    grande = BOM.replace("Custo", "x" * LIMITE_DO_ESQUEMA)
    assert validar_esquema(grande) == ""


def test_limite_conta_bytes_nao_caracteres():
    corpo = "é" * (LIMITE_DO_ESQUEMA // 2)
    assert validar_esquema(BOM.replace("Custo", corpo)) == ""


def test_valor_que_nao_e_texto_e_recusado():
    assert validar_esquema(None) == ""  # type: ignore[arg-type]
