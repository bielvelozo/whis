r"""Entrada de linha de comando do Second Brain.

Oito subcomandos sobre a mesma configuração local e sobre as três costuras do
projeto — `pipeline.processar` para a reunião, `diario.gerar_diario` para o dia
civil, `daily.gerar_daily` para o roteiro falado::

    python -m second_brain init
    python -m second_brain bandeja
    python -m second_brain windows [--limpeza] [--remover]
    python -m second_brain processar <pasta-da-gravacao>
    python -m second_brain reprocessar [<pasta> ...]
    python -m second_brain limpar [--simular]
    python -m second_brain diario [YYYY-MM-DD] [--simular]
    python -m second_brain daily [--anotar TEXTO] [--simular]

Por padrão o comando usa os **adaptadores reais** — Deepgram para o STT, Claude
(conta do usuário, OAuth) para os resumos, git/Linear/Slack para as fontes.
`--fakes` troca todos pelas portas fake: é como exercitar as costuras inteiras
sem gastar crédito nem rede.

A gravação em si também tem entrada própria (`python -m second_brain.gravador`),
para diagnóstico de dispositivo; no uso normal quem a chama é a bandeja.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from . import registro as _registro
from . import retencao as _retencao
from . import vault as _vault
from .coleta import TodasAsFontesFalharam
from .configuracao import (
    Configuracao,
    ConfiguracaoInvalida,
    caminho_padrao,
    carregar,
)
from .daily import ResultadoDaDaily, gerar_daily
from .diario import NenhumaFonteConfigurada, ResultadoDoDiario, gerar_diario
from .fakes import (
    DailyFake,
    ResumoDoDiaFake,
    ResumoFake,
    STTFake,
    fontes_de_exemplo,
    fontes_de_exemplo_da_daily,
)
from .fontes import PortaFonte, data_do_diario
from .gravacao import GravacaoInvalida
from .pipeline import processar
from .portas import (
    ErroDeResumo,
    ErroDeSTT,
    PortaDaily,
    PortaResumo,
    PortaResumoDoDia,
    PortaSTT,
)

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


def montar_fontes(configuracao: Configuracao, *, fakes: bool = False) -> list[PortaFonte]:
    """As fontes passivas ligadas na configuração, na ordem git, Linear, Slack.

    Chave vazia é fonte desligada, e o import de cada coletor mora dentro do
    `if`: enquanto o módulo de uma fonte não existir, ela simplesmente não é
    importada, e o diário nasce com as outras.
    """
    if fakes:
        _log.warning("Usando fontes FAKE — nada é lido do git, do Linear nem do Slack.")
        return list(fontes_de_exemplo())

    fontes: list[PortaFonte] = []
    if configuracao.git_raiz:
        from . import fonte_git

        fontes.append(fonte_git.de_configuracao(configuracao))
    if configuracao.linear_api_key:
        from . import fonte_linear

        fontes.append(fonte_linear.de_configuracao(configuracao))
    if configuracao.slack_user_token:
        from . import fonte_slack

        fontes.append(fonte_slack.de_configuracao(configuracao))
    if not fontes:
        raise NenhumaFonteConfigurada(
            "Nenhuma fonte passiva está ligada na configuração"
            f"{f' ({configuracao.origem})' if configuracao.origem else ''}. "
            "Preencha [git].raiz, [linear].api_key ou [slack].user_token — "
            "ou rode com --fakes para ver o diário funcionando sem rede."
        )
    _log.info("Fontes ligadas: %s.", ", ".join(fonte.nome for fonte in fontes))
    return fontes


def montar_resumo_do_dia(
    configuracao: Configuracao, *, fakes: bool = False
) -> PortaResumoDoDia:
    """O resumo do dia: o Claude da conta do usuário, ou o fake."""
    if fakes:
        _log.warning("Usando resumo do dia FAKE — nada é enviado ao Claude.")
        return ResumoDoDiaFake()

    from .resumo_dia_claude import ResumoDoDiaClaude

    return ResumoDoDiaClaude(modelo=configuracao.claude_modelo or None)


def montar_fontes_da_daily(
    configuracao: Configuracao, *, fakes: bool = False
) -> list[PortaFonte]:
    """As mesmas fontes do diário; só o `--fakes` muda.

    A janela da daily não é um dia civil, então as fontes fake do diário — que
    trazem os exemplos numa hora fixa — cairiam fora dela quase sempre.
    """
    if fakes:
        _log.warning("Usando fontes FAKE — nada é lido do git, do Linear nem do Slack.")
        return list(fontes_de_exemplo_da_daily())
    return montar_fontes(configuracao)


def montar_roteiro_da_daily(
    configuracao: Configuracao, *, fakes: bool = False
) -> PortaDaily:
    """O roteiro da daily: o Claude da conta do usuário, ou o fake."""
    if fakes:
        _log.warning("Usando roteiro da daily FAKE — nada é enviado ao Claude.")
        return DailyFake()

    from .resumo_dia_claude import ResumoDoDiaClaude

    return ResumoDoDiaClaude(modelo=configuracao.claude_modelo or None)


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
    """Apaga o áudio bruto já virado nota e vencido; `--simular` só mostra.

    Registra também no arquivo de log: quando quem chama é a tarefa agendada
    (sem console), o relatório impresso aqui não teria para onde ir.
    """
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
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


# -- diario -----------------------------------------------------------------


def _comando_diario(args: argparse.Namespace) -> int:
    """Lê as fontes passivas do dia e escreve `diario/YYYY-MM-DD.md`.

    Sem data, o dia é deduzido do relógio pela janela da configuração: às 02:00
    de quinta, com `inicio_do_dia = "04:00"`, o diário a gerar ainda é o de
    quarta. Registra também no arquivo de log, porque quem costuma chamar este
    comando é a tarefa agendada, que não tem console.
    """
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)

    data = args.data or data_do_diario(
        datetime.now().astimezone(), configuracao.diario_inicio_do_dia
    )
    fontes = montar_fontes(configuracao, fakes=args.fakes)
    # Em simulação o resumo não é chamado; o fake entra como marcador para que
    # conferir o filtro não dependa de credencial nem do adaptador do Claude.
    resumo = montar_resumo_do_dia(configuracao, fakes=args.fakes or args.simular)

    resultado = gerar_diario(
        data,
        configuracao=configuracao,
        fontes=fontes,
        resumo=resumo,
        simular=args.simular,
    )
    _relatar_diario(resultado)
    return 0


def _relatar_diario(resultado: ResultadoDoDiario) -> None:
    if resultado.vazio:
        print(
            f"Nada aconteceu em {resultado.data.isoformat()} — nenhum diário foi escrito."
        )
        return

    if resultado.simulado:
        print(f"Simulação do diário de {resultado.data.isoformat()} — nada foi escrito.")
        print(f"Janela: {resultado.janela.como_texto()}")
        for evento in resultado.eventos:
            referencia = f" ({evento.referencia})" if evento.referencia else ""
            print(f"  {evento.momento:%H:%M}  [{evento.fonte}]{referencia} {evento.titulo}")
        if not resultado.eventos:
            print("  (nenhum evento)")
    else:
        print(f"Diário: {resultado.nota}")

    for reuniao in resultado.reunioes:
        print(f"  reunião: {reuniao}")
    if resultado.excluidos:
        print(f"O filtro de exclusão removeu {resultado.excluidos} evento(s).")
    for falha in resultado.fontes_com_falha:
        print(f"Fonte '{falha.fonte}' não entrou: {falha.motivo}")
    if resultado.falha_do_resumo:
        print(f"Sem narrativa neste diário: {resultado.falha_do_resumo}")


# -- daily ------------------------------------------------------------------


def _comando_daily(args: argparse.Namespace) -> int:
    """Lê da última daily até agora, escreve `daily/` e imprime o roteiro.

    O que sai no terminal é o que o usuário lê em voz alta um minuto depois; a
    nota guarda o mesmo roteiro com as listas cruas embaixo. Nada é agendado:
    quem decide a hora é ele.
    """
    configuracao = _configuracao(args)
    if args.anotar is not None:
        return _anotar_ponto(configuracao, args.anotar)

    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    fontes = montar_fontes_da_daily(configuracao, fakes=args.fakes)
    # Em simulação o roteiro não é pedido; o fake entra como marcador para que
    # conferir o filtro não dependa de credencial nem do adaptador do Claude.
    roteiro = montar_roteiro_da_daily(configuracao, fakes=args.fakes or args.simular)

    resultado = gerar_daily(
        datetime.now().astimezone(),
        configuracao=configuracao,
        fontes=fontes,
        roteiro=roteiro,
        simular=args.simular,
    )
    _relatar_daily(resultado)
    return 0


def _anotar_ponto(configuracao: Configuracao, texto: str) -> int:
    """Acrescenta um ponto em `notas/daily.md` e sai, sem coletar nada."""
    if not texto.strip():
        _log.error("Nada a anotar: --anotar precisa de um texto.")
        return 1
    raiz = _vault.preparar(configuracao.vault)
    arquivo = _vault.anotar_ponto(raiz, texto)
    print(f"Anotado em {arquivo}")
    print("Ele entra na próxima daily enquanto o checkbox estiver desmarcado.")
    return 0


def _relatar_daily(resultado: ResultadoDaDaily) -> None:
    if resultado.vazio:
        print("Nada aconteceu desde a última daily — nenhuma nota foi escrita.")
        print(_vault.cobertura_da_janela(resultado.janela))
        return

    print(f"Daily — {resultado.janela.data.isoformat()}")
    print(_vault.cobertura_da_janela(resultado.janela))
    print()

    for titulo, itens in _vault.secoes_do_roteiro(resultado.roteiro, resultado.pontos):
        print(f"{titulo}:")
        for item in itens:
            print(f"  - {item}")
        if not itens:
            print("  (nada)")
        print()

    if resultado.simulado:
        print("Simulação — o Claude não foi chamado e nada foi escrito.")
        for evento in resultado.eventos:
            referencia = f" ({evento.referencia})" if evento.referencia else ""
            print(
                f"  {evento.momento:%d/%m %H:%M}  [{evento.fonte}]{referencia} "
                f"{evento.titulo}"
            )
        if not resultado.eventos:
            print("  (nenhum evento)")
    else:
        print(f"Nota: {resultado.nota}")

    for reuniao in resultado.reunioes:
        print(f"  reunião: {reuniao}")
    if resultado.excluidos:
        print(f"O filtro de exclusão removeu {resultado.excluidos} evento(s).")
    for falha in resultado.fontes_com_falha:
        print(f"Fonte '{falha.fonte}' não entrou: {falha.motivo}")
    if resultado.falha_do_roteiro:
        print(f"Sem roteiro nesta daily: {resultado.falha_do_roteiro}")


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

[diario]
inicio_do_dia = "04:00"      # o diário de um dia vai desta hora à mesma hora do dia seguinte
hora_da_tarefa = "19:00"     # quando a tarefa agendada gera o diário

[privacidade]
excluir = []                 # trechos que nunca saem da máquina (substring, sem diferenciar maiúsculas)

[git]
raiz = ""                    # pasta onde varrer repositórios; vazio = fonte desligada
profundidade = 3
excluir = []                 # pastas ignoradas na varredura
autores = []                 # vazio = deduz do git config user.email de cada repositório

[linear]
api_key = ""                 # Personal API Key read-only; vazio = fonte desligada

[slack]
user_token = ""              # user token xoxp da app interna; vazio = fonte desligada
conversas_excluidas = []     # canais e DMs que o coletor nunca lê
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


# -- windows ----------------------------------------------------------------


def _comando_windows(args: argparse.Namespace) -> int:
    """Amarra (ou desamarra) o coletor ao Windows: logon e limpeza diária.

    Duas amarrações explícitas, cada uma com o seu `--remover`. A limpeza
    agendada só existe se o usuário pedir: apagar áudio é irreversível e não
    pode ser efeito colateral de instalar um atalho.
    """
    from . import automacao

    configuracao = _configuracao(args) if args.config else None
    origem = configuracao.origem if configuracao else None
    feitos: list[str] = []

    try:
        if args.remover:
            atalho = automacao.remover_inicializacao()
            feitos.append(
                f"Atalho de inicialização removido de {atalho}"
                if atalho
                else "Não havia atalho de inicialização."
            )
            if args.limpeza:
                removida = automacao.desagendar_limpeza()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA}' removida do Agendador."
                    if removida
                    else "Não havia tarefa de limpeza agendada."
                )
        else:
            atalho = automacao.instalar_inicializacao()
            feitos.append(f"Atalho de inicialização criado em {atalho}")
            feitos.append("A bandeja passa a subir sozinha no próximo logon.")
            if args.limpeza:
                automacao.agendar_limpeza(hora=args.hora, config=origem)
                feitos.append(
                    f"Limpeza diária agendada às {args.hora} como "
                    f"'{automacao.NOME_DA_TAREFA}' — apaga só o áudio já virado "
                    f"nota e vencido pelo prazo de retenção."
                )
    except automacao.ErroDeAutomacao as erro:
        _log.error("%s", erro)
        return 1

    for linha in feitos:
        print(linha)
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


def _data_iso(texto: str) -> date:
    """A data do diário na linha de comando, sempre `YYYY-MM-DD`."""
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{texto!r} não é uma data no formato YYYY-MM-DD."
        ) from None


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

    diario_cmd = subcomandos.add_parser(
        "diario",
        help="lê as fontes passivas do dia e escreve o diário em diario/",
    )
    diario_cmd.add_argument(
        "data",
        nargs="?",
        type=_data_iso,
        default=None,
        help="dia do diário (YYYY-MM-DD); sem ele, o dia deduzido do relógio",
    )
    _acrescentar_config(diario_cmd)
    diario_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="usa fontes e resumo fake em vez de git, Linear, Slack e Claude",
    )
    diario_cmd.add_argument(
        "--simular",
        action="store_true",
        help="mostra o que entraria no diário, sem enviar ao Claude e sem escrever",
    )
    diario_cmd.set_defaults(funcao=_comando_diario)

    daily_cmd = subcomandos.add_parser(
        "daily",
        help="monta o roteiro da daily desde a última fala e escreve em daily/",
    )
    _acrescentar_config(daily_cmd)
    daily_cmd.add_argument(
        "--anotar",
        metavar="TEXTO",
        default=None,
        help="acrescenta um ponto em notas/daily.md e sai, sem coletar nada",
    )
    daily_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="usa fontes e roteiro fake em vez de git, Linear, Slack e Claude",
    )
    daily_cmd.add_argument(
        "--simular",
        action="store_true",
        help="mostra o que entraria na daily, sem enviar ao Claude e sem escrever",
    )
    daily_cmd.set_defaults(funcao=_comando_daily)

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

    windows_cmd = subcomandos.add_parser(
        "windows",
        help="faz a bandeja subir com o logon (e, opcionalmente, agenda a limpeza)",
    )
    _acrescentar_config(windows_cmd)
    windows_cmd.add_argument(
        "--limpeza",
        action="store_true",
        help="também agenda a limpeza diária do áudio bruto vencido",
    )
    windows_cmd.add_argument(
        "--hora",
        default="12:00",
        help="hora da limpeza diária (padrão: 12:00, com o PC ligado)",
    )
    windows_cmd.add_argument(
        "--remover", action="store_true", help="desfaz o que foi instalado"
    )
    windows_cmd.set_defaults(funcao=_comando_windows)
    return parser


def main(argv: list[str] | None = None) -> int:
    forcar_utf8_na_saida()
    parser = construir_parser()
    args = parser.parse_args(argv)
    configurar_logs(args.verboso)
    try:
        return int(args.funcao(args))
    except (
        ConfiguracaoInvalida,
        GravacaoInvalida,
        ErroDeSTT,
        ErroDeResumo,
        TodasAsFontesFalharam,
        NenhumaFonteConfigurada,
    ) as erro:
        _log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
