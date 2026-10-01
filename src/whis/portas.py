"""Portas dos serviços externos: o resumo do dia, a publicação do deck da daily, as três do jornal e a Granola.

Nem o diário, nem a daily, nem o jornal, nem o coletor de reuniões falam com um provedor concreto —
falam com estas portas. Os adaptadores reais (Claude) implementam os
protocolos daqui; os fakes de `whis.fakes` fazem o mesmo para os
testes. Trocar de provedor não toca nenhuma das costuras.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from .fontes import Evento

@dataclass(frozen=True)
class ResumoDoDia:
    """O que a porta de resumo do dia devolve, sempre em português: a narrativa
    do dia a partir dos eventos das fontes passivas."""

    narrativa: str = ""
    destaques: tuple[str, ...] = ()
    pendencias: tuple[str, ...] = ()
    temas: tuple[str, ...] = ()


class ErroDeResumoDoDia(RuntimeError):
    """Falha ao resumir o dia. O diário nasce sem narrativa, marcado."""


@runtime_checkable
class PortaResumoDoDia(Protocol):
    """Resume um dia inteiro de fontes passivas em português."""

    def resumir_dia(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> ResumoDoDia:
        """Devolve narrativa, destaques, pendências e temas do dia.

        Levanta `ErroDeResumoDoDia` quando o serviço falha.
        """
        ...


@dataclass(frozen=True)
class Candidato:
    """Um item de feed que passou pela coleta e pode entrar no jornal.

    `id` é único na edição inteira (`tecnologia-3`), e é só por ele que o
    editor se refere a um item: o que o modelo não recebeu não existe.
    """

    id: str
    secao: str
    fonte: str
    titulo: str
    link: str
    resumo: str = ""
    data: datetime | None = None
    imagem: str | None = None
    destaque: bool = False


@dataclass(frozen=True)
class Janelas:
    """A utilização das janelas do plano da conta, em pontos percentuais."""

    cinco_horas: int | None = None
    sete_dias: int | None = None


@dataclass(frozen=True)
class Medida:
    """Quanto uma chamada ao Claude custou e o que o plano marcava nela.

    `plano_primeiro` e `plano_ultimo` são a primeira e a última leitura das
    janelas vistas durante a chamada; `None` quando o CLI não as emitiu.
    """

    custo_usd: float | None = None
    segundos: float = 0.0
    plano_primeiro: Janelas | None = None
    plano_ultimo: Janelas | None = None


@dataclass(frozen=True)
class ItemEscolhido:
    """Um candidato que o editor pôs no jornal, com título e resumo em português."""

    candidato: Candidato
    titulo: str
    resumo: str


@dataclass(frozen=True)
class Escolha:
    """O que o editor devolve: os itens de cada seção e os do time, já validados."""

    secoes: dict[str, tuple[ItemEscolhido, ...]]
    time: tuple[ItemEscolhido, ...] = ()
    medida: Medida = field(default_factory=Medida)


class ErroDeEditor(RuntimeError):
    """A escolha falhou; o jornal sai com os itens mais novos, sem resumo."""


@runtime_checkable
class PortaEditor(Protocol):
    """Escolhe, traduz e resume os candidatos de cada seção."""

    def escolher(
        self,
        candidatos: dict[str, tuple[Candidato, ...]],
        limites: dict[str, tuple[int, int]],
        time: tuple[Candidato, ...],
    ) -> Escolha:
        """`limites` é `{secao: (minimo, maximo)}`. Levanta `ErroDeEditor`."""
        ...


@dataclass(frozen=True)
class Aula:
    """Um texto da formação, escrito a partir das páginas em `fontes`."""

    titulo: str
    texto: str
    fontes: tuple[str, ...]
    trilha: str = ""


@dataclass(frozen=True)
class Formacao:
    """O que a formação devolve: uma aula de software e as de carro aceitas."""

    software: Aula | None = None
    carros: tuple[Aula, ...] = ()
    medida: Medida = field(default_factory=Medida)

    def aulas(self) -> tuple[Aula, ...]:
        return ((self.software,) if self.software else ()) + self.carros


class ErroDeFormacao(RuntimeError):
    """A formação falhou; o jornal sai sem *Aprender hoje* nem *Para aprender*."""


@runtime_checkable
class PortaFormacao(Protocol):
    """Pesquisa na web e ensina o próximo passo da trilha."""

    def ensinar(self, data: date, trilha: str) -> Formacao:
        """`trilha` é o texto de `noticias/trilha.md`. Levanta `ErroDeFormacao`."""
        ...


@dataclass(frozen=True)
class Publicacao:
    """O endereço do artifact publicado e quanto a publicação custou."""

    url: str
    medida: Medida = field(default_factory=Medida)


class ErroDePublicacao(RuntimeError):
    """A página não saiu; a nota já existe no vault.

    `url` é o endereço que já existe quando a falha veio depois de criá-lo: o
    deck da daily nasce numa sessão do CLI e é preenchido na seguinte.
    """

    def __init__(self, *args: object, url: str | None = None) -> None:
        super().__init__(*args)
        self.url = url


@runtime_checkable
class PortaPublicacao(Protocol):
    """Publica a página da edição como artifact, no mesmo endereço quando houver um."""

    def publicar(
        self, html: Path, capas: dict[str, Path], url_atual: str | None
    ) -> Publicacao:
        """`capas` é `{"img/N.jpg": caminho local}`. Levanta `ErroDePublicacao`."""
        ...


@runtime_checkable
class PortaPublicacaoDoDeck(Protocol):
    """Publica os arquivos do deck da daily no Claude Slides, sempre no mesmo endereço."""

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        """`arquivos` são os caminhos publicados (`project/...`) sob `raiz`, o índice incluído.

        Sem `url_atual`, cria o deck pelo tipo Slides e o preenche. Levanta
        `ErroDePublicacao`, com `url` quando o deck chegou a ser criado.
        """
        ...


@dataclass(frozen=True)
class ReuniaoListada:
    """Uma reunião como a lista da Granola a traz: o bastante para saber se é nova."""

    id: str
    titulo: str
    inicio: datetime


@dataclass(frozen=True)
class Reuniao:
    """Uma reunião detalhada. `resumo` vazio é reunião cujo resumo a Granola ainda gera."""

    id: str
    titulo: str
    inicio: datetime
    participantes: tuple[str, ...] = ()
    resumo: str = ""
    url: str = ""


class ErroDaGranola(RuntimeError):
    """A Granola não respondeu, respondeu erro, ou mandou o que não dá para ler."""


class LoginNecessario(ErroDaGranola):
    """Não há login válido, e esta execução não pode abrir o navegador para pedir um."""


@runtime_checkable
class PortaReunioes(Protocol):
    """As reuniões da conta da Granola do usuário."""

    def listar(self) -> tuple[ReuniaoListada, ...]:
        """As reuniões dos últimos 30 dias. Levanta `ErroDaGranola`."""
        ...

    def detalhar(self, ids: Sequence[str]) -> tuple[Reuniao, ...]:
        """Resumo, participantes e link de até 10 reuniões. Levanta `ErroDaGranola`."""
        ...
