"""A pasta de gravação: leitura dos metadados e do estado de processamento.

O formato é o do contrato `.scratch/tracer-bullet/contrato-pasta-gravacao.md`:

    <gravacoes>/YYYY-MM-DD-HHMM-<slug>/
      microfone.wav
      sistema.wav
      gravacao.json     # dono: o gravador
      estado.json       # dono: o pipeline
      transcricao.json  # dono: o pipeline — o que o STT devolveu

`estado.json` é a fonte de verdade da idempotência (não reprocessar o que já
virou nota) e da retenção do áudio bruto.

`transcricao.json` é o que o STT devolveu, gravado **antes** do resumo: uma
falha no resumo não pode custar uma segunda chamada de STT no reprocesso. Vive
na pasta de gravação, fora do vault, e some junto com ela na limpeza — a
transcrição definitiva já está no vault a essa altura.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .portas import CanaisDaGravacao, Fala, Transcricao

_log = logging.getLogger("whis.gravacao")

#: Versão do formato de `estado.json`.
VERSAO_DO_ESTADO = 1

#: Versão do formato de `transcricao.json`.
VERSAO_DA_TRANSCRICAO = 1

STATUS_PENDENTE = "pendente"
STATUS_TRANSCRITO = "transcrito"
STATUS_FALHOU = "falhou"

_NOME_DA_PASTA = re.compile(r"^(?P<data>\d{4}-\d{2}-\d{2})-(?P<hora>\d{4})-(?P<slug>.+)$")

ARQUIVO_DE_METADADOS = "gravacao.json"
ARQUIVO_DE_ESTADO = "estado.json"
ARQUIVO_DE_TRANSCRICAO = "transcricao.json"


def parece_pasta_de_gravacao(nome: str) -> bool:
    """O nome segue `YYYY-MM-DD-HHMM-<slug>`?

    A limpeza (`whis.retencao`) usa isto como cerca: pasta que não
    nasceu do gravador nunca é candidata a ser apagada.
    """
    return _NOME_DA_PASTA.match(nome) is not None


class GravacaoInvalida(RuntimeError):
    """A pasta não segue o contrato ou não tem áudio nenhum para transcrever."""


@dataclass(frozen=True)
class Estado:
    """O conteúdo de `estado.json`."""

    status: str = STATUS_PENDENTE
    processado_em: str | None = None
    nota: str | None = None
    transcricao: str | None = None
    erro: str | None = None
    versao: int = VERSAO_DO_ESTADO

    def como_dicionario(self) -> dict:
        return {
            "versao": self.versao,
            "status": self.status,
            "processado_em": self.processado_em,
            "nota": self.nota,
            "transcricao": self.transcricao,
            "erro": self.erro,
        }


@dataclass(frozen=True)
class PastaDeGravacao:
    """Uma pasta de gravação já lida: nome, data, título e canais."""

    caminho: Path
    data: str
    hora: str
    slug: str
    titulo: str | None
    canais: CanaisDaGravacao

    @property
    def basename(self) -> str:
        """O prefixo compartilhado por nota e transcrição no vault.

        Vem do nome da pasta, nunca do relógio do processamento — é o que
        torna o reprocesso determinístico.
        """
        return f"{self.data}-{self.hora}-{self.slug}"

    @property
    def nome_legivel(self) -> str:
        """Como a reunião é chamada na nota: o título, ou o slug humanizado."""
        return self.titulo or self.slug.replace("-", " ")

    def ler_estado(self) -> Estado:
        """O estado atual do processamento — `pendente` quando ainda não há arquivo."""
        return ler_estado(self.caminho)

    def gravar_estado(self, estado: Estado) -> None:
        """Escreve `estado.json` na pasta de gravação (fora do vault)."""
        gravar_estado(self.caminho, estado)

    def ler_transcricao(self) -> Transcricao | None:
        """A transcrição já guardada, ou `None` quando o STT ainda não rodou."""
        return ler_transcricao(self.caminho)

    def gravar_transcricao(self, transcricao: Transcricao) -> Path:
        """Guarda o que o STT devolveu, antes de qualquer tentativa de resumo."""
        return gravar_transcricao(self.caminho, transcricao)


def ler_estado(pasta: Path) -> Estado:
    """Lê `estado.json`; devolve estado `pendente` se não existir ou estiver corrompido."""
    arquivo = pasta / ARQUIVO_DE_ESTADO
    if not arquivo.is_file():
        return Estado()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _log.warning("Estado ilegível em %s — tratando a gravação como pendente.", arquivo)
        return Estado()
    return Estado(
        status=dados.get("status", STATUS_PENDENTE),
        processado_em=dados.get("processado_em"),
        nota=dados.get("nota"),
        transcricao=dados.get("transcricao"),
        erro=dados.get("erro"),
        versao=dados.get("versao", VERSAO_DO_ESTADO),
    )


def gravar_estado(pasta: Path, estado: Estado) -> None:
    """Escreve `estado.json` de forma legível para inspeção manual."""
    arquivo = pasta / ARQUIVO_DE_ESTADO
    arquivo.write_text(
        json.dumps(estado.como_dicionario(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def caminho_da_transcricao(pasta: Path) -> Path:
    """Onde a transcrição guardada mora dentro da pasta de gravação."""
    return Path(pasta) / ARQUIVO_DE_TRANSCRICAO


def ler_transcricao(pasta: Path) -> Transcricao | None:
    """Lê `transcricao.json`.

    Devolve `None` quando o arquivo não existe (o STT ainda não rodou com
    sucesso) e também quando existe mas está ilegível — nesse caso o pipeline
    transcreve de novo, que é o único caminho seguro.
    """
    arquivo = caminho_da_transcricao(pasta)
    if not arquivo.is_file():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        falas = tuple(
            Fala(
                falante=str(fala["falante"]),
                texto=str(fala["texto"]),
                inicio_s=fala.get("inicio_s"),
            )
            for fala in dados["falas"]
        )
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        _log.warning(
            "Transcrição guardada ilegível em %s — será transcrita de novo.", arquivo
        )
        return None
    return Transcricao(falas=falas, idioma=str(dados.get("idioma", "pt-BR")))


def gravar_transcricao(pasta: Path, transcricao: Transcricao) -> Path:
    """Escreve `transcricao.json` na pasta de gravação, fora do vault.

    Chamado assim que o STT devolve e **antes** do resumo: é o que faz o
    reprocesso de uma falha de resumo custar zero de STT.
    """
    arquivo = caminho_da_transcricao(pasta)
    dados = {
        "versao": VERSAO_DA_TRANSCRICAO,
        "gerada_em": agora_iso(),
        "idioma": transcricao.idioma,
        "falas": [
            {"falante": fala.falante, "texto": fala.texto, "inicio_s": fala.inicio_s}
            for fala in transcricao.falas
        ],
    }
    arquivo.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return arquivo


def agora_iso() -> str:
    """Horário local em ISO 8601, como o contrato pede em `processado_em`."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ler(pasta: Path) -> PastaDeGravacao:
    """Lê uma pasta de gravação e valida o mínimo para transcrever.

    Levanta `GravacaoInvalida` quando a pasta não existe, quando o nome foge
    do contrato ou quando não há nenhum canal de áudio.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise GravacaoInvalida(f"Pasta de gravação não encontrada: {pasta}")

    partes = _NOME_DA_PASTA.match(pasta.name)
    if partes is None:
        raise GravacaoInvalida(
            f"Nome de pasta fora do contrato: {pasta.name!r} — "
            f"esperado YYYY-MM-DD-HHMM-<slug>."
        )

    metadados = _ler_metadados(pasta)
    canais = _montar_canais(pasta, metadados)
    if canais.microfone is None and canais.sistema is None:
        raise GravacaoInvalida(
            f"Nenhum canal de áudio em {pasta} — nada a transcrever."
        )

    titulo = metadados.get("titulo") or None
    return PastaDeGravacao(
        caminho=pasta,
        data=partes["data"],
        hora=partes["hora"],
        slug=partes["slug"],
        titulo=titulo,
        canais=canais,
    )


def _ler_metadados(pasta: Path) -> dict:
    arquivo = pasta / ARQUIVO_DE_METADADOS
    if not arquivo.is_file():
        _log.warning(
            "Sem %s em %s — usando os arquivos de áudio encontrados na pasta.",
            ARQUIVO_DE_METADADOS,
            pasta,
        )
        return {}
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise GravacaoInvalida(f"Metadados inválidos em {arquivo}: {erro}") from erro


def _montar_canais(pasta: Path, metadados: dict) -> CanaisDaGravacao:
    declarados = metadados.get("canais") or {}
    microfone, taxa_microfone = _canal(pasta, declarados.get("microfone"), "microfone.wav")
    sistema, taxa_sistema = _canal(pasta, declarados.get("sistema"), "sistema.wav")
    return CanaisDaGravacao(
        microfone=microfone,
        sistema=sistema,
        taxa_microfone_hz=taxa_microfone,
        taxa_sistema_hz=taxa_sistema,
        metadados=metadados,
    )


def _canal(pasta: Path, declarado: dict | None, padrao: str) -> tuple[Path | None, int | None]:
    """Resolve um canal: o declarado nos metadados, ou o arquivo padrão da pasta."""
    if declarado:
        arquivo = pasta / declarado.get("arquivo", padrao)
        taxa = declarado.get("taxa_hz")
        return (arquivo if arquivo.is_file() else None, taxa)
    arquivo = pasta / padrao
    return (arquivo if arquivo.is_file() else None, None)
