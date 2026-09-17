$log = 'C:\Users\gabri\development\whis\.rota-log-log.txt'
Set-Content -Path $log -Value ("lido " + (Get-Date -Format o))
$bandejaLog = Join-Path $env:APPDATA 'whis\bandeja.log'
"existe=$(Test-Path $bandejaLog)" | Add-Content -Path $log
if (Test-Path $bandejaLog) { Get-Content $bandejaLog -Tail 12 | Add-Content -Path $log }
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*-m whis bandeja*' } | ForEach-Object { "processo $($_.ProcessId) pai=$($_.ParentProcessId) $($_.ExecutablePath)" } | Add-Content -Path $log
$cfg = Join-Path $env:APPDATA 'whis\config.toml'
Get-Content $cfg -Encoding UTF8 | Select-String '^atalho' | ForEach-Object { "config: $($_.Line)" } | Add-Content -Path $log
