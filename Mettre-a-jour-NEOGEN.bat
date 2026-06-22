@echo off
REM ============================================================
REM   NEOGEN - Mise a jour (double-clic)
REM   Recupere la derniere version depuis GitHub et reconstruit
REM   le conteneur. Equivalent de "hermes update".
REM ============================================================
title NEOGEN - Mise a jour
cd /d "%~dp0"

echo.
echo === NEOGEN : recuperation de la derniere version ===
git pull
if errorlevel 1 (
  echo.
  echo [!] git pull a echoue. Verifie ta connexion ou tes modifications locales.
  pause
  exit /b 1
)

echo.
echo === Reconstruction du conteneur ===
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo [!] La reconstruction a echoue. Verifie que Docker tourne.
  pause
  exit /b 1
)

echo.
echo === NEOGEN est a jour et relance ! ===
echo Ouvre http://localhost:8000
timeout /t 5 >nul
