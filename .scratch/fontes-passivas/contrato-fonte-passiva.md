# Contrato: fonte passiva, janela e diário

Decisão do orquestrador, fixada **antes** de abrir qualquer camada, para que os três
coletores (git, Linear, Slack) e o resumo do dia sejam construídos em paralelo contra
o mesmo formato. Não substitui nenhuma decisão da [spec](spec.md) — só fecha o que ela
deixou em aberto entre camadas. Executor que discordar **surfaceia ao orquestrador**,
não altera sozinho.

Vale a lição da entrega anterior: o [DEFERRED do tracer bullet](../tracer-bullet/DEFERRED.md)
registra que as camadas 01 e 02 duplicaram a leitura do TOML porque nenhum executor podia
tocar o arquivo do outro. Aqui isso é resolvido por construção — **a camada 01 escreve
todas as chaves de configuração das três fontes de uma vez**, e ninguém mais mexe em
`configuracao.py`.

---

## 1. Os tipos comuns (`src/second_brain/fontes.py`, dono: camada 01)

```python
@dataclass(frozen=True)
class Janela:
    """O intervalo que um diário cobre. Sempre com fuso, sempre meio-aberto."""
    data: date          # o dia a que o diário pertence
    inicio: datetime    # aware, inclusivo
    fim: datetime       # aware, exclusivo


@dataclass(frozen=True)
class Evento:
    """Um acontecimento do dia, no formato comum a toda fonte passiva."""
    fonte: str                        # "git" | "linear" | "slack"
    momento: datetime                 # aware, hora local
    titulo: str                       # uma linha, já legível em português ou no idioma original
    detalhe: str = ""                 # corpo opcional (texto da mensagem, do comentário)
    referencia: str | None = None     # onde aconteceu: repo, projeto, canal
    url: str | None = None            # link quando a fonte tiver um
    pessoas: tuple[str, ...] = ()      # quem aparece — alimenta o filtro e o resumo


class ErroDeFonte(RuntimeError):
    """A fonte não pôde ser lida. O diário nasce sem ela, marcado."""


@runtime_checkable
class PortaFonte(Protocol):
    nome: str
    def coletar(self, janela: Janela) -> tuple[Evento, ...]: ...
```

Regras que valem para **toda** implementação de `PortaFonte`:

- `coletar` devolve só eventos **dentro da janela**. Filtrar por tempo é da fonte, que
  sabe pedir isso à sua API; o diário não re-filtra.
- `momento` é sempre **aware**. Uma fonte que receba UTC converte para o fuso local antes
  de devolver — o agrupamento por dia e o `HH:MM` da nota dependem disso.
- Qualquer falha vira `ErroDeFonte` com mensagem em português que diga o que fazer
  ("token do Slack ausente em `[slack].user_token`"). Nunca deixe vazar `httpx.HTTPError`
  nem `CalledProcessError`: quem trata é a costura, e ela só conhece `ErroDeFonte`.
- Uma fonte **sem nada no dia** devolve tupla vazia. Isso não é falha.
- A ordem dos eventos não importa: a costura ordena por `momento`.

## 2. As portas de resumo (`src/second_brain/portas.py`, dono: camada 01)

Ficam ao lado de `Resumo`/`PortaResumo` porque são irmãs delas — o mesmo tipo de coisa
(serviço externo que resume em português), com entrada diferente.

```python
@dataclass(frozen=True)
class ResumoDoDia:
    narrativa: str = ""                 # dois ou três parágrafos sobre o dia
    destaques: tuple[str, ...] = ()
    pendencias: tuple[str, ...] = ()
    temas: tuple[str, ...] = ()         # vai para o frontmatter


class ErroDeResumoDoDia(RuntimeError):
    """Falha ao resumir o dia. O diário nasce sem narrativa, marcado."""


@runtime_checkable
class PortaResumoDoDia(Protocol):
    def resumir_dia(self, eventos: tuple[Evento, ...], reunioes: tuple[str, ...]) -> ResumoDoDia: ...
```

## 3. A costura (`src/second_brain/diario.py`, dono: camada 01)

```python
def gerar_diario(
    data: date,
    *,
    configuracao: Configuracao,
    fontes: Sequence[PortaFonte],
    resumo: PortaResumoDoDia,
    simular: bool = False,
) -> ResultadoDoDiario
```

Ordem de operações, fixa:

1. Monta a `Janela` a partir de `data` e `[diario].inicio_do_dia`.
2. Chama cada fonte **na ordem recebida**. `ErroDeFonte` é capturado e vira `FalhaDeFonte`;
   a execução continua nas outras.
3. Aplica o **filtro de exclusão** sobre tudo que voltou — este é o único ponto onde o
   filtro age, e é o que garante que nenhuma fonte possa esquecer dele.
4. Descobre as **reuniões da janela** no vault.
5. Se **todas** as fontes falharam → `TodasAsFontesFalharam`. Nada é escrito.
6. Se zero eventos **e** zero reuniões → dia vazio: `ResultadoDoDiario(vazio=True, nota=None)`,
   sem escrever.
7. Se `simular=True` → devolve o resultado sem chamar o resumo e sem escrever.
8. Chama o resumo. `ErroDeResumoDoDia` é capturado e registrado como falha; segue em frente.
9. Escreve `diario/YYYY-MM-DD.md`, **sobrescrevendo**.

```python
@dataclass(frozen=True)
class FalhaDeFonte:
    fonte: str
    motivo: str


@dataclass(frozen=True)
class ResultadoDoDiario:
    data: date
    janela: Janela
    nota: Path | None                              # None em dia vazio e em simulação
    eventos: tuple[Evento, ...]                    # já filtrados e ordenados
    excluidos: int                                 # quantos o filtro removeu
    fontes_lidas: tuple[str, ...]
    fontes_com_falha: tuple[FalhaDeFonte, ...]
    reunioes: tuple[str, ...]                      # caminhos relativos no vault
    resumo: ResumoDoDia | None
    vazio: bool = False
    simulado: bool = False


class TodasAsFontesFalharam(RuntimeError): ...
class NenhumaFonteConfigurada(RuntimeError): ...
```

`NenhumaFonteConfigurada` é levantada por quem monta a lista (a CLI), não pela costura:
lista vazia e "todas falharam" são problemas diferentes e merecem mensagens diferentes.

### A janela

```python
def janela_do_dia(data: date, inicio_do_dia: str = "04:00") -> Janela
def data_do_diario(agora: datetime, inicio_do_dia: str = "04:00") -> date
```

`janela_do_dia(date(2026, 9, 3), "04:00")` → `2026-09-03 04:00` (inclusivo) até
`2026-09-04 04:00` (exclusivo), no fuso local. `data_do_diario` é o inverso, usado pela
CLI quando o usuário não passa data: às 02:00 de 4 de setembro ela devolve `2026-09-03`.

### O filtro

```python
def filtrar(eventos: Iterable[Evento], padroes: Sequence[str]) -> tuple[tuple[Evento, ...], int]
```

Um evento é excluído se **algum** padrão aparecer como substring em `titulo`, `detalhe`,
`referencia` ou em qualquer item de `pessoas`. Comparação com `casefold()` dos dois lados;
padrões vazios ou só com espaço são ignorados. Devolve os eventos que ficaram e quantos
saíram.

**Substring, não regex** — de propósito. Regex em arquivo de configuração é armadilha: um
padrão mal escrito ou explode na cara do usuário ou casa com tudo e esvazia o diário em
silêncio. Se um dia precisar de mais poder, é decisão nova.

## 4. A nota (`src/second_brain/vault.py`, dono: camada 01)

Caminho: `diario/YYYY-MM-DD.md` — a data do diário, sem hora, um por dia.

```markdown
---
data: 2026-09-03
tipo: diario
janela: "2026-09-03T04:00:00-03:00 → 2026-09-04T04:00:00-03:00"
fontes: [git, linear]
fontes_com_falha: [slack]
temas: ["fontes passivas", "review do OMS"]
reunioes: ["[[reunioes/2026-09-03-1430-daily-do-time]]"]
---

# Diário — 3 de setembro de 2026 (quinta-feira)

> Slack não entrou neste diário: token ausente em [slack].user_token.

Narrativa do dia, em português, dois ou três parágrafos.

## Destaques

- ...

## Pendências

- ...

## Reuniões

- [[reunioes/2026-09-03-1430-daily-do-time]]

## Git

### second-brain

- 14:02 `62b55ce` Abre a proxima entrega com o handoff de fontes passivas

## Linear

### Plataforma

- 11:20 [FN-123 Corrigir o cálculo de frete](https://linear.app/...) — movida para Done
  > texto do comentário, quando houver
```

Regras da montagem:

- Uma seção por fonte, sempre na ordem **git, Linear, Slack**, com o nome capitalizado
  para leitura (`## Git`, `## Linear`, `## Slack`).
- Dentro da seção, `### <referencia>` por referência distinta, na ordem da primeira
  aparição. Evento sem `referencia` fica direto sob o `##`.
- Linha do evento: `- HH:MM <titulo>`, com o título virando link markdown quando houver
  `url`. `detalhe` entra como blockquote indentado na linha seguinte.
- Fonte que **rodou e não trouxe nada** ganha sua seção com `_(nada registrado)_` — é o que
  distingue "não houve" de "não está configurada".
- Fonte **não configurada** não aparece: nem na seção, nem em `fontes`.
- Fonte que **falhou** aparece em `fontes_com_falha`, na linha de aviso (`>`) logo abaixo do
  título, e sua seção diz o motivo. O aviso é obrigatório: um diário incompleto que se
  passa por completo é pior que um diário ausente.
- Sem resumo (Claude falhou ou não configurado): não há narrativa, `Destaques` nem
  `Pendências`; o aviso explica, e as listas cruas ficam.
- `_(nada registrado)_` para lista vazia, como já faz a nota de reunião.

### Zona de propriedade — a mudança que a camada 01 precisa fazer com cuidado

Hoje `vault.escrever` recusa `diario/`, e **isso é testado**
(`tests/test_zona_de_propriedade.py`, parâmetro `"diario/2026-08-20.md"`). Abrir a zona
globalmente quebraria a invariante do pipeline de reunião.

A mudança correta é tornar as zonas um **parâmetro por coletor**:

```python
def escrever(vault, relativo, conteudo, *, zonas=ZONAS_DE_ESCRITA) -> Path
ZONAS_DO_DIARIO = (PASTA_DIARIO,)
```

O pipeline de reunião segue com o padrão (`reunioes/`, `transcricoes/`); o diário passa
`zonas=ZONAS_DO_DIARIO`. Resultado: os testes existentes continuam valendo **sem alteração**,
o diário não consegue escrever em `reunioes/`, e `notas/` continua recusada para os dois.
A mensagem de recusa (`_recusa`) deixa de falar em "coletor de reunião" e passa a nomear as
zonas que aquela chamada permitia.

### Reuniões da janela

```python
def reunioes_na_janela(vault: Path, janela: Janela) -> tuple[str, ...]
```

Varre `reunioes/*.md` e lê o prefixo `YYYY-MM-DD-HHMM` do nome do arquivo (o basename do
[contrato da pasta de gravação](../tracer-bullet/contrato-pasta-gravacao.md)), montando um
datetime local. Ficam as que caem na janela — é o que faz uma reunião da meia-noite e meia
aparecer no diário do dia anterior, igual aos commits. Arquivo com nome fora do padrão é
ignorado em silêncio: `diario/` não pode quebrar por causa de um arquivo renomeado à mão.

## 5. Configuração — todas as chaves de uma vez (dono: camada 01)

`configuracao.py` é escrito **inteiro pela camada 01**, com as chaves das três fontes.
As camadas 02, 03, 05 e 06 **leem** `Configuracao` e não editam este arquivo.

```toml
[diario]
inicio_do_dia = "04:00"    # o diário de um dia vai desta hora até a mesma hora do dia seguinte
hora_da_tarefa = "19:00"   # quando a tarefa agendada gera o diário

[privacidade]
excluir = []               # trechos que nunca saem da máquina (substring, sem diferenciar maiúsculas)

[git]
raiz = ""                  # pasta onde varrer repositórios; vazio = fonte desligada
profundidade = 3
excluir = []               # pastas ignoradas na varredura
autores = []               # vazio = deduz do git config user.email de cada repositório

[linear]
api_key = ""               # Personal API Key read-only; vazio = fonte desligada

[slack]
user_token = ""            # user token xoxp da app interna; vazio = fonte desligada
conversas_excluidas = []   # canais e DMs que o coletor nunca lê
```

Campos correspondentes em `Configuracao` (achatados, como `deepgram_api_key` já é), todos
com padrão — configuração antiga continua carregando:

`diario_inicio_do_dia: str = "04:00"`, `diario_hora_da_tarefa: str = "19:00"`,
`privacidade_excluir: tuple[str, ...] = ()`, `git_raiz: Path | None = None`,
`git_profundidade: int = 3`, `git_excluir: tuple[str, ...] = ()`,
`git_autores: tuple[str, ...] = ()`, `linear_api_key: str = ""`,
`slack_user_token: str = ""`, `slack_conversas_excluidas: tuple[str, ...] = ()`.

Tuplas, não listas — o dataclass é `frozen`. `inicio_do_dia` e `hora_da_tarefa` são validados
no carregamento (`HH:MM`, 24h) e falham com `ConfiguracaoInvalida` didática, no mesmo
espírito da validação de `retencao_dias`. O modelo de `second-brain init`
(`MODELO_DE_CONFIGURACAO`) ganha as seções novas com estes comentários.

## 6. Como cada fonte entra na CLI (dono: camada 01; 02, 03 e 05 não editam)

A camada 01 escreve, em `__main__.py`:

```python
def montar_fontes(configuracao, *, fakes=False) -> list[PortaFonte]:
    if fakes:
        return [FonteFake(...)]
    fontes = []
    if configuracao.git_raiz:
        from . import fonte_git
        fontes.append(fonte_git.de_configuracao(configuracao))
    if configuracao.linear_api_key:
        from . import fonte_linear
        fontes.append(fonte_linear.de_configuracao(configuracao))
    if configuracao.slack_user_token:
        from . import fonte_slack
        fontes.append(fonte_slack.de_configuracao(configuracao))
    if not fontes:
        raise NenhumaFonteConfigurada(...)
    return fontes
```

O import é local e condicionado à chave: enquanto o módulo de uma fonte não existir, ela
simplesmente não é importada. Cada camada entrega **só** o seu módulo, com estas assinaturas
fixas:

| camada | módulo | fábrica | `nome` |
|---|---|---|---|
| 02 | `fonte_git.py` | `de_configuracao(configuracao) -> FonteGit` | `"git"` |
| 03 | `fonte_linear.py` | `de_configuracao(configuracao) -> FonteLinear` | `"linear"` |
| 05 | `fonte_slack.py` | `de_configuracao(configuracao) -> FonteSlack` | `"slack"` |
| 04 | `resumo_dia_claude.py` | `ResumoDoDiaClaude(modelo=None)` | — |

Mesmo padrão de `stt_deepgram.de_configuracao`, que já existe. Cada camada acrescenta **o
seu** teste do ramo correspondente de `montar_fontes`; a 01 testa só o caso "nada
configurado".

## 7. CLI (camada 01 abre; 06 completa)

```
second-brain diario [YYYY-MM-DD] [--fakes] [--simular] [--config ...]
```

- Sem data: `data_do_diario(agora)` — às 02:00 de quarta, gera o diário de terça.
- `--fakes`: fontes fake e resumo fake. Nada sai da máquina.
- `--simular`: coleta, filtra e **imprime** o que entraria, sem chamar o Claude e sem
  escrever no vault. É a ferramenta com que o usuário confere o filtro de exclusão
  (user story 10) — imprime também quantos eventos o filtro removeu.
- Sem `--fakes`, o resumo real vem de `resumo_dia_claude`, que só existe a partir da
  camada 04: até lá, o comando funciona com `--fakes` e `--simular`, e o caminho real
  levanta `ImportError`. Isso é esperado, não é regressão.

Agendamento (camada 06): `second-brain windows --diario` registra a tarefa diária
`SecondBrain-Diario` no mesmo mecanismo de `agendar_limpeza`, na hora de
`[diario].hora_da_tarefa`. O `--hora` que já existe continua sendo o da limpeza — dois
horários no mesmo flag confundiria; o do diário mora na configuração.

## 8. O que cada camada não deve fazer

- **Nenhuma camada acrescenta dependência nova** sem falar com o orquestrador. `httpx` já
  está no projeto e atende Linear e Slack; git é subprocesso. O ADR 0001 pede projeto fino.
- **Nenhuma camada além da 01 edita** `configuracao.py`, `fontes.py`, `diario.py`,
  `portas.py`, `vault.py` ou `montar_fontes`. Precisou? Surfaceia ao orquestrador.
- **Nenhum teste novo fala com serviço real** fora de `@pytest.mark.rede`. O `addopts` já
  desseleciona; o marcador é obrigatório.
- **Nenhum segredo em teste, fixture ou doc.** Token de exemplo é `xoxp-EXEMPLO`.

---

## 9. Adendo: a daily (camada 07, redesenhada com o usuário em 2026-09-03)

Escopo acrescentado depois de o primeiro diário real rodar, e **redesenhado** na mesma
conversa quando o usuário fixou duas coisas que viram o desenho anterior do avesso:

1. **A janela é da última daily até agora** — não um dia civil. Numa segunda-feira cobre o
   fim de semana inteiro.
2. **A daily é o arquivo que ele vai usar**; o diário ele não vai ler.

Consequência direta: a daily **não deriva do diário**. As duas janelas são recortes
diferentes (o diário é `04:00 → 04:00`; a daily é `última fala → agora`) e um não se
reconstrói do outro depois de resumido. A daily coleta sozinha e faz a própria chamada ao
Claude.

E como ela carrega também as listas cruas, **ela vira o registro durável** — é o que a
entrega seguinte (recuperação de contexto) vai ler. O diário continua existindo como
comando, mas **deixa de ser agendado**: uma chamada por dia serve para as duas coisas.

### A janela

```python
def janela_da_daily(agora: datetime, vault: Path) -> JanelaDaDaily
```

- `ate` = agora.
- `desde` = o campo `ate` da daily mais recente **de um dia anterior**. Sem nenhuma, cai
  para `agora - 24h` e a nota diz que foi a primeira.
- Rodar de novo no mesmo dia **mantém o `desde`** e estende o `ate` até agora,
  reescrevendo a nota daquele dia. É a mesma idempotência do diário: uma daily por dia,
  sempre regenerável, e nada nunca cai no vão entre a geração e a fala — o que acontecer
  depois entra na daily de amanhã.

A âncora vive no **frontmatter da nota anterior**, não num arquivo de estado escondido: o
vault é a fonte da verdade e o usuário consegue auditar a janela lendo a própria nota.

### O tipo (`portas.py`)

```python
@dataclass(frozen=True)
class Daily:
    entreguei: tuple[str, ...] = ()   # o que fechou ou andou — o trabalho DELE
    sigo_em: tuple[str, ...] = ()     # o que ficou em andamento
    preciso_de: tuple[str, ...] = ()  # o que depende de OUTRA PESSOA
    duvidas: tuple[str, ...] = ()     # pergunta aberta no material do dia
```

`off_topic` e os pontos livres **não** estão aqui: são do usuário, e vêm de `notas/daily.md`.

`preciso_de` é o que dá valor ao comando: só entra o que espera alguém — review parado, PR
sem merge, aprovação pendente. Nota para si mesmo ("faltou testar o estado expirado") não é
daily.

O prompt precisa distinguir **o trabalho dele** do **contexto do time**: os commits do git
são dele por construção (a fonte filtra por autor), mas o Linear traz o time inteiro — 172
eventos contra 28 commits, num dia real medido. `entreguei` e `sigo_em` são dele;
movimentação alheia é contexto, e no máximo vira `duvidas` ou `preciso_de`.

### Os pontos do usuário (`notas/daily.md`)

Mora na **zona do usuário**. O agente **lê** e nunca escreve por iniciativa própria — a
única exceção é `--anotar`, que é o "pedido explícito" que o glossário já prevê.

```markdown
# Daily — meus pontos

Marque o checkbox depois de falar: o que estiver marcado não aparece na próxima daily.

## Dúvidas
- [ ] o link coringa muda para todo mundo ou só para novos pedidos?

## Off-topic
- [ ] staging caiu duas vezes ontem à tarde

## Pontos
- [ ] quero puxar a conversa sobre a retenção de 180 dias
```

- Só entram na daily os itens **desmarcados** (`- [ ]`). O agente nunca marca nada: quem
  marca é o usuário, no Obsidian, depois de falar. É o gesto de consumir sem o agente
  encostar na zona dele.
- Arquivo ausente, seção ausente ou lista vazia **não é erro** — a daily só não mostra
  aquela seção.
- `second-brain daily --anotar "texto"` acrescenta em `## Pontos`, criando o arquivo com o
  cabeçalho acima se não existir. As outras duas seções se editam no Obsidian; ampliar o
  `--anotar` para elas é decisão de outro dia.

### A nota (`daily/YYYY-MM-DD.md` — zona nova)

`vault.ESTRUTURA` ganha `daily`; `ZONAS_DA_DAILY = ("daily",)`. O coletor de daily escreve
**só** ali, como o de diário só escreve em `diario/`.

```markdown
---
tipo: daily
data: 2026-09-04
desde: 2026-09-03T09:12:00-03:00
ate: 2026-09-04T09:05:00-03:00
fontes: [git, linear]
fontes_com_falha: []
temas: [...]
reunioes: ["[[reunioes/...]]"]
---

# Daily — 4 de setembro de 2026 (sexta-feira)

Cobre de quinta, 03/09 09:12, até agora.

## Entreguei
## Sigo em
## Preciso de
## Dúvidas
## Meus pontos
## Off-topic

## Reuniões
## Git
## Linear
## Slack
```

- As seis primeiras são o roteiro, na ordem de falar. `## Dúvidas` junta as do Claude e as
  desmarcadas do usuário; `## Meus pontos` e `## Off-topic` são só do usuário.
- Seção manual vazia **não aparece** — o roteiro não pode ter buraco para o usuário pular
  em voz alta.
- Da `## Reuniões` para baixo é a memória durável, no mesmo formato do diário (mesma
  função `_secao_da_fonte`, agrupada por referência).
- A linha "Cobre de ..." é obrigatória: sem ela o usuário lê a daily de sexta na segunda
  achando que é de ontem.

### O comando

```
second-brain daily [--anotar TEXTO] [--fakes] [--simular] [--config ...]
```

Sem argumento: coleta a janela, chama o Claude, escreve a nota e **imprime o roteiro** no
terminal, pronto para ler em voz alta. `--simular` coleta e imprime sem chamar o Claude e
sem escrever. `--anotar` só acrescenta em `notas/daily.md` e sai — não coleta nada.

Degradação igual à do diário: fonte que falha vira marca na nota; resumo que falha deixa a
nota nascer com as listas cruas e os pontos do usuário. **Nada é agendado** — o usuário
decidiu rodar na hora, um minuto antes de falar.

---

## 10. Adendo: o que o roteiro sabe do mundo (camada 08)

Escopo acrescentado em 2026-09-04, depois de o usuário ler a **primeira daily real**. Três
achados da mesma família: o roteiro precisa de fatos que os dados não carregam.

O que a daily real mostrou, e que nenhum teste pegaria:

1. **Projeto pessoal entrou na fala.** `[git].raiz` é a pasta de desenvolvimento inteira, e
   naquele dia **30 dos 52 commits** eram de projeto pessoal (`second-brain`, `renovo-hub`)
   contra 22 do trabalho. O Claude não errou: os commits são do usuário, e nada nos dados diz
   que um repositório é do trabalho e outro não.
2. **O roteiro inventou uma revisão humana.** Escreveu que cinco PRs esperavam "revisão humana e
   merge". No time do usuário **a aprovação do Zeno basta**, e **o merge é dele mesmo** — então
   aquelas PRs não dependem de ninguém e, pela regra do próprio prompt, não deviam estar em
   `preciso_de`. A inferência veio do nome do estado `In Review` no Linear.
3. **O link foi descartado.** A URL das PRs **já chegava ao Claude**, dentro do `detalhe` do
   comentário do Linear, e o modelo escreveu só `#1636`. Nada falta nos dados.

### As chaves novas (`configuracao.py`)

O contrato reserva `configuracao.py` à camada 01 (seção 8). **O orquestrador libera a camada 08
a editá-lo**, com exatamente estas duas chaves e nenhuma outra:

```toml
[daily]
referencias_pessoais = []      # repositórios e canais que são seus, não do trabalho
contexto_do_time = ""          # como o seu processo funciona, em texto livre, para o roteiro não inventar
```

Campos achatados em `Configuracao`, no padrão já existente:
`daily_referencias_pessoais: tuple[str, ...] = ()` e `daily_contexto_do_time: str = ""`.
`MODELO_DE_CONFIGURACAO` ganha a seção com estes comentários. Configuração antiga continua
carregando, e **lista vazia significa "tudo é trabalho"** — o comportamento de hoje, preservado
para quem não configurar nada.

A comparação é **substring com `casefold()`** contra `Evento.referencia`, como o filtro de
exclusão já faz. Evento **sem referência** é do trabalho.

**Lista-se o pessoal, não o trabalho** — e o motivo é a direção do erro. O que é do trabalho
cresce toda semana (projeto novo no Linear, repositório novo); o que é pessoal é um punhado de
coisas que o usuário conhece. Listar o trabalho faria todo projeto novo nascer **mudo** na
daily, e **ausência é mais difícil de notar que excesso**: projeto pessoal que sobrou ele vê ao
reler o roteiro antes de falar, e conserta em dez segundos; trabalho que sumiu, ele pode não
perceber. Nada se perde do vault em nenhum dos dois casos.

### Onde cada coisa age

| achado | mecanismo | por quê |
|---|---|---|
| trabalho vs. pessoal | **filtro**, antes de chamar a porta | o modelo pode escorregar; o que se fala na frente do time não pode depender de persuasão |
| processo do time | **texto no prompt** | errar produz frase imprecisa, não vazamento |
| link | **regra fixa do prompt** | vale para qualquer usuário, não é configuração |

O corte de trabalho/pessoal acontece em `daily.gerar_daily`, entre a coleta e a chamada da
porta. **A porta não muda de assinatura** e o adaptador não conhece o conceito:

- o que vai a `roteiro.resumir_daily(...)` é só o do trabalho;
- **`vault.montar_daily` continua recebendo todos os eventos** — as listas cruas guardam tudo,
  porque a daily é o registro durável do vault e a memória é do usuário, não do time.

`contexto_do_time` entra em `montar_pergunta_da_daily` como um bloco próprio, rotulado, depois
dos eventos. Vazio, nenhum bloco aparece.

### O que **não** muda

- **O diário não é tocado.** `gerar_diario` continua levando tudo ao Claude, projeto pessoal
  incluído: o diário é o retrato do dia civil **dele**, e silenciar metade do dia ali seria
  mentir sobre o dia que ele viveu.
- **As listas cruas da daily não perdem nada.** Se um teste passar filtrando os eventos da nota,
  a camada quebrou a decisão que faz a daily existir.
- **`evento.url` continua fora do prompt.** O DEFERRED registrou essa escolha na camada 04, e
  ela foi reconsiderada aqui: mandar a URL de ~260 eventos por dia para beneficiar duas linhas
  do roteiro não se paga. A camada 08 usa só o que **já está no material**, dentro do `detalhe`.
- **Nenhuma dependência nova**, e nenhum teste existente editado.

### O exemplo errado que está no prompt hoje

`PROMPT_DA_DAILY` ensina que `"os PRs #1623 e #1628 estão aguardando merge" entra, porque quem
faz o merge é outra pessoa`. Para este usuário isso é **falso**, e o exemplo empurra o modelo
para o erro que a daily real cometeu. O exemplo precisa parar de afirmar de quem é o merge — a
regra geral ("só o que depende de OUTRA PESSOA") já estava certa e continua valendo. Há testes
de prompt em `tests/test_roteiro_da_daily.py` que citam a frase antiga; a camada 08 **pode
editá-los**, e esta é a única exceção à regra de não tocar teste existente.

