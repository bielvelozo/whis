"""Portas dos serviços externos: STT, resumos, daily e as três do jornal.

Nem o pipeline, nem o diário, nem a daily falam com um provedor concreto —
falam com estas portas. Os adaptadores reais (Deepgram, Claude) implementam os
protocolos daqui; os fakes de `whis.fakes` fazem o mesmo para os
testes. Trocar de provedor não toca nenhuma das costuras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .fontes import Evento

if TYPE_CHECKING:
    from .nota_viva import NotaViva

#: Rótulo do falante que é o próprio usuário — vem do canal do microfone.
EU = "eu"

#: Rótulo dos demais participantes — vem do canal do áudio do sistema (loopback).
OUTROS = "outros"


@dataclass(frozen=True)
class Fala:
    """Um trecho contínuo de fala de um dos lados da reunião.

    `falante` é `EU` ou `OUTROS`: a distinção vem dos canais separados da
    gravação, não de diarização. Um adaptador que conheça nomes reais pode
    usá-los, mas nunca é obrigado a isso.
    """

    falante: str
    texto: str
    inicio_s: float | None = None


@dataclass(frozen=True)
class Transcricao:
    """O que a porta de STT devolve: a reunião inteira em falas ordenadas."""

    falas: tuple[Fala, ...]
    idioma: str = "pt-BR"

    def texto_corrido(self) -> str:
        """A transcrição como texto simples, uma linha por fala."""
        return "\n".join(f"{fala.falante}: {fala.texto}" for fala in self.falas)

    def falantes(self) -> tuple[str, ...]:
        """Os falantes distintos, na ordem em que aparecem."""
        vistos: list[str] = []
        for fala in self.falas:
            if fala.falante not in vistos:
                vistos.append(fala.falante)
        return tuple(vistos)


@dataclass(frozen=True)
class Resumo:
    """O que a porta de resumo devolve, sempre em português.

    `participantes` é o que o resumo conseguiu identificar na transcrição;
    quando vem vazio, o pipeline cai para os falantes da transcrição.
    """

    decisoes: tuple[str, ...] = ()
    acoes: tuple[str, ...] = ()
    topicos: tuple[str, ...] = ()
    participantes: tuple[str, ...] = ()
    titulo: str | None = None


@dataclass(frozen=True)
class CanaisDaGravacao:
    """Os arquivos de áudio de uma pasta de gravação.

    Um canal ausente (falha no loopback, por exemplo) chega como `None`:
    o gravador só reporta, quem decide o que fazer é o adaptador de STT.
    """

    microfone: Path | None
    sistema: Path | None
    taxa_microfone_hz: int | None = None
    taxa_sistema_hz: int | None = None
    metadados: dict = field(default_factory=dict)


class ErroDeSTT(RuntimeError):
    """Falha na transcrição — a gravação é preservada e nada é escrito no vault.

    O tratamento (retenção indefinida, sinalização) é da camada 03; a porta
    já declara o erro para o adaptador real ter onde encaixar.
    """


class ErroDeResumo(RuntimeError):
    """Falha na geração do resumo — a transcrição não se perde por isso."""


@runtime_checkable
class PortaSTT(Protocol):
    """Transcreve os canais separados de uma gravação."""

    def transcrever(self, canais: CanaisDaGravacao) -> Transcricao:
        """Devolve a transcrição já com a distinção "eu vs. os outros".

        Levanta `ErroDeSTT` quando o serviço falha.
        """
        ...


@runtime_checkable
class PortaResumo(Protocol):
    """Resume uma transcrição em português."""

    def resumir(self, transcricao: Transcricao, titulo: str | None = None) -> Resumo:
        """Devolve decisões, ações/pendências e tópicos.

        Levanta `ErroDeResumo` quando o serviço falha.
        """
        ...


@dataclass(frozen=True)
class ResumoDoDia:
    """O que a porta de resumo do dia devolve, sempre em português.

    Irmã de `Resumo`: o mesmo tipo de serviço externo, com outra entrada — os
    eventos das fontes passivas no lugar de uma transcrição.
    """

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
class ItemNovo:
    """Um item que ainda não está na nota viva e o modelo quer acrescentar.

    `sob` é onde ele entra: o id de um item existente, para virar sub-item
    dele; o texto exato de outro item novo da mesma resposta, para o modelo
    montar um grupo com sub-itens de uma vez; ou `None`, para o fim da lista.
    """

    texto: str
    sob: str | None = None


@dataclass(frozen=True)
class Daily:
    """O que o modelo quer mudar na nota viva depois de ler a janela.

    Irmã de `ResumoDoDia`, com outro recorte e outro destino: o diário é uma
    narrativa nova a cada dia; a daily é uma lista que o usuário mantém, e o
    modelo só **acrescenta** e **aponta**. `fiz` e `fazendo` são itens novos
    para *O que eu fiz* e *O que estou fazendo*; `mover` são ids de itens de
    *O que estou fazendo* que terminaram. O texto de um item que já existe
    nunca volta aqui: quem move é a costura, copiando a linha literal.

    Tudo vazio é uma resposta válida — a nota já diz tudo.
    """

    fiz: tuple[ItemNovo, ...] = ()
    fazendo: tuple[ItemNovo, ...] = ()
    mover: tuple[str, ...] = ()


class ErroDeDaily(RuntimeError):
    """Falha ao montar a resposta. A nota viva fica como estava; a datada nasce marcada."""


@runtime_checkable
class PortaDaily(Protocol):
    """Lê os eventos de uma janela contra a nota viva e diz o que muda nela."""

    def resumir_daily(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...], nota: NotaViva
    ) -> Daily:
        """Devolve os itens novos de cada lista e os ids a mover.

        `nota` é a nota viva como está: as duas listas do agente com um id por
        item, e as seções do usuário como contexto para não repetir.

        Levanta `ErroDeDaily` quando o serviço falha.
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
    """A página não saiu; a nota da edição já existe no vault."""


@runtime_checkable
class PortaPublicacao(Protocol):
    """Publica a página da edição como artifact, no mesmo endereço quando houver um."""

    def publicar(
        self, html: Path, capas: dict[str, Path], url_atual: str | None
    ) -> Publicacao:
        """`capas` é `{"img/N.jpg": caminho local}`. Levanta `ErroDePublicacao`."""
        ...
