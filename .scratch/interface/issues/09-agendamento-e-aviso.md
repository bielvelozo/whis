# 09 — Camada 2: agendamento confiável e o aviso

Type: task
Status: ready-for-agent
Blocked by: 07

**What to build:** a daily nascendo sozinha cinco minutos antes da reunião mesmo que o PC estivesse
desligado na hora; um jeito do Whis dar toast de verdade; e um vigia fora do Whis.

Spec: [../spec.md](../spec.md), *Os avisos* e *Horário por dia da semana*. Fatos:
[research/02](../research/02-windows-agendador-e-aviso.md).

- [ ] `[daily]` ganha horários **por dia da semana** (uma tabela: `segunda`…`domingo`, `HH:MM`,
      dia ausente = sem daily), validados como `configuracao._hora`, no `MODELO_DE_CONFIGURACAO`
      com os valores do usuário: seg/ter/qui `13:55`, qua/sex `10:25`.
- [ ] `automacao.py` cria tarefas pelo módulo PowerShell `ScheduledTasks`
      (`New-ScheduledTaskAction/Trigger/SettingsSet` + `Register-ScheduledTask`) com
      `-StartWhenAvailable`, `-WakeToRun` e `-AllowStartIfOnBatteries`; nunca mais `schtasks`.
      Uma tarefa `Whis-Daily` com um gatilho semanal por dia configurado; `Whis-Limpeza` migrada.
- [ ] `avisos.py`: porta de toast (`ToastNotification` por PowerShell + `Windows.UI.Notifications`
      com a AUMID da camada 0), título, corpo e **botão opcional** com `activationType="protocol"`.
      Sai por `executar` injetável.
- [ ] O vigia: um script `.ps1` próprio (em `src/whis/`, empacotado) que consulta
      `Get-ScheduledTaskInfo` das tarefas do Whis e dispara toast quando `LastTaskResult` ≠ 0 ou
      uma execução foi perdida; registrado como tarefa `Whis-Vigia` diária. Ele não importa nem
      chama Python.
- [ ] `whis windows` instala/remove tudo isso; `--limpeza` continua explícito.
- [ ] Testes por `executar`: os scripts PowerShell montados; hora certa por dia; nenhum teste
      toca o Agendador.
- [ ] Suíte inteira verde; testes existentes de `agendar_limpeza` que afirmam `schtasks` podem
      ser editados, listados no comentário.

## Notas para o executor

- Sonda feita na sessão principal antes desta camada: se `Register-ScheduledTask` funciona sem
  elevação nesta máquina. Resultado no comentário abaixo.
- O `.ps1` do vigia precisa rodar com `-ExecutionPolicy Bypass -File`; PowerShell 5.1.
- Toast por PowerShell precisa de uma AUMID cujo atalho exista no Menu Iniciar — a da camada 0.
  Para o vigia, a mesma AUMID serve (o atalho está lá mesmo com o Whis morto).

## Comments

**Sonda feita na sessão principal, 2026-09-12** (passo 4 do pipeline), nesta máquina, sem elevação
(`IsInRole(Administrator) = False`), PowerShell 5.1.26100:

```
Register-ScheduledTask -TaskName Whis-Sonda-Descartavel -Action (cmd.exe /c exit 0)
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 03:00)
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries) -Force
→ registrada, State=Ready, StartWhenAvailable=True, WakeToRun=True, RunAs=gabri, LogonType=Interactive
Get-ScheduledTaskInfo → LastTaskResult 267011 (nunca rodou), NumberOfMissedRuns 0, NextRunTime 14/09 03:00
Unregister-ScheduledTask -Confirm:$false → apagada
```

Conclusões para a camada: o módulo funciona **sem elevação** para tarefa do próprio usuário; a
propriedade de bateria se lê como `Settings.DisallowStartIfOnBatteries` (o `-AllowStartIfOnBatteries`
a põe em `False`; `AllowStartIfOnBatteries` não existe como propriedade); `LastTaskResult 267011`
(`0x41303`) é "a tarefa ainda não rodou" — o vigia não pode tratá-lo como falha. A tarefa antiga
`SecondBrain-Limpeza` continua no Agendador desta máquina (é o usuário quem a remove com
`whis windows --remover-legado`).
