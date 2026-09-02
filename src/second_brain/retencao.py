"""Retenção do áudio bruto: o que a limpeza apaga, o que ela nunca toca.

O áudio bruto vive **fora do vault**, na pasta `gravacoes` da configuração, e
é o único artefato do coletor que o Second Brain apaga sozinho. A regra vem da
spec (user story 13) e do contrato da pasta de gravação:

- só `status: "transcrito"` é candidato — a reunião já virou nota no vault;
- só depois de `retencao_dias` contados do processamento;
- `falhou` e `pendente` ficam retidos **indefinidamente**, até o reprocesso;
- pasta com nome fora do contrato nunca é candidata: não nasceu do gravador.

Apagar é irreversível, então este módulo trabalha em duas etapas explícitas:
`avaliar()` diz o que aconteceria e por quê, `limpar(simular=True)` mostra isso
ao usuário sem tocar em nada, e só `limpar(simular=False)` apaga — registrando
cada pasta, sua idade e o motivo no log.

O vault não é tocado aqui em nenhuma hipótese: a transcrição definitiva e a
nota de reunião já estão lá, e é justamente por isso que o áudio pode sumir.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import gravacao as _gravacao
from .configuracao import Configuracao
from .gravacao import (
    ARQUIVO_DE_ESTADO,
    STATUS_FALHOU,
    STATUS_PENDENTE,
    STATUS_TRANSCRITO,
    Estado,
)

_log = logging.getLogger("second_brain.retencao")

SEGUNDOS_POR_DIA = 86400.0


@dataclass(frozen=True)
class Avaliacao:
    """O veredito da retenção sobre uma pasta de gravação.

    `motivo` é texto para o usuário ler no log e no relatório: apagar áudio de
    reunião sem dizer por quê não é uma opção.
    """

    pasta: Path
    status: str
    idade_dias: float | None
    vencida: bool
    motivo: str
    bytes: int = 0

    @property
    def nome(self) -> str:
        return self.pasta.name


@dataclass(frozen=True)
class Limpeza:
    """O que a rotina de limpeza fez (ou faria, quando `simulado`)."""

    apagadas: tuple[Avaliacao, ...] = ()
    preservadas: tuple[Avaliacao, ...] = ()
    falhas: tuple[tuple[Avaliacao, str], ...] = ()
    simulado: bool = False
    retencao_dias: int = 7

    @property
    def bytes_liberados(self) -> int:
        return sum(avaliacao.bytes for avaliacao in self.apagadas)


def avaliar(
    gravacoes: Path | str,
    *,
    retencao_dias: int,
    agora: datetime | None = None,
) -> tuple[Avaliacao, ...]:
    """Julga cada pasta de gravação sem apagar nada.

    `agora` existe para o teste fixar o relógio; em produção é a hora local.
    Pastas fora do contrato de nome são ignoradas em silêncio (nível debug):
    a limpeza não opina sobre o que não é dela.
    """
    raiz = Path(gravacoes)
    momento = agora or datetime.now().astimezone()
    if not raiz.is_dir():
        _log.info("Pasta de gravações inexistente (%s) — nada a limpar.", raiz)
        return ()

    avaliacoes: list[Avaliacao] = []
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        if not _gravacao.parece_pasta_de_gravacao(pasta.name):
            _log.debug(
                "Ignorando %s — nome fora do contrato YYYY-MM-DD-HHMM-<slug>.", pasta.name
            )
            continue
        avaliacoes.append(_avaliar_pasta(pasta, retencao_dias, momento))
    return tuple(avaliacoes)


def limpar(
    gravacoes: Path | str,
    *,
    retencao_dias: int,
    simular: bool = False,
    agora: datetime | None = None,
) -> Limpeza:
    """Apaga as gravações vencidas — ou só mostra quais, com `simular=True`.

    Cada pasta apagada vira uma linha de log com nome, idade, tamanho e
    motivo. Uma falha ao apagar não interrompe as outras: fica registrada em
    `Limpeza.falhas` e o comando devolve código de erro.
    """
    avaliacoes = avaliar(gravacoes, retencao_dias=retencao_dias, agora=agora)
    vencidas = tuple(a for a in avaliacoes if a.vencida)
    preservadas = tuple(a for a in avaliacoes if not a.vencida)

    for avaliacao in preservadas:
        _log.debug("Preservada %s — %s.", avaliacao.nome, avaliacao.motivo)

    if not vencidas:
        _log.info(
            "Nenhuma gravação passou dos %d dias de retenção (%d preservada(s)).",
            retencao_dias,
            len(preservadas),
        )
        return Limpeza(
            preservadas=preservadas, simulado=simular, retencao_dias=retencao_dias
        )

    apagadas: list[Avaliacao] = []
    falhas: list[tuple[Avaliacao, str]] = []
    for avaliacao in vencidas:
        if simular:
            _log.info(
                "[simulação] Apagaria %s (%s, %s) — %s.",
                avaliacao.nome,
                _idade_legivel(avaliacao.idade_dias),
                tamanho_legivel(avaliacao.bytes),
                avaliacao.motivo,
            )
            apagadas.append(avaliacao)
            continue
        try:
            shutil.rmtree(avaliacao.pasta)
        except OSError as erro:
            _log.error("Não foi possível apagar %s: %s", avaliacao.pasta, erro)
            falhas.append((avaliacao, str(erro)))
            continue
        _log.info(
            "Apagada %s (%s, %s) — %s.",
            avaliacao.nome,
            _idade_legivel(avaliacao.idade_dias),
            tamanho_legivel(avaliacao.bytes),
            avaliacao.motivo,
        )
        apagadas.append(avaliacao)

    resultado = Limpeza(
        apagadas=tuple(apagadas),
        preservadas=preservadas,
        falhas=tuple(falhas),
        simulado=simular,
        retencao_dias=retencao_dias,
    )
    verbo = "Liberaria" if simular else "Liberados"
    _log.info(
        "%s %s em %d gravação(ões); %d preservada(s).",
        verbo,
        tamanho_legivel(resultado.bytes_liberados),
        len(resultado.apagadas),
        len(resultado.preservadas),
    )
    return resultado


def limpar_da_configuracao(
    configuracao: Configuracao,
    *,
    simular: bool = False,
    retencao_dias: int | None = None,
    agora: datetime | None = None,
) -> Limpeza:
    """A limpeza como a CLI a chama: caminho e prazo vindos da configuração."""
    return limpar(
        configuracao.gravacoes,
        retencao_dias=retencao_dias
        if retencao_dias is not None
        else configuracao.retencao_dias,
        simular=simular,
        agora=agora,
    )


def retidas(gravacoes: Path | str) -> tuple[Path, ...]:
    """As gravações que ainda não viraram nota — as candidatas ao reprocesso.

    São as de status `falhou` (o processamento quebrou) e `pendente` (nunca
    foi tentado, ou o gravador parou e ninguém processou). São exatamente as
    que a limpeza nunca apaga.
    """
    raiz = Path(gravacoes)
    if not raiz.is_dir():
        return ()
    return tuple(
        pasta
        for pasta in sorted(p for p in raiz.iterdir() if p.is_dir())
        if _gravacao.parece_pasta_de_gravacao(pasta.name)
        and _gravacao.ler_estado(pasta).status != STATUS_TRANSCRITO
    )


def tamanho_legivel(bytes_: int) -> str:
    """Tamanho em unidade humana, com vírgula decimal como manda o português."""
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            texto = f"{valor:.0f}" if unidade == "B" else f"{valor:.1f}"
            return f"{texto.replace('.', ',')} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


# -- Bastidores -------------------------------------------------------------


def _avaliar_pasta(pasta: Path, retencao_dias: int, agora: datetime) -> Avaliacao:
    estado = _gravacao.ler_estado(pasta)
    tamanho = _bytes_da_pasta(pasta)

    if estado.status == STATUS_FALHOU:
        return Avaliacao(
            pasta=pasta,
            status=estado.status,
            idade_dias=_idade_em_dias(pasta, estado, agora),
            vencida=False,
            motivo="processamento falhou — retida até o reprocesso",
            bytes=tamanho,
        )
    if estado.status != STATUS_TRANSCRITO:
        return Avaliacao(
            pasta=pasta,
            status=estado.status or STATUS_PENDENTE,
            idade_dias=_idade_em_dias(pasta, estado, agora),
            vencida=False,
            motivo="ainda não processada — retida até virar nota no vault",
            bytes=tamanho,
        )

    idade = _idade_em_dias(pasta, estado, agora)
    if idade is None:
        return Avaliacao(
            pasta=pasta,
            status=estado.status,
            idade_dias=None,
            vencida=False,
            motivo="transcrita, mas sem data de processamento legível — retida por segurança",
            bytes=tamanho,
        )
    if idade < retencao_dias:
        return Avaliacao(
            pasta=pasta,
            status=estado.status,
            idade_dias=idade,
            vencida=False,
            motivo=f"transcrita há {_idade_legivel(idade)}, dentro dos {retencao_dias} dias de retenção",
            bytes=tamanho,
        )
    return Avaliacao(
        pasta=pasta,
        status=estado.status,
        idade_dias=idade,
        vencida=True,
        motivo=(
            f"transcrita há {_idade_legivel(idade)}, além dos {retencao_dias} dias de "
            f"retenção; a nota e a transcrição já estão no vault"
        ),
        bytes=tamanho,
    )


def _idade_em_dias(pasta: Path, estado: Estado, agora: datetime) -> float | None:
    """Há quantos dias esta gravação foi processada.

    A fonte preferida é o `processado_em` do `estado.json` (o contrato manda);
    quando ele falta ou não é legível, cai para o mtime do próprio arquivo de
    estado, que é escrito no mesmo instante.
    """
    marco = _quando(estado.processado_em)
    if marco is None:
        arquivo = pasta / ARQUIVO_DE_ESTADO
        if not arquivo.is_file():
            return None
        marco = datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone()
    if marco.tzinfo is None:
        marco = marco.astimezone()
    return (agora - marco).total_seconds() / SEGUNDOS_POR_DIA


def _quando(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        _log.warning("Data de processamento ilegível (%r) — usando a data do arquivo.", iso)
        return None


def _idade_legivel(idade_dias: float | None) -> str:
    if idade_dias is None:
        return "idade desconhecida"
    if idade_dias < 1:
        horas = max(0, int(timedelta(days=idade_dias).total_seconds() // 3600))
        return f"{horas} h"
    dias = int(idade_dias)
    return "1 dia" if dias == 1 else f"{dias} dias"


def _bytes_da_pasta(pasta: Path) -> int:
    total = 0
    for caminho in pasta.rglob("*"):
        try:
            if caminho.is_file():
                total += caminho.stat().st_size
        except OSError:  # arquivo sumiu no meio da varredura
            continue
    return total
