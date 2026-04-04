@echo off
schtasks /create /tn "StockMonitorDaily" /tr "C:\Users\User\stock-monitor\run_daily.bat" /sc daily /st 08:00 /f
echo Done.
pause
