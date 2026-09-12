"""A costura da daily: `gerar_daily(agora) → nota viva mantida + nota em daily/`.

A janela não é um dia civil: vai do fim da última daily até agora. Numa
segunda-feira ela cobre o fim de semana inteiro, e é isso que impede que o
trabalho de sábado caia no vão entre duas falas. A âncora mora no frontmatter
da nota datada anterior — o vault é a fonte da verdade, e o usuário audita a
janela lendo o próprio arquivo.

O que se lê antes da reunião é a **nota viva** `daily/atual.md`: o modelo
recebe a janela e a nota como está, e devolve só o que é novo e o que
terminou; quem acrescenta e move é `NotaViva`, copiando cada linha do usuário
byte a byte. A nota datada `daily/YYYY-MM-DD.md` nasce ao lado, com a janela,
o que mudou nesta execução, o bloco de *O que eu fiz* arquivado ao abrir a
janela e as listas cruas — o registro durável e de conferência.

A daily **não deriva do diário**: os dois recortes são diferentes e um não se
reconstrói do outro depois de resumido. O que as duas costuras compartilham é a
leitura das fontes, em `coleta.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from . import vault as _vault
from .coleta import FalhaDeFonte, coletar
from .configuracao import Configuracao
from .fontes import Evento, Janela, PortaFonte
from .nota_viva import SECAO_FIZ, Mudancas, NotaViva
from .portas import Daily, ErroDeDaily, PortaDaily

_log = logging.getLogger("whis.daily")

#: Quanto a primeira daily de todas cobre, por não ter nota anterior.
PRIMEIRA_JANELA = timedelta(hours=24)


@dataclass(frozen=True)
class JanelaDaDaily:
    """O intervalo que uma daily cobre: da última fala até agora."""

    data: date
    desde: datetime
    ate: datetime
    primeira: bool = False

    def como_janela(self) -> Janela:
        """A mesma janela no formato que toda fonte passiva conhece."""
        return Janela(data=self.data, inicio=self.desde, fim=self.ate)


@dataclass(frozen=True)
class ResultadoDaDaily:
    """O que a geração produziu — o suficiente para falar sem reler a nota."""

    janela: JanelaDaDaily
    nota: Path | None
    eventos: tuple[Evento, ...]
    excluidos: int
    fontes_lidas: tuple[str, ...]
    fontes_com_falha: tuple[FalhaDeFonte, ...]
    reunioes: tuple[str, ...]
    roteiro: Daily | None
    #: `daily/atual.md`, quando ela existe ao fim da execução.
    nota_viva: Path | None
    #: As quatro seções da nota viva como ficaram — o que se lê em voz alta.
    secoes: tuple[tuple[str, tuple[str, ...]], ...]
    #: O que esta execução acrescentou e moveu; `None` se a nota viva não foi tocada.
    mudancas: Mudancas | None
    #: Eventos que ficam só no vault: casaram com `[daily].referencias_pessoais`.
    calados: tuple[Evento, ...] = ()
    vazio: bool = False
    simulado: bool = False
    falha_do_roteiro: str | None = None


def janela_da_daily(agora: datetime, vault: Path) -> JanelaDaDaily:
    """De quando até quando esta daily fala.

    `desde` é o `ate` da daily mais recente **de um dia anterior** — nunca o da
    daily de hoje, senão rodar o comando duas vezes no mesmo dia deixaria a
    segunda com uma janela vazia. Sem nenhuma daily anterior, cobre as últimas
    24 horas e a nota diz que foi a primeira.

    A daily de hoje entra por outro motivo: se ela já existe, o `desde` dela é
    o que vale, e a nova execução só estende o `ate`. Sem isso, a janela de
    quem roda o comando duas vezes escorregaria para frente.
    """
    anterior = _vault.ate_da_daily_anterior(vault, agora.date())
    de_hoje = _vault.desde_da_daily_de(vault, agora.date())

    if de_hoje is not None:
        _log.info("Já há daily hoje — mantendo o início em %s.", de_hoje.isoformat())
        return JanelaDaDaily(
            data=agora.date(), desde=de_hoje, ate=agora, primeira=anterior is None
        )
    if anterior is not None:
        _log.info("Ancorada na daily anterior, que foi até %s.", anterior.isoformat())
        return JanelaDaDaily(data=agora.date(), desde=anterior, ate=agora)

    _log.info("Nenhuma daily anterior no vault — cobrindo as últimas 24 horas.")
    return JanelaDaDaily(
        data=agora.date(), desde=agora - PRIMEIRA_JANELA, ate=agora, primeira=True
    )


def do_trabalho(
    eventos: Sequence[Evento], pessoais: Sequence[str]
) -> tuple[tuple[Evento, ...], tuple[Evento, ...]]:
    """Separa o que se fala na daily do que só fica guardado no vault.

    Um evento é **pessoal** se algum padrão aparecer na `referencia` dele —
    substring, `casefold()` dos dois lados, como o filtro de exclusão. Todo o
    resto é do trabalho, inclusive evento **sem referência**.

    Lista-se o pessoal, e não o trabalho, porque o que é do trabalho cresce
    toda semana — projeto novo no Linear, repositório novo — e o que é pessoal
    é um punhado de coisas que o usuário conhece. Assim a régua erra para o
    lado de **falar demais**, que ele vê ao reler o roteiro antes de falar;
    errar para o silêncio esconderia trabalho de verdade, e ausência é mais
    difícil de notar que excesso.

    Lista vazia devolve tudo como do trabalho: o comportamento de quem nunca
    configurou nada.
    """
    padroes = [padrao.casefold() for padrao in pessoais if padrao.strip()]
    if not padroes:
        return tuple(eventos), ()

    falados: list[Evento] = []
    calados: list[Evento] = []
    for evento in eventos:
        referencia = (evento.referencia or "").casefold()
        pessoal = bool(referencia) and any(p in referencia for p in padroes)
        (calados if pessoal else falados).append(evento)
    return tuple(falados), tuple(calados)


def gerar_daily(
    agora: datetime,
    *,
    configuracao: Configuracao,
    fontes: Sequence[PortaFonte],
    roteiro: PortaDaily,
    simular: bool = False,
) -> ResultadoDaDaily:
    """Lê a janela desde a última daily, mantém `daily/atual.md` e escreve a nota do dia.

    Rodar de novo no mesmo dia mantém o `desde`, estende o `ate` até agora e
    reescreve a nota daquele dia; a nota viva só ganha o que ainda não estava
    nela. Nada cai no vão: o que acontecer depois da geração entra na daily de
    amanhã.

    `simular=True` coleta e filtra, mas não chama o Claude nem escreve nada.
    """
    janela = janela_da_daily(agora, configuracao.vault)
    _log.info(
        "Daily de %s — de %s até %s.",
        janela.data.isoformat(),
        janela.desde.isoformat(),
        janela.ate.isoformat(),
    )

    colhido = coletar(fontes, janela.como_janela(), configuracao=configuracao)

    # O corte trabalho/pessoal acontece antes da simulação de propósito: é pelo
    # `--simular` que o usuário confere a configuração sem pagar uma chamada.
    para_falar, calados = do_trabalho(
        colhido.eventos, configuracao.daily_referencias_pessoais
    )
    if calados:
        _log.info(
            "%d evento(s) de [daily].referencias_pessoais não vão ao roteiro; "
            "continuam nas listas cruas da nota.",
            len(calados),
        )

    nota_viva = _vault.ler_nota_viva(configuracao.vault)
    parcial = ResultadoDaDaily(
        janela=janela,
        nota=None,
        eventos=colhido.eventos,
        excluidos=colhido.excluidos,
        fontes_lidas=colhido.fontes_lidas,
        fontes_com_falha=colhido.fontes_com_falha,
        reunioes=colhido.reunioes,
        roteiro=None,
        nota_viva=None,
        secoes=nota_viva.secoes(),
        mudancas=None,
        calados=calados,
    )

    if colhido.vazia():
        _log.info("Nada desde a última daily — nenhuma nota foi escrita.")
        return replace(parcial, vazio=True)

    if simular:
        _log.info("Simulação — o Claude não foi chamado e nada foi escrito.")
        return replace(parcial, simulado=True)

    # Só o que é do trabalho é FALADO; `montar_daily` abaixo recebe todos os
    # eventos, porque a nota datada é o registro durável do vault e a memória
    # é do usuário — o time só ouve o que está na nota viva.
    if not para_falar and not colhido.reunioes:
        # Um fim de semana inteiro de projeto pessoal é isto: pedir ao modelo
        # sobre nada gastaria a assinatura para receber três listas vazias. A
        # nota viva é mantida mesmo assim — a janela abriu, e *O que eu fiz*
        # da janela anterior precisa ser arquivado.
        _log.info("Nada do trabalho no período — o Claude não foi chamado.")
        falado, falha = None, (
            "não houve nada do trabalho neste período — só o que está em "
            "[daily].referencias_pessoais, que fica fora do roteiro."
        )
        resposta: Daily | None = Daily()
    else:
        falado, falha = _montar_roteiro(roteiro, para_falar, colhido.reunioes, nota_viva)
        resposta = falado

    raiz = _vault.preparar(configuracao.vault)
    arquivado = _vault.arquivo_da_nota_viva(raiz, janela.data)
    mudancas: Mudancas | None = None
    caminho_da_nota_viva: Path | None = None
    if resposta is not None:
        if arquivado is None:
            arquivado = nota_viva.arquivar_fiz()
            _log.info(
                "Janela nova: %d linha(s) de '%s' arquivadas na nota de hoje.",
                len(arquivado),
                SECAO_FIZ,
            )
        mudancas = nota_viva.aplicar(resposta)
        caminho_da_nota_viva = _vault.escrever_nota_viva(raiz, nota_viva)
        _log.info(
            "Nota viva mantida: %d bloco(s) acrescentado(s), %d movido(s), "
            "%d referência(s) ignorada(s), %d repetido(s).",
            len(mudancas.acrescentadas),
            len(mudancas.movidas),
            len(mudancas.ignorados),
            len(mudancas.repetidos),
        )
    elif (raiz / _vault.CAMINHO_DA_NOTA_VIVA).is_file():
        caminho_da_nota_viva = raiz / _vault.CAMINHO_DA_NOTA_VIVA

    caminho = _vault.caminho_da_daily(janela.data)
    nota = _vault.escrever(
        raiz,
        caminho,
        _vault.montar_daily(
            janela=janela,
            eventos=colhido.eventos,
            reunioes=colhido.reunioes,
            fontes_lidas=colhido.fontes_lidas,
            fontes_com_falha=colhido.fontes_com_falha,
            mudancas=mudancas,
            arquivado=arquivado,
            falha_do_roteiro=falha,
        ),
        zonas=_vault.ZONAS_DA_DAILY,
    )
    _log.info("Daily disponível no vault: %s", caminho)

    return replace(
        parcial,
        nota=nota,
        roteiro=falado,
        nota_viva=caminho_da_nota_viva,
        secoes=nota_viva.secoes(),
        mudancas=mudancas,
        falha_do_roteiro=falha,
    )


def _montar_roteiro(
    roteiro: PortaDaily,
    eventos: tuple[Evento, ...],
    reunioes: tuple[str, ...],
    nota_viva: NotaViva,
) -> tuple[Daily | None, str | None]:
    """Pede ao Claude o que muda na nota viva; uma falha dele não custa a daily.

    As listas cruas não existem em nenhum outro lugar — perder a nota datada
    por causa do Claude seria perder o período. A nota viva, essa fica como
    estava.
    """
    try:
        return roteiro.resumir_daily(eventos, reunioes, nota_viva), None
    except ErroDeDaily as erro:
        _log.error("A daily ficou sem roteiro: %s", erro)
        return None, str(erro)
