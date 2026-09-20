@echo off
cd /d "%~dp0"
rem 开机后等一会儿，让网络就绪再跑
timeout /t 90 /nobreak >nul
"C:/Users/Kangxu Zheng/.workbuddy/binaries/python/envs/dyspark/Scripts/pythonw.exe" run_daily_once.py >> "%~dp0logs\boot.log" 2>&1
