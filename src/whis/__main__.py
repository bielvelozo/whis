r"""Entrada de linha de comando do Whis.

Nove subcomandos sobre a mesma configuração local e sobre as costuras do
projeto — `diario.gerar_diario` para o dia civil, `daily.gerar_daily` para os
slides da daily, `pergunta.responder` para a busca no vault,
`jornal.gerar_jornal` para o jornal de notícias e `reunioes.puxar_reunioes`
para as reuniões da Granola::

    python -m whis init
    python -m whis bandeja
    python -m whis windows [--daily] [--news] [--meetings] [--remover] [--remover-legado]
    python -m whis diario [YYYY-MM-DD] [--simular]
    python -m whis daily [--anotar TEXTO] [--simular] [--fakes] [--agendada]
    python -m whis news [--agendada] [--fakes] [--simular]
    python -m whis meetings [--agendada] [--fakes]
    python -m whis hunt [--simular] [--fakes] [--do-zero] [--freelas]
    python -m whis linkedin [--fakes] | linkedin-login | linkedin-publicar <nota>
    python -m whis contas [--so SITE] [--senha SITE] | navegador [url]
    python -m whis lembrete [--agendada] | candidaturas
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
por ele); `--meetings` agenda a puxada das reuniões da Granola em
`[granola].horario`, do mesmo jeito. As tarefas rodam mesmo que o PC
estivesse desligado na hora.

`meetings` puxa da Granola as reuniões dos últimos 30 dias que ainda não estão
em `reunioes/`. No terminal ele pode abrir o navegador para o login;
`--agendada` (a tarefa) nunca abre, e só avisa quando chegou nota ou falhou.
`--fakes` usa uma Granola de mentira e escreve num vault temporário.

Por padrão o comando usa os **adaptadores reais** — Claude (conta do usuário,
OAuth) para os resumos, git/Linear/Slack para as fontes.
`--fakes` troca todos pelas portas fake: é como exercitar as costuras inteiras
sem gastar crédito nem rede.

`news` gera o jornal do dia: a nota em `noticias/` e a página publicada como
artifact, no mesmo endereço de sempre; `--simular` e `--fakes` montam nota e
página numa pasta temporária, sem publicar nem escrever no vault (`--fakes`
também sem chamar o Claude).

`diario` e `news` saem com um código que diz **se a nota nasceu, e inteira**:
`0` completa, `3` parcial (uma fonte ou o Claude falhou — a nota existe,
marcada), `1` não nasceu (todas as fontes falharam, nenhuma configurada, ou
não havia nada no período). `daily` tem os seus: `0` com os slides no ar ou
com a nota vazia, `3` quando só a cópia nasceu. `2` é do argparse: erro de uso.
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
    LeitorDoXFake,
    MarcacoesFake,
    PublicacaoFake,
    QuizFake,
    ResumoDoDiaFake,
    ReunioesFake,
    fontes_de_exemplo,
)
from .fontes import PortaFonte, data_do_diario
from .pergunta import PerguntaVazia, responder
from .portas import ErroDaGranola, PortaPublicacaoDoDeck, PortaResumoDoDia, PortaReunioes
from .reunioes import ResultadoDasReunioes, puxar_reunioes

_log = logging.getLogger("whis")

#: Códigos de saída de `diario` e `daily`. `2` fica de fora de propósito: é o
#: que o argparse devolve para erro de uso, e um script que confundisse "data
#: digitada errada" com "nota parcial" leria a daily errada.
SAIDA_COMPLETA = 0
SAIDA_NAO_NASCEU = 1
SAIDA_DE_USO = 2
SAIDA_PARCIAL = 3

CODIGOS_DE_SAIDA = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  a nota nasceu inteira
  {SAIDA_PARCIAL}  a nota nasceu parcial: uma fonte ou o Claude falhou, e a nota diz qual
  {SAIDA_NAO_NASCEU}  a nota não nasceu: todas as fontes falharam, nenhuma está
     configurada, ou não havia nada no período
  2  erro de uso (argumento inválido)
o rastro de toda execução fica em bandeja.log, ao lado do config.toml"""

CODIGOS_DA_DAILY = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  os slides saíram no link de sempre, ou a nota estava vazia e nada foi publicado
  {SAIDA_PARCIAL}  os slides não saíram: a cópia em daily/ nasceu com o aviso e o toast abre a nota
  {SAIDA_NAO_NASCEU}  não rodou: configuração inválida
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
    """As portas do jornal: o Claude da conta do usuário e o Chrome do X, ou os fakes.

    Os adaptadores do jornal usam o CLI de `[claude].cli` (vazio = o do npm,
    se houver): é o que emite as janelas do plano e aceita as capas no artifact.
    """
    if fakes:
        _log.warning("Usando editor, formação, publicação, quiz, marcações e X FAKE — nada vai ao Claude nem ao X.")
        return PortasDoJornal(
            EditorFake(), FormacaoFake(), PublicacaoFake(), LeitorDoXFake(), MarcacoesFake(), QuizFake()
        )

    from .fonte_x import LeitorDoX
    from .jornal_claude import EditorClaude, FormacaoClaude, PublicacaoClaude
    from .marcacoes_claude import MarcacoesClaude
    from .quiz_claude import QuizClaude

    modelo = configuracao.claude_modelo or None
    cli = configuracao.claude_cli or None
    return PortasDoJornal(
        editor=EditorClaude(modelo=modelo, cli=cli),
        formacao=FormacaoClaude(modelo=modelo, cli=cli),
        publicacao=PublicacaoClaude(cli=cli),
        leitor_do_x=LeitorDoX(),
        marcacoes=MarcacoesClaude(cli=cli),
        quiz=QuizClaude(modelo=modelo, cli=cli),
    )


def montar_reunioes(
    configuracao: Configuracao, *, fakes: bool = False, pode_logar: bool = True
) -> PortaReunioes:
    """A Granola da conta do usuário, pelo MCP oficial, ou o fake.

    O login mora ao lado da configuração (`granola.json`, cifrado para o
    usuário do Windows). `pode_logar=False` é a tarefa agendada: sem login, ela
    não abre navegador nenhum.
    """
    if fakes:
        _log.warning("Usando a Granola FAKE — nada é pedido à Granola.")
        return ReunioesFake()

    from .granola import GranolaMCP
    from .granola_login import GuardaDoLogin, pasta_do_login

    pasta = pasta_do_login(configuracao)
    return GranolaMCP(GuardaDoLogin(pasta), pasta=pasta, pode_logar=pode_logar)


def montar_dm(configuracao: Configuracao) -> PortaDM:
    """A DM do bot no Slack, por Socket Mode. Levanta `ErroDeDM` sem os tokens."""
    from .dm_slack import de_configuracao

    return de_configuracao(configuracao)


def montar_portas_da_cacada(configuracao: Configuracao, *, fakes: bool = False, a_fundo: bool = False):
    """Os cinco adaptadores do Claude na caçada (a conta do usuário), ou os fakes.

    `a_fundo` dá ao explorador da web mais turnos e mais tempo (modo freelas rápidos).
    """
    if fakes:
        from .fakes_da_cacada import portas_fake

        _log.warning("Usando a caçada FAKE — nada é lido da rede nem enviado ao Claude.")
        return portas_fake()

    from .cacada import PortasDaCacada
    from .cacada_claude import ApostasClaude, ExploradorClaude, PerfilClaude, PreparoClaude, TriagemClaude

    from .acoes import Registro
    from .corrida import pasta_da_cacada

    opcoes = {"modelo": configuracao.claude_modelo or None, "cli": configuracao.claude_cli or None}
    navegador = None
    if configuracao.cacada_enviar_sozinho:
        from .navegador_agente import AgenteDoNavegador

        navegador = AgenteDoNavegador(**opcoes)
    return PortasDaCacada(
        perfil=PerfilClaude(**opcoes),
        explorador=ExploradorClaude(a_fundo=a_fundo, **opcoes),
        triagem=TriagemClaude(**opcoes),
        apostas=ApostasClaude(**opcoes),
        preparo=PreparoClaude(**opcoes),
        navegador=navegador,
        registro=Registro(pasta_da_cacada()),
        ler_caixa=montar_leitura_da_caixa(configuracao),
    )


def montar_leitura_da_caixa(configuracao: Configuracao):
    """A leitura do Gmail dedicado, só leitura; `None` sem e-mail ou sem senha de app."""
    if not (configuracao.cacada_email and configuracao.cacada_senha_de_app):
        return None
    from .caixa import ler_caixa

    return lambda: ler_caixa(configuracao.cacada_email, configuracao.cacada_senha_de_app)


def montar_linkedin_api(configuracao: Configuracao):
    """A API oficial do LinkedIn com o login guardado no cofre, ao lado do config."""
    from .cofre import cofre_padrao
    from .linkedin import LinkedInAPI

    return LinkedInAPI(configuracao.linkedin_client_id, configuracao.linkedin_client_secret, cofre_padrao(configuracao))


def preparar_linkedin_de(configuracao: Configuracao, *, fakes: bool = False):
    """`linkedin`: a análise do perfil (se há export) e os rascunhos de post. Nada é publicado."""
    from .cacada import CAMINHO_DO_PERFIL
    from .criterios_da_cacada import ler_criterios
    from .evidencias import montar_evidencias
    from .linkedin import preparar_linkedin

    raiz = _vault.preparar(configuracao.vault)
    criterios = ler_criterios(raiz)
    perfil = raiz / CAMINHO_DO_PERFIL
    if fakes:
        from .fakes_da_cacada import AnaliseDoPerfilFake, PostsFake

        analise, posts, evidencias = AnaliseDoPerfilFake(), PostsFake(), "(evidências de exemplo)"
    else:
        from .linkedin import AnaliseDoPerfilClaude, PostsClaude

        opcoes = {"modelo": configuracao.claude_modelo or None, "cli": configuracao.claude_cli or None}
        analise, posts, evidencias = AnaliseDoPerfilClaude(**opcoes), PostsClaude(**opcoes), montar_evidencias(configuracao)
    return preparar_linkedin(
        raiz,
        exportacao=configuracao.linkedin_exportacao,
        analise=analise,
        posts=posts,
        quantos=configuracao.linkedin_posts_por_vez,
        evidencias=evidencias,
        perfil_do_whis=perfil.read_text(encoding="utf-8") if perfil.is_file() else "",
        procuro=criterios.procuro,
        sobre_mim=criterios.sobre_mim,
        hoje=date.today(),
    )


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


def _comando_x_login(_args: argparse.Namespace) -> int:
    from . import fonte_x

    print(
        "Abrindo o Chrome do Whis no login do X. Entre na sua conta (pode ser pelo Google) e, "
        "quando a home aparecer, feche a janela."
    )
    if fonte_x.abrir_login():
        print("Sessão do X salva: a próxima edição do jornal lê o X.")
        return 0
    print("Login não concluído: a home do X não abriu logada nesse perfil. Rode de novo e entre antes de fechar.")
    return 1


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
    simular = args.simular or args.fakes
    if args.sabado and not simular:
        print("--sabado só vale com --simular ou --fakes: a edição de verdade só é de sábado no sábado.")
        return SAIDA_DE_USO
    portas = montar_portas_do_jornal(configuracao, fakes=args.fakes)
    try:
        resultado = gerar_jornal(
            datetime.now().astimezone(),
            configuracao,
            editor=portas.editor,
            formacao=portas.formacao,
            publicacao=portas.publicacao,
            leitor_do_x=portas.leitor_do_x,
            marcacoes=portas.marcacoes,
            quiz=portas.quiz,
            sabado=True if args.sabado else None,
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
    if edicao.quiz is not None:
        print(f"  Quiz da semana: {len(edicao.quiz.perguntas)} pergunta(s)")
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
    """Acrescenta uma linha em *Pontos* de `daily/atual.md` e sai, sem publicar nada."""
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


# -- meetings ---------------------------------------------------------------


def _comando_meetings(args: argparse.Namespace) -> int:
    """Puxa da Granola as reuniões que ainda não estão em `reunioes/`.

    Quem chama na hora agendada é a tarefa `Whis-Reunioes`: ela não abre
    navegador, e o toast só sai quando chegou nota ou falhou — reunião ainda
    sem resumo fica para a puxada seguinte, sem avisar. Com `--fakes`, a
    Granola é de mentira e o vault é temporário: uma reunião inventada no vault
    de verdade ficaria lá para sempre e o `ask` a leria como real.
    """
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.fakes:
        import tempfile
        from dataclasses import replace

        configuracao = replace(configuracao, vault=Path(tempfile.mkdtemp(prefix="whis-meetings-")))
        print(f"Vault temporário: {configuracao.vault}")
    porta = montar_reunioes(configuracao, fakes=args.fakes, pode_logar=not args.agendada)
    try:
        resultado = puxar_reunioes(configuracao, porta)
    except ErroDaGranola as erro:
        _log.error("As reuniões da Granola não vieram: %s", erro)
        print(f"As reuniões da Granola não vieram: {erro}")
        if not args.fakes:
            _palheta.avisar_resultado(configuracao, _palheta.resultado_das_reunioes_que_falharam(erro))
        return SAIDA_NAO_NASCEU

    _relatar_reunioes(resultado)
    avisar = not args.agendada or resultado.novas or resultado.falhas
    if avisar and not args.fakes:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_das_reunioes(resultado))
    if resultado.nada_veio:
        return SAIDA_NAO_NASCEU
    return SAIDA_PARCIAL if resultado.parcial else SAIDA_COMPLETA


def _relatar_reunioes(resultado: ResultadoDasReunioes) -> None:
    if not resultado.novas:
        print(f"Nada novo na Granola ({resultado.ja_no_vault} reunião(ões) dos últimos 30 dias já no vault).")
    for caminho in resultado.novas:
        print(f"  nova: {caminho}")
    for titulo in resultado.sem_resumo:
        print(f"  ainda sem resumo: {titulo}")
    for falha in resultado.falhas:
        print(f"  não veio: {falha}")


# -- hunt -------------------------------------------------------------------

CODIGOS_DA_CACADA = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  a caçada terminou: o relatório em cacada/ está inteiro
  {SAIDA_PARCIAL}  a caçada parou antes do fim (o plano do Claude, ou uma etapa falhou): o relatório
     tem o que deu, e rodar de novo continua de onde parou
  {SAIDA_NAO_NASCEU}  não rodou: outra caçada está correndo, ou a configuração é inválida
  2  erro de uso (argumento inválido)
o rastro de toda execução fica em bandeja.log, ao lado do config.toml"""


def _comando_hunt(args: argparse.Namespace) -> int:
    """A caçada de vagas e freelas: horas lendo, julgando e preparando; nada é enviado.

    Quem chama pela palheta é um processo próprio, solto da bandeja: a
    palheta não fica presa horas e o toast do fim é o sinal de que acabou.
    """
    from . import corrida as _corrida
    from .cacada import cacar
    from .freelas_rapidos import MODO_FREELAS

    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.simular:
        return _simular_coleta(configuracao, freelas=args.freelas)

    pasta = _corrida.pasta_da_cacada()
    if args.fakes:
        import tempfile
        from dataclasses import replace

        temporaria = Path(tempfile.mkdtemp(prefix="whis-hunt-"))
        configuracao = replace(configuracao, vault=temporaria / "vault")
        pasta = temporaria / "estado"
        print(f"Vault temporário: {configuracao.vault}")

    avisar = not args.fakes
    try:
        with _corrida.TravaDaCacada(pasta):
            _corrida.manter_acordado()
            if avisar:
                _palheta.avisar_resultado(
                    configuracao,
                    _palheta.Resultado(
                        "A caçada começou",
                        "Corre por horas e não envia nada. O relatório nasce em cacada/ e eu aviso quando acabar.",
                    ),
                )
            ao_pausar = (
                (lambda aviso: _palheta.avisar_resultado(configuracao, _palheta.Resultado("A caçada pausou", aviso.capitalize() + ".")))
                if avisar
                else None
            )
            try:
                resultado = cacar(
                    configuracao,
                    montar_portas_da_cacada(configuracao, fakes=args.fakes, a_fundo=args.freelas),
                    pasta_do_estado=pasta,
                    do_zero=args.do_zero,
                    modo=MODO_FREELAS if args.freelas else "",
                    ao_pausar=ao_pausar,
                )
                if args.freelas and resultado.completa and resultado.sobrou_plano:
                    _relatar_cacada(resultado)
                    print("Os freelas acabaram e ainda sobra plano antes da virada: emendando a caçada de vagas.", flush=True)
                    resultado = cacar(
                        configuracao,
                        montar_portas_da_cacada(configuracao, fakes=args.fakes),
                        pasta_do_estado=pasta,
                        ao_pausar=ao_pausar,
                    )
            finally:
                _corrida.liberar_sono()
    except _corrida.CacadaEmAndamento as erro:
        andamento = _corrida.ler_andamento(pasta) or {}
        print(f"Não comecei: {erro} Etapa: {andamento.get('etapa', '?')} {andamento.get('detalhe', '')}".rstrip())
        return SAIDA_NAO_NASCEU

    _relatar_cacada(resultado)
    if avisar:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_da_cacada(resultado))
    return SAIDA_COMPLETA if resultado.completa else SAIDA_PARCIAL


def _simular_coleta(configuracao: Configuracao, *, freelas: bool = False) -> int:
    """Só a coleta em Python, sem Claude e sem escrever nada além dos critérios: que fonte responde?"""
    from .criterios_da_cacada import ler_criterios
    from .fontes_da_cacada import coletar

    criterios = ler_criterios(_vault.preparar(configuracao.vault))
    if freelas:
        from .freelas_rapidos import criterios_de_freelas

        criterios = criterios_de_freelas(criterios)
    coleta = coletar(criterios.fontes, datetime.now().astimezone(), ao_ler=lambda nome: print(f"lendo {nome}...", flush=True))
    print()
    for nome, lista in coleta.por_fonte.items():
        print(f"{nome}: {len(lista)}")
        for oportunidade in lista[:3]:
            print(f"    {oportunidade.titulo[:90]} — {oportunidade.link}")
    for nome, motivo in coleta.falhas.items():
        print(f"{nome}: NÃO RESPONDEU — {motivo}")
    web = [fonte.nome for fonte in criterios.fontes if fonte.tipo == "web"]
    if web:
        print(f"Fontes do explorador (só na caçada de verdade, pelo Claude): {', '.join(web)}")
    print(f"Total: {len(coleta.todas())} oportunidade(s) únicas. Nada foi enviado ao Claude.")
    return SAIDA_COMPLETA if coleta.por_fonte else SAIDA_NAO_NASCEU


def _relatar_cacada(resultado) -> None:
    print(f"Relatório: {resultado.relatorio}")
    print(
        f"{resultado.chances_boas} chances boas ({resultado.pacotes} com pacote) · "
        f"{resultado.tentar_a_sorte} para tentar a sorte · {resultado.descartadas} descartadas"
    )
    if resultado.plano_antes is not None:
        print(f"Plano semanal: {resultado.plano_antes}% → {resultado.plano_depois}%")
    print(f"Equivalente a US$ {resultado.custo_usd:.2f} na tabela da API (a assinatura não cobra por token).")
    for nome, motivo in resultado.fontes_com_falha.items():
        print(f"Não respondeu: {nome} — {motivo}")
    if resultado.parada:
        print(f"Parou antes do fim: {resultado.parada}. Rode de novo para continuar.")


# -- lembrete e candidaturas -------------------------------------------------


def _comando_lembrete(args: argparse.Namespace) -> int:
    """O toast da véspera: a semana do plano vira nas próximas 30 h? Só lembra, nunca solta a caçada."""
    from . import corrida as _corrida
    from .lembrete import ja_lembrado, marcar_lembrado, proxima_virada, texto_do_lembrete

    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    pasta = _corrida.pasta_da_cacada()
    conhecida = _corrida.ler_virada(pasta)
    if conhecida is None:
        from .cacada_claude import SondaDoPlano

        try:
            plano = SondaDoPlano(cli=configuracao.claude_cli or None).ler()
        except Exception as erro:  # noqa: BLE001
            _log.warning("A sonda do plano falhou: %s", erro)
            plano = None
        if plano is None or plano.vira_sete_dias is None:
            print("Ainda não sei quando a semana do plano vira (o CLI do Claude não mostrou a janela semanal).")
            return SAIDA_NAO_NASCEU
        conhecida = plano.vira_sete_dias
        _corrida.guardar_virada(pasta, conhecida)
    agora = datetime.now().astimezone()
    virada = proxima_virada(conhecida, agora)
    print(f"A próxima virada da semana do plano: {virada.astimezone():%d/%m %H:%M}.")
    texto = texto_do_lembrete(virada, agora)
    if texto is None:
        print("Longe ainda: nada a lembrar hoje.")
        return SAIDA_COMPLETA
    if args.agendada and ja_lembrado(pasta, virada):
        return SAIDA_COMPLETA
    print(texto)
    _palheta.avisar_resultado(configuracao, _palheta.Resultado("Véspera da virada do plano", texto))
    marcar_lembrado(pasta, virada)
    return SAIDA_COMPLETA


def _comando_candidaturas(args: argparse.Namespace) -> int:
    """Regenera `cacada/candidaturas.md` agora (a caçada já faz isso no fim de cada corrida)."""
    from . import acompanhamento
    from .acoes import Registro
    from .corrida import pasta_da_cacada

    configuracao = _configuracao(args)
    mensagens: list[dict[str, str]] = []
    leitura = montar_leitura_da_caixa(configuracao)
    if leitura is not None:
        try:
            mensagens = [{"remetente": m.remetente, "assunto": m.assunto, "quando": m.quando} for m in leitura()]
        except Exception as erro:  # noqa: BLE001
            print(f"O Gmail não abriu: {erro}")
    caminho = acompanhamento.atualizar(_vault.preparar(configuracao.vault), registro=Registro(pasta_da_cacada()), mensagens=mensagens)
    print(f"Candidaturas: {caminho}")
    return SAIDA_COMPLETA


# -- contas -----------------------------------------------------------------


def _comando_contas(args: argparse.Namespace) -> int:
    """Cria as contas de `cacada/criterios.md` com o Gmail dedicado, confirma e completa os perfis.

    Feito para rodar com ele no PC: CAPTCHA, telefone e documento são dele, e o
    Chrome da caçada fica na tela.
    """
    from . import corrida as _corrida
    from .acoes import Registro
    from .cacada import CAMINHO_DO_PERFIL
    from .cofre import cofre_padrao
    from .contas import chave_no_cofre, cuidar_das_contas, escrever_nota
    from .criterios_da_cacada import ler_criterios
    from .navegador_agente import AgenteDoNavegador

    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    cofre = cofre_padrao(configuracao)
    if args.senha:
        guardada = cofre.obter(chave_no_cofre(args.senha))
        if not guardada:
            print(f"Não há conta de '{args.senha}' no cofre.")
            return SAIDA_NAO_NASCEU
        print(f"{guardada.get('site')}: {guardada.get('email')} / {guardada.get('senha')}")
        return SAIDA_COMPLETA

    raiz = _vault.preparar(configuracao.vault)
    criterios = ler_criterios(raiz)
    if not criterios.contas:
        print("Nenhum site em '## Contas' de cacada/criterios.md.")
        return SAIDA_NAO_NASCEU
    perfil = raiz / CAMINHO_DO_PERFIL
    perfil_texto = perfil.read_text(encoding="utf-8") if perfil.is_file() else criterios.sobre_mim
    pasta = _corrida.pasta_da_cacada()
    try:
        with _corrida.TravaDaCacada(pasta):
            _corrida.manter_acordado()
            try:
                resultado = cuidar_das_contas(
                    configuracao,
                    criterios,
                    agente=AgenteDoNavegador(modelo=configuracao.claude_modelo or None, cli=configuracao.claude_cli or None),
                    cofre=cofre,
                    registro=Registro(pasta),
                    perfil_texto=perfil_texto,
                    ler_caixa=montar_leitura_da_caixa(configuracao),
                    so=args.so or "",
                )
            finally:
                _corrida.liberar_sono()
    except _corrida.CacadaEmAndamento as erro:
        print(f"Não comecei: {erro} (contas e caçada usam o mesmo Chrome; espere uma acabar).")
        return SAIDA_NAO_NASCEU
    except ValueError as erro:
        print(f"Não comecei: {erro}.")
        return SAIDA_NAO_NASCEU
    nota = escrever_nota(raiz, resultado, configuracao.cacada_email, datetime.now().astimezone())
    for situacao in resultado.situacoes:
        marcas = " ".join(
            f"{nome} {'✓' if feito else '—'}"
            for nome, feito in (("conta", situacao.conta_feita), ("e-mail", situacao.confirmada), ("perfil", situacao.perfil_feito))
        )
        print(f"{situacao.conta.nome}: {marcas}{f' — falta: {situacao.pendente}' if situacao.pendente else ''}")
    for falha in resultado.falhas:
        print(f"Falha: {falha}")
    print(f"Resumo em {nota}. As senhas ficam no cofre: 'whis contas --senha <site>'.")
    _palheta.avisar_resultado(
        configuracao,
        _palheta.Resultado(
            "Contas: o Whis terminou a rodada",
            f"{len(resultado.pendentes)} site(s) precisam de você." if resultado.pendentes else "Tudo feito.",
            nota=nota,
        ),
    )
    return SAIDA_PARCIAL if resultado.pendentes or resultado.falhas else SAIDA_COMPLETA


def _comando_navegador(args: argparse.Namespace) -> int:
    """Abre um Chrome comum no perfil da caçada, para ele entrar à mão nos sites (Google incluso)."""
    import subprocess

    from .fonte_x import caminho_do_chrome
    from .navegador_agente import pasta_do_perfil

    chrome = caminho_do_chrome()
    if chrome is None:
        print("O Chrome não foi encontrado.")
        return SAIDA_NAO_NASCEU
    perfil = pasta_do_perfil()
    perfil.mkdir(parents=True, exist_ok=True)
    print(f"Abrindo o Chrome da caçada ({perfil}). Entre nos sites que quiser e feche a janela quando terminar.")
    subprocess.Popen([str(chrome), f"--user-data-dir={perfil}", "--no-first-run", "--no-default-browser-check", args.url])
    return SAIDA_COMPLETA


# -- linkedin ---------------------------------------------------------------


def _comando_linkedin(args: argparse.Namespace) -> int:
    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.fakes:
        import tempfile
        from dataclasses import replace

        configuracao = replace(configuracao, vault=Path(tempfile.mkdtemp(prefix="whis-linkedin-")))
        print(f"Vault temporário: {configuracao.vault}")
    resultado = preparar_linkedin_de(configuracao, fakes=args.fakes)
    if resultado.analise:
        print(f"Análise do perfil: {resultado.analise}")
    for caminho in resultado.rascunhos:
        print(f"Rascunho: {caminho}")
    for falha in resultado.falhas:
        print(f"Faltou: {falha}")
    print("Nada foi publicado. Para publicar um rascunho: posts na palheta (Enter) ou 'whis linkedin-publicar <nota>'.")
    if not args.fakes:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_do_linkedin(resultado))
    return SAIDA_COMPLETA if resultado.rascunhos and not resultado.falhas else (SAIDA_PARCIAL if resultado.rascunhos or resultado.analise else SAIDA_NAO_NASCEU)


def _comando_linkedin_login(args: argparse.Namespace) -> int:
    from .linkedin import RETORNO, ErroDoLinkedIn

    configuracao = _configuracao(args)
    api = montar_linkedin_api(configuracao)
    print(f"Abrindo o LinkedIn no navegador. Autorize o app; a página volta para {RETORNO}.")
    try:
        api.login()
    except ErroDoLinkedIn as erro:
        print(f"Login não concluído: {erro}")
        return SAIDA_NAO_NASCEU
    print(f"Login guardado no cofre; vale por {api.dias_restantes()} dias.")
    return SAIDA_COMPLETA


def _comando_linkedin_publicar(args: argparse.Namespace) -> int:
    """Publica um rascunho de `linkedin/posts/` — sempre perguntando antes: é o aval dele."""
    from .linkedin import ErroDoLinkedIn, ler_post, publicar_post

    configuracao = _configuracao(args)
    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    raiz = Path(configuracao.vault)
    caminho = args.nota.replace("\\", "/")
    if Path(caminho).is_absolute():
        caminho = Path(caminho).resolve().relative_to(raiz.resolve()).as_posix()
    post = ler_post(raiz, caminho)
    if post is None:
        print(f"{caminho} não é um post do Whis em linkedin/posts/.")
        return SAIDA_NAO_NASCEU
    print(post.texto)
    print()
    resposta = input("Publicar este post no seu LinkedIn agora? [s/N] ").strip().casefold()
    if resposta not in ("s", "sim", "y", "yes"):
        print("Nada publicado.")
        return SAIDA_COMPLETA
    try:
        url = publicar_post(raiz, caminho, montar_linkedin_api(configuracao))
    except ErroDoLinkedIn as erro:
        print(f"Não publicado: {erro}")
        return SAIDA_NAO_NASCEU
    print(f"Publicado: {url}")
    return SAIDA_COMPLETA


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
    fábricas dos subcomandos. `meetings` fica indisponível com `--fakes`: ele
    escreve no vault de verdade, e reunião inventada ficaria lá para sempre.
    """
    from . import bandeja as _bandeja

    configuracao = _configuracao(args)
    fakes = args.fakes
    comandos = _palheta.comandos_padrao(
        publicacao_do_deck=lambda atual: montar_publicacao_do_deck(atual),
        simular_daily=fakes,
        busca=lambda atual: montar_busca(atual, fakes=fakes),
        portas_do_jornal=lambda atual: montar_portas_do_jornal(atual, fakes=fakes),
        reunioes=None if fakes else (lambda atual: montar_reunioes(atual, pode_logar=True)),
        linkedin=lambda atual: preparar_linkedin_de(atual, fakes=fakes),
        linkedin_api=None if fakes else (lambda atual: montar_linkedin_api(atual)),
        iniciar_cacada=(
            (lambda _atual: _palheta.Resultado("Caçada indisponível", "Com --fakes, rode 'whis hunt --fakes' num terminal."))
            if fakes
            else None
        ),
        iniciar_contas=(
            (lambda _atual: _palheta.Resultado("Contas indisponíveis", "Com --fakes, as contas não são criadas."))
            if fakes
            else None
        ),
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
        (args.daily or args.news or args.meetings or args.hunt) and not args.remover
    )
    configuracao = _configuracao(args) if precisa_da_configuracao else None
    origem = (configuracao.origem if configuracao else None) or caminho_padrao()
    feitos: list[str] = []
    so_remover_legado = args.remover_legado and not (
        args.atendente or args.daily or args.news or args.meetings or args.hunt
    )

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
            if args.hunt:
                removida = automacao.desagendar_lembrete()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA_DO_LEMBRETE}' removida do Agendador."
                    if removida
                    else "Não havia lembrete da caçada agendado."
                )
            if args.meetings:
                removida = automacao.desagendar_reunioes()
                feitos.append(
                    f"Tarefa '{automacao.NOME_DA_TAREFA_DAS_REUNIOES}' removida do Agendador."
                    if removida
                    else "Não havia tarefa das reuniões agendada."
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
            if args.hunt:
                automacao.agendar_lembrete(configuracao)
                feitos.append(
                    f"Lembrete da caçada agendado como '{automacao.NOME_DA_TAREFA_DO_LEMBRETE}': todo dia às "
                    f"{configuracao.cacada_hora_do_lembrete} ele olha se a semana do plano vira nas próximas 30 h "
                    f"e avisa por toast, uma vez por virada. A caçada continua só quando você chama."
                )
            if args.meetings:
                automacao.agendar_reunioes(configuracao)
                feitos.append(
                    f"Reuniões agendadas como '{automacao.NOME_DA_TAREFA_DAS_REUNIOES}': todo dia "
                    f"às {configuracao.granola_horario}, puxando da Granola o que ainda não está "
                    f"em reunioes/. Ela nunca abre o navegador: o primeiro login é pela palheta "
                    f"(meetings)."
                )
                if not args.daily and automacao.vigia_agendado():
                    vigiadas = automacao.agendar_vigia(configuracao)
                    feitos.append(
                        f"Vigia reagendado como '{automacao.NOME_DA_TAREFA_DO_VIGIA}': "
                        f"avisa por toast se {' ou '.join(vigiadas)} falhou ou a bandeja "
                        f"não está no ar."
                    )
                elif not args.daily:
                    feitos.append(
                        f"'{automacao.NOME_DA_TAREFA_DO_VIGIA}' não está agendado: rode "
                        f"'whis windows --daily' para ele olhar também pelas reuniões."
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
            if args.daily or args.news or args.meetings:
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
        help="publica os slides de daily/atual.md no link de sempre e grava a cópia em daily/",
        epilog=CODIGOS_DA_DAILY,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(daily_cmd)
    daily_cmd.add_argument(
        "--anotar",
        metavar="TEXTO",
        default=None,
        help="acrescenta uma linha em '## Pontos' de daily/atual.md e sai, sem publicar nada",
    )
    daily_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="o mesmo que --simular: mostra os slides sem publicar nem escrever",
    )
    daily_cmd.add_argument(
        "--simular",
        action="store_true",
        help="mostra os slides que sairiam, sem publicar e sem escrever",
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
    news_cmd.add_argument(
        "--sabado",
        action="store_true",
        help="faz a edição de sábado (o quiz no lugar das aulas novas) em qualquer dia; só com --simular ou --fakes",
    )
    news_cmd.set_defaults(funcao=_comando_news)

    x_login_cmd = subcomandos.add_parser(
        "x-login",
        help="abre o Chrome do Whis no login do x.com para você entrar na conta do jornal",
        description=(
            "Abre um Chrome comum com o perfil só do Whis (%LOCALAPPDATA%\\whis\\navegador-x) na tela "
            "de login do x.com. Entre na sua conta e feche a janela quando a home aparecer; o Whis "
            "confere a sessão e o jornal passa a ler a seção Dev com IA. O Whis nunca vê a senha."
        ),
    )
    x_login_cmd.set_defaults(funcao=_comando_x_login)

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

    meetings_cmd = subcomandos.add_parser(
        "meetings",
        help="puxa da Granola as reuniões que ainda não estão em reunioes/",
        description=(
            "Lista as reuniões dos últimos 30 dias na Granola (MCP oficial) e escreve em "
            "reunioes/ as que ainda não estão lá, com o resumo da Granola. Uma nota que já "
            "existe nunca é reescrita. Sem login guardado, abre a Granola no navegador."
        ),
        epilog=CODIGOS_DE_SAIDA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(meetings_cmd)
    meetings_cmd.add_argument(
        "--agendada",
        action="store_true",
        help="é como a tarefa Whis-Reunioes chama: nunca abre o navegador e só avisa se chegou nota ou falhou",
    )
    meetings_cmd.add_argument(
        "--fakes",
        action="store_true",
        help="usa uma Granola de mentira e escreve num vault temporário (sem rede, sem login)",
    )
    meetings_cmd.set_defaults(funcao=_comando_meetings)

    hunt_cmd = subcomandos.add_parser(
        "hunt",
        help="caça vagas e freelas por horas e deixa tudo pronto em cacada/; nada é enviado",
        description=(
            "Lê as fontes de cacada/criterios.md (APIs de vaga, Workana, 99Freelas, a busca pública do "
            "LinkedIn, a web pelo Claude), monta o seu perfil, faz a triagem e prepara as chances boas: "
            "proposta pronta, preço, como enviar e, no freela web, uma amostra. Pausa quando a janela de "
            "5 h do plano bate e para perto do teto semanal. Rodar de novo retoma de onde parou."
        ),
        epilog=CODIGOS_DA_CACADA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _acrescentar_config(hunt_cmd)
    hunt_cmd.add_argument(
        "--simular",
        action="store_true",
        help="só lê as fontes e mostra quantas oportunidades cada uma trouxe (sem Claude, sem escrever)",
    )
    hunt_cmd.add_argument(
        "--fakes", action="store_true", help="a caçada inteira com portas fake num vault temporário (sem rede)"
    )
    hunt_cmd.add_argument(
        "--do-zero", action="store_true", help="ignora a caçada inacabada e começa outra"
    )
    hunt_cmd.add_argument(
        "--freelas",
        action="store_true",
        help=(
            "modo freelas rápidos: só freela pequeno de preço fechado que paga logo e casa com você; "
            "lê só as fontes de freela e vasculha a web a fundo por vários lados"
        ),
    )
    hunt_cmd.set_defaults(funcao=_comando_hunt)

    contas_cmd = subcomandos.add_parser(
        "contas",
        help="cria as contas de cacada/criterios.md com o Gmail dedicado, confirma e completa os perfis (com você no PC)",
    )
    _acrescentar_config(contas_cmd)
    contas_cmd.add_argument("--so", metavar="SITE", default=None, help="só o site cujo nome começa com isto")
    contas_cmd.add_argument("--senha", metavar="SITE", default=None, help="mostra o e-mail e a senha guardados de um site e sai")
    contas_cmd.set_defaults(funcao=_comando_contas)

    lembrete_cmd = subcomandos.add_parser(
        "lembrete", help="avisa por toast quando a semana do plano do Claude vira nas próximas 30 h (véspera da caçada)"
    )
    _acrescentar_config(lembrete_cmd)
    lembrete_cmd.add_argument(
        "--agendada", action="store_true", help="é como a tarefa Whis-Lembrete-Cacada chama: um toast só por virada"
    )
    lembrete_cmd.set_defaults(funcao=_comando_lembrete)

    candidaturas_cmd = subcomandos.add_parser(
        "candidaturas", help="atualiza cacada/candidaturas.md: pacotes, o que o Whis enviou e as respostas no Gmail"
    )
    _acrescentar_config(candidaturas_cmd)
    candidaturas_cmd.set_defaults(funcao=_comando_candidaturas)

    navegador_cmd = subcomandos.add_parser(
        "navegador", help="abre o Chrome da caçada para você entrar à mão num site (Gupy, Workana...)"
    )
    navegador_cmd.add_argument("url", nargs="?", default="https://portal.gupy.io", help="onde abrir")
    navegador_cmd.set_defaults(funcao=_comando_navegador)

    linkedin_cmd = subcomandos.add_parser(
        "linkedin",
        help="analisa o perfil do LinkedIn (pelo export de dados) e escreve rascunhos de post; nada é publicado",
    )
    _acrescentar_config(linkedin_cmd)
    linkedin_cmd.add_argument("--fakes", action="store_true", help="sem Claude, num vault temporário")
    linkedin_cmd.set_defaults(funcao=_comando_linkedin)

    linkedin_login_cmd = subcomandos.add_parser(
        "linkedin-login", help="entra no LinkedIn pela API oficial (OAuth) para o Whis poder publicar o que você aprovar"
    )
    _acrescentar_config(linkedin_login_cmd)
    linkedin_login_cmd.set_defaults(funcao=_comando_linkedin_login)

    linkedin_publicar_cmd = subcomandos.add_parser(
        "linkedin-publicar", help="publica um rascunho de linkedin/posts/ no seu perfil, depois de você confirmar"
    )
    _acrescentar_config(linkedin_publicar_cmd)
    linkedin_publicar_cmd.add_argument("nota", help="o caminho da nota, relativo ao vault (linkedin/posts/...md)")
    linkedin_publicar_cmd.set_defaults(funcao=_comando_linkedin_publicar)

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
        help="faz a bandeja subir com o logon (e, opcionalmente, agenda a daily, o jornal e as reuniões)",
        description=(
            "Amarra o Whis ao Windows. Sozinho, cria o atalho de logon da bandeja. "
            "--daily agenda a daily nos dias e horas de [daily].horarios e o vigia que "
            "avisa por toast quando uma peça do Whis não subiu; --news agenda o jornal "
            "todo dia em [noticias].horario; --meetings agenda a puxada das reuniões da "
            "Granola todo dia em [granola].horario. As tarefas rodam mesmo que o PC "
            "estivesse desligado na hora. --remover com os mesmos flags desfaz."
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
        "--meetings",
        action="store_true",
        help=(
            "também agenda a puxada das reuniões da Granola todo dia em [granola].horario "
            "(tarefa Whis-Reunioes) e reagenda o vigia, se existe, para olhar por ela"
        ),
    )
    windows_cmd.add_argument(
        "--hunt",
        action="store_true",
        help=(
            "também agenda o lembrete da véspera da caçada todo dia em [cacada].hora_do_lembrete "
            "(tarefa Whis-Lembrete-Cacada); a caçada em si continua só quando você chama"
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
