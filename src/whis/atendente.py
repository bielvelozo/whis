"""O atendente: o agente morando numa DM do Slack.

É a entrega inteira do ponto de vista do usuário. Ele manda mensagem na DM do
bot, a qualquer hora, do PC ou do celular; o bot reage na hora (uma busca
demora, e silêncio parece pane), pergunta ao vault pela costura `responder` e
publica a resposta ali mesmo, citando as notas. O fio de 24 horas da camada 01
vale por DM: a chave em `conversas.json` é o id do canal.

Este módulo é casca fina sobre `pergunta.responder`, como a bandeja é sobre o
coletor: nenhuma lógica de busca vive aqui. O Slack entra pela porta `PortaDM`,
que os testes substituem por `fakes.DMFake` entregando mensagens de fixture.

Regras que valem sempre:

- Só a **DM com o bot** é atendida. Mensagem em canal, group DM ou de outro
  bot é ignorada, e a própria mensagem do bot também — senão ele responde a si
  mesmo em laço.
- **Nada derruba o processo.** Uma resposta que falha vira mensagem de erro em
  português na DM, e o atendimento continua na próxima.
- A única escrita no vault é o pedido explícito `anotar <texto>`, que acrescenta
  um ponto em `notas/daily.md` pelo mesmo caminho de `daily --anotar` — sem
  passar pelo modelo, para a zona do usuário continuar dele.

É um processo separado da bandeja de propósito: ela tem trava de instância e
máquina de estados de gravação, e o pipeline de reunião está em uso real.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from . import registro as _registro
from . import vault as _vault
from .busca import ErroDeBusca, PortaBusca, Resposta
from .configuracao import Configuracao
from .conversa import Conversas
from .instancia import OutraInstancia, Trava
from .pergunta import SEM_RESPOSTA, PerguntaVazia, responder

_log = logging.getLogger("whis.atendente")

#: A reação que diz "recebi, estou procurando".
EMOJI_RECEBIDA = "eyes"

#: Quanto tempo `proxima` espera por mensagem antes de checar se é para parar.
INTERVALO_S = 1.0

#: O único tipo de conversa atendido.
DM = "im"

NOME_DA_TRAVA = "atendente.lock"

_PEDIDO_DE_ANOTACAO = re.compile(r"^\s*anotar\b\s*[:\-—]?\s*(?P<texto>.*)$", re.IGNORECASE | re.DOTALL)
_LINK_MARKDOWN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_NEGRITO_MARKDOWN = re.compile(r"\*\*([^*]+)\*\*")


@dataclass(frozen=True)
class Mensagem:
    """Uma mensagem como o Slack a entrega, já reduzida ao que o atendente usa."""

    canal: str
    usuario: str
    texto: str
    ts: str
    tipo_de_canal: str = DM
    subtipo: str | None = None
    do_bot: bool = False


class ErroDeDM(RuntimeError):
    """O Slack não pôde ser alcançado — token, rede, ou a app sem Socket Mode."""


@runtime_checkable
class PortaDM(Protocol):
    """A DM do bot: receber mensagens, reagir e responder."""

    def iniciar(self) -> str:
        """Conecta e devolve o id de usuário do bot. Levanta `ErroDeDM`."""
        ...

    def proxima(self, timeout_s: float) -> Mensagem | None:
        """A próxima mensagem recebida, ou `None` se nenhuma chegou a tempo."""
        ...

    def reagir(self, mensagem: Mensagem, emoji: str) -> None: ...

    def responder(self, mensagem: Mensagem, texto: str) -> None: ...

    def encerrar(self) -> None: ...


class Atendente:
    """Recebe cada mensagem da DM, responde e mantém o fio por conversa."""

    def __init__(
        self,
        configuracao: Configuracao,
        *,
        dm: PortaDM,
        busca: PortaBusca,
        conversas: Conversas | None = None,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self._configuracao = configuracao
        self._dm = dm
        self._busca = busca
        self._conversas = conversas
        self._relogio = relogio or (lambda: datetime.now().astimezone())
        self.eu = ""

    def executar(self, *, parar: threading.Event | None = None) -> int:
        """Atende até `parar` ser sinalizado. Devolve quantas mensagens atendeu."""
        parar = parar or threading.Event()
        self.eu = self._dm.iniciar()
        _log.info("Atendente no ar como %s; só a DM comigo é atendida.", self.eu)
        atendidas = 0
        try:
            while not parar.is_set():
                mensagem = self._dm.proxima(INTERVALO_S)
                if mensagem is None:
                    continue
                if self.atender(mensagem):
                    atendidas += 1
        finally:
            self._dm.encerrar()
            _log.info("Atendente encerrado depois de %d mensagem(ns).", atendidas)
        return atendidas

    def atender(self, mensagem: Mensagem) -> bool:
        """Uma mensagem: filtra, reage, responde. Devolve se era para atender."""
        if not self._e_para_mim(mensagem):
            _log.debug("Ignorada: canal %s (%s), de %s.", mensagem.canal, mensagem.tipo_de_canal, mensagem.usuario)
            return False
        _log.info("Mensagem na DM %s: %r", mensagem.canal, _resumida(mensagem.texto))
        try:
            self._dm.reagir(mensagem, EMOJI_RECEBIDA)
        except ErroDeDM as erro:
            _log.warning("Não consegui reagir à mensagem (sigo respondendo): %s", erro)
        texto = self.responder(mensagem)
        try:
            self._dm.responder(mensagem, texto)
        except ErroDeDM as erro:
            _log.error("Não consegui publicar a resposta na DM %s: %s", mensagem.canal, erro)
        return True

    def responder(self, mensagem: Mensagem) -> str:
        """O texto da resposta. Nunca levanta: falha vira mensagem em português."""
        pedido = _PEDIDO_DE_ANOTACAO.match(mensagem.texto)
        if pedido is not None:
            return self._anotar(pedido.group("texto").strip())

        agora = self._relogio()
        conversa = self._conversas.abrir(mensagem.canal, agora=agora) if self._conversas else None
        try:
            resposta = responder(
                mensagem.texto,
                configuracao=self._configuracao,
                busca=self._busca,
                conversa=conversa,
                agora=agora,
            )
        except PerguntaVazia:
            return "Manda a pergunta junto — a mensagem veio vazia."
        except ErroDeBusca as erro:
            _log.error("A busca falhou na DM %s: %s", mensagem.canal, erro)
            return f"Não consegui responder agora: {erro}"
        except Exception as erro:  # noqa: BLE001 — o atendente fica no ar o dia inteiro
            # Qualquer exceção que escapasse aqui derrubaria o processo sem
            # ninguém olhando, e o usuário só descobriria na próxima pergunta
            # sem resposta. O rastro completo vai ao log.
            _log.exception("Erro inesperado respondendo na DM %s", mensagem.canal)
            return (
                f"Não consegui responder agora: erro inesperado ({type(erro).__name__}). "
                f"O detalhe está no log."
            )
        if self._conversas is not None and conversa is not None:
            self._conversas.guardar(mensagem.canal, conversa)
        return formatar_para_slack(resposta)

    def _anotar(self, texto: str) -> str:
        if not texto:
            return "Anotar o quê? Manda `anotar <o que você quer levantar na daily>`."
        raiz = _vault.preparar(self._configuracao.vault)
        _vault.anotar_ponto(raiz, texto)
        _log.info("Ponto anotado pela DM em %s", _vault.ARQUIVO_DE_PONTOS)
        return (
            f"Anotado em `{_vault.ARQUIVO_DE_PONTOS}`. "
            f"Entra na próxima daily enquanto o checkbox estiver desmarcado."
        )

    def _e_para_mim(self, mensagem: Mensagem) -> bool:
        return (
            mensagem.tipo_de_canal == DM
            and not mensagem.do_bot
            and mensagem.usuario != self.eu
            and mensagem.subtipo is None
            and bool(mensagem.texto.strip())
        )


def formatar_para_slack(resposta: Resposta) -> str:
    """A resposta no mrkdwn do Slack, com as fontes embaixo."""
    partes = [_mrkdwn(resposta.texto.strip() or SEM_RESPOSTA)]
    if resposta.citacoes:
        fontes = [
            f"• `{citacao.origem}`" + (f" — {_mrkdwn(citacao.trecho)}" if citacao.trecho else "")
            for citacao in resposta.citacoes
        ]
        partes.append("_Fontes:_\n" + "\n".join(fontes))
    if not resposta.achou:
        partes.append("_(nada no vault sustenta uma resposta — não estou inventando)_")
    return "\n\n".join(partes)


def caminho_da_trava(configuracao: Configuracao) -> Path:
    base = configuracao.origem.parent if configuracao.origem else Path.home()
    return base / NOME_DA_TRAVA


def executar(
    configuracao: Configuracao,
    *,
    dm: PortaDM,
    busca: PortaBusca,
    verboso: bool = False,
    parar: threading.Event | None = None,
) -> int:
    """Sobe o atendente com a DM e a busca de verdade. É o que o subcomando chama.

    Trava de instância própria: dois atendentes responderiam cada pergunta
    duas vezes. `Ctrl+C` encerra limpo.
    """
    trava = Trava(caminho_da_trava(configuracao))
    try:
        trava.adquirir()
    except OutraInstancia as erro:
        print(str(erro).replace("uma bandeja", "um atendente"))
        return 1

    destino = _registro.acrescentar_arquivo(configuracao, verboso=verboso)
    atendente = Atendente(
        configuracao, dm=dm, busca=busca, conversas=Conversas.de_configuracao(configuracao)
    )
    try:
        print(f"Atendente do Whis subindo. Log em {destino}", flush=True)
        try:
            atendente.executar(parar=parar)
        except KeyboardInterrupt:
            _log.info("Atendente encerrado pelo usuário.")
        except ErroDeDM as erro:
            _log.error("O atendente não conseguiu ficar no ar: %s", erro)
            return 1
    finally:
        trava.liberar()
    return 0


def _mrkdwn(texto: str) -> str:
    """Do markdown que o modelo escreve para o mrkdwn que o Slack renderiza."""
    texto = _LINK_MARKDOWN.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", texto)
    return _NEGRITO_MARKDOWN.sub(r"*\1*", texto)


def _resumida(texto: str, tamanho: int = 80) -> str:
    limpo = " ".join(texto.split())
    return limpo if len(limpo) <= tamanho else limpo[: tamanho - 1] + "…"
