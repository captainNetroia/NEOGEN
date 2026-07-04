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
    _USERS, _SESSIONS, _FEEDBACKS, _CONTACTS_ENTREPRISE,
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
    # Anti-squat : sur l'instance PUBLIQUE, un email owner/admin ne peut pas etre pris par un
    # inconnu (sinon il heriterait du palier owner). Sur l'instance PERSO (owner_unlimited), le
    # proprietaire cree librement son compte owner sur SA machine.
    import quotas as _q
    if not _q._owner_unlimited():
        _reserves = {_os.environ.get("NEOGEN_OWNER_EMAIL", "").strip().lower(),
                     _os.environ.get("NEOGEN_ADMIN_EMAIL", "").strip().lower()} - {""}
        if email in _reserves:
            raise HTTPException(403, "Cet email est reserve. Contacte l'administrateur.")
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
    # Credit GEN initial du palier gratuit (200 GEN), puis recredite chaque mois calendaire
    # (voir credits_gratuit.py) : sans ca le portefeuille affiche 0 des le 2e mois.
    try:
        import credits_gratuit as _cg
        _cg.crediter_si_necessaire(uid)
    except Exception:
        pass
    # Email de bienvenue (best-effort, non bloquant : un echec ne casse jamais l'inscription)
    try:
        import threading, emailer
        threading.Thread(target=emailer.envoyer_bienvenue,
                         args=(email, user["name"]), daemon=True).start()
    except Exception:
        pass
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


@router.post("/auth/change-password")
def auth_change_password(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    ancien = data.get("ancien", "")
    nouveau = data.get("nouveau", "")
    if not _verifypw(ancien, user.get("pw_hash", "")):
        raise HTTPException(403, "Mot de passe actuel incorrect")
    if len(nouveau) < 6:
        raise HTTPException(400, "Nouveau mot de passe trop court (6 caracteres minimum)")
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == user["id"]:
            u["pw_hash"] = _hashpw(nouveau)
    _wjsonl(_USERS, users)
    return {"ok": True}


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
    profil = _lire_profil(user["id"])
    profil.update({
        "prenom": prenom,
        "projets": (data.get("projets") or "").strip(),
        "aime": (data.get("aime") or "").strip(),
        "naime_pas": (data.get("naime_pas") or "").strip(),
        "style_travail": (data.get("style_travail") or "").strip(),
        "complet": True,
        "updated_at": _dt.utcnow().isoformat(),
    })
    _ecrire_profil(user["id"], profil)
    return {"ok": True}


_LANGUES_SUPPORTEES = {"fr", "en"}


@router.post("/compte/langue")
def compte_langue_post(data: dict, authorization: str = Header(None)):
    """Change la langue d'interface preferee de l'utilisateur, independamment
    du reste du profil (pas besoin de prenom/projets pour juste changer de langue)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    langue = (data.get("langue") or "").strip().lower()
    if langue not in _LANGUES_SUPPORTEES:
        raise HTTPException(400, f"Langue non supportee. Valides : {sorted(_LANGUES_SUPPORTEES)}")
    profil = _lire_profil(user["id"])
    profil["langue"] = langue
    profil["updated_at"] = _dt.utcnow().isoformat()
    _ecrire_profil(user["id"], profil)
    return {"ok": True, "langue": langue}


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


@router.post("/contact/entreprise")
def contact_entreprise(data: dict):
    nom = (data.get("nom") or "").strip()
    email = (data.get("email") or "").strip()
    societe = (data.get("societe") or "").strip()
    besoin = (data.get("besoin") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")
    if not besoin:
        raise HTTPException(400, "Decris ton besoin")
    entree = {
        "id": str(_uid.uuid4()),
        "nom": nom, "email": email, "societe": societe, "besoin": besoin,
        "created_at": _dt.utcnow().isoformat(),
    }
    _ajsonl(_CONTACTS_ENTREPRISE, entree)
    # Notification email best-effort (non bloquant : la demande est deja enregistree ci-dessus)
    try:
        import emailer
        emailer.envoyer_contact_entreprise(nom, email, societe, besoin)
    except Exception:
        pass
    return {"ok": True, "id": entree["id"]}


@router.get("/admin/feedbacks")
def admin_feedbacks(authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Acces refuse")
    items = _rjsonl(_FEEDBACKS)
    return {"feedbacks": list(reversed(items)), "total": len(items)}
