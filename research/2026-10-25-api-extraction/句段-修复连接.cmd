@echo off
setlocal
chcp 65001 >nul
set "JANUS_PYTHON=D:\Environment\Miniconda3\python.exe"
if not exist "%JANUS_PYTHON%" set "JANUS_PYTHON=python"
rem 只做连接诊断并准备恢复，不发送生成请求
"%JANUS_PYTHON%" "%~dp0sentence_launch.py" repair
set "JANUS_EXIT=%ERRORLEVEL%"
pause
exit /b %JANUS_EXIT%
