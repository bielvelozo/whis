# O vigia do Whis: consulta o Agendador e avisa quando uma peça não subiu.
#
# Autossuficiente de propósito: não chama Python, não lê config.toml, não
# depende de nenhum outro arquivo do projeto — o que ele vigia é o Whis
# morrendo, e um vigia que dependesse do Whis morreria junto. Por isso o toast
# está duplicado aqui em vez de vir de avisar.ps1.
#
# Recebe a AUMID (a do atalho do Menu Iniciar, que existe mesmo com o Whis
# morto) e os nomes das tarefas a vigiar, separados por vírgula.
param(
    [Parameter(Mandatory = $true)][string]$Aumid,
    [Parameter(Mandatory = $true)][string]$Tarefas
)

$ErrorActionPreference = "Continue"

# 267011 (0x41303) é "a tarefa ainda não rodou" e 267009 (0x41301) é "rodando
# agora": nenhum dos dois é falha.
$resultadosNormais = @(0, 267011, 267009)

$problemas = @()

foreach ($nome in ($Tarefas -split ",")) {
    $nome = $nome.Trim()
    if (-not $nome) { continue }
    $tarefa = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
    if (-not $tarefa) {
        $problemas += "A tarefa $nome sumiu do Agendador."
        continue
    }
    $info = $tarefa | Get-ScheduledTaskInfo
    if ($resultadosNormais -notcontains $info.LastTaskResult) {
        $quando = if ($info.LastRunTime) { " em " + $info.LastRunTime.ToString("dd/MM HH:mm") } else { "" }
        $problemas += "$nome falhou$quando (código $($info.LastTaskResult))."
    }
    if ($info.NumberOfMissedRuns -gt 0) {
        $problemas += "$nome perdeu $($info.NumberOfMissedRuns) execução(ões)."
    }
}

$bandeja = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*-m whis bandeja*" }
if (-not $bandeja) {
    $problemas += "A bandeja não está no ar."
}

if ($problemas.Count -eq 0) {
    Write-Output "Tudo de pé: $Tarefas e a bandeja."
    exit 0
}

$problemas | ForEach-Object { Write-Output $_ }

function Escapar([string]$texto) {
    return [System.Security.SecurityElement]::Escape($texto)
}

[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$texto = ($problemas | ForEach-Object { Escapar $_ }) -join "&#10;"
$xml = "<toast><visual><binding template=""ToastGeneric""><text>O Whis precisa de você</text><text>$texto</text></binding></visual></toast>"

$documento = New-Object Windows.Data.Xml.Dom.XmlDocument
$documento.LoadXml($xml)
$toast = New-Object Windows.UI.Notifications.ToastNotification -ArgumentList $documento
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($Aumid).Show($toast)
exit 0
