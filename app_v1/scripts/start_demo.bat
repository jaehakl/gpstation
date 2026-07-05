@echo off
setlocal
cd /d %~dp0..
start "GP Station v1 Server" cmd /k "cd server && call run.bat"
timeout /t 2 >nul
start "GP Station v1 Worker" cmd /k "cd worker && call run.bat"
start "GP Station v1 Web" cmd /k "cd example\web && call run.bat"
