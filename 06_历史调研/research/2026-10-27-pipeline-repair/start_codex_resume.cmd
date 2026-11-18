@echo off
chcp 65001 >nul
setlocal
cd /d D:\Projects\Dog\Janus-Dataset
set "CODEX=C:\Users\26585\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe"
set "LOG=research\2026-10-27-pipeline-repair\local\codex_resume.log"
if not exist "research\2026-10-27-pipeline-repair\local" mkdir "research\2026-10-27-pipeline-repair\local"
echo [%DATE% %TIME%] start >> "%LOG%"
type "research\2026-10-27-pipeline-repair\codex_handoff_prompt.md" | "%CODEX%" exec -s workspace-write -c approval_policy=never - >> "%LOG%" 2>&1
echo [%DATE% %TIME%] exit %ERRORLEVEL% >> "%LOG%"
endlocal
