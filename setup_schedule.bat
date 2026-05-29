@echo off
schtasks /create /tn "StockMonitorDaily" /tr "C:\Users\User\Documents\github-projects-commandcenter\90_stock-monitor\run_daily.bat" /sc daily /st 08:00 /f
echo Done.
pause
