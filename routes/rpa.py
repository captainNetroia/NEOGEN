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
def rpa_ping():
    rpa.ping_agent()
    return {"recording": rpa.is_recording() or rpa.is_continuous(),
            "continuous": rpa.is_continuous()}


@router.post("/rpa/continuous")
def rpa_continuous_set(body: RpaContinuousBody, authorization: str | None = Header(default=None)):
    if body.enabled:
        import quotas
        if not quotas.verifier(_auth(authorization), "apprentissage_continu")["autorise"]:
            raise HTTPException(status_code=402,
                                detail="L'apprentissage continu est reserve a la version premium.")
    return {"enabled": rpa.set_continuous(body.enabled)}


@router.get("/rpa/continuous")
def rpa_continuous_get():
    return rpa.continuous_status()


@router.get("/rpa/status")
def rpa_status():
    return {"connected": rpa.is_agent_connected(), "recording": rpa.is_recording(),
            "queue_len": len(rpa.RpaQueue.list_queue())}


@router.get("/rpa/pending")
def rpa_pending():
    act = rpa.RpaQueue.get_pending()
    if not act:
        raise HTTPException(status_code=404, detail="No pending actions")
    return act


@router.post("/rpa/screenshot")
def rpa_screenshot(body: dict):
    img = body.get("image", "")
    if not img:
        raise HTTPException(status_code=400, detail="image manquante")
    rpa.store_screenshot(img)
    return {"ok": True}


@router.post("/rpa/action/result")
def rpa_action_result(body: RpaResultBody):
    ok = rpa.RpaQueue.set_result(body.id, body.status, body.error)
    if not ok:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"ok": True}


@router.post("/rpa/clear")
def rpa_clear(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    count = rpa.RpaQueue.clear()
    return {"cleared": count}


@router.post("/rpa/execute")
def rpa_execute(body: RpaExecuteBody, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    ids = rpa.RpaQueue.push_multiple(body.actions)
    return {"ids": ids}


@router.post("/rpa/record/start")
def rpa_record_start():
    rpa.start_recording()
    return {"ok": True}


@router.post("/rpa/record/action")
def rpa_record_action(action: dict):
    rpa.add_recorded_action(action)
    return {"ok": True}


@router.post("/rpa/record/stop")
def rpa_record_stop(body: RpaRecordStopBody):
    rec = rpa.stop_recording(body.name)
    if not rec:
        raise HTTPException(status_code=400, detail="Recording not active")
    return rec


@router.get("/rpa/recordings")
def rpa_list_recordings():
    return {"recordings": rpa.list_recordings()}


@router.get("/rpa/recordings/{rec_id}")
def rpa_get_recording(rec_id: str):
    rec = rpa.get_recording(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return rec


@router.post("/rpa/browser_context")
def rpa_store_browser_context(body: dict):
    rpa.store_browser_context(body)
    return {"ok": True}


@router.get("/rpa/browser_context")
def rpa_get_browser_context():
    return rpa.get_browser_context()


# ── Settings (consent level) ────────────────────────────────────────────────

@router.get("/rpa/settings")
def rpa_settings_get():
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
def rpa_goal(body: RpaGoalBody):
    """
    Mode Objectif : l'utilisateur décrit une mission en langage naturel.
    Le LLM analyse l'écran actuel + l'objectif, génère un plan d'actions RPA,
    identifie les infos manquantes, puis exécute la mission via outil_executer_mission_rpa.
    """
    import json as _json
    import time as _time
    import gateway as _gw
    import outils as _outils

    if not rpa.is_agent_connected():
        return {"erreur": "Agent RPA non connecté. Lance rpa_agent.py sur ton poste."}

    objectif = body.objectif.strip()
    infos_util = (body.infos_utilisateur or "").strip()

    # Capture screenshot pour donner le contexte écran au LLM
    screen_b64 = None
    t_shot = rpa.request_screenshot()
    for _ in range(15):
        _time.sleep(0.3)
        screen_b64 = rpa.get_screenshot(apres=t_shot)
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

    rapport = _outils.outil_executer_mission_rpa(
        objectif=objectif,
        actions=actions,
        infos_utilisateur=infos_util,
    )
    return {"rapport": rapport}
