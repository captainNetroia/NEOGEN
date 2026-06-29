@echo off
chcp 65001 >nul
title NEOGEN — Lancement

echo Vérification de Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker n'est pas lancé. Lance Docker Desktop puis relance ce script.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo Fichier .env créé. Tu peux ajouter ta clé IA ^(optionnel^) dans .env
    echo.
)

echo Démarrage de NEOGEN...
docker compose up -d --build

echo.
echo NEOGEN est prêt : http://localhost:8000
echo.
echo Commandes utiles :
echo   Voir les logs  : docker compose logs -f
echo   Arrêter        : docker compose down
echo   Mettre à jour  : Mettre-a-jour-NEOGEN.bat
echo.
start http://localhost:8000
pause
