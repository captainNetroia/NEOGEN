from __future__ import annotations
import uuid as _uid
from datetime import datetime as _dt

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .deps import (
    _auth, _est_admin, _ajsonl, _rjsonl, _wjsonl,
    _hashpw, _verifypw, _user_by_email, _make_session,
    _USERS, _SESSIONS, _FEEDBACKS,
)

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
    return {
        "id": user["id"], "email": user["email"],
        "name": user["name"], "created_at": user.get("created_at"),
        "is_admin": _est_admin(user),
        "premium": bool(user.get("premium")),
        "palier": _q.palier(user),
        "solde_gen": _cred.solde(user["id"]),
    }


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
