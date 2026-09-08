"""Adaptador real das duas perguntas sobre trabalho: o Claude da conta do usuário.

Irmão de `resumo_claude`, com outra entrada: no lugar da transcrição de uma
reunião chegam os eventos das fontes passivas e as reuniões que já viraram nota
no vault. A postura é a mesma — Claude Agent SDK, credenciais do `claude` CLI
(a conta Pro/Max do usuário por OAuth, como manda o ADR 0001), um turno só, sem
ferramenta nenhuma. Se uma chave de API paga estiver no ambiente, o adaptador
**recusa a chamada** em vez de gastar dinheiro do usuário sem ele pedir.

São duas perguntas porque são dois artefatos com recortes de tempo diferentes,
e não um derivado do outro:

- `resumir_dia` escreve o **diário** de um dia civil. O que se pede não é uma
  lista reescrita — as listas cruas já ficam na nota, logo abaixo da narrativa.
  O que só o Claude consegue fazer é **ligar as fontes**: dizer que o commit da
  tarde é a issue que a reunião da manhã destravou.
- `resumir_daily` escreve o **roteiro falado** da daily, cobrindo tudo desde a
  última fala — um dia, ou um fim de semana inteiro. O que se pede é separar o
  trabalho **dele** do contexto do time e dizer o que espera outra pessoa.

Falhar aqui não custa a nota: a costura captura o erro e o artefato nasce com as
listas cruas e a marca do que faltou. Por isso toda mensagem de erro daqui é
escrita para ser lida no aviso da nota.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Iterable, Sequence

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    query,
)

from .fontes import Evento
from .portas import Daily, ErroDeDaily, ErroDeResumoDoDia, ResumoDoDia
from .resumo_claude import VARIAVEIS_DE_API_PAGA

_log = logging.getLogger("second_brain.resumo_do_dia")

#: Modelo usado na chamada. `None` = o padrão da conta/CLI do usuário.
#:
#: Fica em `None` pelo mesmo motivo do adaptador de reunião: o diário roda na
#: máquina do usuário, contra a assinatura dele, e fixar um id aqui arriscaria
#: pedir um modelo fora do plano. Quem quiser fixar preenche `[claude] modelo`.
MODELO_PADRAO: str | None = None

#: Acima disso o dia não é enviado — ver `_recusar_dia_longo`.
LIMITE_DE_CARACTERES = 400_000

#: Quantos caracteres do `detalhe` de um evento vão ao Claude. A nota guarda o
#: detalhe inteiro; o roteiro precisa do gist. A primeira segunda-feira real
#: (2026-09-08) trouxe 878 eventos do Linear em quatro dias, com um comentário
#: de 7.500 caracteres, e o período inteiro estourou o teto de uma chamada.
DETALHE_MAXIMO = 500

#: Teto de tempo para a chamada inteira, em segundos.
TIMEOUT_PADRAO_S = 300.0

#: Quantos caracteres da resposta crua entram no log/erro quando o parse falha.
_TRECHO_DE_DIAGNOSTICO = 600

#: `2026-09-03-1430-daily-do-time` — o basename da nota de reunião no vault.
_NOME_DA_REUNIAO = re.compile(
    r"^(?P<ano>\d{4})-(?P<mes>\d{2})-(?P<dia>\d{2})-(?P<hora>\d{2})(?P<minuto>\d{2})"
    r"(?:-(?P<titulo>.*))?$"
)

PROMPT_DO_SISTEMA = """\
Você escreve o diário de trabalho de um desenvolvedor a partir dos rastros que \
o dia dele deixou nas ferramentas: commits do git, movimentação no Linear, \
conversas no Slack e as reuniões que já viraram nota no vault.

Escreva tudo em português do Brasil. O usuário fala português com jargão técnico \
em inglês: preserve esses termos exatamente como aparecem (deploy, rollback, \
review, sprint, issue, daily, branch, merge, bug). Nunca os traduza.

Responda com um único objeto JSON, sem nenhum texto antes ou depois e sem cercas \
de código, exatamente neste formato:

{"narrativa": "dois ou três parágrafos sobre o dia",
 "destaques": ["o que importou no dia"],
 "pendencias": ["o que ficou em aberto"],
 "temas": ["termos curtos para buscar este dia depois"]}

Regras do conteúdo:
- A narrativa **liga** as fontes: conta que dia foi aquele, o fio entre a \
conversa, a issue e o commit. Ela não reescreve a lista de eventos — as listas \
cruas já ficam na nota logo abaixo do seu texto, e repeti-las é desperdício. \
Prefira "a correção do frete saiu da reunião da manhã para produção no fim da \
tarde" a "houve 3 commits e 2 issues".
- A narrativa é o que o usuário lê em trinta segundos: dois ou três parágrafos, \
sem título, sem lista dentro dela e sem preâmbulo do tipo "neste dia".
- "destaques" e "pendencias" são frases curtas e independentes, em português.
- "pendencias" é só o que ficou em aberto ao fim do dia e aparece nos eventos: \
issue que não fechou, review esperando, combinado sem dono, erro sem \
acompanhamento.
- "temas" são termos curtos, de uma a três palavras, sem verbo e sem frase. Eles \
vão para o frontmatter da nota e servem para achar este dia numa busca meses \
depois: nomes de projeto, repositório, sistema ou assunto.
- Registre apenas o que está nos eventos e nas reuniões listadas. Não invente, \
não deduza o que não foi dito e não preencha um campo só para ele não ficar \
vazio.
- Uma lista vazia é uma resposta válida e melhor do que um item inventado.\
"""

PROMPT_DA_DAILY = """\
Você prepara o roteiro que um desenvolvedor vai FALAR na daily do time do dia, a \
partir dos rastros que o trabalho dele deixou nas ferramentas: commits do git, \
movimentação no Linear, conversas no Slack e as reuniões que já viraram nota no \
vault.

Os eventos cobrem tudo que aconteceu desde a última daily — pode ser um dia, \
pode ser um fim de semana inteiro, pode ser uma semana de folga. Não diga "hoje" \
nem "ontem": diga o que foi feito.

Escreva em português do Brasil, na primeira pessoa e na voz de quem fala em voz \
alta para o time. O usuário fala português com jargão técnico em inglês: \
preserve esses termos exatamente como aparecem (deploy, rollback, review, sprint, \
issue, daily, branch, merge, PR, bug). Nunca os traduza.

Responda com um único objeto JSON, sem nenhum texto antes ou depois e sem cercas \
de código, exatamente neste formato:

{"entreguei": ["o que fechou ou andou"],
 "sigo_em": ["o que continua agora"],
 "preciso_de": ["o que espera outra pessoa"],
 "duvidas": ["pergunta aberta no material"]}

De quem é cada coisa — a regra que mais importa:
- Os commits do git são DELE: a fonte já filtra por autor.
- O Linear e o Slack trazem o time INTEIRO. Issue que outra pessoa moveu, \
comentário que outra pessoa escreveu e mensagem de outra pessoa são CONTEXTO, \
não trabalho dele.
- "entreguei" e "sigo_em" são só o trabalho DELE. Quando não der para saber quem \
fez, deixe de fora: uma daily curta e verdadeira é melhor que uma longa que \
atribui a ele o trabalho de outra pessoa.
- Conversa de DM no Slack mistura trabalho e vida pessoal na mesma thread: \
piada, combinação de almoço, papo de futebol, assunto de família. SÓ o que é \
trabalho entra no roteiro. Assunto pessoal não vira "entreguei", não vira \
"duvidas" e não é citado nem de passagem — nem para dizer que aconteceu. Na \
dúvida sobre se uma conversa é trabalho, deixe de fora: o roteiro é falado na \
frente do time inteiro.
- Movimentação alheia só entra na resposta se virar "preciso_de" (ele depende \
dela para andar) ou "duvidas" (ela levanta uma pergunta para ele).

O que vai em cada batida:
- "entreguei": o que fechou ou andou de verdade, de três a cinco itens. Agrupe o \
que é a mesma entrega em vez de listar commit por commit, e escreva o que outra \
pessoa entenderia sem contexto. Frase curta, no passado: "subi a validação do \
link coringa e fechei a FN-1610".
- "sigo_em": o que ficou pela metade e continua agora — issue que terminou o \
período em In Progress, branch sem PR, refatoração começada. De um a três itens, \
no presente: "sigo nas FN-1617, FN-1618 e FN-1619, que ficaram em In Progress".
- "preciso_de": SÓ o que depende de OUTRA PESSOA para andar — review parado, \
aprovação, acesso, resposta que não veio —, dizendo de quem ou de quê é a \
dependência. "a FN-1623 está parada esperando o review da Ana" entra, porque quem \
revisa é outra pessoa. NÃO deduza de quem é uma etapa pelo nome do estado nem \
pela convenção de outros times: uma issue em "In Review" ou um PR aberto podem \
depender só dele, e cada time combina isso de um jeito. Nota para si mesmo NÃO entra: "faltou exercitar o \
estado expirado na validação" e "não fiz a comparação visual" dependem só dele e \
ficam de fora da daily inteira. Se nada estiver esperando outra pessoa, devolva \
lista vazia — dizer que não está bloqueado é uma daily melhor do que inventar um \
bloqueio.
- "duvidas": pergunta em aberto que apareceu no material e que vale levar ao \
time — decisão sem dono, combinado ambíguo, erro sem explicação. Nunca invente \
pergunta para preencher.

Regras gerais:
- Cada item é uma frase curta, dita em voz alta: o roteiro inteiro cabe em \
sessenta segundos. Sem título e sem parágrafo dentro do item.
- Quando o item cobrar uma ação sobre algo que tem link no material — PR, issue, \
documento —, traga o link em markdown com rótulo curto: "[#1636](https://...)". \
É a única marcação permitida dentro de um item: ela existe para ele clicar depois \
de falar, e em voz alta ele lê só o rótulo. Nunca cole a URL crua e nunca invente \
um link que não esteja no material.
- Registre apenas o que está nos eventos e nas reuniões listadas. Não invente, \
não deduza o que não foi dito e não preencha uma batida só para ela não ficar \
vazia.
- Uma lista vazia é uma resposta válida e melhor do que um item inventado.
- Quando o material trouxer um bloco "Como este time funciona", ele descreve o \
processo real dele e vale mais que qualquer dedução sua a partir de nome de \
estado ou de costume de outros times: siga-o.\
"""


class ResumoDoDiaClaude:
    """As portas de resumo do dia e da daily, pelo Claude da conta do usuário.

    Um objeto só atende as duas porque é o mesmo serviço, a mesma credencial e
    o mesmo teto de tamanho: o que muda é a pergunta e o formato da resposta.

    Levanta `ErroDeResumoDoDia` (diário) ou `ErroDeDaily` (daily) em qualquer
    falha — sem credencial, sem CLI, tempo esgotado, período grande demais ou
    resposta que não vira o tipo esperado. As costuras já sabem o que fazer com
    isso: escrevem a nota com as listas cruas e o aviso do que faltou.
    """

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_PADRAO,
        limite_de_caracteres: int = LIMITE_DE_CARACTERES,
        timeout_s: float = TIMEOUT_PADRAO_S,
        contexto_do_time: str = "",
    ) -> None:
        self.modelo = modelo or None
        self.limite_de_caracteres = limite_de_caracteres
        self.timeout_s = timeout_s
        # Entra pelo construtor, e não pela porta: `PortaDaily.resumir_daily`
        # tem a mesma assinatura para todo adaptador, e o processo do time é
        # configuração desta máquina, como o modelo.
        self.contexto_do_time = contexto_do_time.strip()

    def resumir_dia(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> ResumoDoDia:
        """Manda o dia ao Claude e devolve narrativa, destaques, pendências e temas."""
        pergunta = montar_pergunta(eventos, reunioes)
        self._recusar_dia_longo(pergunta)

        _log.info(
            "Pedindo o resumo do dia ao Claude (%d evento(s), %d reunião(ões), "
            "%d caracteres, modelo: %s)...",
            len(eventos),
            len(reunioes),
            len(pergunta),
            self.modelo or "padrão da conta",
        )
        resposta = self._conversar(pergunta)
        resumo = interpretar_resposta(resposta)
        _log.info(
            "Resumo do dia recebido: %d caractere(s) de narrativa, %d destaque(s), "
            "%d pendência(s), %d tema(s).",
            len(resumo.narrativa),
            len(resumo.destaques),
            len(resumo.pendencias),
            len(resumo.temas),
        )
        return resumo

    def resumir_daily(
        self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]
    ) -> Daily:
        """Manda a janela ao Claude e devolve as quatro batidas do roteiro."""
        pergunta = montar_pergunta_da_daily(
            eventos, reunioes, contexto_do_time=self.contexto_do_time
        )
        self._recusar_periodo_longo(pergunta)

        _log.info(
            "Pedindo o roteiro da daily ao Claude (%d evento(s), %d reunião(ões), "
            "%d caracteres, modelo: %s)...",
            len(eventos),
            len(reunioes),
            len(pergunta),
            self.modelo or "padrão da conta",
        )
        try:
            resposta = self._conversar(pergunta, PROMPT_DA_DAILY)
        except ErroDeResumoDoDia as erro:
            raise ErroDeDaily(str(erro)) from erro
        roteiro = interpretar_daily(resposta)
        _log.info(
            "Roteiro recebido: %d entregue(s), %d em andamento, %d esperando outra "
            "pessoa, %d dúvida(s).",
            len(roteiro.entreguei),
            len(roteiro.sigo_em),
            len(roteiro.preciso_de),
            len(roteiro.duvidas),
        )
        return roteiro

    def _recusar_dia_longo(self, pergunta: str) -> None:
        if len(pergunta) <= self.limite_de_caracteres:
            return
        raise ErroDeResumoDoDia(
            f"Dia grande demais para um resumo em uma chamada só: "
            f"{len(pergunta)} caracteres, limite {self.limite_de_caracteres}. "
            f"O diário nasce com as listas cruas e sem narrativa; para caber, "
            f"restrinja o que é coletado em [privacidade].excluir ou nas fontes."
        )

    def _recusar_periodo_longo(self, pergunta: str) -> None:
        if len(pergunta) <= self.limite_de_caracteres:
            return
        raise ErroDeDaily(
            f"Período grande demais para um roteiro em uma chamada só: "
            f"{len(pergunta)} caracteres, limite {self.limite_de_caracteres}. "
            f"A daily nasce com as listas cruas e sem roteiro; para caber, "
            f"restrinja o que é coletado em [privacidade].excluir ou nas fontes."
        )

    def _conversar(self, pergunta: str, sistema: str = PROMPT_DO_SISTEMA) -> str:
        """Faz a chamada e devolve o texto cru da resposta.

        É o único ponto que toca a rede: os testes sem rede substituem este
        método e exercitam todo o resto do caminho.
        """
        verificar_credencial()
        try:
            return asyncio.run(
                asyncio.wait_for(
                    _conversar_async(pergunta, modelo=self.modelo, sistema=sistema),
                    timeout=self.timeout_s,
                )
            )
        except TimeoutError as erro:
            raise ErroDeResumoDoDia(
                f"O Claude não respondeu em {self.timeout_s:.0f}s — "
                f"o dia ficou sem narrativa."
            ) from erro
        except ClaudeSDKError as erro:
            raise ErroDeResumoDoDia(
                f"Falha ao falar com o Claude ({type(erro).__name__}): {erro}"
            ) from erro


def verificar_credencial() -> None:
    """Recusa a chamada se o ambiente puder cobrar por API key paga.

    O Agent SDK herda o ambiente do processo, e o `claude` CLI prefere uma
    chave de API à conta logada. Como o diário roda todo dia por tarefa
    agendada, cair nesse caminho em silêncio viraria uma despesa recorrente
    que o usuário não pediu — então paramos aqui e dizemos como consertar.
    """
    presentes = [nome for nome in VARIAVEIS_DE_API_PAGA if os.environ.get(nome)]
    if not presentes:
        return
    raise ErroDeResumoDoDia(
        f"O resumo do dia usa a conta Claude do usuário (OAuth), nunca uma API "
        f"key paga, mas {' e '.join(presentes)} está no ambiente e o Claude "
        f"cobraria por ela. Remova a variável e entre com `claude login` para o "
        f"diário voltar a ter narrativa."
    )


def montar_pergunta(eventos: Sequence[Evento], reunioes: Sequence[str]) -> str:
    """O turno do usuário: o dia inteiro em ordem cronológica e as reuniões.

    A lista sai cronológica e não agrupada por fonte de propósito: o que se
    pede é a narrativa que **liga** as fontes, e é o entrelaçamento no tempo
    que a torna possível. Cada linha leva o dia junto da hora porque a janela
    do diário atravessa a meia-noite — o commit da 01:00 pertence ao mesmo dia
    de trabalho que a reunião das 14:00.
    """
    linhas = [
        "Eventos do dia, em ordem cronológica, no formato "
        "`DD/MM HH:MM [fonte] referência — título`:",
        "",
    ]
    if eventos:
        for evento in eventos:
            linhas.extend(_linhas_do_evento(evento))
    else:
        linhas.append("(nenhum evento das fontes passivas neste dia)")

    linhas.extend(["", "Reuniões deste dia já transcritas no vault:", ""])
    if reunioes:
        linhas.extend(f"- {_reuniao_legivel(reuniao)}" for reuniao in reunioes)
    else:
        linhas.append("(nenhuma reunião gravada neste dia)")

    return "\n".join(linhas) + "\n"


def montar_pergunta_da_daily(
    eventos: Sequence[Evento], reunioes: Sequence[str], *, contexto_do_time: str = ""
) -> str:
    """O turno do usuário: a janela inteira desde a última daily.

    Mesma lista cronológica do diário, com outra moldura: aqui o período pode
    ter vários dias, e dizer isso é o que impede o Claude de escrever "hoje"
    numa daily de segunda-feira que cobre o fim de semana.

    `contexto_do_time` é o que o usuário escreveu sobre o próprio processo. Sem
    ele o modelo deduz pelo nome do estado — foi assim que a primeira daily real
    afirmou que cinco PRs esperavam uma revisão humana que não existe no time
    dele.
    """
    linhas = [
        "Tudo que aconteceu desde a última daily, em ordem cronológica, no "
        "formato `DD/MM HH:MM [fonte] referência — título`:",
        "",
    ]
    if eventos:
        for evento in eventos:
            linhas.extend(_linhas_do_evento(evento))
    else:
        linhas.append("(nenhum evento das fontes passivas neste período)")

    linhas.extend(["", "Reuniões deste período já transcritas no vault:", ""])
    if reunioes:
        linhas.extend(f"- {_reuniao_legivel(reuniao)}" for reuniao in reunioes)
    else:
        linhas.append("(nenhuma reunião gravada neste período)")

    if contexto_do_time:
        linhas.extend(["", "Como este time funciona:", "", contexto_do_time])

    return "\n".join(linhas) + "\n"


def interpretar_daily(bruto: str) -> Daily:
    """Traduz a resposta do Claude em `Daily`, ou levanta `ErroDeDaily`.

    Um roteiro com as quatro batidas vazias vale como falha, e não como uma
    daily curta: seções vazias sem aviso fariam a nota se passar por completa,
    que é justamente o que ela promete nunca fazer.
    """
    try:
        dados = _extrair_objeto(bruto)
    except ErroDeResumoDoDia as erro:
        raise ErroDeDaily(str(erro)) from erro

    if not any(
        chave in dados for chave in ("entreguei", "sigo_em", "preciso_de", "duvidas")
    ):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeDaily(
            "O Claude devolveu um JSON sem 'entreguei', 'sigo_em', 'preciso_de' "
            f"nem 'duvidas' — resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )

    roteiro = Daily(
        entreguei=_lista_de_textos(dados.get("entreguei")),
        sigo_em=_lista_de_textos(dados.get("sigo_em")),
        preciso_de=_lista_de_textos(dados.get("preciso_de")),
        duvidas=_lista_de_textos(dados.get("duvidas")),
    )
    if not (
        roteiro.entreguei or roteiro.sigo_em or roteiro.preciso_de or roteiro.duvidas
    ):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeDaily(
            "O Claude devolveu um roteiro de daily inteiramente vazio — resposta "
            f"crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )
    return roteiro


def interpretar_resposta(bruto: str) -> ResumoDoDia:
    """Traduz a resposta do Claude em `ResumoDoDia`, ou levanta `ErroDeResumoDoDia`.

    O modelo às vezes embrulha o JSON em cerca de código ou em uma frase de
    apresentação; aceitamos isso. O que não aceitamos é uma resposta sem objeto
    JSON, sem nenhum dos quatro campos, ou com os quatro vazios: um diário com
    seções vazias e sem aviso se passaria por completo, que é justamente o que
    a nota promete nunca fazer.
    """
    dados = _extrair_objeto(bruto)
    if not any(
        chave in dados for chave in ("narrativa", "destaques", "pendencias", "temas")
    ):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeResumoDoDia(
            "O Claude devolveu um JSON sem 'narrativa', 'destaques', 'pendencias' "
            f"nem 'temas' — resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
        )

    resumo = ResumoDoDia(
        narrativa=_narrativa(dados.get("narrativa")),
        destaques=_lista_de_textos(dados.get("destaques")),
        pendencias=_lista_de_textos(dados.get("pendencias")),
        temas=_lista_de_textos(dados.get("temas")),
    )
    if not (resumo.narrativa or resumo.destaques or resumo.pendencias or resumo.temas):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeResumoDoDia(
            "O Claude devolveu um resumo do dia inteiramente vazio — resposta crua "
            f"no log. Começo da resposta: {_trecho(bruto)!r}"
        )
    return resumo


def registrar_custo(resultado: ResultMessage | None) -> None:
    """Deixa no log o peso desta chamada na assinatura do usuário.

    A conta é por **assinatura**, via OAuth: nada é cobrado por token, e o
    valor em dólar **não é uma cobrança**. Ele é o que a mesma chamada custaria
    na API paga, e serve como medida relativa — é assim que se responde, um mês
    depois, se o hábito ficou pesado na cota de uso.
    """
    if resultado is None:
        return
    uso = resultado.usage or {}
    _log.info(
        "Resumo do dia: equivalente a %s na tabela da API — a assinatura não "
        "cobra por token —, %s tokens de entrada (%s lidos de cache), %s de "
        "saída, em %s ms.",
        _dinheiro(resultado.total_cost_usd),
        uso.get("input_tokens", "?"),
        uso.get("cache_read_input_tokens", "?"),
        uso.get("output_tokens", "?"),
        resultado.duration_ms,
    )


async def _conversar_async(
    pergunta: str, *, modelo: str | None, sistema: str = PROMPT_DO_SISTEMA
) -> str:
    """Um turno com o Claude, sem ferramentas e sem estado de projeto."""
    opcoes = ClaudeAgentOptions(
        system_prompt=sistema,
        model=modelo,
        # Resumir o dia é uma pergunta, não uma sessão de agente: sem
        # ferramentas, sem skills, sem CLAUDE.md nem settings da máquina, sem
        # MCP. Assim o resumo depende só dos eventos, aqui e na máquina de
        # destino — e o Claude não alcança o disco do usuário.
        tools=[],
        allowed_tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        permission_mode="dontAsk",
        max_turns=1,
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

    # Antes do `is_error`: um turno que terminou mal também consumiu.
    registrar_custo(resultado)

    if resultado is not None and resultado.is_error:
        raise ErroDeResumoDoDia(
            f"O Claude terminou em erro ({resultado.subtype}): "
            f"{resultado.result or 'sem detalhe'}"
        )

    texto = resultado.result if resultado and resultado.result else "\n".join(partes)
    if not texto.strip():
        raise ErroDeResumoDoDia(
            "O Claude respondeu vazio — nenhum texto para virar resumo do dia."
        )
    return texto


def _linhas_do_evento(evento: Evento) -> list[str]:
    cabeca = f"{evento.momento:%d/%m %H:%M} [{evento.fonte}]"
    if evento.referencia:
        cabeca = f"{cabeca} {evento.referencia} —"
    linhas = [f"{cabeca} {evento.titulo}".strip()]
    linhas.extend(
        f"    {trecho.strip()}"
        for trecho in _detalhe_curto(evento.detalhe).splitlines()
        if trecho.strip()
    )
    if evento.pessoas:
        linhas.append(f"    pessoas: {', '.join(evento.pessoas)}")
    return linhas


def _detalhe_curto(detalhe: str) -> str:
    if len(detalhe) <= DETALHE_MAXIMO:
        return detalhe
    return detalhe[:DETALHE_MAXIMO].rstrip() + "…"


def _reuniao_legivel(caminho: str) -> str:
    """`reunioes/2026-09-03-1430-daily-do-time.md` → `03/09 14:30 — daily do time`.

    Nome fora do padrão volta como veio: o resumo do dia não pode falhar por
    causa de uma nota renomeada à mão, do mesmo jeito que a varredura do vault
    não falha.
    """
    nome = caminho.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".md")
    partes = _NOME_DA_REUNIAO.match(nome)
    if partes is None:
        return caminho
    titulo = (partes["titulo"] or "").replace("-", " ").strip()
    quando = f"{partes['dia']}/{partes['mes']} {partes['hora']}:{partes['minuto']}"
    return f"{quando} — {titulo}" if titulo else quando


def _dinheiro(valor: float | None) -> str:
    return f"US$ {valor:.4f}" if isinstance(valor, (int, float)) else "não informado"


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
            raise ErroDeResumoDoDia(
                "O Claude não devolveu um objeto JSON — resposta crua no log. "
                f"Começo da resposta: {_trecho(bruto)!r}"
            )
        raise ErroDeResumoDoDia(
            f"O JSON do resumo do dia veio malformado ({falha}) — resposta crua "
            f"no log. Começo da resposta: {_trecho(bruto)!r}"
        )

    if not isinstance(dados, dict):
        _registrar_resposta_ilegivel(bruto)
        raise ErroDeResumoDoDia(
            f"O JSON do resumo do dia não é um objeto, e sim {type(dados).__name__} "
            f"— resposta crua no log. Começo da resposta: {_trecho(bruto)!r}"
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


def _narrativa(valor: object) -> str:
    """A narrativa como texto corrido — o modelo às vezes manda um item por parágrafo."""
    if isinstance(valor, list):
        paragrafos = (_texto_do_item(item) for item in valor)
        return "\n\n".join(paragrafo for paragrafo in paragrafos if paragrafo)
    return _texto_do_item(valor)


def _lista_de_textos(valor: object) -> tuple[str, ...]:
    """Normaliza um campo de lista, tolerando item que não veio como string."""
    if valor is None:
        return ()
    itens: Iterable[object] = valor if isinstance(valor, list) else [valor]
    textos = (_texto_do_item(item) for item in itens)
    return tuple(texto for texto in textos if texto)


def _texto_do_item(item: object) -> str:
    """Vira uma frase: o modelo às vezes devolve `{tema, motivo}` no lugar."""
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


def _trecho(bruto: str) -> str:
    return bruto.strip()[:200]


def _registrar_resposta_ilegivel(bruto: str) -> None:
    _log.error(
        "Resposta do Claude que não virou resumo do dia (primeiros %d caracteres):\n%s",
        _TRECHO_DE_DIAGNOSTICO,
        bruto.strip()[:_TRECHO_DE_DIAGNOSTICO],
    )
