@echo off
title Sea Siege Tower Defense
cd /d "%~dp0"

rem --- pick a Python that has pyngrok installed --------------------------------
set "PY=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=python"

rem --- optional: set your ngrok token here if the tunnel ever stops working ---
rem set "NGROK_AUTHTOKEN=put_your_token_here"

rem --- this launcher wants the public link, so ask for it explicitly -----------
rem --- (server.py never opens a tunnel unless USE_NGROK=1 or --ngrok is set) ---
set "USE_NGROK=1"

echo Starting Sea Siege Tower Defense...
echo Close this window (or press Ctrl+C) to stop the site.
echo.
"%PY%" server.py

echo.
echo Server stopped.
pause
