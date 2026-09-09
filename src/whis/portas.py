"""Portas dos serviços externos: STT, resumo de reunião, resumo do dia e daily.

Nem o pipeline, nem o diário, nem a daily falam com um provedor concreto —
falam com estas portas. Os adaptadores reais (Deepgram, Claude) implementam os
protocolos daqui; os fakes de `whis.fakes` fazem o mesmo para os
testes. Trocar de provedor não toca nenhuma das costuras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .fontes import Evento

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
class Daily:
    """As quatro batidas do roteiro que o usuário lê na daily do time.

    Irmã de `ResumoDoDia`, com outro recorte e outro destino: o diário é
    memória durável, escrita para ser relida meses depois; a daily é o oposto —
    trinta segundos falados, agora, para outras pessoas ouvirem.

    `entreguei` e `sigo_em` são o trabalho **dele**. Movimentação de outra
    pessoa é contexto e, no máximo, vira `duvidas` ou `preciso_de`.

    `preciso_de` é a batida que dá valor ao comando: só entra o que depende de
    **outra pessoa** — review parado, PR sem merge, aprovação, acesso. Nota
    para si mesmo não é daily.

    Os pontos livres e o off-topic **não** estão aqui: são do usuário, vêm de
    `notas/daily.md` e nunca passam por um serviço externo.
    """

    entreguei: tuple[str, ...] = ()
    sigo_em: tuple[str, ...] = ()
    preciso_de: tuple[str, ...] = ()
    duvidas: tuple[str, ...] = ()


class ErroDeDaily(RuntimeError):
    """Falha ao montar o roteiro. A daily nasce sem ele, marcada."""


@runtime_checkable
class PortaDaily(Protocol):
    """Transforma os eventos de uma janela no roteiro falado da daily."""

    def resumir_daily(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> Daily:
        """Devolve o que foi entregue, o que segue, o que espera alguém e as dúvidas.

        Levanta `ErroDeDaily` quando o serviço falha.
        """
        ...
