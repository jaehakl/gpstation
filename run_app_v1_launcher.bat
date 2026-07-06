@echo off
setlocal
cd /d "%~dp0app_v1\slave\launcher"
poetry run gpstation-v1-slave-launcher
