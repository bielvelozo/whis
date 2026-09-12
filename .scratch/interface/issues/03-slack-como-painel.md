# 03 — O Slack como painel, não só como pergunta

Type: research
Status: resolved
Blocked by: 01

## Question

O bot **existe e funciona** (bot `U0C0AJXB59V`, DM `D0C1LAWCNHE`). O que ele pode virar sem uma
segunda rodada de aprovação do admin — e o que exigiria uma?

Levantar fatos, não decidir:

- **Block Kit**: botões numa mensagem (*Gerar de novo*, *Abrir no Obsidian*). Exige scope novo?
  Exige *Interactivity* ligada na app? O envelope `interactive` chega por Socket Mode (o
  `dm_slack._receber` já o confirma e descarta — ticket 01), então o que falta é tratamento. Um
  botão `url:` com `obsidian://` funciona, ou o Slack só aceita `http(s)`?
- **Slash commands**: `/daily`, `/anota`. O que custam em aprovação e em configuração da app;
  funcionam por Socket Mode (envelope `slash_commands`); o limite de 3 s de resposta e como se
  contorna (`response_url`, mensagem de "estou procurando").
- **Mensagem proativa**: o bot pode iniciar conversa na própria DM sem o usuário falar primeiro?
  Precisa de `im:write` ou `conversations.open`? E `chat.scheduleMessage` — serve para quê, se o
  conteúdo da daily só existe depois de gerada?
- **Tamanho**: o roteiro da daily cabe numa mensagem? Limites do `chat.postMessage` (`text` e
  blocos `section`), quantos blocos por mensagem. **Medir contra uma daily real do vault**, não
  contra a documentação sozinha.
- **Imagem e áudio na DM** (achado do DEFERRED, levantado pelo usuário antes de qualquer outra
  coisa): o que exige de verdade — `files:read` na app?, baixar o `url_private` com o bot token,
  e transcrever antes no caso do áudio (a Deepgram já está no projeto, com crédito). É o item que
  **força a segunda rodada com o admin**, então o custo de aprovação precisa estar claro antes do
  *grilling*.
- **A regra da reunião de 04/09** (*sem personalidade, informação direta*): o que na resposta de
  hoje viola isso, e o que é do modelo (`busca_claude`) versus do formatador
  (`atendente.formatar_para_slack`).

O resultado alimenta o 05 e o 06.

## Answer

**Quase tudo que faria da DM um painel já cabe nos quatro scopes de hoje.** O que cobra aprovação
nova é o slash command e o arquivo (imagem/áudio). Detalhes, limites e fontes em
[../research/03-slack-como-painel.md](../research/03-slack-como-painel.md).

- **A daily entregue na DM não custa scope nenhum.** `im:write` é *"Start direct messages with
  people"* e cobre `conversations.open` — **`chat.postMessage` não está na lista dele**. Como a
  DM já existe, postar nela proativamente cabe no `chat:write` que a app tem. O que falta é
  código: guardar o id da DM, que hoje só se conhece quando uma mensagem chega.
- **Botões também não custam scope** — só *Interactivity* ligada. O envelope `interactive` já
  chega e já é confirmado por `dm_slack._receber`; o `return` seguinte o descarta. Falta tratar.
- **Melhor que um botão `obsidian://`**: um botão com `action_id`, cujo clique chega ao Whis no
  PC por Socket Mode, e é o Whis quem abre a nota. A documentação define `url` como *"A URL to
  load in the user's browser"* e **não confirma** esquema fora de `http(s)` — e no celular não há
  Obsidian de desktop para abrir. O caminho pelo `action_id` funciona apertando do celular.
- **Slash command custa `commands`** — scope novo, reinstalação, admin. Vale perguntar o que
  `/daily` daria que *"gera a daily"* escrito na DM não dá.
- **Tamanho não é problema, e isso foi medido**: o roteiro das duas dailies reais tem **2.647 e
  2.612 caracteres**; dividido pelos seis cabeçalhos, a maior seção tem **1.088** contra o teto
  de 3.000 de um bloco `section`. São oito blocos de cinquenta. O que não cabe são as listas
  cruas (139 mil e 493 mil caracteres) — e elas ficam no vault, que é o registro durável.
- **Pedir resposta mais curta ao modelo já está no prompt, e não funcionou.** `PROMPT_DA_BUSCA`
  diz *"a resposta precisa ser curta, direta e verificável"* e repete *"curta e direta: ele lê no
  celular"* — e saíram 3.933 tokens. O caminho é estrutural (teto de caracteres, outro formato de
  saída), não um adjetivo a mais. Já o bloco de fontes é do formatador: uma linha por citação
  **com o trecho inteiro**, 7 linhas na demo real. Mostrar só a origem, ou agrupar por nota (4 em
  vez de 7), encurta sem tocar na decisão dele de *"toda resposta cita"*.
- **Imagem e áudio são três obstáculos, não um**: o filtro `_e_para_mim` descarta antes de olhar
  (arquivo chega com `subtype: "file_share"`); `mensagem_do_evento` lê só `text`; e só então vem
  o `files:read` para baixar o `url_private_download` com o bot token — **é esse o item que força
  a segunda rodada com o admin**. Para áudio, some a transcrição.
