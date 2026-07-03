@echo off
REM 백엔드 실행 (새 창)
cd ./apps/platform/api
start cmd /k "call run.bat"
cd ../../..

REM 프론트엔드 실행 (새 창)
cd ./apps/platform/ui   
start cmd /k "call run.bat"
cd ../../..

rem @echo off
rem REM Worker 실행 (새 창)
rem cd ./apps/worker/fastapi/
rem start cmd /k "call fastapi.bat"
rem cd ../../../..
    



