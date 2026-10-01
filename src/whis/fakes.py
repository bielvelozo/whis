"""Fakes das portas: implementações de verdade que devolvem dados fixos.

Não são mocks — não são interrogados sobre como foram chamados. São os
adaptadores que os testes (e o `--fakes` da CLI) injetam no lugar do Claude,
do git, do Linear e do Slack. Os testes verificam só o que aparece
no vault.

As exceções são `ResumoDoDiaFake` e `BuscaFake`, que guardam o
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
from pathlib import Path

from .atendente import Mensagem
from .busca import Citacao, Resposta
from .conversa import Turno
from .ferramentas import Ferramentas
from .fontes import Evento, Janela
from .portas import (
    Aula,
    Candidato,
    Escolha,
    Formacao,
    ItemEscolhido,
    Janelas,
    Medida,
    Publicacao,
    ResumoDoDia,
    Reuniao,
    ReuniaoListada,
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


def fontes_de_exemplo() -> list[FonteDeExemplo]:
    """As fontes que o `--fakes` do diário injeta: git e Linear num dia plausível."""
    return [
        FonteDeExemplo("git", EVENTOS_DE_GIT),
        FonteDeExemplo("linear", EVENTOS_DE_LINEAR),
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


#: O que os fakes do jornal dizem ter medido: plausível, com as janelas do plano
#: preenchidas para o cabeçalho da edição ter o que mostrar.
MEDIDA_DO_EDITOR_FAKE = Medida(
    custo_usd=0.40,
    segundos=48.0,
    plano_primeiro=Janelas(cinco_horas=30, sete_dias=60),
    plano_ultimo=Janelas(cinco_horas=31, sete_dias=60),
)
MEDIDA_DA_FORMACAO_FAKE = Medida(
    custo_usd=0.24,
    segundos=95.0,
    plano_primeiro=Janelas(cinco_horas=31, sete_dias=60),
    plano_ultimo=Janelas(cinco_horas=31, sete_dias=61),
)
MEDIDA_DA_PUBLICACAO_FAKE = Medida(
    custo_usd=0.07,
    segundos=32.0,
    plano_primeiro=Janelas(cinco_horas=31, sete_dias=61),
    plano_ultimo=Janelas(cinco_horas=31, sete_dias=61),
)

URL_DO_JORNAL_FAKE = "https://claude.ai/artifact/fake-jornal"
URL_DO_DECK_FAKE = "https://claude.ai/artifact/fake-daily"


class EditorFake:
    """Editor que escolhe os `min` primeiros de cada seção, sem chamar ninguém.

    O título ganha `[fake] ` na frente para a edição denunciar de onde veio; o
    resumo é o do feed. Respeita o teto de 2 itens da mesma fonte por seção e
    devolve até 2 do time. Guarda o que recebeu.
    """

    def __init__(self, medida: Medida = MEDIDA_DO_EDITOR_FAKE, erro: Exception | None = None) -> None:
        self._medida = medida
        self._erro = erro
        self.candidatos_recebidos: dict[str, tuple[Candidato, ...]] = {}
        self.limites_recebidos: dict[str, tuple[int, int]] = {}
        self.time_recebido: tuple[Candidato, ...] = ()

    def escolher(
        self,
        candidatos: dict[str, tuple[Candidato, ...]],
        limites: dict[str, tuple[int, int]],
        time: tuple[Candidato, ...],
    ) -> Escolha:
        self.candidatos_recebidos = dict(candidatos)
        self.limites_recebidos = dict(limites)
        self.time_recebido = tuple(time)
        if self._erro is not None:
            raise self._erro
        secoes = {
            secao: _primeiros_por_fonte(lista, limites.get(secao, (3, 5))[0])
            for secao, lista in candidatos.items()
        }
        return Escolha(secoes=secoes, time=_primeiros_por_fonte(time, 2), medida=self._medida)


def _primeiros_por_fonte(candidatos: Iterable[Candidato], quantos: int) -> tuple[ItemEscolhido, ...]:
    escolhidos: list[ItemEscolhido] = []
    por_fonte: dict[str, int] = {}
    for candidato in candidatos:
        if len(escolhidos) >= quantos:
            break
        if por_fonte.get(candidato.fonte, 0) >= 2:
            continue
        por_fonte[candidato.fonte] = por_fonte.get(candidato.fonte, 0) + 1
        escolhidos.append(
            ItemEscolhido(candidato=candidato, titulo=f"[fake] {candidato.titulo}", resumo=candidato.resumo)
        )
    return tuple(escolhidos)


class FormacaoFake:
    """Formação que ensina sempre as mesmas três aulas: uma de software, duas de carro.

    Cada aula traz uma URL `https://` em `fontes` e a linha da trilha do dia
    recebido. Guarda a data e a trilha que recebeu.
    """

    def __init__(self, medida: Medida = MEDIDA_DA_FORMACAO_FAKE, erro: Exception | None = None) -> None:
        self._medida = medida
        self._erro = erro
        self.data_recebida: date | None = None
        self.trilha_recebida: str | None = None

    def ensinar(self, data: date, trilha: str) -> Formacao:
        self.data_recebida = data
        self.trilha_recebida = trilha
        if self._erro is not None:
            raise self._erro
        dia = data.isoformat()
        return Formacao(
            software=Aula(
                titulo="[fake] Testes de contrato",
                texto=(
                    "Um teste de contrato fixa o que uma porta promete, não como o adaptador "
                    "faz. Por que isso importa: trocar o adaptador não quebra quem o usa."
                ),
                fontes=("https://martinfowler.com/bliki/ContractTest.html",),
                trilha=f"- {dia} — software: testes de contrato",
            ),
            carros=(
                Aula(
                    titulo="[fake] O motor rotativo",
                    texto=(
                        "O Wankel troca pistões por um rotor triangular. Por que isso importa: "
                        "explica o som e a fama do RX-7."
                    ),
                    fontes=("https://en.wikipedia.org/wiki/Wankel_engine",),
                    trilha=f"- {dia} — carros: motor rotativo Wankel",
                ),
                Aula(
                    titulo="[fake] O que é JDM",
                    texto=(
                        "JDM são os carros feitos para o mercado japonês. Por que isso importa: "
                        "é a porta de entrada da cultura que ele começou a acompanhar."
                    ),
                    fontes=("https://en.wikipedia.org/wiki/Japanese_domestic_market",),
                    trilha=f"- {dia} — carros: o que é JDM",
                ),
            ),
            medida=self._medida,
        )


class PublicacaoFake:
    """Publicação que não publica: devolve uma URL fixa e guarda o que recebeu.

    `pagina` é o HTML lido na hora da chamada — a pasta da edição é temporária
    e pode sumir antes de o teste olhar.
    """

    def __init__(
        self,
        url: str = URL_DO_JORNAL_FAKE,
        medida: Medida = MEDIDA_DA_PUBLICACAO_FAKE,
        erro: Exception | None = None,
    ) -> None:
        self._url = url
        self._medida = medida
        self._erro = erro
        self.html: Path | None = None
        self.capas: dict[str, Path] = {}
        self.url_recebida: str | None = None
        self.pagina: str | None = None

    def publicar(self, html: Path, capas: dict[str, Path], url_atual: str | None) -> Publicacao:
        self.html = html
        self.capas = dict(capas)
        self.url_recebida = url_atual
        self.pagina = html.read_text(encoding="utf-8") if html.is_file() else None
        if self._erro is not None:
            raise self._erro
        return Publicacao(url=self._url, medida=self._medida)


class PublicacaoDoDeckFake:
    """Publicação do deck que não publica: guarda o que recebeu e devolve uma URL fixa.

    `conteudos` é lido na hora da chamada, porque a pasta de trabalho é
    temporária. Só os testes a usam: `--fakes` na daily é simulação.
    """

    def __init__(self, url: str = URL_DO_DECK_FAKE, erro: Exception | None = None) -> None:
        self._url = url
        self._erro = erro
        self.chamadas = 0
        self.url_recebida: str | None = None
        self.conteudos: dict[str, str] = {}

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        self.chamadas += 1
        self.url_recebida = url_atual
        self.conteudos = {caminho: (raiz / caminho).read_text(encoding="utf-8") for caminho in arquivos}
        if self._erro is not None:
            raise self._erro
        return Publicacao(url=url_atual or self._url, medida=MEDIDA_DA_PUBLICACAO_FAKE)


#: As reuniões de exemplo da Granola: uma com resumo e uma que ainda não foi resumida.
REUNIOES_DE_EXEMPLO = (
    Reuniao(
        id="00000000-fake-4000-8000-000000000001",
        titulo="Daily do time (exemplo)",
        inicio=_momento(14, 0),
        participantes=("Ana Lima", "Bruno Costa"),
        resumo="# Decisões\n\n- O rollback fica para depois do review.",
        url="https://notes.granola.ai/d/00000000-fake-4000-8000-000000000001",
    ),
    Reuniao(
        id="00000000-fake-4000-8000-000000000002",
        titulo="1:1 (exemplo, ainda sem resumo)",
        inicio=_momento(16, 30),
        url="https://notes.granola.ai/d/00000000-fake-4000-8000-000000000002",
    ),
)


class ReunioesFake:
    """A Granola sem rede: lista e detalha `reunioes`, e guarda os lotes pedidos.

    `erro_ao_listar` derruba a lista; `erro_no_lote` derruba o lote daquela
    posição (0 é o primeiro `detalhar`); `omitir` são ids que `detalhar` não
    devolve, como se a Granola os tivesse perdido.
    """

    def __init__(
        self,
        reunioes: Iterable[Reuniao] = REUNIOES_DE_EXEMPLO,
        *,
        erro_ao_listar: Exception | None = None,
        erro_no_lote: dict[int, Exception] | None = None,
        omitir: Iterable[str] = (),
    ) -> None:
        self._reunioes = tuple(reunioes)
        self._erro_ao_listar = erro_ao_listar
        self._erro_no_lote = dict(erro_no_lote or {})
        self._omitir = frozenset(omitir)
        self.lotes: list[tuple[str, ...]] = []

    def listar(self) -> tuple[ReuniaoListada, ...]:
        if self._erro_ao_listar is not None:
            raise self._erro_ao_listar
        return tuple(ReuniaoListada(r.id, r.titulo, r.inicio) for r in self._reunioes)

    def detalhar(self, ids) -> tuple[Reuniao, ...]:
        posicao = len(self.lotes)
        self.lotes.append(tuple(ids))
        if posicao in self._erro_no_lote:
            raise self._erro_no_lote[posicao]
        pedidos = set(ids) - self._omitir
        return tuple(r for r in self._reunioes if r.id in pedidos)
