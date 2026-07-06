@echo off
setlocal
cd /d "%~dp0"
poetry run gpstation-v1-slave-launcher
