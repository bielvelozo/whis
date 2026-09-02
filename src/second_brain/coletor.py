"""O coletor de reunião: liga, desliga e a nota aparece no vault.

Este módulo é o **coletor** do glossário (`CONTEXT.md`): captura um sinal — o
áudio da reunião — e o transforma em notas no vault. É a costura entre o
gravador (camada 02) e o pipeline (camada 01, com os adaptadores reais das
camadas 03 e 04), e existe separado da bandeja de propósito:

- a **bandeja** (`second_brain.bandeja`) é pixels, cliques e balões do Windows;
- o **coletor** é a máquina de estados por trás dela, sem nenhuma dependência
  de UI — o que permite provar por teste tudo o que a bandeja promete.

Nenhuma lógica de pipeline vive aqui: `processar()` continua sendo a costura
única, chamada como qualquer outro comando a chamaria. O que este módulo
acrescenta é o que a bandeja precisa e o terminal não precisava — parar a
gravação sem bloquear a interface, lembrar do último resultado e **nunca
engolir uma falha**.

Estados possíveis::

    PARADO ──iniciar()──> GRAVANDO ──parar()──> PROCESSANDO ──┬──> PARADO
                                                              └──> ERRO

`ERRO` é um estado visível de propósito: a gravação continua retida no disco e
o comando `reprocessar` (camada 06) a completa depois. Sair do erro é começar a
próxima reunião — ou chamar `reconhecer_erro()`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import gravador as _gravador
from . import pipeline as _pipeline
from .configuracao import Configuracao
from .portas import PortaResumo, PortaSTT

_log = logging.getLogger("second_brain.coletor")


class Estado(str, Enum):
    """O que o coletor está fazendo agora — e o que a bandeja desenha."""

    PARADO = "parado"
    GRAVANDO = "gravando"
    PROCESSANDO = "processando"
    ERRO = "erro"


#: RMS abaixo disto é silêncio digital — o mesmo limiar que o gravador usa.
LIMIAR_RMS_MUDO = 1.0

#: Quanto esperar antes de conferir se algum canal está mudo. Tempo suficiente
#: para alguém falar no começo da reunião, e cedo o bastante para consertar.
SEGUNDOS_ATE_CONFERIR_CANAIS = 20.0


@dataclass(frozen=True)
class Situacao:
    """Uma leitura instantânea do coletor, para a interface desenhar.

    É um retrato imutável: a bandeja lê isto a cada mudança em vez de
    perguntar campo a campo a um objeto que outra thread está mexendo.

    `aviso` é a reunião saindo torta sem estar falhando: o caso real é o canal
    do sistema mudo, que produz uma nota só com a sua voz.
    """

    estado: Estado
    pasta: Path | None = None
    titulo: str | None = None
    nota: Path | None = None
    erro: str | None = None
    aviso: str | None = None

    @property
    def gravando(self) -> bool:
        return self.estado is Estado.GRAVANDO

    @property
    def ocupado(self) -> bool:
        """Gravando ou processando — há trabalho em curso."""
        return self.estado in (Estado.GRAVANDO, Estado.PROCESSANDO)

    def descricao(self) -> str:
        """A frase que a bandeja mostra no tooltip, sempre em português."""
        if self.estado is Estado.GRAVANDO:
            gravando = f"Gravando: {self.titulo or 'reunião'}"
            return f"{gravando} — {self.aviso}" if self.aviso else gravando
        if self.estado is Estado.PROCESSANDO:
            return "Processando a reunião (transcrição e resumo)..."
        if self.estado is Estado.ERRO:
            return f"Falhou: {self.erro or 'erro desconhecido'}"
        if self.nota is not None:
            return f"Pronto. Última nota: {self.nota.name}"
        return "Parado. Clique para gravar a reunião."


class Coletor:
    """Liga e desliga a gravação; ao desligar, a reunião vira nota no vault.

    A bandeja chama três coisas — `iniciar()`, `parar()` e `alternar()` — e lê
    `situacao()`. Todo o resto é bastidor.

    O processamento roda em outra thread porque a transcrição e o resumo levam
    minutos: com a interface bloqueada, o usuário não saberia se o programa
    morreu. Em teste, `em_segundo_plano=False` torna tudo síncrono e o
    comportamento observável é o mesmo.

    `ao_mudar` é chamado a cada transição de estado, com a `Situacao` nova. É
    por onde a bandeja repinta o ícone; qualquer exceção dentro dele é logada e
    ignorada, porque uma interface quebrada não pode derrubar uma reunião.
    """

    def __init__(
        self,
        configuracao: Configuracao,
        *,
        portas: Callable[[], tuple[PortaSTT, PortaResumo]],
        gravador: object | None = None,
        ao_mudar: Callable[[Situacao], None] | None = None,
        em_segundo_plano: bool = True,
        segundos_ate_conferir_canais: float = SEGUNDOS_ATE_CONFERIR_CANAIS,
    ) -> None:
        self._configuracao = configuracao
        self._portas = portas
        self._gravador = gravador
        self._ao_mudar = ao_mudar
        self._em_segundo_plano = em_segundo_plano
        self._espera_do_aviso = segundos_ate_conferir_canais

        self._trava = threading.RLock()
        self._estado = Estado.PARADO
        self._pasta: Path | None = None
        self._titulo: str | None = None
        self._nota: Path | None = None
        self._erro: str | None = None
        self._aviso: str | None = None
        self._trabalho: threading.Thread | None = None
        self._fim_da_gravacao = threading.Event()

    # -- leitura ------------------------------------------------------------

    @property
    def configuracao(self) -> Configuracao:
        """A configuração viva do coletor — a bandeja usa para abrir pastas."""
        return self._configuracao

    def observar(self, ao_mudar: Callable[[Situacao], None] | None) -> None:
        """Registra quem repinta a interface a cada transição.

        Existe como método porque a interface só nasce depois do coletor: a
        bandeja precisa do coletor para se construir, e o coletor precisa da
        bandeja para se anunciar.
        """
        with self._trava:
            self._ao_mudar = ao_mudar

    def situacao(self) -> Situacao:
        """O retrato atual — o que a bandeja desenha."""
        with self._trava:
            return Situacao(
                estado=self._estado,
                pasta=self._pasta,
                titulo=self._titulo,
                nota=self._nota,
                erro=self._erro,
                aviso=self._aviso,
            )

    @property
    def estado(self) -> Estado:
        with self._trava:
            return self._estado

    # -- comandos -----------------------------------------------------------

    def iniciar(self, titulo: str | None = None) -> Path:
        """Começa a gravar. Devolve a pasta da gravação.

        Começar uma reunião limpa o erro da anterior da tela — a gravação que
        falhou continua retida no disco, e é o `reprocessar` que a completa.
        """
        with self._trava:
            if self._estado is Estado.GRAVANDO:
                raise ErroDoColetor("já existe uma gravação em andamento")
            gravador = self._garantir_gravador()
            pasta = gravador.iniciar(titulo)
            self._pasta = Path(pasta)
            self._titulo = titulo
            self._erro = None
            self._aviso = None
            self._fim_da_gravacao.clear()
            self._mudar(Estado.GRAVANDO)
            _log.info("Gravando em %s", pasta)
        self._vigiar_canais()
        return Path(pasta)

    def parar(self) -> Path:
        """Para a gravação e dispara o processamento. Devolve a pasta gravada.

        Retorna assim que o áudio está salvo: transcrever e resumir acontece
        depois, sem prender a interface. Quem precisa do fim — o teste, o
        fechamento do programa — chama `aguardar()`.
        """
        with self._trava:
            if self._estado is not Estado.GRAVANDO:
                raise ErroDoColetor("não há gravação em andamento")
            gravador = self._garantir_gravador()
            pasta = Path(gravador.parar())
            self._fim_da_gravacao.set()
            self._pasta = pasta
            self._aviso = None
            self._mudar(Estado.PROCESSANDO)
            _log.info("Gravação encerrada em %s — processando.", pasta)

        if self._em_segundo_plano:
            trabalho = threading.Thread(
                target=self._processar,
                args=(pasta,),
                name="second-brain-processamento",
                daemon=True,
            )
            with self._trava:
                self._trabalho = trabalho
            trabalho.start()
        else:
            self._processar(pasta)
        return pasta

    def alternar(self, titulo: str | None = None) -> None:
        """O clique único da bandeja: grava se estiver parado, para se estiver gravando."""
        if self.estado is Estado.GRAVANDO:
            self.parar()
        else:
            self.iniciar(titulo)

    def reconhecer_erro(self) -> None:
        """Tira o erro da tela sem apagar nada do disco."""
        with self._trava:
            if self._estado is Estado.ERRO:
                self._erro = None
                self._mudar(Estado.PARADO)

    def aguardar(self, timeout: float | None = None) -> bool:
        """Espera o processamento em andamento terminar. `True` se terminou."""
        with self._trava:
            trabalho = self._trabalho
        if trabalho is None:
            return True
        trabalho.join(timeout)
        return not trabalho.is_alive()

    def encerrar(self) -> None:
        """Fecha o coletor com o mínimo de dano: para a gravação, se houver.

        Chamado quando o usuário sai pela bandeja. Uma reunião interrompida
        pela saída ainda vira nota — é justamente o caso em que perder a
        gravação seria pior.
        """
        if self.estado is Estado.GRAVANDO:
            try:
                self.parar()
            except Exception as erro:  # noqa: BLE001 — sair nunca pode explodir
                _log.error("Falha ao encerrar a gravação: %s", erro)
        self.aguardar()

    # -- canais mudos -------------------------------------------------------

    def conferir_canais(self) -> str | None:
        """Algum canal está gravando silêncio digital? Devolve o aviso, ou `None`.

        O modo de falha real do usuário: com fone, o loopback capturado pode
        não ser a saída por onde o Meet está tocando, e a reunião inteira sai
        só com a voz dele. O gravador já avisa no log — mas quem está numa
        reunião não está lendo log, está olhando para a bandeja.
        """
        gravador = self._gravador
        niveis = getattr(gravador, "niveis", None)
        if niveis is None:
            return None
        mudos = [canal for canal, rms in niveis().items() if rms < LIMIAR_RMS_MUDO]
        if not mudos:
            return None
        if "sistema" in mudos and "microfone" in mudos:
            return "nenhum áudio está entrando — confira microfone e saída de som"
        if "sistema" in mudos:
            return "só a sua voz está entrando; a dos outros, não"
        return "seu microfone não está entrando"

    def _vigiar_canais(self) -> None:
        """Confere os níveis um pouco depois do início, sem prender ninguém."""
        if not self._em_segundo_plano:
            return

        def vigia() -> None:
            if self._fim_da_gravacao.wait(self._espera_do_aviso):
                return  # a reunião acabou antes da conferência
            with self._trava:
                if self._estado is not Estado.GRAVANDO:
                    return
                aviso = self.conferir_canais()
                if aviso is None or aviso == self._aviso:
                    return
                self._aviso = aviso
                _log.warning("Durante a gravação: %s", aviso)
                self._mudar(Estado.GRAVANDO)

        threading.Thread(target=vigia, name="second-brain-canais", daemon=True).start()

    # -- bastidores ---------------------------------------------------------

    def _processar(self, pasta: Path) -> None:
        """Roda a costura única. Nenhuma regra de pipeline mora aqui."""
        try:
            stt, resumo = self._portas()
            resultado = _pipeline.processar(
                pasta, configuracao=self._configuracao, stt=stt, resumo=resumo
            )
        except Exception as erro:  # noqa: BLE001 — a bandeja não pode engolir falha
            _log.error("Processamento de %s falhou: %s", Path(pasta).name, erro)
            _log.info(
                "A gravação continua em %s — complete depois com "
                "'python -m second_brain reprocessar'.",
                pasta,
            )
            with self._trava:
                self._erro = str(erro) or erro.__class__.__name__
                self._mudar(Estado.ERRO)
            return
        with self._trava:
            self._nota = Path(resultado.nota)
            self._erro = None
            self._mudar(Estado.PARADO)
        _log.info("Reunião no vault: %s", resultado.nota)

    def _garantir_gravador(self):
        """Cria o gravador na primeira vez — e só então toca no áudio da máquina.

        Adiar isto até o primeiro clique é o que permite a bandeja subir numa
        máquina com o áudio mal configurado e ainda assim mostrar o erro em vez
        de morrer na inicialização.
        """
        if self._gravador is None:
            self._gravador = _gravador.Gravador(
                _gravador.de_configuracao(self._configuracao)
            )
        return self._gravador

    def _mudar(self, estado: Estado) -> None:
        self._estado = estado
        situacao = Situacao(
            estado=estado,
            pasta=self._pasta,
            titulo=self._titulo,
            nota=self._nota,
            erro=self._erro,
            aviso=self._aviso,
        )
        if self._ao_mudar is None:
            return
        try:
            self._ao_mudar(situacao)
        except Exception as erro:  # noqa: BLE001 — UI quebrada não derruba reunião
            _log.error("Falha ao atualizar a interface: %s", erro)


class ErroDoColetor(RuntimeError):
    """Gesto impossível no estado atual (parar sem gravar, gravar duas vezes)."""
