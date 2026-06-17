"""
VIVARIUM - Service FastAPI : l'organisme devient exploitable

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

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import registre
from executeur_conteneur import docker_disponible
from pipeline import fabriquer_reel
from ui import PAGE

app = FastAPI(
    title="VIVARIUM",
    description="Une intention parlee devient une application gouvernee, generee et executee en conteneur durci.",
    version="5.0",
)


class DemandeFabrication(BaseModel):
    intention: str = Field(min_length=3, max_length=2000,
                           description="ce que le produit doit faire, en langage naturel")
    reparer: bool = Field(default=True, description="auto-reparation sur echec d'execution")
    max_tentatives: int = Field(default=3, ge=1, le=5)


class ReponseFabrication(BaseModel):
    succes: bool
    verdict: str
    tentatives: int
    lignes: int
    lecons: list[str]
    produit_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def racine():
    """Page humaine de l'organisme : decrire une intention, voir le produit + le catalogue."""
    return PAGE


@app.get("/info")
def info():
    return {
        "service": "VIVARIUM",
        "version": "5.0",
        "endpoints": ["/ (UI)", "/fabriquer (POST)", "/produits", "/produits/{id}", "/health", "/info"],
    }


@app.get("/health")
def health():
    ok, info = docker_disponible()
    return {
        "status": "ok",
        "docker": ok,
        "docker_info": info,
        "note": "sans Docker, l'execution du code genere retombe sur l'isolation processus (moins sure)",
    }


@app.post("/fabriquer", response_model=ReponseFabrication)
def fabriquer_endpoint(demande: DemandeFabrication):
    """Transforme une intention en produit : ADN -> code -> 3 garde-fous -> conteneur -> registre."""
    try:
        r = fabriquer_reel(
            demande.intention,
            reparer=demande.reparer,
            max_tentatives=demande.max_tentatives,
            enregistrer=True,
        )
    except Exception as e:  # cle API manquante, panne reseau Claude, etc.
        raise HTTPException(status_code=502, detail=f"echec de fabrication : {e}")

    produit_id = None
    if r.succes:
        entrees = registre.lister()
        if entrees:
            produit_id = entrees[-1]["id"]

    return ReponseFabrication(
        succes=r.succes, verdict=r.verdict, tentatives=r.tentatives,
        lignes=r.lignes, lecons=r.lecons, produit_id=produit_id,
    )


@app.get("/produits")
def lister_produits():
    """Catalogue des produits qui ont passe les garde-fous et tourne."""
    return {"produits": registre.lister()}


@app.get("/produits/{produit_id}")
def obtenir_produit(produit_id: str):
    code = registre.charger(produit_id)
    if code is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    return {"id": produit_id, "code": code}
