# O Slack como painel, não só como pergunta

Levantado em 2026-09-10 contra fontes primárias — a documentação da API do Slack, o `slack_sdk`
instalado no `.venv`, o código do projeto e uma **medição das dailies reais do vault**. Nenhuma
chamada foi feita à API do Slack. Ticket: [03](../issues/03-slack-como-painel.md).

**Isto é levantamento, não decisão.**

---

## Resumo dos achados que mudam a decisão

1. **A daily entregue na DM não custa scope nenhum.** `im:write` é *"Start direct messages with
   people"* e cobre `conversations.open` — **não** o `chat.postMessage`. Como a DM
   `D0C1LAWCNHE` **já existe**, postar nela proativamente cabe no `chat:write` que a app já tem.
   Zero aprovação nova.
2. **Botões também não custam scope** — só a *Interactivity* ligada na configuração da app. E o
   envelope `interactive` já chega e já é confirmado pelo `dm_slack._receber`; o que falta é
   tratá-lo.
3. **Slash command custa um scope novo** (`commands`) e, com ele, reinstalação e uma segunda
   conversa com o admin. É o único item do "painel" que cobra isso.
4. **O roteiro da daily cabe folgado numa mensagem** — medido: **2.612 e 2.647 caracteres** nas
   duas dailies reais do vault, contra um teto de 50 blocos por mensagem. Dividido pelos seis
   cabeçalhos, a maior seção tem **1.088 caracteres** contra o limite de 3.000 de um bloco
   `section`. Não é apertado: é confortável.
5. **O `obsidian://` num botão é duvidoso e, no celular, inútil.** A documentação diz que `url`
   é *"A URL to load in the user's browser"*. Mas há um caminho melhor e já disponível: um botão
   **sem** `url`, cujo clique chega ao Whis pelo Socket Mode — e é o Whis, no PC, que abre o
   arquivo. Funciona apertando do celular.
6. **Pedir resposta mais curta ao modelo já foi tentado e não funcionou.** O
   `PROMPT_DA_BUSCA` **já** diz *"a resposta precisa ser curta, direta e verificável"* e repete
   *"curta e direta: ele lê no celular"* — e a resposta real saiu com 3.933 tokens. O conserto
   não é insistir no prompt.
7. **Imagem e áudio exigem `files:read`** — e esse é o item que força a segunda rodada com o
   admin. Mas há um bloqueio mais barato antes dele: hoje o Whis descarta a mensagem **antes**
   de olhar o arquivo, porque `_e_para_mim` exige `subtipo is None` e um arquivo chega com
   `subtype: "file_share"`.

---

## 1. O que o transporte já entrega

Socket Mode entrega cinco tipos de envelope — `hello`, `disconnect`, `events_api`,
`slash_commands` e `interactive` ([Using Socket Mode][socket]) — e a documentação é explícita:
*"When using Socket Mode, your app does not need a Request URL to use the Events API."* Vale
igualmente para interatividade e slash commands. **Nada disto pede servidor nem URL pública**, o
que mantém o ADR 0001 de pé.

No código do projeto (`dm_slack._receber`), a ordem é:

```python
if requisicao.envelope_id:
    cliente.send_socket_mode_response(SocketModeResponse(envelope_id=requisicao.envelope_id))
if requisicao.type != "events_api":
    return
```

Ou seja: **todo envelope já é confirmado, e todo envelope que não é `events_api` é jogado fora em
seguida.** Botão e slash command já *chegam* na máquina dele hoje; ninguém os lê.

Um detalhe do SDK que importa para slash command: `SocketModeResponse` aceita `payload`
opcional (`slack_sdk/socket_mode/response.py`), e a documentação confirma o formato
`{"envelope_id": <id>, "payload": <payload>}`. É por aí que uma resposta imediata cabe dentro da
própria confirmação — o freio contra o limite de 3 segundos.

---

## 2. Botões (Block Kit)

**Scope:** nenhum novo. Blocos vão no mesmo `chat.postMessage` que já é usado.

**Configuração da app:** *Interactivity* precisa ser ligada. Com Socket Mode, **sem Request URL**.

**O clique:** chega como envelope `interactive` e **precisa ser confirmado**. Vale inclusive para
o botão que só abre uma URL: *"If you're using `url`, you'll still receive an interaction payload
and will need to send an acknowledgement response"* ([button element][button]).

**Limites do botão:** `text` até 75 caracteres, `value` até 2.000, `url` até 3.000.

### O `obsidian://` num botão

A documentação define `url` como *"A URL to load in the user's browser when the button is
clicked"*. **Não consegui confirmar em fonte primária** se o Slack aceita um esquema que não seja
`http`/`https` nesse campo — a documentação não diz nem que aceita nem que recusa. E há um
problema que independe disso: **no celular não existe Obsidian de desktop para abrir**, e é do
celular que ele usa a DM.

O caminho que contorna os dois problemas já está disponível: **um botão sem `url`, com
`action_id`**. O clique vira envelope `interactive`, que chega ao processo do Whis rodando no PC
por Socket Mode, e **é o Whis quem abre a nota localmente** — com o `obsidian://` que já está
registrado na máquina dele (verificado no ticket 02), ou simplesmente abrindo o arquivo. Apertar
do celular abre a nota no PC. Não custa scope nenhum e usa o transporte que já existe.

Verificado na máquina: `HKCU:\SOFTWARE\Classes\obsidian` existe, com handler
`Obsidian.exe "%1"`.

---

## 3. Slash commands

**Scope: `commands`** — *"add shortcuts and/or slash commands that people can use"*
([Scopes][scopes]). É **scope novo**, logo reinstalação da app e, pela política que o workspace já
demonstrou, uma segunda conversa com o admin.

Funciona por Socket Mode (envelope `slash_commands`, sem Request URL). O limite de resposta de 3
segundos se resolve confirmando na hora — com `payload` na própria confirmação, ou com uma
mensagem de "estou procurando" seguida de follow-up.

**Não confirmado:** por quanto tempo o `response_url` de um slash command continua válido e
quantas vezes pode ser usado. Não achei o número em fonte primária nesta rodada.

**Vale a pergunta de produto:** o que `/daily` daria que *"gera a daily"* escrito na DM não dá?
A DM já entende texto, já custa zero scope e já funciona. O slash command ganha descoberta
(aparece na lista de comandos do Slack) e perde uma rodada de aprovação.

---

## 4. A daily entregue na DM

**Este é o achado mais barato de todos.** O bot pode postar na DM **sem o usuário falar primeiro**,
com os scopes de hoje:

- `im:write` é *"Start direct messages with people"* e cobre `conversations.archive`,
  `conversations.close`, `conversations.create`, `conversations.kick`, `conversations.leave`,
  `conversations.mark`, `conversations.rename`, `conversations.unarchive` e
  `conversations.open` — **`chat.postMessage` não está na lista** ([im:write][imwrite]).
- A DM com o bot **já existe** (`D0C1LAWCNHE`, provada em 10/09), então não há o que abrir.

Logo: **`chat:write` basta**. A daily pode aparecer na DM às 9:55 sem nenhuma aprovação nova.

O que falta no código é guardar o id da DM: hoje o atendente só o conhece quando uma mensagem
chega (`Mensagem.canal`), e um processo que gera a daily não tem de onde tirá-lo. É decisão de
implementação, não de permissão.

**Não confirmado:** se o workspace tem alguma política que trate mensagem não solicitada de app de
forma diferente. E `chat.scheduleMessage` foi descartado no levantamento por não servir ao caso —
ele agenda um **texto que você já tem**, e o roteiro da daily só existe depois de gerado.

---

## 5. Tamanho: medido contra as dailies reais

Limites oficiais:

| o quê | limite | fonte |
|---|---|---|
| blocos por mensagem | **50** (*"You can include up to 50 blocks in each message"*) | [Block Kit][blockkit] |
| `text` de um bloco `section` | **3.000** caracteres | [section block][section] |
| `fields` de um `section` | 10 itens, 2.000 caracteres cada | [section block][section] |
| `text` de um botão | 75 caracteres | [button element][button] |

Medido em `C:\Users\gabri\whis-vault\daily\`, nas duas dailies que existem:

| nota | nota inteira | **só o roteiro** | maior seção do roteiro |
|---|---|---|---|
| `2026-09-04.md` | 138.916 caracteres | **2.647** | `## Entreguei`, 871 |
| `2026-09-08.md` | 493.113 caracteres | **2.612** | `## Entreguei`, 1.088 |

O roteiro tem sempre os mesmos seis cabeçalhos — *Entreguei, Sigo em, Preciso de, Dúvidas, Meus
pontos, Reuniões* — e **nenhum deles chega perto do teto de 3.000 de um bloco**. Seis blocos
`section`, mais um cabeçalho e uma linha de botões, dá **oito blocos de cinquenta**.

Duas leituras disso:

- **O roteiro cabe numa mensagem com folga.** Não há problema de tamanho a resolver.
- **O que não cabe são as listas cruas** — 139 mil e 493 mil caracteres. Mas elas nunca foram
  para a DM e não precisam ir: a nota no vault é o registro durável, e a DM pode linkar.

Atenção a um detalhe: o roteiro inteiro num **único** bloco `section` daria 2.647 de 3.000 —
**88% do teto**. Um dia mais movimentado estoura. Dividir por cabeçalho não é refinamento, é o que
mantém a coisa de pé.

---

## 6. Imagem e áudio na DM

O achado do DEFERRED, que o usuário levantou antes de qualquer outra coisa. São **três**
obstáculos, não um, e só o terceiro envolve o admin:

1. **O filtro do próprio Whis descarta antes de olhar.** Uma mensagem com arquivo chega com
   `subtype: "file_share"` (*"A file was shared into a channel"*, [message event][message]), e
   `atendente._e_para_mim` exige `mensagem.subtipo is None`. Por isso não sai nem o 👀. **Isto é
   uma linha de código e não custa permissão nenhuma** — mas mudá-la sem o resto só faz o Whis
   reagir a um arquivo que ele continua não sabendo ler.
2. **`dm_slack.mensagem_do_evento` lê só `text`.** O array `files` do evento é ignorado na
   tradução para `Mensagem`. Também é código.
3. **Baixar o arquivo exige `files:read`** — *"retrieve both information about files uploaded to
   workspaces as well as download those files"* ([files:read][filesread]) — usando
   `url_private_download` com `Authorization: Bearer xoxb-...`. **É aqui que entra a segunda
   rodada com o admin**, e é um scope novo além dos quatro.

Para **áudio**, há um quarto passo: transcrever antes de mandar ao modelo. A Deepgram já está no
projeto, com crédito, e o pipeline de reunião já sabe fazer isso — mas o formato do áudio do
Slack e a rota de arquivo curto não foram verificados aqui.

**Não confirmado:** se o Slack já entrega transcrição própria dos *audio clips* no payload do
arquivo (o que pouparia a Deepgram), e como o modelo do Claude Agent SDK recebe uma imagem nesta
costura. Os dois valem checagem antes de qualquer spec.

---

## 7. "Sem personalidade, informação direta" — o que hoje viola

A regra saiu da reunião de demo de 04/09. Onde o texto de hoje nasce:

**Do modelo** (`busca_claude.PROMPT_DA_BUSCA`). E aqui está o achado que importa: **o prompt já
pede resposta curta, duas vezes.**

> *"Ele pergunta pelo Slack, muitas vezes do celular, no meio do trabalho — a resposta precisa ser
> curta, direta e verificável."*
>
> *"Em português do Brasil, curta e direta: ele lê no celular."*

E ainda assim a primeira pergunta real produziu **3.933 tokens de saída**. **Insistir no prompt já
é o estado atual.** O que sobra como caminho é estrutural: um teto de caracteres no campo
`resposta`, um formato de saída que não comporte prosa longa, ou um corte na formatação — não um
adjetivo a mais na instrução.

**Do formatador** (`atendente.formatar_para_slack`). O bloco de fontes é montado assim:

```python
f"• `{citacao.origem}`" + (f" — {_mrkdwn(citacao.trecho)}" if citacao.trecho else "")
```

Uma linha por citação, **com o trecho inteiro**. Na demo real foram **7 citações de 4 notas** — 7
linhas de texto citado penduradas no fim da resposta. E o `trecho` é, por definição do prompt,
*"uma frase copiada"* da nota.

Isto sustenta a hipótese que o handoff pediu para testar no *grilling*: o que incomoda pode ser o
**tamanho do bloco de fontes**, não a existência da fonte. Duas saídas óbvias aparecem sem mexer
na decisão dele de *"toda resposta cita"*: mostrar só `origem` (sem o trecho), ou agrupar por
nota — 4 linhas em vez de 7.

---

## 8. O que cabe nos scopes de hoje

A tabela que mais vale para a decisão. Scopes de bot atuais: `im:history`, `im:read`,
`chat:write`, `reactions:write`.

| capacidade | cabe hoje? | o que exige |
|---|---|---|
| **daily entregue na DM, proativa** | **sim** | nada — `chat:write` basta, a DM já existe |
| **botões (Block Kit)** | **sim** | *Interactivity* ligada na app; tratar o envelope `interactive` |
| **botão que abre a nota no PC** | **sim** | idem — o clique chega por Socket Mode e o Whis abre |
| **botão com `url:` `obsidian://`** | **duvidoso** | não confirmado que o Slack aceite; inútil no celular |
| **resposta em thread** | sim | nada — é um campo do `chat.postMessage` |
| **encurtar resposta e bloco de fontes** | sim | só código (`busca_claude` e `formatar_para_slack`) |
| **slash commands** (`/daily`, `/anota`) | **não** | scope **`commands`**, reinstalação, admin |
| **ler imagem na DM** | **não** | scope **`files:read`**, reinstalação, admin — mais dois consertos de código antes |
| **ler áudio na DM** | **não** | `files:read` + transcrição (Deepgram já está no projeto) |

---

## Fontes

- [Using Socket Mode — tipos de envelope, dispensa de Request URL, formato da confirmação][socket]
- [Button element — `url`, `text`, `value` e a exigência de confirmar mesmo com `url`][button]
- [Block Kit — até 50 blocos por mensagem][blockkit]
- [Section block — 3.000 caracteres de `text`, 10 `fields` de 2.000][section]
- [Scopes — o scope `commands`][scopes]
- [im:write — descrição e métodos cobertos][imwrite]
- [files:read — ler informação e baixar arquivos][filesread]
- [message event — o subtype `file_share`][message]
- Código do projeto: `src/whis/dm_slack.py`, `src/whis/atendente.py`, `src/whis/busca_claude.py`
- SDK instalado: `slack_sdk/socket_mode/request.py` e `response.py`
- Medição: `C:\Users\gabri\whis-vault\daily\2026-09-04.md` e `2026-09-08.md`

[socket]: https://docs.slack.dev/apis/events-api/using-socket-mode
[button]: https://docs.slack.dev/reference/block-kit/block-elements/button-element
[blockkit]: https://docs.slack.dev/block-kit/
[section]: https://docs.slack.dev/reference/block-kit/blocks/section-block
[scopes]: https://api.slack.com/scopes
[imwrite]: https://docs.slack.dev/reference/scopes/im.write/
[filesread]: https://docs.slack.dev/reference/scopes/files.read/
[message]: https://docs.slack.dev/reference/events/message/
