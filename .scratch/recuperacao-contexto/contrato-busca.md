# Contrato: a busca, as ferramentas e a fronteira

Decisão do orquestrador, fixada **antes** de abrir qualquer camada, para que a costura, o
adaptador real, as fontes ao vivo e a DM do Slack sejam construídos contra o mesmo formato.
Não substitui nenhuma decisão da [spec](spec.md) — fecha o que ela deixou em aberto entre
camadas. Executor que discordar **surfaceia ao orquestrador**, não altera sozinho.

A lição das duas entregas anteriores vale aqui: **a camada 01 escreve todas as chaves de
configuração de uma vez**, e ninguém mais toca `configuracao.py`.

---

## 1. Os tipos (`src/second_brain/busca.py`, dono: camada 01)

```python
@dataclass(frozen=True)
class Citacao:
    """De onde uma afirmação veio — sempre um arquivo do vault ou uma fonte."""
    origem: str            # "diario/2026-09-03.md" | "linear:FN-1610" | "slack:#dev-codereview"
    trecho: str = ""       # o pedaço que sustentou a afirmação, quando houver


@dataclass(frozen=True)
class Resposta:
    """O que a busca devolve. `texto` vazio com `achou=False` é 'não sei'."""
    texto: str
    citacoes: tuple[Citacao, ...] = ()
    achou: bool = True
    custo_usd: float | None = None


class ErroDeBusca(RuntimeError):
    """A busca não pôde ser feita — sem credencial, sem rede, resposta ilegível."""


@runtime_checkable
class PortaBusca(Protocol):
    def perguntar(
        self,
        pergunta: str,
        ferramentas: "Ferramentas",
        historico: tuple["Turno", ...] = (),
    ) -> Resposta: ...
```

`Resposta.achou=False` é **resposta legítima**, não erro: "não achei isso no vault" é o que
impede o usuário de confundir invenção com memória. `ErroDeBusca` é para o que impediu a busca
de acontecer.

## 2. As ferramentas (`src/second_brain/ferramentas.py`, dono: camada 01)

O agente **não recebe o vault cru**. Recebe este objeto, e é aqui que a fronteira mora:

```python
class Ferramentas:
    def __init__(self, configuracao: Configuracao) -> None: ...

    def buscar_no_vault(self, termo: str, *, limite: int = 30) -> tuple[Achado, ...]: ...
    def ler_nota(self, caminho: str) -> str: ...
    def listar(self, pasta: str = "") -> tuple[str, ...]: ...
```

Regras que valem para **todas** elas, e que a camada 01 fixa em um ponto só:

- **Nenhuma abre nada fora do vault.** A checagem é no caminho **resolvido**, como
  `vault.escrever` já faz: `..` no meio não escapa.
- **Nenhuma abre nada sob `[privacidade].pastas_privadas`.** Nem em busca, nem em leitura, nem em
  listagem, nem sob pedido explícito do usuário. Um arquivo privado **não existe** para o agente.
- **Nenhuma escreve.** Escrita é outro caminho, sob pedido explícito na conversa, por
  `vault.escrever` com zonas (camada 04).
- Caminho recusado levanta `ForaDaFronteira`, que o adaptador traduz para o modelo como "esse
  arquivo não existe" — e **não** como "esse arquivo é privado". Dizer que existe algo escondido
  já é vazar o que a pasta privada promete esconder.

```python
@dataclass(frozen=True)
class Achado:
    caminho: str       # relativo ao vault
    linha: int
    trecho: str


class ForaDaFronteira(RuntimeError): ...
```

## 3. A costura (`src/second_brain/pergunta.py`, dono: camada 01)

```python
def responder(
    pergunta: str,
    *,
    configuracao: Configuracao,
    busca: PortaBusca,
    conversa: Conversa | None = None,
) -> Resposta
```

Ordem fixa:

1. Recusa pergunta vazia, com mensagem em português.
2. Monta `Ferramentas(configuracao)`.
3. Chama `busca.perguntar(pergunta, ferramentas, historico=conversa.historico if conversa else ())`.
4. Acrescenta a pergunta e a resposta ao fio da conversa.
5. `ErroDeBusca` sobe para quem chamou, que decide o que fazer.
6. Registra no log o que foi perguntado, quantas citações voltaram e o custo.

### O fio de 24 horas (`src/second_brain/conversa.py`, dono: camada 01)

```python
@dataclass(frozen=True)
class Turno:
    quem: str          # "usuario" | "agente"
    texto: str
    momento: datetime  # aware


class Conversa:
    """O fio de uma DM, que expira depois de 24h de silêncio."""
    def historico(self) -> tuple[Turno, ...]: ...
    def acrescentar(self, quem: str, texto: str, *, agora: datetime) -> None: ...
```

- **Expira por silêncio, não por relógio de parede**: 24 horas desde o **último** turno. Uma
  conversa ativa às 23h continua no dia seguinte; uma parada há 25 horas começa limpa.
- **Mora ao lado do `config.toml`**, em `conversas.json`, e **não no vault**: é rascunho de
  conversa, e o vault guarda memória durável, não rascunho.
- **O relógio é injetado** (`agora`), porque a expiração é comportamento e precisa de teste sem
  esperar 24 horas.
- Arquivo corrompido ou ilegível **não derruba o atendimento**: vale como conversa vazia.

## 4. Configuração — todas as chaves de uma vez (dono: camada 01)

```toml
[privacidade]
pastas_privadas = []       # pastas do vault que a busca nunca abre (relativas ao vault)

[busca]
maximo_de_notas = 40       # teto de notas lidas numa pergunta, para uma pergunta não varrer o vault
```

Campos achatados: `privacidade_pastas_privadas: tuple[str, ...] = ()` e
`busca_maximo_de_notas: int = 40`. `MODELO_DE_CONFIGURACAO` ganha as duas com comentário.
Configuração antiga continua carregando.

## 5. Como cada camada entra

| camada | entrega | não toca |
|---|---|---|
| 01 | `busca.py`, `ferramentas.py`, `conversa.py`, `pergunta.py`, as chaves, o fake | — |
| 02 | `busca_claude.py`: o adaptador real, o prompt, as tool definitions | `pergunta.py`, `ferramentas.py` |
| 03 | as fontes ao vivo como ferramentas, pelos coletores existentes | a fronteira da camada 01 |
| 04 | `atendente.py` + `second-brain atender`: a DM do Slack por Socket Mode | `busca.py`, `conversa.py` |
| 05 | logon, log, custo, `docs/smoke-atendente.md` | — |

A camada 04 é a única que depende da aprovação do admin. As três primeiras se provam pelo
comando de diagnóstico `second-brain perguntar`, que existe **para teste**, não como caminho
principal.

## 6. O que nenhuma camada deve fazer

- **Nenhuma dá ao modelo acesso a shell, a `Bash` ou ao sistema de arquivos direto.** A fronteira
  da pasta privada só existe porque todo acesso passa por `Ferramentas`.
- **Nenhuma camada além da 01 edita** `configuracao.py`, `busca.py`, `ferramentas.py` ou
  `pergunta.py`. Precisou? Surfaceia.
- **Nenhuma reimplementa coletor de fonte.** A camada 03 chama `fonte_git`, `fonte_linear` e
  `fonte_slack` pelas fábricas `de_configuracao` — é o que faz a blocklist do Slack e o
  `so_com_mencao` continuarem valendo na consulta ao vivo.
- **Nenhum teste novo fala com serviço real** fora de `@pytest.mark.rede`.
- **Nenhum segredo em teste, fixture ou doc.**

## 7. A demo-mestra

O gesto que fecha a entrega, na máquina do usuário, com o vault real:

> O usuário manda **na DM do Slack**, do celular: *"o que ficou decidido sobre a retenção de 180
> dias?"* — e a resposta chega ali, citando um arquivo do vault.

**Sucesso**: ele reconhece o arquivo citado, abre e confere. Depois manda uma pergunta de
acompanhamento (*"e quem levantou isso?"*) e o agente responde **sem ele repetir o assunto** —
que é a prova do fio de 24 horas. Se a decisão não estiver no vault, a resposta diz que não
achou, e isso também é sucesso.

## 8. Adendos da camada 01 (2026-09-04)

O que a camada 01 acrescentou ao contrato ao construí-lo. As camadas seguintes constroem
contra isto, não contra as seções 1 a 4 sozinhas.

- **`ferramentas.LimiteDeNotas`** — `ler_nota` levanta quando a pergunta já abriu
  `[busca].maximo_de_notas` notas distintas; reler uma nota aberta não conta, e leitura
  recusada também não. Sem isto a chave seria letra morta: `Ferramentas` nasce por pergunta e
  é o único ponto que sabe quantas notas foram lidas. **A camada 02 traduz para o modelo como
  "responda com o que já leu"** — não é erro, é o freio.
- **`Ferramentas.notas_lidas`** — o contador, para o log da costura.
- **Semântica da busca**: todas as palavras do termo na mesma linha, sem acento nem caixa
  (`retencao` acha `retenção`); dentro de cada pasta a nota mais recente vem primeiro; só `.md`;
  pastas que começam com `.` (`.obsidian/`, `.trash/`) ficam de fora. `listar` devolve caminhos
  relativos ao vault, com `/` no fim das subpastas.
- **A recusa é idêntica para o privado e para o inexistente**: `Não existe no vault: '<caminho>'`
  nos dois casos, testado pela igualdade da mensagem. Arquivo que não existe, pasta pedida como
  nota, caminho absoluto, `..` para fora e link para dentro da pasta privada caem na mesma frase.
- **`conversa.Conversas`** — o arquivo `conversas.json`, com `de_configuracao(configuracao)`,
  `abrir(chave, agora=...)` e `guardar(chave, conversa)`. **Abra o fio a cada mensagem, com
  `agora`**: é assim que a expiração é aplicada. A chave é a DM (camada 04) ou `"terminal"`
  (diagnóstico). Gravar um fio vazio remove a chave; gravar poda os outros fios já expirados;
  a escrita é em dois passos (`.tmp` + `os.replace`) porque o atendente fica no ar o dia todo.
- **`Conversa.expirar(agora)`** e **`Conversa.expirada(agora)`** — para quem segura o fio em
  memória. `responder` chama `expirar` antes de ler o histórico, então um fio parado há 25h
  nunca chega à busca mesmo sem reabrir do disco. Momento sem fuso ganha o fuso local.
- **`responder(..., agora=None)`** — o relógio do fio, injetado nos testes; `None` é o relógio
  da máquina. Levanta **`pergunta.PerguntaVazia`** (`ValueError`) para pergunta em branco.
  Quando a busca devolve texto vazio, o fio guarda `pergunta.SEM_RESPOSTA` ("Não achei.") no
  turno do agente, porque o fio guarda falas e uma fala em branco não serve à camada 02.
- **`conversa.USUARIO` / `conversa.AGENTE`** — os dois valores de `Turno.quem`.
- **`fakes.BuscaFake`** guarda `perguntas_recebidas`, `ferramentas_recebidas` e
  `historico_recebido`, e devolve `fakes.RESPOSTA_PADRAO`.
- **`[privacidade].pastas_privadas`** é validada: cada item precisa ser relativo e sem `..`
  (barra invertida e barra final são normalizadas). `[busca].maximo_de_notas` precisa ser
  inteiro ≥ 1.

## 9. Adendos da camada 02 (2026-09-04)

- **`busca_claude.FerramentasDoVault(ferramentas)`** — as três ferramentas como tools de um
  servidor MCP em processo chamado `vault`; `.tools()` devolve as `SdkMcpTool`, `.servidor()`
  o `McpSdkServerConfig`. **A camada 03 acrescenta as fontes ao vivo aqui**, como tools do
  mesmo servidor ou de um segundo, e as lista em `ferramentas_permitidas()` — é a única lista
  que o modelo enxerga (`mcp__<servidor>__<ferramenta>`). O modelo nasce com `tools=[]`: sem
  Bash, Read, Glob ou qualquer ferramenta nativa.
- **Tradução das recusas**, fixada nos handlers: `ForaDaFronteira` e `LimiteDeNotas` voltam
  como resultado com `is_error` e a mensagem da própria exceção; a leitura recusada, a
  inexistente e a privada produzem exatamente o mesmo texto. Um handler que levante outra
  exceção tem a mensagem devolvida ao modelo pelo SDK, não derruba a pergunta.
- **`FerramentasDoVault.chamadas`** e **`.vistos`** — o contador para o log e os caminhos que
  a busca ou a leitura mostraram ao modelo. `perguntar` não filtra citação; só o log aponta
  uma citação a caminho nunca visto.
- **Formato da resposta do modelo**: `{"resposta", "citacoes": [{"origem", "trecho"}], "achou"}`.
  `achou` ausente é deduzido das citações; citação como texto simples vira `origem`;
  `arquivo`/`caminho`/`fonte` valem como `origem`. **A camada 03 usa `origem` com prefixo de
  fonte** (`linear:FN-1610`, `slack:#canal`, `git:repositorio@hash`) — `interpretar_resposta`
  já deixa passar qualquer texto em `origem`.
- **O fio vai como texto no turno** (`montar_pergunta`), os últimos `TURNOS_NO_FIO = 20`
  turnos — não como sessão retomada do SDK, para a expiração de 24h ficar no nosso código.
- **`second-brain perguntar "<pergunta>" [--fakes] [--sem-fio]`** — o comando de diagnóstico.
  Fio na chave `"terminal"` de `conversas.json`; `0` respondeu, `3` respondeu sem achar,
  `1` não conseguiu (`ErroDeBusca`, `PerguntaVazia`, configuração), `2` erro de uso. A
  fábrica é `__main__.montar_busca(configuracao, fakes=)`; a camada 05 documenta os códigos
  no `--help` e o log já sai em `bandeja.log`.
- **`BuscaClaude(modelo=, timeout_s=240, maximo_de_turnos=40)`** — cada chamada de
  ferramenta é um turno; `max_turns` estourado vem como `ErroDeBusca` com o `subtype`.

## 10. Adendos da camada 03 (2026-09-04)

- **`fontes_ao_vivo.FontesAoVivo(fontes, *, excluir=(), relogio=None)`** — os coletores já
  construídos (`PortaFonte`) como tools `consultar_<fonte>` de um segundo servidor MCP,
  `fontes`. `tools()`, `servidor()` (`None` sem fonte), `nomes_permitidos()`, `chamadas`,
  `excluir`. Fonte desligada não está na lista, e por isso não vira ferramenta.
- **Cada tool aceita `horas` (1–336, padrão 24), `termo` e `limite` (padrão 40)** e devolve
  texto com uma linha por evento, **mais recente primeiro**, no formato
  `- <origem>  DD/MM HH:MM  título` + detalhe + `pessoas:` + `link:`. Origem: `git:<repo>@<hash>`,
  `linear:<FN-1234>`, `slack:<referência>`. Falha da fonte é resultado com `is_error` e
  "responda com o que o vault tem".
- **O filtro de exclusão age em `FontesAoVivo.consultar`**, num ponto só, sobre o que o
  coletor devolveu; blocklist e `so_com_mencao` vêm dentro do coletor do Slack.
- **`BuscaClaude(..., fontes_ao_vivo=)`** e **`busca_claude.montar_opcoes(vault, fontes, ...)`**:
  o segundo servidor e o adendo `PROMPT_DAS_FONTES_AO_VIVO` só entram quando há fonte.
- **`__main__.montar_busca`** reusa `montar_fontes`; `NenhumaFonteConfigurada` vira lista vazia
  (a busca responde só com o vault), não erro.
- **A camada 04 não precisa saber de nada disto**: o atendente chama `responder` com a busca
  que `montar_busca` devolve.

## 11. Adendos da camada 04 (2026-09-04)

- **`atendente.PortaDM`**: `iniciar() -> id do bot`, `proxima(timeout_s) -> Mensagem | None`,
  `reagir(mensagem, emoji)`, `responder(mensagem, texto)`, `encerrar()`. Erros da DM são
  `atendente.ErroDeDM`. `fakes.DMFake` entrega mensagens de fixture e, ao esvaziar, sinaliza
  `parar` ou levanta `KeyboardInterrupt` (o encerramento real).
- **`atendente.Mensagem(canal, usuario, texto, ts, tipo_de_canal, subtipo, do_bot)`**; só
  `tipo_de_canal == "im"`, sem `subtipo`, sem `do_bot`, de usuário diferente do bot e com texto
  é atendida.
- **O fio por DM**: chave = id do canal em `conversas.json`, aberto com `agora` a cada mensagem.
- **A única escrita**: `anotar <texto>` (prefixo, sem passar pelo modelo) → `vault.anotar_ponto`
  em `notas/daily.md`. Nenhuma outra mensagem escreve nada.
- **`dm_slack.DMSlack(app_token, bot_token, web=, socket=)`**, `mensagem_do_evento(evento)`,
  `de_configuracao(configuracao)`. Scopes de bot: `im:history`, `im:read`, `chat:write`,
  `reactions:write`; app-level token com `connections:write`; evento `message.im`.
- **Chaves novas**: `[slack].bot_token` (`xoxb-`) e `[slack].app_token` (`xapp-`), conferidas
  pelo prefixo. **Exceção registrada** à regra da seção 6: a camada 04 editou `configuracao.py`
  porque as chaves estavam no ticket dela e não na 01.
- **`second-brain atender [--fakes]`**: `--fakes` troca só a busca; a DM é sempre o Slack real.
  Trava própria em `atendente.lock`. Sai `0` no Ctrl+C, `1` sem tokens, sem Socket Mode ou com
  outra instância no ar.
- **Dependência nova**: `slack_sdk>=3.27`.
