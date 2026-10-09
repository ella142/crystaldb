@echo off
title Stop CrystalDB

powershell -NoProfile -Command ^
"$ports = @(8000,3000); foreach ($port in $ports) { $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach ($c in $connections) { Write-Host ('Stopping CrystalDB port ' + $port + ' PID ' + $c.OwningProcess); Stop-Process -Id $c.OwningProcess -Force } }"

echo.
echo CrystalDB stopped.
pause