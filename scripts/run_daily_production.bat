@echo off
setlocal
cd /d C:\Users\DUC\.openclaw\workspace\invest-os-vn
if not exist logs mkdir logs
echo [%date% %time%] START daily production >> logs\daily_production.log
C:\Python314\python.exe scripts\run_daily_production.py --quiet >> logs\daily_production.log 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] END daily production exit=%EXIT_CODE% >> logs\daily_production.log
exit /b %EXIT_CODE%
