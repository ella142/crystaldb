@echo off
title Repair CrystalDB Frontend

echo Stopping frontend...

powershell -NoProfile -Command ^
"$connections = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue; foreach ($c in $connections) { Stop-Process -Id $c.OwningProcess -Force }"

cd /d D:\document\aiformaterials\crystaldb\web

echo Cleaning Next.js cache...
if exist .next rmdir /s /q .next

echo Restarting frontend...

set NEXT_PUBLIC_CRYSTALDB_API_URL=http://127.0.0.1:8000

pnpm dev