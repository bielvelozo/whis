# Mostra um toast do Windows em nome da AUMID do Whis.
#
# O botão, quando vem, é activationType="protocol": o Windows abre a URI
# (obsidian://...) sozinho, sem o Whis precisar estar vivo para atender o
# clique. O escape do XML é feito aqui, uma vez só. Chamado por whis.avisos.
param(
    [Parameter(Mandatory = $true)][string]$Titulo,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Texto,
    [Parameter(Mandatory = $true)][string]$Aumid,
    [string]$RotuloDoBotao = "",
    [string]$UriDoBotao = ""
)

$ErrorActionPreference = "Stop"

[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

function Escapar([string]$texto) {
    return [System.Security.SecurityElement]::Escape($texto)
}

$acoes = ""
if ($RotuloDoBotao -and $UriDoBotao) {
    $acoes = "<actions><action content=""$(Escapar $RotuloDoBotao)"" activationType=""protocol"" arguments=""$(Escapar $UriDoBotao)""/></actions>"
}

$xml = "<toast><visual><binding template=""ToastGeneric""><text>$(Escapar $Titulo)</text><text>$(Escapar $Texto)</text></binding></visual>$acoes</toast>"

$documento = New-Object Windows.Data.Xml.Dom.XmlDocument
$documento.LoadXml($xml)
$toast = New-Object Windows.UI.Notifications.ToastNotification -ArgumentList $documento
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($Aumid).Show($toast)
