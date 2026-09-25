"""Os três adaptadores do Claude no jornal: o editor, a formação e a publicação.

Mesma postura dos irmãos (`resumo_claude`, `resumo_dia_claude`, `busca_claude`):
Claude Agent SDK, credenciais do `claude` CLI (a conta Pro/Max do usuário por
OAuth, ADR 0001), recusa de API key paga, sem skills, sem configuração de
arquivo, sem MCP, custo no log. Três diferenças que só o jornal tem:

- **saída estruturada**: o editor e a formação pedem `output_format` com um
  JSON Schema e leem `ResultMessage.structured_output` — nunca JSON em texto
  livre (a segunda edição do protótipo caiu por uma chave a menos);
- **`cli_path`**: os três apontam para o `claude.exe` do npm quando existe
  (`caminho_do_cli`), porque só ele emite as janelas do plano e o `files` do
  Artifact sem depender de flag remoto;
- **consumo do plano**: o laço de mensagens lê cada `RateLimitEvent` e guarda a
  primeira e a última leitura das janelas de 5 h e 7 dias em `Medida`.

O único ponto que toca a rede é `_mensagens`; os testes sem rede o substituem
por mensagens gravadas e exercitam todo o resto.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from time import monotonic
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    RateLimitEvent,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from .portas import (
    Aula,
    Candidato,
    ErroDeEditor,
    ErroDeFormacao,
    ErroDePublicacao,
    ErroDeResumo,
    Escolha,
    Formacao,
    ItemEscolhido,
    Janelas,
    Medida,
    Publicacao,
)
from .resumo_claude import caminho_do_cli, registrar_stderr_do_cli, verificar_credencial

_log = logging.getLogger("whis.jornal")

MODELO_DA_PUBLICACAO = "haiku"

TIMEOUT_DA_ESCOLHA_S = 300.0
TIMEOUT_DA_FORMACAO_S = 420.0
TIMEOUT_DA_PUBLICACAO_S = 240.0

TURNOS_DA_FORMACAO = 30
TURNOS_DA_PUBLICACAO = 12

LIMITES_PADRAO = (3, 5)
MAXIMO_DO_TIME = 2
MAXIMO_POR_FONTE = 2
AULAS_DE_CARRO = 2

FERRAMENTAS_DA_FORMACAO = ["WebSearch", "WebFetch"]
FERRAMENTAS_DA_PUBLICACAO = ["Artifact", "Read"]

SAIDA_ESTRUTURADA = "StructuredOutput"

AMBIENTE_DA_PUBLICACAO = {"CLAUDE_CODE_ARTIFACT": "1", "CLAUDE_CODE_ARTIFACT_AUTO_OPEN": "0"}

PADRAO_DA_URL = re.compile(r"https://claude\.ai/(?:code/)?artifact/[\w-]+")
_PADRAO_DA_PUBLICACAO = re.compile(
    r"\bPublished (?!files\b)[^\n]*? at (https://claude\.ai/(?:code/)?artifact/[\w-]+)"
)

_PREFIXOS_HERDADOS = ("CLAUDE", "ANTHROPIC", "AI_AGENT", "BAGGAGE")
_HERDADAS_MANTIDAS = frozenset(
    {"CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_GIT_BASH_PATH"}
)

SISTEMA_ESCOLHA = """\
Você é o editor do jornal matinal pessoal de um desenvolvedor de software brasileiro que também é \
músico (guitarra, teclado; gospel, jazz, rock, indie, equipamentos de áudio) e está começando a se \
interessar por carros.
Você recebe candidatos numerados por seção, todos publicados nas últimas 24 h, cada um com id, fonte, \
título e resumo. Sua tarefa é ESCOLHER, TRADUZIR e RESUMIR. Regras invioláveis:
- Só existe o que está na lista. Cite apenas ids que recebeu, na seção em que vieram. Nunca acrescente \
fato que não esteja no título ou no resumo.
- Se uma seção não tem nada relevante, devolva lista vazia para ela.
- No máximo 2 itens da mesma fonte por seção.
- Tecnologia: programação, IA e hardware primeiro; ignore celebridade e política de empresa.
- Mundo: geopolítica e o que muda o mundo; ignore curiosidade e crime comum.
- Política no Brasil: factual, sem opinião; prefira o que muda lei, eleição, STF, governo.
- Música: NÃO é hit parade. Vale lançamento de instrumento, teclado, guitarra, pedal, plugin, áudio, \
disco de instrumentista, gospel, jazz, rock, indie. Itens marcados destaque=true citam nomes que ele \
acompanha: têm prioridade se forem relevantes.
- Futebol: notícia relevante (transferência, lesão, decisão), não placar (o placar vem de outro lugar).
- Carros: lançamentos de luxo e populares.
- Seção nova, sem regra acima: o que for relevante para o assunto dela.
- Título em português, curto. Resumo em português, duas frases, informativo, sem adjetivo vazio, sem \
"confira".
Devolva em "secoes" uma lista por seção recebida, cada item {id, titulo, resumo}, e em "time" os itens \
do time do coração. Respeite min e max de cada seção quando houver material; "time" tem no máximo 2 \
itens."""

SISTEMA_FORMACAO = """\
Você escreve a parte de FORMAÇÃO do jornal matinal de um desenvolvedor de software brasileiro que está \
começando a gostar de carros. Todo dia você ensina uma coisa nova, progressivamente, e mantém uma TRILHA \
do que já ensinou para não repetir e para avançar em dificuldade. Você tem busca na web (WebSearch) e \
leitura de página (WebFetch): USE-AS. Regras invioláveis:
- Cada texto precisa vir de fontes que você realmente abriu; liste as URLs em "fontes". Sem URL, o item \
é descartado.
- Não invente número, data ou nome. Se não achou, diga que não achou.
- Português do Brasil, tom direto, entre 120 e 200 palavras por item, com um "por que isso importa" no fim.
- Software: um assunto por dia, prático, para quem já programa (arquitetura, testes, linguagens, \
sistemas, ferramentas, história).
- Carros: dois assuntos por dia para iniciante curioso: história (JDM, marcas, modelos icônicos), como \
funciona (motor rotativo, turbo, câmbio, tração), cultura. Comece pelo básico e avance conforme a trilha.
- Use no máximo 6 buscas e 6 leituras no total.
Devolva "software" (uma aula) e "carros" (duas aulas), cada aula com titulo, texto, fontes (URLs) e \
trilha: o assunto de hoje em até 6 palavras, no formato "software: <assunto>" ou "carros: <assunto>"."""

SISTEMA_PUBLICACAO = "Você opera ferramentas. Sem comentários."

_ITEM_ESCOLHIDO = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "titulo": {"type": "string"},
        "resumo": {"type": "string"},
    },
    "required": ["id", "titulo", "resumo"],
    "additionalProperties": False,
}

_AULA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "texto": {"type": "string"},
        "fontes": {"type": "array", "items": {"type": "string"}},
        "trilha": {"type": "string"},
    },
    "required": ["titulo", "texto", "fontes", "trilha"],
    "additionalProperties": False,
}

ESQUEMA_DA_FORMACAO = {
    "type": "object",
    "properties": {
        "software": _AULA,
        "carros": {"type": "array", "items": _AULA},
    },
    "required": ["software", "carros"],
    "additionalProperties": False,
}


@dataclass
class Conversa:
    """O que uma chamada deixou: textos, resultados de ferramenta, o fim e a medida."""

    textos: list[str] = field(default_factory=list)
    ferramentas: list[str] = field(default_factory=list)
    resultados_de_ferramenta: list[str] = field(default_factory=list)
    resultado: ResultMessage | None = None
    plano_primeiro: Janelas | None = None
    plano_ultimo: Janelas | None = None
    medida: Medida = field(default_factory=Medida)

    def texto_final(self) -> str:
        if self.resultado is not None and self.resultado.result:
            return self.resultado.result
        return "\n".join(self.textos)


def ler_janelas(evento: RateLimitEvent) -> Janelas | None:
    """As janelas de 5 h e 7 dias em pontos inteiros; `None` sem `unifiedWindows`.

    `unifiedWindows` é `@internal` no CLI e só existe a partir do 2.1.274: o que
    faltar, ou vier noutro formato, vira `None` — nunca erro.
    """
    bruto = getattr(evento.rate_limit_info, "raw", None)
    janelas = bruto.get("unifiedWindows") if isinstance(bruto, dict) else None
    if not isinstance(janelas, dict):
        return None
    cinco = _pontos(janelas.get("five_hour"))
    sete = _pontos(janelas.get("seven_day"))
    if cinco is None and sete is None:
        return None
    return Janelas(cinco_horas=cinco, sete_dias=sete)


def _pontos(janela: object) -> int | None:
    if not isinstance(janela, dict):
        return None
    uso = janela.get("utilization")
    if isinstance(uso, bool) or not isinstance(uso, (int, float)):
        return None
    return round(100 * uso)


def ambiente_do_cli(extra: dict[str, str] | None = None) -> dict[str, str]:
    """O `env` das opções: neutraliza o que o processo herdou de outra sessão do Claude.

    Chamado de dentro de uma sessão de agente, o Whis herda `CLAUDE_CODE_*`,
    `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_SESSION_ID` e afins, que fariam o CLI
    filho se achar parte daquela sessão (outro proxy, outras ferramentas). O SDK
    só sabe acrescentar variáveis ao ambiente herdado, não tirar; então cada uma
    entra aqui vazia — o CLI trata vazio como ausente — sem mexer em
    `os.environ`. Ficam as que são configuração da máquina, não da sessão:
    o login por token, a pasta de configuração, o bash do Git e o entrypoint
    (que o SDK fixa em `sdk-py`).
    """
    neutras = {
        nome: ""
        for nome in os.environ
        if nome.upper().startswith(_PREFIXOS_HERDADOS) and nome.upper() not in _HERDADAS_MANTIDAS
    }
    return {**neutras, **(extra or {})}


def registrar_custo(etapa: str, conversa: Conversa) -> None:
    """Deixa no log o peso desta chamada na assinatura, com o plano antes e depois.

    O valor em dólar **não é cobrança**: é o equivalente da tabela da API, uma
    medida relativa de cota, como nos outros adaptadores.
    """
    resultado = conversa.resultado
    uso = (resultado.usage if resultado is not None else None) or {}
    _log.info(
        "Jornal · %s: equivalente a %s na tabela da API — a assinatura não cobra por "
        "token —, %s turno(s), %d chamada(s) de ferramenta, %s tokens de entrada (%s "
        "lidos de cache), %s de saída, em %.1f s; plano %s → %s.",
        etapa,
        _dinheiro(conversa.medida.custo_usd),
        resultado.num_turns if resultado is not None else "?",
        len(conversa.ferramentas),
        uso.get("input_tokens", "?"),
        uso.get("cache_read_input_tokens", "?"),
        uso.get("output_tokens", "?"),
        conversa.medida.segundos,
        _plano(conversa.medida.plano_primeiro),
        _plano(conversa.medida.plano_ultimo),
    )


class _AdaptadorDoJornal:
    """O que os três adaptadores têm em comum: opções, laço, tempo e medida."""

    etapa = ""
    erro: type[RuntimeError] = RuntimeError

    def __init__(self, *, modelo: str | None, cli: str | None, timeout_s: float) -> None:
        self.modelo = modelo or None
        self.cli = caminho_do_cli(cli)
        self.timeout_s = timeout_s

    def _verificar_credencial(self) -> None:
        try:
            verificar_credencial()
        except ErroDeResumo as erro:
            raise self.erro(str(erro)) from erro

    def _opcoes(
        self,
        *,
        sistema: str,
        ferramentas: list[str],
        max_turns: int,
        esquema: dict[str, Any] | None = None,
        cwd: Path | None = None,
        ambiente: dict[str, str] | None = None,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=sistema,
            model=self.modelo,
            tools=list(ferramentas),
            allowed_tools=list(ferramentas),
            skills=[],
            setting_sources=[],
            strict_mcp_config=True,
            permission_mode="dontAsk",
            max_turns=max_turns,
            cli_path=self.cli,
            cwd=cwd,
            env=ambiente_do_cli(ambiente),
            output_format={"type": "json_schema", "schema": esquema} if esquema else None,
            stderr=registrar_stderr_do_cli,
        )

    async def _mensagens(self, prompt: str, opcoes: ClaudeAgentOptions) -> AsyncIterator[Any]:
        """A única porta para a rede; os testes a trocam por mensagens gravadas."""
        async for mensagem in query(prompt=prompt, options=opcoes):
            yield mensagem

    def _conversar(self, prompt: str, opcoes: ClaudeAgentOptions) -> Conversa:
        self._verificar_credencial()
        conversa = Conversa()
        inicio = monotonic()
        try:
            asyncio.run(asyncio.wait_for(self._ler(prompt, opcoes, conversa), timeout=self.timeout_s))
        except TimeoutError as erro:
            self._medir(conversa, inicio)
            raise self.erro(
                f"O Claude não terminou a {self.etapa} em {self.timeout_s:.0f}s — cancelada."
            ) from erro
        except ClaudeSDKError as erro:
            self._medir(conversa, inicio)
            raise self.erro(
                f"Falha ao falar com o Claude na {self.etapa} ({type(erro).__name__}): {erro}"
            ) from erro
        self._medir(conversa, inicio)

        resultado = conversa.resultado
        if resultado is not None and resultado.is_error:
            detalhe = resultado.result or "; ".join(resultado.errors or ()) or "sem detalhe"
            raise self.erro(f"O Claude terminou a {self.etapa} em erro ({resultado.subtype}): {detalhe}")
        return conversa

    async def _ler(self, prompt: str, opcoes: ClaudeAgentOptions, conversa: Conversa) -> None:
        async for mensagem in self._mensagens(prompt, opcoes):
            if isinstance(mensagem, RateLimitEvent):
                janelas = ler_janelas(mensagem)
                if janelas is not None:
                    conversa.plano_primeiro = conversa.plano_primeiro or janelas
                    conversa.plano_ultimo = janelas
            elif isinstance(mensagem, AssistantMessage):
                for bloco in mensagem.content:
                    if isinstance(bloco, TextBlock):
                        conversa.textos.append(bloco.text)
                    elif isinstance(bloco, ToolUseBlock) and bloco.name != SAIDA_ESTRUTURADA:
                        conversa.ferramentas.append(bloco.name)
            elif isinstance(mensagem, UserMessage) and isinstance(mensagem.content, list):
                for bloco in mensagem.content:
                    if isinstance(bloco, ToolResultBlock):
                        conversa.resultados_de_ferramenta.append(_texto_do_resultado(bloco.content))
            elif isinstance(mensagem, ResultMessage):
                conversa.resultado = mensagem

    def _medir(self, conversa: Conversa, inicio: float) -> None:
        resultado = conversa.resultado
        conversa.medida = Medida(
            custo_usd=resultado.total_cost_usd if resultado is not None else None,
            segundos=round(monotonic() - inicio, 1),
            plano_primeiro=conversa.plano_primeiro,
            plano_ultimo=conversa.plano_ultimo,
        )
        registrar_custo(self.etapa, conversa)


class EditorClaude(_AdaptadorDoJornal):
    """A porta do editor: um turno, sem ferramenta, com saída estruturada.

    Levanta `ErroDeEditor` em qualquer falha — API key paga no ambiente, tempo
    esgotado, SDK reclamando ou saída estruturada ausente. A costura cai para
    os itens mais novos de cada seção.
    """

    etapa = "escolha"
    erro = ErroDeEditor

    def __init__(
        self,
        *,
        modelo: str | None = None,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_ESCOLHA_S,
    ) -> None:
        super().__init__(modelo=modelo, cli=cli, timeout_s=timeout_s)

    def escolher(
        self,
        candidatos: dict[str, tuple[Candidato, ...]],
        limites: dict[str, tuple[int, int]],
        time: tuple[Candidato, ...],
    ) -> Escolha:
        prompt = montar_pedido_de_escolha(candidatos, limites, time)
        opcoes = self._opcoes(
            sistema=SISTEMA_ESCOLHA,
            ferramentas=[],
            max_turns=1,
            esquema=esquema_da_escolha(candidatos),
        )
        _log.info(
            "Pedindo a escolha ao Claude (%d candidatos em %d seções, %d do time, modelo: %s)...",
            sum(len(lista) for lista in candidatos.values()),
            len(candidatos),
            len(time),
            self.modelo or "padrão da conta",
        )
        conversa = self._conversar(prompt, opcoes)
        dados = conversa.resultado.structured_output if conversa.resultado is not None else None
        if not isinstance(dados, dict):
            raise ErroDeEditor(
                "O Claude não devolveu a saída estruturada da escolha "
                f"(veio {type(dados).__name__}). Começo do texto: {conversa.texto_final()[:200]!r}"
            )
        escolha = interpretar_escolha(dados, candidatos, limites, time)
        return replace(escolha, medida=conversa.medida)


def esquema_da_escolha(candidatos: dict[str, tuple[Candidato, ...]]) -> dict[str, Any]:
    """Uma lista por seção recebida e a do time; os ids são conferidos depois."""
    lista = {"type": "array", "items": _ITEM_ESCOLHIDO}
    return {
        "type": "object",
        "properties": {
            "secoes": {
                "type": "object",
                "properties": {secao: lista for secao in candidatos},
                "required": list(candidatos),
                "additionalProperties": False,
            },
            "time": lista,
        },
        "required": ["secoes", "time"],
        "additionalProperties": False,
    }


def montar_pedido_de_escolha(
    candidatos: dict[str, tuple[Candidato, ...]],
    limites: dict[str, tuple[int, int]],
    time: tuple[Candidato, ...],
) -> str:
    """O turno do usuário: limites, o time do coração e os candidatos em JSON."""
    por_secao = {
        secao: [_candidato_no_pedido(candidato) for candidato in lista]
        for secao, lista in candidatos.items()
    }
    por_secao["time"] = [_candidato_no_pedido(candidato) for candidato in time]
    limites_no_pedido = {
        secao: {"min": minimo, "max": maximo}
        for secao, (minimo, maximo) in ((s, limites.get(s, LIMITES_PADRAO)) for s in candidatos)
    }
    nomes_do_time = sorted({candidato.fonte for candidato in time})
    return (
        f"Limites por seção: {json.dumps(limites_no_pedido, ensure_ascii=False)}\n"
        f"Time do coração (seção 'time'): {', '.join(nomes_do_time) or 'nenhum'}; "
        f"no máximo {MAXIMO_DO_TIME} itens.\n\n"
        f"CANDIDATOS:\n{json.dumps(por_secao, ensure_ascii=False)}"
    )


def _candidato_no_pedido(candidato: Candidato) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": candidato.id,
        "fonte": candidato.fonte,
        "titulo": candidato.titulo,
        "resumo": candidato.resumo,
    }
    if candidato.destaque:
        item["destaque"] = True
    return item


def interpretar_escolha(
    dados: dict,
    candidatos: dict[str, tuple[Candidato, ...]],
    limites: dict[str, tuple[int, int]],
    time: tuple[Candidato, ...],
) -> Escolha:
    """Valida a escolha do modelo contra o que ele recebeu.

    Id que não existe, ou que veio noutra seção, é descartado; repetido também.
    Título e resumo vazios caem para os do feed. Cada seção aceita no máximo
    `MAXIMO_POR_FONTE` itens da mesma fonte e no máximo o `max` dos limites; o
    time, no máximo `MAXIMO_DO_TIME`. Toda seção de `candidatos` aparece na
    `Escolha`, vazia quando o modelo não escolheu nada.
    """
    secoes_dados = dados.get("secoes") if isinstance(dados.get("secoes"), dict) else {}
    secoes = {
        secao: _validar_lista(
            secoes_dados.get(secao), lista, limites.get(secao, LIMITES_PADRAO)[1]
        )
        for secao, lista in candidatos.items()
    }
    return Escolha(secoes=secoes, time=_validar_lista(dados.get("time"), time, MAXIMO_DO_TIME))


def _validar_lista(
    escolhidos: object, recebidos: Iterable[Candidato], maximo: int
) -> tuple[ItemEscolhido, ...]:
    por_id = {candidato.id: candidato for candidato in recebidos}
    aceitos: list[ItemEscolhido] = []
    vistos: set[str] = set()
    por_fonte: dict[str, int] = {}
    for bruto in escolhidos if isinstance(escolhidos, list) else ():
        if len(aceitos) >= maximo:
            break
        if not isinstance(bruto, dict):
            continue
        candidato = por_id.get(str(bruto.get("id", "")))
        if candidato is None or candidato.id in vistos:
            continue
        if por_fonte.get(candidato.fonte, 0) >= MAXIMO_POR_FONTE:
            continue
        vistos.add(candidato.id)
        por_fonte[candidato.fonte] = por_fonte.get(candidato.fonte, 0) + 1
        aceitos.append(
            ItemEscolhido(
                candidato=candidato,
                titulo=_texto(bruto.get("titulo")) or candidato.titulo,
                resumo=_texto(bruto.get("resumo")) or candidato.resumo,
            )
        )
    return tuple(aceitos)


class FormacaoClaude(_AdaptadorDoJornal):
    """A porta da formação: agêntica, com busca e leitura na web, e citação obrigatória.

    Levanta `ErroDeFormacao` quando a chamada falha ou quando nenhuma aula
    chega com pelo menos uma URL em `fontes`.
    """

    etapa = "formação"
    erro = ErroDeFormacao

    def __init__(
        self,
        *,
        modelo: str | None = None,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_FORMACAO_S,
    ) -> None:
        super().__init__(modelo=modelo, cli=cli, timeout_s=timeout_s)

    def ensinar(self, data: date, trilha: str) -> Formacao:
        opcoes = self._opcoes(
            sistema=SISTEMA_FORMACAO,
            ferramentas=FERRAMENTAS_DA_FORMACAO,
            max_turns=TURNOS_DA_FORMACAO,
            esquema=ESQUEMA_DA_FORMACAO,
        )
        _log.info("Pedindo a formação ao Claude (modelo: %s)...", self.modelo or "padrão da conta")
        conversa = self._conversar(montar_pedido_de_formacao(data, trilha), opcoes)
        dados = conversa.resultado.structured_output if conversa.resultado is not None else None
        if not isinstance(dados, dict):
            raise ErroDeFormacao(
                "O Claude não devolveu a saída estruturada da formação "
                f"(veio {type(dados).__name__}). Começo do texto: {conversa.texto_final()[:200]!r}"
            )
        return replace(interpretar_formacao(dados, data), medida=conversa.medida)


def montar_pedido_de_formacao(data: date, trilha: str) -> str:
    """O turno do usuário: a data e a trilha inteira, do mais antigo ao mais novo."""
    return (
        f"Data: {data.isoformat()}\n\n"
        "TRILHA do que já foi ensinado (mais antigo primeiro):\n"
        f"{trilha.strip() or '(vazia: hoje é o primeiro dia)'}\n\n"
        "Escolha os assuntos de hoje, pesquise e escreva."
    )


def interpretar_formacao(dados: dict, data: date) -> Formacao:
    """Aceita só as aulas com texto e pelo menos uma URL `http` em `fontes`.

    Cada aula aceita leva em `trilha` a linha que `noticias/trilha.md` ganha
    por ela; a descartada não deixa linha. Nenhuma aceita → `ErroDeFormacao`.
    """
    software = _aula(dados.get("software"), "software", data)
    carros_dados = dados.get("carros") if isinstance(dados.get("carros"), list) else []
    carros = tuple(
        aula for aula in (_aula(bruta, "carros", data) for bruta in carros_dados) if aula is not None
    )[:AULAS_DE_CARRO]
    if software is None and not carros:
        raise ErroDeFormacao("Nenhuma aula da formação veio com texto e fonte — todas descartadas.")
    return Formacao(software=software, carros=carros)


def _aula(bruta: object, area: str, data: date) -> Aula | None:
    if not isinstance(bruta, dict):
        return None
    texto = _texto(bruta.get("texto"))
    fontes_brutas = bruta.get("fontes") if isinstance(bruta.get("fontes"), list) else []
    fontes = tuple(url for url in (_texto(f) for f in fontes_brutas) if url.startswith("http"))
    if not texto or not fontes:
        _log.warning("Aula de %s descartada: sem texto ou sem URL em fontes.", area)
        return None
    titulo = _texto(bruta.get("titulo")) or texto.split(".")[0][:80]
    assunto = _texto(bruta.get("trilha")) or titulo
    if not assunto.lower().startswith(f"{area}:"):
        assunto = f"{area}: {assunto}"
    return Aula(
        titulo=titulo,
        texto=texto,
        fontes=fontes,
        trilha=f"- {data.isoformat()} — {assunto}",
    )


class PublicacaoClaude(_AdaptadorDoJornal):
    """A porta da publicação: um Haiku que só opera a ferramenta Artifact.

    Levanta `ErroDePublicacao` quando a chamada falha ou quando nenhuma URL de
    artifact aparece na resposta. A nota da edição já existe nesse ponto.
    """

    etapa = "publicação"
    erro = ErroDePublicacao

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_DA_PUBLICACAO,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_PUBLICACAO_S,
    ) -> None:
        super().__init__(modelo=modelo or MODELO_DA_PUBLICACAO, cli=cli, timeout_s=timeout_s)

    def publicar(self, html: Path, capas: dict[str, Path], url_atual: str | None) -> Publicacao:
        prompt = (
            pedido_de_republicacao(html, capas, url_atual)
            if url_atual
            else pedido_de_primeira_publicacao(html, capas)
        )
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_PUBLICACAO,
            max_turns=TURNOS_DA_PUBLICACAO,
            cwd=html.parent,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        _log.info(
            "Publicando o jornal (%d capas, %s)...",
            len(capas),
            f"no mesmo endereço {url_atual}" if url_atual else "primeira edição",
        )
        conversa = self._conversar(prompt, opcoes)
        url = url_publicada(conversa)
        if url is None:
            raise ErroDePublicacao(
                "O Claude não devolveu a URL do artifact publicado. "
                f"Começo da resposta: {conversa.texto_final()[:300]!r}"
            )
        return Publicacao(url=url, medida=conversa.medida)


def pedido_de_primeira_publicacao(html: Path, capas: dict[str, Path]) -> str:
    """Um `publish` só, com o mapa `files` pronto e barras `/` (Haiku erra com `\\`)."""
    return (
        f"Publique o arquivo {html.as_posix()} como um artifact privado com a ferramenta Artifact: "
        f"action publish, file_path={html.as_posix()}, icon 'newspaper', favicon '📰', "
        f"description 'Jornal diário do Whis', e o parâmetro files exatamente assim: "
        f"{_mapa_de_arquivos(capas)}. Não passe capabilities. Não leia as imagens. "
        f"Não edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


def pedido_de_republicacao(html: Path, capas: dict[str, Path], url_atual: str) -> str:
    """Três passos em turnos separados, na ordem que o ticket 09 provou.

    O CLI recusa um `publish` construído no mesmo turno em que a versão viva
    chegou, e recusa trocar ou remover arquivo que a sessão não leu nem listou.
    """
    return (
        f"Outra sessão publicou o artifact {url_atual}; hoje ele recebe a edição nova no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url_atual}. Espere o resultado.\n"
        f"Passo 2 (só depois do resultado do passo 1): ferramenta Artifact, action list com scope files "
        f"(se a ferramenta chamar essa ação de list_files, use list_files), url={url_atual}; e leia "
        f"{html.as_posix()} com a ferramenta Read. Espere os resultados.\n"
        f"Passo 3 (só depois dos resultados do passo 2): ferramenta Artifact, action publish, "
        f"url={url_atual}, file_path={html.as_posix()}, label 'edição de hoje', e files com este mapa "
        f"{_mapa_de_arquivos(capas)} mais uma entrada com valor null para cada caminho img/* que a "
        f"listagem do passo 2 mostrou e que não está nesse mapa; overwrite_unread com a lista de todos "
        f"os caminhos img/* que a listagem do passo 2 mostrou. SEM force, sem capabilities.\n"
        f"Não leia as imagens. Não edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


def _mapa_de_arquivos(capas: dict[str, Path]) -> str:
    return json.dumps(
        {publicado: Path(local).as_posix() for publicado, local in sorted(capas.items())},
        ensure_ascii=False,
    )


def extrair_url(texto: str) -> str | None:
    """A última URL de artifact no texto, curta (`/artifact/<id>`) ou longa (`/code/artifact/<uuid>`)."""
    achadas = PADRAO_DA_URL.findall(texto or "")
    return achadas[-1] if achadas else None


def url_publicada(conversa: Conversa) -> str | None:
    """A URL que a ferramenta confirmou ao publicar; senão, a do texto final."""
    for resultado in reversed(conversa.resultados_de_ferramenta):
        achada = _PADRAO_DA_PUBLICACAO.search(resultado)
        if achada:
            return achada.group(1)
    return extrair_url(conversa.texto_final()) or extrair_url("\n".join(conversa.textos))


def _texto_do_resultado(conteudo: object) -> str:
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "\n".join(
            str(parte.get("text", "")) for parte in conteudo if isinstance(parte, dict)
        )
    return ""


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _dinheiro(valor: float | None) -> str:
    return f"US$ {valor:.4f}" if isinstance(valor, (int, float)) else "não informado"


def _plano(janelas: Janelas | None) -> str:
    if janelas is None:
        return "sem leitura"
    return f"5 h {_por_cento(janelas.cinco_horas)} · 7 d {_por_cento(janelas.sete_dias)}"


def _por_cento(valor: int | None) -> str:
    return f"{valor}%" if valor is not None else "?"
