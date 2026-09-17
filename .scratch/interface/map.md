# Mapa: a interface do Whis (entrega 4)

Labels: wayfinder:map

Aberto em 2026-09-10, a partir de [handoff.md](handoff.md). **É levantamento antes de spec.**
Nenhuma linha de código de interface antes de uma spec aprovada pelo usuário.

## Destination

Uma **spec construível da entrega 4** que diga, com user stories tiradas do dia do usuário:
**por onde ele aciona** o Whis e **por onde o Whis fala com ele** — sem que nada disso dependa
de abrir um terminal. O caminho é: inventário conferido → fatos de cada superfície candidata →
*grilling* sobre o dia dele → decisão e spec.

O motivo, nas palavras dele: *"Percebi que chamar o second brain com comandos vai ser muito
ruim. Vamos ter que construir uma interface pra ele."*

## Notes

- Idioma: todos os artefatos deste esforço em português.
- **A entrega certa não é a que cabe na arquitetura existente, é a que cabe no dia do usuário.**
  A primeira spec da entrega 3 nasceu para o terminal e foi recusada inteira (*"muito complexo e
  nada prático"*). É a segunda vez que o projeto aprende a lição — escrita aqui para a terceira
  não acontecer.
- **Não invente superfície nova onde uma que ele já usa serve.** Precedente: a página HTML da
  daily nasceu e foi revertida no mesmo dia, porque o Obsidian já lê a nota bem
  (`.scratch/fontes-passivas/issues/09-a-daily-como-pagina.md`, commit `9a53218`).
- O ADR 0001 (projeto fino, 100% local, sem servidor) vale: interface web hospedada está fora;
  página local não está, mas a página revertida é o precedente contra.
- Onde o usuário vive: **Slack, Obsidian e a reunião**. Não no terminal.
- Regra vinda da reunião de demo de 04/09: *"a ferramenta não terá personalidade nem falará com
  o usuário: só entregará informação direta"*. A DM hoje **não** obedece.
- Custo por gesto, medido: uma pergunta na DM ≈ **US$ 0,56** e 60 s; uma daily de um dia ≈
  **US$ 0,70**; a daily de segunda-feira (quatro dias) **US$ 1,74** e 36 s. Qualquer interface com
  botão "gerar de novo" precisa saber disso.
- Os seis achados de uso real no fim de `.scratch/fontes-passivas/DEFERRED.md` são **evidência do
  que a interface precisa resolver**, não uma lista de tarefas. Alguns morrem quando a spec
  escolher a superfície.
- Skills da casa: `/research` nos tickets de pesquisa, `/grilling` no 05, `/writing-plans` no 06.
  Achados de research ficam em [research/](research/).
- **O `%APPDATA%` desta sessão de agente não é o do usuário** (provado no ticket 01): o que o
  agente lê de `config.toml` e de `bandeja.log` é uma cópia velha. Quem confere qualquer coisa em
  `%APPDATA%` é ele, nunca o agente.

## Decisions so far

<!-- uma linha por ticket fechado: gist + link -->

- [Inventário dos pontos de contato](issues/01-inventario-dos-pontos-de-contato.md) — a tabela do
  handoff se confirma com três correções que mudam a conversa: **o Whis está morto na máquina
  dele agora** (a bandeja não sobe no logon desde o rename, o atendente nunca teve atalho, e a
  tarefa agendada falha calada todo dia ao meio-dia chamando um módulo que não existe mais); **o
  diário nunca foi agendado por código nenhum** — `[diario].hora_da_tarefa` é lida, validada e
  não usada por ninguém; e **nenhuma falha de automação tem para onde gritar**, porque quem
  falha antes de subir não abre o log. Uma quarta apareceu depois, pelo ticket 04: *"Abrir a
  última nota"* não abre o Obsidian, porque `.md` não tem programa associado nesta máquina.
  Detalhes em [research/01-pontos-de-contato.md](research/01-pontos-de-contato.md).
- [Windows: agendador e aviso](issues/02-windows-agendador-e-aviso.md) — **`schtasks` não serve
  para a daily**: não existe opção que ligue "rodar assim que possível depois de perder o
  horário", e a tarefa de hoje está sem ela — uma daily agendada assim não acontece se o PC
  estiver desligado às 9:55. O módulo PowerShell `ScheduledTasks`, que já vem no Windows,
  resolve. O balão de hoje é `Shell_NotifyIcon` e **nunca** terá botão; toast com botão que abre
  o Obsidian é barato (`activationType="protocol"`, e `obsidian://` está registrado na máquina),
  mas botão que volta ao Whis exige componente COM. **Google Calendar tem uma armadilha**: app em
  *Testing* dá refresh token que expira em 7 dias — o mesmo modo de falha do OAuth vencido.
  Detalhes em [research/02](research/02-windows-agendador-e-aviso.md).
- [O Slack como painel](issues/03-slack-como-painel.md) — **quase tudo cabe nos quatro scopes de
  hoje**: a daily entregue proativamente na DM (`chat:write` basta, `im:write` é para *abrir* DM,
  não para postar), botões, thread, e encurtar a resposta. Custam aprovação nova só o slash
  command (`commands`) e ler imagem/áudio (`files:read`). **Tamanho não é problema**: medido, o
  roteiro real tem ~2.600 caracteres e a maior seção 1.088, contra 3.000 por bloco e 50 blocos
  por mensagem. E **pedir resposta curta ao modelo já está no prompt duas vezes** e não
  funcionou — o caminho é estrutural. Detalhes em [research/03](research/03-slack-como-painel.md).
- [O Obsidian como interface](issues/04-obsidian-como-interface.md) — a URI resolve e os valores
  deste vault estão levantados (nome `whis-vault`, ID `245833c11ad43e6e`). **Correção do
  inventário**: `.md` não tem programa associado nesta máquina, então *"Abrir a última nota"* da
  bandeja **não abre o Obsidian hoje** — trocar `os.startfile` por uma URI é a menor entrega útil
  desta entrega inteira. Nota-painel custa uma linha, mas é um segundo artefato do mesmo dado —
  o crime que derrubou a página HTML. Configuração em nota tem furo: **a nota que declara a pasta
  privada fica fora dela**. Detalhes em [research/04](research/04-obsidian-como-interface.md).

- [O dia do usuário](issues/05-o-dia-do-usuario.md) — sete rodadas de *grilling*, e o handoff
  estava com a prioridade invertida: ele parou de usar o Whis **principalmente porque o conteúdo
  não servia**, não pela superfície. As dailies que ele escreve à mão revelaram o mecanismo que
  faltava: ele **mantém uma lista viva** e o Whis **gera uma narrativa nova todo dia** — *"da
  maneira que ele descrevia o que eu fiz eu não lembrava exatamente o que era e não sabia
  explicar"*. Cinco decisões anteriores caíram, o Slack vai dormir e o Whis vira de mesa.
- [Decisão e spec da entrega 4](issues/06-spec-da-entrega-4.md) — **destino alcançado**: spec em
  [spec.md](spec.md), `ready-for-agent`. A entrega 4 é a **casca** (palheta com atalho global,
  contrato de comando, painel de configuração, vigia por toast, camada zero) mais o **conserto da
  daily** (nota viva, quatro seções, terceira zona de propriedade, carregar sem reescrever).

- **Construção da entrega 4** (2026-09-12, `/rb-orchestrate`, tickets 07–12): as seis camadas
  commitadas com a suíte em **1048 verdes** — a nota viva `daily/atual.md` com a regra de carregar
  sem reescrever (provada byte a byte), agendamento pelo módulo `ScheduledTasks` com
  `StartWhenAvailable`, o vigia fora do Whis, a palheta por `ctrl+alt+w` com contrato dispara-e-some,
  o painel de configuração com escritor de TOML e backup, e o toast com botão que abre o Obsidian.
  Sondas reais na máquina passaram (tarefa descartável, hotkey sob `pythonw`, toast, vigia). **Falta
  a prova dele**: `docs/smoke-interface.md`, terminando numa daily real.
- **Acabamento e ajustes da palheta** (2026-09-16 e 17, tickets 13 e 14): a segunda prova dele
  aprovou ("ficou muito melhor") com quatro ajustes — `ctrl+space`, Tab completa o comando, o rótulo
  filtra e executa, fundo acrílico do DWM com `-alpha` (neste build o DWM não amostra as janelas
  atrás; sonda em `research/sonda-acrilico.py`). Suíte em **1071 verdes**; a bandeja dele
  reiniciada com o config trocado. Faltam dele: `claude login` e os passos 6, 8 e 9 do roteiro.
- **O visual do Raycast** (2026-09-17, ticket 15): na terceira prova ele pediu o fundo mais preto e o
  desenho do Raycast com os detalhes em roxo — janela redesenhada no canvas (painel quase preto e
  quase opaco, borda fina, realce arredondado, nome do comando à direita, rodapé com as teclas) e o
  rótulo de `record` passando a *Stop recording* ao reabrir. Suíte em **1071 verdes**.

## Not yet specified

- **Os seis comandos do assistente pessoal**, listados por ele no *grilling*: buscar vagas e
  freelas a partir do perfil acumulado, notícias de IA e tecnologia, montar a weekly/planning,
  montar slides de uma daily mais formal, criar reminders. Encaixam como comando novo na palheta,
  um por vez, cada um em sua entrega. Dois deles pedem capacidade que o Whis não tem hoje: **rede
  aberta** e **artefato que não é nota**.
- **Pesquisa noturna** — *"a ideia é ele passar a noite inteira pesquisando"*. Atravessa suspensão,
  logoff e reboot; o contrato de comando da entrega 4 não foi desenhado para isso, por decisão
  dele. Provavelmente reescreve o contrato quando chegar.
- **Imagem e áudio na DM** — fica com o Slack dormindo. O scope `files:read` já foi pedido ao
  admin e fica sem uso; se o Slack acordar em seis meses, isto acorda junto.
- **Google Calendar como fonte da hora** — a conta é Workspace, o que torna uma app *Internal*
  viável sem a armadilha do refresh token de 7 dias. Entra se a reunião começar a se mexer.
- ~~Comportamento proativo~~ — **especificado**: a daily nasce cinco minutos antes e avisa por
  toast, e o vigia avisa quando o Whis cai.

## Out of scope

- Reescrever a daily, o diário ou o agente: eles funcionam. Isto decide **por onde** ele os
  aciona e **por onde** eles falam com ele.
- Construir qualquer superfície antes da spec aprovada. Se o *grilling* mostrar que a resposta é
  "a daily aparece sozinha na DM às 9:55 com um botão", a construção é pequena — mas é outra
  sessão, com spec e contrato.
- Consertar os seis achados do DEFERRED um a um. Encurtar a resposta da DM é o único que dá para
  fazer antes, e mesmo esse é acabamento da entrega 3, não interface nova.
- Interface web hospedada — cortada pelo ADR 0001.
