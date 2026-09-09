"""O coletor: o gesto liga/desliga e a nota que aparece no vault.

A mesma costura de sempre — `processar(pasta) → arquivos no vault` — vista pelo
lado de quem clica. O gravador é substituído por um dublê que produz uma pasta
de gravação de fixture, porque captura WASAPI é hardware e fica fora da costura
por decisão da spec; STT e resumo continuam sendo as portas fake.

O que estes testes provam é exatamente o que a bandeja promete ao usuário:
parar dispara o processamento sozinho, o estado é sempre legível, e uma falha
nunca é engolida — vira estado de erro com a gravação preservada.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from fixtures.gravacao import criar_pasta_de_gravacao
from whis.coletor import Coletor, ErroDoColetor, Estado, Situacao
from whis.configuracao import Configuracao
from whis.fakes import ResumoFake, STTFake
from whis.gravacao import STATUS_FALHOU, STATUS_TRANSCRITO, ler_estado
from whis.portas import ErroDeResumo, ErroDeSTT


class GravadorDublê:
    """Um gravador que não toca no áudio: cria a pasta que o de verdade criaria.

    A camada 02 é validada por smoke manual (spec); aqui o que importa é o
    contrato entre gravador e coletor — `iniciar()` devolve uma pasta,
    `parar()` devolve a mesma pasta pronta para o pipeline.
    """

    def __init__(self, gravacoes: Path, nome: str = "2026-08-20-1430-daily-do-time"):
        self._gravacoes = gravacoes
        self._nome = nome
        self.pasta: Path | None = None
        self.gravando = False
        self.paradas = 0

    def iniciar(self, titulo: str | None = None) -> Path:
        self.gravando = True
        self.pasta = criar_pasta_de_gravacao(self._gravacoes, nome=self._nome, titulo=titulo)
        return self.pasta

    def parar(self) -> Path:
        self.gravando = False
        self.paradas += 1
        assert self.pasta is not None
        return self.pasta


class STTQuebrado:
    def transcrever(self, canais):
        raise ErroDeSTT("Deepgram fora do ar")


class ResumoQuebrado:
    def resumir(self, transcricao, titulo=None):
        raise ErroDeResumo("Claude sobrecarregado")


@pytest.fixture
def gravador(caminho_das_gravacoes: Path) -> GravadorDublê:
    return GravadorDublê(caminho_das_gravacoes)


@pytest.fixture
def montar(configuracao: Configuracao, gravador: GravadorDublê):
    """Monta um coletor síncrono — o processamento acontece dentro de `parar()`."""

    def construir(*, stt=None, resumo=None, ao_mudar=None, em_segundo_plano=False):
        return Coletor(
            configuracao,
            portas=lambda: (stt or STTFake(), resumo or ResumoFake()),
            gravador=gravador,
            ao_mudar=ao_mudar,
            em_segundo_plano=em_segundo_plano,
        )

    return construir


# -- o gesto ----------------------------------------------------------------


def test_parar_a_gravacao_faz_a_nota_aparecer_no_vault(montar, caminho_do_vault: Path):
    coletor = montar()

    coletor.iniciar("daily do time")
    coletor.parar()

    nota = caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md"
    transcricao = caminho_do_vault / "transcricoes" / "2026-08-20-1430-daily-do-time.md"
    assert nota.is_file()
    assert transcricao.is_file()
    assert coletor.estado is Estado.PARADO


def test_nenhum_passo_manual_entre_parar_e_a_nota(montar):
    """O critério da spec: parar dispara o processamento sozinho."""
    coletor = montar()
    coletor.iniciar()

    coletor.parar()

    assert coletor.situacao().nota is not None


def test_alternar_grava_e_para_com_o_mesmo_gesto(montar, gravador: GravadorDublê):
    coletor = montar()

    coletor.alternar()
    assert coletor.estado is Estado.GRAVANDO
    assert gravador.gravando

    coletor.alternar()
    assert coletor.estado is Estado.PARADO
    assert gravador.paradas == 1


def test_estado_do_coletor_e_legivel_em_portugues(montar):
    coletor = montar()
    assert "Clique para gravar" in coletor.situacao().descricao()

    coletor.iniciar("daily do time")
    assert coletor.situacao().descricao() == "Gravando: daily do time"

    coletor.parar()
    assert "Última nota" in coletor.situacao().descricao()


def test_gravar_duas_vezes_e_recusado_com_mensagem(montar):
    coletor = montar()
    coletor.iniciar()

    with pytest.raises(ErroDoColetor, match="em andamento"):
        coletor.iniciar()


def test_parar_sem_gravar_e_recusado_com_mensagem(montar):
    with pytest.raises(ErroDoColetor, match="não há gravação"):
        montar().parar()


# -- as transições que a bandeja desenha ------------------------------------


def test_cada_transicao_avisa_a_interface(montar):
    vistos: list[Estado] = []
    coletor = montar(ao_mudar=lambda situacao: vistos.append(situacao.estado))

    coletor.iniciar()
    coletor.parar()

    assert vistos == [Estado.GRAVANDO, Estado.PROCESSANDO, Estado.PARADO]


def test_interface_quebrada_nao_derruba_a_reuniao(montar, caminho_do_vault: Path):
    """Um erro ao repintar o ícone não pode custar a reunião do usuário."""

    def interface_quebrada(_situacao: Situacao) -> None:
        raise RuntimeError("a bandeja explodiu")

    coletor = montar(ao_mudar=interface_quebrada)

    coletor.iniciar()
    coletor.parar()

    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


# -- falhas: a bandeja não engole nada --------------------------------------


def test_falha_do_stt_vira_estado_de_erro_com_a_mensagem(montar):
    coletor = montar(stt=STTQuebrado())

    coletor.iniciar()
    coletor.parar()

    situacao = coletor.situacao()
    assert situacao.estado is Estado.ERRO
    assert "Deepgram fora do ar" in situacao.erro
    assert "Deepgram fora do ar" in situacao.descricao()


def test_falha_do_resumo_vira_estado_de_erro(montar):
    coletor = montar(resumo=ResumoQuebrado())

    coletor.iniciar()
    coletor.parar()

    assert coletor.estado is Estado.ERRO
    assert "Claude sobrecarregado" in coletor.situacao().erro


def test_falha_preserva_a_gravacao_para_o_reprocesso(
    montar, gravador: GravadorDublê, caminho_do_vault: Path
):
    coletor = montar(stt=STTQuebrado())

    coletor.iniciar()
    coletor.parar()

    assert gravador.pasta is not None
    assert (gravador.pasta / "microfone.wav").is_file()
    assert ler_estado(gravador.pasta).status == STATUS_FALHOU
    assert not (caminho_do_vault / "reunioes").exists() or not list(
        (caminho_do_vault / "reunioes").glob("*.md")
    )


def test_a_reuniao_seguinte_limpa_o_erro_da_anterior(montar):
    coletor = montar(stt=STTQuebrado())
    coletor.iniciar()
    coletor.parar()
    assert coletor.estado is Estado.ERRO

    coletor.iniciar()

    assert coletor.estado is Estado.GRAVANDO
    assert coletor.situacao().erro is None


def test_reconhecer_o_erro_volta_ao_parado_sem_apagar_nada(
    montar, gravador: GravadorDublê
):
    coletor = montar(stt=STTQuebrado())
    coletor.iniciar()
    coletor.parar()

    coletor.reconhecer_erro()

    assert coletor.estado is Estado.PARADO
    assert gravador.pasta is not None and gravador.pasta.is_dir()
    assert ler_estado(gravador.pasta).status == STATUS_FALHOU


# -- em segundo plano -------------------------------------------------------


def test_processamento_roda_fora_da_thread_da_interface(montar, caminho_do_vault: Path):
    """`parar()` devolve o controle na hora; a nota chega depois."""
    coletor = montar(em_segundo_plano=True)
    coletor.iniciar()

    coletor.parar()
    assert coletor.aguardar(timeout=30)

    assert coletor.estado is Estado.PARADO
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


def test_encerrar_processa_a_reuniao_em_andamento(montar, caminho_do_vault: Path):
    """Sair pela bandeja no meio de uma reunião não descarta a gravação."""
    coletor = montar(em_segundo_plano=True)
    coletor.iniciar()

    coletor.encerrar()

    assert coletor.estado is Estado.PARADO
    assert (caminho_do_vault / "reunioes" / "2026-08-20-1430-daily-do-time.md").is_file()


def test_encerrar_parado_nao_faz_nada(montar):
    coletor = montar(em_segundo_plano=True)

    coletor.encerrar()

    assert coletor.estado is Estado.PARADO


# -- zona de propriedade ----------------------------------------------------


def test_o_coletor_nao_escreve_fora_das_zonas_do_agente(montar, caminho_do_vault: Path):
    (caminho_do_vault / "notas").mkdir(parents=True)
    minha = caminho_do_vault / "notas" / "minha-nota.md"
    minha.write_text("nota manual\n", encoding="utf-8")

    coletor = montar()
    coletor.iniciar()
    coletor.parar()

    assert minha.read_text(encoding="utf-8") == "nota manual\n"
    escritos = {caminho.parent.name for caminho in caminho_do_vault.rglob("*.md")}
    assert escritos <= {"reunioes", "transcricoes", "notas"}


def test_gravacao_bem_sucedida_fica_marcada_como_transcrita(
    montar, gravador: GravadorDublê
):
    coletor = montar()
    coletor.iniciar()
    coletor.parar()

    assert gravador.pasta is not None
    assert ler_estado(gravador.pasta).status == STATUS_TRANSCRITO


# -- canal mudo: a reunião saindo torta sem estar falhando -------------------


class GravadorComNiveis(GravadorDublê):
    """Um gravador cujo canal de sistema não recebe nada — o caso do fone."""

    def __init__(self, gravacoes: Path, niveis: dict[str, float]):
        super().__init__(gravacoes)
        self._niveis = niveis

    def niveis(self) -> dict[str, float]:
        return dict(self._niveis)


@pytest.mark.parametrize(
    ("niveis", "trecho"),
    [
        ({"microfone": 120.0, "sistema": 0.0}, "só a sua voz"),
        ({"microfone": 0.0, "sistema": 300.0}, "microfone não está entrando"),
        ({"microfone": 0.0, "sistema": 0.0}, "nenhum áudio"),
    ],
)
def test_canal_mudo_durante_a_gravacao_vira_aviso(
    configuracao: Configuracao, caminho_das_gravacoes: Path, niveis, trecho
):
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorComNiveis(caminho_das_gravacoes, niveis),
        em_segundo_plano=False,
    )
    coletor.iniciar()

    assert trecho in coletor.conferir_canais()


def test_canais_saudaveis_nao_geram_aviso(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorComNiveis(
            caminho_das_gravacoes, {"microfone": 120.0, "sistema": 400.0}
        ),
        em_segundo_plano=False,
    )
    coletor.iniciar()

    assert coletor.conferir_canais() is None


def test_o_aviso_aparece_na_situacao_e_no_texto_da_bandeja(
    configuracao: Configuracao, caminho_das_gravacoes: Path
):
    """A vigilância roda sozinha durante a gravação, sem esperar o fim dela."""
    vistos: list[str | None] = []
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorComNiveis(
            caminho_das_gravacoes, {"microfone": 120.0, "sistema": 0.0}
        ),
        ao_mudar=lambda situacao: vistos.append(situacao.aviso),
        em_segundo_plano=True,
        segundos_ate_conferir_canais=0.05,
    )

    coletor.iniciar("daily do time")
    for _ in range(100):  # a vigília é outra thread; espera o aviso chegar
        if coletor.situacao().aviso:
            break
        time.sleep(0.02)

    situacao = coletor.situacao()
    assert situacao.estado is Estado.GRAVANDO  # avisar não é falhar
    assert "só a sua voz" in situacao.aviso
    assert "só a sua voz" in situacao.descricao()
    assert vistos[-1] == situacao.aviso


def test_gravador_sem_niveis_nao_quebra_a_vigilancia(montar):
    """O dublê da camada 02 pode não expor `niveis()` — isso não é erro."""
    coletor = montar()
    coletor.iniciar()

    assert coletor.conferir_canais() is None


def test_parar_limpa_o_aviso(configuracao: Configuracao, caminho_das_gravacoes: Path):
    coletor = Coletor(
        configuracao,
        portas=lambda: (STTFake(), ResumoFake()),
        gravador=GravadorComNiveis(
            caminho_das_gravacoes, {"microfone": 120.0, "sistema": 0.0}
        ),
        em_segundo_plano=False,
    )
    coletor.iniciar()

    coletor.parar()

    assert coletor.situacao().aviso is None
