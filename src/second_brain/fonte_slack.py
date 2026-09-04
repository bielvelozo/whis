"""Fonte passiva do Slack: as conversas do dia, com a blocklist antes da busca.

A última das três fontes, e a única que depende de gente: a app interna precisa
de aprovação do admin do workspace. Por isso o diário nasce sem ela, marcado —
e por isso o roteiro humano vive em `docs/smoke-slack.md`.

Parâmetros fixados contra a documentação oficial (conferida em 2026-09-03):

- `GET https://slack.com/api/<método>`, autenticado com
  `Authorization: Bearer <user token>` — https://docs.slack.dev/apis/web-api/
- `users.conversations` lista as conversas de que o usuário é membro, com
  `types`, `exclude_archived`, `limit` e o cursor em
  `response_metadata.next_cursor`. Tier 3, `limit` até 999 com recomendação de
  no máximo 200 — https://docs.slack.dev/reference/methods/users.conversations/
- `conversations.history` e `conversations.replies` recortam por `oldest` e
  `latest` em epoch, com `inclusive` — https://docs.slack.dev/reference/methods/conversations.history/
- `users.info` resolve id em nome, Tier 4, scope `users:read` —
  https://docs.slack.dev/reference/methods/users.info/
- o Slack responde `HTTP 200` com `{"ok": false, "error": "..."}` nos erros de
  método, e `HTTP 429` com o cabeçalho `Retry-After` em segundos —
  https://docs.slack.dev/apis/web-api/rate-limits/

**A exceção de rate limit que sustenta esta camada, re-checada em 2026-09-03:**
a mudança de 29/mai/2025 derrubou apps *comercialmente distribuídas* fora do
Marketplace para 1 requisição/min e 15 objetos por resposta em
`conversations.history`/`.replies`, mas a página de rate limits continua
dizendo que "apps já aprovadas no Marketplace e *internal customer-built
applications* não devem ver mudança de rate limit", e as páginas dos dois
métodos continuam declarando **Tier 3 (50+/min)** com `limit` de até 1.000 para
esse caso. A app deste projeto é interna e não distribuída: fica no Tier 3.

O token vem só da configuração local (`[slack].user_token`); nenhuma mensagem
de erro daqui repete o token, e a blocklist é aplicada **antes** de qualquer
requisição de conteúdo — conversa excluída não é sequer consultada.
"""

from __future__ import annotations

import contextlib
import html
import json
import logging
import re
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from .configuracao import Configuracao
from .fontes import ErroDeFonte, Evento, Janela

_log = logging.getLogger("second_brain.fonte_slack")

#: O nome desta fonte no contrato — vai para o frontmatter e para a seção da nota.
NOME = "slack"

#: Raiz da Web API. Sem barra no fim; cada método é um caminho abaixo dela.
BASE = "https://slack.com/api"

#: Os user scopes que a app interna precisa, e nada além disso. `search:read`
#: fica de fora de propósito: a busca não é usada aqui e é dos scopes que mais
#: levantam bandeira na revisão do admin.
SCOPES_MINIMOS = (
    "channels:history",
    "channels:read",
    "groups:history",
    "groups:read",
    "im:history",
    "im:read",
    "mpim:history",
    "mpim:read",
    "users:read",
)

#: Canais públicos e privados, group DMs e DMs — "tudo que o usuário participa".
TIPOS_DE_CONVERSA = "public_channel,private_channel,mpim,im"

#: Conversas por página. O teto é 999, mas a própria documentação recomenda
#: não passar de 200.
CONVERSAS_POR_PAGINA = 200

#: Mensagens por página, pela mesma recomendação. Um dia de canal movimentado
#: cabe numa página só.
MENSAGENS_POR_PAGINA = 200

#: Teto de páginas por listagem. Existe contra um cursor que não avança, que
#: giraria para sempre queimando a cota do usuário.
PAGINAS_MAXIMAS = 20

#: Quantas vezes esperar o `Retry-After` antes de desistir da coleta.
TENTATIVAS_APOS_429 = 3

#: Quanto esperar quando o Slack limita sem dizer por quanto tempo.
ESPERA_PADRAO_S = 5.0

#: Espera acima da qual desistir em vez de dormir. A tarefa agendada roda à
#: noite sem ninguém olhando: melhor um diário marcado como incompleto que um
#: processo pendurado por uma hora.
ESPERA_MAXIMA_S = 60.0

#: Tempos limite explícitos: rede caída tem que aparecer rápido, porque o
#: diário roda sozinho.
TEMPO_LIMITE_PADRAO = httpx.Timeout(connect=15.0, write=30.0, read=60.0, pool=15.0)

#: Erros que condenam a coleta inteira: nenhuma outra conversa vai funcionar.
ERROS_DE_CREDENCIAL = frozenset(
    {
        "not_authed",
        "invalid_auth",
        "account_inactive",
        "token_revoked",
        "token_expired",
        "missing_scope",
        "not_allowed_token_type",
        "no_permission",
        "org_login_required",
        "team_access_not_granted",
    }
)

#: Erros que valem para uma conversa só. O diário segue sem ela — perder um
#: canal é melhor que perder o Slack inteiro.
ERROS_DE_CONVERSA = frozenset(
    {
        "channel_not_found",
        "not_in_channel",
        "is_archived",
        "access_denied",
        "ekm_access_denied",
        "channel_is_limited_access",
        "enterprise_is_restricted",
        "thread_not_found",
        "message_not_found",
    }
)

#: Subtipos que são manutenção do canal, não conversa. Entrar e sair de canal
#: encheria o diário de linhas que não dizem nada sobre o trabalho.
SUBTIPOS_IGNORADOS = frozenset(
    {
        "channel_join",
        "channel_leave",
        "channel_topic",
        "channel_purpose",
        "channel_name",
        "channel_archive",
        "channel_unarchive",
        "group_join",
        "group_leave",
        "group_topic",
        "group_purpose",
        "group_name",
        "group_archive",
        "group_unarchive",
    }
)

_ID_DE_SLACK = re.compile(r"[UWCDGBST][A-Z0-9]{6,}")
_MENCAO = re.compile(r"<([@#!])([^>|]*)(?:\|([^>]*))?>")
_LINK = re.compile(r"<((?:https?|mailto):[^>|]*)(?:\|([^>]*))?>")
_SUFIXO_DE_GRUPO = re.compile(r"-\d+$")


class _ErroDoSlack(ErroDeFonte):
    """Um `ok: false` do Slack, já traduzido, com o código para quem decide.

    É um `ErroDeFonte` de propósito: se escapar sem ninguém olhar o código, a
    costura ainda sabe tratá-lo — o contrato proíbe qualquer outra exceção sair
    daqui.
    """

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


class FonteSlack:
    """Fonte passiva do Slack, falando a Web API por HTTP.

    `cliente` existe para os testes injetarem um `httpx.Client` com transporte
    falso: assim o caminho que monta a requisição é o mesmo em teste e em
    produção. `dormir` existe pelo mesmo motivo — a espera do `Retry-After` é
    comportamento, e teste não pode dormir de verdade.
    """

    nome = NOME

    def __init__(
        self,
        user_token: str,
        *,
        conversas_excluidas: Sequence[str] = (),
        so_com_mencao: Sequence[str] = (),
        base: str = BASE,
        conversas_por_pagina: int = CONVERSAS_POR_PAGINA,
        mensagens_por_pagina: int = MENSAGENS_POR_PAGINA,
        tempo_limite: httpx.Timeout | float = TEMPO_LIMITE_PADRAO,
        cliente: httpx.Client | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = (user_token or "").strip()
        brutos = [padrao.strip().lstrip("#@") for padrao in conversas_excluidas]
        brutos = [padrao for padrao in brutos if padrao]
        self._excluidas = tuple(padrao.casefold() for padrao in brutos)
        # Resolver o nome de quem está do outro lado de cada DM custa uma
        # requisição por conversa. Só vale a pena quando a blocklist tem algum
        # padrão que não é um id — que é o caso de "@joana".
        self._blocklist_por_nome = any(
            not _ID_DE_SLACK.fullmatch(padrao) for padrao in brutos
        )
        self._so_com_mencao = tuple(
            padrao.strip().lstrip("#@").casefold()
            for padrao in so_com_mencao
            if padrao.strip()
        )
        self._base = base.rstrip("/")
        self._conversas_por_pagina = conversas_por_pagina
        self._mensagens_por_pagina = mensagens_por_pagina
        self._tempo_limite = tempo_limite
        self._cliente = cliente
        self._dormir = dormir

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        """As mensagens da janela nas conversas que a blocklist não bloqueou.

        Toda falha vira `ErroDeFonte`: token ausente, token recusado, scope
        faltando, HTTP que não é 200, corpo que não é JSON e o `ok: false` do
        Slack. É o que deixa o diário nascer sem o Slack, marcado, em vez de
        não nascer.
        """
        if not self._token:
            raise ErroDeFonte(
                "Token do Slack ausente em [slack].user_token. Crie a app "
                "interna no seu workspace, autorize os User Token Scopes de "
                "leitura e cole o token xoxp no config.toml — o roteiro está "
                "em docs/smoke-slack.md."
            )

        eventos: list[Evento] = []
        bloqueadas = 0
        descartados = 0
        with self._sessao() as cliente:
            chamar = _Chamador(
                cliente, self._token, self._base, self._tempo_limite, self._dormir
            )
            # `auth.test` não lê conversa nenhuma e serve a dois propósitos: dá
            # o endereço do workspace, de onde saem os permalinks, e recusa um
            # token inválido antes de percorrer o workspace inteiro.
            sou_eu = chamar("auth.test", verbo="POST")
            workspace = str(sou_eu.get("url") or "")
            nomes = _Nomes(chamar)
            meus_nomes = self._meus_nomes(sou_eu, nomes)

            for conversa in self._conversas(chamar):
                if self._bloqueada(conversa, nomes):
                    bloqueadas += 1
                    continue
                colhidos = self._da_conversa(
                    chamar, nomes, conversa, janela, workspace
                )
                if self._so_o_que_me_cita(conversa, nomes):
                    antes = len(colhidos)
                    colhidos = [e for e in colhidos if _me_cita(e, meus_nomes)]
                    descartados += antes - len(colhidos)
                eventos.extend(colhidos)

        if bloqueadas:
            # Só a contagem: o nome de uma conversa que o usuário mandou nunca
            # ler não deve acabar no arquivo de log por causa do diagnóstico.
            _log.info(
                "Slack: %d conversa(s) da blocklist não foram consultadas.", bloqueadas
            )
        if descartados:
            _log.info(
                "Slack: %d mensagem(ns) fora de [slack].so_com_mencao descartadas "
                "por não citarem você.",
                descartados,
            )
        _log.info(
            "Slack: %d eventos entre %s e %s.",
            len(eventos),
            janela.inicio.isoformat(),
            janela.fim.isoformat(),
        )
        return tuple(eventos)

    # -- Conversas ----------------------------------------------------------

    @contextlib.contextmanager
    def _sessao(self) -> Iterator[httpx.Client]:
        """O cliente injetado (teste) ou um cliente próprio, fechado no fim."""
        if self._cliente is not None:
            yield self._cliente
            return
        with httpx.Client(timeout=self._tempo_limite) as cliente:
            yield cliente

    def _conversas(self, chamar: _Chamador) -> Iterator[dict[str, Any]]:
        """As conversas de que o usuário é membro, página a página."""
        for corpo in _paginar(
            chamar,
            "users.conversations",
            {
                "types": TIPOS_DE_CONVERSA,
                "exclude_archived": "true",
                "limit": self._conversas_por_pagina,
            },
        ):
            for conversa in corpo.get("channels") or []:
                if isinstance(conversa, dict) and conversa.get("id"):
                    yield conversa

    def _bloqueada(self, conversa: dict[str, Any], nomes: _Nomes) -> bool:
        """A conversa está na blocklist? Decidido **antes** de qualquer leitura.

        Casa por substring, sem diferenciar maiúsculas, contra o id, o nome do
        canal e — nas DMs — o nome de quem está do outro lado. Bloquear demais
        é o erro seguro numa lista cujo propósito é privacidade.
        """
        if not self._excluidas:
            return False

        candidatos = [str(conversa.get("id") or ""), str(conversa.get("name") or "")]
        if conversa.get("user"):
            candidatos.append(str(conversa["user"]))
        if self._casa("\n".join(candidatos)):
            return True

        if not conversa.get("is_im") or not self._blocklist_por_nome:
            return False
        # Uma DM não tem nome: sem resolver quem está do outro lado, "@joana"
        # não teria como bloquear nada. `users.info` fala sobre a pessoa, não
        # sobre a conversa — nenhuma mensagem é lida aqui.
        return self._casa("\n".join(nomes.apelidos(conversa.get("user"))))

    def _meus_nomes(self, sou_eu: dict[str, Any], nomes: _Nomes) -> tuple[str, ...]:
        """Como o meu nome aparece em `Evento.pessoas`, para reconhecê-lo lá.

        Vem do `auth.test` que já foi feito, e não da configuração: quem sou eu
        naquele workspace é fato do token, e pedir isso ao usuário seria um
        cadastro a mais para ele errar.
        """
        if not self._so_com_mencao:
            return ()
        identificador = str(sou_eu.get("user_id") or "").strip()
        apelidos = list(nomes.apelidos(identificador)) if identificador else []
        for bruto in (sou_eu.get("user"), identificador):
            texto = str(bruto or "").strip()
            if texto and texto not in apelidos:
                apelidos.append(texto)
        return tuple(apelidos)

    def _so_o_que_me_cita(self, conversa: dict[str, Any], nomes: _Nomes) -> bool:
        """Nesta conversa, só entra o que cita o usuário?

        Diferente da blocklist, isto age **depois** da leitura: o canal é lido
        inteiro e a maior parte é descartada. É a única forma de saber quem uma
        mensagem cita, e o custo em requisição é o mesmo de ler o canal todo.
        """
        if not self._so_com_mencao:
            return False
        candidatos = [str(conversa.get("id") or ""), str(conversa.get("name") or "")]
        if conversa.get("user"):
            candidatos.extend(nomes.apelidos(conversa.get("user")))
        alvo = "\n".join(candidatos).casefold()
        return any(padrao in alvo for padrao in self._so_com_mencao)

    def _casa(self, alvo: str) -> bool:
        dobrado = alvo.casefold()
        return any(padrao in dobrado for padrao in self._excluidas)

    # -- Mensagens ----------------------------------------------------------

    def _da_conversa(
        self,
        chamar: _Chamador,
        nomes: _Nomes,
        conversa: dict[str, Any],
        janela: Janela,
        workspace: str,
    ) -> list[Evento]:
        """As mensagens de uma conversa na janela, threads incluídas.

        Uma conversa que o Slack recusa individualmente — canal arquivado, o
        usuário removido dele — vira aviso no log e a coleta segue: perder um
        canal é melhor que perder o Slack inteiro do diário.
        """
        canal = str(conversa["id"])
        referencia = _referencia(conversa, nomes)
        eventos: list[Evento] = []
        try:
            for mensagem in self._historico(chamar, canal, janela):
                evento = _evento(
                    mensagem,
                    janela=janela,
                    canal=canal,
                    referencia=referencia,
                    workspace=workspace,
                    nomes=nomes,
                )
                if evento is not None:
                    eventos.append(evento)
                if not _abre_thread(mensagem):
                    continue
                eventos.extend(
                    self._da_thread(
                        chamar,
                        nomes,
                        canal,
                        str(mensagem["ts"]),
                        janela,
                        referencia,
                        workspace,
                    )
                )
        except _ErroDoSlack as erro:
            if erro.codigo not in ERROS_DE_CONVERSA:
                raise
            _log.warning(
                "Slack: a conversa %s não pôde ser lida (%s) — o diário segue "
                "sem ela.",
                canal,
                erro.codigo,
            )
        return eventos

    def _historico(
        self, chamar: _Chamador, canal: str, janela: Janela
    ) -> Iterator[dict[str, Any]]:
        """As mensagens da conversa dentro da janela, página a página."""
        for corpo in _paginar(
            chamar,
            "conversations.history",
            {
                "channel": canal,
                "oldest": _epoch(janela.inicio),
                "latest": _epoch(janela.fim),
                "inclusive": "true",
                "limit": self._mensagens_por_pagina,
            },
        ):
            yield from _mensagens(corpo)

    def _da_thread(
        self,
        chamar: _Chamador,
        nomes: _Nomes,
        canal: str,
        thread_ts: str,
        janela: Janela,
        referencia: str | None,
        workspace: str,
    ) -> list[Evento]:
        """As respostas de uma thread que caem na janela.

        `conversations.replies` devolve a mensagem-mãe junto das respostas; ela
        é descartada aqui porque já entrou pelo histórico.
        """
        eventos: list[Evento] = []
        for corpo in _paginar(
            chamar,
            "conversations.replies",
            {
                "channel": canal,
                "ts": thread_ts,
                "oldest": _epoch(janela.inicio),
                "latest": _epoch(janela.fim),
                "inclusive": "true",
                "limit": self._mensagens_por_pagina,
            },
        ):
            for resposta in _mensagens(corpo):
                if str(resposta.get("ts") or "") == thread_ts:
                    continue
                evento = _evento(
                    resposta,
                    janela=janela,
                    canal=canal,
                    referencia=referencia,
                    workspace=workspace,
                    nomes=nomes,
                    thread_ts=thread_ts,
                )
                if evento is not None:
                    eventos.append(evento)
        return eventos


def de_configuracao(configuracao: Configuracao, **extras: Any) -> FonteSlack:
    """Monta o coletor a partir da configuração local — o atalho da CLI."""
    return FonteSlack(
        configuracao.slack_user_token,
        conversas_excluidas=configuracao.slack_conversas_excluidas,
        so_com_mencao=configuracao.slack_so_com_mencao,
        **extras,
    )


# -- HTTP -------------------------------------------------------------------


class _Chamador:
    """Uma chamada à Web API, já traduzida para corpo útil ou `ErroDeFonte`.

    Concentra o que toda chamada compartilha: o cabeçalho de autorização, o
    `Retry-After` do 429 e a tradução dos códigos de erro do Slack em conselhos
    em português.
    """

    def __init__(
        self,
        cliente: httpx.Client,
        token: str,
        base: str,
        tempo_limite: httpx.Timeout | float,
        dormir: Callable[[float], None],
    ) -> None:
        self._cliente = cliente
        self._token = token
        self._base = base
        self._tempo_limite = tempo_limite
        self._dormir = dormir

    def __call__(
        self,
        metodo: str,
        parametros: dict[str, Any] | None = None,
        *,
        verbo: str = "GET",
    ) -> dict[str, Any]:
        for tentativa in range(TENTATIVAS_APOS_429 + 1):
            resposta = self._requisitar(metodo, parametros or {}, verbo)

            limitado = resposta.status_code == httpx.codes.TOO_MANY_REQUESTS
            corpo: dict[str, Any] = {}
            if not limitado:
                if resposta.status_code != httpx.codes.OK:
                    raise _erro_de_http(metodo, resposta)
                corpo = _corpo(metodo, resposta)
                if corpo.get("ok"):
                    return corpo
                limitado = str(corpo.get("error") or "") == "ratelimited"

            if not limitado:
                raise _erro_do_slack(metodo, corpo)
            if tentativa == TENTATIVAS_APOS_429:
                break
            self._esperar(metodo, resposta.headers.get("retry-after"))

        raise ErroDeFonte(
            f"O Slack continuou limitando a taxa de requisições em '{metodo}' "
            f"depois de {TENTATIVAS_APOS_429} espera(s). Gere o diário deste "
            "dia de novo mais tarde — a nota é sempre regenerada."
        )

    def _requisitar(
        self, metodo: str, parametros: dict[str, Any], verbo: str
    ) -> httpx.Response:
        alvo = f"{self._base}/{metodo}"
        try:
            return self._cliente.request(
                verbo,
                alvo,
                params=parametros or None,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self._tempo_limite,
            )
        except httpx.TimeoutException as erro:
            raise ErroDeFonte(
                f"O Slack não respondeu a tempo em '{metodo}' "
                f"({type(erro).__name__}). O diário deste dia nasce sem ele; "
                "rode o comando de novo com a rede estável para regenerar a nota."
            ) from erro
        except httpx.HTTPError as erro:
            raise ErroDeFonte(
                f"Falha de rede ao falar com o Slack em '{metodo}': "
                f"{type(erro).__name__}: {erro}. Confira a conexão e gere o "
                "diário de novo — a nota é sempre regenerada."
            ) from erro

    def _esperar(self, metodo: str, cabecalho: str | None) -> None:
        segundos = _segundos(cabecalho)
        if segundos > ESPERA_MAXIMA_S:
            raise ErroDeFonte(
                f"O Slack pediu {segundos:.0f}s de espera em '{metodo}', mais "
                f"que o teto de {ESPERA_MAXIMA_S:.0f}s deste coletor. O diário "
                "deste dia nasce sem o Slack; gere de novo mais tarde."
            )
        _log.warning(
            "Slack limitou a taxa em '%s'; esperando %.0fs como o Retry-After pediu.",
            metodo,
            segundos,
        )
        self._dormir(segundos)


def _paginar(
    chamar: _Chamador, metodo: str, parametros: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    """Percorre um método com cursor, devolvendo o corpo de cada página."""
    cursor = ""
    vistos: set[str] = set()
    for numero in range(1, PAGINAS_MAXIMAS + 1):
        corpo = chamar(metodo, {**parametros, **({"cursor": cursor} if cursor else {})})
        yield corpo

        metadados = corpo.get("response_metadata") or {}
        cursor = str(metadados.get("next_cursor") or "").strip()
        if not cursor:
            return
        if cursor in vistos:
            _log.warning(
                "Slack devolveu o mesmo cursor duas vezes em '%s' — parando na "
                "página %d para não girar em falso.",
                metodo,
                numero,
            )
            return
        vistos.add(cursor)
    _log.warning(
        "Slack: '%s' passou de %d páginas e a leitura foi interrompida — o "
        "diário deste dia pode sair incompleto.",
        metodo,
        PAGINAS_MAXIMAS,
    )


def _corpo(metodo: str, resposta: httpx.Response) -> dict[str, Any]:
    try:
        corpo = resposta.json()
    except (json.JSONDecodeError, ValueError) as erro:
        raise ErroDeFonte(
            f"O Slack respondeu HTTP {resposta.status_code} em '{metodo}' mas o "
            f"corpo não é JSON: {erro}. Gere o diário de novo; se repetir, é "
            "problema do lado do Slack."
        ) from erro
    if not isinstance(corpo, dict):
        raise ErroDeFonte(
            f"O Slack devolveu em '{metodo}' um corpo JSON que não é um objeto. "
            "Gere o diário de novo; se repetir, é problema do lado do Slack."
        )
    return corpo


def _segundos(cabecalho: str | None) -> float:
    """Quanto esperar segundo o `Retry-After`, em segundos."""
    try:
        return max(float(str(cabecalho).strip()), 0.0)
    except (TypeError, ValueError):
        return ESPERA_PADRAO_S


def _mensagens(corpo: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for mensagem in corpo.get("messages") or []:
        if isinstance(mensagem, dict):
            yield mensagem


# -- Tradução para Evento ---------------------------------------------------


def _evento(
    mensagem: dict[str, Any],
    *,
    janela: Janela,
    canal: str,
    referencia: str | None,
    workspace: str,
    nomes: _Nomes,
    thread_ts: str | None = None,
) -> Evento | None:
    """Traduz uma mensagem do Slack no `Evento` comum a toda fonte passiva."""
    if str(mensagem.get("subtype") or "") in SUBTIPOS_IGNORADOS:
        return None

    momento = _momento(mensagem.get("ts"))
    if momento is None or not janela.contem(momento):
        return None

    texto, mencionados = _texto(mensagem, nomes)
    if not texto:
        return None

    autor = _autor(mensagem, nomes)
    return Evento(
        fonte=NOME,
        momento=momento,
        titulo=f"{autor} (em thread)" if thread_ts else autor,
        detalhe=texto,
        referencia=referencia,
        url=_permalink(workspace, canal, str(mensagem.get("ts") or ""), thread_ts),
        pessoas=_distintos(autor, *mencionados),
    )


def _abre_thread(mensagem: dict[str, Any]) -> bool:
    """A mensagem é a mãe de uma thread com respostas?"""
    if not mensagem.get("ts"):
        return False
    if str(mensagem.get("thread_ts") or mensagem["ts"]) != str(mensagem["ts"]):
        return False
    try:
        return int(mensagem.get("reply_count") or 0) > 0
    except (TypeError, ValueError):
        return False


def _autor(mensagem: dict[str, Any], nomes: _Nomes) -> str:
    """Quem falou, já com nome de gente — não `U01234`.

    Mensagem de app traz `username` ou `bot_profile` em vez de um id de pessoa;
    é ela que nomeia o build que quebrou ou o alerta que disparou.
    """
    if mensagem.get("user"):
        return nomes.nome(mensagem["user"])
    perfil = mensagem.get("bot_profile") or {}
    nome = str(mensagem.get("username") or perfil.get("name") or "").strip()
    return nome or "alguém"


def _texto(mensagem: dict[str, Any], nomes: _Nomes) -> tuple[str, tuple[str, ...]]:
    """O texto legível da mensagem e as pessoas citadas dentro dele.

    Uma mensagem sem texto — só arquivo, só reação — cai no `fallback` do
    anexo; sem nada legível, ela não vira evento: linha em branco no diário não
    ajuda ninguém.
    """
    bruto = str(mensagem.get("text") or "").strip()
    if not bruto:
        for anexo in mensagem.get("attachments") or []:
            if not isinstance(anexo, dict):
                continue
            bruto = str(anexo.get("fallback") or anexo.get("text") or "").strip()
            if bruto:
                break
    if not bruto:
        return "", ()

    citados: list[str] = []

    def trocar_mencao(casamento: re.Match[str]) -> str:
        marca, alvo, rotulo = casamento.groups()
        if marca == "@":
            nome = nomes.nome(alvo) if alvo else ""
            escolhido = nome or (rotulo or "").strip() or alvo
            if nome:
                citados.append(nome)
            return f"@{escolhido}"
        if marca == "#":
            return f"#{(rotulo or '').strip() or alvo}"
        return f"@{(rotulo or '').strip().lstrip('@') or alvo.split('^')[0]}"

    texto = _LINK.sub(lambda c: (c.group(2) or "").strip() or c.group(1), bruto)
    texto = _MENCAO.sub(trocar_mencao, texto)
    return html.unescape(texto).strip(), tuple(citados)


def _referencia(conversa: dict[str, Any], nomes: _Nomes) -> str | None:
    """Onde a conversa aconteceu, como o usuário a chama no Slack."""
    if conversa.get("is_im"):
        return f"DM com {nomes.nome(conversa.get('user'))}"
    nome = str(conversa.get("name") or "").strip()
    if conversa.get("is_mpim"):
        return _grupo(nome)
    return f"#{nome}" if nome else None


def _grupo(nome: str) -> str:
    """Um group DM legível a partir do `mpdm-ana--bruno--gabriel-1` do Slack."""
    interior = _SUFIXO_DE_GRUPO.sub("", nome.removeprefix("mpdm-"))
    participantes = [parte.strip() for parte in interior.split("--") if parte.strip()]
    return f"Grupo com {', '.join(participantes)}" if participantes else "Grupo"


def _permalink(
    workspace: str, canal: str, ts: str, thread_ts: str | None = None
) -> str | None:
    """O link da mensagem, montado sem gastar uma requisição por mensagem.

    É o mesmo endereço que `chat.getPermalink` devolve
    (`https://<workspace>.slack.com/archives/<canal>/p<ts sem ponto>`, com
    `thread_ts` e `cid` nas respostas de thread), e vem do endereço do
    workspace que o `auth.test` já trouxe — pedir um permalink por mensagem
    custaria centenas de requisições por diário.
    """
    if not workspace or not canal or not ts:
        return None
    raiz = workspace if workspace.endswith("/") else f"{workspace}/"
    alvo = f"{raiz}archives/{canal}/p{ts.replace('.', '')}"
    if thread_ts and thread_ts != ts:
        alvo += f"?thread_ts={thread_ts}&cid={canal}"
    return alvo


def _momento(bruto: Any) -> datetime | None:
    """Converte o `ts` do Slack — epoch com fração — para o fuso local, aware.

    O contrato exige `momento` aware no fuso local, porque é dele que saem o
    agrupamento por dia e o `HH:MM` da nota.
    """
    try:
        return datetime.fromtimestamp(float(str(bruto)), UTC).astimezone()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _epoch(momento: datetime) -> str:
    """O limite da janela como `oldest`/`latest` esperam: epoch com fração."""
    return f"{momento.timestamp():.6f}"


def _me_cita(evento: Evento, meus_nomes: Sequence[str]) -> bool:
    """O usuário aparece nesta mensagem — citado nela ou como autor dela?

    O autor entra de propósito: o que ele mesmo escreveu num canal é trabalho
    dele, e descartá-lo por não se auto-citar tiraria da daily justamente o que
    é mais dele.
    """
    return any(nome in evento.pessoas for nome in meus_nomes)


def _distintos(*nomes: str) -> tuple[str, ...]:
    escolhidos: list[str] = []
    for nome in nomes:
        limpo = (nome or "").strip()
        if limpo and limpo not in escolhidos:
            escolhidos.append(limpo)
    return tuple(escolhidos)


class _Nomes:
    """Cache de `users.info`: cada id vira nome uma vez por coleta.

    Um dia tem muitas mensagens e poucas pessoas distintas; sem o cache, o
    diário gastaria uma requisição por mensagem só para não escrever `U01234`.
    """

    def __init__(self, chamar: _Chamador) -> None:
        self._chamar = chamar
        self._cache: dict[str, tuple[str, ...]] = {}

    def nome(self, identificador: Any) -> str:
        """O nome de exibição de uma pessoa, ou o id quando não der para saber."""
        apelidos = self.apelidos(identificador)
        return apelidos[0] if apelidos else str(identificador or "").strip()

    def apelidos(self, identificador: Any) -> tuple[str, ...]:
        """Todos os nomes conhecidos daquele id — o que a blocklist compara."""
        chave = str(identificador or "").strip()
        if not chave:
            return ()
        if chave not in self._cache:
            self._cache[chave] = self._buscar(chave)
        return self._cache[chave]

    def _buscar(self, identificador: str) -> tuple[str, ...]:
        try:
            corpo = self._chamar("users.info", {"user": identificador})
        except _ErroDoSlack as erro:
            if erro.codigo in ERROS_DE_CREDENCIAL:
                raise
            _log.warning(
                "Slack: o nome de %s não pôde ser resolvido (%s).",
                identificador,
                erro.codigo,
            )
            return (identificador,)

        pessoa = corpo.get("user") or {}
        perfil = pessoa.get("profile") or {}
        return _distintos(
            str(perfil.get("real_name") or pessoa.get("real_name") or ""),
            str(perfil.get("display_name") or ""),
            str(pessoa.get("name") or ""),
            identificador,
        )


# -- Erros ------------------------------------------------------------------

#: Conselho por código de erro do Slack. A mensagem vai literal para o aviso da
#: nota do diário: é ela que diz se o usuário precisa mexer na app, no token ou
#: só esperar.
_CONSELHOS = {
    "not_authed": (
        "Nenhum token foi aceito. Confira se [slack].user_token está preenchido "
        "com o User OAuth Token (xoxp-...) da sua app interna."
    ),
    "invalid_auth": (
        "Token do Slack inválido. Ele é invalidado quando você troca a senha ou "
        "quando o admin revoga a app. Reinstale a app em api.slack.com/apps → "
        "OAuth & Permissions e atualize [slack].user_token."
    ),
    "token_revoked": (
        "O token do Slack foi revogado. Reinstale a app interna em "
        "api.slack.com/apps → OAuth & Permissions e atualize [slack].user_token."
    ),
    "token_expired": (
        "O token do Slack expirou — o workspace deve estar com rotação de token "
        "ligada. Gere outro em OAuth & Permissions e atualize "
        "[slack].user_token."
    ),
    "account_inactive": (
        "A conta ligada a este token está desativada no workspace. Fale com o "
        "admin ou apague [slack].user_token para o diário parar de tentar."
    ),
    "not_allowed_token_type": (
        "O token de [slack].user_token não é um user token. O diário precisa do "
        "User OAuth Token (xoxp-...), não do Bot User OAuth Token (xoxb-...)."
    ),
    "no_permission": (
        "O token não tem permissão para o que o diário pede. Confira os User "
        "Token Scopes da app em OAuth & Permissions."
    ),
    "org_login_required": (
        "O workspace faz parte de uma organização Enterprise Grid e exige um "
        "token da organização. Fale com o admin sobre instalar a app interna "
        "no seu workspace."
    ),
    "team_access_not_granted": (
        "A app interna não foi aprovada para este workspace. Peça a aprovação "
        "ao admin — o que dizer a ele está em docs/smoke-slack.md."
    ),
    "invalid_cursor": (
        "O Slack recusou o cursor de paginação. Gere o diário de novo; se "
        "repetir, é problema do lado do Slack."
    ),
    "fatal_error": "O Slack falhou do lado dele. Gere o diário deste dia de novo mais tarde.",
    "internal_error": (
        "O Slack falhou do lado dele. Gere o diário deste dia de novo mais tarde."
    ),
    "service_unavailable": (
        "O Slack está fora do ar ou instável. Gere o diário deste dia de novo "
        "mais tarde — a nota é sempre regenerada."
    ),
    "request_timeout": (
        "O Slack não completou a requisição a tempo. Gere o diário deste dia de "
        "novo mais tarde."
    ),
}


def _erro_do_slack(metodo: str, corpo: dict[str, Any]) -> _ErroDoSlack:
    """Traduz o `ok: false` do Slack numa mensagem que diga o que fazer."""
    codigo = str(corpo.get("error") or "desconhecido")
    if codigo == "missing_scope":
        faltando = corpo.get("needed") or "os scopes de leitura"
        conselho = (
            f"Falta o scope {faltando} no token do Slack. Abra "
            "api.slack.com/apps → sua app → OAuth & Permissions, acrescente o "
            "que falta em User Token Scopes e reinstale a app — o token muda "
            "quando os scopes mudam."
        )
    else:
        conselho = _CONSELHOS.get(
            codigo,
            "Confira [slack].user_token e os User Token Scopes da app interna "
            "em api.slack.com/apps; o roteiro está em docs/smoke-slack.md.",
        )
    return _ErroDoSlack(
        codigo, f"O Slack recusou '{metodo}' com o erro '{codigo}': {conselho}"
    )


def _erro_de_http(metodo: str, resposta: httpx.Response) -> ErroDeFonte:
    """O status HTTP que não é 200 — o Slack reporta quase tudo dentro de um 200."""
    codigo = resposta.status_code
    if codigo >= 500:
        conselho = (
            "O Slack está fora do ar ou instável. Gere o diário deste dia de "
            "novo mais tarde — a nota é sempre regenerada."
        )
    elif codigo in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
        conselho = (
            "O Slack recusou o token. Reinstale a app interna em "
            "api.slack.com/apps → OAuth & Permissions e atualize "
            "[slack].user_token no config.toml."
        )
    else:
        conselho = (
            "O Slack recusou a requisição. Confira [slack].user_token e os "
            "User Token Scopes da app em api.slack.com/apps."
        )
    return ErroDeFonte(
        f"Slack respondeu HTTP {codigo} em '{metodo}': {conselho}{_detalhe(resposta)}"
    )


def _detalhe(resposta: httpx.Response) -> str:
    """O pouco que o Slack manda junto do status, quando manda."""
    texto = (resposta.text or "").strip()
    return f" Resposta: {texto[:200]}" if texto else ""
