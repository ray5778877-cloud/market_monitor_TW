@echo off
REM 平日 08:30：先跑回測寫入持倉快照，再推播 LINE
cd /d "%~dp0"
if not exist "data" mkdir data
echo ===== [%date% %time%] backtest_2.py ===== >> "data\line_alert_task.log"
python backtest_2.py >> "data\line_alert_task.log" 2>&1
if errorlevel 1 (
  echo backtest FAILED >> "data\line_alert_task.log"
  exit /b 1
)
echo ===== [%date% %time%] line_alert.py ===== >> "data\line_alert_task.log"
python line_alert.py >> "data\line_alert_task.log" 2>&1
