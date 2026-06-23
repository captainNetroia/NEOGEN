"""
NEOGEN - Télémétrie RGPD opt-in.

Consentement granulaire 3 niveaux :
  "erreurs"  : erreurs techniques uniquement
  "usage"    : erreurs + patterns d'utilisation
  "tout"     : erreurs + usage + skills contribués

Données anonymisées via anonymizer.py avant toute écriture.
Droit à l'effacement : effacer(user_id) supprime toutes les entrées liées au hash.
Rétention : données brutes 90 jours, pas d'envoi externe pour l'instant (local).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import threading
from typing import Literal

import anonymizer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONSENT_FILE = os.path.join(BASE_DIR, "data", "telemetrie_consent.json")
DATA_FILE    = os.path.join(BASE_DIR, "data", "telemetrie_data.jsonl")

RETENTION_JOURS = 90
_LOCK = threading.Lock()

NiveauConsent = Literal["aucun", "erreurs", "usage", "tout"]


# ── Consentement ─────────────────────────────────────────────────────────────

def _lire_consents() -> dict:
    if not os.path.exists(CONSENT_FILE):
        return {}
    try:
        with open(CONSENT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_consents(data: dict) -> None:
    os.makedirs(os.path.dirname(CONSENT_FILE), exist_ok=True)
    with open(CONSENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def get_consentement(user_id: str) -> NiveauConsent:
    return _lire_consents().get(_hash(user_id), {}).get("niveau", "aucun")


def set_consentement(user_id: str, niveau: NiveauConsent) -> None:
    with _LOCK:
        data = _lire_consents()
        data[_hash(user_id)] = {"niveau": niveau, "ts": time.time()}
        _ecrire_consents(data)


# ── Collecte ─────────────────────────────────────────────────────────────────

def enregistrer(
    user_id: str,
    type_: Literal["erreur", "usage", "skill"],
    payload: dict,
) -> bool:
    """
    Enregistre un événement télémétrique si le niveau de consentement le permet.
    Retourne True si enregistré.
    """
    niveau = get_consentement(user_id)
    autorise = (
        (type_ == "erreur" and niveau in ("erreurs", "usage", "tout")) or
        (type_ == "usage"  and niveau in ("usage", "tout")) or
        (type_ == "skill"  and niveau == "tout")
    )
    if not autorise:
        return False

    entree = {
        "uid_hash": _hash(user_id),
        "ts": time.time(),
        "type": type_,
        "data": anonymizer.nettoyer_dict(payload),
    }
    with _LOCK:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return True


# ── Droit à l'effacement RGPD ─────────────────────────────────────────────────

def effacer(user_id: str) -> dict:
    """
    Supprime TOUTES les données liées à l'utilisateur (consentement + données).
    Retourne {supprime_consent, supprime_lignes}.
    """
    h = _hash(user_id)
    supprime_consent = False
    supprime_lignes = 0

    with _LOCK:
        # Retirer du fichier de consentement
        consents = _lire_consents()
        if h in consents:
            del consents[h]
            _ecrire_consents(consents)
            supprime_consent = True

        # Filtrer les lignes de données
        if os.path.exists(DATA_FILE):
            lignes_gardees = []
            with open(DATA_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get("uid_hash") == h:
                            supprime_lignes += 1
                        else:
                            lignes_gardees.append(line)
                    except Exception:
                        lignes_gardees.append(line)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                f.writelines(lignes_gardees)

    return {"supprime_consent": supprime_consent, "supprime_lignes": supprime_lignes}


def purger_anciens() -> int:
    """Supprime les entrées de plus de RETENTION_JOURS jours."""
    if not os.path.exists(DATA_FILE):
        return 0
    limite = time.time() - (RETENTION_JOURS * 86400)
    gardees = []
    supprimees = 0
    with _LOCK:
        with open(DATA_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get("ts", 0) < limite:
                        supprimees += 1
                    else:
                        gardees.append(line)
                except Exception:
                    gardees.append(line)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.writelines(gardees)
    return supprimees


def stats_agregees() -> dict:
    """Stats anonymes agrégées pour le dashboard admin Jordan."""
    if not os.path.exists(DATA_FILE):
        return {"total": 0, "par_type": {}, "users_actifs": 0}
    par_type: dict[str, int] = {}
    users: set[str] = set()
    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                t = e.get("type", "inconnu")
                par_type[t] = par_type.get(t, 0) + 1
                users.add(e.get("uid_hash", ""))
            except Exception:
                pass
    return {"total": sum(par_type.values()), "par_type": par_type,
            "users_actifs": len(users)}


if __name__ == "__main__":
    import tempfile
    tmp = tempfile.mkdtemp()
    globals()["CONSENT_FILE"] = os.path.join(tmp, "c.json")
    globals()["DATA_FILE"]    = os.path.join(tmp, "d.jsonl")

    uid = "__test_tele__"
    assert get_consentement(uid) == "aucun"
    # Pas de consentement → pas d'enregistrement
    assert not enregistrer(uid, "erreur", {"msg": "fail"})
    set_consentement(uid, "erreurs")
    assert enregistrer(uid, "erreur", {"msg": "fail", "email": "x@y.com"})
    # Usage refusé au niveau "erreurs"
    assert not enregistrer(uid, "usage", {"action": "crea"})
    set_consentement(uid, "tout")
    assert enregistrer(uid, "skill", {"nom": "mon skill"})
    r = effacer(uid)
    assert r["supprime_consent"] and r["supprime_lignes"] == 2
    assert get_consentement(uid) == "aucun"
    print("telemetrie.py : tous les tests OK")
