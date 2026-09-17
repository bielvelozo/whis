$repo = 'C:\Users\gabri\development\whis'
$m = "$repo\.rota-marcador.txt"
Set-Content -Path $m -Value (Get-Date -Format o)
Set-Content -Path 'C:\Users\gabri\rota-marcador.txt' -Value (Get-Date -Format o)
$cfg = Join-Path $env:APPDATA 'whis\config.toml'
"config=$cfg existe=$(Test-Path $cfg)" | Add-Content -Path $m
Get-Content $cfg | Select-String '^atalho' | ForEach-Object { $_.Line } | Add-Content -Path $m
Get-Process pythonw -ErrorAction SilentlyContinue | ForEach-Object { "pythonw $($_.Id)" } | Add-Content -Path $m
