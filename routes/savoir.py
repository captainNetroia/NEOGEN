from __future__ import annotations

import json as _json

from fastapi import APIRouter, Body, Header, HTTPException, Query, Response

import quotas as _quotas
import savoir as _savoir
import proposeur_hub as _proposeur

# Clés de payload qui signalent qu'une règle nécessite du code runtime (pas juste JSON).
_CLES_COMPORTEMENTALES = {"controle", "action", "etapes", "increment", "verification",
                           "algorithme", "detecter", "scanner", "rejeter", "appliquer"}

def _regle_necessite_code(payload: dict) -> bool:
    return bool(_CLES_COMPORTEMENTALES & {str(k).lower() for k in payload})

router = APIRouter(prefix="/savoir", tags=["savoir"])


def _gate_owner(authorization: str | None = Header(default=None)):
    """Route réservée au propriétaire (NEOGEN_OWNER_UNLIMITED=1 ou email owner)."""
    if _quotas._owner_unlimited():
        return
    from routes.deps import _auth
    user = _auth(authorization)
    if _quotas.palier(user) == "enterprise":
        return
    raise HTTPException(status_code=403, detail="Section réservée au propriétaire.")


def _gate_auth(authorization: str | None = Header(default=None)):
    """Route ouverte à tout utilisateur connecté (agit sur SON sac). 401 si non connecté.
    L'owner passe toujours (instance locale ou email maître)."""
    if _quotas._owner_unlimited():
        return None
    from routes.deps import _auth
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Connecte-toi à ton compte pour personnaliser ton interface.")
    return user


@router.get("/etat")
def hub_etat(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    return _savoir.HUB.etat()


@router.get("/reseau")
def reseau_etat(authorization: str | None = Header(default=None)):
    """Etat du reseau d'intelligence distribuee : environnement + file de contribution."""
    _gate_owner(authorization)
    import reseau_savoir as _rs
    return _rs.etat()


@router.post("/reseau/contribuer")
def reseau_contribuer(authorization: str | None = Header(default=None)):
    """Declenche manuellement le cycle de contribution montante (proprietaire)."""
    _gate_owner(authorization)
    import reseau_savoir as _rs
    return _rs.cycle_contribution()


@router.post("/rafraichir")
def hub_rafraichir(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    stats = _savoir.HUB.rafraichir()
    nouvelles = _proposeur.generer()
    return {"ok": True, "grains_par_silo": stats, "nouvelles_propositions": len(nouvelles)}


@router.get("/chercher")
def hub_chercher(
    q: str = Query(..., min_length=1),
    domaine: str | None = Query(default=None),
    k: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
):
    _gate_owner(authorization)
    return _savoir.HUB.chercher(q, domaine=domaine, k=k)


@router.get("/propositions")
def hub_propositions(
    statut: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    _gate_owner(authorization)
    return _savoir.charger_propositions(statut=statut)


@router.post("/propositions/{prop_id}/approuver")
def hub_approuver(prop_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    # Lire la proposition avant approbation pour alimenter l'Ingenieur
    prop = next((p for p in _savoir.charger_propositions() if p.get("id") == prop_id), None)
    res = _proposeur.approuver(prop_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("erreur", "erreur"))
    # L'Ingenieur passe SYSTEMATIQUEMENT sur toute approbation : il decide si du code est requis.
    if prop:
        import ingenieur as _ing
        chg = prop.get("changement", {}) if isinstance(prop.get("changement"), dict) else {}
        titre = chg.get("titre") or prop.get("titre") or ""
        type_ = chg.get("type") or prop.get("type") or ""
        payload = chg.get("payload", {}) if isinstance(chg.get("payload"), dict) else {}
        payload_visible = {k: v for k, v in payload.items() if not k.startswith("_")}
        besoin = (
            f"Une évolution NEOGEN vient d'être approuvée par Jordan : « {titre} » "
            f"(type: {type_}). Détail : {_json.dumps(payload_visible, ensure_ascii=False)[:400]}. "
            f"Décide si cette évolution nécessite une implémentation code pour être vraiment active, "
            f"ou si le stockage JSON suffit. Si du code est requis : forge la cellule et ancre-la "
            f"au bon point du flux. Si le JSON suffit : confirme-le dans ton rapport."
        )
        job_id = _ing.lancer_async(besoin, titre=titre,
                                   pensee_id=res.get("pensee_id") or "")
        res["job_id"] = job_id
    return res


@router.post("/propositions/{prop_id}/refuser")
def hub_refuser(prop_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    res = _proposeur.refuser(prop_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("erreur", "erreur"))
    return res


# ── La Pensee : intelligence collective autonome ────────────────────────────────

@router.get("/pensees")
def pensees_lister(
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    """Archive complete des pensees (tous scores), plus recentes d'abord."""
    _gate_owner(authorization)
    import pensee as _pensee
    return {"etat": _pensee.etat(), "pensees": _pensee.lister(limit=limit)}


@router.get("/pensees/bulles")
def pensees_bulles(authorization: str | None = Header(default=None)):
    """Pensees a haut score non lues -> bulles de notification (polling UI)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return {"bulles": _pensee.bulles_non_lues()}


@router.post("/pensees/{pensee_id}/lue")
def pensees_marquer_lue(pensee_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    import pensee as _pensee
    res = _pensee.marquer_lue(pensee_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail="pensee introuvable")
    return res


@router.post("/pensees/{pensee_id}/archiver")
def pensees_archiver(pensee_id: str, authorization: str | None = Header(default=None)):
    """Archive une pensee (masquee par defaut, visible via filtre 'archivee' dans l'UI)."""
    _gate_owner(authorization)
    import pensee as _pensee
    res = _pensee.marquer_archive(pensee_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail="pensee introuvable")
    return res


@router.post("/pensees/archiver-anciens")
def pensees_archiver_anciens(semaines: int = 1, authorization: str | None = Header(default=None)):
    """Archive les pensees en etat actif/generee depuis plus de N semaines (1 par defaut)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee.archiver_anciens(semaines)


# Types/indices qui demandent du VRAI code (passent par la forge), pas du data-driven.
_TYPES_FORGE = {"fonction", "capacite"}
_INDICES_TECHNIQUES = ("etapes", "code", "action", "scanner", "valider", "reparer",
                       "parser", "detecter", "compiler", "indexer", "automatis",
                       "scann", "analyse", "extrait", "classe ", "refactor", "periodi",
                       "genere un", "rapport", "lecture system", "ses propres modules",
                       "ses modules", "architecture", "surveille", "inspecte")

# Indices qu'une idee concerne l'INTERFACE/experience visuelle.
_INDICES_INTERFACE = ("interface", "affichage", "ecran", "liste", "replier", "repliable",
                      "deroulant", "regrouper", "compact", "densite", "layout", "onglet",
                      "vue", "agrandir", "plus grand", "chat", "scroll", "bloc", "carte",
                      "lisible", "organis", "espace", "colonne", "mise en page")

# Indices d'un SYSTEME BACKEND (registry, pipeline, compose) -> skip forges UI -> VOIE 1/2/3.
_INDICES_SYSTEME_BACKEND = ("registre", "registry", "fossile", "compose_ui", "compose ui",
                             "pipeline", "biblioth", "catalogue", "fragment system",
                             "index de fragment", "index des fragment")

# Indices d'un NOUVEAU COMPOSANT HTML explicite -> forge_fragments (nouveau widget/section).
_INDICES_NOUVEAU_COMPOSANT = ("nouveau panel", "nouvelle section", "nouvelle carte",
                               "carte vivante", "ajouter un onglet", "nouvel onglet",
                               "miroir de", "tableau de bord", "visualis")


_ZONE_KEYWORDS = {
    "cerveau":      ("cerveau", "agent", "memoire", "skill", "savoir", "connaissance"),
    "production":   ("production", "registre", "genealog", "produit", "creation"),
    "compte":       ("compte", "rpa", "ecran", "preference", "secretaire"),
    "analyse":      ("analyse", "analyste", "metrique", "statistique", "pattern"),
    "evolution":    ("evolution", "architecte", "store", "noyau", "changement", "gouverne"),
    "integrations": ("integration", "connecteur", "provider", "api", "fournisseur"),
}

def _zone_depuis_pensee(p: dict) -> str:
    """Detecte la zone forge_fragments la plus pertinente depuis le contenu de la pensee."""
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    for zone, mots in _ZONE_KEYWORDS.items():
        if any(m in blob for m in mots):
            return zone
    return "evolution"  # fallback


def _est_interface(evo: dict | None, p: dict) -> bool:
    """Une pensee concerne l'INTERFACE si son evolution est de type esthetique/section,
    ou si son contenu evoque l'affichage/l'experience visuelle."""
    if isinstance(evo, dict) and (evo.get("type") or "").lower() in ("esthetique", "section", "interface"):
        return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_INTERFACE)


def _est_systeme_backend(evo: dict | None, p: dict) -> bool:
    """Detecte les idees qui visent un SYSTEME BACKEND (registre, pipeline, compose...)
    Ces idees ne passent PAS par les forges UI -> VOIE 1/2/3 vers l'Ingenieur."""
    if isinstance(evo, dict) and (evo.get("type") or "").lower() in ("systeme", "backend", "registre"):
        return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_SYSTEME_BACKEND)


def _est_nouveau_composant(evo: dict | None, p: dict) -> bool:
    """Detecte les idees qui veulent ajouter un NOUVEAU widget/section HTML
    (distinct du CSS pur applique a l'existant)."""
    if isinstance(evo, dict) and (evo.get("type") or "").lower() in ("section", "composant"):
        return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_NOUVEAU_COMPOSANT)


def _est_technique(evo: dict | None, p: dict) -> bool:
    """Une pensee est 'technique' (donc forgeable en code) si son evolution vise une fonction,
    ou si son payload/contenu contient des indices d'action executable."""
    if isinstance(evo, dict):
        if (evo.get("type") or "").lower() in _TYPES_FORGE:
            return True
        payload = evo.get("payload") if isinstance(evo.get("payload"), dict) else {}
        if any(k in payload for k in ("etapes", "code", "action")):
            return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_TECHNIQUES)


@router.post("/pensees/{pensee_id}/donner-vie")
def pensees_donner_vie(pensee_id: str, authorization: str | None = Header(default=None)):
    """Donne vie a une pensee :
      - VOIE 0 (interface) : forge HTML immediate (apercu, pas de consentement requis).
      - Toutes les autres voies -> PROPOSE dans le Hub. L'Ingenieur est lance APRES
        l'approbation de Jordan (hub_approuver). Jamais avant. Une seule execution."""
    _gate_owner(authorization)
    import pensee as _pensee
    import evolution_gouvernee as _evo

    toutes = _pensee.lister(limit=500)
    p = next((x for x in toutes if x.get("id") == pensee_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="pensee introuvable")

    evo = p.get("evolution") if isinstance(p.get("evolution"), dict) else None

    # VOIE 0 : idee d'INTERFACE. Les systemes backend ET les idees techniques (code/analyse)
    # sont EXCLUS ici et tombent en VOIE 1/2/3 vers l'Ingenieur. Technique prime toujours sur interface.
    if _est_interface(evo, p) and not _est_systeme_backend(evo, p) and not _est_technique(evo, p):
        idee = f"{p.get('titre','')}. {p.get('synthese','')}".strip()

        # VOIE 0b : nouveau COMPOSANT HTML explicite -> forge_fragments -> apercu bloc HTML.
        if _est_nouveau_composant(evo, p):
            import forge_fragments as _ff
            zone = _zone_depuis_pensee(p)
            apercu = _ff.generer_apercu(idee, zone)
            if apercu.get("ok"):
                return {"ok": True, "voie": "forge_blocs", "pensee_id": pensee_id,
                        "titre": apercu.get("titre") or p.get("titre", ""),
                        "html": apercu["html"], "zone": zone,
                        "explication": apercu.get("explication", "")}
            return {"ok": False, "voie": "forge_blocs", "raison": apercu.get("raison", "echec")}

        # VOIE 0a (defaut interface) : modification VISUELLE CSS -> forge_interface -> CSS reel.
        # S'applique a l'interface existante via data/ui_overrides.css (hot-reload, aucun rebuild).
        import forge_interface as _fi
        apercu = _fi.generer_apercu(idee)
        if apercu.get("ok"):
            return {"ok": True, "voie": "interface", "pensee_id": pensee_id,
                    "titre": p.get("titre", ""), "css": apercu["css"],
                    "explication": apercu.get("explication", "")}
        return {"ok": False, "voie": "interface", "raison": apercu.get("raison", "echec")}

    # VOIE 1 : technique -> proposition avec besoin encode (Ingenieur lance a l'approbation).
    if _est_technique(evo, p):
        besoin = f"{p.get('titre','')}. {p.get('synthese','')}".strip()
        if evo and isinstance(evo.get("payload"), dict):
            besoin += " Details : " + str(evo["payload"])[:400]
        r = _evo.proposer("idee",
                          {"besoin": besoin, "_voie": "ingenieur", "_pensee_id": pensee_id},
                          titre=p.get("titre", ""), raison=p.get("synthese", ""))
        r["voie"] = "propose"
        return r

    # VOIE 2 : data-driven -> proposition uniquement (Ingenieur lance a l'approbation).
    if evo and evo.get("type") and isinstance(evo.get("payload"), dict):
        payload = dict(evo["payload"])
        payload["_pensee_id"] = pensee_id
        r = _evo.proposer(evo["type"], payload, titre=p.get("titre", ""),
                          raison=evo.get("raison", "") or p.get("synthese", ""))
        r["voie"] = "propose"
        return r

    # VOIE 3 : idee pure -> proposition uniquement (Ingenieur lance a l'approbation).
    r = _evo.proposer(
        "idee",
        {"idee": f"{p.get('titre', '')} : {p.get('synthese', '')}".strip(),
         "_pensee_id": pensee_id},
        titre=p.get("titre", ""), raison=p.get("synthese", ""))
    r["voie"] = "propose"
    try:
        _pensee.marquer_forge(pensee_id, "notee")
    except Exception:
        pass
    return r


@router.get("/pensees/config")
def pensees_config(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee._config()


@router.post("/pensees/config")
def pensees_set_config(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Met a jour mode (eco/fort/mixte), actif (bool), intervalle_min (int)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee._set_config(
        mode=corps.get("mode"),
        actif=corps.get("actif"),
        intervalle_min=corps.get("intervalle_min"),
    )


@router.post("/pensees/cycle")
def pensees_cycle(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Provoque immediatement une session de pensee (proprietaire).
    Optionnel : {"sujet": "..."} -> discussion personnalisee sur ce theme avec les agents."""
    _gate_owner(authorization)
    import pensee as _pensee
    sujet = (corps or {}).get("sujet") if isinstance(corps, dict) else None
    return _pensee.cycle_pensee(force=True, sujet=sujet)


# ── Evolution gouvernee : la super-capacite (s'auto-modifier sans toucher au noyau) ──

def _user_courant(authorization: str | None):
    try:
        from routes.deps import _auth
        return _auth(authorization)
    except Exception:
        return None


@router.get("/evolution/etat")
def evolution_etat(authorization: str | None = Header(default=None)):
    """Noyau (ADN+murs), generation courante, stores forgeables actifs."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return _evo.etat()


@router.delete("/evolution/agents/{cle}")
def evolution_supprimer_agent(cle: str, authorization: str | None = Header(default=None)):
    """Supprime un bébé-agent custom (agents noyau intouchables)."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return _evo.supprimer_agent(cle)


@router.get("/evolution/generation")
def evolution_generation(authorization: str | None = Header(default=None)):
    """Generation NEOGEN courante (1 an) + changelog enrichi des statuts reels."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return {"generation": _evo.generation_courante(), "changelog": _evo.statuts_changelog()}


@router.post("/evolution/generation/nettoyer")
def evolution_nettoyer_doublons(authorization: str | None = Header(default=None)):
    """Supprime les doublons du changelog (1 entree par artefact). Idempotent."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return _evo.nettoyer_doublons_changelog()


@router.post("/evolution/generation/statuts/refresh")
def evolution_statuts_refresh(authorization: str | None = Header(default=None)):
    """Recalcule les statuts réels de toutes les entrées du changelog. Cron journalier."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return {"ok": True, "changelog": _evo.statuts_changelog()}


@router.get("/evolution/types")
def evolution_types(authorization: str | None = Header(default=None)):
    """Types forgeables (perso / systeme) et frontiere du noyau."""
    _gate_owner(authorization)
    import noyau as _noyau
    return _noyau.resume()


@router.post("/evolution/proposer")
def evolution_proposer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Soumet un changement : gardien noyau -> proposition (consentement via /propositions)."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    res = _evo.proposer(
        corps.get("type", ""), corps.get("payload", {}) or {},
        titre=corps.get("titre", ""), raison=corps.get("raison", ""),
        cible=corps.get("cible"), user=_user_courant(authorization),
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


@router.post("/evolution/appliquer")
def evolution_appliquer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Applique directement un changement (admin : le consentement est l'acte d'appel).
    Re-garde par le noyau ; un changement systeme reste refuse pour un non-admin."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    res = _evo.appliquer(corps or {}, user=_user_courant(authorization))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


# ── La Forge : suivi de progression + cellules de code reel generees ─────────────

@router.get("/evolution/forge/{job_id}")
def evolution_forge_statut(job_id: str, authorization: str | None = Header(default=None)):
    """Etat d'avancement d'une forge en cours (polling UI pour la bulle de progression).
    Ouvert à tout user connecté : il poll SA propre forge (job_id aléatoire non devinable)."""
    _gate_auth(authorization)
    import forge_evolution as _forge
    return _forge.statut_job(job_id)


@router.get("/evolution/cellules")
def evolution_cellules(authorization: str | None = Header(default=None)):
    """Liste des cellules de code reel forgees par l'utilisateur (son sac), récentes d'abord.
    Owner → cellules système ; user web → cellules de SON sac (isolé des autres)."""
    _gate_auth(authorization)
    import forge_evolution as _forge
    return {"cellules": _forge.lister_cellules(_user_courant(authorization))}


@router.get("/evolution/cellules/{nom}")
def evolution_cellule(nom: str, authorization: str | None = Header(default=None)):
    """Une cellule forgee AVEC son code Python reel + verdict Membrane + resume du test.
    Lue dans le sac de l'utilisateur (un user ne voit jamais les cellules d'un autre)."""
    _gate_auth(authorization)
    import forge_evolution as _forge
    c = _forge.cellule(nom, _user_courant(authorization))
    if not c:
        raise HTTPException(status_code=404, detail="cellule introuvable")
    return c


# ── L'Ingenieur : patchs de code proposes, autorisations noyau, rebuild ───────────

@router.get("/evolution/ingenieur")
def ingenieur_etat(authorization: str | None = Header(default=None)):
    """Tableau de bord de l'Ingenieur : patchs proposes, autorisations noyau en attente,
    rebuild requis. Alimente le bloc UI dedie."""
    _gate_owner(authorization)
    import outils_dev as _id
    return {
        "patchs": _id.lister_patchs(),
        "autorisations": [a for a in _id.lister_autorisations() if a.get("statut") == "en_attente"],
        "rebuild": _id.etat_rebuild(),
    }


@router.get("/evolution/ingenieur/diagnostic")
def ingenieur_diagnostic(authorization: str | None = Header(default=None)):
    """Diagnostic 360 instantane (sante + coherence + cellules + patchs + rebuild), sans LLM.
    Affiche directement dans la section Ingenieur."""
    _gate_owner(authorization)
    import outils_dev as _id
    return {"diagnostic": _id.outil_diagnostic_ingenieur()}


@router.post("/evolution/ingenieur/tache")
def ingenieur_tache(demande: str = Body(embed=True),
                    authorization: str | None = Header(default=None)):
    """Confie une tache directe a l'Ingenieur (ex: « repare ou supprime la capacite obsolete X »,
    « ajoute telle fonction »). Il diagnostique, code, teste, integre. Renvoie un job_id : l'UI
    poll /evolution/forge/{job_id} (meme bulle de progression)."""
    _gate_owner(authorization)
    if not (demande or "").strip():
        raise HTTPException(status_code=400, detail="demande vide")
    import ingenieur as _ing
    job_id = _ing.lancer_async(demande.strip(), titre=demande.strip()[:60])
    return {"ok": True, "job_id": job_id}


@router.get("/evolution/ingenieur/patch/{pid}")
def ingenieur_patch(pid: str, authorization: str | None = Header(default=None)):
    """Un patch propose AVEC son diff complet (ancien/nouveau) pour revue avant rebuild."""
    _gate_owner(authorization)
    import outils_dev as _id
    p = _id.patch(pid)
    if not p:
        raise HTTPException(status_code=404, detail="patch introuvable")
    return p


@router.post("/evolution/ingenieur/autorisation/{aid}")
def ingenieur_autorisation(aid: str, accordee: bool = Body(embed=True),
                           authorization: str | None = Header(default=None)):
    """Jordan accorde/refuse un patch qui touche le NOYAU (le mur). Trace la decision ;
    l'application reelle du patch noyau reste manuelle (Claude Code + rebuild)."""
    _gate_owner(authorization)
    import outils_dev as _id
    r = _id.decider_autorisation(aid, accordee)
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("raison", "introuvable"))
    return r


@router.post("/evolution/ingenieur/rebuild-fait")
def ingenieur_rebuild_fait(authorization: str | None = Header(default=None)):
    """Marque le rebuild comme effectue (efface le badge UI). A appeler apres
    'docker compose up -d --build'."""
    _gate_owner(authorization)
    import outils_dev as _id
    return _id.marquer_rebuild_fait()


@router.get("/evolution/ingenieur/decisions")
def ingenieur_decisions(authorization: str | None = Header(default=None)):
    """Decisions bloquantes en attente : l'Ingenieur s'est arrete (securite/irreversible) et
    attend une reponse de Jordan (bouton d'option ou texte libre). Alimente la bulle UI."""
    _gate_owner(authorization)
    import ingenieur as _ing
    return {"decisions": _ing.lister_decisions_en_attente()}


@router.post("/evolution/ingenieur/decisions/{job_id}/repondre")
def ingenieur_repondre_decision(job_id: str, reponse: str = Body(embed=True),
                                authorization: str | None = Header(default=None)):
    """Jordan repond a une decision en attente : relance l'Ingenieur avec sa reponse injectee."""
    _gate_owner(authorization)
    import ingenieur as _ing
    r = _ing.repondre_decision(job_id, reponse)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("raison", "echec"))
    return r


# ── Conscience du systeme : ce que NEOGEN sait de lui-meme ────────────────────────

@router.get("/conscience")
def conscience_etat(authorization: str | None = Header(default=None)):
    """Vue d'auto-connaissance : etat global (sante %) + liste des capacites avec statut reel."""
    _gate_owner(authorization)
    import conscience as _c
    return {"etat": _c.etat_systeme(), "capacites": _c.lister()}


@router.post("/conscience/diagnostiquer")
def conscience_diagnostiquer(authorization: str | None = Header(default=None)):
    """Le systeme se regarde lui-meme : reconcilie le registre avec la realite
    (cellules verifiees, regles sans code, tensions) et met a jour chaque statut."""
    _gate_owner(authorization)
    import conscience as _c
    return _c.diagnostiquer()


@router.post("/conscience/{id}/reparer")
def conscience_reparer(id: str, authorization: str | None = Header(default=None)):
    """Relance la forge sur une capacite a_reparer/echouee, avec le contexte d'echec injecte.
    Renvoie {ok, job_id} -> l'UI poll /evolution/forge/{job_id} comme une forge normale."""
    _gate_owner(authorization)
    import conscience as _c
    r = _c.reparer(id)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("raison", "reparation impossible"))
    return r


@router.get("/conscience/ancrages")
def conscience_ancrages(authorization: str | None = Header(default=None)):
    """Catalogue des points d'ancrage (ou une cellule peut s'auto-declencher dans le flux)."""
    _gate_owner(authorization)
    import capacites_forgees as _cf
    return {"ancrages": _cf.ANCRAGES}


@router.post("/conscience/{id}/ancrage")
def conscience_ancrage(id: str, corps: dict = Body(default={}),
                       authorization: str | None = Header(default=None)):
    """Assigne le point d'ancrage d'une cellule (auto-cablage) : ou elle s'execute toute seule."""
    _gate_owner(authorization)
    import capacites_forgees as _cf
    r = _cf.definir_ancrage(id, (corps or {}).get("point", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("raison", "ancrage impossible"))
    return r


@router.post("/conscience/auto-reparer")
def conscience_auto_reparer(authorization: str | None = Header(default=None)):
    """Relance la forge sur toutes les capacites a_reparer/echouee (garde anti-boucle)."""
    _gate_owner(authorization)
    import conscience as _c
    return _c.auto_reparer()


@router.post("/conscience/controle-sante")
def conscience_controle_sante(authorization: str | None = Header(default=None)):
    """Re-verifie chaque capacite integree (test de non-regression) et met a jour les statuts."""
    _gate_owner(authorization)
    import conscience as _c
    return _c.controle_sante()


# ── Resolveur d'objectif : les 3 etats appliques a toute demande ───────────────────

@router.post("/objectif/analyser")
def objectif_analyser(corps: dict = Body(default={}), authorization: str | None = Header(default=None)):
    """Analyse un objectif -> classe chaque element en CERTAIN/INCONNU/ANGLE_MORT (sans agir)."""
    _gate_owner(authorization)
    import resolveur as _r
    r = _r.analyser((corps or {}).get("objectif", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("raison", "analyse impossible"))
    return r


@router.post("/objectif/resoudre")
def objectif_resoudre(corps: dict = Body(default={}), authorization: str | None = Header(default=None)):
    """Analyse PUIS agit : forge les INCONNUS, collecte questions + donnees sensibles a demander."""
    _gate_owner(authorization)
    import resolveur as _r
    c = corps or {}
    r = _r.resoudre(c.get("objectif", ""), auto_forge=bool(c.get("auto_forge", True)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("raison", "resolution impossible"))
    return r


@router.get("/objectif")
def objectif_lister(authorization: str | None = Header(default=None)):
    """Liste des objectifs en cours de resolution (plus recents d'abord)."""
    _gate_owner(authorization)
    import resolveur as _r
    return {"objectifs": _r.lister_objectifs()}


# ── Subconscient : le reve de NEOGEN (bisociation + novelty search) ────────────────

@router.get("/reves")
def reves_lister(authorization: str | None = Header(default=None)):
    """Reves archives + etat du graphe associatif (la memoire ou le reve circule)."""
    _gate_owner(authorization)
    import subconscient as _s
    return {"reves": _s.lister_reves(), "etat": _s.etat()}


@router.post("/reves/rever")
def reves_rever(corps: dict = Body(default={}), authorization: str | None = Header(default=None)):
    """Declenche un cycle de reve a la demande (sinon il tourne la nuit dans la maintenance).
    Les reves nouveaux remontent en bulle (pensee type « reve »)."""
    _gate_owner(authorization)
    import subconscient as _s
    n = int((corps or {}).get("n", 3) or 3)
    return _s.cycle_reve(n=max(1, min(8, n)))


# ── Forge d'interface : l'override CSS reel applique a l'ecran (admin) ────────────

@router.get("/evolution/ui.css")
def evolution_ui_css(authorization: str | None = Header(default=None)):
    """Sert l'override CSS d'interface de l'utilisateur connecté (son sac) ou du maître.
    Pas de gate : c'est du CSS d'apparence ; mais lit le user pour servir SON CSS isolé.
    Le CSS s'applique dans le navigateur uniquement — jamais une donnée sensible."""
    import forge_interface as _fi
    return Response(content=_fi.overrides_actuels(_user_courant(authorization)),
                    media_type="text/css")


@router.post("/evolution/ui/appliquer")
def evolution_ui_appliquer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Applique le CSS à l'interface de l'utilisateur : maître (owner) ou son sac (user web).
    Ouvert à tout utilisateur connecté — le CSS est assaini et n'affecte que SON navigateur."""
    _gate_auth(authorization)
    import forge_interface as _fi
    res = _fi.appliquer((corps or {}).get("css", ""), user=_user_courant(authorization),
                        titre=(corps or {}).get("titre", ""))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


@router.post("/evolution/ui/reset")
def evolution_ui_reset(authorization: str | None = Header(default=None)):
    """Reinitialise l'interface de l'utilisateur : retour a l'apparence d'origine (reversibilite).
    Chaque user ne réinitialise que SON sac ; l'owner réinitialise le maître."""
    _gate_auth(authorization)
    import forge_interface as _fi
    return _fi.reinitialiser(_user_courant(authorization))


# ── Forge de fragments : de VRAIS blocs HTML/CSS injectes a l'ecran (proprio) ─────

@router.get("/fragments")
def fragments_lister(authorization: str | None = Header(default=None)):
    """Tous les fragments forges, par zone (metadonnees pour l'UI de pilotage)."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    return {"zones": list(_ff.ZONES.items()), "fragments": _ff.lister()}


@router.get("/fragments/{zone}/{frag_id}")
def fragments_un(zone: str, frag_id: str, authorization: str | None = Header(default=None)):
    """Un fragment complet (avec son HTML) pour previsualisation/edition."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    f = _ff.fragment(zone, frag_id)
    if not f:
        raise HTTPException(status_code=404, detail="fragment introuvable")
    return f


@router.post("/fragments/apercu")
def fragments_apercu(corps: dict = Body(default={}),
                     authorization: str | None = Header(default=None)):
    """Genere un apercu de fragment a partir d'une idee {idee, zone} (NON applique)."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    res = _ff.generer_apercu((corps or {}).get("idee", ""), (corps or {}).get("zone", ""))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "echec"))
    return res


@router.post("/fragments/appliquer")
def fragments_appliquer(corps: dict = Body(default={}),
                        authorization: str | None = Header(default=None)):
    """Applique un fragment {html, zone, titre, frag_id?} (proprio) ou le remonte (public)."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    c = corps or {}
    res = _ff.appliquer(c.get("html", ""), c.get("zone", ""), titre=c.get("titre", ""),
                        user=_user_courant(authorization), frag_id=c.get("frag_id"))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "echec"))
    return res


@router.post("/fragments/{zone}/{frag_id}/basculer")
def fragments_basculer(zone: str, frag_id: str, authorization: str | None = Header(default=None)):
    """Active/desactive un fragment sans le supprimer (reversibilite douce)."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    res = _ff.basculer(zone, frag_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("raison", "introuvable"))
    return res


@router.post("/fragments/{zone}/{frag_id}/supprimer")
def fragments_supprimer(zone: str, frag_id: str, authorization: str | None = Header(default=None)):
    """Retire un fragment definitivement (rollback instantane, pas de restart)."""
    _gate_owner(authorization)
    import forge_fragments as _ff
    res = _ff.supprimer(zone, frag_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("raison", "introuvable"))
    return res


# ── Forge UI Python : graver de VRAIS blocs dans le CODE (permanent, git, proprio) ─

@router.get("/ui-python")
def ui_python_etat(authorization: str | None = Header(default=None)):
    """Blocs permanents graves + backups disponibles."""
    _gate_owner(authorization)
    import forge_ui_python as _fup
    return {"blocs": _fup.blocs(), "backups": _fup.lister_backups()}


@router.post("/ui-python/graver")
def ui_python_graver(corps: dict = Body(default={}),
                     authorization: str | None = Header(default=None)):
    """Grave un bloc permanent {zone, html, titre} dans le code (backup + compile + rollback)."""
    _gate_owner(authorization)
    import forge_ui_python as _fup
    c = corps or {}
    res = _fup.graver(c.get("zone", ""), c.get("html", ""), titre=c.get("titre", ""),
                      user=_user_courant(authorization))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "echec"))
    return res


@router.post("/ui-python/retirer")
def ui_python_retirer(corps: dict = Body(default={}),
                      authorization: str | None = Header(default=None)):
    """Retire le bloc permanent d'une zone {zone} (backup + rollback)."""
    _gate_owner(authorization)
    import forge_ui_python as _fup
    res = _fup.retirer((corps or {}).get("zone", ""), user=_user_courant(authorization))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "echec"))
    return res


@router.post("/ui-python/restaurer")
def ui_python_restaurer(corps: dict = Body(default={}),
                        authorization: str | None = Header(default=None)):
    """Restaure un backup de ui_custom.py {backup_id} (rollback manuel)."""
    _gate_owner(authorization)
    import forge_ui_python as _fup
    res = _fup.restaurer((corps or {}).get("backup_id", ""))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "echec"))
    return res


# ── Point d'entree forge utilisateur web ─────────────────────────────────────────

@router.post("/evolution/mon-skill")
def mon_skill_forger(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
    x_llm_key: str | None = Header(default=None),
    x_llm_provider: str | None = Header(default=None),
    x_llm_model: str | None = Header(default=None),
    x_llm_base: str | None = Header(default=None),
):
    """Lance la forge d'un skill dans le sac de l'utilisateur (tout user connecte).
    BYOK obligatoire — la forge consomme des tokens LLM (clé dans les Integrations).
    Quota creation_app_forge : gratuit=0, essential=15/mois, pro=50/mois.
    L'owner passe toujours (enterprise, cle systeme)."""
    from routes.deps import _exiger_byok, _verifier_quota
    from gateway import contexte_depuis_headers

    # 1. Auth : 401 si non connecte, owner passe
    _gate_auth(authorization)

    # 2. Quota (owner enterprise = illimite)
    _verifier_quota(authorization, "creation_app_forge")

    # 3. BYOK : la forge consomme des tokens
    ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(ctx)

    c = corps or {}
    besoin = (c.get("besoin") or "").strip()
    titre = (c.get("titre") or besoin[:60]).strip()
    if not besoin:
        raise HTTPException(status_code=400, detail="besoin vide")

    import forge_evolution as _forge
    byok_key = ctx.api_key if ctx else None
    _u = _user_courant(authorization)
    job_id = _forge.lancer_forge_async(
        besoin, titre=titre,
        user=_u,
        byok_key=byok_key,
    )
    # Comptabilise la forge lancee (applique la limite mensuelle des paliers payants).
    # Owner/enterprise : limite None => jamais bloque, l'increment reste sans effet.
    try:
        import quotas as _quotas
        if _u and _u.get("id"):
            _quotas.incrementer(_u["id"], "creation_app_forge")
    except Exception:
        pass
    return {"ok": True, "job_id": job_id, "voie": "forge_sac"}


# ── Garde-fou de compatibilité : version noyau vs cellules forgées ───────────────

@router.get("/evolution/compatibilite")
def evolution_compatibilite(
    forcer: bool = False,
    authorization: str | None = Header(default=None),
):
    """Scan de compatibilité : vérifie que les cellules forgées compilent toujours
    après une mise à jour du noyau. Retourne le rapport + les cellules à_reverifier."""
    _gate_owner(authorization)
    import version_guard as _vg
    return _vg.scanner(forcer=forcer)


@router.get("/evolution/compatibilite/rapport")
def evolution_compatibilite_rapport(authorization: str | None = Header(default=None)):
    """Dernier rapport de scan sans relancer le scan (lecture seule)."""
    _gate_owner(authorization)
    import version_guard as _vg
    rapport = _vg.dernier_rapport()
    if rapport is None:
        return {"ts": None, "version": None, "total": 0, "ok": 0, "ko": 0, "cellules": {}}
    return rapport
