@echo off
REM TikTok Affiliate Pipeline — called by Windows Task Scheduler
REM Starts ComfyUI if not running, then generates and posts one carousel.

set PYTHON=C:\Users\james\ComfyUI\venv\Scripts\python.exe
set COMFYUI_DIR=C:\Users\james\ComfyUI
set PIPELINE_DIR=C:\Users\james\youtube\TikTok

REM Start ComfyUI in background if not already running
tasklist /FI "IMAGENAME eq python.exe" | find "python.exe" >nul 2>&1
if errorlevel 1 (
    echo Starting ComfyUI...
    start /B "" "%PYTHON%" "%COMFYUI_DIR%\main.py" --gpu-only --listen 127.0.0.1 >> "%PIPELINE_DIR%\logs\comfyui.log" 2>&1
    timeout /t 20 /nobreak >nul
)

REM Run the pipeline
cd /d "%PIPELINE_DIR%"
"%PYTHON%" run_pipeline.py womens-fashion

exit /b %errorlevel%
