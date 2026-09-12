# 02 — Windows: a daily nascer sozinha e o aviso chegar

Type: research
Status: resolved
Blocked by: 01

## Question

O que é preciso, **sem stack nova e dentro do ADR 0001**, para que:

- a **daily nasça sozinha** alguns minutos antes da reunião, e
- o usuário **saiba disso** sem abrir terminal nem log?

Levantar fatos, não decidir:

- **Agendar**: `schtasks` já é usado para a limpeza (`automacao.agendar_limpeza`). O que muda para
  agendar `daily` e `diario`? Tarefa que não roda com a máquina desligada — o que o Agendador
  oferece (*Run task as soon as possible after a scheduled start is missed*) e como isso se pede
  pela linha de comando (`schtasks /Create` aceita? precisa de XML por `/XML`?).
- **A hora da reunião**: horário fixo em `config.toml` versus **Google Calendar**. Para o
  Calendar, levantar o custo real: OAuth de conta Google, que credencial precisa existir, o que
  isso significa numa máquina doméstica, e se cabe no ADR 0001 (é rede, mas é leitura sob demanda
  como o Linear e o Slack já são).
- **Avisar**: `pystray.Icon.notify` já existe e já é usado (ticket 01) — mas **sem botão**. O que
  custa um *toast* do Windows 11 **com botão** a partir de Python: `winrt`/`windows-toasts`,
  `plyer`, ou XML pelo PowerShell com `Windows.UI.Notifications`. Para cada um: dependência nova?,
  funciona com `pythonw.exe` sem console?, o botão consegue abrir um `obsidian://` ou um arquivo?,
  o que acontece se o Whis não estiver no ar quando o usuário clicar.
- **A falha que ninguém vê**: como um processo agendado avisa que **não conseguiu nem começar**
  (OAuth vencido, módulo errado, config inválida). Quem dá o aviso, se quem falhou é o próprio
  Whis? O Agendador do Windows sabe reagir a uma tarefa que saiu com erro?

O resultado alimenta o 05 (opções com fatos, não achismo) e o 06.

## Answer

Tudo o que a daily precisa é possível sem stack nova, **menos uma coisa**, e há uma armadilha de
OAuth que mataria o caminho ingênuo da agenda. Detalhes e fontes em
[../research/02-windows-agendador-e-aviso.md](../research/02-windows-agendador-e-aviso.md).

- **`schtasks` não serve para a daily.** Não existe opção que ligue *"rodar assim que possível
  depois de perder o horário"* — percorrida a sintaxe inteira do `/create` na referência oficial.
  A tarefa de hoje está com `StartWhenAvailable: False`, o que significa que **uma daily agendada
  assim não acontece se o PC estiver desligado às 9:55**, e não avisa. O caminho que resolve é o
  módulo PowerShell `ScheduledTasks` (`-StartWhenAvailable`, `-WakeToRun`, `-RestartCount`,
  `-RunOnlyIfNetworkAvailable`), que **já vem no Windows** e que o projeto já sabe invocar por
  `subprocess` — é o mesmo custo que criar o `.lnk` já cobrou.
- **O balão de hoje não é um toast.** `pystray` usa `Shell_NotifyIcon`/`NIF_INFO`, o balão legado
  da bandeja: funciona sem pré-requisito nenhum e **nunca** terá botão. Toast é outro mecanismo.
- **Toast com botão que abre o Obsidian é barato; toast com botão que volta ao Whis é caro.** O
  `<action activationType="protocol">` lança outro app pela URI, e `obsidian://` **está
  registrado na máquina dele** — nada precisa estar vivo. Já um botão *"Gerar de novo"* exige um
  componente COM com CLSID implementando `INotificationActivationCallback`. E para o toast
  aparecer, um app não empacotado precisa de atalho no Menu Iniciar **com AUMID** — o atalho de
  hoje não tem.
- **Google Calendar tem uma pegadinha que decide**: uma app OAuth em *Testing* recebe refresh
  token que **expira em 7 dias** (texto do Google, citado no achado). O Whis pararia de ler a
  agenda toda semana, calado, numa tarefa agendada — **o mesmo modo de falha do OAuth vencido de
  10/09**. As saídas são publicar a app ou usar uma app *Internal* de uma organização Workspace,
  e aí **a pergunta é dele: a agenda da daily está numa conta pessoal ou do trabalho?**
- **Quem avisa que o Whis caiu não precisa ser o Whis**: `Get-ScheduledTaskInfo` devolve
  `LastTaskResult` de qualquer tarefa, sem log e sem privilégio — foi assim que a falha de ontem
  ficou provada. Mas isso **só cobre tarefas agendadas**; o atendente e a bandeja são atalhos de
  logon e não deixam rastro nenhum quando não sobem. E a rota "tarefa disparada por evento"
  (`/SC ONEVENT`) está bloqueada aqui: o canal `Microsoft-Windows-TaskScheduler/Operational`
  **está desligado nesta máquina**, e ligá-lo é passo de administrador.

**Sobra para o grilling, e é pergunta de produto:** quando o Whis inteiro está morto, onde o aviso
pode aparecer, sabendo que nenhuma peça do Whis é confiável para dá-lo?
