"""
NEOGEN - Système de récompenses Genyte.

Déclencheurs événements → gain GEN automatique.
Anti-abus : délais minimum entre gains du même type par utilisateur.
Persisté dans data/recompenses_log.json.
"""
from __future__ import annotations

import json
import os
import time
import threading

import credits as _credits

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "data", "recompenses_log.json")

_LOCK = threading.Lock()

# Définition des récompenses : montant GEN + cooldown en secondes (0 = une seule fois).
RECOMPENSES: dict[str, dict] = {
    "premiere_creation":   {"gen": 20,  "cooldown": 0,          "desc": "Première création réussie"},
    "premier_skill":       {"gen": 10,  "cooldown": 0,          "desc": "Premier skill créé"},
    "streak_7j":           {"gen": 15,  "cooldown": 86400 * 7,  "desc": "7 jours d'activité consécutifs"},
    "skill_valide":        {"gen": 5,   "cooldown": 3600,        "desc": "Skill validé par la communauté"},
    "parrainage":          {"gen": 50,  "cooldown": 0,           "desc": "Parrainage : ami inscrit"},
    "telemetrie_mensuelle":{"gen": 5,   "cooldown": 86400 * 28,  "desc": "Participation télémétrie (mensuel)"},
    "cadeau_tirage":       {"gen": 0,   "cooldown": 0,           "desc": "Cadeau tirage hebdomadaire"},
}


def _lire_log() -> dict:
    if not os.path.exists(LOG_FILE):
        return {}
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_log(data: dict) -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def declencher(user_id: str, evenement: str, override_gen: int | None = None) -> dict:
    """
    Déclenche une récompense si le cooldown est respecté.
    Retourne {ok, gen_gagnes, message, raison_refus}.
    override_gen : pour cadeau_tirage ou parrainage côté parrain/filleul.
    """
    r = RECOMPENSES.get(evenement)
    if not r:
        return {"ok": False, "gen_gagnes": 0, "message": "", "raison_refus": f"Événement inconnu : {evenement}"}

    with _LOCK:
        log = _lire_log()
        u = log.setdefault(user_id, {})
        dernier = u.get(evenement, {}).get("ts", 0)
        nb      = u.get(evenement, {}).get("nb", 0)
        cooldown = r["cooldown"]

        # Une seule fois (cooldown=0 + déjà déclenché)
        if cooldown == 0 and nb > 0:
            return {"ok": False, "gen_gagnes": 0, "message": "",
                    "raison_refus": f"Récompense '{evenement}' déjà obtenue."}

        # Cooldown actif
        if cooldown > 0 and (time.time() - dernier) < cooldown:
            restant = int(cooldown - (time.time() - dernier))
            return {"ok": False, "gen_gagnes": 0, "message": "",
                    "raison_refus": f"Cooldown actif ({restant}s restantes)."}

        gen = override_gen if override_gen is not None else r["gen"]
        u[evenement] = {"ts": time.time(), "nb": nb + 1}
        _ecrire_log(log)

    if gen > 0:
        _credits.crediter(user_id, gen, "earn", r["desc"])

    msg = f"+{gen} GEN — {r['desc']}" if gen > 0 else r["desc"]
    return {"ok": True, "gen_gagnes": gen, "message": msg, "raison_refus": ""}


def parrainage(parrain_id: str, filleul_id: str) -> dict:
    """Récompense les deux côtés d'un parrainage."""
    r1 = declencher(parrain_id, "parrainage", override_gen=50)
    # Filleul reçoit aussi 50 GEN pour s'être inscrit via parrainage.
    r2 = declencher(filleul_id, "parrainage", override_gen=50)
    return {"parrain": r1, "filleul": r2}


def historique_recompenses(user_id: str) -> dict:
    """Retourne le log des récompenses de l'utilisateur."""
    return _lire_log().get(user_id, {})


if __name__ == "__main__":
    import tempfile
    tmp = tempfile.mkdtemp()
    globals()["LOG_FILE"] = os.path.join(tmp, "r.json")
    # Monkey-patch credits pour test isolé
    import types
    fake_credits = types.SimpleNamespace(crediter=lambda *a, **k: None)
    import sys
    sys.modules["credits"] = fake_credits
    globals()["_credits"] = fake_credits

    uid = "__test_reco__"
    r = declencher(uid, "premiere_creation")
    assert r["ok"] and r["gen_gagnes"] == 20, r
    r2 = declencher(uid, "premiere_creation")
    assert not r2["ok"], "one-shot devrait refuser"
    r3 = declencher(uid, "evenement_inexistant")
    assert not r3["ok"]
    print("recompenses.py : tous les tests OK")
