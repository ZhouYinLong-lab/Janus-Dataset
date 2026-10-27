@echo off
setlocal
chcp 65001 >nul
set "JANUS_PYTHON=D:\Environment\Miniconda3\python.exe"
if not exist "%JANUS_PYTHON%" set "JANUS_PYTHON=python"
rem 准备来源与全文、建立句段工作区并检查预算
"%JANUS_PYTHON%" "%~dp0sentence_launch.py" prepare
set "JANUS_EXIT=%ERRORLEVEL%"
pause
exit /b %JANUS_EXIT%
