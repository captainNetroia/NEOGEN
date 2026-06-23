"""
NEOGEN - Boosts temporaires (Flash).

Flash 24h / Flash 7j : usage illimité pendant la durée.
Activé par dépense de GEN ou achat Stripe direct.
Persisté dans data/boosts_actifs.json.
"""
from __future__ import annotations

import json
import os
import time
import threading

import credits as _credits

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOSTS_FILE = os.path.join(BASE_DIR, "data", "boosts_actifs.json")

_LOCK = threading.Lock()

TYPES_BOOST: dict[str, dict] = {
    "flash_24h": {"duree": 86400,        "label": "Flash 24h — usage illimité"},
    "flash_7j":  {"duree": 86400 * 7,    "label": "Flash 7j — usage illimité"},
}


def _lire() -> dict:
    if not os.path.exists(BOOSTS_FILE):
        return {}
    try:
        with open(BOOSTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire(data: dict) -> None:
    os.makedirs(os.path.dirname(BOOSTS_FILE), exist_ok=True)
    with open(BOOSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def activer(user_id: str, type_boost: str, palier: str = "gratuit",
            gratuit: bool = False) -> dict:
    """
    Active un boost en débitant les GEN si gratuit=False.
    Retourne {ok, expiration, message, raison_refus}.
    """
    b = TYPES_BOOST.get(type_boost)
    if not b:
        return {"ok": False, "expiration": 0, "message": "",
                "raison_refus": f"Type de boost inconnu : {type_boost}"}

    if not gratuit:
        cout_gen = _credits.cout(type_boost, palier)
        if cout_gen is None:
            return {"ok": False, "expiration": 0, "message": "",
                    "raison_refus": f"Boost '{type_boost}' non disponible sur le palier {palier}."}
        if cout_gen > 0:
            result = _credits.debiter(user_id, cout_gen, type_boost, b["label"])
            if not result["ok"]:
                return {"ok": False, "expiration": 0, "message": "",
                        "raison_refus": f"Solde GEN insuffisant ({result['manque']} GEN manquants)."}

    with _LOCK:
        data = _lire()
        u = data.setdefault(user_id, {})
        # Prolonge si boost déjà actif
        maintenant = time.time()
        base = max(u.get(type_boost, {}).get("expiration", maintenant), maintenant)
        expiration = base + b["duree"]
        u[type_boost] = {"expiration": expiration, "active_le": maintenant}
        _ecrire(data)

    return {"ok": True, "expiration": expiration,
            "message": f"{b['label']} activé jusqu'au {_fmt(expiration)}",
            "raison_refus": ""}


def est_actif(user_id: str, type_boost: str) -> bool:
    """Retourne True si le boost est actif et non expiré."""
    data = _lire()
    b = data.get(user_id, {}).get(type_boost, {})
    return b.get("expiration", 0) > time.time()


def boosts_actifs(user_id: str) -> list[dict]:
    """Liste des boosts actifs (non expirés) avec temps restant."""
    data = _lire()
    maintenant = time.time()
    result = []
    for type_boost, info in data.get(user_id, {}).items():
        exp = info.get("expiration", 0)
        if exp > maintenant:
            result.append({
                "type": type_boost,
                "label": TYPES_BOOST.get(type_boost, {}).get("label", type_boost),
                "expiration": exp,
                "restant_s": int(exp - maintenant),
            })
    return result


def purger_expires() -> int:
    """Supprime les entrées expirées. Retourne le nombre supprimé."""
    with _LOCK:
        data = _lire()
        maintenant = time.time()
        n = 0
        for uid in list(data.keys()):
            for tb in list(data[uid].keys()):
                if data[uid][tb].get("expiration", 0) <= maintenant:
                    del data[uid][tb]
                    n += 1
            if not data[uid]:
                del data[uid]
        _ecrire(data)
    return n


def _fmt(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


if __name__ == "__main__":
    import tempfile, types, sys
    tmp = tempfile.mkdtemp()
    globals()["BOOSTS_FILE"] = os.path.join(tmp, "b.json")
    fake = types.SimpleNamespace(
        cout=lambda f, p: 30,
        debiter=lambda *a, **k: {"ok": True, "manque": 0},
    )
    sys.modules["credits"] = fake
    globals()["_credits"] = fake

    uid = "__test_boost__"
    r = activer(uid, "flash_24h", "gratuit")
    assert r["ok"], r
    assert est_actif(uid, "flash_24h")
    assert not est_actif(uid, "flash_7j")
    ba = boosts_actifs(uid)
    assert len(ba) == 1 and ba[0]["type"] == "flash_24h"
    print("boosts.py : tous les tests OK")
