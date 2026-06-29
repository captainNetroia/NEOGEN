#!/bin/bash
# NEOGEN — Mettre a jour sur Mac / Linux

set -e

echo "Mise a jour de NEOGEN..."

git pull origin main

echo "Reconstruction du conteneur..."
docker compose down
docker compose up -d --build

echo ""
echo "NEOGEN mis a jour et relance : http://localhost:8000"
