"""Seed ponctuel : marque tous les comptes gratuits existants comme deja credites
pour le mois calendaire courant, AVANT l'activation du cron mensuel (credits_gratuit.py).

Sans ce seed, le premier cycle du cron recrediterait immediatement tous les comptes
gratuits deja credites ce mois-ci via l'inscription ou le backfill (double credit).

Idempotent : ne fait qu'ecrire l'entree de suivi, ne credite jamais de GEN.
Usage : python scripts/seed_credits_gratuit_suivi.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import credits_gratuit
from routes.deps import _rjsonl, _USERS


def main() -> None:
    users = _rjsonl(_USERS)
    touches = 0
    for u in users:
        palier = u.get("palier") or "gratuit"
        if palier != "gratuit":
            continue
        uid = u.get("id")
        if not uid:
            continue
        credits_gratuit.marquer_credite(uid)
        touches += 1
        print(f"  marque (deja credite ce mois-ci) : {u.get('email')}")
    print(f"Seed termine : {touches} compte(s) gratuit(s) marque(s) pour {credits_gratuit._mois_actuel()}.")


if __name__ == "__main__":
    main()
