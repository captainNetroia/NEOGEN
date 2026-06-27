from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import rpa
from .deps import _auth

router = APIRouter()


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
def rpa_clear():
    count = rpa.RpaQueue.clear()
    return {"cleared": count}


@router.post("/rpa/execute")
def rpa_execute(body: RpaExecuteBody):
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
