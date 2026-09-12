# Windows: a daily nascer sozinha e o aviso chegar

Levantado em 2026-09-10 contra fontes primárias — documentação oficial da Microsoft e do Google, a
ajuda do próprio `schtasks.exe`, o código do `pystray` instalado e o registro da máquina do
usuário. Ticket: [02](../issues/02-windows-agendador-e-aviso.md).

**Isto é levantamento, não decisão.** Onde há trade-off, os dois lados estão com o custo.

---

## Resumo dos achados que mudam a decisão

1. **`schtasks` não consegue ligar "rodar assim que possível depois de perder o horário".** Não
   existe a opção. A tarefa de limpeza de hoje foi criada assim e está com
   `StartWhenAvailable: False` — **uma daily agendada por `schtasks` simplesmente não acontece se
   o PC estiver desligado às 9:55**, e não avisa. O caminho que resolve é o módulo PowerShell
   `ScheduledTasks`, que já vem no Windows e que o projeto já sabe chamar.
2. **O balão que funciona hoje não é um toast.** `pystray` usa `Shell_NotifyIcon`, o balão
   legado da bandeja — por isso funciona sem nenhum pré-requisito, e por isso **nunca** vai ter
   botão. Toast com botão é outro mecanismo, com pré-requisitos reais.
3. **Toast com botão que abre o Obsidian é viável e barato** — `activationType="protocol"` lança
   outro app pela URI, e `obsidian://` está registrado na máquina dele. O caro é o inverso: um
   botão que chame o **Whis** de volta exige um componente COM registrado, e aí a conta muda.
4. **Google Calendar tem uma pegadinha que mata o caminho ingênuo**: uma app OAuth em *Testing*
   dá refresh token que **expira em 7 dias**. Um Whis que lê a agenda pararia toda semana — o
   mesmo modo de falha do OAuth vencido de 10/09, agora agendado.
5. **Quem avisa que o Whis caiu não precisa ser o Whis**: `Get-ScheduledTaskInfo` devolve o
   `LastTaskResult` de cada tarefa sem depender de log nenhum — foi assim que se provou que a
   limpeza falhou ontem. **Já o log de eventos do Agendador está desligado nesta máquina**, o que
   derruba a rota "tarefa disparada por evento" sem um passo de administrador antes.

---

## 1. Agendar `daily` e `diario`

### O que `schtasks` faz, e o que não faz

`automacao.agendar_limpeza` monta `schtasks /Create /TN <nome> /TR <comando> /SC DAILY /ST <hora>
/F`. Para `daily` e `diario` a forma é a mesma — muda o subcomando e a hora. Isso funciona.

O problema é o que `schtasks` **não** expõe. Percorrendo a sintaxe completa do `/create` na
referência oficial ([schtasks create][schtasks]), as opções são `/sc /tn /tr /s /u /p /ru /rp /mo
/d /m /i /st /ri /et /du /k /sd /ed /it /np /z /xml /v1 /f /rl /delay /hresult` — e **nenhuma
corresponde a *Run task as soon as possible after a scheduled start is missed***. As duas que
parecem, não são:

| opção | o que realmente faz (texto oficial) |
|---|---|
| `/z` | *"Specifies to delete the task upon the completion of its schedule."* — apaga a tarefa depois da última execução |
| `/v1` | *"Creates a task visible to pre-Vista operating systems."* |

Os únicos caminhos para essa configuração são `/xml <arquivo>` (montar o XML inteiro da tarefa à
mão) ou o módulo PowerShell.

**Prova na máquina dele**, com a tarefa que existe hoje:

```
StartWhenAvailable : False
Enabled            : True
ExecutionTimeLimit : PT72H
MultipleInstances  : IgnoreNew
```

Ou seja: a limpeza criada por `schtasks` perdeu o meio-dia toda vez que o PC esteve desligado, e
não tentou de novo. **Para a limpeza isso é irrelevante** (ela roda todo dia). **Para a daily é
fatal**: o dia em que o PC ligar às 9:58 é o dia em que a daily não existe, cinco minutos antes
da reunião, sem aviso.

### O módulo `ScheduledTasks` do PowerShell

`Register-ScheduledTask` e `New-ScheduledTaskSettingsSet` vêm do módulo **`ScheduledTasks`**, que
já está na máquina (confirmado: `(Get-Command Register-ScheduledTask).Source` → `ScheduledTasks`).
**Não é dependência nova**, e o projeto **já chama PowerShell por `subprocess`** para criar os
atalhos `.lnk` (`automacao._criar_atalho`) — então é o mesmo tipo de custo que já foi aceito.

As opções de `New-ScheduledTaskSettingsSet` que importam aqui, no texto oficial
([New-ScheduledTaskSettingsSet][settingsset]):

| opção | o que faz | por que importa |
|---|---|---|
| `-StartWhenAvailable` | *"Indicates that Task Scheduler can start the task at any time after its scheduled time has passed."* | **é a que falta**: a daily nasce quando o PC ligar, mesmo atrasada |
| `-WakeToRun` | *"Indicates that Task Scheduler wakes the computer before it runs the task."* | acorda a máquina em suspensão para gerar a daily |
| `-RunOnlyIfNetworkAvailable` | *"…runs the task only when a network is available."* (exige `-NetworkId`) | a daily fala com o Claude, o Linear e o Slack |
| `-RestartCount` / `-RestartInterval` | quantas vezes e de quanto em quanto tempo tentar de novo | uma falha de rede às 9:55 ganharia segunda chance |
| `-AllowStartIfOnBatteries` / `-DontStopIfGoingOnBatteries` | rodar e continuar na bateria | o desenvolvimento é num notebook |

Trade-off honesto: `schtasks` é uma linha e o projeto já a tem; o PowerShell é três linhas
(`New-ScheduledTaskAction`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskSettingsSet` e
`Register-ScheduledTask`) com aspas para escapar num `subprocess`, e **entrega o comportamento que
a daily exige**. Uma terceira via é `schtasks /XML`, que troca o problema de escape pelo de gerar
um XML de tarefa correto.

**Não confirmado:** se `Register-ScheduledTask` funciona sem elevação para tarefa do próprio
usuário nesta máquina. A tarefa que existe hoje roda como o usuário, em `TaskPath: \`, e foi
criada por `schtasks` sem elevação — mas isso não prova o caso do cmdlet. **Vale testar antes de
escrever qualquer spec em cima disso.**

---

## 2. Avisar: o balão de hoje e o toast com botão

### O balão de hoje não é um toast

`bandeja._balao` chama `pystray.Icon.notify`. No `pystray` 0.19.5 instalado, `_win32.py` implementa
isso com `Shell_NotifyIcon` e a flag `NIF_INFO` — é o **balão legado do ícone da bandeja**, não
uma `ToastNotification`. Consequências, e elas explicam tudo:

- **Funciona sem nenhum pré-requisito** — sem AUMID, sem atalho especial, sem COM. É por isso que
  o aviso de reunião funciona hoje.
- **Nunca vai ter botão**, campo de texto ou ação: a API não tem onde pôr.
- **Depende de a bandeja estar no ar** — e a bandeja é justamente o que morre.
- Os limites de 128/256/64 caracteres já tratados em `bandeja.encurtar` são do `Shell_NotifyIcon`,
  não do toast.

### Toast com botão: o que a Microsoft exige

Um toast de verdade (`ToastNotification` + XML) tem dois pré-requisitos diferentes, e é crucial
não confundi-los:

**(a) Para o toast simplesmente aparecer**, um app desktop não empacotado precisa de um atalho no
Menu Iniciar com a propriedade `System.AppUserModel.ID`: *"Without a valid shortcut installed in
the Start screen or in All Programs, you cannot raise a toast notification from a desktop app"*
([enable-desktop-toast-with-appusermodelid][aumid]). O Whis hoje instala um atalho na pasta
**Inicialização** (que fica sob `Start Menu\Programs\Startup`) **sem** essa propriedade — então o
atalho existe, mas não serve para isto como está.

**(b) Para o clique voltar para o seu app**, é preciso um componente COM com CLSID registrado
implementando `INotificationActivationCallback` — *"a CLSID that points to your COM component that
implements INotificationActivationCallback is required"*. **Isto é caro** e é o que empurraria o
projeto para uma biblioteca maior ou para código Win32 de verdade.

**E aqui está a saída barata:** o botão não precisa voltar para o Whis. O elemento `<action>` do
schema de toast aceita `activationType="protocol"`, documentado como *"Launch a different app
using protocol activation"*, com o `arguments` carregando a URI ([element-action][action]). Um
toast pode ter **até cinco** botões (o elemento pai `actions` declara *"up to five inputs and up to
five button actions"*).

Isso significa: *"a daily de hoje está pronta"* + botão **Abrir no Obsidian** com
`arguments="obsidian://open?..."` é **protocol activation pura** — o Windows lança o Obsidian, e o
Whis não precisa estar vivo nem ter COM registrado. Já *"Gerar de novo"* precisaria voltar ao
Whis, e cai no caso (b).

**Verificado na máquina dele:** `obsidian://` está registrado em
`HKCU:\SOFTWARE\Classes\obsidian` (`URL Protocol`), com handler
`"C:\Users\gabri\AppData\Local\Programs\Obsidian\Obsidian.exe" "%1"`. O botão tem para onde ir.

### As bibliotecas, e o que cada uma cobra

| caminho | dependência | botão? | volta para o Whis? |
|---|---|---|---|
| `pystray.Icon.notify` (**hoje**) | nenhuma nova | **não** | não |
| XML + `Windows.UI.Notifications` via PowerShell | nenhuma nova (é `subprocess`, como o `.lnk`) | sim | só por protocolo |
| `windows-toasts` | pacote novo, puxa `winrt`/`winsdk` | sim | sim, com AUMID registrado |
| `win11toast` | pacote novo, também sobre WinRT | sim | sim |
| `plyer` | pacote novo, multiplataforma | aviso simples | não |

**Não confirmado, e precisa ser medido antes de decidir:** o tamanho real que `winrt`/`winsdk`
acrescenta ao ambiente, e se `windows-toasts` funciona a partir de `pythonw.exe` sem console. A
documentação de AUMID da biblioteca fala em registrar a AUMID por script, mas não detalha o
comportamento sem registro — **pergunta aberta**.

---

## 3. A hora da reunião: agenda versus horário fixo

### Horário fixo no `config.toml`

Custo: uma chave nova e nada mais. O projeto já valida hora
(`configuracao._hora`, usada em `[diario].hora_da_tarefa`). Limitação: reunião que muda de horário,
feriado, e o dia em que a daily é adiada.

### Google Calendar

A pegadinha que decide, e ela é grave para uma máquina doméstica. Na documentação do próprio
Google ([Manage app audience][audience]):

> *"Projects configured with a publishing status of **Testing** are limited to up to 100 test users
> listed in the OAuth consent screen."*
>
> *"Authorizations by a test user will expire seven days from the time of consent. If your OAuth
> client requests an `offline` access type and receives a refresh token, that token will also
> expire."*

E na referência de OAuth ([Using OAuth 2.0][oauth2]), a mesma regra: *"A Google Cloud Platform
project with an OAuth consent screen configured for an external user type and a publishing status
of 'Testing' is issued a refresh token expiring in 7 days"*.

**Um Whis que lê a agenda com uma app em *Testing* pararia de ler a cada sete dias** — e pararia
exatamente como o OAuth do Claude parou em 10/09: calado, numa tarefa agendada, descoberto na
reunião. É o mesmo modo de falha que esta entrega existe para resolver.

As saídas, e cada uma tem um custo:

- **Publicar a app ("In production")**: *"A project's publishing status is considered In production
  after selecting the Publish app button"*, e a app fica disponível para qualquer conta Google. A
  verificação do Google entra em cena para nome e logo na tela de autorização; escopos sensíveis
  (e Calendar é um deles) têm exigência própria de verificação. **Não consegui confirmar**, em
  fonte primária, se uma app não verificada em produção com `calendar.readonly` continua
  funcionando com a tela de aviso, e por quanto tempo. É a pergunta que decide este caminho.
- **App "Internal"**: *"Projects associated with a Google Cloud Organization can configure Internal
  users to limit authorization requests to members of the organization."* Se a agenda da reunião
  estiver numa conta **Google Workspace do trabalho**, este é o caminho limpo — mas depende de a
  organização permitir, o que é o mesmo tipo de dependência de admin que o Slack já tem.
  **Pergunta para ele: a agenda da daily está numa conta pessoal ou do trabalho?**
- **Outras razões de o refresh token morrer**, todas documentadas: o usuário revogar o acesso, o
  token ficar seis meses sem uso, o usuário trocar a senha (quando há escopo do Gmail), exceder o
  número máximo de refresh tokens vivos, ou o acesso ter sido concedido por tempo limitado.

Contra o ADR 0001: uma leitura sob demanda da agenda é do mesmo tipo que o projeto já faz com
Linear e Slack — rede, sim; servidor, não. O que **não** é do mesmo tipo é o ciclo de consentimento
OAuth, que hoje o projeto só tem via conta Claude — e que já provou ser um ponto de falha.

---

## 4. Quem avisa que o Whis caiu

O buraco que o ticket 01 achou: quem falha antes de subir não escreve log, e o único aviso
espontâneo (o balão) depende da bandeja estar no ar.

### O que o Agendador oferece sozinho

**`Get-ScheduledTaskInfo` devolve o resultado da última execução, sem depender de log nenhum.**
Foi como a falha de ontem ficou provada:

```
TaskName           : SecondBrain-Limpeza
LastRunTime        : 10/09/2026 12:00:01
LastTaskResult     : 1
NextRunTime        : 11/09/2026 12:00:00
NumberOfMissedRuns : 0
```

`LastTaskResult: 1` é o `No module named second_brain` de ontem ao meio-dia, registrado pelo
próprio Windows. **Qualquer processo pode ler isso a qualquer hora** — inclusive a bandeja, que
fica no ar o dia inteiro. É a rota mais barata para "a daily de hoje não nasceu": não precisa de
componente novo, de log ligado nem de privilégio.

O limite: isso só cobre o que é **tarefa agendada**. Não cobre o atendente, que é um atalho de
logon, nem a própria bandeja.

### A rota por evento, e por que ela está bloqueada aqui

`schtasks /Create /SC ONEVENT` existe, com `/EC <canal>` — *"Specifies the event channel name
triggered by the ONEVENT schedule type that matches a system event log criteria"* — e o próprio
`schtasks /Create /?` traz o exemplo de disparar algo quando um evento é publicado. Em tese, uma
segunda tarefa poderia observar o canal `Microsoft-Windows-TaskScheduler/Operational` e avisar
quando a tarefa da daily terminasse com código diferente de zero.

**Só que esse canal está desligado nesta máquina** (é o padrão do Windows):

```
LogName            : Microsoft-Windows-TaskScheduler/Operational
IsEnabled          : False
RecordCount        :
```

Ligá-lo é um passo de administrador (`wevtutil sl <canal> /e:true`), e é configuração de sistema —
exatamente o tipo de coisa que um projeto "fino e 100% local" prefere não exigir do usuário. **Se
a decisão for por esta rota, ligar o canal vira passo humano de roteiro, com o custo que isso tem.**

### O caso que nenhuma das duas cobre

O atendente e a bandeja **não são tarefas agendadas**: são atalhos de logon. Se o atalho aponta
para um módulo que não existe — o que está acontecendo agora — nada no Windows registra isso, e
`LastTaskResult` não existe para eles. As opções que apareceram no levantamento, todas com custo:

- Transformar o atendente e a bandeja em **tarefas agendadas com gatilho de logon** (`/SC ONLOGON`
  ou `New-ScheduledTaskTrigger -AtLogOn`) em vez de atalhos `.lnk`. Ganha-se `LastTaskResult`,
  `-RestartCount` e a possibilidade de reiniciar sozinho. Perde-se a simplicidade do atalho que o
  usuário vê, move e apaga pelo Explorer — que foi a razão declarada da escolha original
  (`automacao._criar_atalho`).
- **Um heartbeat**: o processo que está vivo escreve um arquivo com a hora, e outro processo
  reclama se ele envelhecer. Resolve o caso de "subiu e morreu depois", não o de "nunca subiu",
  a menos que quem reclama seja independente dos dois.
- **Aceitar que o aviso venha de fora da máquina** — a DM do Slack, que é onde ele está. Mas o
  atendente também morre, então quem avisaria seria a daily agendada, e não o atendente.

**A pergunta que sobra para o grilling, e ela é de produto, não técnica:** quando o Whis inteiro
está morto, **onde** esse aviso pode aparecer, sabendo que nenhuma peça do Whis é confiável para
dá-lo?

---

## Fontes

- [schtasks create — sintaxe completa e descrição de cada opção][schtasks]
- [New-ScheduledTaskSettingsSet — módulo ScheduledTasks][settingsset]
- [element-action — schema do toast, atributos `activationType` e `arguments`][action]
- [How to enable desktop toast notifications through an AppUserModelID][aumid]
- [Google — Manage app audience: Internal/External, Testing/In production][audience]
- [Google — Using OAuth 2.0: expiração do refresh token][oauth2]
- `pystray` 0.19.5, `_win32.py` (`Shell_NotifyIcon` + `NIF_INFO`) — no `.venv` do projeto
- Máquina do usuário: `Get-ScheduledTaskInfo`, `Get-ScheduledTask`, `Get-WinEvent -ListLog`,
  `HKCU:\SOFTWARE\Classes\obsidian`

[schtasks]: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create
[settingsset]: https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset
[action]: https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/element-action
[aumid]: https://learn.microsoft.com/en-us/windows/win32/shell/enable-desktop-toast-with-appusermodelid
[audience]: https://support.google.com/cloud/answer/15549945
[oauth2]: https://developers.google.com/identity/protocols/oauth2
