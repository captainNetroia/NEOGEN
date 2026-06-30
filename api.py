"""
NEOGEN - Service FastAPI : l'organisme devient exploitable

Expose le pipeline reel de production derriere une API HTTP :
  POST /fabriquer      intention -> produit gouverne, execute en conteneur
  GET  /produits       liste les produits persistes au registre
  GET  /produits/{id}  recharge le code d'un produit
  GET  /health         etat du service + disponibilite Docker

MODELE DE CONFIANCE (assume) :
  - CE service est notre code (de confiance) : il a le droit de piloter Docker
    pour creer des bacs a sable.
  - le code GENERE par l'IA (non fiable) ne touche JAMAIS au demon Docker : il
    tourne dans un conteneur durci (--network none, --cap-drop ALL, non-root,
    ressources bornees) via executeur_conteneur.
  - en conteneur, ce service monte le socket Docker (sibling containers) -> il a
    un controle root-equivalent du Docker hote. ACCEPTABLE seulement sur une
    MACHINE DEDIEE. JAMAIS sur le VPS de production (netroia.tech + n8n).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations

import os as _os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import robustesse as _rob
from executeur_conteneur import docker_disponible
import ui as _ui


@asynccontextmanager
async def _lifespan(app):
    """Démarrage : lance cron + Telegram + auto-amélioration + socle compétences.
    Chaque démarrage est protégé (jamais bloquant). Remplace on_event (déprécié, dette F005)."""
    _rob.protege(lambda: __import__("planificateur").demarrer(), operation="start cron", source="startup")
    _rob.protege(lambda: __import__("passerelle_telegram").demarrer(), operation="start telegram", source="startup")
    _rob.protege(lambda: __import__("auto_amelioration").demarrer(), operation="start auto-amelioration", source="startup")
    _rob.protege(lambda: __import__("competences").assurer_socle(), operation="socle competences", source="startup")
    _rob.protege(lambda: __import__("savoir").HUB.rafraichir(), operation="rafraichir hub savoir", source="startup")
    # Conscience de soi : charge les capacites forgees + reconcilie le registre avec la realite,
    # pour que le systeme sache des le demarrage ce qui est integre / en echec / a reparer.
    _rob.protege(lambda: __import__("capacites_forgees").recharger(), operation="charger capacites forgees", source="startup")
    _rob.protege(lambda: __import__("conscience").diagnostiquer(), operation="diagnostic conscience", source="startup")
    # Le systeme se soigne seul : auto-reparation des capacites cassees + maintenance periodique.
    _rob.protege(lambda: __import__("conscience").auto_reparer(), operation="auto-reparation conscience", source="startup")
    _rob.protege(lambda: __import__("conscience").demarrer_maintenance(6.0), operation="maintenance conscience", source="startup")
    _rob.protege(lambda: __import__("version_guard").check_on_startup(), operation="garde-fou compatibilite", source="startup")
    _rob.journaliser("NEOGEN demarre : services autonomes actifs", "info", source="startup")
    yield


app = FastAPI(
    title="NEOGEN",
    description="Une intention parlee devient une application gouvernee, generee et executee en conteneur durci.",
    version="5.0",
    lifespan=_lifespan,
)

# CORS resserre : par defaut localhost uniquement. En prod, definir NEOGEN_CORS_ORIGINS.
_cors_env = _os.environ.get("NEOGEN_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or [
    "http://localhost:8000", "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Durcissement frontieres publiques : rate limit + headers securite (CSP/nosniff/frame).
# Non intrusif : desactive sur l'instance proprio, exempte static/health.
_rob.protege(lambda: __import__("securite_web").installer(app),
             operation="installer securite web", source="startup")
app.mount("/static", StaticFiles(directory=_os.path.join(_os.path.dirname(__file__), "static")), name="static")

# ── Routers ────────────────────────────────────────────────────────────────────
from routes.auth import router as _r_auth
from routes.produits import router as _r_produits
from routes.agents import router as _r_agents
from routes.premium import router as _r_premium
from routes.telemetrie import router as _r_telemetrie
from routes.integrations import router as _r_integrations
from routes.rpa import router as _r_rpa
from routes.savoir import router as _r_savoir
from routes.convs import router as _r_convs

app.include_router(_r_auth)
app.include_router(_r_produits)
app.include_router(_r_agents)
app.include_router(_r_premium)
app.include_router(_r_telemetrie)
app.include_router(_r_integrations)
app.include_router(_r_rpa)
app.include_router(_r_savoir)
app.include_router(_r_convs)

# ── Chemins data ───────────────────────────────────────────────────────────────
_BASE = _os.path.dirname(_os.path.abspath(__file__))
_DATA = _os.path.join(_BASE, "data")

_MIME_RAPPORTS = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv":  "text/csv; charset=utf-8",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html; charset=utf-8",
}

# ── Routes core ────────────────────────────────────────────────────────────────

@app.get("/telegram/statut")
def telegram_statut():
    import passerelle_telegram
    return passerelle_telegram.statut()


@app.get("/", response_class=HTMLResponse)
def racine():
    # rendre_page injecte les fragments forges (fail-closed : sert la page d'origine si souci).
    return _ui.rendre_page()


@app.get("/info")
def info():
    return {
        "service": "NEOGEN",
        "version": "5.0",
        "endpoints": ["/ (UI)", "/fabriquer (POST)", "/produits", "/produits/{id}", "/health", "/info"],
    }


@app.get("/fichiers/rapports/{nom}")
def telecharger_rapport(nom: str):
    import pathlib, re
    if not re.fullmatch(r"rapport_[a-f0-9]{8}\.(docx|pdf|xlsx|csv|pptx|html)", nom):
        raise HTTPException(status_code=400, detail="nom invalide")
    p = pathlib.Path(_DATA) / "rapports" / nom
    if not p.exists():
        raise HTTPException(status_code=404, detail="rapport introuvable")
    ext = nom.rsplit(".", 1)[-1]
    media = _MIME_RAPPORTS.get(ext, "application/octet-stream")
    return FileResponse(str(p), filename=nom, media_type=media)


@app.get("/health")
def health():
    ok, info = docker_disponible()
    sortie = {
        "status": "ok",
        "docker": ok,
        "docker_info": info,
        "note": "sans Docker, l'execution du code genere retombe sur l'isolation processus (moins sure)",
    }
    try:
        sortie["sante"] = _rob.sante().get("composants", {})
        sortie["alertes_recentes"] = _rob.lire_journal(limite=10, niveau_min="alerte")
    except Exception:
        pass
    try:
        import planificateur as _pl
        sortie["cron"] = _pl.statut()
    except Exception:
        pass
    try:
        import passerelle_telegram as _tg
        sortie["telegram"] = _tg.statut()
    except Exception:
        pass
    try:
        import routeur_bandit as _rb
        sortie["routeur_bandit"] = _rb.etat()
    except Exception:
        pass
    try:
        import environnement as _env
        sortie["environnement"] = _env.resume()
    except Exception:
        pass
    try:
        import coherence_auto as _coh
        sortie["coherence"] = _coh.audit_journeys()
    except Exception:
        pass
    return sortie
