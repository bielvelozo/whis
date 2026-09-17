"""A palheta: um campo de texto, o comando, e a janela some.

O contrato é **dispara e some**: `despachar(texto)` devolve na hora, o comando
roda num thread de trabalho, o resultado vira nota no vault quando há nota, e
um toast avisa ao terminar — com o botão "Abrir no Obsidian" quando há o que
abrir. Nenhum comando cabe numa janela que se fica olhando: a pergunta leva um
minuto e a daily quarenta segundos.

Este módulo é costura pura: não conhece Tk, bandeja nem teclado. O registro de
comandos é dados (`Comando`, em inglês desde a prova do usuário: `daily`,
`note`, `doubt`, `ask`, `open`, `record`, `settings`), `interpretar` lê o
texto digitado, `Palheta` despacha e transforma `Resultado` em toast. As
portas de verdade — as fontes, o roteiro, a busca — entram por
`comandos_padrao`, e é por aí que `--fakes` da bandeja chega aqui. `record` e
`settings` são da própria `Palheta`, porque gravar e abrir o painel são de
quem a hospeda: a bandeja injeta `gravar`/`gravando` e `abrir_painel`.

Dois cuidados que vêm do custo: um comando custa dinheiro e minutos, então um
despacho enquanto outro roda é **recusado** com um toast curto, e a falha de
um comando vira toast com a mensagem — nunca exceção solta num thread.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from . import avisos as _avisos
from . import vault as _vault
from .busca import PortaBusca, Resposta
from .configuracao import Configuracao
from .conversa import Conversas
from .daily import ResultadoDaDaily, gerar_daily
from .fontes import PortaFonte
from .nota_viva import SECAO_DUVIDAS, SECAO_PONTOS
from .obsidian import lancar as _lancar_no_windows
from .obsidian import uri_da_nota
from .pergunta import responder
from .portas import PortaDaily

_log = logging.getLogger("whis.palheta")

#: A chave do fio da palheta em `conversas.json`; o terminal e a DM têm as suas.
FIO_DA_PALHETA = "palheta"

ROTULO_DO_BOTAO = "Abrir no Obsidian"
TITULO_DO_TOAST_DA_DAILY = "A daily está pronta"
TITULO_DA_DAILY_QUE_NAO_NASCEU = "A daily não nasceu"
TITULO_DA_RESPOSTA = "Whis"
TITULO_DE_NAO_ACHOU = "Não achei"
TITULO_DE_OCUPADA = "Ainda estou no comando anterior"
TITULO_DE_FALHA = "O comando falhou"
TITULO_DE_NAO_ENTENDI = "Não entendi"

NOME_DE_GRAVAR = "record"
NOME_DE_CONFIGURAR = "settings"

#: A ordem em que as ações aparecem na janela: as três que o usuário pediu
#: primeiro, e existem mesmo com o campo vazio.
ORDEM_DAS_ACOES = ("open", "daily", NOME_DE_GRAVAR, "ask", "note", "doubt", NOME_DE_CONFIGURAR)

#: Quanto da resposta cabe no toast: o resto está na nota que o botão abre.
LIMITE_DO_TEXTO_DO_TOAST = 240


@dataclass(frozen=True)
class Resultado:
    """O que um comando devolve, e que a palheta transforma no toast.

    `nota` é o caminho relativo ao vault da nota que o botão abre; `None` é
    toast sem botão.
    """

    titulo: str
    texto: str
    nota: str | None = None


#: `rodar(argumento, configuracao)`: a configuração vem da palheta a cada
#: chamada, para o painel poder recarregá-la sem reconstruir os comandos.
Rodar = Callable[[str, Configuracao], "Resultado | None"]


@dataclass(frozen=True)
class Comando:
    """Uma entrada do registro: o nome digitado, o que a lista mostra e quem roda.

    `rotulo` é o título da linha na janela (em inglês, como o comando) e pode
    ser função, para "Start recording" virar "Stop recording"; `descricao` é a
    frase curta embaixo; `icone` é um glifo em texto.
    """

    nome: str
    ajuda: str
    rodar: Rodar
    parametro: str = ""
    rotulo: str | Callable[[], str] = ""
    descricao: str = ""
    icone: str = ""

    def uso(self) -> str:
        return f"{self.nome} <{self.parametro}>" if self.parametro else self.nome

    def rotulo_atual(self) -> str:
        if callable(self.rotulo):
            return self.rotulo()
        return self.rotulo or self.nome.capitalize()


class ComandoDesconhecido(ValueError):
    """A primeira palavra não é comando nenhum — a mensagem lista os que existem."""


def interpretar(texto: str, comandos: Sequence[Comando]) -> tuple[Comando, str]:
    """A primeira palavra é o comando (sem diferenciar maiúsculas); o resto é o argumento."""
    partes = texto.strip().split(None, 1)
    if not partes:
        raise ComandoDesconhecido(f"Escreva um comando. {_lista(comandos)}")

    nome = partes[0].casefold()
    argumento = partes[1].strip() if len(partes) > 1 else ""
    comando = _por_nome(comandos, nome)
    if comando is None:
        raise ComandoDesconhecido(f"Não conheço '{partes[0]}'. {_lista(comandos)}")
    return comando, argumento


def _por_nome(comandos: Sequence[Comando], nome: str) -> Comando | None:
    return next((comando for comando in comandos if comando.nome == nome), None)


def _lista(comandos: Sequence[Comando]) -> str:
    return "Comandos: " + ", ".join(comando.uso() for comando in comandos) + "."


#: Quem roda uma função em segundo plano — síncrono nos testes.
IniciarThread = Callable[[Callable[[], None]], None]


def _em_thread(alvo: Callable[[], None]) -> None:
    threading.Thread(target=alvo, name="whis-palheta", daemon=True).start()


class Palheta:
    """O despacho: lê o texto, roda o comando em segundo plano e avisa ao terminar.

    `configuracao` é atributo público de propósito: o painel a recarrega
    depois de salvar, e o próximo comando já roda com a nova. `abrir_painel`,
    `gravar` e `gravando` são preenchidos por quem hospeda a palheta (a
    bandeja): abrir uma janela é coisa do thread do Tk, e gravar é do coletor.
    """

    def __init__(
        self,
        comandos: Sequence[Comando],
        configuracao: Configuracao,
        *,
        avisar: Callable[..., bool] | None = None,
        iniciar_thread: IniciarThread | None = None,
        abrir_painel: Callable[[], None] | None = None,
        gravar: Callable[[], None] | None = None,
        gravando: Callable[[], bool] | None = None,
    ) -> None:
        self.configuracao = configuracao
        self.abrir_painel = abrir_painel or self._painel_indisponivel
        self.gravar = gravar or self._gravador_indisponivel
        self.gravando = gravando or (lambda: False)
        self._avisar = avisar
        self._iniciar_thread = iniciar_thread or _em_thread
        self._ocupada = threading.Lock()
        proprios = [
            Comando(
                NOME_DE_GRAVAR,
                "começa a gravar a reunião, ou para e processa",
                self._gravar,
                rotulo=self._rotulo_de_gravar,
                descricao="Toggle the meeting recorder in the tray",
                icone="●",
            ),
            Comando(
                NOME_DE_CONFIGURAR,
                "abre o painel de configuração",
                self._configurar,
                rotulo="Settings",
                descricao="Open the settings panel (all config keys)",
                icone="⚙",
            ),
        ]
        registrados = [comando.nome for comando in comandos]
        self.comandos: tuple[Comando, ...] = (
            *comandos,
            *(comando for comando in proprios if comando.nome not in registrados),
        )

    def acoes(self) -> tuple[Comando, ...]:
        """Os comandos na ordem da lista da janela: as três ações pedidas primeiro."""
        posicao = {nome: indice for indice, nome in enumerate(ORDEM_DAS_ACOES)}
        return tuple(
            sorted(self.comandos, key=lambda comando: posicao.get(comando.nome, len(posicao)))
        )

    def despachar(self, texto: str) -> bool:
        """Dispara o comando e devolve na hora. `False` quando outro ainda roda.

        Texto vazio não faz nada — Enter na palheta vazia só a esconde. A
        recusa vira toast num thread próprio: quem chama é o handler da
        janela, e mostrar um toast custa um processo do PowerShell.
        """
        if not texto.strip():
            return False
        if not self._ocupada.acquire(blocking=False):
            _log.info("Palheta ocupada; pedido recusado: %r", _resumido(texto))
            self._iniciar_thread(
                lambda: self.avisar(
                    Resultado(
                        TITULO_DE_OCUPADA,
                        f"Quando terminar eu aviso. Ficou de fora: {_resumido(texto)}",
                    )
                )
            )
            return False
        self._iniciar_thread(lambda: self._rodar(texto))
        return True

    def ocupada(self) -> bool:
        return self._ocupada.locked()

    def avisar(self, resultado: Resultado) -> bool:
        return avisar_resultado(self.configuracao, resultado, avisar=self._avisar)

    def _rodar(self, texto: str) -> None:
        try:
            resultado = self._executar(texto)
        except Exception as erro:  # noqa: BLE001 — nenhuma exceção fica solta no thread
            _log.exception("O comando da palheta falhou: %r", _resumido(texto))
            resultado = Resultado(TITULO_DE_FALHA, str(erro) or type(erro).__name__)
        finally:
            self._ocupada.release()
        if resultado is not None:
            self.avisar(resultado)

    def _executar(self, texto: str) -> Resultado | None:
        try:
            comando, argumento = interpretar(texto, self.comandos)
        except ComandoDesconhecido as erro:
            return Resultado(TITULO_DE_NAO_ENTENDI, str(erro))
        _log.info("Palheta: %s %s", comando.nome, _resumido(argumento))
        return comando.rodar(argumento, self.configuracao)

    def _configurar(self, _argumento: str, _configuracao: Configuracao) -> None:
        self.abrir_painel()
        return None

    def _gravar(self, _argumento: str, _configuracao: Configuracao) -> None:
        self.gravar()
        return None

    def _rotulo_de_gravar(self) -> str:
        return "Stop recording" if self.gravando() else "Start recording"

    @staticmethod
    def _painel_indisponivel() -> None:
        raise RuntimeError("O painel de configuração não está disponível nesta execução.")

    @staticmethod
    def _gravador_indisponivel() -> None:
        raise RuntimeError("Gravar só funciona com a palheta hospedada na bandeja.")


def avisar_resultado(
    configuracao: Configuracao, resultado: Resultado, *, avisar: Callable[..., bool] | None = None
) -> bool:
    """O toast de um resultado: com o botão do Obsidian quando há nota.

    `avisos.avisar` é resolvido na chamada, e não na importação, para o teste
    poder espioná-lo no módulo.
    """
    mostrar = avisar or _avisos.avisar
    botao = (ROTULO_DO_BOTAO, uri_da_nota(configuracao, resultado.nota)) if resultado.nota else None
    return mostrar(resultado.titulo, resultado.texto, botao=botao)


# -- os comandos desta entrega ----------------------------------------------


def texto_do_toast_da_daily(resultado: ResultadoDaDaily) -> str:
    """Uma linha: o que mudou na nota viva, ou por que nada mudou."""
    if resultado.vazio:
        return "Nada aconteceu desde a última daily — nenhuma nota foi escrita."
    if resultado.falha_do_roteiro:
        return (
            f"A nota nasceu parcial: {resultado.falha_do_roteiro}. "
            f"A nota viva ficou como estava."
        )
    mudancas = resultado.mudancas
    if mudancas is None or mudancas.vazia():
        return "Nada mudou na nota viva."
    partes: list[str] = []
    if novos := len(mudancas.acrescentadas):
        partes.append(f"{novos} {'item novo' if novos == 1 else 'itens novos'}")
    if movidos := len(mudancas.movidas):
        partes.append(f"{movidos} {'movido' if movidos == 1 else 'movidos'} para 'O que eu fiz'")
    return " e ".join(partes) + "."


def resultado_da_daily(resultado: ResultadoDaDaily) -> Resultado:
    """O toast da daily — o mesmo para `whis daily` e para a palheta."""
    if resultado.nota_viva is None:
        return Resultado(TITULO_DA_DAILY_QUE_NAO_NASCEU, texto_do_toast_da_daily(resultado))
    return Resultado(
        TITULO_DO_TOAST_DA_DAILY,
        texto_do_toast_da_daily(resultado),
        nota=_vault.CAMINHO_DA_NOTA_VIVA,
    )


def resultado_da_resposta(resposta: Resposta, nota: str) -> Resultado:
    """O toast de `ask`: o começo da resposta; a nota tem o resto e as fontes."""
    if not resposta.achou:
        texto = resposta.texto.strip() or "Nenhuma nota do vault sustenta uma resposta."
        return Resultado(TITULO_DE_NAO_ACHOU, _encurtar(texto), nota=nota)
    return Resultado(TITULO_DA_RESPOSTA, _encurtar(resposta.texto.strip() or "(vazia)"), nota=nota)


def comandos_padrao(
    *,
    fontes_da_daily: Callable[[Configuracao], Sequence[PortaFonte]],
    roteiro_da_daily: Callable[[Configuracao], PortaDaily],
    busca: Callable[[Configuracao], PortaBusca],
    lancar: Callable[[str], None] | None = None,
    relogio: Callable[[], datetime] | None = None,
) -> tuple[Comando, ...]:
    """Os cinco comandos que tocam o vault, com as portas injetadas.

    As fábricas recebem a configuração a cada chamada — é o que faz uma
    configuração recarregada valer no comando seguinte. `record` e
    `settings` são da própria `Palheta`.
    """
    agora = relogio or (lambda: datetime.now().astimezone())
    lancar_alvo = lancar or _lancar_no_windows

    def daily(_argumento: str, configuracao: Configuracao) -> Resultado:
        resultado = gerar_daily(
            agora(),
            configuracao=configuracao,
            fontes=fontes_da_daily(configuracao),
            roteiro=roteiro_da_daily(configuracao),
        )
        return resultado_da_daily(resultado)

    def anotar_em(secao: str, nome: str) -> Rodar:
        def anotar(texto: str, configuracao: Configuracao) -> Resultado:
            if not texto.strip():
                return Resultado("Anotar o quê?", f"Escreva `{nome} <o texto>`.")
            raiz = _vault.preparar(configuracao.vault)
            _vault.anotar_ponto(raiz, texto, secao)
            return Resultado(f"Anotado em {secao}", texto.strip(), nota=_vault.CAMINHO_DA_NOTA_VIVA)

        return anotar

    def perguntar(pergunta: str, configuracao: Configuracao) -> Resultado:
        if not pergunta.strip():
            return Resultado("Perguntar o quê?", "Escreva `ask <a pergunta>`.")
        momento = agora()
        conversas = Conversas.de_configuracao(configuracao)
        conversa = conversas.abrir(FIO_DA_PALHETA, agora=momento)
        resposta = responder(
            pergunta,
            configuracao=configuracao,
            busca=busca(configuracao),
            conversa=conversa,
            agora=momento,
        )
        conversas.guardar(FIO_DA_PALHETA, conversa)

        raiz = _vault.preparar(configuracao.vault)
        caminho = _vault.caminho_da_resposta(momento, pergunta)
        _vault.escrever(
            raiz,
            caminho,
            _vault.montar_resposta(pergunta=pergunta, resposta=resposta),
            zonas=_vault.ZONAS_DAS_RESPOSTAS,
        )
        return resultado_da_resposta(resposta, caminho)

    def abrir(_argumento: str, configuracao: Configuracao) -> None:
        lancar_alvo(uri_da_nota(configuracao, _vault.CAMINHO_DA_NOTA_VIVA))
        return None

    return (
        Comando(
            "open",
            "abre daily/atual.md no Obsidian",
            abrir,
            rotulo="Open note",
            descricao="daily/atual.md in Obsidian",
            icone="▤",
        ),
        Comando(
            "daily",
            "gera a daily agora e mantém daily/atual.md",
            daily,
            rotulo="Generate daily",
            descricao="Update daily/atual.md from git, Linear and Slack (~40 s)",
            icone="☀",
        ),
        Comando(
            "ask",
            "pergunta ao vault; a resposta vira nota em respostas/",
            perguntar,
            parametro="question",
            rotulo="Ask",
            descricao="Ask the vault; the answer becomes a note in respostas/ (~60 s)",
            icone="?",
        ),
        Comando(
            "note",
            f"acrescenta uma linha em {SECAO_PONTOS} da nota viva",
            anotar_em(SECAO_PONTOS, "note"),
            parametro="text",
            rotulo="Note",
            descricao=f"Add a line to {SECAO_PONTOS} in daily/atual.md",
            icone="✎",
        ),
        Comando(
            "doubt",
            f"acrescenta uma linha em {SECAO_DUVIDAS} da nota viva",
            anotar_em(SECAO_DUVIDAS, "doubt"),
            parametro="text",
            rotulo="Doubt",
            descricao=f"Add a line to {SECAO_DUVIDAS} in daily/atual.md",
            icone="¿",
        ),
    )


def _encurtar(texto: str, limite: int = LIMITE_DO_TEXTO_DO_TOAST) -> str:
    limpo = " ".join(texto.split())
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 1].rstrip() + "…"


def _resumido(texto: str, tamanho: int = 80) -> str:
    return _encurtar(texto, tamanho)
