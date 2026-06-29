from __future__ import annotations
import json as _json
import os as _os
import uuid as _uid
from datetime import datetime as _dt

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .deps import (
    _auth, _est_admin, _ajsonl, _rjsonl, _wjsonl,
    _hashpw, _verifypw, _user_by_email, _make_session,
    _USERS, _SESSIONS, _FEEDBACKS,
)

_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_USERS_DIR = _os.path.join(_BASE, "data", "users")


def _profil_path(user_id: str) -> str:
    d = _os.path.join(_USERS_DIR, user_id)
    _os.makedirs(d, exist_ok=True)
    return _os.path.join(d, "profil.json")


def _lire_profil(user_id: str) -> dict:
    p = _profil_path(user_id)
    if not _os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {}


def _ecrire_profil(user_id: str, data: dict) -> None:
    p = _profil_path(user_id)
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)

router = APIRouter()


@router.post("/auth/register")
def auth_register(data: dict):
    email = data.get("email", "").strip().lower()
    pw = data.get("password", "")
    name = data.get("name", "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")
    if len(pw) < 6:
        raise HTTPException(400, "Mot de passe trop court (6 caracteres minimum)")
    if _user_by_email(email):
        raise HTTPException(409, "Email deja utilise")
    uid = str(_uid.uuid4())
    user = {
        "id": uid, "email": email,
        "name": name or email.split("@")[0],
        "pw_hash": _hashpw(pw),
        "created_at": _dt.utcnow().isoformat(),
    }
    _ajsonl(_USERS, user)
    token = _make_session(uid)
    return {"token": token, "user": {"id": uid, "email": email, "name": user["name"]}}


@router.post("/auth/login")
def auth_login(data: dict):
    email = data.get("email", "").strip().lower()
    pw = data.get("password", "")
    user = _user_by_email(email)
    if not user or not _verifypw(pw, user.get("pw_hash", "")):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    token = _make_session(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@router.get("/auth/me")
def auth_me(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import quotas as _q
    import credits as _cred
    profil = _lire_profil(user["id"])
    return {
        "id": user["id"], "email": user["email"],
        "name": user["name"], "created_at": user.get("created_at"),
        "is_admin": _est_admin(user),
        "premium": bool(user.get("premium")),
        "palier": _q.palier(user),
        "solde_gen": _cred.solde(user["id"]),
        "profil_complet": bool(profil.get("complet")),
    }


@router.get("/compte/profil")
def compte_profil_get(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    p = _lire_profil(user["id"])
    return {"profil": p, "complet": bool(p.get("complet"))}


@router.post("/compte/profil")
def compte_profil_post(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    prenom = (data.get("prenom") or "").strip()
    if not prenom:
        raise HTTPException(400, "Prenom requis")
    profil = {
        "prenom": prenom,
        "projets": (data.get("projets") or "").strip(),
        "aime": (data.get("aime") or "").strip(),
        "naime_pas": (data.get("naime_pas") or "").strip(),
        "style_travail": (data.get("style_travail") or "").strip(),
        "complet": True,
        "updated_at": _dt.utcnow().isoformat(),
    }
    _ecrire_profil(user["id"], profil)
    return {"ok": True}


@router.post("/auth/logout")
def auth_logout(authorization: str = Header(None)):
    if not authorization:
        return {"ok": True}
    token = authorization.replace("Bearer ", "").strip()
    _wjsonl(_SESSIONS, [s for s in _rjsonl(_SESSIONS) if s.get("token") != token])
    return {"ok": True}


@router.get("/quotas/me")
def quotas_me(authorization: str = Header(None)):
    import quotas
    return quotas.etat(_auth(authorization))


class PremiumBody(BaseModel):
    email: str
    premium: bool = True


@router.post("/admin/premium")
def admin_premium(body: PremiumBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Reserve a l'administrateur")
    cible = _user_by_email(body.email.strip().lower())
    if not cible:
        raise HTTPException(404, "Utilisateur introuvable")
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == cible["id"]:
            u["premium"] = bool(body.premium)
    _wjsonl(_USERS, users)
    return {"ok": True, "email": body.email, "premium": bool(body.premium)}


@router.post("/feedback")
def post_feedback(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    msg = data.get("message", "").strip()
    if not msg:
        raise HTTPException(400, "Message vide")
    fb = {
        "id": str(_uid.uuid4()),
        "user_id": user["id"] if user else None,
        "user_email": user["email"] if user else data.get("email", "anonyme"),
        "user_name": user["name"] if user else data.get("name", "Anonyme"),
        "message": msg,
        "rating": data.get("rating"),
        "created_at": _dt.utcnow().isoformat(),
    }
    _ajsonl(_FEEDBACKS, fb)
    return {"ok": True, "id": fb["id"]}


@router.get("/admin/feedbacks")
def admin_feedbacks(authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Acces refuse")
    items = _rjsonl(_FEEDBACKS)
    return {"feedbacks": list(reversed(items)), "total": len(items)}
