r"""Entrada de linha de comando do Whis.

Oito subcomandos sobre a mesma configuração local e sobre as costuras do
projeto — `diario.gerar_diario` para o dia civil, `daily.gerar_daily` para a
nota viva da daily, `pergunta.responder` para a busca no vault e
`jornal.gerar_jornal` para o jornal de notícias::

    python -m whis init
    python -m whis bandeja
    python -m whis windows [--daily] [--news] [--remover] [--remover-legado]
    python -m whis diario [YYYY-MM-DD] [--simular]
    python -m whis daily [--anotar TEXTO] [--simular] [--agendada]
    python -m whis news [--agendada] [--fakes] [--simular]
    python -m whis perguntar "<pergunta>" [--sem-fio]
    python -m whis atender

`atender` é o agente de verdade: fica no ar escutando a DM do bot no Slack por
Socket Mode e responde ali, com o fio de 24 horas por conversa. `perguntar`
existe **para teste e diagnóstico**: responde no terminal, citando as notas, e
continua o fio do terminal entre uma chamada e outra.

`windows` amarra o Whis à máquina: o atalho de logon da bandeja sempre;
`--daily` agenda a daily nos horários de `[daily].horarios` (e o vigia, que
avisa por toast quando uma peça do Whis não subiu); `--news` agenda o jornal
todo dia em `[noticias].horario` (e reagenda o vigia, se existe, para olhar
por ele). As tarefas rodam mesmo que o PC estivesse desligado na hora.

Por padrão o comando usa os **adaptadores reais** — Claude (conta do usuário,
OAuth) para os resumos, git/Linear/Slack para as fontes.
`--fakes` troca todos pelas portas fake: é como exercitar as costuras inteiras
sem gastar crédito nem rede.

`news` gera o jornal do dia: a nota em `noticias/` e a página publicada como
artifact, no mesmo endereço de sempre; `--simular` e `--fakes` montam nota e
página numa pasta temporária, sem publicar nem escrever no vault (`--fakes`
também sem chamar o Claude).

`diario`, `daily` e `news` saem com um código que diz **se a nota nasceu, e inteira**:
`0` completa, `3` parcial (uma fonte ou o Claude falhou — a nota existe,
marcada), `1` não nasceu (todas as fontes falharam, nenhuma configurada, ou
não havia nada no período). `2` é do argparse: erro de uso.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from . import palheta as _palheta
from . import registro as _registro
from . import vault as _vault
from .atalho_global import analisar_atalho
from .atendente import ErroDeDM, PortaDM
from .busca import ErroDeBusca, PortaBusca, Resposta
from .coleta import TodasAsFontesFalharam
from .configuracao import (
    MODELO_DE_CONFIGURACAO,
    Configuracao,
    ConfiguracaoInvalida,
    caminho_padrao,
    carregar,
)
from .conversa import Conversas
from .daily import ResultadoDaDaily, gerar_daily
from .jornal import JornalNaoNasceu, PortasDoJornal, ResultadoDoJornal, gerar_jornal
from .diario import NenhumaFonteConfigurada, ResultadoDoDiario, gerar_diario
from .fakes import (
    BuscaFake,
    EditorFake,
    FormacaoFake,
    PublicacaoFake,
    ResumoDoDiaFake,
    fontes_de_exemplo,
)
from .fontes import PortaFonte, data_do_diario
from .pergunta import PerguntaVazia, responder
from .portas import PortaPublicacaoDoDeck, PortaResumoDoDia

_log = logging.getLogger("whis")

#: Códigos de saída de `diario` e `daily`. `2` fica de fora de propósito: é o
#: que o argparse devolve para erro de uso, e um script que confundisse "data
#: digitada errada" com "nota parcial" leria a daily errada.
SAIDA_COMPLETA = 0
SAIDA_NAO_NASCEU = 1
SAIDA_PARCIAL = 3

CODIGOS_DE_SAIDA = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  a nota nasceu inteira
  {SAIDA_PARCIAL}  a nota nasceu parcial: uma fonte ou o Claude falhou, e a nota diz qual
  {SAIDA_NAO_NASCEU}  a nota não nasceu: todas as fontes falharam, nenhuma está
     configurada, ou não havia nada no período
  2  erro de uso (argumento inválido)
o rastro de toda execução fica em bandeja.log, ao lado do config.toml"""

CODIGOS_DA_PERGUNTA = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  respondeu, citando o vault ou uma fonte
  {SAIDA_PARCIAL}  respondeu sem achar: nenhuma nota sustenta uma resposta, e ele disse isso
  {SAIDA_NAO_NASCEU}  não conseguiu: sem conta Claude, API key paga no ambiente, pergunta vazia
     ou configuração inválida
  2  erro de uso (argumento inválido)
a pergunta, as citações e o custo equivalente ficam em bandeja.log, ao lado do config.toml"""


def forcar_utf8_na_saida() -> None:
    """Faz `stdout`/`stderr` aguentarem o texto em português fora do console.

    Quando a saída não é um console interativo — pipe, redirecionamento para
    arquivo, captura pela bandeja ou por outro processo — o Python no Windows
    escolhe cp1252 e qualquer acento derruba o comando com `UnicodeEncodeError`.
    Aqui isso morderia sempre: "Diário", "simulação", "reunião" aparecem
    em toda saída. Só a CLI mexe nos fluxos do processo: quem importa o módulo como biblioteca não é
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
    """Logs legíveis dos comandos: fontes, resumo, escrita."""
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    if not verboso:
        logging.getLogger("httpx").setLevel(logging.WARNING)


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
            "ou rode com --fakes para ver o comando funcionando sem rede."
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


def montar_publicacao_do_deck(configuracao: Configuracao) -> PortaPublicacaoDoDeck:
    """A publicação do deck da daily: o Haiku da conta do usuário, pelo CLI de `[claude].cli`.

    Não há fake aqui de propósito: `--fakes` na daily é simulação, e uma
    publicação fake que gravasse a cópia deixaria um `deck:` falso no vault.
    """
    from .deck_claude import PublicacaoDoDeckClaude

    return PublicacaoDoDeckClaude(cli=configuracao.claude_cli or None)


def montar_busca(configuracao: Configuracao, *, fakes: bool = False) -> PortaBusca:
    """A busca: o Claude da conta do usuário com o vault e as fontes ao vivo, ou o fake.

    As fontes ao vivo são os mesmos coletores da daily, pelas mesmas fábricas
    — é o que mantém a blocklist do Slack e o `so_com_mencao` valendo numa
    consulta ao vivo. Nenhuma fonte ligada não é erro aqui: a busca responde
    só com o vault.
    """
    if fakes:
        _log.warning("Usando busca FAKE — nada é enviado ao Claude.")
        return BuscaFake()

    from .busca_claude import BuscaClaude
    from .fontes_ao_vivo import FontesAoVivo

    try:
        fontes = montar_fontes(configuracao)
    except NenhumaFonteConfigurada:
        fontes = []
        _log.info("Nenhuma fonte ao vivo ligada: a busca responde só com o vault.")
    return BuscaClaude(
        modelo=configuracao.claude_modelo or None,
        fontes_ao_vivo=FontesAoVivo(fontes, excluir=configuracao.privacidade_excluir),
    )


def montar_portas_do_jornal(configuracao: Configuracao, *, fakes: bool = False) -> PortasDoJornal:
    """As três portas do jornal: o Claude da conta do usuário, ou os fakes.

    Os adaptadores do jornal usam o CLI de `[claude].cli` (vazio = o do npm,
    se houver): é o que emite as janelas do plano e aceita as capas no artifact.
    """
    if fakes:
        _log.warning("Usando editor, formação e publicação FAKE — nada é enviado ao Claude.")
        return PortasDoJornal(EditorFake(), FormacaoFake(), PublicacaoFake())

    from .jornal_claude import EditorClaude, FormacaoClaude, PublicacaoClaude

    modelo = configuracao.claude_modelo or None
    cli = configuracao.claude_cli or None
    return PortasDoJornal(
        editor=EditorClaude(modelo=modelo, cli=cli),
        formacao=FormacaoClaude(modelo=modelo, cli=cli),
        publicacao=PublicacaoClaude(cli=cli),
    )


def montar_dm(configuracao: Configuracao) -> PortaDM:
    """A DM do bot no Slack, por Socket Mode. Levanta `ErroDeDM` sem os tokens."""
    from .dm_slack import de_configuracao

    return de_configuracao(configuracao)


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
    return _codigo_de_saida(
        f"Diário de {data.isoformat()}",
        vazio=resultado.vazio,
        parcial=bool(resultado.fontes_com_falha or resultado.falha_do_resumo),
    )


def _codigo_de_saida(nota: str, *, vazio: bool, parcial: bool) -> int:
    """O código que diz se a nota nasceu, e inteira — e o registra no log.

    A linha no log é o que sobra de uma execução que ninguém viu: o terminal
    já fechou, mas o arquivo diz se a daily daquele dia nasceu sem o Slack ou
    não nasceu.
    """
    if vazio:
        _log.info(
            "%s: a nota não nasceu, nada no período (saída %d).", nota, SAIDA_NAO_NASCEU
        )
        return SAIDA_NAO_NASCEU
    if parcial:
        _log.warning("%s: a nota nasceu parcial (saída %d).", nota, SAIDA_PARCIAL)
        return SAIDA_PARCIAL
    _log.info("%s: a nota nasceu inteira (saída %d).", nota, SAIDA_COMPLETA)
    return SAIDA_COMPLETA


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
    """Publica os slides da nota viva no link de sempre e grava a cópia em `daily/`.

    O que sai no terminal são os slides como foram, e o link; quem chama na
    hora agendada é a tarefa `Whis-Daily`, e o toast com o botão é o único
    sinal de que os slides saíram.
    """
    configuracao = _configuracao(args)
    if args.anotar is not None:
        return _anotar_ponto(configuracao, args.anotar)

    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.agendada and not configuracao.daily_ativa:
        _log.info(
            "Daily desligada em [daily].ativa de %s — a tarefa agendada não gerou nada.",
            configuracao.origem,
        )
        return SAIDA_COMPLETA
    simular = args.simular or args.fakes
    resultado = gerar_daily(
        datetime.now().astimezone(),
        configuracao=configuracao,
        publicacao=None if simular else montar_publicacao_do_deck(configuracao),
        simular=simular,
    )
    _relatar_daily(resultado)
    if not simular:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_da_daily(resultado))
    return _codigo_da_daily(resultado)


def _codigo_da_daily(resultado: ResultadoDaDaily) -> int:
    """0 com os slides no ar ou com a nota vazia; 3 quando só a cópia nasceu."""
    if resultado.simulado or resultado.vazio or resultado.publicado:
        _log.info("Daily de %s: saída %d.", resultado.data.isoformat(), SAIDA_COMPLETA)
        return SAIDA_COMPLETA
    _log.warning(
        "Daily de %s: os slides não saíram (saída %d).", resultado.data.isoformat(), SAIDA_PARCIAL
    )
    return SAIDA_PARCIAL


# -- news -------------------------------------------------------------------


def _comando_news(args: argparse.Namespace) -> int:
    """Gera o jornal de hoje, publica a página e avisa com o link.

    Quem chama na hora agendada é a tarefa `Whis-Noticias`: o toast é o único
    sinal de que a edição saiu, e o botão abre a página.
    """
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.agendada and not configuracao.noticias_ativa:
        _log.info(
            "Jornal desligado em [noticias].ativa de %s — a tarefa agendada não gerou nada.",
            configuracao.origem,
        )
        return SAIDA_COMPLETA
    portas = montar_portas_do_jornal(configuracao, fakes=args.fakes)
    simular = args.simular or args.fakes
    try:
        resultado = gerar_jornal(
            datetime.now().astimezone(),
            configuracao,
            editor=portas.editor,
            formacao=portas.formacao,
            publicacao=portas.publicacao,
            simular=simular,
        )
    except JornalNaoNasceu as erro:
        _log.error("O jornal não nasceu: %s", erro)
        print(f"O jornal não nasceu: {erro}")
        if not simular:
            _palheta.avisar_resultado(configuracao, _palheta.resultado_do_jornal_que_nao_nasceu(erro))
        return SAIDA_NAO_NASCEU

    _relatar_jornal(resultado)
    if not simular:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_do_jornal(resultado))
    return SAIDA_PARCIAL if resultado.parcial else SAIDA_COMPLETA


def _relatar_jornal(resultado: ResultadoDoJornal) -> None:
    from .pagina_do_jornal import texto_do_custo, texto_do_plano

    edicao = resultado.edicao
    if resultado.simulado:
        print(f"Simulação — nada publicado nem escrito no vault. Nota: {resultado.nota}")
        print(f"Página: {resultado.pagina}")
    else:
        print(f"Jornal de {edicao.data.isoformat()} no vault: {resultado.nota}")
        if resultado.url:
            print(f"Página: {resultado.url}")
        else:
            print(f"A página não saiu: {resultado.falha_da_publicacao}")
    for secao in edicao.secoes:
        print(f"  {secao.titulo}: {len(secao.itens)}")
    if edicao.time:
        print(f"  {edicao.time_nome or 'Time'}: {len(edicao.time)}")
    aulas = (1 if edicao.aprender else 0) + len(edicao.para_aprender)
    print(f"  Aulas: {aulas}")
    print(
        " · ".join(
            parte
            for parte in (
                f"{edicao.segundos:.0f} s",
                texto_do_custo(edicao.custo_usd),
                texto_do_plano(edicao.plano_antes, edicao.plano_depois),
            )
            if parte
        )
    )
    for aviso in edicao.avisos:
        print(f"Faltou: {aviso}")
    if edicao.fontes_com_falha:
        print("Não responderam: " + ", ".join(edicao.fontes_com_falha))


def _anotar_ponto(configuracao: Configuracao, texto: str) -> int:
    """Acrescenta uma linha em *Pontos* de `daily/atual.md` e sai, sem coletar nada."""
    if not texto.strip():
        _log.error("Nada a anotar: --anotar precisa de um texto.")
        return 1
    raiz = _vault.preparar(configuracao.vault)
    arquivo = _vault.anotar_ponto(raiz, texto)
    print(f"Anotado em {arquivo}")
    print(f"Está em '## {_vault.SECAO_PONTOS}' da nota viva, e fica lá até você tirar.")
    return 0


def _relatar_daily(resultado: ResultadoDaDaily) -> None:
    print(f"Daily — {resultado.data.isoformat()}")
    print()
    for slide in resultado.deck.slides:
        print(f"{slide.titulo}:")
        for item in slide.itens:
            print(f"{'  ' * (item.profundidade + 1)}{item.texto}")
        print()

    if resultado.simulado:
        print("Simulação — nada foi publicado nem gravado.")
        if resultado.vazio:
            print("A nota da daily está vazia: nenhum slide sairia.")
        return
    if resultado.vazio:
        print(f"A nota da daily está vazia — escreva em {_vault.CAMINHO_DA_NOTA_VIVA} e rode de novo.")
        return
    if resultado.publicado:
        print(f"Slides: {resultado.url}")
    else:
        print(f"Os slides não saíram: {resultado.falha_da_publicacao}")
    if resultado.copia is not None:
        print(f"Cópia: {resultado.copia}")


# -- perguntar --------------------------------------------------------------

#: A chave do fio do terminal em `conversas.json`. A DM do Slack tem a sua.
FIO_DO_TERMINAL = "terminal"


def _comando_perguntar(args: argparse.Namespace) -> int:
    """Pergunta ao vault pelo terminal — a mesma costura que a DM do Slack usa.

    O fio de 24 horas vale aqui também: duas chamadas seguidas continuam a
    mesma conversa, e `--sem-fio` pergunta sem ler nem gravar o fio.
    """
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    busca = montar_busca(configuracao, fakes=args.fakes)
    agora = datetime.now().astimezone()

    conversas = None if args.sem_fio else Conversas.de_configuracao(configuracao)
    conversa = conversas.abrir(FIO_DO_TERMINAL, agora=agora) if conversas else None
    resposta = responder(
        args.pergunta, configuracao=configuracao, busca=busca, conversa=conversa, agora=agora
    )
    if conversas is not None and conversa is not None:
        conversas.guardar(FIO_DO_TERMINAL, conversa)

    _relatar_resposta(resposta)
    return SAIDA_COMPLETA if resposta.achou else SAIDA_PARCIAL


def _relatar_resposta(resposta: Resposta) -> None:
    print(resposta.texto or "Não achei.")
    if resposta.citacoes:
        print()
        print("Fontes:")
        for citacao in resposta.citacoes:
            trecho = f" — {citacao.trecho}" if citacao.trecho else ""
            print(f"  {citacao.origem}{trecho}")
    if not resposta.achou:
        print()
        print("(não achou: nenhuma nota do vault sustenta uma resposta)")


# -- atender ----------------------------------------------------------------


def _comando_atender(args: argparse.Namespace) -> int:
    """Sobe o atendente: a DM do Slack escutando por Socket Mode até o Ctrl+C.

    `--fakes` troca só a busca pelo fake: a DM continua sendo o Slack de
    verdade, que é como se ensaia a app aprovada sem gastar a assinatura.
    """
    from . import atendente as _atendente

    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    busca = montar_busca(configuracao, fakes=args.fakes)
    try:
        dm = montar_dm(configuracao)
    except ErroDeDM as erro:
        _log.error("%s", erro)
        return 1
    return _atendente.executar(configuracao, dm=dm, busca=busca, verboso=args.verboso)


# -- bandeja ----------------------------------------------------------------


def _comando_bandeja(args: argparse.Namespace) -> int:
    """Sobe o ícone na bandeja com a palheta hospedada nele.

    Aqui só se decide de onde vêm as portas dos comandos da palheta — reais por
    padrão, fakes com `--fakes`: `daily`, `news` e `ask` rodam com as mesmas
    fábricas dos subcomandos.
    """
    from . import bandeja as _bandeja

    configuracao = _configuracao(args)
    fakes = args.fakes
    comandos = _palheta.comandos_padrao(
        publicacao_do_deck=lambda atual: montar_publicacao_do_deck(atual),
        simular_daily=fakes,
        busca=lambda atual: montar_busca(atual, fakes=fakes),
        portas_do_jornal=lambda atual: montar_portas_do_jornal(atual, fakes=fakes),
    )
    palheta = _palheta.Palheta(comandos, configuracao)

    def painel(raiz) -> None:
        from .painel import abrir_painel

        abrir_painel(raiz, palheta, destino=configuracao.origem)

    return _bandeja.executar(
        configuracao,
        verboso=args.verboso,
        palheta=palheta,
        atalho=analisar_atalho(configuracao.palheta_atalho),
        painel=painel,
    )


# -- init -------------------------------------------------------------------


def _comando_init(args: argparse.Namespace) -> int:
    """Escreve o `config.toml` inicial na máquina de destino.

    Antes disso o usuário tinha que criar o arquivo à mão, adivinhando as
    chaves — e o primeiro erro provável era a barra invertida do Windows. O
    arquivo nasce com o vault no perfil do usuário e comentários explicando o
    que preencher.
    """
    destino = Path(args.config) if args.config else caminho_padrao()
    if destino.exists() and not args.forcar:
        print(f"Já existe uma configuração em {destino}.")
        print("Abra o arquivo para editar, ou rode 'init --forcar' para sobrescrever.")
        return 1

    perfil = Path.home()
    conteudo = MODELO_DE_CONFIGURACAO.format(vault=(perfil / "whis-vault").as_posix())
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")

    print(f"Configuração criada em {destino}")
    print()
    print("Próximos passos:")
    print("  1. Confira o caminho do vault no arquivo.")
    print("  2. Rode 'python -m whis bandeja' e abra a palheta pelo atalho ou pelo ícone.")
    return 0


# -- windows ----------------------------------------------------------------


#: Como cada chave de `[daily].horarios` aparece para o usuário.
_DIAS_POR_EXTENSO = {
    "segunda": "segunda",
    "terca": "terça",
    "quarta": "quarta",
    "quinta": "quinta",
    "sexta": "sexta",
    "sabado": "sábado",
    "domingo": "domingo",
}


def _horarios_por_extenso(configuracao: Configuracao) -> str:
    return ", ".join(
        f"{_DIAS_POR_EXTENSO[dia]} {hora}" for dia, hora in configuracao.daily_horarios
    )


def _comando_windows(args: argparse.Namespace) -> int:
    """Amarra (ou desamarra) o Whis ao Windows: logon, daily, jornal e vigia.

    Amarrações explícitas, cada uma com o seu `--remover`. A daily precisa da configuração
    (é dela que saem os dias e horas); a tarefa recebe o caminho do arquivo
    explicitamente, porque não herda `WHIS_CONFIG` de quem a criou.
    """
    from . import automacao

    precisa_da_configuracao = bool(args.config) or (
        (args.daily or args.news) and not args.remover
    )
    configuracao = _configuracao(args) if precisa_da_configuracao else None
    origem = (configuracao.origem if configuracao else None) or caminho_padrao()
    feitos: list[str] = []
    so_remover_legado = args.remover_legado and not (args.atendente or args.daily or args.news)

    if args.daily and not args.remover and not configuracao.daily_horarios:
        _log.error(
            "A tabela [daily].horarios de %s está vazia: não há dia nem hora para "
            'agendar. Preencha-a (por exemplo horarios = { segunda = "13:55" }) e '
            "rode de novo.",
            origem,
        )
        return 1

    try:
        if args.remover_legado:
            legado = automacao.remover_legado()
            feitos.append(
                f"Atalho antigo removido de {legado.atalho}"
                if legado.atalho
                else f"Não havia atalho '{automacao.NOME_DO_ATALHO_LEGADO}' na Inicialização."
            )
            for nome in automacao.TAREFAS_LEGADAS:
                feitos.append(
                    f"Tarefa antiga '{nome}' removida do Agendador."
                    if nome in legado.tarefas
                    else f"Não havia tarefa '{nome}' no Agendador."
                )
        if args.remover:
            atalho = automacao.remover_inicializacao()
            feitos.append(
                f"Atalho de inicialização removido de {atalho}"
                if atalho
                else "Não havia atalho de inicialização."
            )
            if args.atendente:
                removido = automacao.remover_atendente()
                feitos.append(
                    f"Atalho do atendente removido de {removido}"
                    if removido
                    else "Não havia atalho do atendente."
                )
            if args.daily:
                removida = automacao.desagendar_daily()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA_DA_DAILY}' removida do Agendador."
                    if removida
                    else "Não havia tarefa da daily agendada."
                )
                removido = automacao.desagendar_vigia()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA_DO_VIGIA}' removida do Agendador."
                    if removido
                    else "Não havia vigia agendado."
                )
            if args.news:
                removida = automacao.desagendar_noticias()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA_DO_JORNAL}' removida do Agendador."
                    if removida
                    else "Não havia tarefa do jornal agendada."
                )
                if removida and not args.daily and automacao.vigia_agendado():
                    vigiadas = automacao.agendar_vigia(configuracao or _configuracao(args))
                    feitos.append(
                        f"Vigia reagendado como '{automacao.NOME_DA_TAREFA_DO_VIGIA}': "
                        f"agora vigia {', '.join(vigiadas)}."
                    )
        elif not so_remover_legado:
            atalho = automacao.instalar_inicializacao()
            feitos.append(f"Atalho de inicialização criado em {atalho}")
            feitos.append(
                f"Atalho do Menu Iniciar criado em {automacao.caminho_do_atalho_do_menu()} "
                f"(AUMID {automacao.AUMID}) — é o que permite ao Whis mostrar toast."
            )
            feitos.append("A bandeja passa a subir sozinha no próximo logon.")
            if args.atendente:
                atalho_do_atendente = automacao.instalar_atendente()
                feitos.append(f"Atalho do atendente criado em {atalho_do_atendente}")
                feitos.append(
                    "O agente da DM do Slack passa a subir sozinho no próximo logon, "
                    "ao lado da bandeja."
                )
            if args.news:
                automacao.agendar_noticias(configuracao)
                feitos.append(
                    f"Jornal agendado como '{automacao.NOME_DA_TAREFA_DO_JORNAL}': todo dia "
                    f"às {configuracao.noticias_horario}. Com [noticias].ativa = false a "
                    f"tarefa continua lá, mas sai sem gerar."
                )
                vigia_ja_agendado = not args.daily and automacao.vigia_agendado()
                if vigia_ja_agendado:
                    vigiadas = automacao.agendar_vigia(configuracao)
                    feitos.append(
                        f"Vigia reagendado como '{automacao.NOME_DA_TAREFA_DO_VIGIA}': "
                        f"avisa por toast se {' ou '.join(vigiadas)} falhou ou a bandeja "
                        f"não está no ar."
                    )
                elif not args.daily:
                    feitos.append(
                        f"'{automacao.NOME_DA_TAREFA_DO_VIGIA}' não está agendado: rode "
                        f"'whis windows --daily' para ele olhar também pelo jornal."
                    )
            if args.daily:
                automacao.agendar_daily(configuracao)
                feitos.append(
                    f"Daily agendada como '{automacao.NOME_DA_TAREFA_DA_DAILY}': "
                    f"{_horarios_por_extenso(configuracao)}."
                )
                vigiadas = automacao.agendar_vigia(configuracao)
                feitos.append(
                    f"Vigia agendado como '{automacao.NOME_DA_TAREFA_DO_VIGIA}': "
                    f"{automacao.ATRASO_DO_VIGIA.seconds // 60} minutos depois de cada "
                    f"daily e todo dia às {automacao.HORA_DA_RONDA_DO_VIGIA} — avisa por "
                    f"toast se {' ou '.join(vigiadas)} falhou ou a bandeja não está no ar."
                )
            if args.daily or args.news:
                feitos.append(
                    "As tarefas rodam mesmo que o PC estivesse desligado na hora: assim "
                    "que ele ligar, e acordando a máquina se estiver em suspensão."
                )
    except automacao.ErroDeAutomacao as erro:
        _log.error("%s", erro)
        return 1

    for linha in feitos:
        print(linha)
    return 0


# -- Bastidores da CLI ------------------------------------------------------


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


def _acrescentar_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=None,
        help=r"caminho do config.toml (padrão: WHIS_CONFIG ou %%APPDATA%%\whis)",
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whis",
        description="Agente pessoal local: diário, daily, jornal e busca no vault Obsidian.",
    )
    parser.add_argument("-v", "--verboso", action="store_true", help="logs detalhados")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    diario_cmd = subcomandos.add_parser(
        "diario",
        help="lê as fontes passivas do dia e escreve o diário em diario/",
        epilog=CODIGOS_DE_SAIDA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="mantém a nota viva da daily (daily/atual.md) desde a última fala e escreve a nota do dia",
        epilog=CODIGOS_DE_SAIDA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(daily_cmd)
    daily_cmd.add_argument(
        "--anotar",
        metavar="TEXTO",
        default=None,
        help="acrescenta uma linha em '## Pontos' de daily/atual.md e sai, sem coletar nada",
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
    daily_cmd.add_argument(
        "--agendada",
        action="store_true",
        help="é como a tarefa Whis-Daily chama: sai sem gerar nada se [daily].ativa = false",
    )
    daily_cmd.set_defaults(funcao=_comando_daily)

    news_cmd = subcomandos.add_parser(
        "news",
        help="gera o jornal de hoje em noticias/ e publica a página",
        description=(
            "Lê os feeds de noticias/fontes.md, pede ao Claude da sua conta que escolha, "
            "resuma e ensine, escreve noticias/AAAA-MM-DD.md e publica a página como "
            "artifact, no mesmo endereço da edição anterior."
        ),
        epilog=CODIGOS_DE_SAIDA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(news_cmd)
    news_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="usa editor, formação e publicação fake: sem Claude, sem publicar, sem escrever no vault",
    )
    news_cmd.add_argument(
        "--simular",
        action="store_true",
        help="gera nota e página numa pasta temporária, sem publicar e sem escrever no vault",
    )
    news_cmd.add_argument(
        "--agendada",
        action="store_true",
        help="é como a tarefa Whis-Noticias chama: sai sem gerar nada se [noticias].ativa = false",
    )
    news_cmd.set_defaults(funcao=_comando_news)

    perguntar_cmd = subcomandos.add_parser(
        "perguntar",
        help="pergunta ao vault pelo terminal, citando as notas (para teste e diagnóstico)",
        epilog=CODIGOS_DA_PERGUNTA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(perguntar_cmd)
    perguntar_cmd.add_argument("pergunta", help="a pergunta, entre aspas")
    perguntar_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="usa a busca fake em vez do Claude (sem rede, sem gastar a assinatura)",
    )
    perguntar_cmd.add_argument(
        "--sem-fio",
        action="store_true",
        help="pergunta sem ler nem gravar o fio de conversa do terminal",
    )
    perguntar_cmd.set_defaults(funcao=_comando_perguntar)

    atender_cmd = subcomandos.add_parser(
        "atender",
        help="fica no ar respondendo na DM do bot no Slack (Socket Mode, sem porta aberta)",
        description=(
            "Fica no ar escutando a DM do bot no Slack por Socket Mode — conexão de dentro "
            "para fora, sem porta aberta — e responde ali, citando as notas do vault. "
            "Ctrl+C encerra. Precisa de [slack].bot_token e [slack].app_token."
        ),
    )
    _acrescentar_config(atender_cmd)
    atender_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="responde na DM de verdade com a busca fake (ensaia o Slack sem gastar a assinatura)",
    )
    atender_cmd.set_defaults(funcao=_comando_atender)

    bandeja_cmd = subcomandos.add_parser(
        "bandeja",
        help="ícone na bandeja do Windows com a palheta no atalho global",
    )
    _acrescentar_config(bandeja_cmd)
    bandeja_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="os comandos da palheta rodam com as portas fake (sem rede, sem gastar a assinatura)",
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
        help="faz a bandeja subir com o logon (e, opcionalmente, agenda a daily e o jornal)",
        description=(
            "Amarra o Whis ao Windows. Sozinho, cria o atalho de logon da bandeja. "
            "--daily agenda a daily nos dias e horas de [daily].horarios e o vigia que "
            "avisa por toast quando uma peça do Whis não subiu; --news agenda o jornal "
            "todo dia em [noticias].horario. As tarefas rodam mesmo que o PC estivesse "
            "desligado na hora. --remover com os mesmos flags desfaz."
        ),
    )
    _acrescentar_config(windows_cmd)
    windows_cmd.add_argument(
        "--atendente",
        action="store_true",
        help="também faz o agente da DM do Slack (atender) subir com o logon",
    )
    windows_cmd.add_argument(
        "--daily",
        action="store_true",
        help=(
            "também agenda a daily nos horários de [daily].horarios (tarefa Whis-Daily) "
            "e o vigia (Whis-Vigia)"
        ),
    )
    windows_cmd.add_argument(
        "--news",
        action="store_true",
        help=(
            "também agenda o jornal todo dia em [noticias].horario (tarefa Whis-Noticias) "
            "e reagenda o vigia, se existe, para olhar por ele"
        ),
    )
    windows_cmd.add_argument(
        "--remover", action="store_true", help="desfaz o que foi instalado"
    )
    windows_cmd.add_argument(
        "--remover-legado",
        action="store_true",
        help=(
            "apaga o atalho 'Second Brain.lnk' e as tarefas 'SecondBrain-Limpeza' e "
            "'Whis-Limpeza', que chamam o que não existe mais; sozinho, não instala nada"
        ),
    )
    windows_cmd.set_defaults(funcao=_comando_windows)
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.stdout is None:
        # Sob `pythonw.exe` (bandeja, tarefas agendadas): sem isto cada `git`,
        # PowerShell e CLI do Claude abriria um console próprio na tela.
        from . import sem_console

        sem_console.instalar()
    forcar_utf8_na_saida()
    parser = construir_parser()
    args = parser.parse_args(argv)
    configurar_logs(args.verboso)
    try:
        return int(args.funcao(args))
    except (
        ConfiguracaoInvalida,
        ErroDeBusca,
        PerguntaVazia,
        TodasAsFontesFalharam,
        NenhumaFonteConfigurada,
    ) as erro:
        _log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
