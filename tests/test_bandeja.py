"""A bandeja: o ícone que hospeda a palheta.

O ícone de verdade só existe rodando no Windows, com a bandeja na tela — isso é
smoke manual. O que dá para provar aqui é o menu como dados: o clique esquerdo
abre a palheta, e sair desliga o ícone e quem o hospeda.

O ícone é injetado — um dublê que só guarda o que a bandeja mandou fazer.
"""

from __future__ import annotations

import pytest

from whis import bandeja as _bandeja
from whis import registro
from whis.bandeja import TAMANHO, Bandeja, desenhar_icone
from whis.configuracao import Configuracao


class IconeDublê:
    """Guarda o que a bandeja pediu para desenhar e notificar."""

    def __init__(self) -> None:
        self.icon = None
        self.title = ""
        self.visible = True
        self.rodou = False
        self.parou = False
        self.notificacoes: list[tuple[str, str]] = []
        self.menus_atualizados = 0

    def run(self) -> None:
        self.rodou = True

    def stop(self) -> None:
        self.parou = True

    def notify(self, mensagem: str, titulo: str) -> None:
        self.notificacoes.append((titulo, mensagem))

    def update_menu(self) -> None:
        self.menus_atualizados += 1


@pytest.fixture
def icone() -> IconeDublê:
    return IconeDublê()


def test_o_clique_esquerdo_abre_a_palheta(icone: IconeDublê):
    abertos: list[str] = []
    bandeja = Bandeja(icone=icone, abrir_palheta=lambda: abertos.append("palheta"))

    [padrao] = [item for item in bandeja.itens_do_menu() if item.padrao]
    padrao.acao()

    assert padrao.rotulo == "Abrir a palheta"
    assert abertos == ["palheta"]


def test_sem_quem_a_hospede_o_menu_so_tem_sair(icone: IconeDublê):
    itens = Bandeja(icone=icone).itens_do_menu()

    assert [item.rotulo for item in itens] == ["Sair"]
    assert not any(item.padrao for item in itens)


def test_sair_esconde_o_icone_e_avisa_quem_hospeda(icone: IconeDublê):
    encerrados: list[str] = []
    bandeja = Bandeja(icone=icone, ao_sair=lambda: encerrados.append("atalho e janela"))

    bandeja.sair()

    assert icone.parou and not icone.visible
    assert encerrados == ["atalho e janela"]


def test_o_icone_e_um_circulo_do_tamanho_da_bandeja():
    imagem = desenhar_icone()

    assert imagem.size == (TAMANHO, TAMANHO)
    assert imagem.mode == "RGBA"
    assert imagem.getpixel((TAMANHO // 2, TAMANHO // 2))[3] == 0  # vazado no meio


def test_o_log_da_bandeja_fica_ao_lado_da_configuracao(configuracao: Configuracao):
    """Sem console, o log é a única forma de diagnosticar o que aconteceu."""
    destino = _bandeja.arquivo_de_log(configuracao)
    assert destino == registro.arquivo_de_log(configuracao)  # a bandeja delega

    assert destino.parent == configuracao.origem.parent
    assert destino.name == "bandeja.log"
