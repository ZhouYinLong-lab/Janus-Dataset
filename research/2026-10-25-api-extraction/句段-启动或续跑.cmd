@echo off
setlocal
chcp 65001 >nul
set "JANUS_PYTHON=D:\Environment\Miniconda3\python.exe"
if not exist "%JANUS_PYTHON%" set "JANUS_PYTHON=python"
rem 先跑五篇试跑，验收通过后启动全库提取
"%JANUS_PYTHON%" "%~dp0sentence_launch.py" run
set "JANUS_EXIT=%ERRORLEVEL%"
pause
exit /b %JANUS_EXIT%
