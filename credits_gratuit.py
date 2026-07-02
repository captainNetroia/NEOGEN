"""
NEOGEN - Recredit mensuel automatique des comptes gratuits (200 GEN/mois).

Les comptes payants sont recredites a chaque cycle de facturation Stripe
(voir routes/premium.py, evenement invoice.paid). Les comptes gratuits n'ont
pas d'abonnement Stripe : ce module joue le meme role pour eux.

Idempotent par mois calendaire (cle "YYYY-MM") : un compte gratuit ne recoit
jamais plus d'un credit par mois, meme si le serveur redemarre plusieurs fois
dans le mois. Persistance : data/credits_gratuit_suivi.json.

Conception : Jordan VINCENT (NetroIA) + Claude. 2026-07-02.
"""
from __future__ import annotations

import json
import os
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUIVI_FILE = os.path.join(BASE_DIR, "data", "credits_gratuit_suivi.json")

_LOCK = threading.Lock()
_THREAD = None
INTERVALLE_S = 3600  # verifie toutes les heures : peu couteux, largement suffisant pour un cycle mensuel


def _lire() -> dict:
    if not os.path.exists(SUIVI_FILE):
        return {}
    try:
        with open(SUIVI_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire(d: dict) -> None:
    os.makedirs(os.path.dirname(SUIVI_FILE), exist_ok=True)
    with open(SUIVI_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def _mois_actuel() -> str:
    return time.strftime("%Y-%m")


def marquer_credite(uid: str, mois: str | None = None) -> None:
    """Marque un compte comme deja credite pour le mois calendaire donne (defaut : mois courant),
    SANS le crediter. Sert au seed initial (compte deja credite via inscription ou backfill)."""
    with _LOCK:
        suivi = _lire()
        suivi[uid] = mois or _mois_actuel()
        _ecrire(suivi)


def crediter_si_necessaire(uid: str) -> bool:
    """Credite 200 GEN si ce compte gratuit n'a pas encore ete credite ce mois-ci.
    Idempotent : appel multiple dans le meme mois = un seul credit. Retourne True si credite."""
    import credits
    with _LOCK:
        suivi = _lire()
        mois = _mois_actuel()
        if suivi.get(uid) == mois:
            return False
        credits.recharger_mensuel(uid, "gratuit")
        suivi[uid] = mois
        _ecrire(suivi)
        return True


def _cycle() -> None:
    import robustesse as rob
    from routes.deps import _rjsonl, _USERS
    touches = 0
    for u in _rjsonl(_USERS):
        palier = u.get("palier") or "gratuit"
        if palier != "gratuit":
            continue
        uid = u.get("id")
        if uid and crediter_si_necessaire(uid):
            touches += 1
    if touches:
        rob.journaliser(f"credit mensuel gratuit : {touches} compte(s) recredite(s)",
                        "info", source="credits_gratuit")


def _boucle() -> None:
    import robustesse as rob
    while True:
        with rob.garde("boucle credits gratuit", source="credits_gratuit"):
            _cycle()
        time.sleep(INTERVALLE_S)


def demarrer() -> None:
    """Demarre le thread de recredit mensuel (idempotent)."""
    global _THREAD
    if _THREAD is None or not _THREAD.is_alive():
        _THREAD = threading.Thread(target=_boucle, daemon=True)
        _THREAD.start()


if __name__ == "__main__":
    import tempfile
    tmp = tempfile.mkdtemp()
    globals()["SUIVI_FILE"] = os.path.join(tmp, "suivi.json")

    import credits as _cred
    _cred_bak_solde, _cred_bak_charge = _cred.SOLDES_FILE, _cred.TXNS_FILE
    _cred.SOLDES_FILE = os.path.join(tmp, "s.json")
    _cred.TXNS_FILE = os.path.join(tmp, "t.jsonl")

    print("=" * 60)
    print("NEOGEN - CREDITS GRATUIT MENSUEL : auto-verification")
    print("=" * 60)
    uid = "__test_gratuit__"
    assert _cred.solde(uid) == 0
    assert crediter_si_necessaire(uid) is True
    assert _cred.solde(uid) == 200
    # Idempotence : meme mois -> pas de second credit
    assert crediter_si_necessaire(uid) is False
    assert _cred.solde(uid) == 200
    # Mois different -> recredite
    marquer_credite(uid, mois="2000-01")
    assert crediter_si_necessaire(uid) is True
    assert _cred.solde(uid) == 400
    print("  crediter_si_necessaire (idempotent par mois) : OK")

    _cred.SOLDES_FILE, _cred.TXNS_FILE = _cred_bak_solde, _cred_bak_charge
    print("=" * 60)
