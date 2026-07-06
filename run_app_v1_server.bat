@echo off
setlocal
cd /d "%~dp0app_v1\server"
poetry run gpstation-v1-server
