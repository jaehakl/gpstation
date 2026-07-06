@echo off
setlocal
cd /d "%~dp0app_v1\slave\launcher"
poetry install
if errorlevel 1 exit /b %errorlevel%

cd /d "%~dp0app_v1\slave\executables\echo"
poetry install
