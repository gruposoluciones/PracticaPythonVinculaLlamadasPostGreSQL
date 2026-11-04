@echo off
title Vincula - Consulta local de llamadas
cd /d "%~dp0"
echo Iniciando Vincula...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1"
echo.
echo El servidor se detuvo.
pause
