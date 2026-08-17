@echo off
REM AxiomDesk 一键启动 (Windows)
setlocal
set PORT=8137
set HOST=127.0.0.1
set DIR=%~dp0
cd /d "%DIR%"

set URL=http://%HOST%:%PORT%/
if "%PYTHON%"=="" set PYTHON=python

REM 健康检查
powershell -Command "try { (Invoke-WebRequest -Uri '%URL%api/health' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL%==0 (
  echo AxiomDesk already running: %URL%
  goto :open
)

echo Starting AxiomDesk on port %PORT% ...
start "" "%PYTHON%" -m uvicorn server.app:app --host %HOST% --port %PORT%
for /L %%i in (1,1,30) do (
  powershell -Command "try { (Invoke-WebRequest -Uri '%URL%api/health' -UseBasicParsing -TimeoutSec 1).StatusCode } catch { exit 1 }" >nul 2>&1
  if %ERRORLEVEL%==0 goto :open
  timeout /t 1 >nul
)

:open
echo Open: %URL%
start "" "%URL%"
endlocal
