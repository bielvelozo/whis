"""O pipeline do pós-gravação: `processar(pasta) → arquivos no vault`.

Esta é a costura única do repositório. Tudo que é externo — STT e resumo —
entra por porta injetada, então o mesmo caminho de código roda em teste (com
fakes) e em produção (com Deepgram e Claude).

A transcrição é guardada na pasta de gravação assim que o STT devolve, antes
de qualquer tentativa de resumo: uma falha do Claude não pode custar uma
segunda chamada à Deepgram no reprocesso.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from . import gravacao as _gravacao
from . import vault as _vault
from .configuracao import Configuracao
from .gravacao import STATUS_FALHOU, STATUS_TRANSCRITO, Estado, PastaDeGravacao
from .portas import ErroDeResumo, ErroDeSTT, PortaResumo, PortaSTT

_log = logging.getLogger("second_brain.pipeline")


@dataclass(frozen=True)
class Resultado:
    """O que o processamento produziu — caminhos absolutos, para inspeção."""

    nota: Path
    transcricao: Path
    gravacao: PastaDeGravacao
    estado: Estado
    reaproveitado: bool = False
    transcricao_reaproveitada: bool = False


def processar(
    pasta: Path | str,
    *,
    configuracao: Configuracao,
    stt: PortaSTT,
    resumo: PortaResumo,
    reprocessar: bool = False,
    reaproveitar_transcricao: bool = True,
) -> Resultado:
    """Transforma uma pasta de gravação em nota + transcrição no vault.

    Reprocessar uma pasta já transcrita não refaz o trabalho nem duplica
    notas: os nomes vêm da pasta de gravação, e `estado.json` diz o que já
    foi feito. `reprocessar=True` força o caminho completo de novo, ainda
    escrevendo nos mesmos dois arquivos.

    `reaproveitar_transcricao=False` manda ignorar a transcrição guardada na
    pasta e chamar o STT de novo — é a saída para quando a transcrição em si
    ficou ruim, e a única forma de gastar STT numa gravação que já tem uma.
    """
    gravacao = _gravacao.ler(Path(pasta))
    _log.info(
        "Gravação encontrada: %s (canais: microfone=%s, sistema=%s)",
        gravacao.caminho,
        "sim" if gravacao.canais.microfone else "ausente",
        "sim" if gravacao.canais.sistema else "ausente",
    )

    raiz = _vault.preparar(configuracao.vault)
    caminho_nota = _vault.caminho_da_nota(gravacao.basename)
    caminho_transcricao = _vault.caminho_da_transcricao(gravacao.basename)

    estado = gravacao.ler_estado()
    if not reprocessar and _ja_concluida(raiz, estado, caminho_nota, caminho_transcricao):
        _log.info("Gravação já processada em %s — nada a fazer.", estado.processado_em)
        return Resultado(
            nota=raiz / caminho_nota,
            transcricao=raiz / caminho_transcricao,
            gravacao=gravacao,
            estado=estado,
            reaproveitado=True,
        )

    guardada = gravacao.ler_transcricao() if reaproveitar_transcricao else None
    try:
        if guardada is not None:
            transcricao = guardada
            _log.info(
                "Transcrição já guardada em %s (%d falas) — o STT não é chamado de novo.",
                _gravacao.caminho_da_transcricao(gravacao.caminho),
                len(transcricao.falas),
            )
        else:
            _log.info("Transcrevendo os canais da gravação...")
            transcricao = stt.transcrever(gravacao.canais)
            _log.info("Transcrição pronta: %d falas.", len(transcricao.falas))
            arquivo = gravacao.gravar_transcricao(transcricao)
            _log.info(
                "Transcrição guardada em %s — uma falha no resumo não a perde.", arquivo
            )

        _log.info("Gerando o resumo em português...")
        resumo_gerado = resumo.resumir(transcricao, gravacao.titulo)
        _log.info(
            "Resumo pronto: %d decisões, %d ações, %d tópicos.",
            len(resumo_gerado.decisoes),
            len(resumo_gerado.acoes),
            len(resumo_gerado.topicos),
        )
    except (ErroDeSTT, ErroDeResumo) as erro:
        # Nenhuma nota parcial: a gravação fica retida e o erro fica registrado.
        # O tratamento completo (sinalização, reprocesso) é das camadas 03 e 06.
        _log.error("Processamento interrompido: %s", erro)
        gravacao.gravar_estado(
            Estado(
                status=STATUS_FALHOU,
                processado_em=_gravacao.agora_iso(),
                erro=str(erro),
            )
        )
        raise

    titulo = gravacao.titulo or resumo_gerado.titulo or gravacao.nome_legivel
    participantes = resumo_gerado.participantes or transcricao.falantes()

    nota_escrita = _vault.escrever(
        raiz,
        caminho_nota,
        _vault.montar_nota(
            basename=gravacao.basename,
            data=gravacao.data,
            titulo=titulo,
            participantes=tuple(participantes),
            resumo=resumo_gerado,
        ),
    )
    transcricao_escrita = _vault.escrever(
        raiz,
        caminho_transcricao,
        _vault.montar_transcricao(
            basename=gravacao.basename,
            data=gravacao.data,
            titulo=titulo,
            transcricao=transcricao,
        ),
    )

    estado_final = Estado(
        status=STATUS_TRANSCRITO,
        processado_em=_gravacao.agora_iso(),
        nota=caminho_nota,
        transcricao=caminho_transcricao,
        erro=None,
    )
    gravacao.gravar_estado(estado_final)
    _log.info("Reunião '%s' disponível no vault.", titulo)

    return Resultado(
        nota=nota_escrita,
        transcricao=transcricao_escrita,
        gravacao=gravacao,
        estado=estado_final,
        transcricao_reaproveitada=guardada is not None,
    )


def _ja_concluida(raiz: Path, estado: Estado, nota: str, transcricao: str) -> bool:
    """A gravação já virou nota e os dois arquivos continuam no vault?"""
    if estado.status != STATUS_TRANSCRITO:
        return False
    return (raiz / nota).is_file() and (raiz / transcricao).is_file()
