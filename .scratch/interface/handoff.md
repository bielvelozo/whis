# Handoff: a interface do Whis (entrega 4)

Documento de continuação, reescrito em 2026-09-10, no fim da sessão que **fechou o Slack** e
rebatizou o projeto. Assume **zero contexto**: leia inteiro antes de tocar em qualquer coisa.

A frente 1 do handoff anterior (finalizar o Slack) **está feita**. O que resta é a frente 2,
que é **um levantamento, não uma construção** — e o motivo dela, nas palavras do usuário:

> *"Percebi que chamar o second brain com comandos vai ser muito ruim. Vamos ter que construir
> uma interface pra ele."*

É a **segunda vez** que este projeto aprende a mesma lição. A primeira spec da recuperação de
contexto foi escrita para o terminal e foi recusada inteira (*"muito complexo e nada prático"*).
O aviso continua valendo: **a entrega certa não é a que cabe na arquitetura existente, é a que
cabe no dia do usuário.** O levantamento vem **antes** de qualquer spec.

---

## 0. Onde as coisas estão

| | |
|---|---|
| suíte | **862 verdes**, 8 desselecionados (7 antigos + o teste de rede da busca) |
| nome | o projeto virou **Whis** em 2026-09-09 — era Second Brain |
| entrega 3 (recuperação de contexto) | **provada na máquina do usuário**; ticket 04 `resolved`, 05 `ready-for-human` por dois passos que só ele fecha |
| em uso real | bandeja + reunião, diário, daily, **e agora a DM do Slack** |

### Verifique antes de começar

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m whis perguntar --fakes --sem-fio "teste"
git log --oneline -10
```

862 passam. O `perguntar --fakes` imprime a resposta de exemplo e sai `0`.

### O que ler, nesta ordem

1. `CONTEXT.md` — o glossário. **Daily** e **Diário** são termos distintos, e **Whis** (este
   projeto) não é o **Whis da EC2** (o agente aposentado dele).
2. `.scratch/fontes-passivas/DEFERRED.md`, os **últimos seis itens** — os achados de uso real
   da DM, de 09–10/09. São matéria-prima direta desta entrega.
3. `.scratch/recuperacao-contexto/issues/04-a-dm-do-slack.md`, o comentário de entrega — o que
   foi provado com o mundo real, com números.
4. `.scratch/second-brain/map.md` — o mapa do esforço original. Esta é a **entrega 4** nele.
   (A pasta mantém o nome antigo de propósito: uma dúzia de documentos históricos linka para
   dentro dela.)
5. `docs/smoke-atendente.md` — o roteiro do Slack, já cumprido, com o custo real anotado.

---

## 1. O que a sessão de 09–10/09 fez

**Fechou o Slack.** O passo humano do roteiro foi feito com o usuário: quatro scopes de bot,
bot user, Messages Tab, Socket Mode, `message.im`, reinstalação e os dois tokens. A DM
funcionou de ponta a ponta.

O que ficou provado, com números:

- **O Slack**: 👀 em um ou dois segundos e resposta na DM. Bot `U0C0AJXB59V`, DM `D0C1LAWCNHE`.
- **O Claude**: primeira pergunta real custou o equivalente a **US$ 0,5589**, 18 turnos,
  **17 chamadas de ferramenta**, 63 s, 7 citações de 4 notas. As 17 chamadas **mataram o risco
  que estava aberto desde a camada 02**: `mcp__vault__<ferramenta>` em `allowed_tools` casa com
  o que o SDK espera, e não era só convenção do Claude Code.
- **O fio de 24 h**: provado pela porta dos fundos — a primeira pergunta real abriu com
  *"Correção do que eu disse antes"*, desmentindo a resposta que o ensaio com `--fakes` tinha
  deixado no `conversas.json`.
- **A fonte ao vivo**: citou com origem `slack:DM com Whis`, e não com caminho de nota.

**Rebatizou o projeto.** `second_brain` → `whis` em pacote, comando, variável de ambiente
(`WHIS_CONFIG`), pasta de estado (`%APPDATA%\whis`), vault (`~\whis-vault`), gravações e tarefa
agendada. `IDEA.md`, a ADR 0001 e os documentos de entregas fechadas **não** foram reescritos —
são registro do que aconteceu; cada um ganhou uma linha dizendo que o nome mudou.

**Registrou seis achados no DEFERRED**, todos de uso real, todos decisões de interface.

---

## 2. Pendências com o usuário — nenhuma bloqueia a frente 2

Em ordem de importância real. **Pergunte antes de assumir que alguma foi feita.**

1. **A pasta privada nunca foi exercitada.** `[privacidade].pastas_privadas` está vazia desde
   04/09 — hoje o agente enxerga o vault inteiro. É a única garantia de privacidade da entrega
   3 e a única não testada na máquina dele. Passo 9 do `docs/smoke-atendente.md`, dois minutos,
   mas **a escolha da pasta é dele**.
2. **A pasta do repositório ainda é `second-brain`.** Renomear exige a sessão do agente fechada
   (o Windows não renomeia o *cwd* de um processo vivo) e, **logo depois**,
   `.venv\Scripts\python.exe -m pip install -e .` — o editable install gravou o caminho absoluto
   antigo em `.venv/Lib/site-packages/__editable__.whis-0.1.0.pth`, e sem refazer, o
   `import whis` quebra.
3. **Os atalhos de logon e a tarefa agendada** ainda têm os nomes antigos e apontam para o
   caminho antigo. `Second Brain.lnk` na pasta de Inicialização e a tarefa `SecondBrain-Limpeza`
   precisam sair na mão (mudaram de nome, então `whis windows` não os sobrescreve), e depois
   `whis windows --limpeza` e `--atendente`. **Só depois do item 2.**
4. **`[daily].referencias_pessoais` tem `whis` e `second-brain` ao mesmo tempo**, de propósito,
   porque a pasta do repositório ainda não mudou. Quando mudar, tire a string velha. Se essa
   lista errar o nome da pasta, **a daily para de reconhecer os commits do projeto sem dar erro
   nenhum**.
5. **O aviso ao admin do Slack.** A reinstalação passou sem aprovação, então não há portão
   técnico. Mas o pedido anterior afirmava ao admin que a app não teria scope de escrita, e
   agora tem quatro de bot. Texto pronto no passo 5 do roteiro. **Decisão dele.**

---

## 3. Armadilhas desta sessão — não redescubra

As dos handoffs anteriores continuam valendo. Acrescente:

- **O `%APPDATA%` do agente pode não ser o do usuário.** Nesta sessão, tudo que o agente
  escreveu em `%APPDATA%` ficou numa camada que só ele via: leituras passavam pelo disco real,
  escritas não voltavam. Custou uma hora e um susto de "sumiram os tokens". Sintoma: o agente
  afirma que o arquivo está lá e o usuário recebe `DirectoryNotFoundException` no caminho
  literal. **Teste antes de confiar**: peça a ele para criar uma pasta boba em `%APPDATA%` e
  veja se você a enxerga; depois escreva uma e veja se ele enxerga. Se divergir, a saída é
  copiar os bytes para um caminho fora do `AppData` (`C:\Users\gabri\` funciona nos dois
  sentidos) e o usuário move. **Nunca conclua que a configuração está certa por tê-la lido você
  mesmo** — quem verifica `%APPDATA%` é ele. Se o overlay continuar, considere pôr o config num
  caminho compartilhado e apontar `WHIS_CONFIG` para lá.
- **O terminal do usuário é PowerShell 5.1, não bash.** `/c/Users/...` vira `C:\c\Users\...` e
  falha, e `&&` não existe nessa versão. Comandos para ele usam `C:\caminho\assim` e `;` como
  separador. Esta sessão errou isso duas vezes seguidas.
- **O Slack tem duas marcações na Messages Tab.** Ligar a aba faz a DM aparecer; deixar o
  usuário escrever nela é o checkbox *Allow users to send Slash commands and messages*, logo
  abaixo. Sem ele, o Slack mostra *"Sending messages to this app has been turned off"*, e o
  roteiro parece ter falhado no passo errado.
- **Os scopes de bot vêm antes do App Home** — o Slack só destrava as abas depois do primeiro
  scope no bot token. O roteiro já está na ordem certa.
- **Credencial não se grava por insistência.** O usuário vai pedir para você colar o token no
  `config.toml`, e vai insistir. A saída que funciona é um comando com `Read-Host` que ele roda
  no terminal dele — o valor nunca passa por você. Use `[IO.File]::WriteAllText`, porque
  `Set-Content` no PowerShell 5.1 escreve UTF-8 **com BOM** e o `tomllib` engasga com BOM.
- **Não decida a interface pela arquitetura.** Está escrito três vezes neste documento de
  propósito.

---

## Frente 2 — Levantamento: como pode ser a interface

**É levantamento, não construção.** O entregável é um mapa de opções com fatos verificados,
uma conversa de *grilling* com o usuário sobre o dia dele, e no fim uma spec — nesta ordem.
Nenhuma linha de código de interface antes da spec aprovada por ele.

### O problema, em uma frase

Tudo que o Whis faz hoje, fora a bandeja, é acionado por comando de terminal — e o
usuário não vive no terminal. Ele vive **no Slack, no Obsidian e na reunião**.

### Inventário dos pontos de contato hoje

Levantado em 2026-09-09, atualizado com o uso real de 10/09. É o ponto de partida do ticket 01;
confira antes de confiar.

| gesto | como se faz hoje | onde o usuário está nessa hora | dor |
|---|---|---|---|
| gravar a reunião | clique no ícone da bandeja | no Meet, no PC | nenhuma: é o gesto da spec original |
| ler a nota da reunião | Obsidian, `reunioes/` | no PC, depois | nenhuma |
| **gerar a daily** | `whis daily` no terminal, um minuto antes de falar | entrando na reunião, no PC | **a maior**: abrir terminal, digitar, esperar 40 s, ler |
| anotar um ponto para a daily | editar `notas/daily.md` no Obsidian, ou `daily --anotar "..."`, ou `anotar ...` na DM | qualquer hora, qualquer lugar | depende de lembrar do arquivo |
| conferir o filtro / ver o que entraria | `daily --simular` | no PC | raro, aceitável no terminal |
| gerar o diário | `whis diario`, pensado para tarefa agendada às 19:00 — **conferir se ele agendou** (`windows --limpeza` agenda só a limpeza) | — | nenhuma se agendado; senão, esquecido |
| perguntar ao vault | **a DM do Slack**, do PC ou do celular (o `perguntar` virou diagnóstico) | no Slack | resolvida — mas ver os achados de uso abaixo |
| configurar (pasta privada, blocklist, referências pessoais, contexto do time) | editar `config.toml` à mão em `%APPDATA%` | raro | ele nunca preencheu a pasta privada, e não achou o arquivo sozinho quando precisou |
| subir no logon, limpar áudio, init | comandos `windows`, `limpar`, `init` | uma vez | aceitável |
| saber que algo falhou | balão da bandeja (reunião); código de saída e `bandeja.log` (o resto) | — | o diário e a daily falham em silêncio se ninguém olha o log |

O ponto de contato que dói é **a daily**: ela é o momento de maior valor e o pior gesto.

### Fatos que o levantamento herda

**Do uso real da DM, em 09–10/09.** Estes são novos e valem mais que os outros, porque saíram
do celular dele e não de análise:

- **"Me deu uma resposta enorme e me retornou as fontes, o que não é necessário."** São dois
  consertos diferentes: o tamanho sai do modelo (`busca_claude`, 3.933 tokens de saída na
  medição), o bloco de fontes sai de `atendente.formatar_para_slack`. **Cuidado**: "toda
  resposta cita" foi decisão dele na entrega 3, e foi o que permitiu conferir a auto-correção
  do fake. A hipótese a testar no *grilling* é que o incômodo seja o **tamanho do bloco**, não a
  existência da fonte.
- **O OAuth da conta Claude vence e derruba tudo que fala com o modelo.** Aconteceu no meio da
  demo. Na DM o agente avisa em português; a daily e o diário, que rodam sozinhos, falham só no
  `bandeja.log`. Uma daily que não nasce às 9:55 porque o login venceu de madrugada é
  descoberta na reunião. **Cruza direto com a linha "saber que algo falhou" do inventário.**
- **Imagem e áudio na DM são ignorados em silêncio** — nem o 👀. Ele perguntou por isso antes
  de qualquer outra coisa: *"não precisa de um scope para ver imagens? E áudio"*. "Mandar áudio
  em vez de digitar no celular" é candidato de peso, e o custo de adiar é uma segunda rodada de
  aprovação com o admin.
- **O agente lê a própria DM como fonte ao vivo**, inclusive as próprias mensagens de erro.
- **A resposta do `--fakes` entra no fio de 24 h** e vai ao Claude na pergunta seguinte.

Os herdados de antes:

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
- **O Whis da EC2, agente anterior dele, morava em mensageiro.** Ele escolheu o Slack para o
  agente atual sabendo das DMs. Chat é a forma que ele já demonstrou usar — e agora usou.
- **ADR 0001**: projeto fino, 100% local, sem servidor. Uma interface web hospedada está fora;
  uma página local não está, mas a página revertida é o precedente contra.
- **Comportamento proativo está em "Not yet specified" no mapa** — *"depende de uso real"*.
  O uso real chegou: a daily de 5 minutos antes da reunião **é** comportamento proativo, e a
  reunião de 04/09 o pediu. É a primeira coisa a fechar com ele.
- **Custo**: uma daily de um dia ≈ US$ 0,70 equivalente; a de segunda-feira (quatro dias)
  custou US$ 1,74 e 36 s; **uma pergunta na DM ≈ US$ 0,56 e 60 s**. Qualquer interface que
  ofereça "gerar de novo" com um clique precisa saber disso.
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
   o ADR 0001 aceita?); o que acontece se a máquina está desligada. **E o OAuth vencido: um
   agendamento que falha calado é pior que comando nenhum.**
2. **A bandeja, ampliada.** O ícone já existe e sobe no logon. Itens de menu: *Gerar a daily
   agora*, *Abrir a daily de hoje*, *Anotar um ponto…*, *Perguntar…*. Perguntas: entrada de
   texto a partir da bandeja (uma janelinha? o `pystray` não tem); a bandeja tem trava e
   máquina de estados de gravação — misturar é o risco que a entrega 3 evitou.
3. **A DM do Slack como painel, não só como pergunta.** O bot **existe e funciona**. Mensagens
   como *"gera a daily"*, *"o que entra na daily?"*, *"anota X"*; e a daily **entregue na
   DM** quando nasce (é onde ele está entrando na reunião, no PC ou no celular). Slack tem
   *Block Kit* (botões: *Gerar de novo*, *Abrir no Obsidian* via URI `obsidian://`), *slash
   commands* e mensagens agendadas — tudo funciona por Socket Mode, e os envelopes
   `interactive`/`slash_commands` já são confirmados em `dm_slack._receber`. Perguntas: o
   admin aprova botões (scope nenhum a mais, mas *Interactivity* ligada)?; texto de 40 s de
   espera na DM; o roteiro em mrkdwn cabe numa mensagem?; **a regra da reunião de 04/09**:
   *sem personalidade, informação direta* — a DM precisa obedecer, e hoje não obedece.
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
- Quando o Whis precisar te avisar de algo (daily pronta, reunião gravada, diário falhou,
  **login vencido**), **onde** o aviso tem que aparecer para você ver?
- Você quer **ler** a daily ou quer que ela **apareça**? (nota no Obsidian versus mensagem
  na DM versus toast)
- O que você está disposto a **digitar**, e onde? (pergunta longa no celular? um "anota X"?
  **um áudio?**)
- A resposta na DM: o que exatamente incomodou — o tamanho do texto, o bloco de fontes, ou
  ambos? Em que situação você **abriria** o arquivo citado?
- Configuração: você quer mexer em `config.toml` ou quer que a pasta privada, a blocklist
  e o contexto do time sejam perguntas na DM? (ele não achou o arquivo sozinho quando precisou)
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
- **Não é consertar os seis achados do DEFERRED um a um.** Eles são evidência do que a
  interface precisa resolver, não uma lista de tarefas. Alguns morrem quando a spec decidir a
  superfície; outros viram user story. Encurtar a resposta da DM é o único que dá para fazer
  antes — e mesmo esse é acabamento da entrega 3, não interface nova.
