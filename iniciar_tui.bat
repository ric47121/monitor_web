@echo off
title Monitor Web Pro - Consola TUI
cd /d "%~dp0"
:: Se recomienda usar python normal para TUI (no pythonw) para ver la salida
python monitor_tui.py
pause
