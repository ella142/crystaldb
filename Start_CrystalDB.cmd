@echo off
title CrystalDB Launcher

echo ======================================
echo Starting CrystalDB...
echo ======================================

REM ---- Backend ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul

if errorlevel 1 (
    echo Starting backend...
    start "CrystalDB Backend" cmd /k "cd /d D:\document\aiformaterials\crystaldb && set "CRYSTALDB_MONGO_DATABASE=crystaldb" && set "PYTHONPATH=D:\document\aiformaterials\crystaldb\src" && D:\Users\30146\anaconda3\envs\crystaldb\python.exe -m uvicorn crystaldb.api.main:app --host 127.0.0.1 --port 8000"
) else (
    echo Backend already running on port 8000.
)

REM ---- Frontend ----
netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul

if errorlevel 1 (
    echo Starting frontend...
    start "CrystalDB Frontend" cmd /k "cd /d D:\document\aiformaterials\crystaldb\web && set "NEXT_PUBLIC_CRYSTALDB_API_URL=http://127.0.0.1:8000" && node node_modules\next\dist\bin\next dev -p 3000"
) else (
    echo Frontend already running on port 3000.
)

timeout /t 6 /nobreak >nul

start "" http://localhost:3000

exit