@echo off
setlocal
cd /d "%~dp0app_v1\launcher"
poetry run launcher
