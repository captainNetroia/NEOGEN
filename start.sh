#!/bin/bash
# NEOGEN — Lancer sur Mac / Linux

set -e

# Verifier Docker
if ! command -v docker &> /dev/null; then
    echo "Docker n'est pas installe."
    echo "Telecharge Docker Desktop : https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "Docker n'est pas lance. Demarre Docker Desktop puis relance ce script."
    exit 1
fi

# Creer .env si absent
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env cree depuis .env.example"
    echo "Tu peux ajouter ta cle IA (optionnel) : edite .env -> ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
fi

echo "Demarrage de NEOGEN..."
docker compose up -d --build

echo ""
echo "NEOGEN est pret : http://localhost:8000"
echo ""
echo "Commandes utiles :"
echo "  Voir les logs  : docker compose logs -f"
echo "  Arreter        : docker compose down"
echo "  Mettre a jour  : ./update.sh"
