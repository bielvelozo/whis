$log = 'C:\Users\gabri\development\whis\.rota-parar-log.txt'
Set-Content -Path $log -Value ("inicio " + (Get-Date -Format o))
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*-m whis bandeja*' } | ForEach-Object {
    "parando $($_.ProcessId) $($_.CommandLine)" | Add-Content -Path $log
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
$restantes = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*-m whis bandeja*' })
"restantes=$($restantes.Count)" | Add-Content -Path $log
