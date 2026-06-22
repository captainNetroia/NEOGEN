@echo off
REM ============================================================
REM   NEOGEN - Lanceur de l'agent local (double-clic)
REM   Lance l'agent qui pilote souris/clavier/navigateur avec
REM   une icone dans la barre systeme. Installe les dependances
REM   manquantes au premier lancement.
REM ============================================================
title NEOGEN - Agent local
cd /d "%~dp0"

echo Verification des dependances...
python -m pip install --quiet --disable-pip-version-check pyautogui pynput requests pystray pillow

echo Lancement de l'agent (icone barre systeme)...
REM pythonw = pas de fenetre console, l'agent vit dans la barre systeme
start "" pythonw rpa_agent.py

echo.
echo Agent lance ! Cherche l'icone dans la barre systeme (en bas a droite).
echo Clic droit sur l'icone pour le menu (Statut / Ouvrir NEOGEN / Quitter).
echo.
timeout /t 4 >nul
