@echo off
cd /d C:\Users\LENOVO\Desktop\SENSEI

echo [System] Cleaning up port 8080...
:: Use netstat to find the PID of the process using port 8080 and kill it
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080') do (
    echo [System] Killing process %%a...
    taskkill /F /PID %%a /T
)

echo [System] Ensuring all zombie python processes are gone...
taskkill /F /IM python.exe /T >nul 2>&1

echo [System] Starting SENSEI Server on port 8080...
python -m uvicorn app:app --port 8080 --reload
pause