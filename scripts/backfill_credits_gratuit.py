"""Backfill ponctuel : credite 200 GEN aux comptes gratuits crees avant le fix
qui credite automatiquement le solde initial a l'inscription (auth_register).
Idempotent : ne touche que les comptes gratuits dont le solde est encore a 0.
Usage : python scripts/backfill_credits_gratuit.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import credits
from routes.deps import _rjsonl, _USERS


def main() -> None:
    users = _rjsonl(_USERS)
    touches = 0
    for u in users:
        palier = u.get("palier") or "gratuit"
        if palier != "gratuit":
            continue
        uid = u.get("id")
        if not uid or credits.solde(uid) > 0:
            continue
        credits.recharger_mensuel(uid, "gratuit")
        touches += 1
        print(f"  credite : {u.get('email')} -> 200 GEN")
    print(f"Backfill termine : {touches} compte(s) credite(s) sur {len(users)}.")


if __name__ == "__main__":
    main()
