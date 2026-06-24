from __future__ import annotations
import json as _json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .deps import _auth, _est_admin, _exiger_byok, _verifier_quota

router = APIRouter()

_registry_cache: dict = {"ts": 0.0, "data": None}
_REGISTRY_TTL = 3600.0
_REGISTRY_URL = (
    "https://raw.githubusercontent.com/captainNetroia/VIVARIUM/main/registry/skills-community.json"
)


class SkillBody(BaseModel):
    nom: str
    description: str = ""
    instructions: str
    outils: list[str] = Field(default_factory=list)


class ImportSkillBody(BaseModel):
    skills: list[dict]


class TacheBody(BaseModel):
    nom: str
    agent: str = "cerveau"
    message: str
    intervalle_minutes: int = 60
    provider: str = "local"
    model: str | None = None


class TacheToggleBody(BaseModel):
    actif: bool


class MemoireBody(BaseModel):
    contenu: str
    type: str = "fait"


class RecommanderBody(BaseModel):
    demande: str


class MessageChat(BaseModel):
    role: str
    content: str


class DemandeChat(BaseModel):
    message: str
    historique: list[MessageChat] = Field(default_factory=list)
    image_b64: str | None = None
    image_mime: str = "image/png"
    fichier_b64: str | None = None
    fichier_nom: str = ""


# ── Agents ──────────────────────────────────────────────────────────────────────

@router.get("/agents")
def lister_agents():
    from agent_core import PROFILS
    return {"agents": {k: {"titre": v["titre"], "outils": v["outils"],
                           "delegue": v.get("delegue", False)} for k, v in PROFILS.items()}}


# ── Skills ──────────────────────────────────────────────────────────────────────

@router.get("/skills")
def lister_skills():
    import competences
    return {"skills": competences.lister()}


@router.post("/skills")
def creer_skill(body: SkillBody):
    import competences
    s = competences.creer(body.nom, body.description, body.instructions, body.outils)
    return {"ok": True, "skill": s}


@router.delete("/skills/{nom}")
def supprimer_skill(nom: str):
    import competences
    return {"ok": competences.supprimer(nom)}


@router.get("/skills/registry")
def skills_registry():
    import time
    import httpx as _hx
    now = time.time()
    if _registry_cache["data"] and (now - _registry_cache["ts"]) < _REGISTRY_TTL:
        return {"ok": True, "source": "cache", "skills": _registry_cache["data"]}
    try:
        resp = _hx.get(_REGISTRY_URL, timeout=10.0)
        resp.raise_for_status()
        skills = resp.json().get("skills", [])
        _registry_cache["ts"] = now
        _registry_cache["data"] = skills
        return {"ok": True, "source": "registry", "skills": skills}
    except Exception:
        if _registry_cache["data"]:
            return {"ok": True, "source": "cache_stale", "skills": _registry_cache["data"]}
        import pathlib, json
        p = pathlib.Path(__file__).parent.parent / "registry" / "skills-community.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                skills = json.load(f).get("skills", [])
            if skills:
                _registry_cache["ts"] = now
                _registry_cache["data"] = skills
                return {"ok": True, "source": "local", "skills": skills}
        raise HTTPException(status_code=503, detail="registry inaccessible et aucun fallback local")


@router.post("/skills/import")
def importer_skills(body: ImportSkillBody):
    import competences
    result = competences.importer_depuis_registry(body.skills)
    return {"ok": True, **result}


# ── Auto-amélioration ───────────────────────────────────────────────────────────

@router.get("/auto-amelioration")
def auto_amelioration():
    import auto_amelioration as aa
    return aa.analyser_usage()


@router.get("/auto-amelioration/journal")
def auto_amelioration_journal():
    import auto_amelioration as aa
    return {"actions": aa.journal_actions(limite=30)}


@router.post("/auto-amelioration/cycle")
def auto_amelioration_cycle(authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Reserve a l'administrateur")
    import auto_amelioration as aa
    return aa.cycle(force=True)


# ── Tâches cron ─────────────────────────────────────────────────────────────────

@router.get("/taches")
def lister_taches():
    import planificateur
    return {"taches": planificateur.lister()}


@router.post("/taches")
def creer_tache(body: TacheBody):
    import planificateur
    return {"ok": True, "tache": planificateur.creer(
        body.nom, body.agent, body.message, body.intervalle_minutes,
        provider=body.provider, model=body.model)}


@router.post("/taches/{tache_id}/toggle")
def toggle_tache(tache_id: str, body: TacheToggleBody):
    import planificateur
    return {"ok": planificateur.basculer(tache_id, body.actif)}


@router.delete("/taches/{tache_id}")
def supprimer_tache(tache_id: str):
    import planificateur
    return {"ok": planificateur.supprimer(tache_id)}


# ── Mémoire ─────────────────────────────────────────────────────────────────────

@router.get("/memoire")
def lister_memoire():
    import memoire_agent
    return {"memoires": memoire_agent.lister()}


@router.post("/memoire")
def creer_memoire(body: MemoireBody):
    import memoire_agent
    return {"ok": True, "memoire": memoire_agent.memoriser(body.contenu, body.type)}


@router.delete("/memoire/{mem_id}")
def supprimer_memoire(mem_id: str):
    import memoire_agent
    return {"ok": memoire_agent.supprimer(mem_id)}


# ── LLM recommander ─────────────────────────────────────────────────────────────

@router.post("/llm/recommander")
def llm_recommander(body: RecommanderBody):
    import gateway
    return gateway.recommander_tier(body.demande)


# ── Chat agent SSE ──────────────────────────────────────────────────────────────

@router.post("/agent/{role}/chat/stream")
def agent_chat_stream(role: str, demande: DemandeChat,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None),
                      x_llm_eco: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
    import queue, threading
    from sanitizer import nettoyer
    from gateway import contexte_depuis_headers
    from agent_core import dialoguer, PROFILS

    if role not in PROFILS:
        raise HTTPException(status_code=404, detail=f"agent inconnu : {role}")

    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _eco = str(x_llm_eco or "").strip() in ("1", "true", "True", "on")
    _user = _auth(authorization)
    hist = [{"role": m.role, "content": m.content} for m in demande.historique]

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def emit(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            msg = demande.message
            if demande.image_b64:
                emit({"type": "pensee", "texte": "Analyse de l'image en cours..."})
                try:
                    import gateway as _gw
                    desc = _gw.voir(_ctx, demande.image_b64,
                        "Decris precisement cette image : textes visibles, elements visuels, structure, contenu.",
                        mime=demande.image_mime)
                    msg = f"[Image jointe]\n{desc}\n\n{msg}".strip() if msg.strip() else f"[Image jointe]\n{desc}"
                except Exception as _e_img:
                    msg = f"[Image jointe — analyse indisponible : {_e_img}]\n\n{msg}".strip()
            if demande.fichier_b64 and demande.fichier_nom:
                emit({"type": "pensee", "texte": f"Lecture de {demande.fichier_nom}..."})
                try:
                    import outils_fichiers as _of
                    contenu = _of.extraire_texte_b64(demande.fichier_b64, demande.fichier_nom)
                    prefix = f"[Fichier joint : {demande.fichier_nom}]\n{contenu}"
                    msg = f"{prefix}\n\n{msg}".strip() if msg.strip() else prefix
                except Exception as _e_fic:
                    msg = f"[Fichier joint : {demande.fichier_nom} — lecture echouee : {_e_fic}]\n\n{msg}".strip()
            dialoguer(role, msg, historique=hist, ctx=_ctx, emit=emit, eco=_eco, user=_user)
        except Exception as e:
            file_evts.put({"type": "erreur", "message": nettoyer(str(e))})
        finally:
            file_evts.put(_SENTINEL)

    threading.Thread(target=travailler, daemon=True).start()

    def flux():
        while True:
            evt = file_evts.get()
            if evt is _SENTINEL:
                break
            yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
