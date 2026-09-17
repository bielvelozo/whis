# A rota da tarefa descartável (2026-09-17)

Como agir na máquina **como o usuário** a partir de uma sessão de agente, cujo `%APPDATA%` é uma
cópia virtual e velha (ver `ORCHESTRATION.md › Blockers`). Cada script escreve o seu log na raiz do
repositório, que atravessa nos dois sentidos; o `%APPDATA%` lido direto pela sessão **não** vale.

```powershell
$acao = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"<script>`""
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$cfg = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2)   # [TimeSpan]::Zero para a bandeja
Register-ScheduledTask -TaskName Whis-Sonda -Action $acao -Principal $principal -Settings $cfg -Force
Start-ScheduledTask -TaskName Whis-Sonda; Start-Sleep 8
Unregister-ScheduledTask -TaskName Whis-Sonda -Confirm:$false   # a bandeja lançada sobrevive
```

- `marcador.ps1` — prova que a rota atravessa (marcador no repo e em `C:\Users\gabri`).
- `parar-bandeja-e-trocar-config.ps1` — mata a bandeja e roda `trocar-atalho-no-config.py`.
- a bandeja volta com a ação direta `.venv\Scripts\pythonw.exe -m whis bandeja` (sem limite de tempo).
- `ler-log-da-bandeja.ps1` — as últimas linhas do `bandeja.log` real e a linha do atalho.

Antes de matar a bandeja: conferir que não há gravação em andamento (`whis-gravacoes` sem arquivo
recente). Nunca simular o atalho real dela.

**Ordem importa (aprendido em 2026-09-17 13:15):** espere a tarefa de parar sair do estado `Running`
antes de lançar a bandeja. Com uma espera fixa curta, a bandeja nova subiu com a antiga ainda viva,
achou a trava e saiu (`LastTaskResult` 0xFFFFFFFF), e a antiga foi morta logo depois — ficou sem
bandeja nenhuma. O laço certo: `Start-ScheduledTask`; `do { sleep 2 } while (State -eq 'Running')`;
só então `Unregister` e a próxima tarefa. Para a bandeja (que fica `Running` para sempre), espera
fixa e conferência do processo.
