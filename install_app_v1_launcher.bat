@echo off
setlocal
cd /d "%~dp0app_v1\launcher"
poetry install
if errorlevel 1 exit /b %errorlevel%

cd /d "%~dp0app_v1\slaves\echo"
poetry install
