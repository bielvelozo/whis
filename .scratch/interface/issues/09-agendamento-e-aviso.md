# 09 — Camada 2: agendamento confiável e o aviso

Type: task
Status: resolved
Blocked by: 07

**What to build:** a daily nascendo sozinha cinco minutos antes da reunião mesmo que o PC estivesse
desligado na hora; um jeito do Whis dar toast de verdade; e um vigia fora do Whis.

Spec: [../spec.md](../spec.md), *Os avisos* e *Horário por dia da semana*. Fatos:
[research/02](../research/02-windows-agendador-e-aviso.md).

- [x] `[daily]` ganha horários **por dia da semana** (uma tabela: `segunda`…`domingo`, `HH:MM`,
      dia ausente = sem daily), validados como `configuracao._hora`, no `MODELO_DE_CONFIGURACAO`
      com os valores do usuário: seg/ter/qui `13:55`, qua/sex `10:25`.
- [x] `automacao.py` cria tarefas pelo módulo PowerShell `ScheduledTasks`
      (`New-ScheduledTaskAction/Trigger/SettingsSet` + `Register-ScheduledTask`) com
      `-StartWhenAvailable`, `-WakeToRun` e `-AllowStartIfOnBatteries`; nunca mais `schtasks`.
      Uma tarefa `Whis-Daily` com um gatilho semanal por dia configurado; `Whis-Limpeza` migrada.
- [x] `avisos.py`: porta de toast (`ToastNotification` por PowerShell + `Windows.UI.Notifications`
      com a AUMID da camada 0), título, corpo e **botão opcional** com `activationType="protocol"`.
      Sai por `executar` injetável.
- [x] O vigia: um script `.ps1` próprio (em `src/whis/`, empacotado) que consulta
      `Get-ScheduledTaskInfo` das tarefas do Whis e dispara toast quando `LastTaskResult` ≠ 0 ou
      uma execução foi perdida; registrado como tarefa `Whis-Vigia` diária. Ele não importa nem
      chama Python.
- [x] `whis windows` instala/remove tudo isso; `--limpeza` continua explícito.
- [x] Testes por `executar`: os scripts PowerShell montados; hora certa por dia; nenhum teste
      toca o Agendador.
- [x] Suíte inteira verde; testes existentes de `agendar_limpeza` que afirmam `schtasks` podem
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

**Camada 2 construída** (2026-09-12, executor "windows"; sem commit, sem tocar no Agendador).

- Novos: `src/whis/agendar_tarefa.ps1`, `src/whis/avisar.ps1`, `src/whis/vigia.ps1` (os três com
  BOM, validados pelo parser do PowerShell 5.1, nenhum executado), `src/whis/avisos.py`,
  `tests/test_agendamento_e_aviso.py` (41 testes). Alterados: `configuracao.py`
  (`daily_horarios`, `DIAS_DA_SEMANA`), `automacao.py` (tudo pelo `ScheduledTasks`;
  `agendar_daily`/`agendar_vigia` e os pares), `__main__.py` (`--daily`, modelo, ajuda).
- Suíte: **945 verdes** (eram 904), 8 desselecionados.
- Testes existentes editados, só em `tests/test_acabamento.py`, porque liam o comando `schtasks`
  que deixou de existir: `test_a_limpeza_agendada_roda_o_comando_limpar_diariamente` (afirmava
  `schtasks /Create` e lia `/TR`; agora afirma `-File agendar_tarefa.ps1`, `-Nome`, `-Gatilhos
  Daily=12:00`, `-Argumentos`) e `test_a_limpeza_agendada_nunca_apaga_direto` (lia o comando
  em `/TR`; agora em `-Argumentos`). `remover_legado` continua por `schtasks /Delete` — o teste
  que o afirma em `test_arrumar_a_casa.py` não podia mudar, e a tarefa legada foi criada por ele.
- Pendência: `--remover --limpeza` sozinho deixa o vigia vigiando `Whis-Limpeza` até um novo
  `whis windows --daily`; a mensagem impressa avisa isso.

**Camada 2 entregue e fechada** (2026-09-12; executor `windows`, revisão, sondas e gate na sessão principal).

- Três scripts empacotados com BOM: `agendar_tarefa.ps1` (módulo `ScheduledTasks`, gatilhos `Dia=HH:MM`
  numa string), `avisar.ps1` (toast `ToastGeneric` com botão `activationType="protocol"`), `vigia.ps1`
  (autossuficiente; imprime cada problema na saída e dispara um toast só). `avisos.avisar(...)` nunca
  levanta. `[daily].horarios` como tabela inline; `whis windows --daily` agenda `Whis-Daily` e
  `Whis-Vigia` (daily +10 min e ronda às 09:00); `--limpeza` migrado para o módulo.
- **Sondas na máquina, sessão principal** (tudo apagado em seguida):
  - `automacao._registrar_tarefa(...)` → tarefa descartável com `-m whis daily --config "C:\...\pasta com espaco\config.toml"`
    intacto, `MSFT_TaskWeeklyTrigger` Monday 13:55 e Wednesday 10:25, `MSFT_TaskDailyTrigger` 09:00,
    `StartWhenAvailable=True WakeToRun=True DisallowStartIfOnBatteries=False Limit=PT30M Multi=IgnoreNew`;
    `_desregistrar_tarefa` → apagada; `_tarefa_agendada` → False.
  - `avisar.ps1` com botão e texto contendo `< & "` → saiu 0 pela AUMID do PowerShell (que tem atalho no
    Menu Iniciar); pela AUMID `Whis.Agente` também sai 0, mas o toast só aparece depois de o usuário
    criar o atalho com `whis windows` — conferência dele.
  - `vigia.ps1 -Tarefas Whis-Daily,SecondBrain-Limpeza` → imprimiu "A tarefa Whis-Daily sumiu do
    Agendador.", "SecondBrain-Limpeza falhou em 11/09 12:00 (código 1)." e "A bandeja não está no ar."
    — exatamente as três falhas silenciosas que motivaram a entrega.
- Suíte: **945 verdes** (eram 904; 41 novos em `tests/test_agendamento_e_aviso.py`), 8 desselecionados.
  Testes existentes editados (dois, em `test_acabamento.py`): `test_a_limpeza_agendada_roda_o_comando_limpar_diariamente`
  e `test_a_limpeza_agendada_nunca_apaga_direto` afirmavam `schtasks /Create` e `/TR`; agora afirmam o
  `-File agendar_tarefa.ps1` e `-Argumentos`.
- Pendências: `--remover --limpeza` sozinho deixa o vigia vigiando `Whis-Limpeza` até um novo
  `whis windows --daily` (a mensagem avisa); `remover_legado` segue por `schtasks /Delete`, que é o
  certo para uma tarefa que nasceu por `schtasks`.
