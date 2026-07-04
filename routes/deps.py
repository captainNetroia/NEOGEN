"""
NEOGEN - Dépendances partagées entre les routers FastAPI.
Helpers d'auth, JSONL, mots de passe, LLM, gestion utilisateurs.
"""
from __future__ import annotations

import hashlib as _hl
import hmac as _hmac
import os as _os
import secrets as _sec
import uuid as _uid
from datetime import datetime as _dt, timedelta as _td

from fastapi import HTTPException

import robustesse as _rob

# Chemins — __file__ est dans routes/, donc remonter d'un niveau
_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_DATA = _os.path.join(_BASE, "data")
_USERS = _os.path.join(_DATA, "users.jsonl")
_SESSIONS = _os.path.join(_DATA, "sessions.jsonl")
_FEEDBACKS = _os.path.join(_DATA, "feedbacks.jsonl")
_CONTACTS_ENTREPRISE = _os.path.join(_DATA, "contacts_entreprise.jsonl")
_ADMIN_EMAIL = _os.environ.get("NEOGEN_ADMIN_EMAIL", "").strip().lower()


# ── JSONL (délèguent à robustesse — dette F004) ────────────────────────────────

def _rjsonl(path: str) -> list:
    return _rob.lire_jsonl(path)

def _ajsonl(path: str, obj: dict) -> None:
    _rob.ajout_jsonl(path, obj)

def _wjsonl(path: str, items: list) -> None:
    _rob.ecrire_jsonl(path, items)


# ── Auth ────────────────────────────────────────────────────────────────────────

def _est_admin(user) -> bool:
    if not _ADMIN_EMAIL or not user:
        return False
    return (user.get("email") or "").strip().lower() == _ADMIN_EMAIL


def _hashpw(pw: str) -> str:
    salt = _sec.token_hex(16)
    k = _hl.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000)
    return f"pbkdf2:{salt}:{k.hex()}"


def _verifypw(pw: str, h: str) -> bool:
    try:
        _, salt, key = h.split(":")
        k = _hl.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000)
        return _sec.compare_digest(k.hex(), key)
    except Exception:
        return False


def _user_by_email(email: str) -> dict | None:
    for u in _rjsonl(_USERS):
        if u.get("email") == email:
            return u
    return None


def _user_by_token(token: str) -> dict | None:
    now = _dt.utcnow().isoformat()
    for s in _rjsonl(_SESSIONS):
        if _hmac.compare_digest(s.get("token", ""), token) and s.get("expires_at", "") > now:
            uid = s.get("user_id")
            for u in _rjsonl(_USERS):
                if u.get("id") == uid:
                    return u
    return None


def _make_session(user_id: str) -> str:
    token = _sec.token_urlsafe(32)
    exp = (_dt.utcnow() + _td(days=30)).isoformat()
    _ajsonl(_SESSIONS, {"token": token, "user_id": user_id,
                        "expires_at": exp, "created_at": _dt.utcnow().isoformat()})
    return token


def _auth(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    return _user_by_token(authorization.replace("Bearer ", "").strip())


# ── Credentials ────────────────────────────────────────────────────────────────

def _load_cred(filename: str, key: str) -> str:
    from credentials_loader import lire_cred
    return lire_cred(filename, key)


# ── Gestion premium / utilisateurs ────────────────────────────────────────────

def _set_premium(user_id: str, premium: bool, palier: str = "essential") -> bool:
    users = _rjsonl(_USERS)
    trouve = False
    for u in users:
        if u.get("id") == user_id:
            u["premium"] = bool(premium)
            u["palier"] = palier if premium else "gratuit"
            trouve = True
    if trouve:
        _wjsonl(_USERS, users)
    return trouve


def _marquer_essai_utilise(user_id: str) -> None:
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == user_id:
            u["essai_utilise"] = True
    _wjsonl(_USERS, users)


def _lier_stripe_customer(user_id: str, customer_id: str) -> None:
    if not customer_id:
        return
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == user_id:
            u["stripe_customer_id"] = customer_id
    _wjsonl(_USERS, users)


def _revoquer_premium_par_customer(customer_id: str) -> bool:
    if not customer_id:
        return False
    users = _rjsonl(_USERS)
    trouve = False
    for u in users:
        if u.get("stripe_customer_id") == customer_id:
            u["premium"] = False
            u["palier"] = "gratuit"
            trouve = True
    if trouve:
        _wjsonl(_USERS, users)
    return trouve


def _palier_depuis_price_id(price_id: str) -> str:
    mapping = {
        _load_cred("stripe.env", "STRIPE_PRICE_ESSENTIAL_MENSUEL"): "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_ESSENTIAL_ANNUEL"):  "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_PRO_MENSUEL"):       "pro",
        _load_cred("stripe.env", "STRIPE_PRICE_PRO_ANNUEL"):        "pro",
        _load_cred("stripe.env", "STRIPE_PRICE_POWER_MENSUEL"):     "power",
        _load_cred("stripe.env", "STRIPE_PRICE_POWER_ANNUEL"):      "power",
        _load_cred("stripe.env", "STRIPE_PRICE_ENTERPRISE_MENSUEL"):"enterprise",
        _load_cred("stripe.env", "STRIPE_PRICE_ENTERPRISE_ANNUEL"): "enterprise",
        _load_cred("stripe.env", "STRIPE_PRICE_ID_MENSUEL"): "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_ID_ANNUEL"):  "essential",
    }
    return mapping.get(price_id, "essential")


# ── LLM ────────────────────────────────────────────────────────────────────────

def _exiger_byok(ctx) -> None:
    import os
    if os.environ.get("NEOGEN_ALLOW_DEFAULT_KEY", "").strip().lower() in ("1", "true", "yes", "on"):
        return
    if ctx is not None and (ctx.api_key or (ctx.provider or "").lower() == "local"):
        return
    raise HTTPException(status_code=402, detail=(
        "Connecte ton modele IA dans Integrations (ta cle API, ou Ollama en local) pour "
        "utiliser les agents et la creation. NEOGEN n'utilise jamais une cle par defaut."
    ))


def _verifier_quota(authorization: str | None, type_: str):
    import quotas
    user = _auth(authorization)
    if user is None:
        return None, False
    v = quotas.verifier(user, type_)
    if not v["autorise"]:
        raise HTTPException(status_code=402, detail=v["raison"])
    return user, quotas.est_premium(user)


def _llm_client(provider=None, model=None, key=None, base=None, tier="fort"):
    from gateway import client as _gw, contexte_depuis_headers
    ctx = contexte_depuis_headers(provider, model, key, base)
    _exiger_byok(ctx)
    return _gw(ctx, tier=tier)
