"""Constrói pastas de gravação de fixture, no formato do contrato.

Os WAV são gerados aqui com o módulo `wave` da stdlib — curtos, válidos, PCM
16-bit mono. O conteúdo do áudio é irrelevante: o STT dos testes é fake.
"""

from __future__ import annotations

import json
import math
import os
import struct
import wave
from datetime import datetime, timedelta
from pathlib import Path

from whis.gravacao import ARQUIVO_DE_ESTADO, Estado, gravar_estado

NOME_PADRAO = "2026-08-20-1430-daily-do-time"
TITULO_PADRAO = "daily do time"


def criar_wav(caminho: Path, *, duracao_s: float = 0.2, taxa_hz: int = 16000) -> Path:
    """Escreve um WAV mono PCM 16-bit com um tom curto."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    quadros = int(duracao_s * taxa_hz)
    amostras = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / taxa_hz)))
        for i in range(quadros)
    )
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa_hz)
        arquivo.writeframes(amostras)
    return caminho


def criar_pasta_de_gravacao(
    gravacoes: Path,
    *,
    nome: str = NOME_PADRAO,
    titulo: str | None = TITULO_PADRAO,
    com_sistema: bool = True,
) -> Path:
    """Cria `<gravacoes>/<nome>/` com os dois canais e `gravacao.json`."""
    pasta = Path(gravacoes) / nome
    pasta.mkdir(parents=True, exist_ok=True)

    criar_wav(pasta / "microfone.wav")
    canais: dict[str, dict | None] = {
        "microfone": {
            "arquivo": "microfone.wav",
            "taxa_hz": 16000,
            "canais": 1,
            "dispositivo": "<microfone padrão>",
            "offset_inicio_s": 0.0,
        },
        "sistema": None,
    }
    if com_sistema:
        criar_wav(pasta / "sistema.wav")
        canais["sistema"] = {
            "arquivo": "sistema.wav",
            "taxa_hz": 16000,
            "canais": 1,
            "dispositivo": "<loopback padrão>",
            "offset_inicio_s": 0.04,
        }

    metadados = {
        "versao": 1,
        "titulo": titulo,
        "inicio": "2026-08-20T14:30:12-03:00",
        "fim": "2026-08-20T15:02:44-03:00",
        "duracao_s": 1952.4,
        "canais": canais,
    }
    (pasta / "gravacao.json").write_text(
        json.dumps(metadados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return pasta


def datar_processamento(
    pasta: Path,
    *,
    status: str,
    dias_atras: float,
    nota: str | None = None,
    transcricao: str | None = None,
    erro: str | None = None,
    processado_em: str | None | bool = True,
) -> Path:
    """Escreve `estado.json` como se o processamento tivesse ocorrido no passado.

    Nenhum teste dorme nem depende da hora que o relógio marca: a data é
    calculada a partir de "agora" no momento do teste, então a idade em dias é
    exatamente `dias_atras` qualquer que seja o dia da execução. O mtime do
    arquivo é alinhado à mesma data, porque ele é a fonte de queda da retenção
    quando `processado_em` falta.

    `processado_em=None` grava o estado **sem** a data, para exercitar
    justamente essa queda para o mtime.
    """
    quando = datetime.now().astimezone() - timedelta(days=dias_atras)
    carimbo = (
        quando.isoformat(timespec="seconds") if processado_em is True else processado_em
    )
    gravar_estado(
        pasta,
        Estado(
            status=status,
            processado_em=carimbo,
            nota=nota,
            transcricao=transcricao,
            erro=erro,
        ),
    )
    arquivo = Path(pasta) / ARQUIVO_DE_ESTADO
    os.utime(arquivo, (quando.timestamp(), quando.timestamp()))
    return arquivo
