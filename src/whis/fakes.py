"""Fakes das portas: implementações de verdade que devolvem dados fixos.

Não são mocks — não são interrogados sobre como foram chamados. São os
adaptadores que os testes (e o `--fakes` da CLI) injetam no lugar da Deepgram,
do Claude, do git, do Linear e do Slack. Os testes verificam só o que aparece
no vault.

As exceções são `ResumoDoDiaFake`, `DailyFake` e `BuscaFake`, que guardam o
que receberam: o filtro de exclusão e a pasta privada prometem que o conteúdo
excluído **não sai da máquina**, e a única forma de provar isso é olhar o que
chegou à porta.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable
from dataclasses import replace
from datetime import date, datetime, time

from .atendente import Mensagem
from .busca import Citacao, Resposta
from .conversa import Turno
from .ferramentas import Ferramentas
from .fontes import Evento, Janela
from .portas import (
    EU,
    OUTROS,
    CanaisDaGravacao,
    Daily,
    Fala,
    Resumo,
    ResumoDoDia,
    Transcricao,
)

#: Transcrição de exemplo — pt-BR com termos em inglês, como as reuniões reais.
TRANSCRICAO_PADRAO = Transcricao(
    falas=(
        Fala(EU, "Bom dia, pessoal. Vamos começar pela daily?", 0.0),
        Fala(OUTROS, "Bom dia! Ontem terminei o deploy do pipeline novo.", 3.2),
        Fala(EU, "Fechado. Então o rollback fica pra depois do review.", 9.8),
        Fala(OUTROS, "Combinado, eu abro a issue ainda hoje.", 14.1),
    ),
)

#: Resumo de exemplo, na estrutura que a nota de reunião espera.
RESUMO_PADRAO = Resumo(
    decisoes=("O rollback fica para depois do review.",),
    acoes=("Abrir a issue do rollback ainda hoje.",),
    topicos=("Deploy do pipeline novo", "Planejamento do rollback"),
)

#: O dia a que os eventos de exemplo pertencem; `FonteDeExemplo` os transporta.
DATA_DE_EXEMPLO = date(2026, 9, 3)


def _momento(hora: int, minuto: int) -> datetime:
    return datetime.combine(DATA_DE_EXEMPLO, time(hora, minuto)).astimezone()


#: Eventos de exemplo do git, no formato que o coletor da camada 02 devolverá.
EVENTOS_DE_GIT = (
    Evento(
        fonte="git",
        momento=_momento(9, 12),
        titulo="`a1b2c3d` Fecha a camada 01 do diario",
        referencia="whis",
        pessoas=("Gabriel",),
    ),
    Evento(
        fonte="git",
        momento=_momento(17, 45),
        titulo="`d4e5f6a` Corrige o calculo de frete no checkout",
        referencia="loja",
        pessoas=("Gabriel",),
    ),
)

#: Eventos de exemplo do Linear, com url e comentário, para exercitar o formato.
EVENTOS_DE_LINEAR = (
    Evento(
        fonte="linear",
        momento=_momento(11, 20),
        titulo="FN-123 Corrigir o cálculo de frete — movida para Done",
        detalhe="Subiu em produção; falta acompanhar o gráfico de erros.",
        referencia="Plataforma",
        url="https://linear.app/exemplo/issue/FN-123",
        pessoas=("Gabriel", "Ana"),
    ),
    Evento(
        fonte="linear",
        momento=_momento(14, 2),
        titulo="FN-130 Diário automático — comentário",
        detalhe="Combinamos gerar o diário às 19:00, com a máquina ligada.",
        referencia="Plataforma",
        url="https://linear.app/exemplo/issue/FN-130",
        pessoas=("Ana",),
    ),
)

#: Resumo do dia de exemplo, na estrutura que o diário espera.
RESUMO_DO_DIA_PADRAO = ResumoDoDia(
    narrativa=(
        "Dia dividido entre fechar a camada do diário e apagar um incêndio no "
        "checkout. A correção do frete saiu do Linear para produção no mesmo dia."
    ),
    destaques=(
        "A camada 01 do diário foi fechada.",
        "O cálculo de frete foi corrigido e subiu.",
    ),
    pendencias=("Acompanhar o gráfico de erros do checkout.",),
    temas=("fontes passivas", "checkout"),
)

#: Roteiro de daily de exemplo, na estrutura que a nota da daily espera.
DAILY_PADRAO = Daily(
    entreguei=(
        "Fechei a camada 01 do diário.",
        "Corrigi o cálculo de frete do checkout e subi para produção.",
    ),
    sigo_em=("Sigo no coletor de git, que ficou pela metade.",),
    preciso_de=("Preciso do review da Ana na FN-123 para fechar.",),
    duvidas=("Vale mesmo gerar o diário às 19:00 com a máquina ligada?",),
)


class STTFake:
    """Porta de STT que devolve sempre a mesma transcrição.

    `erro` faz a transcrição falhar — é a costura de que as camadas 03 e 06
    precisam para os casos de falha; a camada 01 não os exercita.
    """

    def __init__(
        self,
        transcricao: Transcricao = TRANSCRICAO_PADRAO,
        erro: Exception | None = None,
    ) -> None:
        self._transcricao = transcricao
        self._erro = erro

    def transcrever(self, canais: CanaisDaGravacao) -> Transcricao:
        if self._erro is not None:
            raise self._erro
        return self._transcricao


class ResumoFake:
    """Porta de resumo que devolve sempre o mesmo resumo em português."""

    def __init__(self, resumo: Resumo = RESUMO_PADRAO, erro: Exception | None = None) -> None:
        self._resumo = resumo
        self._erro = erro

    def resumir(self, transcricao: Transcricao, titulo: str | None = None) -> Resumo:
        if self._erro is not None:
            raise self._erro
        return self._resumo


class FonteFake:
    """Fonte passiva que devolve eventos fixos, recortados pela janela.

    Recorta como uma fonte de verdade recortaria — filtrar por tempo é da
    fonte, pelo contrato —, e é isso que torna a janela do dia testável pelo
    comportamento. `erro` faz a coleta falhar, para exercitar a degradação
    graciosa sem depender de rede.
    """

    def __init__(
        self,
        nome: str = "git",
        eventos: tuple[Evento, ...] = (),
        erro: Exception | None = None,
    ) -> None:
        self.nome = nome
        self._eventos = tuple(eventos)
        self._erro = erro

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        if self._erro is not None:
            raise self._erro
        return tuple(
            evento for evento in self._eventos if janela.contem(evento.momento)
        )


class FonteDeExemplo:
    """Fonte fake que traz seus eventos de exemplo para a janela pedida.

    Sem isso `whis diario --fakes` só produziria nota no dia em que os
    exemplos foram escritos: em qualquer outra data eles cairiam fora da janela
    e o dia seria vazio.
    """

    def __init__(self, nome: str, eventos: tuple[Evento, ...]) -> None:
        self.nome = nome
        self._eventos = tuple(eventos)

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        do_dia = (_transportar(evento, janela.data) for evento in self._eventos)
        return tuple(evento for evento in do_dia if janela.contem(evento.momento))


class FonteDaJanela:
    """Fonte fake que espalha seus eventos ao longo da janela pedida.

    A janela da daily não é um dia civil: ela começa quando a última daily
    terminou, e um evento preso a um horário fixo cairia fora dela em quase
    toda execução. Espalhar é o que faz `daily --fakes` mostrar sempre um
    período plausível, seja ele de duas horas ou de um fim de semana.
    """

    def __init__(self, nome: str, eventos: tuple[Evento, ...]) -> None:
        self.nome = nome
        self._eventos = tuple(eventos)

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        duracao = janela.fim - janela.inicio
        passo = duracao / (len(self._eventos) + 1)
        return tuple(
            replace(evento, momento=janela.inicio + passo * (posicao + 1))
            for posicao, evento in enumerate(self._eventos)
        )


def fontes_de_exemplo() -> list[FonteDeExemplo]:
    """As fontes que o `--fakes` do diário injeta: git e Linear num dia plausível."""
    return [
        FonteDeExemplo("git", EVENTOS_DE_GIT),
        FonteDeExemplo("linear", EVENTOS_DE_LINEAR),
    ]


def fontes_de_exemplo_da_daily() -> list[FonteDaJanela]:
    """As fontes que o `--fakes` da daily injeta, cabendo em qualquer janela."""
    return [
        FonteDaJanela("git", EVENTOS_DE_GIT),
        FonteDaJanela("linear", EVENTOS_DE_LINEAR),
    ]


class ResumoDoDiaFake:
    """Porta de resumo do dia que devolve sempre o mesmo resumo em português.

    Guarda em `eventos_recebidos` e `reunioes_recebidas` o que lhe entregaram:
    é assim que o teste do filtro de exclusão prova que o conteúdo excluído
    nunca chegou perto de sair da máquina.
    """

    def __init__(
        self,
        resumo: ResumoDoDia = RESUMO_DO_DIA_PADRAO,
        erro: Exception | None = None,
    ) -> None:
        self._resumo = resumo
        self._erro = erro
        self.eventos_recebidos: tuple[Evento, ...] = ()
        self.reunioes_recebidas: tuple[str, ...] = ()

    def resumir_dia(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> ResumoDoDia:
        self.eventos_recebidos = tuple(eventos)
        self.reunioes_recebidas = tuple(reunioes)
        if self._erro is not None:
            raise self._erro
        return self._resumo


class DailyFake:
    """Porta de daily que devolve sempre o mesmo roteiro em português.

    Guarda o que recebeu pelo mesmo motivo que `ResumoDoDiaFake`: é assim que o
    teste do filtro de exclusão prova que o conteúdo excluído nunca chegou
    perto de sair da máquina.
    """

    def __init__(
        self, roteiro: Daily = DAILY_PADRAO, erro: Exception | None = None
    ) -> None:
        self._roteiro = roteiro
        self._erro = erro
        self.eventos_recebidos: tuple[Evento, ...] = ()
        self.reunioes_recebidas: tuple[str, ...] = ()

    def resumir_daily(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> Daily:
        self.eventos_recebidos = tuple(eventos)
        self.reunioes_recebidas = tuple(reunioes)
        if self._erro is not None:
            raise self._erro
        return self._roteiro


#: Resposta de exemplo, citando uma nota como o adaptador real citaria.
RESPOSTA_PADRAO = Resposta(
    texto="A retenção ficou em 180 dias, decidida na reunião de 3 de setembro.",
    citacoes=(
        Citacao("reunioes/2026-09-03-1403-reuniao.md", "retenção de 180 dias"),
    ),
)


class BuscaFake:
    """Porta de busca que devolve sempre a mesma resposta.

    Guarda a pergunta, as ferramentas e o histórico que recebeu: é assim que a
    costura prova o que **não** chegou ao Claude — a pergunta vazia, o fio
    expirado — e, pelas próprias ferramentas recebidas, que a pasta privada
    está fora do alcance de quem responde.
    """

    def __init__(
        self, resposta: Resposta = RESPOSTA_PADRAO, erro: Exception | None = None
    ) -> None:
        self._resposta = resposta
        self._erro = erro
        self.perguntas_recebidas: list[str] = []
        self.ferramentas_recebidas: Ferramentas | None = None
        self.historico_recebido: tuple[Turno, ...] = ()

    def perguntar(
        self,
        pergunta: str,
        ferramentas: Ferramentas,
        historico: tuple[Turno, ...] = (),
    ) -> Resposta:
        self.perguntas_recebidas.append(pergunta)
        self.ferramentas_recebidas = ferramentas
        self.historico_recebido = tuple(historico)
        if self._erro is not None:
            raise self._erro
        return self._resposta


class DMFake:
    """A DM do bot sem Slack: entrega as mensagens de fixture e guarda o que saiu.

    Quando a fila esvazia, sinaliza `parar` — ou, sem ele, levanta
    `KeyboardInterrupt`, que é como o atendente de verdade é encerrado. Os
    erros injetáveis existem para provar que nenhum deles derruba o laço.
    """

    def __init__(
        self,
        mensagens: Iterable[Mensagem] = (),
        *,
        eu: str = "U0BOT",
        parar: threading.Event | None = None,
        erro_ao_iniciar: Exception | None = None,
        erro_ao_reagir: Exception | None = None,
        erro_ao_responder: Exception | None = None,
    ) -> None:
        self._fila = deque(mensagens)
        self.eu = eu
        self.parar = parar
        self._erro_ao_iniciar = erro_ao_iniciar
        self._erro_ao_reagir = erro_ao_reagir
        self._erro_ao_responder = erro_ao_responder
        self.iniciada = False
        self.encerrada = False
        self.reacoes: list[tuple[Mensagem, str]] = []
        self.respostas: list[tuple[Mensagem, str]] = []

    def iniciar(self) -> str:
        if self._erro_ao_iniciar is not None:
            raise self._erro_ao_iniciar
        self.iniciada = True
        return self.eu

    def proxima(self, timeout_s: float) -> Mensagem | None:
        if self._fila:
            return self._fila.popleft()
        if self.parar is not None:
            self.parar.set()
            return None
        raise KeyboardInterrupt

    def reagir(self, mensagem: Mensagem, emoji: str) -> None:
        if self._erro_ao_reagir is not None:
            raise self._erro_ao_reagir
        self.reacoes.append((mensagem, emoji))

    def responder(self, mensagem: Mensagem, texto: str) -> None:
        if self._erro_ao_responder is not None:
            raise self._erro_ao_responder
        self.respostas.append((mensagem, texto))

    def encerrar(self) -> None:
        self.encerrada = True


def _transportar(evento: Evento, dia: date) -> Evento:
    return replace(evento, momento=datetime.combine(dia, evento.momento.time()).astimezone())
