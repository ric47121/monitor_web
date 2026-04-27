@echo off
title Lanzador Monitor Web Pro
cd /d "%~dp0"
echo Iniciando Monitor de Sitios Web Pro...
start "" pythonw monitor.py
exit