@echo off
setlocal
chcp 65001 >nul
set "JANUS_PYTHON=D:\Environment\Miniconda3\python.exe"
if not exist "%JANUS_PYTHON%" set "JANUS_PYTHON=python"
"%JANUS_PYTHON%" "%~dp0candidate_launch.py" status
set "JANUS_EXIT=%ERRORLEVEL%"
pause
exit /b %JANUS_EXIT%
