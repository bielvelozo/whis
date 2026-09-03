# Smoke manual: fonte passiva do Slack

Roteiro para ligar o Slack no diário. É a validação do que fica fora da costura
de teste automatizada: a app de verdade, contra a API de verdade.

Tempo: ~15 minutos seus, mais o tempo que o admin do workspace levar para
aprovar. **O diário nasce sem o Slack enquanto isso** — marcado, com o motivo
na nota. Não é preciso esperar a aprovação para usar as outras fontes.

Rode tudo de dentro do repositório, com o interpretador do ambiente virtual. Nos
exemplos abaixo, `python` significa `.venv\Scripts\python.exe`.

## O que este coletor lê

As conversas de que **você é membro**, dentro da janela do dia: canais públicos,
canais privados, group DMs e **DMs**. De cada uma, as mensagens do dia e as
respostas das threads abertas no dia.

Ele **só lê**. Nada é postado, editado, reagido ou marcado como lido pelo Second
Brain — nenhum scope de escrita é pedido.

Duas camadas de privacidade, nesta ordem:

1. **`[slack].conversas_excluidas`** — a blocklist. Conversa listada aqui **não
   é sequer consultada**: nenhuma requisição sai para ela.
2. **`[privacidade].excluir`** — o filtro geral do diário, que age depois, sobre
   o que todas as fontes trouxeram.

## Passo 1 — Criar a app interna no seu workspace

Em <https://api.slack.com/apps>, **Create New App → From scratch**.

1. Nome: `Second Brain (diário)`. Workspace: o do trabalho.
2. **Não** ative *Distribution* / *Public Distribution*. A app tem que continuar
   sendo uma *internal customer-built application*: é essa condição que mantém
   `conversations.history` e `conversations.replies` no **Tier 3** (~50
   requisições/min, até 1.000 mensagens por resposta). Apps distribuídas fora do
   Marketplace caíram, em maio de 2025, para 1 requisição/min e 15 mensagens por
   resposta — o coletor ainda funcionaria, mas lento.

**Sucesso:** a app aparece na sua lista em api.slack.com/apps.

**Falha:** se o botão de criar app não existir, o admin bloqueou a criação de
apps por membros. Vá direto ao passo 3 e peça a liberação antes de continuar.

## Passo 2 — Pedir só os scopes de leitura

Em **OAuth & Permissions → Scopes → User Token Scopes**, acrescente
exatamente estes nove:

| scope | para quê |
|---|---|
| `channels:read` | listar os canais públicos de que você participa |
| `channels:history` | ler as mensagens desses canais |
| `groups:read` | listar os canais privados de que você participa |
| `groups:history` | ler as mensagens desses canais |
| `im:read` | listar suas DMs |
| `im:history` | ler as mensagens das DMs |
| `mpim:read` | listar seus group DMs |
| `mpim:history` | ler as mensagens dos group DMs |
| `users:read` | trocar `U01234` pelo nome da pessoa |

**Não peça `search:read`.** A busca não é usada por este coletor, e é dos
scopes que mais levantam bandeira na revisão do admin.

**Não peça nenhum *Bot Token Scope*.** O coletor precisa ver o que **você** vê,
inclusive DMs; um bot só vê os canais em que foi convidado.

**Sucesso:** a lista de *User Token Scopes* tem esses nove e mais nada.

## Passo 3 — Pedir a aprovação do admin

Em muitos workspaces a instalação de qualquer app — inclusive interna — precisa
de aprovação. Ao pedir, diga isto (é tudo verdade e é o que o admin precisa
saber para decidir):

> Criei uma app **interna**, só para o meu uso, que **não será distribuída**.
> Ela **só lê** e usa um **user token**, com nove scopes de leitura:
> `channels:read`/`:history`, `groups:read`/`:history`, `im:read`/`:history`,
> `mpim:read`/`:history` e `users:read`. **Não pedi `search:read`** nem nenhum
> scope de escrita.
>
> Ela alcança exatamente o que eu já alcanço no Slack — nada além. Roda uma vez
> por dia, no meu PC, lê as mensagens daquele dia e escreve um resumo do meu
> trabalho num arquivo local. **Nada é enviado para servidor nenhum além do
> Slack**, e as conversas que eu marcar como excluídas não chegam a ser lidas.
> O token fica só na minha máquina e pode ser revogado por você a qualquer
> momento em Manage apps.

**Sucesso:** a app aparece aprovada em *Manage apps* do workspace.

**Falha:** se o admin recusar, o diário continua nascendo com git e Linear.
Deixe `[slack].user_token` vazio e a fonte simplesmente não aparece na nota.

## Passo 4 — Instalar e copiar o user token

Em **OAuth & Permissions → Install to Workspace** (ou *Reinstall*), autorize.

**Sucesso:** aparece o **User OAuth Token**, começando com `xoxp-`.

> É o token de cima, o *User* OAuth Token. O **Bot** User OAuth Token
> (`xoxb-`) não serve: ele não enxerga suas DMs. Se você colar o `xoxb-`, o
> coletor avisa com todas as letras.

**Nunca** use token de sessão do navegador (`xoxc`/`xoxd`): além de frágil,
viola os termos da Slack.

**Atenção:** sempre que você mudar os scopes, precisa **reinstalar** — e o
token muda.

## Passo 5 — Colar o token e montar a blocklist

Abra `%APPDATA%\second-brain\config.toml` e preencha a seção `[slack]`:

```toml
[slack]
user_token = "xoxp-...cole aqui o token inteiro..."
conversas_excluidas = ["#terapia", "@joana", "D01234ABCDE"]
```

Cada item da blocklist casa por **substring, sem diferenciar maiúsculas**,
contra o id da conversa, o nome do canal e — nas DMs — o nome de quem está do
outro lado. O `#` e o `@` iniciais são opcionais, estão ali só para ler melhor.

Bloquear demais é o erro seguro: `"ana"` bloquearia também `#planejamento`. Se
quiser precisão cirúrgica, use o **id da conversa** (o `C…`/`D…`/`G…` que
aparece no fim do link "Copy link" da conversa) — e, como bônus, uma blocklist
só de ids não gasta nenhuma requisição resolvendo nome de ninguém.

O arquivo está no `.gitignore` e é o único lugar onde o token mora. Nunca o
coloque em variável de ambiente, em teste, em fixture nem em issue.

**Sucesso:** o arquivo continua carregando:

```
python -m second_brain diario --simular
```

**Falha:** se aparecer `Configuração inválida`, confira aspas e barras — use
barras normais (`/`) em qualquer caminho.

## Passo 6 — Ver o que seria coletado, sem escrever nada

```
python -m second_brain diario --simular
```

`--simular` coleta, aplica o filtro de exclusão e **imprime**: não chama o
Claude e não escreve nada no vault.

**Sucesso:** aparece a janela do dia e uma linha por mensagem, com as marcadas
`[slack]` entre elas:

```
Simulação do diário de 2026-09-03 — nada foi escrito.
Janela: 2026-09-03T04:00:00-03:00 → 2026-09-04T04:00:00-03:00
  14:02  [slack] (#plataforma) Ana Prado
  14:20  [slack] (#plataforma) Gabriel Velozo
  17:45  [slack] (#plataforma) Gabriel Velozo (em thread)
  15:40  [slack] (DM com Ana Prado) Ana Prado
```

Confira, nesta ordem:

1. **Nenhuma conversa da blocklist aparece.** Esta é a conferência que importa:
   ela não foi filtrada depois, ela não foi nem lida.
2. **As DMs aparecem** com `DM com <nome>`, e os group DMs com
   `Grupo com <pessoas>` — não com `D01234` nem `mpdm-...`.
3. **Nenhum `U01234` sobrou** no lugar de um nome, nem no início da linha nem
   dentro do texto de uma menção.
4. **O horário bate com o seu relógio**, não com UTC.
5. **Um dia sem conversa é normal:** se você não falou nada naquele dia, não sai
   linha `[slack]` nenhuma, e isso não é falha.

**Falha — token recusado:**

```
Fonte 'slack' não entrou: O Slack recusou 'auth.test' com o erro 'invalid_auth': ...
```

Volte ao passo 4 e reinstale a app. O diário nasce mesmo assim, marcado — mas
sem o Slack.

**Falha — scope faltando:**

```
Fonte 'slack' não entrou: O Slack recusou 'conversations.history' com o erro
'missing_scope': Falta o scope im:history no token do Slack...
```

A mensagem nomeia o scope. Volte ao passo 2, acrescente e **reinstale** — o
token muda.

## Passo 7 — Gerar o diário de um dia movimentado

Escolha um dia em que você sabe que conversou (pode ser uma data passada):

```
python -m second_brain diario 2026-09-03
```

Este passo **chama o Claude** para o resumo e **escreve no vault**.

**Sucesso:** o comando imprime o caminho da nota, e a nota tem a seção
`## Slack`, com um `### #canal` (ou `### DM com ...`) por conversa e uma linha
`- HH:MM <quem falou>` por mensagem, com o texto em blockquote na linha
seguinte e o título linkando o permalink da mensagem no Slack:

```markdown
## Slack

### #plataforma

- 14:02 [Ana Prado](https://<workspace>.slack.com/archives/C0PLATAFORMA/p1788454920000000)
  > Subi o fix do frete em #frete-v2, @Gabriel Velozo revisa?
```

Clique num desses links: ele tem que abrir a mensagem certa no Slack.

## Passo 8 — Rodar o teste de rede de propósito

```
python -m pytest -m rede tests/test_fonte_slack.py
```

**Sucesso:** o teste passa lendo a janela de ontem contra a API de verdade.
Sem `[slack].user_token` preenchido ele **pula limpo**, e isso também é um
resultado válido — é o estado esperado enquanto a app não for aprovada.

## Se precisar revogar

Em api.slack.com/apps → sua app → **OAuth & Permissions → Revoke All OAuth
Tokens** (ou peça ao admin para remover a app em *Manage apps*), e apague o
valor de `[slack].user_token`. O diário volta a nascer só com as outras fontes,
marcado com o motivo. Nada no vault precisa ser mexido.

O token também é invalidado sozinho quando você troca a senha do Slack ou
quando o workspace liga rotação de token. Nesse caso o diário do dia seguinte
já nasce com o aviso, e o conserto é reinstalar a app (passo 4).

## Custo e limites

Zero: a Web API do Slack não cobra por uso.

O coletor gasta **uma requisição por conversa de que você participa**, mais uma
por página extra e uma por thread aberta no dia, mais uma por pessoa distinta
que apareceu (`users.info`, em cache dentro da execução). Num workspace com
muitas DMs antigas isso pode passar do Tier 3 (~50/min): quando passa, o Slack
responde `429` com `Retry-After` e o coletor **espera o que ele pediu** e
continua, até três vezes. Uma espera acima de 60 segundos é recusada em vez de
pendurar a tarefa agendada — o diário do dia nasce marcado como incompleto, e
rodar de novo o regenera.

Se a execução ficar longa demais, encurte a lista de conversas em
`[slack].conversas_excluidas`: cada conversa bloqueada é uma requisição a menos,
além de ser privacidade.
