@echo off
cd /d "%~dp0"
python workflow.py check --settings workflow.example.json
pause
