"""
NEOGEN - Passerelle Telegram : piloter l'agent à distance depuis Telegram.

Si un token de bot Telegram est configuré (env TELEGRAM_BOT_TOKEN ou
credentials/telegram.env), NEOGEN écoute les messages (long-polling getUpdates)
et y répond via l'agent Cerveau. Tu peux ainsi parler à ton agent depuis ton
téléphone, où que tu sois.

SÉCURITÉ :
  - BYOK : répond sur le MODELE LOCAL (Ollama, gratuit) -> aucun crédit payant.
  - Liste blanche optionnelle : NEOGEN_TELEGRAM_ALLOWED = chat_ids séparés par des
    virgules. Si définie, seuls ces chats reçoivent une réponse (évite qu'un inconnu
    pilote ton agent). Sinon, le bot répond à tout le monde (à n'utiliser qu'en privé).
  - Désactivée proprement si aucun token : no-op (aucune erreur).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-22.
"""

from __future__ import annotations

import os
import threading
import time

_THREAD = None
_API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    """Token du bot : env d'abord, puis credentials/telegram.env (chargeur unique, dette F003)."""
    from credentials_loader import lire_cred
    return lire_cred("telegram.env", "TELEGRAM_BOT_TOKEN").strip()


def _autorises() -> set:
    v = os.environ.get("NEOGEN_TELEGRAM_ALLOWED", "").strip()
    return {x.strip() for x in v.split(",") if x.strip()}


def _chat_id_proprietaire() -> str:
    """Destinataire des notifications proactives (decision requise, alertes...).
    Priorite : NEOGEN_TELEGRAM_OWNER_CHAT_ID explicite, sinon le premier de la liste blanche."""
    dedie = os.environ.get("NEOGEN_TELEGRAM_OWNER_CHAT_ID", "").strip()
    if dedie:
        return dedie
    autorises = _autorises()
    return next(iter(autorises), "")


def notifier(texte: str) -> bool:
    """Pousse un message proactif au proprietaire (pas une reponse a un message recu).
    No-op propre si pas de token ou pas de destinataire configure. Ne leve jamais."""
    try:
        token = _token()
        chat_id = _chat_id_proprietaire()
        if not token or not chat_id:
            return False
        res = _appel(token, "sendMessage", chat_id=chat_id, text=(texte or "")[:4000])
        return bool(res.get("ok"))
    except Exception:
        return False


def notifier_decision(job_id: str, titre: str, question: str, options: list) -> bool:
    """Notifie une decision bloquante en attente (l'Ingenieur s'est arrete pour demander)."""
    lignes = [f"🔧 NEOGEN — L'Ingenieur attend ta decision sur « {titre} »", "", question, ""]
    for i, o in enumerate(options or [], 1):
        lbl = o.get("label", "") if isinstance(o, dict) else str(o)
        dsc = o.get("description", "") if isinstance(o, dict) else ""
        lignes.append(f"{i}. {lbl}" + (f" — {dsc}" if dsc else ""))
    lignes.append("")
    lignes.append(f"Reponds dans l'app NEOGEN (section Ingenieur, job {job_id[:8]}) — choix ou reponse libre.")
    return notifier("\n".join(lignes))


def _appel(token: str, methode: str, **params):
    import httpx
    try:
        r = httpx.post(_API.format(token=token, method=methode), json=params, timeout=70)
        return r.json()
    except Exception:
        return {}


def _repondre_agent(message: str) -> str:
    """Fait répondre l'agent Cerveau sur le modèle local (gratuit)."""
    try:
        from agent_core import dialoguer
        from gateway import LLMContext
        return dialoguer("cerveau", message, ctx=LLMContext(provider="local"), eco=True)
    except Exception as e:
        return f"[erreur agent] {e}"


def _boucle(token: str) -> None:
    """Long-polling : récupère les messages et y répond."""
    autorises = _autorises()
    offset = 0
    while True:
        try:
            try:
                import robustesse as _rob
                _rob.battement("telegram", liste_blanche=bool(autorises))
            except Exception:
                pass
            res = _appel(token, "getUpdates", offset=offset, timeout=60)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                texte = (msg.get("text") or "").strip()
                if not texte or not chat_id:
                    continue
                if autorises and chat_id not in autorises:
                    _appel(token, "sendMessage", chat_id=chat_id,
                           text="Ce bot NEOGEN est prive (ton chat n'est pas autorise).")
                    continue
                _appel(token, "sendChatAction", chat_id=chat_id, action="typing")
                rep = _repondre_agent(texte)
                # Telegram limite a 4096 caracteres par message.
                _appel(token, "sendMessage", chat_id=chat_id, text=(rep or "...")[:4000])
        except Exception:
            time.sleep(5)


def demarrer() -> bool:
    """Démarre la passerelle si un token est configuré. Retourne True si active."""
    global _THREAD
    token = _token()
    if not token:
        return False
    if _THREAD is None or not _THREAD.is_alive():
        _THREAD = threading.Thread(target=_boucle, args=(token,), daemon=True)
        _THREAD.start()
    return True


def statut() -> dict:
    """État de la passerelle (pour l'UI) — sans jamais exposer le token."""
    return {
        "configuree": bool(_token()),
        "active": bool(_THREAD and _THREAD.is_alive()),
        "liste_blanche": bool(_autorises()),
    }


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - PASSERELLE TELEGRAM : auto-vérification")
    print("=" * 60)
    st = statut()
    assert "configuree" in st and "active" in st
    # Sans token -> demarrer() renvoie False proprement.
    if not _token():
        assert demarrer() is False
        print("  pas de token -> passerelle desactivee proprement : OK")
    else:
        print("  token detecte -> passerelle prete : OK")
    print("=" * 60)
