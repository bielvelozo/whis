r"""O fio de uma conversa com o agente, que expira depois de 24 horas de silêncio.

A DM do Slack lembra do que foi dito: pergunta de manhã, volta à tarde, o fio
continua e a pergunta de acompanhamento funciona sem repetir o assunto. Depois
de 24 horas **sem ninguém falar**, começa limpo — é o último turno que conta,
não a meia-noite: uma conversa ativa às 23h continua no dia seguinte.

O fio mora em `conversas.json` ao lado do `config.toml`, em
`%APPDATA%\second-brain\`, e **não no vault**: é rascunho de conversa, e o vault
guarda memória durável. Arquivo corrompido ou ilegível não derruba o
atendimento — vale como conversa vazia, com aviso no log.

O relógio é sempre injetado (`agora`): a expiração é comportamento, e ninguém
espera 24 horas para rodar a suíte.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .configuracao import Configuracao

_log = logging.getLogger("second_brain.conversa")

#: Quanto silêncio encerra um fio.
SILENCIO_MAXIMO = timedelta(hours=24)

#: Nome do arquivo ao lado do `config.toml`.
NOME_DO_ARQUIVO = "conversas.json"

#: Versão do formato de `conversas.json`.
VERSAO = 1

USUARIO = "usuario"
AGENTE = "agente"


@dataclass(frozen=True)
class Turno:
    """Uma fala do fio: quem disse, o quê e quando."""

    quem: str
    texto: str
    momento: datetime


class Conversa:
    """O fio de uma DM.

    `agora` no construtor aplica a expiração a turnos vindos do disco; quem
    segura uma conversa em memória por horas chama `expirar` antes de ler o
    histórico, e é o que `responder` faz.
    """

    def __init__(self, turnos: tuple[Turno, ...] = (), *, agora: datetime | None = None) -> None:
        self._turnos = list(turnos)
        if agora is not None:
            self.expirar(agora)

    def historico(self) -> tuple[Turno, ...]:
        return tuple(self._turnos)

    def vazia(self) -> bool:
        return not self._turnos

    def ultimo_momento(self) -> datetime | None:
        return self._turnos[-1].momento if self._turnos else None

    def expirada(self, agora: datetime) -> bool:
        """Verdadeiro quando o último turno é de 24 horas atrás ou mais."""
        ultimo = self.ultimo_momento()
        return ultimo is not None and _ciente(agora) - ultimo >= SILENCIO_MAXIMO

    def expirar(self, agora: datetime) -> bool:
        """Esquece o fio se ele expirou. Devolve se esqueceu."""
        if not self.expirada(agora):
            return False
        self._turnos.clear()
        return True

    def acrescentar(self, quem: str, texto: str, *, agora: datetime) -> None:
        momento = _ciente(agora)
        self.expirar(momento)
        self._turnos.append(Turno(quem=quem, texto=texto, momento=momento))


class Conversas:
    """O arquivo com todos os fios, um por chave (a DM, ou "terminal")."""

    def __init__(self, arquivo: Path) -> None:
        self.arquivo = Path(arquivo)

    @classmethod
    def de_configuracao(cls, configuracao: Configuracao) -> Conversas:
        base = configuracao.origem.parent if configuracao.origem else Path.home()
        return cls(base / NOME_DO_ARQUIVO)

    def abrir(self, chave: str, *, agora: datetime) -> Conversa:
        """O fio daquela chave, já sem o que expirou. Sem arquivo é fio vazio."""
        turnos = self._ler().get(chave, ())
        return Conversa(turnos, agora=agora)

    def guardar(self, chave: str, conversa: Conversa) -> Path:
        """Grava o fio; um fio vazio some do arquivo, e os expirados também."""
        fios = self._ler()
        if conversa.vazia():
            fios.pop(chave, None)
        else:
            fios[chave] = conversa.historico()
        referencia = conversa.ultimo_momento()
        if referencia is not None:
            fios = {
                outra: turnos
                for outra, turnos in fios.items()
                if outra == chave or not Conversa(turnos).expirada(referencia)
            }
        self._escrever(fios)
        return self.arquivo

    def _ler(self) -> dict[str, tuple[Turno, ...]]:
        if not self.arquivo.is_file():
            return {}
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            return {
                str(chave): tuple(_turno(item) for item in turnos)
                for chave, turnos in dados["conversas"].items()
            }
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as erro:
            _log.warning(
                "O arquivo de conversas em %s está ilegível (%s); seguindo sem histórico.",
                self.arquivo,
                erro,
            )
            return {}

    def _escrever(self, fios: dict[str, tuple[Turno, ...]]) -> None:
        dados = {
            "versao": VERSAO,
            "conversas": {
                chave: [
                    {"quem": turno.quem, "texto": turno.texto, "momento": turno.momento.isoformat()}
                    for turno in turnos
                ]
                for chave, turnos in fios.items()
            },
        }
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        # Gravação em dois passos: o atendente fica no ar o dia inteiro, e um
        # arquivo pela metade viraria "conversa vazia" na próxima leitura.
        temporario = self.arquivo.with_name(self.arquivo.name + ".tmp")
        temporario.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporario, self.arquivo)


def _turno(item: dict) -> Turno:
    momento = datetime.fromisoformat(str(item["momento"]))
    return Turno(quem=str(item["quem"]), texto=str(item["texto"]), momento=_ciente(momento))


def _ciente(momento: datetime) -> datetime:
    """Todo momento do fio tem fuso: sem isso a diferença de 24h não fecha."""
    return momento if momento.tzinfo is not None else momento.astimezone()
