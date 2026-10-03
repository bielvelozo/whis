"""A caçada: lê as fontes, monta o perfil, faz a triagem e deixa tudo mastigado no vault.

`cacar` é a costura da entrega 1 de `.scratch/vagas-e-freelas/`. Corre por
horas, chamada à mão na véspera da virada semanal do plano, e **não envia nada
a ninguém**: o que sai é o relatório `cacada/<corrida>.md` e, para cada chance
boa, um pacote `cacada/<corrida>/<slug>.md` com a proposta pronta e, no freela
web, a amostra. Ele lê, ajusta e envia.

As etapas, na ordem que gasta menos se a corrida parar no meio (research 07):

1. **perfil** — evidências da máquina (`evidencias`) e *Sobre mim* → o perfil;
2. **coleta** — as fontes em Python (`fontes_da_cacada`) e o explorador na web;
3. **triagem** — tudo, em lotes, sem ferramenta;
4. **preparo** — as chances boas, da melhor para a pior;
5. **apostas** — a mensagem curta de cada tentar a sorte.

Cada etapa grava o que produziu no checkpoint (`corrida.Checkpoint`), e o
relatório é reescrito ao fim de cada uma — se a corrida parar, o que já
existe está no vault, e a próxima chamada retoma de onde parou.

O plano manda no ritmo: a janela de 5 h que bate **pausa** a corrida até ela
abrir (com o PC acordado); a semanal no teto (100%, o padrão), ou a menos de 5 min de
virar, **encerra** — a semana nova é a do trabalho dele.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import httpx

from . import vault as _vault
from .cacada_claude import ErroDaCacada, LimiteDoPlano, Plano
from .configuracao import Configuracao
from .corrida import Checkpoint, escrever_andamento
from .criterios_da_cacada import CAMINHO_DOS_CRITERIOS, PASTA_CACADA, Criterios, FonteDaCacada, ler_criterios
from .oportunidades import (
    CHANCE_BOA,
    DESCARTADA,
    FREELA,
    TENTAR_A_SORTE,
    Aposta,
    Oportunidade,
    Pacote,
    Perfil,
    Veredito,
    link_canonico,
)

_log = logging.getLogger("whis.cacada")

CAMINHO_DO_PERFIL = f"{PASTA_CACADA}/perfil.md"
ZONAS_DA_CACADA = (PASTA_CACADA,)

LOTE_DA_TRIAGEM = 20
LOTE_DAS_APOSTAS = 8
MAXIMO_DE_APOSTAS = 60
#: Fora da véspera (a semana vira em mais de 36 h), a corrida para mais cedo: a cota é do trabalho.
TETO_FORA_DA_VESPERA = 70
VESPERA = timedelta(hours=36)
MARGEM_DA_VIRADA = timedelta(minutes=5)
MAXIMO_DA_PAUSA = timedelta(hours=5, minutes=15)
PAUSA_SEM_HORA = timedelta(minutes=30)
FOLGA_DEPOIS_DA_VIRADA = timedelta(minutes=2)
PAUSAS_POR_CHAMADA = 3
IDADE_MAXIMA_DA_RETOMADA = timedelta(days=4)


class Parada(RuntimeError):
    """A corrida encerra antes do fim, com o que já tem: o motivo vai para o relatório."""


class PortaPerfil(Protocol):
    ultimo_plano: Plano | None
    custo_usd: float

    def montar(self, evidencias: str, procuro: str, sobre_mim: str) -> Perfil: ...


class PortaExplorador(Protocol):
    ultimo_plano: Plano | None
    custo_usd: float

    def explorar(
        self, pedido: str, perfil: Perfil, procuro: str, sobre_mim: str, ja_vistas: Sequence[str], nome: str
    ) -> tuple[Oportunidade, ...]: ...


class PortaTriagem(Protocol):
    ultimo_plano: Plano | None
    custo_usd: float

    def triar(self, oportunidades: Sequence[Oportunidade], perfil: Perfil, procuro: str, sobre_mim: str) -> tuple[Veredito, ...]: ...


class PortaApostas(Protocol):
    ultimo_plano: Plano | None
    custo_usd: float

    def escrever(
        self, oportunidades: Sequence[tuple[Oportunidade, Veredito]], perfil: Perfil, procuro: str, sobre_mim: str
    ) -> tuple[Aposta, ...]: ...


class PortaPreparo(Protocol):
    ultimo_plano: Plano | None
    custo_usd: float

    def preparar(
        self, oportunidade: Oportunidade, veredito: Veredito, pagina: str, perfil: Perfil, procuro: str, sobre_mim: str
    ) -> Pacote: ...


@dataclass
class PortasDaCacada:
    """Os cinco adaptadores do Claude e, para os testes, a rede, a coleta e as amostras."""

    perfil: PortaPerfil
    explorador: PortaExplorador
    triagem: PortaTriagem
    apostas: PortaApostas
    preparo: PortaPreparo
    rede: httpx.BaseTransport | None = None
    coletar: Callable[..., Any] | None = None
    ler_detalhe: Callable[[Oportunidade], str] | None = None
    evidencias: Callable[[Configuracao], str] | None = None
    amostras: bool = True
    navegador: Any | None = None
    registro: Any | None = None
    ler_caixa: Callable[[], Sequence[Any]] | None = None

    def todas(self) -> tuple[Any, ...]:
        portas = (self.perfil, self.explorador, self.triagem, self.apostas, self.preparo)
        return portas + ((self.navegador,) if self.navegador is not None else ())


@dataclass
class ResultadoDaCacada:
    """O que a corrida deixou: o relatório, as contagens e, quando parou, o porquê."""

    relatorio: str
    corrida: str
    chances_boas: int = 0
    tentar_a_sorte: int = 0
    descartadas: int = 0
    pacotes: int = 0
    fontes_com_falha: dict[str, str] = field(default_factory=dict)
    parada: str = ""
    perguntas: tuple[str, ...] = ()
    custo_usd: float = 0.0
    duracao_s: float = 0.0
    plano_antes: int | None = None
    plano_depois: int | None = None
    enviadas: int = 0
    precisam_de_voce: int = 0

    @property
    def completa(self) -> bool:
        return not self.parada


# -- a guarda do plano --------------------------------------------------------------------------


class GuardaDoPlano:
    """Lê o plano depois de cada chamada e decide: segue, pausa ou para."""

    def __init__(
        self,
        teto_semanal: int,
        *,
        relogio: Callable[[], datetime],
        dormir: Callable[[float], None],
        ao_pausar: Callable[[str], None] | None = None,
    ) -> None:
        self.teto_semanal = teto_semanal
        self._relogio = relogio
        self._dormir = dormir
        self._ao_pausar = ao_pausar
        self.plano: Plano | None = None
        self.primeiro: Plano | None = None
        self.pausas: list[str] = []

    def ler(self, porta: Any) -> None:
        plano = getattr(porta, "ultimo_plano", None)
        if plano is not None:
            self.plano = plano
            self.primeiro = self.primeiro or plano

    def teto(self) -> int:
        vira = self.plano.vira_sete_dias if self.plano else None
        if vira is not None and vira - self._relogio() > VESPERA:
            return min(self.teto_semanal, TETO_FORA_DA_VESPERA)
        return self.teto_semanal

    def conferir(self) -> None:
        """Levanta `Parada` quando a semana passou do teto ou está para virar."""
        if self.plano is None:
            return
        semanal = self.plano.sete_dias
        if semanal is not None and semanal >= self.teto():
            raise Parada(f"o plano semanal chegou a {semanal}% (o teto desta corrida é {self.teto()}%)")
        vira = self.plano.vira_sete_dias
        if vira is not None and vira - self._relogio() < MARGEM_DA_VIRADA:
            raise Parada("a semana do plano está para virar: daqui em diante a cota é a do trabalho")

    def chamar(self, porta: Any, funcao: Callable[[], Any]) -> Any:
        """Chama o Claude com paciência: espera a janela de 5 h abrir; para na semanal."""
        for tentativa in range(PAUSAS_POR_CHAMADA + 1):
            self.conferir()
            try:
                resultado = funcao()
            except LimiteDoPlano as limite:
                self.ler(porta)
                if limite.semanal:
                    raise Parada("o limite semanal do plano bateu") from limite
                if tentativa >= PAUSAS_POR_CHAMADA:
                    raise Parada("a janela de 5 h bateu de novo depois de três pausas") from limite
                self._pausar(limite)
                continue
            self.ler(porta)
            self.conferir()
            return resultado
        raise Parada("a janela de 5 h não abriu")

    def _pausar(self, limite: LimiteDoPlano) -> None:
        agora = self._relogio()
        alvo = (limite.retoma_em + FOLGA_DEPOIS_DA_VIRADA) if limite.retoma_em else agora + PAUSA_SEM_HORA
        espera = min(max(alvo - agora, timedelta(minutes=1)), MAXIMO_DA_PAUSA)
        retoma = (agora + espera).astimezone()
        aviso = f"pausada até {retoma:%H:%M} (a janela de 5 h do plano bateu)"
        self.pausas.append(aviso)
        _log.warning("Caçada %s.", aviso)
        if self._ao_pausar is not None:
            self._ao_pausar(aviso)
        self._dormir(espera.total_seconds())


# -- a corrida -------------------------------------------------------------------------------------


def cacar(
    configuracao: Configuracao,
    portas: PortasDaCacada,
    *,
    pasta_do_estado: Path,
    do_zero: bool = False,
    relogio: Callable[[], datetime] | None = None,
    dormir: Callable[[float], None] = time.sleep,
    ao_pausar: Callable[[str], None] | None = None,
) -> ResultadoDaCacada:
    """A corrida inteira, retomando do checkpoint quando há um inacabado e recente."""
    agora = relogio or (lambda: datetime.now().astimezone())
    inicio_monotonico = time.monotonic()
    raiz = _vault.preparar(configuracao.vault)
    criterios = ler_criterios(raiz)

    checkpoint = Checkpoint.abrir(pasta_do_estado, do_zero=do_zero)
    if checkpoint.retomada and _velho(checkpoint.get("inicio"), agora()):
        _log.info("O checkpoint da caçada tem mais de %d dias: começando do zero.", IDADE_MAXIMA_DA_RETOMADA.days)
        checkpoint = Checkpoint.abrir(pasta_do_estado, do_zero=True)
    if not checkpoint.retomada:
        momento = agora()
        checkpoint.guardar(inicio=momento.isoformat(timespec="seconds"), corrida=f"{momento:%Y-%m-%d-%H%M}", etapa="perfil")

    estado = _Estado(configuracao, raiz, criterios, checkpoint, pasta_do_estado)
    guarda = GuardaDoPlano(configuracao.cacada_teto_semanal, relogio=agora, dormir=dormir, ao_pausar=ao_pausar)
    parada = ""
    try:
        _etapa_do_perfil(estado, portas, guarda)
        _etapa_da_coleta(estado, portas, guarda, agora())
        _etapa_da_triagem(estado, portas, guarda)
        _escrever_relatorio(estado, guarda, parada="", em_andamento="preparando os pacotes")
        _etapa_do_preparo(estado, portas, guarda)
        _escrever_relatorio(estado, guarda, parada="", em_andamento="escrevendo as mensagens de tentar a sorte")
        _etapa_das_apostas(estado, portas, guarda)
        _etapa_do_envio(estado, portas, guarda)
        _etapa_da_caixa(estado, portas)
    except Parada as motivo:
        parada = str(motivo)
        _log.warning("A caçada parou antes do fim: %s.", parada)

    if not parada:
        checkpoint.guardar(etapa="terminada")
        checkpoint.terminar()
    escrever_andamento(pasta_do_estado, "terminada" if not parada else "parada", parada)
    caminho = _escrever_relatorio(estado, guarda, parada=parada)
    custo = sum(float(getattr(porta, "custo_usd", 0.0) or 0.0) for porta in portas.todas())
    vereditos = estado.vereditos()
    return ResultadoDaCacada(
        relatorio=caminho,
        corrida=estado.corrida,
        chances_boas=sum(1 for v in vereditos.values() if v.classe == CHANCE_BOA),
        tentar_a_sorte=sum(1 for v in vereditos.values() if v.classe == TENTAR_A_SORTE),
        descartadas=sum(1 for v in vereditos.values() if v.classe == DESCARTADA),
        pacotes=len(estado.pacotes()),
        fontes_com_falha=dict(checkpoint.get("falhas") or {}),
        parada=parada,
        perguntas=estado.perguntas(),
        custo_usd=custo,
        duracao_s=round(time.monotonic() - inicio_monotonico, 1),
        enviadas=sum(1 for e in (checkpoint.get("envios") or {}).values() if e.get("status") == "feito"),
        precisam_de_voce=sum(1 for e in (checkpoint.get("envios") or {}).values() if e.get("status") == "precisa_de_voce"),
        plano_antes=guarda.primeiro.sete_dias if guarda.primeiro else None,
        plano_depois=guarda.plano.sete_dias if guarda.plano else None,
    )


class _Estado:
    """O checkpoint com cara de dados da caçada."""

    def __init__(self, configuracao: Configuracao, raiz: Path, criterios: Criterios, checkpoint: Checkpoint, pasta: Path) -> None:
        self.configuracao = configuracao
        self.raiz = raiz
        self.criterios = criterios
        self.checkpoint = checkpoint
        self.pasta = pasta

    @property
    def corrida(self) -> str:
        return str(self.checkpoint.get("corrida"))

    def andamento(self, etapa: str, detalhe: str = "") -> None:
        self.checkpoint.guardar(etapa=etapa)
        escrever_andamento(self.pasta, etapa, detalhe)

    def perfil(self) -> Perfil | None:
        dados = self.checkpoint.get("perfil")
        return Perfil.de_json(dados) if isinstance(dados, dict) else None

    def oportunidades(self) -> dict[str, Oportunidade]:
        return {o["id"]: Oportunidade.de_json(o) for o in self.checkpoint.get("oportunidades") or []}

    def vereditos(self) -> dict[str, Veredito]:
        return {v["id"]: Veredito.de_json(v) for v in self.checkpoint.get("vereditos") or []}

    def pacotes(self) -> dict[str, dict[str, Any]]:
        return dict(self.checkpoint.get("pacotes") or {})

    def apostas(self) -> dict[str, Aposta]:
        return {chave: Aposta.de_json(valor) for chave, valor in (self.checkpoint.get("apostas") or {}).items()}

    def perguntas(self) -> tuple[str, ...]:
        """O que o perfil não conseguiu saber e só ele responde."""
        perfil = self.perfil()
        return tuple(perfil.perguntas) if perfil else ()

    def escrever(self, relativo: str, conteudo: str) -> Path:
        if relativo == CAMINHO_DOS_CRITERIOS:
            raise _vault.ForaDaZonaDePropriedade("cacada/criterios.md é dele: a caçada nunca escreve nela")
        return _vault.escrever(self.raiz, relativo, conteudo, zonas=ZONAS_DA_CACADA)


# -- as etapas --------------------------------------------------------------------------------------


def _etapa_do_perfil(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano) -> None:
    if estado.perfil() is not None:
        return
    estado.andamento("perfil", "lendo o git e o vault")
    from .evidencias import montar_evidencias

    evidencias = (portas.evidencias or montar_evidencias)(estado.configuracao)
    criterios = estado.criterios
    try:
        perfil = guarda.chamar(portas.perfil, lambda: portas.perfil.montar(evidencias, criterios.procuro, criterios.sobre_mim))
    except ErroDaCacada as erro:
        _log.warning("O perfil não saiu (%s): a caçada segue com Sobre mim.", erro)
        perfil = Perfil(resumo=f"(o perfil automático não saiu: {erro}) Ver Sobre mim.")
    estado.checkpoint.guardar(perfil=perfil.para_json())
    estado.escrever(CAMINHO_DO_PERFIL, montar_nota_do_perfil(perfil, estado.corrida))


def _etapa_da_coleta(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano, agora: datetime) -> None:
    if estado.checkpoint.get("coletada"):
        return
    from .fontes_da_cacada import coletar

    criterios = estado.criterios
    ja_vistas = links_ja_vistos(estado.raiz, excluir=estado.corrida)
    estado.andamento("coleta", "lendo as fontes")
    coleta = (portas.coletar or coletar)(
        criterios.fontes, agora, rede=portas.rede, ao_ler=lambda nome: escrever_andamento(estado.pasta, "coleta", nome)
    )
    lidas: dict[str, int] = {nome: len(lista) for nome, lista in coleta.por_fonte.items()}
    falhas: dict[str, str] = dict(coleta.falhas)
    todas: dict[str, Oportunidade] = {o.id: o for o in coleta.todas()}

    perfil = estado.perfil() or Perfil(resumo="")
    for fonte in (f for f in criterios.fontes if f.tipo == "web"):
        estado.andamento("coleta", f"explorando a web: {fonte.nome}")
        vistas_agora = sorted(ja_vistas | {o.link for o in todas.values()})
        try:
            achadas = guarda.chamar(
                portas.explorador,
                lambda fonte=fonte: portas.explorador.explorar(
                    fonte.argumento, perfil, criterios.procuro, criterios.sobre_mim, vistas_agora, fonte.nome
                ),
            )
        except ErroDaCacada as erro:
            falhas[fonte.nome] = str(erro)[:200]
            continue
        lidas[fonte.nome] = len(achadas)
        for oportunidade in achadas:
            todas.setdefault(oportunidade.id, oportunidade)

    novas = [o for o in todas.values() if o.link not in ja_vistas]
    _log.info("Caçada: %d oportunidade(s) coletada(s), %d nova(s).", len(todas), len(novas))
    estado.checkpoint.guardar(
        oportunidades=[o.para_json() for o in novas],
        lidas=lidas,
        falhas=falhas,
        repetidas=len(todas) - len(novas),
        coletada=True,
    )


def _etapa_da_triagem(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano) -> None:
    oportunidades = estado.oportunidades()
    perfil = estado.perfil() or Perfil(resumo="")
    criterios = estado.criterios
    tentativas: dict[str, int] = dict(estado.checkpoint.get("tentativas_da_triagem") or {})
    while True:
        vereditos = estado.vereditos()
        pendentes = [o for i, o in oportunidades.items() if i not in vereditos]
        if not pendentes:
            return
        lote = pendentes[:LOTE_DA_TRIAGEM]
        estado.andamento("triagem", f"{len(vereditos)} de {len(oportunidades)} triadas")
        try:
            novos = guarda.chamar(portas.triagem, lambda: portas.triagem.triar(lote, perfil, criterios.procuro, criterios.sobre_mim))
        except ErroDaCacada as erro:
            _log.warning("Um lote da triagem falhou: %s", erro)
            novos = ()
        recebidos = {v.id for v in novos}
        sem_resposta = []
        for oportunidade in lote:
            if oportunidade.id in recebidos:
                continue
            tentativas[oportunidade.id] = tentativas.get(oportunidade.id, 0) + 1
            if tentativas[oportunidade.id] >= 2:
                sem_resposta.append(
                    Veredito(oportunidade.id, DESCARTADA, "a triagem não respondeu sobre ela (abra o link se quiser ver)")
                )
        lista = [v.para_json() for v in (*estado.vereditos().values(), *novos, *sem_resposta)]
        estado.checkpoint.guardar(vereditos=lista, tentativas_da_triagem=tentativas)


def _etapa_do_preparo(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano) -> None:
    oportunidades = estado.oportunidades()
    vereditos = estado.vereditos()
    perfil = estado.perfil() or Perfil(resumo="")
    criterios = estado.criterios
    chances = _ordenadas(oportunidades, vereditos, CHANCE_BOA)[: estado.configuracao.cacada_maximo_de_pacotes]
    from .fontes_da_cacada import ler_detalhe

    for numero, (oportunidade, veredito) in enumerate(chances, 1):
        pacotes = estado.pacotes()
        if oportunidade.id in pacotes:
            continue
        estado.andamento("preparo", f"{numero} de {len(chances)}: {oportunidade.titulo[:60]}")
        pagina = (portas.ler_detalhe or (lambda o: ler_detalhe(o, rede=portas.rede)))(oportunidade)
        try:
            pacote = guarda.chamar(
                portas.preparo,
                lambda: portas.preparo.preparar(oportunidade, veredito, pagina, perfil, criterios.procuro, criterios.sobre_mim),
            )
        except ErroDaCacada as erro:
            _log.warning("O pacote de %s não saiu: %s", oportunidade.link, erro)
            pacotes[oportunidade.id] = {"falha": str(erro)[:300]}
            estado.checkpoint.guardar(pacotes=pacotes)
            continue
        caminho = caminho_do_pacote(estado.corrida, oportunidade)
        amostra = _amostra(estado, portas, oportunidade, pacote, caminho) if pacote.amostra_html else {}
        estado.escrever(caminho, montar_pacote(oportunidade, veredito, pacote, amostra))
        pacotes[oportunidade.id] = {"caminho": caminho, **amostra, "pacote": {**pacote.para_json(), "amostra_html": ""}}
        estado.checkpoint.guardar(pacotes=pacotes)


def _amostra(
    estado: _Estado, portas: PortasDaCacada, oportunidade: Oportunidade, pacote: Pacote, caminho: str
) -> dict[str, str]:
    from . import amostras

    pasta = f"{caminho.removesuffix('.md')}-amostra"
    arquivo = amostras.gravar(estado.raiz, pasta, pacote.amostra_html)
    info = {"amostra": f"{pasta}/index.html"}
    if not portas.amostras:
        return info
    if amostras.tirar_print(arquivo) is not None:
        info["print"] = f"{pasta}/amostra.png"
    publicada = amostras.publicar(estado.configuracao, arquivo, Path(pasta).name)
    if isinstance(publicada, str):
        info["sem_link"] = publicada
    elif publicada.url:
        info["url"] = publicada.url
    return info


def _etapa_das_apostas(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano) -> None:
    oportunidades = estado.oportunidades()
    vereditos = estado.vereditos()
    perfil = estado.perfil() or Perfil(resumo="")
    criterios = estado.criterios
    alvo = _ordenadas(oportunidades, vereditos, TENTAR_A_SORTE)[:MAXIMO_DE_APOSTAS]
    tentadas: set[str] = set(estado.checkpoint.get("apostas_tentadas") or [])
    while True:
        feitas = estado.apostas()
        pendentes = [(o, v) for o, v in alvo if o.id not in feitas and o.id not in tentadas]
        if not pendentes:
            return
        lote = pendentes[:LOTE_DAS_APOSTAS]
        estado.andamento("apostas", f"{len(feitas)} de {len(alvo)} mensagens prontas")
        try:
            novas = guarda.chamar(portas.apostas, lambda: portas.apostas.escrever(lote, perfil, criterios.procuro, criterios.sobre_mim))
        except ErroDaCacada as erro:
            _log.warning("Um lote de mensagens de tentar a sorte falhou: %s", erro)
            novas = ()
        tentadas |= {o.id for o, _ in lote}
        todas = {**{k: v.para_json() for k, v in feitas.items()}, **{a.id: a.para_json() for a in novas}}
        estado.checkpoint.guardar(apostas=todas, apostas_tentadas=sorted(tentadas))


def _etapa_do_envio(estado: _Estado, portas: PortasDaCacada, guarda: GuardaDoPlano) -> None:
    """Entrega 2: as de tentar a sorte que a política deixa, uma por uma, com o registro antes e depois.

    Quem decide se pode é `politica.pode_enviar_sozinho`, em código. Desligado
    (`[cacada].enviar_sozinho = false`, o padrão), esta etapa não faz nada.
    """
    configuracao = estado.configuracao
    if not configuracao.cacada_enviar_sozinho or portas.navegador is None or portas.registro is None:
        return
    from .acoes import CANDIDATURA, FALHOU
    from .contas import dados_dele
    from .politica import pode_enviar_sozinho

    dados = dados_dele(configuracao, estado.criterios)
    oportunidades = estado.oportunidades()
    vereditos = estado.vereditos()
    apostas = estado.apostas()
    envios: dict[str, dict[str, str]] = dict(estado.checkpoint.get("envios") or {})
    feitos = sum(1 for e in envios.values() if e.get("status") == "feito")
    for oportunidade, veredito in _ordenadas(oportunidades, vereditos, TENTAR_A_SORTE):
        if feitos >= configuracao.cacada_maximo_de_envios:
            break
        if oportunidade.id in envios or oportunidade.id not in apostas:
            continue
        pode, motivo = pode_enviar_sozinho(oportunidade, veredito, portas.registro, ligado=True)
        if not pode:
            continue
        estado.andamento("envio", f"candidatando: {oportunidade.titulo[:60]}")
        mensagem = apostas[oportunidade.id].mensagem
        id_ = portas.registro.intencao(CANDIDATURA, oportunidade.link, texto=mensagem, detalhe=oportunidade.titulo)
        try:
            desfecho = guarda.chamar(
                portas.navegador, lambda: portas.navegador.candidatar(oportunidade.link, oportunidade.titulo, mensagem, dados)
            )
        except ErroDaCacada as erro:
            portas.registro.concluir(id_, FALHOU, str(erro)[:200])
            envios[oportunidade.id] = {"status": "falhou", "motivo": str(erro)[:200]}
            estado.checkpoint.guardar(envios=envios)
            continue
        except Parada:
            portas.registro.concluir(id_, FALHOU, "a caçada parou no meio da candidatura: confira no site")
            raise
        status = desfecho.status if desfecho.status in ("feito", "precisa_de_voce") else "falhou"
        portas.registro.concluir(id_, status, desfecho.motivo)
        envios[oportunidade.id] = {"status": status, "motivo": desfecho.motivo, "falta": desfecho.o_que_falta}
        feitos += status == "feito"
        estado.checkpoint.guardar(envios=envios)


def _etapa_da_caixa(estado: _Estado, portas: PortasDaCacada) -> None:
    """O que chegou no Gmail dedicado: só a lista, para ele ler. Nada é respondido."""
    if portas.ler_caixa is None or estado.checkpoint.get("caixa") is not None:
        return
    estado.andamento("caixa", "lendo o Gmail dedicado")
    try:
        mensagens = portas.ler_caixa()
    except Exception as erro:  # noqa: BLE001 — a caixa não derruba a caçada
        estado.checkpoint.guardar(caixa={"falha": str(erro)[:200]})
        return
    lista = [
        {"remetente": m.remetente, "assunto": m.assunto, "quando": m.quando}
        for m in sorted(mensagens, key=lambda m: m.quando, reverse=True)[:40]
    ]
    estado.checkpoint.guardar(caixa={"mensagens": lista})


def _ordenadas(
    oportunidades: dict[str, Oportunidade], vereditos: dict[str, Veredito], classe: str
) -> list[tuple[Oportunidade, Veredito]]:
    pares = [(oportunidades[i], v) for i, v in vereditos.items() if v.classe == classe and i in oportunidades]
    return sorted(pares, key=lambda par: par[1].encaixe, reverse=True)


# -- o que já foi visto ---------------------------------------------------------------------------

_LINK_MD = re.compile(r"\]\((https?://[^)\s]+)\)")
#: Oportunidade de corrida abandonada que nem foi triada não conta como vista.
MARCA_SEM_TRIAGEM = "ainda sem triagem"


def links_ja_vistos(vault: Path, *, excluir: str = "") -> set[str]:
    """Os links que já apareceram em caçadas anteriores — relatórios e pacotes —, canônicos."""
    pasta = Path(vault) / PASTA_CACADA
    vistos: set[str] = set()
    if not pasta.is_dir():
        return vistos
    for arquivo in pasta.rglob("*.md"):
        relativo = arquivo.relative_to(vault).as_posix()
        if relativo in (CAMINHO_DOS_CRITERIOS, CAMINHO_DO_PERFIL) or (excluir and excluir in relativo):
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            if MARCA_SEM_TRIAGEM in linha:
                continue
            vistos.update(link_canonico(link) for link in _LINK_MD.findall(linha))
    return vistos


# -- as notas -----------------------------------------------------------------------------------------


def caminho_do_relatorio(corrida: str) -> str:
    return f"{PASTA_CACADA}/{corrida}.md"


def caminho_do_pacote(corrida: str, oportunidade: Oportunidade) -> str:
    return f"{PASTA_CACADA}/{corrida}/{_vault._slug(oportunidade.titulo, 'oportunidade')[:50]}-{oportunidade.id[:6]}.md"


def montar_nota_do_perfil(perfil: Perfil, corrida: str) -> str:
    linhas = [
        "---",
        "tipo: perfil-da-cacada",
        f'corrida: "{corrida}"',
        "---",
        "",
        "# O perfil que a caçada usa",
        "",
        "Montado pelo Whis a cada caçada, a partir do git, do vault e de *Sobre mim* em [[cacada/criterios]]. "
        "Para corrigir, escreva em *Sobre mim*: esta nota é regenerada.",
        "",
        perfil.resumo.strip() or "_(vazio)_",
        "",
        f"**Stack:** {', '.join(perfil.stack) or '—'}",
        "",
        f"**Senioridade estimada:** {perfil.senioridade or '—'}",
        "",
    ]
    if perfil.perguntas:
        linhas += ["## O que falta você dizer", "", *(f"- {p}" for p in perfil.perguntas), ""]
    return "\n".join(linhas)


def montar_pacote(oportunidade: Oportunidade, veredito: Veredito, pacote: Pacote, amostra: dict[str, str]) -> str:
    def lista(itens: Sequence[str], vazio: str = "_(nenhum)_") -> list[str]:
        return [f"- {item}" for item in itens] if itens else [vazio]

    cabecalho = " · ".join(
        parte
        for parte in (
            "Freela" if oportunidade.tipo == FREELA else "Vaga",
            oportunidade.fonte,
            oportunidade.local,
            oportunidade.regime,
            oportunidade.faixa,
            f"publicada {oportunidade.publicada[:10]}" if oportunidade.publicada else "",
            f"encaixe {veredito.encaixe}",
        )
        if parte
    )
    empresa = f" — {oportunidade.empresa}" if oportunidade.empresa else ""
    linhas = [
        "---",
        "tipo: pacote",
        f'link: "{oportunidade.link}"',
        f"encaixe: {veredito.encaixe}",
        "---",
        "",
        f"# {oportunidade.titulo}{empresa}",
        "",
        f"[Abrir a oportunidade]({oportunidade.link}) · {cabecalho}",
        "",
        f"> {veredito.motivo}" if veredito.motivo else "",
        "",
        "## O que pedem",
        "",
        pacote.resumo or "_(sem resumo)_",
        "",
        "## Por que casa",
        "",
        pacote.por_que_casa or "—",
        "",
    ]
    if pacote.o_que_estica:
        linhas += ["## O que estica", "", pacote.o_que_estica, ""]
    linhas += ["## Alertas", "", *lista(pacote.alertas), ""]
    linhas += ["## Preço e prazo", "", f"- **Preço / pretensão:** {pacote.preco or '—'}", f"- **Prazo:** {pacote.prazo or '—'}", ""]
    linhas += ["## Proposta pronta", "", "```text", pacote.proposta.strip() or "(vazia)", "```", ""]
    linhas += ["## Como enviar", "", pacote.como_enviar or "—", ""]
    linhas += ["## Plano de execução", "", *lista(pacote.plano), ""]
    if pacote.perguntas:
        linhas += ["## Perguntas para o cliente", "", *lista(pacote.perguntas), ""]
    if amostra:
        linhas += ["## Amostra", ""]
        if amostra.get("url"):
            linhas.append(f"- Link público (sem seu nome; sai do ar em 30 dias): {amostra['url']}")
        elif amostra.get("sem_link"):
            linhas.append(f"- Sem link público: {amostra['sem_link']}.")
        linhas.append(f"- Arquivo: `{amostra['amostra']}` (abra no navegador)")
        if amostra.get("print"):
            linhas += ["- Print para anexar (é o que vai na Workana, que não aceita link):", "", f"![[{amostra['print']}]]"]
        linhas.append("")
    return "\n".join(linhas)


def _escrever_relatorio(estado: _Estado, guarda: GuardaDoPlano, *, parada: str, em_andamento: str = "") -> str:
    caminho = caminho_do_relatorio(estado.corrida)
    estado.escrever(caminho, montar_relatorio(estado, guarda, parada=parada, em_andamento=em_andamento))
    return caminho


def montar_relatorio(estado: _Estado, guarda: GuardaDoPlano, *, parada: str, em_andamento: str = "") -> str:
    oportunidades = estado.oportunidades()
    vereditos = estado.vereditos()
    pacotes = estado.pacotes()
    apostas = estado.apostas()
    chances = _ordenadas(oportunidades, vereditos, CHANCE_BOA)
    sorte = _ordenadas(oportunidades, vereditos, TENTAR_A_SORTE)
    descartadas = _ordenadas(oportunidades, vereditos, DESCARTADA)
    sem_veredito = [o for i, o in oportunidades.items() if i not in vereditos]
    inicio = _data(estado.checkpoint.get("inicio"))

    titulo = f"# Caçada de {_vault._data_por_extenso(inicio.date())}, {inicio:%H:%M}" if inicio else "# Caçada"
    plano = ""
    if guarda.primeiro and guarda.plano and guarda.primeiro.sete_dias is not None:
        plano = f" · plano semanal {guarda.primeiro.sete_dias}% → {guarda.plano.sete_dias}%"
    linhas = [
        "---",
        "tipo: cacada",
        f"chances_boas: {len(chances)}",
        f"tentar_a_sorte: {len(sorte)}",
        f"descartadas: {len(descartadas)}",
        f"completa: {'false' if parada or em_andamento else 'true'}",
        "---",
        "",
        titulo,
        "",
        f"**{len(chances)} chances boas · {len(sorte)} para tentar a sorte · {len(descartadas)} descartadas**{plano}",
        "",
        _frase_do_envio(estado),
        "",
    ]
    if parada:
        linhas += [
            "> [!warning] A caçada parou antes do fim",
            f"> {parada}. O que está aqui vale; rode `hunt` de novo (na véspera da virada da semana) para continuar de onde parou.",
            "",
        ]
    elif em_andamento:
        linhas += [f"> [!info] A caçada ainda está correndo: {em_andamento}. Esta nota é reescrita ao fim de cada etapa.", ""]
    for pausa in guarda.pausas:
        linhas.append(f"- Ficou {pausa}.")
    if guarda.pausas:
        linhas.append("")

    perguntas = estado.perguntas()
    em_branco = estado.criterios.respostas_em_branco()
    if perguntas or em_branco:
        linhas += ["## Antes de tudo: responda em [[cacada/criterios]]", "", "Escreva em *Sobre mim*; a próxima caçada usa.", ""]
        linhas += [f"- {p}" for p in perguntas]
        if em_branco:
            linhas.append(f"- Ainda em branco em *Sobre mim*: {', '.join(em_branco)}.")
        linhas.append("")

    linhas += ["## Chances boas", ""]
    if not chances:
        linhas += ["_Nenhuma nesta caçada._", ""]
    for numero, (oportunidade, veredito) in enumerate(chances, 1):
        empresa = f" — {oportunidade.empresa}" if oportunidade.empresa else ""
        linhas += [f"### {numero}. {oportunidade.titulo}{empresa}", "", _linha_da_oportunidade(oportunidade, veredito), ""]
        if veredito.motivo:
            linhas += [veredito.motivo, ""]
        pacote = pacotes.get(oportunidade.id) or {}
        if pacote.get("caminho"):
            linhas.append(f"→ **[[{pacote['caminho'].removesuffix('.md')}|Abrir o pacote]]** (proposta pronta, preço, como enviar)")
            if pacote.get("url"):
                linhas.append(f"→ Amostra no ar: {pacote['url']}")
            elif pacote.get("amostra"):
                linhas.append(f"→ Amostra: `{pacote['amostra']}`")
        elif pacote.get("falha"):
            linhas.append(f"→ O pacote não saiu ({pacote['falha'][:120]}). Abra a oportunidade e decida.")
        else:
            linhas.append("→ Sem pacote nesta corrida (teto de pacotes ou a corrida parou antes).")
        linhas.append("")

    linhas += ["## Tentar a sorte", ""]
    if not sorte:
        linhas += ["_Nenhuma nesta caçada._", ""]
    for oportunidade, veredito in sorte:
        empresa = f" — {oportunidade.empresa}" if oportunidade.empresa else ""
        linhas += [f"### {oportunidade.titulo}{empresa}", "", _linha_da_oportunidade(oportunidade, veredito)]
        if veredito.motivo:
            linhas += ["", veredito.motivo]
        envio = (estado.checkpoint.get("envios") or {}).get(oportunidade.id)
        if envio:
            rotulo = {"feito": "**Enviada pelo Whis.**", "precisa_de_voce": "**O Whis começou e precisa de você:**"}.get(
                envio.get("status", ""), "**O Whis tentou enviar e não conseguiu:**"
            )
            linhas += ["", f"{rotulo} {envio.get('falta') or envio.get('motivo', '')}".rstrip()]
        aposta = apostas.get(oportunidade.id)
        if aposta is not None:
            linhas += ["", "> [!quote]- Mensagem pronta (clique para abrir)"]
            linhas += [f"> {linha}" if linha else ">" for linha in aposta.mensagem.strip().splitlines()]
            if aposta.como_enviar:
                linhas += [">", f"> **Como enviar:** {aposta.como_enviar}"]
        linhas.append("")

    linhas += ["## Descartadas", ""]
    if descartadas or sem_veredito:
        linhas.append(f"> [!note]- {len(descartadas) + len(sem_veredito)} descartadas ou sem triagem (clique para ver)")
        for oportunidade, veredito in descartadas:
            linhas.append(f"> - [{_curto(oportunidade.titulo)}]({oportunidade.link}) — {oportunidade.fonte} — {veredito.motivo}")
        for oportunidade in sem_veredito:
            linhas.append(f"> - [{_curto(oportunidade.titulo)}]({oportunidade.link}) — {oportunidade.fonte} — {MARCA_SEM_TRIAGEM}")
    else:
        linhas.append("_Nenhuma._")
    linhas.append("")

    caixa = estado.checkpoint.get("caixa")
    if isinstance(caixa, dict):
        linhas += ["## Caixa do Gmail dedicado", ""]
        if caixa.get("falha"):
            linhas.append(f"_Não deu para ler: {caixa['falha']}_")
        elif caixa.get("mensagens"):
            linhas.append("Só a lista, para você abrir e responder; o Whis não responde ninguém.")
            linhas.append("")
            linhas += [f"- {m['quando'][:16].replace('T', ' ')} — {m['remetente']} — {m['assunto']}" for m in caixa["mensagens"]]
        else:
            linhas.append("_Nada nos últimos 14 dias._")
        linhas.append("")

    linhas += ["## Fontes", ""]
    lidas: dict[str, int] = estado.checkpoint.get("lidas") or {}
    falhas: dict[str, str] = estado.checkpoint.get("falhas") or {}
    for fonte in estado.criterios.fontes:
        if fonte.nome in falhas:
            linhas.append(f"- {fonte.nome}: **não respondeu** — {falhas[fonte.nome]}")
        elif fonte.nome in lidas:
            linhas.append(f"- {fonte.nome}: {lidas[fonte.nome]} lida(s)")
        else:
            linhas.append(f"- {fonte.nome}: não chegou a ser lida")
    repetidas = estado.checkpoint.get("repetidas")
    if repetidas:
        linhas.append(f"- {repetidas} já tinham aparecido em caçadas anteriores e ficaram de fora.")
    for aviso in estado.criterios.avisos:
        linhas.append(f"- Aviso: {aviso}")
    linhas += ["", "O perfil usado está em [[cacada/perfil]]; os critérios, em [[cacada/criterios]].", ""]
    return "\n".join(linha for linha in linhas if linha is not None)


def _frase_do_envio(estado: _Estado) -> str:
    envios = (estado.checkpoint.get("envios") or {}).values()
    feitos = sum(1 for e in envios if e.get("status") == "feito")
    if not feitos:
        return "Nada foi enviado a ninguém: tudo aqui espera você ler, ajustar e mandar."
    return (
        f"O Whis enviou sozinho {feitos} candidatura(s) de tentar a sorte (marcadas abaixo, e no registro de ações); "
        "as chances boas e o resto esperam você."
    )


def _linha_da_oportunidade(oportunidade: Oportunidade, veredito: Veredito) -> str:
    partes = [
        "Freela" if oportunidade.tipo == FREELA else "Vaga",
        oportunidade.fonte,
        oportunidade.local,
        oportunidade.regime,
        oportunidade.faixa or ("faixa desconhecida" if oportunidade.tipo != FREELA else "orçamento não informado"),
        f"encaixe {veredito.encaixe}",
    ]
    return " · ".join(p for p in partes if p) + f" · [Abrir]({oportunidade.link})"


def _curto(texto: str, tamanho: int = 90) -> str:
    texto = texto.replace("[", "(").replace("]", ")")
    return texto if len(texto) <= tamanho else texto[: tamanho - 1] + "…"


def _data(texto: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


def _velho(inicio: object, agora: datetime) -> bool:
    momento = _data(inicio)
    if momento is None:
        return True
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return agora - momento > IDADE_MAXIMA_DA_RETOMADA


def fontes_lidas_aqui(fontes: Sequence[FonteDaCacada]) -> list[FonteDaCacada]:
    from .fontes_da_cacada import TIPOS_LIDOS_AQUI

    return [fonte for fonte in fontes if fonte.tipo in TIPOS_LIDOS_AQUI]
