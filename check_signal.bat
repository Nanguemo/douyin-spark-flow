@echo off
cd /d "%~dp0"
"C:/Users/Kangxu Zheng/.workbuddy/binaries/python/envs/dyspark/Scripts/pythonw.exe" check_signal.py >> "%~dp0logs\signal.log" 2>&1
