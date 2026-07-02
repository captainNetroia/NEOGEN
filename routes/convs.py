"""NEOGEN — Conversations multi-tours : stockage server-side par utilisateur/agent."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from .deps import _auth

router = APIRouter()

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USERS_DIR = os.path.join(_BASE, "data", "users")

# role/conv_id sont attaquant-controlables (query/body/path param) : liste blanche stricte
# pour empecher toute traversee de repertoire (".." etc.) dans les chemins construits.
_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]")


def _id_sur(valeur: str, defaut: str = "") -> str:
    return _ID_SAFE.sub("", valeur or "")[:64] or defaut


def _conv_dir(user_id: str, role: str) -> str:
    d = os.path.join(_USERS_DIR, user_id, "convs", _id_sur(role, "defaut"))
    os.makedirs(d, exist_ok=True)
    return d


def _conv_path(user_id: str, role: str, conv_id: str) -> str:
    cid = _id_sur(conv_id)
    if not cid:
        raise HTTPException(400, "id de conversation invalide")
    return os.path.join(_conv_dir(user_id, role), f"{cid}.json")


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/agent/convs")
def list_convs(role: str, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    d = _conv_dir(user["id"], role)
    convs = []
    for fname in sorted(os.listdir(d), reverse=True):
        if not fname.endswith(".json"):
            continue
        try:
            c = _read(os.path.join(d, fname))
            convs.append({
                "id": c["id"],
                "title": c.get("title", "Sans titre"),
                "created_at": c.get("created_at"),
                "updated_at": c.get("updated_at"),
                "archived": c.get("archived", False),
                "message_count": len(c.get("messages", [])),
            })
        except Exception:
            pass
    convs.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"convs": convs}


@router.post("/agent/convs")
def save_conv(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    role = (data.get("role") or "").strip()
    if not role:
        raise HTTPException(400, "role requis")
    conv_id = (data.get("id") or "").strip() or str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    path = _conv_path(user["id"], role, conv_id)
    existing: dict = {}
    if os.path.exists(path):
        try:
            existing = _read(path)
        except Exception:
            pass
    conv = {
        "id": conv_id,
        "role": role,
        "title": (data.get("title") or existing.get("title") or "Conversation").strip(),
        "messages": data.get("messages", existing.get("messages", [])),
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "archived": data.get("archived", existing.get("archived", False)),
    }
    _write(path, conv)
    return {"ok": True, "id": conv_id}


@router.get("/agent/convs/{conv_id}")
def get_conv(conv_id: str, role: str, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    path = _conv_path(user["id"], role, conv_id)
    if not os.path.exists(path):
        raise HTTPException(404, "Introuvable")
    return _read(path)


@router.delete("/agent/convs/{conv_id}")
def delete_conv(conv_id: str, role: str, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    path = _conv_path(user["id"], role, conv_id)
    if os.path.exists(path):
        os.remove(path)
    return {"ok": True}


@router.post("/agent/compact")
def compact_conv(data: dict, authorization: str = Header(None)):
    """Resume les messages via LLM Haiku (leger, econome)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    messages = data.get("messages", [])
    if len(messages) < 4:
        raise HTTPException(400, "Pas assez de messages (minimum 4)")
    conv_text = "\n".join(
        f"{'Utilisateur' if m['role'] == 'user' else 'Agent'}: {(m.get('content') or '').strip()}"
        for m in messages
        if (m.get("content") or "").strip()
    )
    prompt = (
        "Resume cette conversation de facon concise et structuree. "
        "Conserve : les decisions importantes, le contexte technique, "
        "les elements cles necessaires pour continuer. "
        "Reponds uniquement avec le resume structure, sans introduction.\n\n"
        + conv_text
    )
    try:
        import gateway
        cli = gateway.client(ctx=None, tier="leger")
        result = cli.messages.create(
            system="Tu es un assistant qui resumes des conversations pour en preserver le contexte essentiel.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        summary = result.content[0].text if result.content else ""
        return {"summary": summary}
    except Exception as exc:
        raise HTTPException(500, f"Erreur resume : {exc}")
