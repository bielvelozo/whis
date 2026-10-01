param([ValidateSet('login', 'medir', 'medir-com-janela')][string]$Modo = 'medir')

$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$worktree = (Resolve-Path (Join-Path $aqui '..\..\..\..')).Path
$python = 'C:\Users\gabri\development\whis\.venv\Scripts\python.exe'
$log = Join-Path $aqui "rodada-$Modo.log"

$env:PYTHONPATH = Join-Path $worktree 'src'
$env:PYTHONUTF8 = '1'
$argumentos = @(Join-Path $aqui 'prototipo.py')
if ($Modo -eq 'login') { $argumentos += '--login' }
if ($Modo -eq 'medir-com-janela') { $argumentos += '--com-janela' }

Set-Location $worktree
"inicio $(Get-Date -Format o) modo=$Modo LOCALAPPDATA=$env:LOCALAPPDATA" | Out-File -Encoding utf8 $log
& $python @argumentos *>&1 | ForEach-Object { "$_" } | Out-File -Encoding utf8 -Append $log
"fim $(Get-Date -Format o) saida=$LASTEXITCODE" | Out-File -Encoding utf8 -Append $log
