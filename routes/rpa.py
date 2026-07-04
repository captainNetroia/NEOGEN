from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import quotas as _quotas
import rpa
from .deps import _auth

router = APIRouter()


def _gate_owner(authorization: str | None = None):
    """Vérifie que l'appelant est le propriétaire (NEOGEN_OWNER_UNLIMITED=1 ou palier enterprise)."""
    if _quotas._owner_unlimited():
        return
    user = _auth(authorization)
    if _quotas.palier(user) == "enterprise":
        return
    raise HTTPException(status_code=403, detail="Section réservée au propriétaire.")


def _gate_rpa(authorization: str | None = None) -> str:
    """Authentifie l'appelant pour un endpoint RPA et renvoie le user_id à utiliser
    pour scoper sa file/ses résultats/son contexte navigateur. Le propriétaire
    (instance perso ou palier enterprise) a un accès illimité sous l'id "__owner__".
    Sinon : compte connecté obligatoire (401) + palier minimum "essential" pour le
    RPA (402), cf. quotas.PALIER_REQUIS["rpa"]."""
    if _quotas._owner_unlimited():
        return "__owner__"
    user = _auth(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Non authentifié.")
    if _quotas.palier(user) == "enterprise":
        return "__owner__"
    v = _quotas.verifier(user, "rpa")
    if not v["autorise"]:
        raise HTTPException(status_code=402, detail=v["raison"])
    return user["id"]


def _refuser_si_liste_noire(exc: Exception):
    if isinstance(exc, rpa.ActionRpaRefusee):
        raise HTTPException(status_code=400, detail=str(exc))
    raise exc


class RpaContinuousBody(BaseModel):
    enabled: bool


class RpaResultBody(BaseModel):
    id: str
    status: str
    error: str | None = None


class RpaExecuteBody(BaseModel):
    actions: list[dict]


class RpaRecordStopBody(BaseModel):
    name: str


@router.post("/rpa/agent/ping")
def rpa_ping(authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    rpa.ping_agent(uid)
    return {"recording": rpa.is_recording() or rpa.is_continuous(),
            "continuous": rpa.is_continuous()}


@router.post("/rpa/continuous")
def rpa_continuous_set(body: RpaContinuousBody, authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    if body.enabled:
        if not _quotas.verifier(_auth(authorization), "apprentissage_continu")["autorise"]:
            raise HTTPException(status_code=402,
                                detail="L'apprentissage continu est reserve a la version premium.")
    return {"enabled": rpa.set_continuous(body.enabled)}


@router.get("/rpa/continuous")
def rpa_continuous_get(authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    return rpa.continuous_status()


@router.get("/rpa/status")
def rpa_status(authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    return {"connected": rpa.is_agent_connected(uid), "recording": rpa.is_recording(),
            "queue_len": len(rpa.RpaQueue.list_queue(uid))}


@router.get("/rpa/pending")
def rpa_pending(authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    act = rpa.RpaQueue.get_pending(uid)
    if not act:
        raise HTTPException(status_code=404, detail="No pending actions")
    return act


@router.post("/rpa/screenshot")
def rpa_screenshot(body: dict, authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    img = body.get("image", "")
    if not img:
        raise HTTPException(status_code=400, detail="image manquante")
    rpa.store_screenshot(uid, img)
    return {"ok": True}


@router.post("/rpa/action/result")
def rpa_action_result(body: RpaResultBody, authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    ok = rpa.RpaQueue.set_result(uid, body.id, body.status, body.error)
    if not ok:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"ok": True}


@router.post("/rpa/clear")
def rpa_clear(authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    count = rpa.RpaQueue.clear(uid)
    return {"cleared": count}


@router.post("/rpa/execute")
def rpa_execute(body: RpaExecuteBody, authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    try:
        ids = rpa.RpaQueue.push_multiple(uid, body.actions)
    except rpa.ActionRpaRefusee as e:
        _refuser_si_liste_noire(e)
    return {"ids": ids}


@router.post("/rpa/record/start")
def rpa_record_start(authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    rpa.start_recording()
    return {"ok": True}


@router.post("/rpa/record/action")
def rpa_record_action(action: dict, authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    rpa.add_recorded_action(action)
    return {"ok": True}


@router.post("/rpa/record/stop")
def rpa_record_stop(body: RpaRecordStopBody, authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    rec = rpa.stop_recording(body.name)
    if not rec:
        raise HTTPException(status_code=400, detail="Recording not active")
    return rec


@router.get("/rpa/recordings")
def rpa_list_recordings(authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    return {"recordings": rpa.list_recordings()}


@router.get("/rpa/recordings/{rec_id}")
def rpa_get_recording(rec_id: str, authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    rec = rpa.get_recording(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return rec


@router.post("/rpa/browser_context")
def rpa_store_browser_context(body: dict, authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    rpa.store_browser_context(uid, body)
    return {"ok": True}


@router.get("/rpa/browser_context")
def rpa_get_browser_context(authorization: str | None = Header(default=None)):
    uid = _gate_rpa(authorization)
    return rpa.get_browser_context(uid)


# ── Settings (consent level) ────────────────────────────────────────────────
# Réglage global partagé (pas par utilisateur) : voir le commentaire dans rpa.py
# au-dessus de _SETTINGS_FILE — c'est un paramètre de la MACHINE hôte de l'agent,
# pas du compte NEOGEN connecté.

@router.get("/rpa/settings")
def rpa_settings_get(authorization: str | None = Header(default=None)):
    _gate_rpa(authorization)
    return rpa.get_settings()


@router.post("/rpa/settings")
def rpa_settings_post(body: dict, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    return rpa.save_settings(body)


# ── Mode Objectif (/goal) ───────────────────────────────────────────────────

class RpaGoalBody(BaseModel):
    objectif: str
    infos_utilisateur: str = ""


@router.post("/rpa/goal")
def rpa_goal(body: RpaGoalBody, authorization: str | None = Header(default=None)):
    """
    Mode Objectif : l'utilisateur décrit une mission en langage naturel.
    Le LLM analyse l'écran actuel + l'objectif, génère un plan d'actions RPA,
    identifie les infos manquantes, puis exécute la mission via outil_executer_mission_rpa.
    """
    import json as _json
    import time as _time
    import gateway as _gw
    import outils as _outils

    uid = _gate_rpa(authorization)

    if not rpa.is_agent_connected(uid):
        return {"erreur": "Agent RPA non connecté. Lance rpa_agent.py sur ton poste."}

    objectif = body.objectif.strip()
    infos_util = (body.infos_utilisateur or "").strip()

    # Capture screenshot pour donner le contexte écran au LLM
    screen_b64 = None
    t_shot = rpa.request_screenshot(uid)
    for _ in range(15):
        _time.sleep(0.3)
        screen_b64 = rpa.get_screenshot(uid, apres=t_shot)
        if screen_b64:
            break

    _SYSTEM = (
        "Tu es un agent RPA expert. Tu pilotes physiquement un ordinateur Windows.\n"
        "Actions disponibles : click(x,y), double_click(x,y), right_click(x,y), "
        "type(text), press(key), hotkey(keys:[]), scroll(x,y,direction,amount), "
        "open_url(url), screenshot(), sleep(ms).\n\n"
        "Réponds en JSON STRICT (sans bloc markdown) :\n"
        "{\n"
        "  \"infos_manquantes\": [{\"question\": \"...\", \"champ\": \"id_court\"}],\n"
        "  \"actions\": [{\"action\": \"...\", ...}]\n"
        "}\n"
        "RÈGLES :\n"
        "- Si des données spécifiques sont nécessaires (identifiant, mot de passe, SIRET, "
        "valeur de formulaire) et non fournies → liste-les dans infos_manquantes, laisse "
        "actions vide.\n"
        "- Sinon, génère la séquence d'actions complète. Utilise les coordonnées visibles "
        "sur l'écran fourni. Pour open_url, utilise l'URL exacte si connue."
    )

    prompt = f"Objectif : {objectif}"
    if infos_util:
        prompt += f"\nInformations fournies par l'utilisateur : {infos_util}"
    if screen_b64:
        prompt += "\nL'écran actuel est fourni ci-joint. Génère les actions précises."
    else:
        prompt += "\nAucun écran disponible — génère un plan d'actions générique."

    try:
        if screen_b64:
            full_prompt = f"{_SYSTEM}\n\n{prompt}"
            text = _gw.voir(None, screen_b64, full_prompt)
        else:
            cli = _gw.client(ctx=None, tier="fort")
            resp = cli.messages.create(
                messages=[{"role": "user", "content": prompt}],
                system=_SYSTEM,
                max_tokens=2000,
            )
            text = "".join(getattr(b, "text", "") for b in resp.content)

        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        plan = _json.loads(text)
    except Exception as e:
        return {"erreur": f"Erreur analyse objectif : {e}"}

    infos_manquantes = plan.get("infos_manquantes") or []
    actions = plan.get("actions") or []

    if infos_manquantes:
        return {"infos_manquantes": infos_manquantes}

    if not actions:
        return {"erreur": "Aucune action générée pour cet objectif."}

    try:
        rapport = _outils.outil_executer_mission_rpa(
            objectif=objectif,
            actions=actions,
            infos_utilisateur=infos_util,
            _user={"id": uid},
        )
    except rpa.ActionRpaRefusee as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"rapport": rapport}
