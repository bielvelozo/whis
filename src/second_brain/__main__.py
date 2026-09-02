r"""Entrada de linha de comando do Second Brain.

Cinco subcomandos, todos sobre a mesma configuração local e, quando processam,
sobre a mesma costura (`pipeline.processar`)::

    python -m second_brain init
    python -m second_brain bandeja
    python -m second_brain processar <pasta-da-gravacao>
    python -m second_brain reprocessar [<pasta> ...]
    python -m second_brain limpar [--simular]

Por padrão o comando usa os **adaptadores reais** — Deepgram para o STT, Claude
(conta do usuário, OAuth) para o resumo. `--fakes` troca os dois pelas portas
fake: é como exercitar o pipeline inteiro sem gastar crédito nem rede.

A gravação em si também tem entrada própria (`python -m second_brain.gravador`),
para diagnóstico de dispositivo; no uso normal quem a chama é a bandeja.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import retencao as _retencao
from .configuracao import (
    Configuracao,
    ConfiguracaoInvalida,
    caminho_padrao,
    carregar,
)
from .fakes import ResumoFake, STTFake
from .gravacao import GravacaoInvalida
from .pipeline import processar
from .portas import ErroDeResumo, ErroDeSTT, PortaResumo, PortaSTT

_log = logging.getLogger("second_brain")


def forcar_utf8_na_saida() -> None:
    """Faz `stdout`/`stderr` aguentarem o texto em português fora do console.

    Quando a saída não é um console interativo — pipe, redirecionamento para
    arquivo, captura pela bandeja ou por outro processo — o Python no Windows
    escolhe cp1252 e qualquer acento derruba o comando com `UnicodeEncodeError`.
    Aqui isso morderia sempre: "Transcrição", "gravação", "simulação" aparecem
    em toda saída. Mesmo tratamento que o gravador já faz (camada 02). Só a CLI
    mexe nos fluxos do processo: quem importa o módulo como biblioteca não é
    afetado.
    """
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # fluxo fechado ou não reconfigurável
            pass


def configurar_logs(verboso: bool = False) -> None:
    """Logs legíveis do pipeline: gravação, transcrição, resumo, escrita."""
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def montar_portas(
    configuracao: Configuracao, *, fakes: bool = False
) -> tuple[PortaSTT, PortaResumo]:
    """Escolhe os adaptadores de STT e de resumo.

    O padrão é o real: Deepgram com a chave da configuração e Claude com o
    modelo da configuração (vazio = o modelo padrão da conta do usuário).
    `fakes=True` devolve as portas fake — o modo de exercitar a costura sem
    chamar serviço nenhum.

    Os adaptadores reais são importados aqui dentro de propósito: `--fakes`
    continua funcionando numa máquina onde o SDK do Claude ou o cliente HTTP
    não estejam instalados.
    """
    if fakes:
        _log.warning(
            "Usando STT e resumo FAKE — nada é enviado à Deepgram nem ao Claude."
        )
        return STTFake(), ResumoFake()

    from . import stt_deepgram
    from .resumo_claude import ResumoClaude

    stt = stt_deepgram.de_configuracao(configuracao)
    resumo = ResumoClaude(modelo=configuracao.claude_modelo or None)
    _log.info(
        "STT: Deepgram; resumo: Claude (modelo %s).",
        configuracao.claude_modelo or "padrão da conta",
    )
    return stt, resumo


# -- processar --------------------------------------------------------------


def _comando_processar(args: argparse.Namespace) -> int:
    configuracao = _configuracao(args)
    stt, resumo = montar_portas(configuracao, fakes=args.fakes)
    resultado = processar(
        Path(args.pasta),
        configuracao=configuracao,
        stt=stt,
        resumo=resumo,
        reprocessar=args.reprocessar,
        reaproveitar_transcricao=not args.refazer_transcricao,
    )
    _relatar(resultado)
    return 0


# -- reprocessar ------------------------------------------------------------


def _comando_reprocessar(args: argparse.Namespace) -> int:
    """Completa gravações retidas: as que falharam ou nunca foram processadas.

    Sem argumento, varre a pasta de gravações da configuração. É idempotente:
    os nomes no vault vêm da pasta de gravação, então rodar de novo reescreve
    os mesmos dois arquivos em vez de criar novos — e uma gravação já
    concluída é reconhecida e pulada.
    """
    configuracao = _configuracao(args)
    if args.pastas:
        pastas = [Path(pasta) for pasta in args.pastas]
    else:
        pastas = list(_retencao.retidas(configuracao.gravacoes))
        if not pastas:
            print("Nenhuma gravação retida — nada a reprocessar.")
            return 0
        _log.info("%d gravação(ões) retida(s) em %s.", len(pastas), configuracao.gravacoes)

    stt, resumo = montar_portas(configuracao, fakes=args.fakes)

    falhas = 0
    for pasta in pastas:
        _log.info("Reprocessando %s", pasta)
        try:
            resultado = processar(
                pasta,
                configuracao=configuracao,
                stt=stt,
                resumo=resumo,
                reprocessar=args.forcar,
                reaproveitar_transcricao=not args.refazer_transcricao,
            )
        except (GravacaoInvalida, ErroDeSTT, ErroDeResumo) as erro:
            _log.error("%s continua retida: %s", Path(pasta).name, erro)
            falhas += 1
            continue
        _relatar(resultado)
    return 1 if falhas else 0


# -- limpar -----------------------------------------------------------------


def _comando_limpar(args: argparse.Namespace) -> int:
    """Apaga o áudio bruto já virado nota e vencido; `--simular` só mostra."""
    configuracao = _configuracao(args)
    limpeza = _retencao.limpar_da_configuracao(
        configuracao, simular=args.simular, retencao_dias=args.dias
    )

    if limpeza.simulado:
        print(f"Simulação — nada foi apagado. Retenção: {limpeza.retencao_dias} dias.")
    else:
        print(f"Retenção: {limpeza.retencao_dias} dias.")

    verbo = "Apagaria" if limpeza.simulado else "Apagadas"
    if limpeza.apagadas:
        tamanho = _retencao.tamanho_legivel(limpeza.bytes_liberados)
        print(f"{verbo} {len(limpeza.apagadas)} gravação(ões) ({tamanho}):")
        for avaliacao in limpeza.apagadas:
            print(f"  - {avaliacao.nome} — {avaliacao.motivo}")
    elif not limpeza.falhas:
        # Só é verdade quando nada venceu. Se as vencidas existem e o sistema de
        # arquivos recusou apagá-las, quem fala é o bloco de falhas abaixo.
        print("Nenhuma gravação venceu o prazo de retenção.")

    if limpeza.preservadas:
        print(f"Preservadas {len(limpeza.preservadas)}:")
        for avaliacao in limpeza.preservadas:
            print(f"  - {avaliacao.nome} [{avaliacao.status}] — {avaliacao.motivo}")

    if limpeza.falhas:
        print(f"Não foi possível apagar {len(limpeza.falhas)}:")
        for avaliacao, erro in limpeza.falhas:
            print(f"  - {avaliacao.nome} — {erro}")
        return 1
    return 0


# -- bandeja ----------------------------------------------------------------


def _comando_bandeja(args: argparse.Namespace) -> int:
    """Sobe o ícone na bandeja: o gesto da spec, um clique liga e outro desliga.

    A bandeja é casca fina sobre o coletor; aqui só se decide de onde vêm as
    portas — reais por padrão, fakes com `--fakes` para ensaiar o gesto inteiro
    sem gastar crédito.
    """
    from . import bandeja as _bandeja

    configuracao = _configuracao(args)
    return _bandeja.executar(
        configuracao,
        portas=lambda: montar_portas(configuracao, fakes=args.fakes),
        verboso=args.verboso,
    )


# -- init -------------------------------------------------------------------

MODELO_DE_CONFIGURACAO = """\
# Configuração do Second Brain. Use barras normais (/) nos caminhos:
# no TOML a barra invertida é escape e quebra o arquivo.

vault = "{vault}"
gravacoes = "{gravacoes}"
retencao_dias = 7            # dias que o áudio bruto sobrevive depois de virar nota

[deepgram]
api_key = ""                 # crédito de US$ 200; sem ela o STT real não roda

[claude]
modelo = ""                  # vazio = o modelo padrão da sua conta

[audio]
dispositivo_microfone = ""   # vazio = microfone padrão do Windows
dispositivo_sistema = ""     # vazio = loopback da saída padrão do Windows
"""


def _comando_init(args: argparse.Namespace) -> int:
    """Escreve o `config.toml` inicial na máquina de destino.

    Antes disso o usuário tinha que criar o arquivo à mão, adivinhando as
    chaves — e o primeiro erro provável era a barra invertida do Windows. O
    arquivo nasce com caminhos no perfil do usuário e comentários explicando o
    que preencher; nada aqui inventa dispositivo de áudio, que é sempre da
    máquina de destino.
    """
    destino = Path(args.config) if args.config else caminho_padrao()
    if destino.exists() and not args.forcar:
        print(f"Já existe uma configuração em {destino}.")
        print("Abra o arquivo para editar, ou rode 'init --forcar' para sobrescrever.")
        return 1

    perfil = Path.home()
    conteudo = MODELO_DE_CONFIGURACAO.format(
        vault=(perfil / "second-brain-vault").as_posix(),
        gravacoes=(perfil / "second-brain-gravacoes").as_posix(),
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")

    print(f"Configuração criada em {destino}")
    print()
    print("Próximos passos:")
    print("  1. Confira os caminhos do vault e das gravações no arquivo.")
    print("  2. Cole a chave da Deepgram em [deepgram].api_key.")
    print("  3. Rode 'python -m second_brain.gravador dispositivos' e preencha [audio]")
    print("     se o canal do sistema não sair no dispositivo certo.")
    print("  4. Rode 'python -m second_brain bandeja' e clique no ícone para gravar.")
    return 0


# -- Bastidores da CLI ------------------------------------------------------


def _dias_nao_negativos(texto: str) -> int:
    """`--dias` só aceita prazo não negativo — apagar áudio não se desfaz."""
    try:
        dias = int(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número de dias.") from None
    if dias < 0:
        raise argparse.ArgumentTypeError(
            f"prazo negativo ({dias}) apagaria tudo que já virou nota; "
            f"use 0 para apagar assim que virar nota."
        )
    return dias


def _configuracao(args: argparse.Namespace) -> Configuracao:
    configuracao = carregar(args.config)
    _log.info("Configuração lida de %s", configuracao.origem)
    return configuracao


def _relatar(resultado) -> None:
    if resultado.reaproveitado:
        print(f"Já processada. Nota: {resultado.nota}")
        return
    if resultado.transcricao_reaproveitada:
        print("Transcrição reaproveitada da pasta de gravação — o STT não foi chamado.")
    print(f"Nota:        {resultado.nota}")
    print(f"Transcrição: {resultado.transcricao}")


def _acrescentar_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=None,
        help=r"caminho do config.toml (padrão: SECOND_BRAIN_CONFIG ou %%APPDATA%%\second-brain)",
    )


def _acrescentar_portas(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fakes",
        action="store_true",
        help="usa STT e resumo fake em vez da Deepgram e do Claude (sem rede, sem crédito)",
    )
    parser.add_argument(
        "--refazer-transcricao",
        action="store_true",
        help="ignora a transcrição guardada na pasta e chama o STT de novo (gasta crédito)",
    )


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
    _acrescentar_config(processar_cmd)
    _acrescentar_portas(processar_cmd)
    processar_cmd.add_argument(
        "--reprocessar",
        action="store_true",
        help="refaz o processamento mesmo que a gravação já esteja transcrita",
    )
    processar_cmd.set_defaults(funcao=_comando_processar)

    reprocessar_cmd = subcomandos.add_parser(
        "reprocessar",
        help="completa gravações retidas (as que falharam ou nunca foram processadas)",
    )
    reprocessar_cmd.add_argument(
        "pastas",
        nargs="*",
        help="pastas de gravação; sem argumento, todas as retidas da configuração",
    )
    _acrescentar_config(reprocessar_cmd)
    _acrescentar_portas(reprocessar_cmd)
    reprocessar_cmd.add_argument(
        "--forcar",
        action="store_true",
        help="reescreve a nota mesmo de gravações já concluídas",
    )
    reprocessar_cmd.set_defaults(funcao=_comando_reprocessar)

    limpar_cmd = subcomandos.add_parser(
        "limpar",
        help="apaga o áudio bruto já virado nota e vencido pelo prazo de retenção",
    )
    _acrescentar_config(limpar_cmd)
    limpar_cmd.add_argument(
        "--simular",
        action="store_true",
        help="só mostra o que seria apagado, sem apagar nada",
    )
    limpar_cmd.add_argument(
        "--dias",
        type=_dias_nao_negativos,
        default=None,
        help="prazo de retenção em dias (padrão: retencao_dias da configuração)",
    )
    limpar_cmd.set_defaults(funcao=_comando_limpar)

    bandeja_cmd = subcomandos.add_parser(
        "bandeja",
        help="ícone na bandeja do Windows: um clique grava, outro vira nota no vault",
    )
    _acrescentar_config(bandeja_cmd)
    bandeja_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="ensaia o gesto inteiro com STT e resumo fake (sem rede, sem crédito)",
    )
    bandeja_cmd.set_defaults(funcao=_comando_bandeja)

    init_cmd = subcomandos.add_parser(
        "init", help="cria o config.toml inicial com os caminhos e as chaves a preencher"
    )
    _acrescentar_config(init_cmd)
    init_cmd.add_argument(
        "--forcar", action="store_true", help="sobrescreve uma configuração existente"
    )
    init_cmd.set_defaults(funcao=_comando_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    forcar_utf8_na_saida()
    parser = construir_parser()
    args = parser.parse_args(argv)
    configurar_logs(args.verboso)
    try:
        return int(args.funcao(args))
    except (ConfiguracaoInvalida, GravacaoInvalida, ErroDeSTT, ErroDeResumo) as erro:
        _log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
