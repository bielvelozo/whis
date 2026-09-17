"""O acrílico simulado: o desfoque e a tinta são puros; a captura só se prova onde há tela."""

from __future__ import annotations

import sys

import pytest
from PIL import Image

from whis.fundo_desfocado import capturar_atras, cor_media, desfocar, fundo_liso


def metade_branca_metade_preta(largura: int = 80, altura: int = 40) -> Image.Image:
    imagem = Image.new("RGB", (largura, altura), "black")
    imagem.paste("white", (0, 0, largura // 2, altura))
    return imagem


def test_desfocar_borra_a_fronteira_e_escurece_com_a_cor():
    nitida = metade_branca_metade_preta()

    borrada = desfocar(nitida, cor="#000000", opacidade=0.0)
    meio = borrada.getpixel((40, 20))
    assert 40 < meio[0] < 215, "a fronteira branco/preto virou cinza"
    assert borrada.getpixel((4, 20))[0] > 200 and borrada.getpixel((76, 20))[0] < 55

    so_a_cor = desfocar(nitida, cor="#0e0e10", opacidade=1.0)
    assert {so_a_cor.getpixel((x, 20)) for x in (4, 40, 76)} == {(14, 14, 16)}

    escura = desfocar(nitida, cor="#000000", opacidade=0.8)
    assert escura.getpixel((4, 20))[0] < 60


def test_os_cantos_de_fora_vao_na_cor_chave_quando_ha_raio():
    imagem = desfocar(fundo_liso(60, 40, "#ffffff"), cor="#ffffff", opacidade=1.0, raio_dos_cantos=10, cor_de_fora="#010203")

    assert imagem.getpixel((0, 0)) == (1, 2, 3)
    assert imagem.getpixel((59, 39)) == (1, 2, 3)
    assert imagem.getpixel((30, 20)) == (255, 255, 255)
    assert imagem.getpixel((30, 0)) == (255, 255, 255)


def test_cor_media_da_faixa():
    assert cor_media(metade_branca_metade_preta(), (0, 0, 80, 40)) in {"#7f7f7f", "#808080"}
    assert cor_media(metade_branca_metade_preta(), (0, 0, 40, 40)) == "#ffffff"


@pytest.mark.skipif(sys.platform != "win32", reason="captura do DC da tela é do Windows")
def test_capturar_atras_devolve_a_regiao_pedida():
    imagem = capturar_atras(0, 0, 32, 16)

    assert imagem.size == (32, 16) and imagem.mode == "RGB"
