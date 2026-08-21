"""Constrói pastas de gravação de fixture, no formato do contrato.

Os WAV são gerados aqui com o módulo `wave` da stdlib — curtos, válidos, PCM
16-bit mono. O conteúdo do áudio é irrelevante: o STT dos testes é fake.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

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
