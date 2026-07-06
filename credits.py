"""
NEOGEN - Économie Genyte (GEN).

Monnaie virtuelle interne. Chaque utilisateur a un solde.
Les transactions sont horodatées et persistées dans data/credits.jsonl.
Types : earn (gain), spend (dépense), purchase (achat Stripe), gift (cadeau).
Palier premium : coûts réduits selon COUT_PALIER.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Literal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOLDES_FILE = os.path.join(BASE_DIR, "data", "credits_soldes.json")
TXNS_FILE   = os.path.join(BASE_DIR, "data", "credits_transactions.jsonl")

_LOCK = threading.Lock()

# Coût des fonctions par palier (GEN).
# None = interdit sur ce palier.
COUTS: dict[str, dict[str, int | None]] = {
    "conversation":         {"gratuit": 15,   "essential": 15, "pro": 15, "power": 15, "enterprise": 0},
    "mode_juge":            {"gratuit": None, "essential": 60, "pro": 60, "power": 30, "enterprise": 0},
    "deploiement":          {"gratuit": None, "essential": 100,"pro": 100,"power": 50, "enterprise": 0},
    "delegation_complete":  {"gratuit": None, "essential": 15, "pro": 10, "power": 5,  "enterprise": 0},
    "apprentissage_continu":{"gratuit": None, "essential": 10, "pro": 5,  "power": 0,  "enterprise": 0},
    "donner_vie":           {"gratuit": None, "essential": 50, "pro": 50, "power": 25, "enterprise": 0},
    "creation_app_forge":   {"gratuit": None, "essential": 100,"pro": 100,"power": 50, "enterprise": 0},
    "deploiement_gere":     {"gratuit": None, "essential": 100,"pro": 100,"power": 50, "enterprise": 0},
    "skill_communautaire":  {"gratuit": 2,    "essential": 2,  "pro": 1,  "power": 0,  "enterprise": 0},
    "flash_24h":            {"gratuit": 30,   "essential": 20, "pro": 15, "power": 10, "enterprise": 0},
    "flash_7j":             {"gratuit": 150,  "essential": 100,"pro": 75, "power": 50, "enterprise": 0},
}

# GEN offerts mensuellement selon le palier (rechargé au 1er du mois via cron ou à la connexion).
GEN_MENSUEL: dict[str, int] = {
    "gratuit": 200,
    "essential": 1500,
    "pro": 4500,
    "power": 12000,
    "enterprise": 99999,  # illimité en pratique
}


# ── I/O ─────────────────────────────────────────────────────────────────────

def _lire_soldes() -> dict:
    if not os.path.exists(SOLDES_FILE):
        return {}
    try:
        with open(SOLDES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_soldes(data: dict) -> None:
    os.makedirs(os.path.dirname(SOLDES_FILE), exist_ok=True)
    with open(SOLDES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _append_txn(txn: dict) -> None:
    os.makedirs(os.path.dirname(TXNS_FILE), exist_ok=True)
    with open(TXNS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(txn, ensure_ascii=False) + "\n")


# ── API publique ─────────────────────────────────────────────────────────────

def solde(user_id: str) -> int:
    return _lire_soldes().get(user_id, 0)


def crediter(
    user_id: str,
    montant: int,
    type_: Literal["earn", "purchase", "gift", "monthly"],
    description: str = "",
    metadata: dict | None = None,
) -> int:
    """Ajoute des GEN. Retourne le nouveau solde."""
    with _LOCK:
        data = _lire_soldes()
        data[user_id] = data.get(user_id, 0) + montant
        _ecrire_soldes(data)
        _append_txn({
            "user_id": user_id, "ts": time.time(), "type": type_,
            "montant": montant, "description": description,
            "metadata": metadata or {},
        })
        return data[user_id]


def debiter(
    user_id: str,
    montant: int,
    fonction: str,
    description: str = "",
) -> dict:
    """
    Débite des GEN. Retourne {ok, solde_avant, solde_apres, manque}.
    Si solde insuffisant → ok=False, aucune modification.
    """
    if not isinstance(montant, int) or montant < 0:
        # Garde-fou critique : un montant negatif ici inverserait le sens de l'operation
        # (avant - montant_negatif = credit deguise). Fail-closed : jamais de debit avec un
        # montant negatif, peu importe l'appelant. montant == 0 reste autorise (action
        # gratuite sur un palier premium, ex: cout 0 pour "mode_juge" en enterprise) : c'est
        # un no-op legitime, pas une tentative d'exploit.
        return {"ok": False, "solde_avant": solde(user_id), "solde_apres": solde(user_id),
                "manque": 0, "erreur": "montant invalide"}
    with _LOCK:
        data = _lire_soldes()
        avant = data.get(user_id, 0)
        if avant < montant:
            return {"ok": False, "solde_avant": avant, "solde_apres": avant,
                    "manque": montant - avant}
        data[user_id] = avant - montant
        _ecrire_soldes(data)
        if montant > 0:
            # Pas de transaction journalisee pour un debit a 0 GEN (aucun mouvement reel,
            # eviter de polluer l'historique avec des lignes "spend -0").
            _append_txn({
                "user_id": user_id, "ts": time.time(), "type": "spend",
                "montant": -montant, "description": description,
                "metadata": {"fonction": fonction},
            })
        return {"ok": True, "solde_avant": avant, "solde_apres": data[user_id], "manque": 0}


def cout(fonction: str, palier: str) -> int | None:
    """Coût GEN d'une fonction pour un palier donné. None = interdit."""
    return COUTS.get(fonction, {}).get(palier, 0)


def debiter_conversation(user: dict | None) -> dict:
    """Decompte une session de conversation (1 par ouverture, jamais par message).
    Priorite au quota mensuel offert (conversations_offertes, essential=20/pro=60/power=160/
    enterprise=illimite) ; une fois epuise, retombe sur le debit GEN classique (15 GEN,
    tous paliers connectes y compris gratuit). Jamais applique aux visiteurs anonymes BYOK
    (aucun user_id a suivre) - reste gratuit, coherent avec l'usage BYOK actuel.
    Retourne {ok, via: 'offerte'|'gen'|'aucun', ...} - ne bloque jamais la conversation
    elle-meme (best-effort, l'agent repond meme si le debit echoue silencieusement)."""
    import quotas as _quotas
    if not user or not user.get("id"):
        return {"ok": True, "via": "anonyme"}
    uid = user["id"]
    p = _quotas.palier(user)
    v = _quotas.verifier(user, "conversations_offertes")
    if v["autorise"]:
        # gratuit (limite=0) -> reste=0 -> autorise=False -> tombe directement sur le GEN.
        _quotas.incrementer(uid, "conversations_offertes")
        return {"ok": True, "via": "offerte", "reste": (v["reste"] - 1) if v["reste"] is not None else None}
    montant = cout("conversation", p)
    if not montant:
        return {"ok": True, "via": "gen", "solde": solde(uid)}
    r = debiter(uid, montant, "conversation", "Conversation avec un agent")
    return {"ok": r["ok"], "via": "gen", "solde_apres": r.get("solde_apres"), "manque": r.get("manque", 0)}


def historique(user_id: str, limite: int = 50) -> list[dict]:
    """Dernières transactions de l'utilisateur, les plus récentes en premier."""
    txns = []
    if not os.path.exists(TXNS_FILE):
        return []
    with open(TXNS_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line)
                if t.get("user_id") == user_id:
                    txns.append(t)
            except Exception:
                pass
    return sorted(txns, key=lambda x: x.get("ts", 0), reverse=True)[:limite]


def recharger_mensuel(user_id: str, palier: str, cycle_id: str = "") -> int:
    """Crédit mensuel automatique selon le palier. À appeler au renouvellement d'abonnement.

    cycle_id : identifiant unique du cycle facturé (ex: id de session Stripe ou d'invoice).
    Sans lui, un meme cycle confirme par 2 canaux differents (front premium_confirmer +
    webhook checkout.session.completed, ou webhook double-envoye par Stripe) recreditait
    2 fois le meme mois - idempotence deja appliquee au pack GEN ponctuel, etendue ici.
    Si cycle_id est vide (retrocompat appelant sans cycle), aucune dedup n'est possible."""
    montant = GEN_MENSUEL.get(palier, 0)
    if montant <= 0:
        return solde(user_id)
    if cycle_id:
        deja = any((t.get("metadata") or {}).get("cycle_id") == cycle_id
                   for t in historique(user_id, limite=200))
        if deja:
            return solde(user_id)
    return crediter(user_id, montant, "monthly", f"Crédit mensuel palier {palier}",
                     metadata={"cycle_id": cycle_id} if cycle_id else None)


if __name__ == "__main__":
    import tempfile
    # Monkey-patch pour test isolé
    SOLDES_FILE_BAK = SOLDES_FILE
    TXNS_FILE_BAK   = TXNS_FILE
    tmp = tempfile.mkdtemp()
    globals()["SOLDES_FILE"] = os.path.join(tmp, "s.json")
    globals()["TXNS_FILE"]   = os.path.join(tmp, "t.jsonl")

    uid = "__test_credits__"
    assert solde(uid) == 0
    crediter(uid, 100, "earn", "test")
    assert solde(uid) == 100
    r = debiter(uid, 30, "mode_juge")
    assert r["ok"] and r["solde_apres"] == 70
    r2 = debiter(uid, 200, "mode_juge")
    assert not r2["ok"] and r2["manque"] == 130
    assert solde(uid) == 70
    h = historique(uid)
    assert len(h) == 2
    assert cout("mode_juge", "gratuit") is None
    assert cout("mode_juge", "power") == 30
    assert cout("delegation_complete", "gratuit") is None
    # montant == 0 : no-op legitime (ex. fonction gratuite sur un palier premium), pas un refus
    r3 = debiter(uid, 0, "mode_juge")
    assert r3["ok"] and r3["solde_apres"] == 70
    # montant negatif : refuse fail-closed (vuln critique corrigee 2026-07-04 : un montant
    # negatif inversait le sens de l'operation et permettait de se crediter au lieu de se
    # debiter). Le solde ne doit JAMAIS bouger.
    r4 = debiter(uid, -500, "mode_juge")
    assert not r4["ok"] and solde(uid) == 70

    # recharger_mensuel : idempotence par cycle_id (corrige le double-credit
    # premium_confirmer + webhook checkout.session.completed sur le meme paiement).
    s_avant = solde(uid)
    recharger_mensuel(uid, "essential", cycle_id="cs_test_123")
    s_apres_1 = solde(uid)
    assert s_apres_1 == s_avant + GEN_MENSUEL["essential"]
    recharger_mensuel(uid, "essential", cycle_id="cs_test_123")  # meme cycle : no-op
    assert solde(uid) == s_apres_1
    recharger_mensuel(uid, "essential", cycle_id="cs_test_456")  # cycle different : credite
    assert solde(uid) == s_apres_1 + GEN_MENSUEL["essential"]

    # debiter_conversation : quota offert d'abord, puis GEN une fois epuise.
    import quotas as _q
    with _q._LOCK:
        d = _q._lire(); d.pop(uid, None); _q._ecrire(d)
    u_ess = {"id": uid, "palier": "essential"}
    r = debiter_conversation(u_ess)
    assert r["ok"] and r["via"] == "offerte" and r["reste"] == 19
    for _ in range(19):
        debiter_conversation(u_ess)
    s_avant_gen = solde(uid)
    r_epuise = debiter_conversation(u_ess)  # 21e conversation : quota offert epuise -> GEN
    assert r_epuise["ok"] and r_epuise["via"] == "gen"
    assert solde(uid) == s_avant_gen - cout("conversation", "essential")
    # anonyme (pas de user) : jamais debite, toujours gratuit (BYOK)
    r_anon = debiter_conversation(None)
    assert r_anon["ok"] and r_anon["via"] == "anonyme"
    with _q._LOCK:
        d = _q._lire(); d.pop(uid, None); _q._ecrire(d)

    globals()["SOLDES_FILE"] = SOLDES_FILE_BAK
    globals()["TXNS_FILE"]   = TXNS_FILE_BAK
    print("credits.py : tous les tests OK")
