"""Fakes das portas: implementações de verdade que devolvem dados fixos.

Não são mocks — não são interrogados sobre como foram chamados. São os
adaptadores que os testes (e o `--fakes` da CLI) injetam no lugar do Claude,
do git, do Linear e do Slack. Os testes verificam só o que aparece
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
from pathlib import Path

from .atendente import Mensagem
from .busca import Citacao, Resposta
from .conversa import Turno
from .ferramentas import Ferramentas
from .fontes import Evento, Janela
from .nota_viva import NotaViva, id_do_item
from .portas import (
    Aula,
    Candidato,
    Daily,
    Escolha,
    Formacao,
    ItemEscolhido,
    ItemNovo,
    Janelas,
    Medida,
    Publicacao,
    ResumoDoDia,
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

#: O item aberto de exemplo: entra em *O que estou fazendo* na primeira
#: execução e é movido para *O que eu fiz* na seguinte.
ITEM_ABERTO_DE_EXEMPLO = "Sigo no coletor de git, que ficou pela metade."

#: Resposta de daily de exemplo: acrescenta em cada lista e pede um movimento.
#:
#: O id em `mover` é o que `NotaViva` dará ao item aberto assim que ele
#: existir. Na primeira execução ele ainda não está na nota e o pedido é
#: ignorado com log; na segunda, o item está lá e sobe. Nenhum texto entra
#: duas vezes: a costura reconhece o que já está na nota.
DAILY_PADRAO = Daily(
    fiz=(
        ItemNovo("Fechei a camada 01 do diário."),
        ItemNovo("FN-123, o cálculo de frete do checkout: corrigido e em produção."),
    ),
    fazendo=(
        ItemNovo(ITEM_ABERTO_DE_EXEMPLO),
        ItemNovo(
            "FN-130, o diário automático: combinado gerar às 19:00 com a máquina ligada.",
            sob=ITEM_ABERTO_DE_EXEMPLO,
        ),
    ),
    mover=(id_do_item(ITEM_ABERTO_DE_EXEMPLO),),
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
    """Porta de daily que devolve sempre a mesma resposta.

    Guarda o que recebeu pelo mesmo motivo que `ResumoDoDiaFake`: é assim que o
    teste do filtro de exclusão prova que o conteúdo excluído nunca chegou
    perto de sair da máquina — e que a nota viva chegou inteira ao modelo.
    """

    def __init__(
        self, roteiro: Daily = DAILY_PADRAO, erro: Exception | None = None
    ) -> None:
        self._roteiro = roteiro
        self._erro = erro
        self.eventos_recebidos: tuple[Evento, ...] = ()
        self.reunioes_recebidas: tuple[str, ...] = ()
        self.nota_recebida: NotaViva | None = None

    def resumir_daily(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...], nota: NotaViva
    ) -> Daily:
        self.eventos_recebidos = tuple(eventos)
        self.reunioes_recebidas = tuple(reunioes)
        self.nota_recebida = nota
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
