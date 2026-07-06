from __future__ import annotations
import json as _json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .deps import _auth, _est_admin, _exiger_byok

router = APIRouter()


def _gate_connecte(authorization: str | None) -> None:
    """Refuse une action d'ecriture a un anonyme (anti-injection de prompt via skills/taches/memoire).
    L'owner (instance perso) passe toujours ; sinon un compte connecte est exige."""
    import quotas
    if quotas._owner_unlimited():
        return
    if not _auth(authorization):
        raise HTTPException(status_code=401, detail="Connecte-toi a ton compte pour cette action.")


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


class PublierSkillBody(BaseModel):
    nom: str
    description: str = ""
    categorie: str = "General"
    tags: list[str] = Field(default_factory=list)


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
    images: list[dict] = Field(default_factory=list)  # [{b64, mime}] multi-images
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
def creer_skill(body: SkillBody, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import competences
    s = competences.creer(body.nom, body.description, body.instructions, body.outils)
    return {"ok": True, "skill": s}


@router.delete("/skills/{nom}")
def supprimer_skill(nom: str, authorization: str = Header(None)):
    _gate_connecte(authorization)
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
def importer_skills(body: ImportSkillBody, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import competences
    result = competences.importer_depuis_registry(body.skills)
    return {"ok": True, **result}


@router.post("/skills/publier")
def publier_skill(body: PublierSkillBody):
    """Propose un skill local pour la bibliothèque communautaire.
    Sauvegarde dans la file de curation locale ; Jordan valide avant publication."""
    import competences, pathlib, json, datetime
    # Vérifier que le skill existe localement
    sk = competences.charger(body.nom)
    if not sk:
        raise HTTPException(status_code=404, detail=f"Skill '{body.nom}' non trouvé localement.")
    # File de curation : data/skills_curation.json
    curation_file = pathlib.Path(__file__).parent.parent / "data" / "skills_curation.json"
    try:
        queue: list = json.loads(curation_file.read_text(encoding="utf-8")) if curation_file.exists() else []
    except Exception:
        queue = []
    # Éviter les doublons en attente
    if any(e.get("nom") == body.nom for e in queue):
        raise HTTPException(status_code=409, detail="Ce skill est déjà en attente de validation.")
    entry = {
        "nom": body.nom,
        "titre": sk.get("titre", body.nom),
        "description": body.description or sk.get("description", ""),
        "instructions": sk.get("instructions", ""),
        "outils": sk.get("outils", []),
        "categorie": body.categorie,
        "tags": body.tags,
        "date_soumission": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "statut": "en_attente",
    }
    queue.append(entry)
    curation_file.parent.mkdir(parents=True, exist_ok=True)
    curation_file.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": "Skill soumis pour curation.", "nom": body.nom}


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
def creer_tache(body: TacheBody, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import planificateur
    return {"ok": True, "tache": planificateur.creer(
        body.nom, body.agent, body.message, body.intervalle_minutes,
        provider=body.provider, model=body.model)}


@router.post("/taches/{tache_id}/toggle")
def toggle_tache(tache_id: str, body: TacheToggleBody, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import planificateur
    return {"ok": planificateur.basculer(tache_id, body.actif)}


@router.delete("/taches/{tache_id}")
def supprimer_tache(tache_id: str, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import planificateur
    return {"ok": planificateur.supprimer(tache_id)}


# ── Mémoire ─────────────────────────────────────────────────────────────────────

@router.get("/memoire")
def lister_memoire():
    import memoire_agent
    return {"memoires": memoire_agent.lister()}


@router.post("/memoire")
def creer_memoire(body: MemoireBody, authorization: str = Header(None)):
    _gate_connecte(authorization)
    import memoire_agent
    return {"ok": True, "memoire": memoire_agent.memoriser(body.contenu, body.type)}


@router.delete("/memoire/{mem_id}")
def supprimer_memoire(mem_id: str, authorization: str = Header(None)):
    _gate_connecte(authorization)
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
                      x_eclair: str | None = Header(default=None),
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
    _mode_eclair = str(x_eclair or "1").strip() in ("1", "true", "True", "on")
    _user = _auth(authorization)
    hist = [{"role": m.role, "content": m.content} for m in demande.historique]

    if not hist:
        # Debut d'une nouvelle session de chat (jamais par message) : decompte le quota
        # de conversations offertes du palier, ou 15 GEN une fois ce quota epuise. Best
        # effort : n'empeche jamais l'agent de repondre si le debit echoue.
        import credits as _cred
        try:
            _cred.debiter_conversation(_user)
        except Exception:
            pass

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def emit(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            msg = demande.message
            # Traitement images : liste multi-images (nouveau) + rétrocompat image unique
            _all_imgs = list(demande.images or [])
            if demande.image_b64:
                _all_imgs.insert(0, {"b64": demande.image_b64, "mime": demande.image_mime})
            if _all_imgs:
                n = len(_all_imgs)
                emit({"type": "pensee", "texte": f"Analyse de {n} image(s) en cours..."})
                descs = []
                for _i, _img in enumerate(_all_imgs):
                    try:
                        import gateway as _gw
                        _d = _gw.voir(_ctx, _img.get("b64", ""),
                            f"Image {_i+1}/{n} — Decris precisement : textes visibles, elements visuels, structure, contenu.",
                            mime=_img.get("mime", "image/png"))
                        descs.append(f"[Image {_i+1}]\n{_d}")
                    except Exception as _e_img:
                        descs.append(f"[Image {_i+1} — analyse indisponible : {_e_img}]")
                bloc = "\n\n".join(descs)
                msg = f"{bloc}\n\n{msg}".strip() if msg.strip() else bloc
            if demande.fichier_b64 and demande.fichier_nom:
                emit({"type": "pensee", "texte": f"Lecture de {demande.fichier_nom}..."})
                try:
                    import outils_fichiers as _of
                    contenu = _of.extraire_texte_b64(demande.fichier_b64, demande.fichier_nom)
                    prefix = f"[Fichier joint : {demande.fichier_nom}]\n{contenu}"
                    msg = f"{prefix}\n\n{msg}".strip() if msg.strip() else prefix
                except Exception as _e_fic:
                    msg = f"[Fichier joint : {demande.fichier_nom} — lecture echouee : {_e_fic}]\n\n{msg}".strip()
            dialoguer(role, msg, historique=hist, ctx=_ctx, emit=emit, eco=_eco, user=_user, mode_eclair=_mode_eclair)
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
