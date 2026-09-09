"""Adaptador real de `PortaFonte`: a movimentação do Linear dentro da janela.

Lê **tudo que a chave enxerga** — issues que andaram, comentários escritos e
mudanças de estado —, não só a atividade do usuário. O recorte por time não é
feito na consulta: ele mora na própria Personal API Key, que é criada
restrita aos times do usuário e com a permissão **Read**. Quem decide o escopo
é o painel do Linear, não este módulo; o roteiro está em `docs/smoke-linear.md`.

Parâmetros fixados contra a documentação oficial (conferida em 2026-09-03):

- endpoint único `POST https://api.linear.app/graphql`, autenticado com
  `Authorization: <API_KEY>` — **sem** o prefixo `Bearer`, que é só do OAuth
  — https://linear.app/developers/graphql
- chave criada em *Settings → Account → Security & Access*, com permissões
  selecionáveis (Read, Write, Admin, Create issues, Create comments) e limite
  por time — https://linear.app/docs/api-and-webhooks
- filtro `filter: { updatedAt: { gte, lt } }`, com os comparadores de data
  `gt`/`gte`/`lt`/`lte` — https://linear.app/developers/filtering
- paginação Relay com `first`/`after` e `pageInfo { hasNextPage endCursor }`,
  50 itens por padrão — https://linear.app/developers/pagination
- limites de 2.500 requisições/h, 3.000.000 pontos/h e 10.000 pontos por
  consulta — https://linear.app/developers/rate-limiting

A chave vem só da configuração local (`[linear].api_key`); nada de segredo no
repositório, e nenhuma mensagem de erro daqui repete a chave.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .configuracao import Configuracao
from .fontes import ErroDeFonte, Evento, Janela

_log = logging.getLogger("whis.fonte.linear")

#: Endpoint GraphQL único do Linear.
ENDPOINT = "https://api.linear.app/graphql"

#: Itens por página. 50 é o padrão da API e cabe folgado nos 10.000 pontos.
TAMANHO_DA_PAGINA = 50

#: Entradas de histórico lidas por issue, das mais recentes para trás (`last`).
#: Uma issue que andou hoje tem as mudanças de hoje no fim da trilha; pedir as
#: primeiras traria a criação dela, de meses atrás.
HISTORICO_POR_ISSUE = 20

#: Teto de páginas por consulta. Um dia de trabalho não passa de duas ou três;
#: o teto existe contra um cursor que não avança, que giraria para sempre
#: queimando a cota de 2.500 requisições/h do usuário.
PAGINAS_MAXIMAS = 40

#: Tempos limite explícitos: a consulta é pequena, mas rede caída tem que
#: aparecer rápido — o diário roda sozinho, sem ninguém olhando.
TEMPO_LIMITE_PADRAO = httpx.Timeout(connect=15.0, write=30.0, read=60.0, pool=15.0)

#: As issues que andaram na janela, cada uma com o fim da sua trilha de
#: atividade — é de `history` que saem as mudanças de estado.
CONSULTA_DE_ISSUES = """
query DiarioIssues(
  $inicio: DateTimeOrDuration!
  $fim: DateTimeOrDuration!
  $pagina: Int!
  $historico: Int!
  $cursor: String
) {
  issues(
    first: $pagina
    after: $cursor
    orderBy: updatedAt
    filter: { updatedAt: { gte: $inicio, lt: $fim } }
  ) {
    pageInfo { hasNextPage endCursor }
    nodes {
      identifier
      title
      url
      createdAt
      updatedAt
      state { name }
      team { name }
      project { name }
      creator { name }
      assignee { name }
      history(last: $historico) {
        nodes {
          createdAt
          actor { name }
          fromState { name }
          toState { name }
        }
      }
    }
  }
}
""".strip()

#: Os comentários escritos na janela. Filtrados por `createdAt`, e não por
#: `updatedAt`, porque um comentário é um acontecimento na hora em que foi
#: escrito: filtrar pela edição colocaria no diário de hoje um comentário de
#: semana passada, com `momento` fora da janela — o que o contrato proíbe.
CONSULTA_DE_COMENTARIOS = """
query DiarioComentarios(
  $inicio: DateTimeOrDuration!
  $fim: DateTimeOrDuration!
  $pagina: Int!
  $cursor: String
) {
  comments(
    first: $pagina
    after: $cursor
    filter: { createdAt: { gte: $inicio, lt: $fim } }
  ) {
    pageInfo { hasNextPage endCursor }
    nodes {
      body
      createdAt
      url
      user { name }
      project { name }
      issue {
        identifier
        title
        url
        team { name }
        project { name }
      }
    }
  }
}
""".strip()


class FonteLinear:
    """Fonte passiva do Linear, falando GraphQL por HTTP.

    `cliente` existe para os testes injetarem um `httpx.Client` com transporte
    falso: assim o caminho que monta a requisição é o mesmo em teste e em
    produção. Quando não vem, cada coleta abre e fecha o seu cliente.
    """

    nome = "linear"

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = ENDPOINT,
        tamanho_da_pagina: int = TAMANHO_DA_PAGINA,
        historico_por_issue: int = HISTORICO_POR_ISSUE,
        tempo_limite: httpx.Timeout | float = TEMPO_LIMITE_PADRAO,
        cliente: httpx.Client | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._endpoint = endpoint
        self._tamanho_da_pagina = tamanho_da_pagina
        self._historico_por_issue = historico_por_issue
        self._tempo_limite = tempo_limite
        self._cliente = cliente

    def coletar(self, janela: Janela) -> tuple[Evento, ...]:
        """As issues, os comentários e as mudanças de estado da janela.

        Toda falha vira `ErroDeFonte`: a chave ausente, a chave recusada, o
        HTTP que não é 200, o corpo que não é JSON e os erros que o GraphQL
        devolve dentro de um 200. É o que deixa o diário nascer sem o Linear,
        marcado, em vez de não nascer.
        """
        if not self._api_key:
            raise ErroDeFonte(
                "Chave do Linear ausente em [linear].api_key. Crie uma Personal "
                "API Key com a permissão Read em Settings → Account → Security & "
                "Access (linear.app) e cole no config.toml — o roteiro está em "
                "docs/smoke-linear.md."
            )

        inicio = _instante_para_a_api(janela.inicio)
        fim = _instante_para_a_api(janela.fim)
        eventos: list[Evento] = []
        with self._sessao() as cliente:
            for pagina in self._paginar(
                cliente,
                CONSULTA_DE_ISSUES,
                "issues",
                {
                    "inicio": inicio,
                    "fim": fim,
                    "pagina": self._tamanho_da_pagina,
                    "historico": self._historico_por_issue,
                },
            ):
                for issue in pagina:
                    eventos.extend(_eventos_da_issue(issue, janela))

            for pagina in self._paginar(
                cliente,
                CONSULTA_DE_COMENTARIOS,
                "comments",
                {
                    "inicio": inicio,
                    "fim": fim,
                    "pagina": self._tamanho_da_pagina,
                },
            ):
                for comentario in pagina:
                    evento = _evento_do_comentario(comentario, janela)
                    if evento is not None:
                        eventos.append(evento)

        _log.info(
            "Linear: %d eventos entre %s e %s.",
            len(eventos),
            janela.inicio.isoformat(),
            janela.fim.isoformat(),
        )
        return tuple(eventos)

    # -- HTTP ---------------------------------------------------------------

    @contextlib.contextmanager
    def _sessao(self) -> Iterator[httpx.Client]:
        """O cliente injetado (teste) ou um cliente próprio, fechado no fim."""
        if self._cliente is not None:
            yield self._cliente
            return
        with httpx.Client(timeout=self._tempo_limite) as cliente:
            yield cliente

    def _paginar(
        self,
        cliente: httpx.Client,
        consulta: str,
        conexao: str,
        variaveis: dict[str, Any],
    ) -> Iterator[list[dict[str, Any]]]:
        """Percorre uma conexão Relay página a página, devolvendo os nós."""
        cursor: str | None = None
        vistos: set[str] = set()
        for numero in range(1, PAGINAS_MAXIMAS + 1):
            dados = self._consultar(cliente, consulta, {**variaveis, "cursor": cursor})
            bloco = dados.get(conexao) or {}
            yield [no for no in (bloco.get("nodes") or []) if isinstance(no, dict)]

            info = bloco.get("pageInfo") or {}
            cursor = info.get("endCursor")
            if not info.get("hasNextPage") or not cursor:
                return
            if cursor in vistos:
                _log.warning(
                    "Linear devolveu o mesmo cursor duas vezes em '%s' — parando "
                    "na página %d para não girar em falso.",
                    conexao,
                    numero,
                )
                return
            vistos.add(cursor)
        _log.warning(
            "Linear: '%s' passou de %d páginas de %d itens e a leitura foi "
            "interrompida — o diário deste dia pode sair incompleto.",
            conexao,
            PAGINAS_MAXIMAS,
            self._tamanho_da_pagina,
        )

    def _consultar(
        self, cliente: httpx.Client, consulta: str, variaveis: dict[str, Any]
    ) -> dict[str, Any]:
        """Uma requisição GraphQL, já traduzida para `data` ou `ErroDeFonte`."""
        try:
            resposta = cliente.post(
                self._endpoint,
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
                json={"query": consulta, "variables": variaveis},
                timeout=self._tempo_limite,
            )
        except httpx.TimeoutException as erro:
            raise ErroDeFonte(
                f"O Linear não respondeu a tempo ({type(erro).__name__}). O "
                "diário deste dia nasce sem ele; rode o comando de novo com a "
                "rede estável para regenerar a nota."
            ) from erro
        except httpx.HTTPError as erro:
            raise ErroDeFonte(
                f"Falha de rede ao falar com o Linear ({self._endpoint}): "
                f"{type(erro).__name__}: {erro}. Confira a conexão e gere o "
                "diário de novo — a nota é sempre regenerada."
            ) from erro

        if resposta.status_code != httpx.codes.OK:
            raise _erro_de_http(resposta)

        try:
            corpo = resposta.json()
        except (json.JSONDecodeError, ValueError) as erro:
            raise ErroDeFonte(
                f"O Linear respondeu HTTP {resposta.status_code} mas o corpo não "
                f"é JSON: {erro}. Gere o diário de novo; se repetir, é problema "
                "do lado do Linear."
            ) from erro

        if not isinstance(corpo, dict):
            raise ErroDeFonte(
                "O Linear devolveu um corpo JSON que não é um objeto. Gere o "
                "diário de novo; se repetir, é problema do lado do Linear."
            )
        if corpo.get("errors"):
            raise _erro_de_graphql(corpo["errors"])

        dados = corpo.get("data")
        if not isinstance(dados, dict):
            raise ErroDeFonte(
                "O Linear respondeu sem 'data' e sem 'errors' — não dá para "
                "saber o que aconteceu. Gere o diário de novo; se repetir, é "
                "problema do lado do Linear."
            )
        return dados


def de_configuracao(configuracao: Configuracao, **extras: Any) -> FonteLinear:
    """Monta o coletor a partir da configuração local — o atalho da CLI."""
    return FonteLinear(configuracao.linear_api_key, **extras)


# -- Tradução para Evento ---------------------------------------------------


def _eventos_da_issue(issue: dict[str, Any], janela: Janela) -> Iterator[Evento]:
    """Traduz uma issue que andou na janela nos eventos que ela representa.

    Uma issue rende um evento por mudança de estado da janela e, quando foi
    aberta nela, um evento de criação. O evento genérico de "atualizada" é o
    último recurso: entra só quando nenhum dos outros saiu, para a issue que
    só mudou de responsável ou de título não sumir do diário — e para a que
    mudou de estado não aparecer duas vezes.
    """
    identificador = str(issue.get("identifier") or "").strip()
    titulo = str(issue.get("title") or "").strip()
    cabeca = " ".join(parte for parte in (identificador, titulo) if parte)
    if not cabeca:
        return

    referencia = _referencia_da_issue(issue)
    url = issue.get("url") or None
    rendeu = False

    for mudanca in _mudancas_de_estado(issue, janela):
        rendeu = True
        yield Evento(
            fonte="linear",
            momento=mudanca.momento,
            titulo=f"{cabeca} — {mudanca.descricao}",
            referencia=referencia,
            url=url,
            pessoas=mudanca.pessoas,
        )

    criada = _momento_local(issue.get("createdAt"))
    if criada is not None and janela.contem(criada):
        rendeu = True
        yield Evento(
            fonte="linear",
            momento=criada,
            titulo=f"{cabeca} — criada",
            referencia=referencia,
            url=url,
            pessoas=_pessoas(issue.get("creator"), issue.get("assignee")),
        )

    if rendeu:
        return

    atualizada = _momento_local(issue.get("updatedAt"))
    if atualizada is None or not janela.contem(atualizada):
        return
    estado = _nome_de(issue.get("state"))
    sufixo = f" (em {estado})" if estado else ""
    yield Evento(
        fonte="linear",
        momento=atualizada,
        titulo=f"{cabeca} — atualizada{sufixo}",
        referencia=referencia,
        url=url,
        pessoas=_pessoas(issue.get("assignee")),
    )


@dataclass(frozen=True)
class _MudancaDeEstado:
    """Uma passagem de estado na trilha de atividade de uma issue."""

    momento: datetime
    descricao: str
    pessoas: tuple[str, ...]


def _mudancas_de_estado(
    issue: dict[str, Any], janela: Janela
) -> Iterator[_MudancaDeEstado]:
    """As mudanças de estado da trilha de atividade que caem na janela.

    O `history` do Linear não aceita filtro de data, então o recorte é feito
    aqui — e é ele que garante o que o contrato exige: nenhum evento fora da
    janela, nem quando o diário é de uma data passada.
    """
    historico = (issue.get("history") or {}).get("nodes") or []
    for entrada in historico:
        if not isinstance(entrada, dict):
            continue
        destino = _nome_de(entrada.get("toState"))
        if not destino:
            continue
        momento = _momento_local(entrada.get("createdAt"))
        if momento is None or not janela.contem(momento):
            continue
        origem = _nome_de(entrada.get("fromState"))
        descricao = (
            f"movida de {origem} para {destino}" if origem else f"movida para {destino}"
        )
        yield _MudancaDeEstado(momento, descricao, _pessoas(entrada.get("actor")))


def _evento_do_comentario(comentario: dict[str, Any], janela: Janela) -> Evento | None:
    """Traduz um comentário — de issue ou de projeto — num evento do dia."""
    momento = _momento_local(comentario.get("createdAt"))
    if momento is None or not janela.contem(momento):
        return None

    autor = _nome_de(comentario.get("user"))
    issue = comentario.get("issue") or {}
    identificador = str(issue.get("identifier") or "").strip()
    titulo_da_issue = str(issue.get("title") or "").strip()
    onde = " ".join(parte for parte in (identificador, titulo_da_issue) if parte)
    if not onde:
        onde = _nome_de(comentario.get("project")) or "o Linear"

    assinatura = f"comentário de {autor}" if autor else "comentário"
    return Evento(
        fonte="linear",
        momento=momento,
        titulo=f"{onde} — {assinatura}",
        detalhe=str(comentario.get("body") or "").strip(),
        referencia=_referencia_do_comentario(comentario),
        url=comentario.get("url") or issue.get("url") or None,
        pessoas=_pessoas(comentario.get("user")),
    )


def _referencia_da_issue(issue: dict[str, Any]) -> str | None:
    """Onde a issue aconteceu: o projeto quando houver, senão o time.

    O projeto é o agrupamento mais informativo na nota — "review do OMS" diz
    mais que "Plataforma" —, mas nem toda issue tem um.
    """
    return _nome_de(issue.get("project")) or _nome_de(issue.get("team")) or None


def _referencia_do_comentario(comentario: dict[str, Any]) -> str | None:
    issue = comentario.get("issue") or {}
    if issue:
        return _referencia_da_issue(issue)
    return _nome_de(comentario.get("project")) or None


def _nome_de(entidade: Any) -> str:
    if isinstance(entidade, dict):
        return str(entidade.get("name") or "").strip()
    return ""


def _pessoas(*entidades: Any) -> tuple[str, ...]:
    """Os nomes distintos das pessoas envolvidas, na ordem em que apareceram."""
    nomes: list[str] = []
    for entidade in entidades:
        nome = _nome_de(entidade)
        if nome and nome not in nomes:
            nomes.append(nome)
    return tuple(nomes)


def _momento_local(bruto: Any) -> datetime | None:
    """Converte o instante ISO 8601 da API para o fuso local, sempre aware.

    O Linear devolve UTC com sufixo `Z`; o contrato exige `momento` aware no
    fuso local, porque é dele que saem o agrupamento por dia e o `HH:MM` da
    nota.
    """
    if not isinstance(bruto, str) or not bruto.strip():
        return None
    try:
        instante = datetime.fromisoformat(bruto.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone()


def _instante_para_a_api(momento: datetime) -> str:
    """O limite da janela como o filtro do Linear espera: ISO 8601 em UTC."""
    return momento.astimezone(UTC).isoformat().replace("+00:00", "Z")


# -- Erros ------------------------------------------------------------------


def _erro_de_http(resposta: httpx.Response) -> ErroDeFonte:
    """Traduz o status HTTP numa mensagem que diga o que fazer.

    Chave recusada, cota estourada e serviço fora do ar são problemas
    diferentes: esta mensagem vai literal para o aviso da nota do diário, e é
    ela que o usuário lê para saber se precisa mexer na configuração ou só
    esperar.
    """
    codigo = resposta.status_code
    conselhos = {
        400: (
            "O Linear recusou a consulta. Se a chave foi criada restrita a "
            "times, confira se ela ainda enxerga os times que você acompanha."
        ),
        401: (
            "Chave do Linear inválida ou revogada. Gere outra em Settings → "
            "Account → Security & Access com a permissão Read e atualize "
            "[linear].api_key no config.toml."
        ),
        403: (
            "A chave do Linear não tem permissão de leitura para o que o diário "
            "pede. Confira em Settings → Account → Security & Access se ela tem "
            "Read e se os times certos estão marcados."
        ),
        429: (
            "O Linear limitou a taxa de requisições (o teto é 2.500 por hora). "
            "Espere alguns minutos e gere o diário de novo."
        ),
    }
    conselho = conselhos.get(codigo)
    if conselho is None:
        if codigo >= 500:
            conselho = (
                "O Linear está fora do ar ou instável. Gere o diário deste dia "
                "de novo mais tarde — a nota é sempre regenerada."
            )
        else:
            conselho = (
                "O Linear recusou a requisição. Confira [linear].api_key no "
                "config.toml e gere o diário de novo."
            )
    return ErroDeFonte(f"Linear respondeu HTTP {codigo}: {conselho}{_detalhe(resposta)}")


def _erro_de_graphql(erros: Any) -> ErroDeFonte:
    """O 200 que traz `errors` — como o Linear reporta erro de consulta."""
    mensagens = []
    if isinstance(erros, list):
        for erro in erros:
            if isinstance(erro, dict) and erro.get("message"):
                mensagens.append(str(erro["message"]))
    resumo = "; ".join(mensagens) or "sem mensagem"
    return ErroDeFonte(
        f"O Linear recusou a consulta do diário: {resumo}. Confira se "
        "[linear].api_key ainda é válida e tem a permissão Read; se a mensagem "
        "falar de campo desconhecido, a API mudou e o coletor precisa de ajuste."
    )


def _detalhe(resposta: httpx.Response) -> str:
    """As mensagens que o Linear manda junto do status, quando manda."""
    try:
        corpo = resposta.json()
    except (json.JSONDecodeError, ValueError):
        texto = (resposta.text or "").strip()
        return f" Resposta: {texto[:200]}" if texto else ""
    if isinstance(corpo, dict) and isinstance(corpo.get("errors"), list):
        mensagens = [
            str(erro["message"])
            for erro in corpo["errors"]
            if isinstance(erro, dict) and erro.get("message")
        ]
        if mensagens:
            return f" ({'; '.join(mensagens)})"
    return ""
