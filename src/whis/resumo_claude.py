"""Adaptador real da porta de resumo: o Claude da conta do usuário.

Fala com o Claude pelo **Claude Agent SDK**, que reusa as credenciais do
`claude` CLI — ou seja, a conta Pro/Max do usuário por OAuth, como manda o
ADR 0001. Nunca por API key paga à parte: se uma chave de API estiver no
ambiente, o adaptador **recusa a chamada** em vez de gastar dinheiro do
usuário sem ele pedir.

A conversa é de um turno só, sem ferramenta nenhuma: mandamos a transcrição,
pedimos um JSON com decisões, ações/pendências e tópicos, e traduzimos esse
JSON para `Resumo`. Nada de agente com acesso ao disco — o adaptador desliga
as ferramentas embutidas, as skills e as configurações de arquivo do CLI para
que o resumo dependa só da transcrição.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    query,
)

from .portas import ErroDeResumo, Resumo, Transcricao

_log = logging.getLogger("whis.resumo")

#: Variáveis de ambiente que fariam o Claude cobrar por fora da conta do usuário.
VARIAVEIS_DE_API_PAGA = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def registrar_stderr_do_cli(linha: str) -> None:
    """O stderr do CLI do Claude vai ao log, em vez de ser herdado do pai.

    Sem este callback o SDK deixa o filho herdar o stderr do processo — e sob
    `pythonw.exe` não há stderr: o Python entrega ao filho um pipe com a ponta
    de leitura fechada, e um processo Node que escreva uma linha ali morre com
    EPIPE no meio da pergunta (provado com `node -e` sob `pythonw`, ticket 13).
    Com o callback, o SDK abre um pipe de verdade e lê o que vier.
    """
    _log.debug("claude: %s", linha.rstrip())

#: Modelo usado na chamada. `None` = o padrão da conta/CLI do usuário.
#:
#: Fica em `None` de propósito: o coletor roda na máquina do usuário, contra a
#: assinatura dele, e o CLI já escolhe um modelo que aquela conta pode usar.
#: Fixar um id aqui arriscaria pedir um modelo fora do plano na máquina de
#: destino. Quem quiser fixar preenche `[claude] modelo` na configuração.
MODELO_PADRAO: str | None = None

#: Acima disso a transcrição não é enviada — ver `Transcrição longa` no módulo.
LIMITE_DE_CARACTERES = 400_000

#: Teto de tempo para a chamada inteira, em segundos.
TIMEOUT_PADRAO_S = 300.0

#: Quantos caracteres da resposta crua entram no log/erro quando o parse falha.
_TRECHO_DE_DIAGNOSTICO = 600

PROMPT_DO_SISTEMA = """\
Você resume reuniões de trabalho a partir da transcrição.

A transcrição vem de uma reunião em português do Brasil e distingue dois lados: \
"eu" é o usuário, gravado pelo microfone, e "outros" são os demais participantes, \
gravados pelo áudio do sistema. Quando os nomes reais das pessoas aparecerem na \
conversa, use-os.

Escreva tudo em português do Brasil. A conversa mistura português com termos \
técnicos em inglês: preserve esses termos exatamente como foram ditos (deploy, \
rollback, review, sprint, issue, daily). Nunca os traduza.

Responda com um único objeto JSON, sem nenhum texto antes ou depois e sem cercas \
de código, exatamente neste formato:

{"titulo": "título curto da reunião, ou null",
 "participantes": ["nomes reais de pessoas ditos na conversa"],
 "decisoes": ["o que ficou decidido"],
 "acoes": ["o que alguém ficou de fazer, com o responsável quando der para saber"],
 "topicos": ["assuntos discutidos"]}

Regras do conteúdo:
- Cada item é uma frase curta e independente, em português.
- Registre apenas o que está na transcrição. Não invente, não deduza nomes e não \
preencha um campo só para ele não ficar vazio.
- "participantes" recebe só nomes de pessoas ditos na conversa; se ninguém for \
nomeado, devolva uma lista vazia.
- Uma lista vazia é uma resposta válida e melhor do que um item inventado.\
"""


class ResumoClaude:
    """Porta de resumo atendida pelo Claude da conta do usuário (OAuth).

    Levanta `ErroDeResumo` em qualquer falha — sem credencial, sem CLI, tempo
    esgotado, transcrição grande demais ou resposta que não vira `Resumo`. O
    pipeline já sabe o que fazer com isso: registra `falhou` no `estado.json`,
    não escreve nota parcial e preserva a gravação para o reprocesso.
    """

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_PADRAO,
        limite_de_caracteres: int = LIMITE_DE_CARACTERES,
        timeout_s: float = TIMEOUT_PADRAO_S,
    ) -> None:
        self.modelo = modelo or None
        self.limite_de_caracteres = limite_de_caracteres
        self.timeout_s = timeout_s

    def resumir(self, transcricao: Transcricao, titulo: str | None = None) -> Resumo:
        """Manda a transcrição ao Claude e devolve o resumo em português."""
        pergunta = montar_pergunta(transcricao, titulo)
        self._recusar_transcricao_longa(pergunta)

        _log.info(
            "Pedindo o resumo ao Claude (%d falas, %d caracteres, modelo: %s)...",
            len(transcricao.falas),
            len(pergunta),
            self.modelo or "padrão da conta",
        )
        resposta = self._conversar(pergunta)
        resumo = interpretar_resposta(resposta)
        _log.info(
            "Resumo recebido: %d decisões, %d ações, %d tópicos.",
            len(resumo.decisoes),
            len(resumo.acoes),
            len(resumo.topicos),
        )
        return resumo

    def _recusar_transcricao_longa(self, pergunta: str) -> None:
        if len(pergunta) <= self.limite_de_caracteres:
            return
        raise ErroDeResumo(
            f"Transcrição grande demais para um resumo em uma chamada só: "
            f"{len(pergunta)} caracteres, limite {self.limite_de_caracteres}. "
            f"A transcrição está preservada — a nota pode ser gerada depois que "
            f"o resumo em partes existir."
        )

    def _conversar(self, pergunta: str) -> str:
        """Faz a chamada e devolve o texto cru da resposta.

        É o único ponto que toca a rede: os testes sem rede substituem este
        método e exercitam todo o resto do caminho.
        """
        verificar_credencial()
        try:
            return asyncio.run(
                asyncio.wait_for(
                    _conversar_async(pergunta, modelo=self.modelo),
                    timeout=self.timeout_s,
                )
            )
        except TimeoutError as erro:
            raise ErroDeResumo(
                f"O Claude não respondeu em {self.timeout_s:.0f}s — resumo cancelado."
            ) from erro
        except ClaudeSDKError as erro:
            raise ErroDeResumo(
                f"Falha ao falar com o Claude ({type(erro).__name__}): {erro}"
            ) from erro


def verificar_credencial() -> None:
    """Recusa a chamada se o ambiente puder cobrar por API key paga.

    O Agent SDK herda o ambiente do processo, e o `claude` CLI prefere uma
    chave de API à conta logada. Cair nesse caminho em silêncio gastaria
    dinheiro do usuário — então paramos aqui e dizemos como consertar.
    """
    presentes = [nome for nome in VARIAVEIS_DE_API_PAGA if os.environ.get(nome)]
    if not presentes:
        return
    raise ErroDeResumo(
        f"O resumo usa a conta Claude do usuário (OAuth), nunca uma API key paga, "
        f"mas {' e '.join(presentes)} está no ambiente e o Claude cobraria por ela. "
        f"Remova a variável e entre com `claude login` para o coletor continuar."
    )


def montar_pergunta(transcricao: Transcricao, titulo: str | None = None) -> str:
    """O turno do usuário: o título da gravação e a transcrição inteira."""
    cabecalho = [
        f"Título informado ao gravar: {titulo}" if titulo else "A gravação não tem título.",
        f"Idioma da transcrição: {transcricao.idioma}.",
        "",
        "Transcrição, uma fala por linha, no formato `falante: texto`:",
        "",
    ]
    return "\n".join(cabecalho) + transcricao.texto_corrido() + "\n"


def interpretar_resposta(bruto: str) -> Resumo:
    """Traduz a resposta do Claude em `Resumo`, ou levanta `ErroDeResumo`.

    O modelo às vezes embrulha o JSON em cerca de código ou em uma frase de
    apresentação; aceitamos isso. O que não aceitamos é uma resposta sem
    objeto JSON, ou com objeto que não traz nenhuma das três listas — aí a
    resposta crua vai para o log e a falha é explícita.
    """
    dados = _extrair_objeto(bruto)
    if not any(chave in dados for chave in ("decisoes", "acoes", "topicos")):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeResumo(
            "O Claude devolveu um JSON sem 'decisoes', 'acoes' nem 'topicos' — "
            f"resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )

    return Resumo(
        decisoes=_lista_de_textos(dados.get("decisoes")),
        acoes=_lista_de_textos(dados.get("acoes")),
        topicos=_lista_de_textos(dados.get("topicos")),
        participantes=_lista_de_textos(dados.get("participantes")),
        titulo=_texto_ou_nada(dados.get("titulo")),
    )


async def _conversar_async(pergunta: str, *, modelo: str | None) -> str:
    """Um turno com o Claude, sem ferramentas e sem estado de projeto."""
    opcoes = ClaudeAgentOptions(
        system_prompt=PROMPT_DO_SISTEMA,
        model=modelo,
        # Resumir é uma pergunta, não uma sessão de agente: sem ferramentas,
        # sem skills, sem CLAUDE.md nem settings da máquina, sem MCP. Assim o
        # resumo depende só da transcrição, aqui e na máquina de destino.
        tools=[],
        allowed_tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        permission_mode="dontAsk",
        max_turns=1,
        stderr=registrar_stderr_do_cli,
    )

    partes: list[str] = []
    resultado: ResultMessage | None = None
    async for mensagem in query(prompt=pergunta, options=opcoes):
        if isinstance(mensagem, AssistantMessage):
            partes.extend(
                bloco.text for bloco in mensagem.content if isinstance(bloco, TextBlock)
            )
        elif isinstance(mensagem, ResultMessage):
            resultado = mensagem

    if resultado is not None and resultado.is_error:
        raise ErroDeResumo(
            f"O Claude terminou em erro ({resultado.subtype}): "
            f"{resultado.result or 'sem detalhe'}"
        )

    texto = (resultado.result if resultado and resultado.result else "\n".join(partes))
    if not texto.strip():
        raise ErroDeResumo("O Claude respondeu vazio — nenhum texto para virar resumo.")
    return texto


_NADA = object()


def _extrair_objeto(bruto: str) -> dict:
    """Acha e decodifica o objeto JSON dentro da resposta.

    Tenta a resposta inteira primeiro — é o caso normal e o único que sabe
    dizer "veio JSON, mas não é um objeto". Só então recorta entre a primeira
    chave e a última, para o caso de o modelo ter falado antes ou depois.
    """
    texto = _sem_cerca_de_codigo(bruto.strip())
    dados, falha = _decodificar(texto)

    inicio = texto.find("{")
    fim = texto.rfind("}")
    if dados is _NADA and inicio != -1 and fim > inicio:
        dados, falha = _decodificar(texto[inicio : fim + 1])

    if dados is _NADA:
        _registrar_resposta_ilegivel(bruto)
        if inicio == -1:
            raise ErroDeResumo(
                "O Claude não devolveu um objeto JSON — resposta crua no log. "
                f"Começo da resposta: {_trecho(bruto)!r}"
            )
        raise ErroDeResumo(
            f"O JSON do resumo veio malformado ({falha}) — resposta crua no log. "
            f"Começo da resposta: {_trecho(bruto)!r}"
        )

    if not isinstance(dados, dict):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeResumo(
            f"O JSON do resumo não é um objeto, e sim {type(dados).__name__} — "
            f"resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )
    return dados


def _decodificar(texto: str) -> tuple[object, str]:
    """Devolve `(dados, "")` ou `(_NADA, motivo)` — nunca levanta."""
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


def _lista_de_textos(valor: object) -> tuple[str, ...]:
    """Normaliza um campo de lista, tolerando item que não veio como string."""
    if valor is None:
        return ()
    itens: Iterable[object] = valor if isinstance(valor, list) else [valor]
    textos = (_texto_do_item(item) for item in itens)
    return tuple(texto for texto in textos if texto)


def _texto_do_item(item: object) -> str:
    """Vira uma frase: o modelo às vezes devolve `{acao, responsavel}` no lugar."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return " — ".join(
            parte for parte in (_texto_do_item(v) for v in item.values()) if parte
        )
    if isinstance(item, list):
        return ", ".join(parte for parte in (_texto_do_item(v) for v in item) if parte)
    if item is None or isinstance(item, bool):
        return ""
    return str(item).strip()


def _texto_ou_nada(valor: object) -> str | None:
    texto = _texto_do_item(valor)
    return texto or None


def _trecho(bruto: str) -> str:
    return bruto.strip()[:200]


def _registrar_resposta_ilegivel(bruto: str) -> None:
    _log.error(
        "Resposta do Claude que não virou resumo (primeiros %d caracteres):\n%s",
        _TRECHO_DE_DIAGNOSTICO,
        bruto.strip()[:_TRECHO_DE_DIAGNOSTICO],
    )


def caminho_do_cli(preenchido: str | None) -> str | None:
    """O `claude.exe` que os adaptadores do jornal passam como `cli_path`.

    O CLI empacotado no SDK (2.1.238) não emite as janelas do plano e deixa o
    `files` do Artifact atrás de um flag remoto; o do npm (2.1.274 ou mais novo)
    faz as duas coisas. Vence `[claude].cli` preenchido; sem ele, o do npm se
    existir; senão `None`, e o SDK cai no empacotado. O `.cmd` do npm não serve:
    o SDK recusa script batch, tem de ser o `.exe` de `bin/`.
    """
    if preenchido and preenchido.strip():
        return preenchido.strip()
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    do_npm = (
        Path(appdata) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    )
    return str(do_npm) if do_npm.is_file() else None
