@echo off
cd /d "%~dp0"
python workflow.py prepare --settings workflow.example.json
pause
