"""A bandeja: casca fina sobre o coletor.

O ícone de verdade só existe rodando no Windows, com a bandeja na tela — isso é
smoke manual, como a spec decidiu. O que dá para provar aqui é tudo o que não
depende de pixels na tela do usuário: que o clique chega ao coletor, que cada
estado vira um desenho e um texto distintos, que uma falha aparece como balão
com o comando de recuperação, e que a bandeja não conhece pipeline nenhum.

O ícone é injetado — um dublê que só guarda o que a bandeja mandou desenhar.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from second_brain import bandeja as _bandeja
from second_brain.bandeja import Bandeja, desenhar_icone
from second_brain.coletor import Coletor, Estado, Situacao
from second_brain.configuracao import Configuracao
from second_brain.fakes import ResumoFake, STTFake
from second_brain.portas import ErroDeSTT
from test_coletor import GravadorDublê, STTQuebrado


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


@pytest.fixture
def montar(configuracao: Configuracao, caminho_das_gravacoes: Path, icone: IconeDublê):
    """Uma bandeja ligada a um coletor síncrono, com o ícone dublê."""

    def construir(*, stt=None, resumo=None):
        coletor = Coletor(
            configuracao,
            portas=lambda: (stt or STTFake(), resumo or ResumoFake()),
            gravador=GravadorDublê(caminho_das_gravacoes),
            em_segundo_plano=False,
        )
        return Bandeja(coletor, icone=icone), coletor

    return construir


# -- o clique ---------------------------------------------------------------


def test_o_clique_comeca_e_termina_a_gravacao(montar):
    bandeja, coletor = montar()

    bandeja.alternar()
    assert coletor.estado is Estado.GRAVANDO

    bandeja.alternar()
    assert coletor.estado is Estado.PARADO
    assert coletor.situacao().nota is not None


def test_um_gesto_impossivel_vira_aviso_em_vez_de_derrubar_a_bandeja(
    montar, icone: IconeDublê, monkeypatch: pytest.MonkeyPatch
):
    bandeja, coletor = montar()
    monkeypatch.setattr(
        coletor, "iniciar", lambda *a, **k: (_ for _ in ()).throw(ErroDeSTT("sem microfone"))
    )

    bandeja.alternar()  # não levanta

    assert ("Não deu para começar", "sem microfone") in icone.notificacoes


# -- o estado na tela -------------------------------------------------------


def test_cada_estado_tem_um_desenho_proprio():
    """Cor sozinha é ambígua: os quatro ícones precisam diferir como imagem."""
    desenhos = {estado: desenhar_icone(estado).tobytes() for estado in Estado}

    assert len(set(desenhos.values())) == len(Estado)


def test_o_tooltip_diz_o_estado_em_portugues(montar, icone: IconeDublê):
    bandeja, coletor = montar()
    bandeja.atualizar(coletor.situacao())
    assert "Parado" in icone.title

    bandeja.alternar()
    assert "Gravando" in icone.title

    bandeja.alternar()
    assert "Última nota" in icone.title


def test_o_icone_e_repintado_a_cada_transicao(montar, icone: IconeDublê):
    bandeja, _coletor = montar()
    parado = desenhar_icone(Estado.PARADO).tobytes()
    gravando = desenhar_icone(Estado.GRAVANDO).tobytes()

    bandeja.alternar()
    assert icone.icon.tobytes() == gravando

    bandeja.alternar()
    assert icone.icon.tobytes() == parado


def test_o_rotulo_do_menu_acompanha_o_estado(montar):
    bandeja, _coletor = montar()
    assert bandeja._rotulo_do_gesto() == "Gravar reunião"

    bandeja.alternar()

    assert bandeja._rotulo_do_gesto() == "Parar e processar"


# -- falhas visíveis --------------------------------------------------------


def test_a_falha_vira_balao_com_o_comando_de_recuperacao(montar, icone: IconeDublê):
    bandeja, _coletor = montar(stt=STTQuebrado())

    bandeja.alternar()
    bandeja.alternar()

    titulo, mensagem = icone.notificacoes[-1]
    assert titulo == "A reunião não virou nota"
    assert "Deepgram fora do ar" in mensagem
    assert "reprocessar" in mensagem


def test_a_falha_pinta_o_icone_de_erro(montar, icone: IconeDublê):
    bandeja, _coletor = montar(stt=STTQuebrado())

    bandeja.alternar()
    bandeja.alternar()

    assert icone.icon.tobytes() == desenhar_icone(Estado.ERRO).tobytes()


def test_o_sucesso_avisa_uma_vez_por_reuniao(montar, icone: IconeDublê):
    bandeja, coletor = montar()

    bandeja.alternar()
    bandeja.alternar()
    avisos = [n for n in icone.notificacoes if n[0] == "Reunião no vault"]
    assert len(avisos) == 1

    bandeja.atualizar(coletor.situacao())  # repintar não republica a mesma nota

    assert len([n for n in icone.notificacoes if n[0] == "Reunião no vault"]) == 1


# -- sair -------------------------------------------------------------------


def test_sair_processa_a_reuniao_em_andamento_antes_de_fechar(
    montar, icone: IconeDublê, caminho_do_vault: Path
):
    bandeja, _coletor = montar()
    bandeja.alternar()

    bandeja.sair()

    assert icone.parou
    assert not icone.visible
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


# -- casca fina -------------------------------------------------------------


def test_a_bandeja_nao_conhece_o_pipeline():
    """Critério da spec: nenhuma lógica de pipeline vive na bandeja.

    O módulo não pode importar o pipeline, o vault, os adaptadores nem as
    portas: quem processa é o coletor, chamando a costura única. Se um dia
    alguém "resolver rápido" um ajuste de nota aqui dentro, este teste cai.
    """
    fonte = inspect.getsource(_bandeja)

    for proibido in ("pipeline", "vault", "stt_deepgram", "resumo_claude", "gravacao"):
        assert f"import {proibido}" not in fonte
        assert f"from .{proibido}" not in fonte


def test_o_log_da_bandeja_fica_ao_lado_da_configuracao(configuracao: Configuracao):
    """Sem console, o log é a única forma de diagnosticar a reunião de ontem."""
    destino = _bandeja.arquivo_de_log(configuracao)

    assert destino.parent == configuracao.origem.parent
    assert destino.name == "bandeja.log"


# -- gravação saindo torta --------------------------------------------------


def test_o_canal_mudo_vira_balao_com_o_conserto(montar, icone: IconeDublê):
    """Avisar durante a reunião é o que dá tempo de consertar."""
    bandeja, coletor = montar()
    bandeja.alternar()

    bandeja.atualizar(
        Situacao(estado=Estado.GRAVANDO, aviso="só a sua voz está entrando; a dos outros, não")
    )

    titulo, mensagem = icone.notificacoes[-1]
    assert titulo == "A gravação está saindo incompleta"
    assert "dispositivo_sistema" in mensagem
    assert "só a sua voz" in icone.title


def test_o_mesmo_aviso_nao_e_repetido(montar, icone: IconeDublê):
    bandeja, _coletor = montar()
    situacao = Situacao(estado=Estado.GRAVANDO, aviso="só a sua voz está entrando; a dos outros, não")

    bandeja.atualizar(situacao)
    bandeja.atualizar(situacao)

    incompletas = [n for n in icone.notificacoes if n[0] == "A gravação está saindo incompleta"]
    assert len(incompletas) == 1
