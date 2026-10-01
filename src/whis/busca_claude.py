"""Adaptador real da busca: o Claude da conta do usuário com as ferramentas do vault.

Irmão de `resumo_dia_claude`, com uma diferença de forma: lá é um turno só,
sem ferramenta nenhuma; aqui o modelo **decide onde olhar**, chamando
`buscar_no_vault`, `ler_nota` e `listar` quantas vezes precisar. A postura é
a mesma — Claude Agent SDK, credenciais do `claude` CLI (a conta Pro/Max do
usuário por OAuth, como manda o ADR 0001), recusa de API key paga, custo no
log.

O modelo **não recebe shell, nem leitura de arquivo, nem o vault cru**. As
três ferramentas da camada 01 entram como um servidor MCP em processo, e é por
isso que a pasta privada continua privada aqui: cada chamada passa por
`Ferramentas`, onde a fronteira mora. Um caminho recusado chega ao modelo como
"não existe" — nunca como "é privado".

A resposta vem em JSON com as citações; texto sem objeto JSON é `ErroDeBusca`,
com o texto cru no log, porque uma afirmação sem arquivo ao lado é
indistinguível de invenção.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    McpSdkServerConfig,
    ResultMessage,
    SdkMcpTool,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from . import fontes_ao_vivo as _ao_vivo
from .busca import Citacao, ErroDeBusca, Resposta
from .conversa import AGENTE, Turno
from .ferramentas import Ferramentas, ForaDaFronteira, LimiteDeNotas
from .fontes_ao_vivo import FontesAoVivo
from .claude_cli import VARIAVEIS_DE_API_PAGA, registrar_stderr_do_cli

_log = logging.getLogger("whis.busca")

#: Modelo usado na chamada. `None` = o padrão da conta/CLI do usuário, pelo
#: mesmo motivo dos outros adaptadores: fixar um id aqui arriscaria pedir um
#: modelo fora do plano. Quem quiser fixar preenche `[claude] modelo`.
MODELO_PADRAO: str | None = None

#: Teto de tempo para a pergunta inteira, ferramentas incluídas, em segundos.
TIMEOUT_PADRAO_S = 240.0

#: Cada chamada de ferramenta é um turno. É o freio de uma pergunta virar uma
#: sessão sem fim; o teto de notas de `Ferramentas` é o outro.
MAXIMO_DE_TURNOS = 40

#: Quantos turnos do fio vão junto da pergunta. O fio dura 24 horas e pode
#: ficar longo; o modelo precisa do assunto, não da transcrição inteira.
TURNOS_NO_FIO = 20

#: Quantos caracteres da resposta crua entram no log quando o parse falha.
_TRECHO_DE_DIAGNOSTICO = 600

#: O nome do servidor MCP em processo e, a partir dele, o nome que o Claude
#: Code dá a cada ferramenta (`mcp__<servidor>__<ferramenta>`).
NOME_DO_SERVIDOR = "vault"
BUSCAR = "buscar_no_vault"
LER = "ler_nota"
LISTAR = "listar"
NOMES_DAS_FERRAMENTAS = (BUSCAR, LER, LISTAR)

PROMPT_DA_BUSCA = """\
Você é o Whis: o assistente pessoal de um desenvolvedor, com o nome e o jeito do Whis \
de Dragon Ball — sereno, econômico, sem firula. Você responde às perguntas dele sobre \
o próprio trabalho a partir do vault Obsidian em que ele guarda memória. Ele pergunta \
por uma palheta no PC, no meio do trabalho, e lê a resposta de relance: informação \
primeiro, economia de palavras sempre. Só fique mais solto se ele começar a brincar \
com você — e mesmo assim, curto.

O vault, e o que cada pasta guarda:
- `daily/AAAA-MM-DD.md`: o roteiro que ele leu na daily do time, e embaixo as listas \
cruas de tudo que aconteceu desde a daily anterior — commits do git, movimentação no \
Linear, mensagens do Slack, com hora. É o registro mais completo do que aconteceu.
- `diario/AAAA-MM-DD.md`: a narrativa de um dia civil, com destaques, pendências e as \
mesmas listas cruas.
- `reunioes/AAAA-MM-DD-HHMM-titulo.md`: a nota de uma reunião.
- `transcricoes/AAAA-MM-DD-HHMM-titulo.md`: a transcrição integral da mesma reunião. \
Abra quando a nota da reunião não tiver o detalhe.
- `notas/`: o que ele escreve à mão.

Suas ferramentas, e só elas:
- `buscar_no_vault(termo)`: as linhas do vault em que TODAS as palavras do termo \
aparecem, sem diferenciar acento nem maiúsculas. Use termos curtos, de uma a três \
palavras, e tente variações: um identificador (FN-1610, #1636), um nome de pessoa, um \
nome de repositório, um sinônimo. Um termo longo demais não acha nada.
- `ler_nota(caminho)`: a nota inteira. Abra a nota de um achado promissor para ler o \
contexto em volta: a linha sozinha engana.
- `listar(pasta)`: o que existe numa pasta, para descobrir as datas disponíveis.

Como trabalhar:
1. Busque ANTES de responder, sempre. Você não sabe nada sobre o trabalho dele além do \
que está no vault.
2. Abra as notas dos achados que importam, mais recentes primeiro.
3. Se não achou, tente outros termos antes de desistir — duas ou três variações.
4. Um caminho que "não existe" não existe. Não insista nele e não especule que algo \
esteja escondido.
5. A conversa até aqui, quando vier, serve para entender a pergunta de agora: "e quem \
levantou isso?" se refere ao assunto da pergunta anterior.

Responda com um único objeto JSON, sem nenhum texto antes ou depois e sem cercas de \
código, exatamente neste formato:

{"resposta": "a resposta, em português do Brasil",
 "citacoes": [{"origem": "diario/2026-09-03.md", "trecho": "a frase da nota que sustenta"}],
 "achou": true}

Regras da resposta:
- Em português do Brasil. Preserve o jargão técnico em inglês como aparece nas notas \
(deploy, review, merge, PR, issue, branch, staging).
- Teto do campo "resposta": no máximo TRÊS frases ou 400 caracteres, o que vier \
primeiro. Passe disso só se ele pedir detalhe explicitamente ("detalha", "explica \
melhor", "me conta tudo"). Responda como um colega responderia no corredor: "da última \
vez o João pediu 120 dias, então está assim" — e não "de acordo com o histórico do \
git em 25/08 ficou decidido que...".
- O campo "resposta" NÃO traz lista de fontes, bloco "Fontes" nem caminho de nota. As \
fontes vão SÓ em "citacoes"; ele as vê quando pede ("de onde?", "qual nota?") — aí, e \
só aí, responda com o caminho e o trecho no próprio texto.
- Cada afirmação precisa de uma citação em "citacoes". `origem` é o caminho relativo \
EXATO de uma nota que você abriu ou que a busca devolveu; `trecho` é uma frase copiada \
dela. Nunca cite um caminho que você não viu.
- Diga quem disse ou fez e quando, quando isso couber na frase: "na reunião de 03/09, o \
Luan...".
- Se não achou, diga isso com "achou": false, citações vazias e uma resposta do tipo \
"Não achei nada sobre X no vault", dizendo o que você procurou. NUNCA complete com \
conhecimento geral, dedução ou suposição: uma resposta inventada é pior do que "não \
achei". Se achou só parte, diga o que achou e o que ficou faltando.
- Não repita a lista crua inteira: responda à pergunta.\
"""

PROMPT_DAS_FONTES_AO_VIVO = """\
Além do vault, você tem ferramentas que consultam as fontes AO VIVO — as que \
estiverem disponíveis entre `consultar_git`, `consultar_linear` e `consultar_slack`. \
Elas leem o que aconteceu nas últimas N horas direto do git, do Linear e do Slack.

- Use-as só DEPOIS de procurar no vault: quando ele não tiver a resposta, ou quando a \
pergunta for sobre agora ("o que aconteceu hoje", "há dez minutos", "a última mensagem \
da Ana"). A nota é gratuita; a API não, e uma consulta pode virar várias chamadas.
- Peça poucas horas e passe um `termo` quando souber o que procura. Sem termo, uma fonte \
pode devolver centenas de eventos.
- Cite o que veio delas com a origem que cada linha mostra (`linear:FN-1610`, \
`slack:#dev-codereview`, `git:whis@a1b2c3d`), e nunca com um caminho de nota: é \
assim que ele sabe que aquilo não veio do vault. Quando a linha trouxer `link:`, inclua-o \
na resposta em markdown com rótulo curto.
- Uma fonte que "não pôde ser lida agora" não é motivo para inventar: diga que ela não \
respondeu e responda com o vault.\
"""


class FerramentasDoVault:
    """As três ferramentas da camada 01 como tools do SDK, para uma pergunta.

    Traduz cada recusa para o modelo: `ForaDaFronteira` vira "não existe"
    (a própria mensagem da exceção, que já é essa), e `LimiteDeNotas` vira
    "responda com o que já leu". Conta as chamadas para o log e guarda os
    caminhos que o modelo viu, para a citação a um caminho nunca visto ser
    apontada no log.
    """

    def __init__(self, ferramentas: Ferramentas) -> None:
        self._ferramentas = ferramentas
        self.chamadas = 0
        self.vistos: set[str] = set()

    def tools(self) -> list[SdkMcpTool[Any]]:
        ferramentas = self._ferramentas

        @tool(
            BUSCAR,
            "Acha as linhas do vault em que todas as palavras do termo aparecem, "
            "sem diferenciar acento nem maiúsculas. Termos curtos acham mais.",
            {
                "type": "object",
                "properties": {
                    "termo": {"type": "string", "description": "uma a três palavras"},
                    "limite": {
                        "type": "integer",
                        "description": "quantas linhas devolver, no máximo (padrão 30)",
                    },
                },
                "required": ["termo"],
            },
        )
        async def buscar(args: dict[str, Any]) -> dict[str, Any]:
            self.chamadas += 1
            termo = str(args.get("termo", ""))
            limite = int(args.get("limite") or 30)
            achados = ferramentas.buscar_no_vault(termo, limite=max(1, limite))
            self.vistos.update(achado.caminho for achado in achados)
            return _texto(_achados_como_texto(termo, achados))

        @tool(
            LER,
            "Devolve uma nota inteira do vault, pelo caminho relativo que a busca "
            "ou a listagem mostraram.",
            {
                "type": "object",
                "properties": {
                    "caminho": {"type": "string", "description": "ex.: diario/2026-09-03.md"}
                },
                "required": ["caminho"],
            },
        )
        async def ler(args: dict[str, Any]) -> dict[str, Any]:
            self.chamadas += 1
            caminho = str(args.get("caminho", ""))
            try:
                conteudo = ferramentas.ler_nota(caminho)
            except (ForaDaFronteira, LimiteDeNotas) as recusa:
                return _texto(str(recusa), erro=True)
            self.vistos.add(_relativo(caminho))
            return _texto(f"[{_relativo(caminho)}]\n{conteudo}")

        @tool(
            LISTAR,
            "Lista o que existe numa pasta do vault (subpastas terminam com /). "
            "Sem argumento, lista a raiz.",
            {
                "type": "object",
                "properties": {
                    "pasta": {"type": "string", "description": "ex.: daily — vazio é a raiz"}
                },
                "required": [],
            },
        )
        async def listar(args: dict[str, Any]) -> dict[str, Any]:
            self.chamadas += 1
            pasta = str(args.get("pasta") or "")
            try:
                entradas = ferramentas.listar(pasta)
            except ForaDaFronteira as recusa:
                return _texto(str(recusa), erro=True)
            self.vistos.update(entrada for entrada in entradas if not entrada.endswith("/"))
            return _texto("\n".join(entradas) or "(pasta vazia)")

        return [buscar, ler, listar]

    def servidor(self) -> McpSdkServerConfig:
        return create_sdk_mcp_server(NOME_DO_SERVIDOR, tools=self.tools())


def ferramentas_permitidas() -> list[str]:
    """Os nomes com que o Claude Code enxerga as ferramentas do servidor."""
    return [f"mcp__{NOME_DO_SERVIDOR}__{nome}" for nome in NOMES_DAS_FERRAMENTAS]


class BuscaClaude:
    """A porta de busca pelo Claude da conta do usuário.

    Levanta `ErroDeBusca` em qualquer falha — sem credencial, API key paga no
    ambiente, tempo esgotado, o SDK reclamando ou resposta que não vira
    `Resposta`. "Não achei" não é falha: volta como `Resposta(achou=False)`.
    """

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_PADRAO,
        timeout_s: float = TIMEOUT_PADRAO_S,
        maximo_de_turnos: int = MAXIMO_DE_TURNOS,
        fontes_ao_vivo: FontesAoVivo | None = None,
    ) -> None:
        self.modelo = modelo or None
        self.timeout_s = timeout_s
        self.maximo_de_turnos = maximo_de_turnos
        # Entra pelo construtor, e não pela porta: `PortaBusca.perguntar` é a
        # mesma para todo adaptador, e quais fontes estão ligadas é
        # configuração desta máquina, como o modelo.
        self.fontes_ao_vivo = fontes_ao_vivo

    def perguntar(
        self,
        pergunta: str,
        ferramentas: Ferramentas,
        historico: tuple[Turno, ...] = (),
    ) -> Resposta:
        verificar_credencial()
        prompt = montar_pergunta(pergunta, historico)
        _log.info(
            "Perguntando ao Claude (%d turnos de contexto, modelo: %s)...",
            len(historico),
            self.modelo or "padrão da conta",
        )
        bruto, resultado = self._conversar(prompt, ferramentas)
        resposta = interpretar_resposta(bruto)
        custo = resultado.total_cost_usd if resultado is not None else None
        return replace(resposta, custo_usd=custo)

    def _conversar(
        self, prompt: str, ferramentas: Ferramentas
    ) -> tuple[str, ResultMessage | None]:
        """Faz a chamada e devolve o texto cru da resposta e o resultado.

        É o único ponto que toca a rede: os testes sem rede substituem este
        método e exercitam todo o resto do caminho.
        """
        vault = FerramentasDoVault(ferramentas)
        fontes = self.fontes_ao_vivo
        try:
            return asyncio.run(
                asyncio.wait_for(
                    _conversar_async(
                        prompt,
                        vault,
                        fontes,
                        modelo=self.modelo,
                        maximo_de_turnos=self.maximo_de_turnos,
                    ),
                    timeout=self.timeout_s,
                )
            )
        except TimeoutError as erro:
            raise ErroDeBusca(
                f"O Claude não respondeu em {self.timeout_s:.0f}s "
                f"({_chamadas(vault, fontes)} chamada(s) de ferramenta até aqui)."
            ) from erro
        except ClaudeSDKError as erro:
            raise ErroDeBusca(
                f"Falha ao falar com o Claude ({type(erro).__name__}): {erro}"
            ) from erro


def verificar_credencial() -> None:
    """Recusa a chamada se o ambiente puder cobrar por API key paga.

    Mesma razão dos outros adaptadores: o atendente fica no ar o dia inteiro,
    e cair numa API key em silêncio viraria despesa recorrente que o usuário
    não pediu.
    """
    presentes = [nome for nome in VARIAVEIS_DE_API_PAGA if os.environ.get(nome)]
    if not presentes:
        return
    raise ErroDeBusca(
        f"A busca usa a conta Claude do usuário (OAuth), nunca uma API key paga, "
        f"mas {' e '.join(presentes)} está no ambiente e o Claude cobraria por ela. "
        f"Remova a variável e entre com `claude login`."
    )


def montar_pergunta(pergunta: str, historico: Sequence[Turno] = ()) -> str:
    """O turno do usuário: o fio recente, quando houver, e a pergunta de agora.

    O fio vai como texto, não como sessão retomada do SDK: é o que mantém a
    expiração de 24 horas no nosso código, e não em arquivo de sessão que
    ninguém controla.
    """
    linhas: list[str] = []
    recentes = list(historico)[-TURNOS_NO_FIO:]
    if recentes:
        linhas.append("Conversa até aqui, da mais antiga para a mais recente:")
        linhas.append("")
        for turno in recentes:
            quem = "agente" if turno.quem == AGENTE else "usuário"
            linhas.append(f"[{quem}] {turno.texto.strip()}")
        linhas.append("")
    linhas.append("Pergunta de agora:")
    linhas.append("")
    linhas.append(pergunta.strip())
    return "\n".join(linhas) + "\n"


def interpretar_resposta(bruto: str) -> Resposta:
    """Traduz a resposta do Claude em `Resposta`, ou levanta `ErroDeBusca`.

    Cerca de código e frase em volta do JSON são aceitas. O que não é aceito
    é resposta sem objeto JSON ou sem nenhum dos três campos: sem o formato
    não há citação, e sem citação não há como o usuário conferir.
    """
    dados = _extrair_objeto(bruto)
    if not any(chave in dados for chave in ("resposta", "citacoes", "achou")):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeBusca(
            "O Claude devolveu um JSON sem 'resposta', 'citacoes' nem 'achou' — "
            f"resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )
    texto = _texto_do_item(dados.get("resposta"))
    citacoes = _citacoes(dados.get("citacoes"))
    achou = dados.get("achou")
    if not isinstance(achou, bool):
        achou = bool(citacoes)
    if achou and not citacoes:
        _log.warning(
            "Resposta sem citação nenhuma — suspeita, mas não inventamos citação: %r",
            _trecho(texto),
        )
    if not achou and not texto:
        texto = ""
    return Resposta(texto=texto, citacoes=citacoes, achou=achou)


def registrar_custo(resultado: ResultMessage | None, chamadas: int) -> None:
    """Deixa no log o peso desta pergunta na assinatura do usuário.

    Mesmo formato da entrega anterior: a conta é por assinatura, via OAuth, e
    o valor em dólar **não é uma cobrança** — é o equivalente da tabela da API,
    uma medida relativa de cota.
    """
    if resultado is None:
        return
    uso = resultado.usage or {}
    _log.info(
        "Pergunta ao Claude: equivalente a %s na tabela da API — a assinatura não "
        "cobra por token —, %s turno(s), %d chamada(s) de ferramenta, %s tokens de "
        "entrada (%s lidos de cache), %s de saída, em %s ms.",
        _dinheiro(resultado.total_cost_usd),
        resultado.num_turns,
        chamadas,
        uso.get("input_tokens", "?"),
        uso.get("cache_read_input_tokens", "?"),
        uso.get("output_tokens", "?"),
        resultado.duration_ms,
    )


def montar_opcoes(
    vault: FerramentasDoVault,
    fontes: FontesAoVivo | None,
    *,
    modelo: str | None,
    maximo_de_turnos: int,
) -> ClaudeAgentOptions:
    """As opções da chamada: o vault sempre, as fontes ao vivo quando ligadas.

    O adendo do prompt sobre as fontes só entra quando há fonte: um modelo
    instruído a usar uma ferramenta que não existe tende a fingir que usou.
    """
    servidores = {NOME_DO_SERVIDOR: vault.servidor()}
    permitidas = ferramentas_permitidas()
    sistema = PROMPT_DA_BUSCA
    servidor_das_fontes = fontes.servidor() if fontes is not None else None
    if fontes is not None and servidor_das_fontes is not None:
        servidores[_ao_vivo.NOME_DO_SERVIDOR] = servidor_das_fontes
        permitidas += fontes.nomes_permitidos()
        sistema += "\n\n" + PROMPT_DAS_FONTES_AO_VIVO
    return ClaudeAgentOptions(
        system_prompt=sistema,
        model=modelo,
        # Nenhuma ferramenta nativa: sem Bash, sem Read, sem Glob. O modelo só
        # enxerga o disco pelos servidores abaixo, que é onde a fronteira mora.
        tools=[],
        allowed_tools=permitidas,
        mcp_servers=servidores,
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        permission_mode="dontAsk",
        max_turns=maximo_de_turnos,
        stderr=registrar_stderr_do_cli,
    )


def _chamadas(vault: FerramentasDoVault, fontes: FontesAoVivo | None) -> int:
    return vault.chamadas + (fontes.chamadas if fontes is not None else 0)


async def _conversar_async(
    prompt: str,
    vault: FerramentasDoVault,
    fontes: FontesAoVivo | None,
    *,
    modelo: str | None,
    maximo_de_turnos: int,
) -> tuple[str, ResultMessage | None]:
    """Uma pergunta ao Claude com as ferramentas do vault e das fontes, e nada mais."""
    opcoes = montar_opcoes(vault, fontes, modelo=modelo, maximo_de_turnos=maximo_de_turnos)

    ultimo_texto = ""
    resultado: ResultMessage | None = None
    async for mensagem in query(prompt=prompt, options=opcoes):
        if isinstance(mensagem, AssistantMessage):
            texto = "\n".join(
                bloco.text for bloco in mensagem.content if isinstance(bloco, TextBlock)
            )
            if texto.strip():
                ultimo_texto = texto
            for bloco in mensagem.content:
                if isinstance(bloco, ToolUseBlock):
                    _log.debug("Ferramenta pedida: %s %s", bloco.name, bloco.input)
        elif isinstance(mensagem, ResultMessage):
            resultado = mensagem

    # Antes do `is_error`: um turno que terminou mal também consumiu.
    registrar_custo(resultado, _chamadas(vault, fontes))

    if resultado is not None and resultado.is_error:
        raise ErroDeBusca(
            f"O Claude terminou em erro ({resultado.subtype}): "
            f"{resultado.result or 'sem detalhe'}"
        )

    texto = resultado.result if resultado and resultado.result else ultimo_texto
    if not texto.strip():
        raise ErroDeBusca("O Claude respondeu vazio — nenhum texto para virar resposta.")
    return texto, resultado


def _achados_como_texto(termo: str, achados: Iterable) -> str:
    linhas = [f"{achado.caminho}:{achado.linha}: {achado.trecho}" for achado in achados]
    if not linhas:
        return (
            f"Nenhuma linha do vault tem todas as palavras de {termo!r}. Tente um termo "
            f"mais curto, outra grafia, ou um identificador (issue, PR, pessoa, repositório)."
        )
    return f"{len(linhas)} linha(s) com {termo!r}:\n" + "\n".join(linhas)


def _texto(conteudo: str, *, erro: bool = False) -> dict[str, Any]:
    resultado: dict[str, Any] = {"content": [{"type": "text", "text": conteudo}]}
    if erro:
        resultado["is_error"] = True
    return resultado


def _relativo(caminho: str) -> str:
    return caminho.strip().replace("\\", "/")


def _citacoes(valor: object) -> tuple[Citacao, ...]:
    if valor is None:
        return ()
    itens: Iterable[object] = valor if isinstance(valor, list) else [valor]
    citacoes: list[Citacao] = []
    for item in itens:
        if isinstance(item, str):
            origem, trecho = item.strip(), ""
        elif isinstance(item, dict):
            origem = _texto_do_item(
                item.get("origem") or item.get("arquivo") or item.get("caminho") or item.get("fonte")
            )
            trecho = _texto_do_item(item.get("trecho"))
        else:
            continue
        if origem:
            citacoes.append(Citacao(origem=_relativo(origem), trecho=trecho))
    return tuple(citacoes)


def _dinheiro(valor: float | None) -> str:
    return f"US$ {valor:.4f}" if isinstance(valor, (int, float)) else "não informado"


_NADA = object()


def _extrair_objeto(bruto: str) -> dict:
    """Acha e decodifica o objeto JSON dentro da resposta."""
    texto = _sem_cerca_de_codigo(bruto.strip())
    dados, falha = _decodificar(texto)

    inicio = texto.find("{")
    fim = texto.rfind("}")
    if dados is _NADA and inicio != -1 and fim > inicio:
        dados, falha = _decodificar(texto[inicio : fim + 1])

    if dados is _NADA:
        _registrar_resposta_ilegivel(bruto)
        if inicio == -1:
            raise ErroDeBusca(
                "O Claude não devolveu um objeto JSON — resposta crua no log. "
                f"Começo da resposta: {_trecho(bruto)!r}"
            )
        raise ErroDeBusca(
            f"O JSON da resposta veio malformado ({falha}) — resposta crua no log. "
            f"Começo da resposta: {_trecho(bruto)!r}"
        )

    if not isinstance(dados, dict):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeBusca(
            f"O JSON da resposta não é um objeto, e sim {type(dados).__name__} — "
            f"resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )
    return dados


def _decodificar(texto: str) -> tuple[object, str]:
    try:
        return json.loads(texto), ""
    except json.JSONDecodeError as erro:
        return _NADA, str(erro)


def _sem_cerca_de_codigo(texto: str) -> str:
    if not texto.startswith("```"):
        return texto
    sem_abertura = texto.split("\n", 1)[1] if "\n" in texto else ""
    fechamento = sem_abertura.rfind("```")
    return sem_abertura[:fechamento] if fechamento != -1 else sem_abertura


def _texto_do_item(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return " — ".join(
            parte for parte in (_texto_do_item(v) for v in item.values()) if parte
        )
    if isinstance(item, list):
        return "\n\n".join(parte for parte in (_texto_do_item(v) for v in item) if parte)
    if item is None or isinstance(item, bool):
        return ""
    return str(item).strip()


def _trecho(bruto: str) -> str:
    return bruto.strip()[:200]


def _registrar_resposta_ilegivel(bruto: str) -> None:
    _log.error(
        "Resposta do Claude que não virou resposta (primeiros %d caracteres):\n%s",
        _TRECHO_DE_DIAGNOSTICO,
        bruto.strip()[:_TRECHO_DE_DIAGNOSTICO],
    )
