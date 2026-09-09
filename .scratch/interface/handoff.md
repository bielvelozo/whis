# Handoff: fechar o Slack e levantar a interface

Documento de continuação, escrito em 2026-09-09. Assume **zero contexto**: leia inteiro
antes de tocar em qualquer coisa. São **duas frentes**, e a ordem importa: a primeira é
terminar o que já está construído; a segunda é **um levantamento**, não uma construção.

O que o usuário disse, e é o motivo desta segunda frente, com todas as letras:

> *"Percebi que chamar o Whis com comandos vai ser muito ruim. Vamos ter que construir
> uma interface pra ele."*

É a **segunda vez** que este projeto aprende a mesma lição. A primeira spec da recuperação
de contexto foi escrita para o terminal e recusada inteira (*"muito complexo e nada prático"*).
O aviso no handoff anterior dizia: **a entrega certa não é a que cabe na arquitetura
existente, é a que cabe no dia do usuário.** Desta vez, o levantamento vem **antes** de
qualquer spec.

---

## 0. Onde as coisas estão

| | |
|---|---|
| suíte | **862 verdes**, 8 desselecionados (7 antigos + o teste de rede da busca) |
| último commit de código | `6625936` — o corte do detalhe no prompt da daily |
| entrega 3 (recuperação de contexto) | cinco camadas construídas e provadas sem rede; tickets 01–03 `resolved`, 04 e 05 `ready-for-human` |
| em uso real | bandeja + reunião, diário, daily (lida em reunião desde 04/09; a de 08/09 nasceu inteira) |
| **nunca provado** | nenhuma pergunta real ao Claude pelo agente; nenhuma mensagem real na DM do Slack |

### Verifique antes de começar

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m whis perguntar --fakes --sem-fio "teste"
git log --oneline -8
```

862 passam, 8 desselecionados. O `perguntar --fakes` imprime a resposta de exemplo e sai `0`.

### O que ler, nesta ordem

1. `CONTEXT.md` — o glossário. **Daily** e **Diário** são termos distintos.
2. `.scratch/recuperacao-contexto/handoff.md` — o handoff da entrega 3, inteiro. Tem as
   decisões do usuário, as armadilhas pagas e a ordem de prova. Este documento não o repete.
3. `.scratch/recuperacao-contexto/contrato-busca.md`, seções 8 a 12 — a API real construída.
4. `docs/smoke-atendente.md` — o roteiro do passo humano do Slack.
5. `.scratch/second-brain/map.md` — o mapa do esforço original, com as decisões de
   arquitetura. Este handoff abre a **entrega 4** nele.
6. `.scratch/fontes-passivas/DEFERRED.md` — 60+ achados; vários tocam a interface.

---

## Frente 1 — Finalizar o Slack

O código está pronto e provado sem rede. O que falta é humano, e o usuário **já começou**:
em 2026-09-09 ele estava na página *App Home* da app do Slack, que exige um scope de bot antes
de liberar as abas — a ordem do roteiro foi corrigida nesse dia (scopes primeiro, App Home
depois; commit `7f35147`).

### Onde ele parou

Passo 1 do `docs/smoke-atendente.md` (os quatro scopes de bot) — confirmado com ele em
2026-09-09: o App Home ainda mostrava *"First, assign a scope to your bot token"*, ou seja
os quatro scopes de bot **não** estavam salvos. Pergunte a ele em que passo
está antes de assumir qualquer coisa.

**A app do Slack ainda se chama `Second Brain (diário)`.** O projeto foi rebatizado para
**Whis** em 2026-09-09 (commit do rename) e o roteiro já fala em `Whis`: renomear a app e o
bot é parte do passo 2, e o momento certo é **antes** do pedido do passo 5 — depois de o admin
aprovar, ele passa a ver um nome que não foi o que aprovou.

Ele também perguntou se falta scope para o bot **ver imagem e áudio** na DM. Falta, e mais que
scope: hoje um anexo é ignorado em silêncio. Está no DEFERRED, e "mandar áudio em vez de
digitar no celular" é candidato de peso da frente 2. Os passos que faltam, na ordem: scopes → App Home
(bot user + Messages Tab) → Socket Mode + app-level token → `message.im` → **pedido novo ao
admin** (texto pronto no passo 5) → reinstalar e colar os dois tokens.

**Atenção**: reinstalar a app **troca o user token** do coletor. O roteiro avisa; você avise
de novo.

### A ordem de prova, quando ele autorizar

Cada item gasta algo; **peça antes** de cada um que gasta a assinatura.

1. `whis atender --fakes` + uma mensagem na DM → 👀 e a resposta de exemplo. Prova o
   Slack; não gasta nada.
2. `whis perguntar --sem-fio "o que ficou decidido sobre a retenção de 180 dias?"`
   → prova o Claude sem o Slack. **Gasta a assinatura.** É aqui que se confirma o único
   risco que o sem-rede não alcança: o nome `mcp__vault__<ferramenta>` em `allowed_tools` é
   convenção do Claude Code, não do SDK. Se toda resposta vier "não achei" com `0 notas
   lidas` no log, é isso — e o conserto é em `busca_claude.ferramentas_permitidas`.
3. `pytest tests/test_busca_claude.py -m rede -o addopts="" -q` — o teste de rede, com
   vault de fixture e pasta privada.
4. `whis atender` e a demo-mestra do passo 8 do roteiro, **pelo celular**: pergunta,
   pergunta de acompanhamento sem repetir o assunto, pergunta sobre a última hora no Slack.
5. Passo 9 do roteiro: a pasta privada, com um fato plantado. Ele **ainda não escolheu** a
   pasta; `[privacidade].pastas_privadas` está vazia.
6. `whis windows --atendente`, para subir no logon.

Ao fechar, mude os tickets 04 e 05 de `ready-for-human` para `resolved`, com o comentário
de entrega dizendo **o que foi visto na DM** (custo da primeira resposta real, tempo, se
citou o arquivo certo). O custo de cada resposta está no log como *"Pergunta ao Claude:
equivalente a US$ ..."*.

### O que esta frente **não** deve fazer

Não reabra decisões da entrega 3 por causa da frente 2. A DM do Slack é uma superfície
possível da interface, talvez a principal — o levantamento decide. Mas ela precisa
**funcionar** primeiro, para o usuário poder opinar com a experiência na mão.

---

## Frente 2 — Levantamento: como pode ser a interface

**É levantamento, não construção.** O entregável é um mapa de opções com fatos verificados,
uma conversa de *grilling* com o usuário sobre o dia dele, e no fim uma spec — nesta ordem.
Nenhuma linha de código de interface antes da spec aprovada por ele.

### O problema, em uma frase

Tudo que o Whis faz hoje, fora a bandeja, é acionado por comando de terminal — e o
usuário não vive no terminal. Ele vive **no Slack, no Obsidian e na reunião**.

### Inventário dos pontos de contato hoje

Levantado em 2026-09-09. É o ponto de partida do ticket 01; confira antes de confiar.

| gesto | como se faz hoje | onde o usuário está nessa hora | dor |
|---|---|---|---|
| gravar a reunião | clique no ícone da bandeja | no Meet, no PC | nenhuma: é o gesto da spec original |
| ler a nota da reunião | Obsidian, `reunioes/` | no PC, depois | nenhuma |
| **gerar a daily** | `whis daily` no terminal, um minuto antes de falar | entrando na reunião, no PC | **a maior**: abrir terminal, digitar, esperar 40 s, ler |
| anotar um ponto para a daily | editar `notas/daily.md` no Obsidian, ou `daily --anotar "..."`, ou (em breve) `anotar ...` na DM | qualquer hora, qualquer lugar | depende de lembrar do arquivo |
| conferir o filtro / ver o que entraria | `daily --simular` | no PC | raro, aceitável no terminal |
| gerar o diário | `whis diario`, pensado para tarefa agendada às 19:00 — **conferir se ele agendou** (`windows --limpeza` agenda só a limpeza) | — | nenhuma se agendado; senão, esquecido |
| perguntar ao vault | `whis perguntar` (diagnóstico) → DM do Slack (frente 1) | no Slack, no PC ou no celular | resolvida pela DM, quando ela existir |
| configurar (pasta privada, blocklist, referências pessoais, contexto do time) | editar `config.toml` à mão em `%APPDATA%` | raro | aceitável, mas ele nunca preencheu a pasta privada |
| subir no logon, limpar áudio, init | comandos `windows`, `limpar`, `init` | uma vez | aceitável |
| saber que algo falhou | balão da bandeja (reunião); código de saída e `bandeja.log` (o resto) | — | o diário e a daily falham em silêncio se ninguém olha o log |

O ponto de contato que dói é **a daily**: ela é o momento de maior valor e o pior gesto.

### Fatos que o levantamento herda

- **A reunião de demo de 04/09 já decidiu parte disto** (`reunioes/2026-09-04-1449-reuniao.md`
  no vault): *"A daily será gerada automaticamente cerca de cinco minutos antes da reunião
  para permitir uma revisão"*; *"o arquivo de notas passa a ser o lugar onde tudo o que for
  anotado entra como contexto"*; *"a ferramenta não terá personalidade nem falará com o
  usuário: só entregará informação direta"*; e uma ação de *"integrar com a agenda para
  transcrever reuniões automaticamente"*. Um participante sugeriu *"interface no estilo
  Jarvis, com tela redonda"* — registre como ideia, não como decisão.
- **A página HTML da daily foi construída e revertida no mesmo dia** (ticket
  `.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`): o Obsidian entrou e a página
  perdeu a razão de existir. Lição: **não invente superfície nova onde uma que ele já usa
  serve.**
- **O Whis, agente anterior dele, morava no WhatsApp.** Ele escolheu o Slack para o agente
  atual sabendo das DMs. Chat é a forma que ele já demonstrou usar.
- **ADR 0001**: projeto fino, 100% local, sem servidor. Uma interface web hospedada está fora;
  uma página local não está, mas a página revertida é o precedente contra.
- **Comportamento proativo está em "Not yet specified" no mapa** — *"depende de uso real"*.
  O uso real chegou: a daily de 5 minutos antes da reunião **é** comportamento proativo, e a
  reunião de 04/09 o pediu. É a primeira coisa a fechar com ele.
- **Custo**: uma daily de um dia ≈ US$ 0,70 equivalente; a de segunda-feira (quatro dias)
  custou US$ 1,74 e 36 s. Qualquer interface que gere a daily "de novo" com um clique precisa
  saber disso — regenerar é barato de fazer e caro de repetir.
- **A nota da daily é o registro durável**; o roteiro impresso no terminal é descartável. A
  interface pode ler a nota em vez de reexecutar.
- No DEFERRED: `--simular` não mostra o que o filtro removeu; a daily não linka o diário nem
  o contrário; o atendente atende em série; a resposta na DM vai sem thread; `anotar` só
  reconhece o prefixo em português no começo. Todos são decisões de interface.

### As superfícies candidatas — para pesquisar, não para escolher agora

Cada uma vira um ticket de pesquisa com fatos verificados (o que dá para fazer, o que custa,
o que exige de aprovação ou de stack nova). **Nenhuma exclui as outras**; a resposta provável
é uma combinação, e é o *grilling* que diz qual.

1. **O agendador + notificação do Windows.** A daily nasce sozinha cinco minutos antes da
   reunião (a agenda dele diz quando; ou um horário fixo), e um *toast* avisa "a daily de
   hoje está pronta" com um botão que abre a nota no Obsidian. Resolve a maior dor sem
   interface nova. Perguntas: como saber a hora da reunião (Google Calendar? horário fixo no
   `config.toml`?); toast com botão no Windows 11 a partir de Python (`winrt`? `plyer`? o que
   o ADR 0001 aceita?); o que acontece se a máquina está desligada.
2. **A bandeja, ampliada.** O ícone já existe e sobe no logon. Itens de menu: *Gerar a daily
   agora*, *Abrir a daily de hoje*, *Anotar um ponto…*, *Perguntar…*. Perguntas: entrada de
   texto a partir da bandeja (uma janelinha? o `pystray` não tem); a bandeja tem trava e
   máquina de estados de gravação — misturar é o risco que a entrega 3 evitou.
3. **A DM do Slack como painel, não só como pergunta.** O bot já vai existir. Mensagens
   como *"gera a daily"*, *"o que entra na daily?"*, *"anota X"*; e a daily **entregue na
   DM** quando nasce (é onde ele está entrando na reunião, no PC ou no celular). Slack tem
   *Block Kit* (botões: *Gerar de novo*, *Abrir no Obsidian* via URI `obsidian://`), *slash
   commands* e mensagens agendadas — tudo funciona por Socket Mode, e os envelopes
   `interactive`/`slash_commands` já são confirmados em `dm_slack._receber`. Perguntas: o
   admin aprova botões (scope nenhum a mais, mas *Interactivity* ligada)?; texto de 40 s de
   espera na DM; o roteiro em mrkdwn cabe numa mensagem?; **a regra da reunião de 04/09**:
   *sem personalidade, informação direta* — a DM precisa obedecer.
4. **O Obsidian como interface.** O vault já é onde ele lê. Uma nota-painel gerada pelo
   agente (`daily/hoje.md` ou um *dashboard* com links); `notas/daily.md` já é entrada de
   dados por checkbox. Perguntas: plugin próprio (TypeScript, stack nova, contra o ADR de
   projeto fino) versus Obsidian URI + notas geradas; *Dataview* ou similar; o que ele já
   instalou no Obsidian dele.
5. **Uma janela local própria** (`pywebview`, Tk, ou a página revertida ressuscitada).
   Perguntas: o precedente contra é forte; só vale se as quatro anteriores não cobrirem a
   entrada de texto no PC.

### O que perguntar a ele no *grilling* (ticket 05)

- Conte o seu dia: a que horas é a daily, onde você está 5 minutos antes (PC? celular? já no
  Meet?), quantas vezes por dia você pensa "preciso lembrar disso na daily", e onde você está
  nessas horas.
- Quando o Whis precisar te avisar de algo (daily pronta, reunião gravada, diário
  falhou), **onde** o aviso tem que aparecer para você ver?
- Você quer **ler** a daily ou quer que ela **apareça**? (nota no Obsidian versus mensagem
  na DM versus toast)
- O que você está disposto a **digitar**, e onde? (pergunta longa no celular? um "anota X"?)
- Configuração: você quer mexer em `config.toml` ou quer que a pasta privada, a blocklist
  e o contexto do time sejam perguntas na DM?
- A agenda: a daily tem hora fixa, ou vem do Google Calendar? Quem mais está na reunião?
  (isto reabre *"integrar com a agenda"*, decidido na demo)
- O que da reunião de 04/09 ainda vale: *"sem personalidade"*, *"a nota de pontos como
  contexto de tudo"*.

### Como conduzir

Padrão da casa, o mesmo do mapa original: um `map.md` em `.scratch/interface/` com
*Destination*, *Notes*, *Decisions so far*, e tickets em `issues/NN-*.md` do tipo `research` /
`grilling` / `task`. Sugestão de tickets, numerados na ordem em que se resolvem:

| nº | tipo | pergunta |
|---|---|---|
| 01 | research | Inventário dos pontos de contato (a tabela acima, conferida no código e com ele) e o que cada superfície candidata cobre de cada gesto |
| 02 | research | Windows: agendar a daily antes da reunião e avisar com *toast* com botão, a partir de Python sem stack nova; Google Calendar como fonte da hora (custo de aprovação, OAuth) |
| 03 | research | Slack como painel: Block Kit, slash commands, mensagens agendadas e `obsidian://` por Socket Mode; o que exige aprovação a mais; limites de tamanho de mensagem |
| 04 | research | Obsidian como interface: URI, notas geradas, plugins que ele já usa, custo de um plugin próprio |
| 05 | grilling | O dia do usuário (as perguntas acima). **Só depois** dos tickets 02–04, para as opções chegarem com fatos e não com achismo |
| 06 | task | Decisão e spec da entrega 4, com user stories a partir do dia dele, não das superfícies |

Skills da casa para cada tipo: `/research` nos de pesquisa (fontes primárias, achado em
markdown no repo), `/grilling` no 05, `/writing-plans` ou o padrão do contrato da entrega 3
no 06. Os achados de research ficam em `.scratch/interface/research/`.

### O que a frente 2 **não** é

- Não é reescrever a daily, o diário nem o agente: eles funcionam. É decidir **por onde** ele
  os aciona e **por onde** eles falam com ele.
- Não é escolher uma superfície antes de ouvi-lo. A entrega 3 nasceu errada exatamente assim.
- Não é construir. Se o *grilling* mostrar que a resposta é "a daily aparece sozinha na DM às
  9:55 com um botão", a construção é pequena — mas é outra sessão, com spec e contrato.

---

## Armadilhas já pagas

As dos dois handoffs anteriores continuam valendo (leia-as). Desta sessão:

- **A daily de segunda-feira cobre quatro dias** e estourou o teto de 400 mil caracteres da
  chamada. O conserto foi cortar o `detalhe` de cada evento a 500 caracteres no prompt
  (`resumo_dia_claude.DETALHE_MAXIMO`); a nota guarda tudo. Uma semana de folga estoura de
  novo — está no DEFERRED.
- **O Slack exige scope de bot antes de liberar o App Home.** O roteiro já está na ordem certa.
- **Não decida a interface pela arquitetura.** Está escrito três vezes neste documento de
  propósito.
