"""A palheta: um campo de texto, o comando, e a janela some.

O contrato é **dispara e some**: `despachar(texto)` devolve na hora, o comando
roda num thread de trabalho, o resultado vira nota no vault quando há nota, e
um toast avisa ao terminar — com o botão "Abrir no Obsidian" quando há o que
abrir. Nenhum comando cabe numa janela que se fica olhando: a pergunta leva um
minuto e a daily quarenta segundos.

Este módulo é costura pura: não conhece Tk, bandeja nem teclado. O registro de
comandos é dados (`Comando`), `interpretar` lê o texto digitado, `Palheta`
despacha e transforma `Resultado` em toast. As portas de verdade — as fontes,
o roteiro, a busca — entram por `comandos_padrao`, e é por aí que `--fakes` da
bandeja chega aqui.

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
from .nota_viva import SECAO_FALAR
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
TITULO_DA_AJUDA = "Comandos da palheta"
TITULO_DE_OCUPADA = "Ainda estou no comando anterior"
TITULO_DE_FALHA = "O comando falhou"
TITULO_DE_NAO_ENTENDI = "Não entendi"

NOME_DA_AJUDA = "ajuda"
NOME_DE_CONFIGURAR = "configurar"

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
    """Uma entrada do registro: o nome digitado, a ajuda e quem roda."""

    nome: str
    ajuda: str
    rodar: Rodar
    parametro: str = ""

    def uso(self) -> str:
        return f"{self.nome} <{self.parametro}>" if self.parametro else self.nome


class ComandoDesconhecido(ValueError):
    """A primeira palavra não é comando nenhum — a mensagem lista os que existem."""


def interpretar(texto: str, comandos: Sequence[Comando]) -> tuple[Comando, str]:
    """A primeira palavra é o comando (sem diferenciar maiúsculas); o resto é o argumento.

    Texto vazio é `ajuda`, quando ela está no registro: Enter na palheta vazia
    é a pergunta "o que você faz?".
    """
    partes = texto.strip().split(None, 1)
    if not partes:
        ajuda = _por_nome(comandos, NOME_DA_AJUDA)
        if ajuda is None:
            raise ComandoDesconhecido(f"Escreva um comando. {_lista(comandos)}")
        return ajuda, ""

    nome = partes[0].casefold()
    argumento = partes[1].strip() if len(partes) > 1 else ""
    comando = _por_nome(comandos, nome)
    if comando is None:
        raise ComandoDesconhecido(f"Não conheço '{partes[0]}'. {_lista(comandos)}")
    return comando, argumento


def ajuda(comandos: Sequence[Comando]) -> str:
    """Uma linha por comando: `uso — ajuda`."""
    return "\n".join(f"{comando.uso()} — {comando.ajuda}" for comando in comandos)


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
    depois de salvar, e o próximo comando já roda com a nova. `abrir_painel`
    é preenchido por quem hospeda a palheta (a bandeja), porque abrir uma
    janela é coisa do thread do Tk.
    """

    def __init__(
        self,
        comandos: Sequence[Comando],
        configuracao: Configuracao,
        *,
        avisar: Callable[..., bool] | None = None,
        iniciar_thread: IniciarThread | None = None,
        abrir_painel: Callable[[], None] | None = None,
    ) -> None:
        self.configuracao = configuracao
        self.abrir_painel = abrir_painel or self._painel_indisponivel
        self._avisar = avisar
        self._iniciar_thread = iniciar_thread or _em_thread
        self._ocupada = threading.Lock()
        proprios = [
            Comando(NOME_DE_CONFIGURAR, "abre o painel de configuração", self._configurar),
            Comando(NOME_DA_AJUDA, "esta lista", self._ajuda),
        ]
        registrados = [comando.nome for comando in comandos]
        self.comandos: tuple[Comando, ...] = (
            *comandos,
            *(comando for comando in proprios if comando.nome not in registrados),
        )

    def despachar(self, texto: str) -> bool:
        """Dispara o comando e devolve na hora. `False` quando outro ainda roda.

        A recusa também vira toast, mas num thread próprio: quem chama é o
        handler da janela, e mostrar um toast custa um processo do PowerShell.
        """
        if not self._ocupada.acquire(blocking=False):
            _log.info("Palheta ocupada; pedido recusado: %r", _resumido(texto))
            self._iniciar_thread(
                lambda: self.avisar(
                    Resultado(
                        TITULO_DE_OCUPADA,
                        f"Quando terminar eu aviso. Ficou de fora: {_resumido(texto) or '(vazio)'}",
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

    def _ajuda(self, _argumento: str, _configuracao: Configuracao) -> Resultado:
        return Resultado(TITULO_DA_AJUDA, ajuda(self.comandos))

    def _configurar(self, _argumento: str, _configuracao: Configuracao) -> None:
        self.abrir_painel()
        return None

    @staticmethod
    def _painel_indisponivel() -> None:
        raise RuntimeError("O painel de configuração não está disponível nesta execução.")


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
    """O toast de `perguntar`: o começo da resposta; a nota tem o resto e as fontes."""
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
    """Os quatro comandos que tocam o vault, com as portas injetadas.

    As fábricas recebem a configuração a cada chamada — é o que faz uma
    configuração recarregada valer no comando seguinte. `configurar` e `ajuda`
    são da própria `Palheta`.
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

    def anotar(texto: str, configuracao: Configuracao) -> Resultado:
        if not texto.strip():
            return Resultado("Anotar o quê?", "Escreva `anotar <o que você quer levantar na daily>`.")
        raiz = _vault.preparar(configuracao.vault)
        _vault.anotar_ponto(raiz, texto)
        return Resultado(
            f"Anotado em {SECAO_FALAR}", texto.strip(), nota=_vault.CAMINHO_DA_NOTA_VIVA
        )

    def perguntar(pergunta: str, configuracao: Configuracao) -> Resultado:
        if not pergunta.strip():
            return Resultado("Perguntar o quê?", "Escreva `perguntar <a pergunta>`.")
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
        Comando("daily", "gera a daily agora e mantém daily/atual.md", daily),
        Comando("anotar", "acrescenta uma linha em Falar da nota viva", anotar, parametro="texto"),
        Comando(
            "perguntar",
            "pergunta ao vault; a resposta vira nota em respostas/",
            perguntar,
            parametro="pergunta",
        ),
        Comando("abrir", "abre daily/atual.md no Obsidian", abrir),
    )


def _encurtar(texto: str, limite: int = LIMITE_DO_TEXTO_DO_TOAST) -> str:
    limpo = " ".join(texto.split())
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 1].rstrip() + "…"


def _resumido(texto: str, tamanho: int = 80) -> str:
    return _encurtar(texto, tamanho)
