@echo off
cd /d "%~dp0"
"C:/Users/Kangxu Zheng/.workbuddy/binaries/python/envs/dyspark/Scripts/pythonw.exe" run_daily_once.py >> "%~dp0logs\task.log" 2>&1
