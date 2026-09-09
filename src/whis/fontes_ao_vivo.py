"""git, Linear e Slack como ferramentas do agente, pelos coletores que já existem.

Quando o vault não tem a resposta — ou quando a pergunta é sobre agora —, o
modelo pode consultar as fontes ao vivo. Não há caminho novo até as APIs: cada
ferramenta chama o mesmo coletor que a daily e o diário chamam, construído
pela mesma fábrica `de_configuracao`. É isso que faz a blocklist do Slack, o
`so_com_mencao` e o filtro de exclusão continuarem valendo numa consulta ao
vivo sem ninguém precisar lembrar deles: um atalho que falasse com a Web API
direto quebraria a blocklist em silêncio.

O filtro de exclusão age aqui num ponto só, como em `coleta.coletar`. Uma
fonte que falha vira texto para o modelo ("responda com o vault"), não exceção
que derruba a pergunta. Cada evento sai com uma origem própria
(`linear:FN-1610`, `slack:#canal`, `git:repositorio@hash`) para a citação
dizer que aquilo não veio do vault.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool

from .ferramentas import _casa, _normalizar
from .fontes import ErroDeFonte, Evento, Janela, PortaFonte, filtrar

_log = logging.getLogger("whis.fontes_ao_vivo")

#: O nome do servidor MCP em processo das fontes ao vivo.
NOME_DO_SERVIDOR = "fontes"

#: Quantas horas para trás uma consulta olha quando o modelo não diz.
HORAS_PADRAO = 24

#: Duas semanas: mais que isso é pergunta para o vault, não para a API.
HORAS_MAXIMAS = 24 * 14

#: Quantos eventos uma consulta devolve, no máximo, quando o modelo não diz.
LIMITE_PADRAO = 40

_HASH_DO_COMMIT = re.compile(r"`([0-9a-f]{7,40})`")
_IDENTIFICADOR_DE_ISSUE = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")

_DESCRICOES = {
    "git": "Os commits do usuário nas últimas horas, direto dos repositórios locais.",
    "linear": "Issues criadas, movidas e comentadas nas últimas horas, direto do Linear.",
    "slack": "Mensagens das últimas horas, direto do Slack, nas conversas que ele lê.",
}


class FontesAoVivo:
    """As fontes ligadas como tools do SDK: uma `consultar_<fonte>` por coletor.

    `fontes` são os coletores já construídos pelas fábricas; fonte desligada
    simplesmente não está na lista, e por isso não vira ferramenta. `relogio`
    é injetado porque a janela "últimas N horas" é comportamento, e o teste
    precisa fixar o agora.
    """

    def __init__(
        self,
        fontes: Sequence[PortaFonte],
        *,
        excluir: Sequence[str] = (),
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self.fontes = tuple(fontes)
        self.excluir = tuple(excluir)
        self._relogio = relogio or (lambda: datetime.now().astimezone())
        self.chamadas = 0

    def tools(self) -> list[SdkMcpTool[Any]]:
        return [self._tool_de(fonte) for fonte in self.fontes]

    def servidor(self) -> McpSdkServerConfig | None:
        if not self.fontes:
            return None
        return create_sdk_mcp_server(NOME_DO_SERVIDOR, tools=self.tools())

    def nomes_permitidos(self) -> list[str]:
        """Os nomes com que o Claude Code enxerga estas ferramentas."""
        return [f"mcp__{NOME_DO_SERVIDOR}__{nome_da_ferramenta(fonte.nome)}" for fonte in self.fontes]

    def consultar(
        self,
        fonte: PortaFonte,
        *,
        horas: int = HORAS_PADRAO,
        termo: str = "",
        limite: int = LIMITE_PADRAO,
    ) -> tuple[str, bool]:
        """Lê a fonte nas últimas `horas` e devolve `(texto, deu_erro)`."""
        horas = min(max(int(horas), 1), HORAS_MAXIMAS)
        limite = max(int(limite), 1)
        agora = self._relogio()
        janela = Janela(data=agora.date(), inicio=agora - timedelta(hours=horas), fim=agora)
        try:
            colhidos = tuple(fonte.coletar(janela))
        except ErroDeFonte as erro:
            _log.error("Fonte ao vivo '%s' não pôde ser lida: %s", fonte.nome, erro)
            return (
                f"A fonte {fonte.nome} não pôde ser lida agora: {erro} "
                f"Responda com o que o vault tem.",
                True,
            )

        eventos, excluidos = filtrar(colhidos, self.excluir)
        palavras = _normalizar(termo).split()
        if palavras:
            eventos = tuple(evento for evento in eventos if _casa(palavras, _alvo(evento)))
        recentes = sorted(eventos, key=lambda evento: evento.momento, reverse=True)[:limite]
        _log.info(
            "Fonte ao vivo '%s': %d evento(s) nas últimas %dh, %d removido(s) pelo filtro "
            "de exclusão, %d devolvido(s) ao modelo%s.",
            fonte.nome,
            len(colhidos),
            horas,
            excluidos,
            len(recentes),
            f" com o termo {termo!r}" if palavras else "",
        )

        periodo = f"nas últimas {horas}h ({janela.inicio:%d/%m %H:%M} → {janela.fim:%d/%m %H:%M})"
        filtro = f" com {termo.strip()!r}" if palavras else ""
        if not recentes:
            return f"Nada no {fonte.nome} {periodo}{filtro}.", False
        cabeca = f"{len(recentes)} evento(s) do {fonte.nome} {periodo}{filtro}, mais recente primeiro:"
        if len(eventos) > len(recentes):
            cabeca += f" (de {len(eventos)}; peça um termo ou menos horas para ver o resto)"
        linhas = [cabeca]
        for evento in recentes:
            linhas.extend(_linhas_do_evento(evento))
        return "\n".join(linhas), False

    def _tool_de(self, fonte: PortaFonte) -> SdkMcpTool[Any]:
        @tool(
            nome_da_ferramenta(fonte.nome),
            _DESCRICOES.get(fonte.nome, f"O que aconteceu no {fonte.nome} nas últimas horas.")
            + " Cada linha traz a origem para citar. Custa chamadas de API: procure no "
            "vault antes.",
            {
                "type": "object",
                "properties": {
                    "horas": {
                        "type": "integer",
                        "description": f"quantas horas para trás (padrão {HORAS_PADRAO}, máximo {HORAS_MAXIMAS})",
                    },
                    "termo": {
                        "type": "string",
                        "description": "só eventos com todas estas palavras (sem acento nem maiúsculas)",
                    },
                    "limite": {
                        "type": "integer",
                        "description": f"quantos eventos devolver, no máximo (padrão {LIMITE_PADRAO})",
                    },
                },
                "required": [],
            },
        )
        async def consultar(args: dict[str, Any]) -> dict[str, Any]:
            self.chamadas += 1
            texto, erro = self.consultar(
                fonte,
                horas=args.get("horas") or HORAS_PADRAO,
                termo=str(args.get("termo") or ""),
                limite=args.get("limite") or LIMITE_PADRAO,
            )
            resultado: dict[str, Any] = {"content": [{"type": "text", "text": texto}]}
            if erro:
                resultado["is_error"] = True
            return resultado

        return consultar


def nome_da_ferramenta(fonte: str) -> str:
    return f"consultar_{fonte}"


def origem_do_evento(evento: Evento) -> str:
    """A origem que o modelo copia para a citação: nunca um caminho do vault."""
    referencia = (evento.referencia or "").strip()
    if evento.fonte == "git":
        casamento = _HASH_DO_COMMIT.search(evento.titulo)
        hash_do_commit = casamento.group(1) if casamento else ""
        if hash_do_commit and referencia:
            return f"git:{referencia}@{hash_do_commit}"
        return f"git:{hash_do_commit or referencia or 'commit'}"
    if evento.fonte == "linear":
        identificador = _IDENTIFICADOR_DE_ISSUE.search(evento.titulo)
        if identificador:
            return f"linear:{identificador.group(1)}"
        return f"linear:{referencia or 'issue'}"
    return f"{evento.fonte}:{referencia or 'conversa'}"


def _linhas_do_evento(evento: Evento) -> list[str]:
    linhas = [f"- {origem_do_evento(evento)}  {evento.momento:%d/%m %H:%M}  {evento.titulo}".rstrip()]
    linhas.extend(
        f"    {trecho.strip()}" for trecho in evento.detalhe.splitlines() if trecho.strip()
    )
    if evento.pessoas:
        linhas.append(f"    pessoas: {', '.join(evento.pessoas)}")
    if evento.url:
        linhas.append(f"    link: {evento.url}")
    return linhas


def _alvo(evento: Evento) -> str:
    return "\n".join([evento.titulo, evento.detalhe, evento.referencia or "", *evento.pessoas])
