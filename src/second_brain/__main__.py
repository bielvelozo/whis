"""Entrada de linha de comando do Second Brain.

Hoje expõe o subcomando `processar`, que roda o pipeline do pós-gravação. O
gravador tem entrada própria (camada 02) e a unificação da CLI é da camada 05.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .configuracao import ConfiguracaoInvalida, carregar
from .fakes import ResumoFake, STTFake
from .gravacao import GravacaoInvalida
from .pipeline import processar
from .portas import ErroDeResumo, ErroDeSTT, PortaResumo, PortaSTT

_log = logging.getLogger("second_brain")


def configurar_logs(verboso: bool = False) -> None:
    """Logs legíveis do pipeline: gravação, transcrição, resumo, escrita."""
    # O console do Windows nem sempre aceita acentuação: um log jamais pode
    # derrubar o processamento por causa do codepage do terminal.
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def montar_portas(configuracao) -> tuple[PortaSTT, PortaResumo]:
    """Escolhe os adaptadores de STT e resumo.

    Enquanto os adaptadores reais não existem (Deepgram na camada 03, Claude
    na camada 04), o comando roda com os fakes e avisa disso em voz alta.
    """
    _log.warning(
        "Usando STT e resumo FAKE — os adaptadores reais chegam nas camadas 03 e 04."
    )
    return STTFake(), ResumoFake()


def _comando_processar(args: argparse.Namespace) -> int:
    configuracao = carregar(args.config)
    _log.info("Configuração lida de %s", configuracao.origem)
    stt, resumo = montar_portas(configuracao)
    resultado = processar(
        Path(args.pasta),
        configuracao=configuracao,
        stt=stt,
        resumo=resumo,
        reprocessar=args.reprocessar,
    )
    if resultado.reaproveitado:
        print(f"Já processada. Nota: {resultado.nota}")
    else:
        print(f"Nota:        {resultado.nota}")
        print(f"Transcrição: {resultado.transcricao}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="second-brain",
        description="Coletor de reunião sob demanda: da gravação à nota no vault.",
    )
    parser.add_argument("-v", "--verboso", action="store_true", help="logs detalhados")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    processar_cmd = subcomandos.add_parser(
        "processar",
        help="processa uma pasta de gravação e escreve nota + transcrição no vault",
    )
    processar_cmd.add_argument("pasta", help="caminho da pasta de gravação")
    processar_cmd.add_argument(
        "--config",
        default=None,
        help=r"caminho do config.toml (padrão: SECOND_BRAIN_CONFIG ou %%APPDATA%%\second-brain)",
    )
    processar_cmd.add_argument(
        "--reprocessar",
        action="store_true",
        help="refaz o processamento mesmo que a gravação já esteja transcrita",
    )
    processar_cmd.set_defaults(funcao=_comando_processar)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    configurar_logs(args.verboso)
    try:
        return args.funcao(args)
    except (ConfiguracaoInvalida, GravacaoInvalida, ErroDeSTT, ErroDeResumo) as erro:
        _log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
