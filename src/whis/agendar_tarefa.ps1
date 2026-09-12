# Registra (ou substitui) uma tarefa no Agendador pelo módulo ScheduledTasks.
#
# É este módulo, e não o schtasks, que liga -StartWhenAvailable: sem ele a
# tarefa de um dia em que o PC estava desligado no horário não acontece nunca.
# Os gatilhos vêm numa string só, "Dia=HH:MM" separados por vírgula, com o dia
# em inglês (Monday..Sunday) ou "Daily" para todo dia. Chamado por whis.automacao.
param(
    [Parameter(Mandatory = $true)][string]$Nome,
    [Parameter(Mandatory = $true)][string]$Executavel,
    [Parameter(Mandatory = $true)][string]$Argumentos,
    [Parameter(Mandatory = $true)][string]$Diretorio,
    [Parameter(Mandatory = $true)][string]$Gatilhos
)

$ErrorActionPreference = "Stop"

$acao = New-ScheduledTaskAction -Execute $Executavel -Argument $Argumentos -WorkingDirectory $Diretorio

$triggers = @()
foreach ($gatilho in ($Gatilhos -split ",")) {
    $partes = $gatilho.Trim() -split "=", 2
    if ($partes.Count -ne 2 -or -not $partes[0] -or -not $partes[1]) {
        throw "Gatilho inválido: '$gatilho' (esperado Dia=HH:MM ou Daily=HH:MM)."
    }
    $dia = $partes[0].Trim()
    $hora = [datetime]::ParseExact($partes[1].Trim(), "HH:mm", $null)
    if ($dia -eq "Daily") {
        $triggers += New-ScheduledTaskTrigger -Daily -At $hora
    } else {
        $triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dia -At $hora
    }
}
if ($triggers.Count -eq 0) {
    throw "A tarefa '$Nome' precisa de pelo menos um gatilho."
}

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $triggers -Settings $settings -Force | Out-Null
