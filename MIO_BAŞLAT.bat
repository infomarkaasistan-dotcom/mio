@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MIO Executive OS
echo.
echo   ============================================
echo      MIO baslatiliyor...
echo      Tarayici birkac saniye icinde acilacak.
echo      Bu pencereyi KAPATMA (MIO burada calisir).
echo      Durdurmak icin: Ctrl-C
echo   ============================================
echo.

REM Once uv (onerilen; py3.12), olmazsa sistem python'u dene
where uv >nul 2>nul
if %errorlevel%==0 (
  uv run --python 3.12 python -m mio_core app --port 8080
) else (
  python -m mio_core app --port 8080
)

echo.
echo   MIO durdu. Bu pencereyi kapatabilirsin.
pause
