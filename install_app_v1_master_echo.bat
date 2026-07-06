@echo off
setlocal
cd /d "%~dp0app_v1\sdk\master\js"
npm install --no-package-lock
if errorlevel 1 exit /b %errorlevel%

npm run build
if errorlevel 1 exit /b %errorlevel%

cd /d "%~dp0app_v1\master\examples\echo"
npm install
