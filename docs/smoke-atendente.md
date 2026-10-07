# Smoke manual: o agente na DM do Slack

Roteiro para pôr o agente no ar: a app do Slack ganha um bot, o admin aprova de
novo, `whis atender` sobe e você pergunta ao seu vault pela DM — do PC
ou do celular. É a validação do que fica fora da costura de teste automatizada:
o Socket Mode de verdade, a conta Claude de verdade, o seu vault.

Tempo: ~20 minutos seus, mais o tempo que o admin levar. **Nada disto bloqueia
o resto**: a daily, o diário e o coletor do Slack continuam funcionando enquanto
o bot espera aprovação, e `whis perguntar` já responde no terminal.

Rode tudo de dentro do repositório, com o interpretador do ambiente virtual. Nos
exemplos abaixo, `python` significa `.venv\Scripts\python.exe`.

Pré-requisitos: o [smoke do Slack](smoke-slack.md) já passou (a app interna
existe e o user token funciona), e há uma conta Claude logada nesta máquina
(`claude login`), sem `ANTHROPIC_API_KEY` no ambiente.

## O que muda na app, e por quê

O coletor lê o Slack com o **user token** (`xoxp-`), e o roteiro dele prometeu ao
admin que a app **não pediria bot token**. Isso muda agora, e o pedido precisa
ser refeito — o texto está no passo 5.

O motivo: para **receber** mensagem, o Slack exige Socket Mode, que só funciona
com um **app-level token** (`xapp-`) e um **bot** (`xoxb-`). A alternativa —
responder na sua auto-DM postando como você, com `chat:write` no user token —
foi recusada: um `chat:write` de usuário permite postar **como você em qualquer
conversa do workspace**. Um bot que só lê e escreve na própria DM é bem menos
invasivo, e mais fácil de o admin aprovar.

O que o bot alcança, e só isso:

| scope de bot | para quê |
|---|---|
| `im:read` | saber que a DM com ele existe |
| `im:history` | ler o que **você** manda **na DM dele** |
| `chat:write` | responder **nessa DM** |
| `reactions:write` | reagir com 👀 assim que recebe, para você saber que ele está procurando |

Um bot **não vê canal nenhum** em que não foi convidado, e ninguém vai convidá-lo.
Ele não vê suas outras DMs. E nada é publicado fora da DM dele.

## Como o atendente termina

`whis atender` fica no ar até o `Ctrl+C` (ou até o logoff, quando sobe
com o Windows). Ele sai com `1` quando não consegue subir — sem os tokens, com
o Socket Mode desligado, com outra instância já no ar — e diz por quê no
terminal e em `bandeja.log`.

`whis perguntar` é o comando de diagnóstico, e o código de saída dele
diz o que aconteceu com a pergunta:

| código | significado |
|---|---|
| `0` | respondeu, citando o vault ou uma fonte |
| `3` | respondeu **sem achar**: nenhuma nota sustenta uma resposta, e ele disse isso |
| `1` | não conseguiu: sem conta Claude, API key paga no ambiente, pergunta vazia, configuração inválida |
| `2` | erro de uso (argumento inválido) |

Toda pergunta — pelo terminal ou pela DM — deixa rastro em
`%APPDATA%\whis\bandeja.log`: a pergunta, quantas citações voltaram,
quantas notas foram lidas, e o custo equivalente na tabela da API (a
assinatura **não** cobra por token; o número é medida relativa de cota).

## Passo 1 — Os quatro scopes de bot

Em <https://api.slack.com/apps>, abra a app `Whis (diário)`. Em
**OAuth & Permissions → Scopes → Bot Token Scopes**, acrescente exatamente:
`im:history`, `im:read`, `chat:write`, `reactions:write`.

Os scopes vêm **antes** do bot: o Slack só libera as abas do App Home depois
que o bot token tem pelo menos um scope (a página diz *"First, assign a scope to
your bot token"*, com o botão *Review Scopes to Add*, que leva a esta tela).

**Não** mexa nos *User Token Scopes*: os nove do coletor continuam como estão.

**Sucesso:** *Bot Token Scopes* tem esses quatro e mais nada.

## Passo 2 — Dar um bot à app

De volta em **App Home**:

1. **App Display Name → Edit**: nome `Whis`, username `whis`.
   Isso cria o bot user.
2. **Show Tabs**, agora destravado: ligue **Messages Tab** e marque *Allow
   users to send Slash commands and messages from the messages tab*. Sem isso a
   DM com o bot existe, mas não aceita mensagem.

**Sucesso:** a app aparece na sua lista de apps do Slack com uma aba
*Messages*.

## Passo 3 — Ligar o Socket Mode e gerar o app-level token

Em **Socket Mode**, ligue *Enable Socket Mode*. O Slack pede para criar um
**App-Level Token**: nome `atendente`, scope `connections:write`. Copie o token
— começa com `xapp-`.

Socket Mode é uma conexão **de dentro para fora**: o PC abre um websocket até o
Slack. Sem servidor, sem porta aberta, sem URL pública — nada muda no seu
roteador nem no firewall.

**Sucesso:** *Socket Mode* aparece como *Enabled* e o token `xapp-` está copiado.

## Passo 4 — Assinar o evento da DM

Em **Event Subscriptions**, ligue *Enable Events* (com Socket Mode ligado, não há
URL para preencher) e, em **Subscribe to bot events**, acrescente `message.im`.
Salve.

**Sucesso:** `message.im` listado em *Subscribe to bot events*, e a página pede
para reinstalar a app.

## Passo 5 — Pedir a aprovação nova do admin

O pedido anterior dizia que a app não pediria bot token. Diga ao admin, com
todas as letras, o que mudou — é tudo verdade e é o que ele precisa para
decidir:

> A app **interna** `Whis (diário)`, que você aprovou só com scopes de
> leitura no user token, precisa agora de um **bot** — para eu mandar mensagem
> para ela e ela me responder, numa DM só entre mim e ela.
>
> O bot pede quatro scopes: `im:read` e `im:history` (ler **a DM comigo**),
> `chat:write` (responder **nessa DM**) e `reactions:write` (reagir à minha
> mensagem). Um bot não enxerga canal em que não foi convidado, e ninguém vai
> convidá-lo; ele não enxerga outras DMs. Preferi o bot a pedir `chat:write` no
> user token justamente porque `chat:write` de usuário permitiria postar como eu
> em qualquer conversa, e o bot só fala na própria DM.
>
> A conexão é por **Socket Mode**: sai do meu PC para o Slack, sem URL pública
> nem porta aberta. O evento assinado é só `message.im`. Continua sem
> distribuição, sem `search:read`, e os tokens ficam só na minha máquina —
> revogáveis a qualquer momento em Manage apps.

**Sucesso:** a app aparece aprovada (de novo) em *Manage apps*.

**Falha:** se o admin recusar o bot, nada do resto quebra. Deixe
`[slack].bot_token` e `[slack].app_token` vazios: o atendente não sobe, e
`whis perguntar` continua respondendo no terminal.

## Passo 6 — Reinstalar e colar os dois tokens

Em **OAuth & Permissions → Reinstall to Workspace**, autorize. Agora a página
mostra **dois** tokens:

- **User OAuth Token** (`xoxp-`) — o do coletor. Ele **muda** na reinstalação:
  cole o novo em `[slack].user_token`.
- **Bot User OAuth Token** (`xoxb-`) — o do atendente.

Em `%APPDATA%\whis\config.toml`:

```toml
[slack]
user_token = "xoxp-...o novo..."
bot_token = "xoxb-...cole aqui..."
app_token = "xapp-...o do passo 3..."
```

A configuração confere o prefixo de cada um: se você colar o `xoxp-` no lugar
do `xoxb-`, o comando recusa e diz qual é qual, em vez de subir e falhar na
primeira mensagem.

**Sucesso:**

```
python -m whis perguntar --fakes --sem-fio "teste"
```

imprime a resposta de exemplo e sai `0` — a configuração carrega.

## Passo 7 — Ensaiar a DM sem gastar a assinatura

```
python -m whis atender --fakes
```

`--fakes` troca **só a busca** pelo fake; o Slack é o de verdade. No Slack, abra
a DM com `Whis` (procure pelo nome em *Apps*) e mande qualquer coisa.

**Sucesso:** em um ou dois segundos sua mensagem ganha a reação 👀 e o bot
responde com a resposta de exemplo (*"A retenção ficou em 180 dias..."*),
citando `reunioes/2026-09-03-1403-reuniao.md` embaixo de *Fontes:*. O
terminal e o `bandeja.log` mostram `Mensagem na DM D0...`.

Do celular também: a mesma DM, a mesma resposta. Depois, `Ctrl+C` encerra.

**Falha — não sobe:**

```
O atendente precisa de [slack].bot_token e [slack].app_token na configuração...
```

Volte ao passo 6.

```
Não consegui abrir o Socket Mode: ... Confira se o Socket Mode está ligado na app
e se [slack].app_token tem o scope connections:write.
```

Volte ao passo 3.

**Falha — sobe, mas não responde:** o evento não está chegando. Confira o
passo 4 (`message.im` assinado) e o passo 2 (*Messages Tab* ligada), e
reinstale a app depois de qualquer mudança.

**Falha — responde, mas sem o 👀:** falta `reactions:write` (passo 1). A resposta
sai mesmo assim, e o log registra o aviso.

**Falha — `já existe um atendente ... rodando`:** outra instância está no ar
(o atalho de logon, talvez). Feche-a antes, ou deixe-a: uma só basta.

## Passo 8 — A demo-mestra, com o Claude de verdade

Antes, uma pergunta pelo terminal, para separar "o Claude não respondeu" de "o
Slack não entregou":

```
python -m whis perguntar --sem-fio "o que ficou decidido sobre a retenção de 180 dias?"
```

Este passo **gasta a assinatura**. **Sucesso:** a resposta cita um arquivo do
vault (`diario/2026-09-03.md`, por exemplo), o código de saída é `0`, e o log
tem a linha `Pergunta ao Claude: equivalente a US$ ...`. Se sair `3` com
*"não achei"*, também vale: significa que a decisão não está no vault, e o
agente **não inventou**.

Agora o agente de verdade:

```
python -m whis atender
```

E, **do celular**, na DM do bot:

1. *"o que ficou decidido sobre a retenção de 180 dias?"* — a resposta chega em
   dezenas de segundos, com o 👀 antes. **Sucesso:** você reconhece o arquivo
   citado, abre no Obsidian e confere.
2. *"e quem levantou isso?"* — **sem repetir o assunto**. **Sucesso:** o agente
   entende que "isso" é a retenção. É a prova do fio de 24 horas.
3. *"o que aconteceu no Slack na última hora?"* — **Sucesso:** a resposta cita
   com origem `slack:#canal`, e não com um caminho de nota: veio da fonte ao
   vivo, pelo mesmo coletor da daily, com a mesma blocklist.

Se a decisão não estiver no vault, a resposta diz que não achou, e isso também
é sucesso.

## Passo 9 — A pasta privada

Escolha uma pasta do vault que a busca **nunca** deve abrir. Ela ainda não
existe na sua configuração — a lista nasce vazia, que significa vault inteiro
visível.

```toml
[privacidade]
pastas_privadas = ["notas/pessoal"]
```

Crie `notas/pessoal/teste.md` no Obsidian com um fato que não existe em nenhum
outro lugar do vault — *"a senha do cofre é abacaxi"* serve. Reinicie o
atendente (ele lê a configuração ao subir) e pergunte na DM: *"qual é a senha
do cofre?"*

**Sucesso:** *"Não achei nada sobre isso no vault"* — e **nenhuma** menção a
arquivo privado, pasta escondida ou coisa parecida. Para o agente, o arquivo
não existe. Pergunte ainda *"o que tem em notas/pessoal/teste.md?"*: a resposta
é a mesma.

Depois, tire a linha de teste ou deixe a pasta como a sua pasta privada de
verdade.

## Passo 10 — Anotar um ponto pela DM

Na DM: *"anotar preciso do acesso ao Sentry"*.

**Sucesso:** *"Anotado em `daily/atual.md`, em *Pontos*..."*, e a linha
`- preciso do acesso ao Sentry` aparece no fim de `## Pontos` da nota viva, sem
que nenhum outro byte dela mude. Nenhuma outra mensagem escreve no vault: é o
único caminho, e ele não passa pelo Claude.

## Passo 11 — Subir com o Windows

```
python -m whis windows --atendente
```

**Sucesso:** dois atalhos na pasta de Inicialização — `Whis.lnk` (a
bandeja) e `Whis Atendente.lnk` — e o comando diz isso. No próximo logon
o atendente sobe sozinho, sem console, e o rastro dele fica só em
`bandeja.log`.

Para desfazer: `python -m whis windows --atendente --remover`.

## Se precisar revogar

Em api.slack.com/apps → sua app → **OAuth & Permissions → Revoke All OAuth
Tokens**, e apague `[slack].bot_token` e `[slack].app_token`. O atendente para
de subir; o coletor precisa de um user token novo (passo 4 do smoke do Slack).

## Quanto pesa na assinatura

Cada resposta é uma sessão de agente com ferramentas: várias buscas e leituras
de nota, e às vezes uma consulta ao vivo. A linha `Pergunta ao Claude:
equivalente a US$ ...` no log diz o peso de cada uma — o valor **não é
cobrança**, é o equivalente da tabela da API, para você medir se o hábito ficou
pesado na cota. Anote o das primeiras perguntas reais aqui, para o próximo a
ler saber o que esperar.

Medido na primeira pergunta real, em 2026-09-09: *"o que ficou decidido
sobre a retencao de 180 dias?"* custou o equivalente a **US$ 0,5589**, com 18
turnos, 17 chamadas de ferramenta e 63 segundos de espera. Voltou com 7 citacoes
de 4 notas (`diario/2026-09-03.md`, `daily/2026-09-04.md`, `daily/2026-09-08.md`)
e a resposta certa. Para comparar: uma daily de um dia custa ~US$ 0,70.

Os freios: `[busca].maximo_de_notas` (padrão 40 notas por pergunta) e o teto de
turnos do agente. Uma pergunta que estoura qualquer um deles termina com o que
já leu.
