"""
NEOGEN - Evolution gouvernee : l'application se modifie elle-meme, sans toucher au noyau.

C'est le LEVIER que la Pensee (ou un utilisateur, ou la telemetrie) peut actionner AVEC
CONSENTEMENT. NEOGEN devient vraiment modulable et personnalisable : il peut ajouter des
fonctions, skills, capacites, esthetique, sections, agents (bebe-agents), savoir, modeles
IA, integrations, idees, lois, regles... TOUT en respectant l'ADN, les murs et la securite.

COMMENT c'est sur : tout changement est DATA-DRIVEN. Le code Python du noyau (murs,
gouvernance, isolation, auth) n'est JAMAIS reecrit. NEOGEN « modifie son code » en
alimentant des stores runtime (data/*.json) que le code immuable lit. Chaque changement
passe par `noyau.autoriser()` (fail-closed) PUIS par le consentement humain.

PRIVILEGES (reutilise quotas) :
  - ADMIN (proprietaire) : super-capacite COMPLETE. Reforme l'app reelle, propage au public.
  - PUBLIC : super-capacite BRIDEE. Changements PERSO en local ; un changement SYSTEME
    (qui reformerait l'app reelle) remonte en proposition d'evolution (+ telemetrie).

GENERATIONS : une generation NEOGEN dure 1 AN. Chaque changement applique est NOTIFIE au
changelog de la generation courante (pas une generation par changement). Echeance annuelle
-> nouvelle generation. (Regle Jordan, 2026-06-26.)

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import json
import os
import time

import robustesse as rob
import noyau
import user_namespace as _ns

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")

# Stores data-driven (le code immuable les lit ; l'evolution les alimente).
_STORES = {
    "regle":       "regles_actives.json",
    "loi":         "regles_actives.json",
    "idee":        "regles_actives.json",
    "agent":       "agents_custom.json",
    "modele":      "modeles_custom.json",
    "esthetique":  "esthetique_custom.json",
    "section":     "sections_custom.json",
    "integration": "integrations_custom.json",
}
_LEDGER = os.path.join(_DATA, "evolutions.jsonl")
_GENERATIONS = os.path.join(_DATA, "generations_neogen.json")

DUREE_GENERATION_S = 365 * 86400  # une generation = 1 an


# ── I/O stores generiques ───────────────────────────────────────────────────────

def _chemin(fichier: str) -> str:
    return os.path.join(_DATA, fichier)


def _charger(fichier: str, defaut):
    p = _chemin(fichier)
    if not os.path.exists(p):
        return defaut
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defaut


def _sauver(fichier: str, data) -> None:
    os.makedirs(_DATA, exist_ok=True)
    with open(_chemin(fichier), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── I/O user-aware (sac per-user ou base data/) ────────────────────────────────

def _chemin_user(user, fichier: str) -> str:
    """Chemin effectif : sac de l'utilisateur si web, sinon base data/."""
    if _ns.a_un_sac(user):
        return _ns.data_path(user, fichier)
    return _chemin(fichier)


def _charger_user(user, fichier: str, defaut):
    p = _chemin_user(user, fichier)
    if not os.path.exists(p):
        return defaut
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defaut


def _sauver_user(user, fichier: str, data) -> None:
    p = _chemin_user(user, fichier)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Accesseurs pour les consommateurs runtime (code immuable qui LIT les stores) ──

def regles_actives(user=None) -> dict:
    """Regles/lois/idees actives. Pour un user web, lit depuis son sac (isolation totale)."""
    defaut = {"regles": {}, "lois": [], "idees": []}
    if _ns.a_un_sac(user):
        return _charger_user(user, "regles_actives.json", defaut)
    return _charger("regles_actives.json", defaut)


def profils_custom(user=None) -> dict:
    """Bebe-agents crees par evolution. Pour un user web, lit depuis son sac."""
    if _ns.a_un_sac(user):
        return _charger_user(user, "agents_custom.json", {})
    return _charger("agents_custom.json", {})


def modeles_custom() -> dict:
    """Modeles IA ajoutes. {provider: {fort, moyen, leger, base_url?}}. gateway les fusionne."""
    return _charger("modeles_custom.json", {})


def store_custom(type_: str) -> dict:
    """Acces generique a un store (esthetique/section/integration...)."""
    fichier = _STORES.get(type_)
    return _charger(fichier, {}) if fichier else {}


# ── Generations (1 an) ────────────────────────────────────────────────────────

def generation_courante() -> dict:
    """Generation active. Cree la gen 1 si absente ; ouvre la suivante a l'echeance annuelle."""
    gens = _charger("generations_neogen.json", None)
    now = time.time()
    if not gens or not isinstance(gens, dict) or "courante" not in gens:
        gens = {"courante": {"numero": 1, "ouverte_le": now, "changelog": []}, "historique": []}
        _sauver("generations_neogen.json", gens)
        return gens["courante"]
    cur = gens["courante"]
    if now - float(cur.get("ouverte_le", now)) >= DUREE_GENERATION_S:
        gens["historique"].append(cur)
        cur = {"numero": int(cur.get("numero", 1)) + 1, "ouverte_le": now, "changelog": []}
        gens["courante"] = cur
        _sauver("generations_neogen.json", gens)
        rob.journaliser(f"nouvelle generation NEOGEN ouverte : v{cur['numero']}", "info",
                        source="evolution_gouvernee")
    return cur


def _notifier_generation(type_: str, titre: str, detail: str, cle: str = "") -> None:
    """Notifie un changement applique au changelog de la generation courante.
    Deduplication par (type, cle) si cle non vide, sinon par (type, titre).
    Coherence : 1 entree max par artefact identifiable. Ne leve jamais."""
    gens = _charger("generations_neogen.json", None) or {
        "courante": {"numero": 1, "ouverte_le": time.time(), "changelog": []}, "historique": []}
    generation_courante()
    gens = _charger("generations_neogen.json", None)
    changelog = gens["courante"].setdefault("changelog", [])
    # Deduplication : (type, cle) si cle present, sinon (type, titre normalisé).
    def _match(e):
        if cle:
            return e.get("type") == type_ and e.get("cle") == cle
        return e.get("type") == type_ and e.get("titre", "").strip() == titre.strip()[:120]
    for entree in changelog:
        if _match(entree):
            entree["ts"] = time.time()
            entree["titre"] = titre[:120]
            entree["detail"] = detail[:300]
            if cle:
                entree["cle"] = cle
            _sauver("generations_neogen.json", gens)
            return
    changelog.append({
        "ts": time.time(), "type": type_, "cle": cle, "titre": titre[:120], "detail": detail[:300]})
    _sauver("generations_neogen.json", gens)


def nettoyer_doublons_changelog() -> dict:
    """Supprime les doublons existants dans le changelog : garde la version la plus recente
    par (type, titre normalisé). Idempotent. Retourne {supprimés, restants}."""
    gens = _charger("generations_neogen.json", None)
    if not gens:
        return {"ok": False, "raison": "pas de generations"}
    changelog = gens.get("courante", {}).get("changelog", [])
    vus: dict[tuple, dict] = {}
    for e in sorted(changelog, key=lambda x: x.get("ts", 0)):
        cle = e.get("cle", "").strip()
        if cle:
            key = (e.get("type", ""), cle)
        else:
            key = (e.get("type", ""), e.get("titre", "").strip()[:80])
        vus[key] = e  # ecrase -> garde le plus recent
    propre = list(vus.values())
    avant = len(changelog)
    apres = len(propre)
    gens["courante"]["changelog"] = propre
    _sauver("generations_neogen.json", gens)
    return {"ok": True, "avant": avant, "apres": apres, "supprimes": avant - apres}


# ── Proposer un changement (passe par le gardien + le consentement) ──────────────

def proposer(type_: str, payload: dict, *, titre: str = "", raison: str = "",
             cible: str | None = None, user: dict | None = None) -> dict:
    """Soumet un changement : gardien noyau -> proposition (consentement humain).
    Renvoie {ok, prop_id?, refuse?, raison, portee}. Ne leve jamais."""
    changement = {"type": (type_ or "").strip().lower(), "payload": payload or {},
                  "titre": titre or "", "raison": raison or "", "cible": cible or ""}
    # Tâche 4 : taguer le scope utilisateur pour traçabilité
    if _ns.a_un_sac(user):
        changement["scope"] = f"user:{_ns.sac_id(user)}"
    ok, motif = noyau.autoriser(changement)
    if not ok:
        rob.journaliser(f"evolution refusee par le noyau : {motif} ({titre})", "alerte",
                        source="evolution_gouvernee")
        return {"ok": False, "refuse": True, "raison": motif, "portee": None}

    # Garde-fou de contenu (injection/jailbreak/HTML dangereux) pour toute proposition
    # venant d'un utilisateur web (sac). Le proprietaire garde son flux inchange : il est
    # la source de confiance du contenu, ce garde ne s'applique jamais a son propre flux.
    if _ns.a_un_sac(user):
        sain, motif_payload = noyau.payload_sain(changement["type"], changement["payload"])
        if not sain:
            rob.journaliser(f"evolution refusee (payload public) : {motif_payload} ({titre})",
                            "alerte", source="evolution_gouvernee")
            return {"ok": False, "refuse": True, "raison": motif_payload, "portee": None}

    p = noyau.portee(changement["type"], user)
    changement["portee"] = p
    try:
        import proposeur_hub
        res = proposeur_hub.proposer_depuis_evolution(changement)
        return {"ok": True, "prop_id": res.get("id"), "deja": res.get("deja", False),
                "portee": p, "raison": "propose (en attente de consentement)"}
    except Exception as e:
        rob.journaliser(f"evolution : proposition non creee : {e}", "erreur",
                        source="evolution_gouvernee")
        return {"ok": False, "raison": str(e), "portee": p}


# ── Appliquer un changement (sur consentement / approbation) ─────────────────────

def appliquer(changement: dict, user: dict | None = None) -> dict:
    """Applique un changement APRES consentement. Re-verifie le gardien (defense en
    profondeur), applique le bridage admin/public, mute le store data-driven, notifie la
    generation. NE LEVE JAMAIS."""
    with rob.garde("appliquer evolution", source="evolution_gouvernee"):
        ok, motif = noyau.autoriser(changement)
        if not ok:
            return {"ok": False, "raison": motif}

        type_ = changement["type"]
        p = noyau.portee(type_, user)
        # Bridage : un non-admin ne peut PAS appliquer un changement systeme au live.
        if p == "remonte":
            return {"ok": False, "raison": "changement systeme reserve a l'admin (remonte en proposition)"}

        payload = changement.get("payload", {}) if isinstance(changement.get("payload"), dict) else {}
        titre = changement.get("titre", "") or type_

        detail = _dispatch(type_, payload, titre, user=user)
        if not detail.get("ok"):
            return detail

        _cle = (payload.get("cle") or payload.get("nom") or
                payload.get("provider") or payload.get("cle_regle") or _slug(titre))
        scope = changement.get("scope", "")
        _ledger_user(user, {"ts": time.time(), "type": type_, "titre": titre, "portee": p,
                             "detail": detail.get("detail", ""), "scope": scope,
                             "par": "admin" if p == "complet" else "public"})
        # Changelog generation + conscience : seulement pour les changements systeme (owner)
        if not _ns.a_un_sac(user):
            _notifier_generation(type_, titre, detail.get("detail", ""), cle=_cle)
            _enregistrer_conscience(type_, _cle, titre, detail.get("detail", ""), payload)
        rob.journaliser(f"evolution appliquee [{type_}] {titre} (portee={p})", "succes",
                        source="evolution_gouvernee")
        return {"ok": True, "type": type_, "portee": p, "detail": detail.get("detail", ""),
                "generation": generation_courante().get("numero")}
    return {"ok": False, "raison": "erreur capturee (voir journal)"}


# Types reellement consommes par du code vivant (donc « integre »), vs simplement « stocke ».
_TYPES_INTEGRES = {"agent", "modele"}          # PROFILS / gateway : actifs immediatement
_TYPES_STOCKES = {"regle", "loi", "idee", "savoir", "skill", "fonction",
                  "esthetique", "section", "integration", "capacite"}


def _enregistrer_conscience(type_: str, cle: str, titre: str, detail: str, payload: dict) -> None:
    """Inscrit l'evolution appliquee dans le registre d'auto-connaissance (conscience).
    Statut « integre » si un consommateur runtime le lit immediatement, sinon « stocke ».
    Une regle qui requiert du code reste « a_reparer » jusqu'a ce qu'une cellule l'implemente.
    Ne leve jamais."""
    try:
        import conscience
        if type_ in _TYPES_INTEGRES:
            statut = "integree"
        elif type_ == "regle" and payload.get("requiert_code"):
            statut = "a_reparer"
        else:
            statut = "stockee"
        store = _STORES.get(type_, "")
        conscience.enregistrer(cle or _slug(titre), type=type_, titre=titre or cle,
                               statut=statut, note=detail[:160], store=store,
                               consomme_par=_consommateurs(type_))
    except Exception:
        pass


def _consommateurs(type_: str) -> list:
    """Qui LIT ce type de store dans le code vivant (pour tracer les vrais liens)."""
    return {
        "regle": ["agent_core._directives_actives", "pensee._charger_fil_contextuel"],
        "loi":   ["agent_core._directives_actives"],
        "idee":  ["agent_core._directives_actives"],
        "agent": ["agent_core.PROFILS"],
        "modele": ["gateway"],
        "savoir": ["memoire_agent", "savoir.HUB"],
        "skill": ["competences"],
        "fonction": ["competences"],
        "integration": ["integ_hub"],
    }.get(type_, [])


def _dispatch(type_: str, payload: dict, titre: str, user=None) -> dict:
    """Route vers l'applicateur data-driven du type. Chaque applicateur n'ecrit QUE dans data/."""
    if type_ in ("regle", "loi", "idee"):
        return _appliquer_regle(type_, payload, titre, user=user)
    if type_ == "skill" or type_ == "fonction":
        return _appliquer_skill(payload, titre)          # skills = monde commun
    if type_ == "agent":
        return _appliquer_agent(payload, titre, user=user)
    if type_ == "modele":
        return _appliquer_modele(payload, titre, user=user)
    if type_ == "savoir":
        return _appliquer_savoir(payload, titre)         # savoir = monde commun
    if type_ in ("esthetique", "section", "integration", "capacite"):
        return _appliquer_store(type_, payload, titre, user=user)
    return {"ok": False, "raison": f"type '{type_}' sans applicateur"}


def _appliquer_regle(type_: str, payload: dict, titre: str, user=None) -> dict:
    defaut = {"regles": {}, "lois": [], "idees": []}
    store = _charger_user(user, "regles_actives.json", defaut)
    if type_ == "regle":
        cle = payload.get("cle") or _slug(titre)
        versions = store.setdefault("versions_regles", {})
        existante = store.setdefault("regles", {}).get(cle)
        v = _bump_version(versions.get(cle)) if existante is not None else "1"
        store["regles"][cle] = payload.get("valeur", payload)
        versions[cle] = v
        action = f"mis a jour v{v}" if existante is not None else f"cree v{v}"
        detail = f"regle '{cle}' {action}"
        if payload.get("requiert_code"):
            store.setdefault("regles_code_requis", {})[cle] = {
                "titre": titre, "cle": cle, "ts": time.time()
            }
    elif type_ == "loi":
        loi = payload.get("loi") or payload.get("texte") or titre
        store.setdefault("lois", [])
        if loi not in store["lois"]:
            store["lois"].append(loi)
            detail = f"loi ajoutee : {loi[:80]}"
        else:
            detail = f"loi deja presente : {loi[:80]}"
    else:  # idee
        idee = payload.get("idee") or payload.get("texte") or titre
        store.setdefault("idees", [])
        if idee not in store["idees"]:
            store["idees"].append(idee)
            detail = f"idee notee : {idee[:80]}"
        else:
            detail = f"idee deja notee : {idee[:80]}"
    _sauver_user(user, "regles_actives.json", store)
    return {"ok": True, "detail": detail}


def _appliquer_skill(payload: dict, titre: str) -> dict:
    try:
        import competences
        nom = payload.get("nom") or titre
        existant = competences.charger(competences._slug(nom))
        sk = competences.creer(
            nom=nom,
            description=payload.get("description", ""),
            instructions=payload.get("instructions", ""),
            outils=payload.get("outils", []),
            auto=False,
        )
        v = sk.get("version", "1")
        action = f"mis a jour v{v}" if existant else f"cree v{v}"
        return {"ok": True, "detail": f"skill '{sk.get('nom')}' {action}"}
    except Exception as e:
        return {"ok": False, "raison": f"creation skill echouee : {e}"}


def _appliquer_agent(payload: dict, titre: str, user=None) -> dict:
    """Bebe-agent : un profil custom. delegue=False TOUJOURS (il ne peut pas orchestrer
    le Cerveau) ; ses outils sont filtres a un sous-ensemble sur (anti-escalade).
    Si la cle existe deja -> mise a jour + bump version. Sinon -> creation v1."""
    profils = profils_custom(user=user)
    cle = payload.get("cle") or _slug(payload.get("nom") or titre)
    outils_surs = {"conseiller", "lister_creations", "genealogie", "lister_skills",
                   "utiliser_skill", "memoriser", "rappeler", "lire_fichier", "creer_rapport",
                   "forger_bloc", "donner_vie", "proposer_conversation",
                   "scanner_tensions", "remonter_alerte", "ancrer_tension",
                   "proposer_evolution", "appeler_agent"}
    outils = [o for o in (payload.get("outils") or []) if o in outils_surs]
    existant = profils.get(cle)
    if existant:
        nouvelle_version = _bump_version(existant.get("version") or "1")
        profils[cle] = {**existant,
                        "titre": (payload.get("titre") or payload.get("nom") or existant.get("titre") or cle)[:80],
                        "tier": payload.get("tier") if payload.get("tier") in ("moyen", "leger") else existant.get("tier", "moyen"),
                        "delegue": False,
                        "outils": outils if outils else existant.get("outils", []),
                        "role": (payload.get("role") or existant.get("role") or "Tu es un agent specialise de NEOGEN.")[:2000],
                        "version": nouvelle_version,
                        "custom": True}
        action = f"mis a jour v{nouvelle_version}"
    else:
        profils[cle] = {
            "titre": (payload.get("titre") or payload.get("nom") or cle)[:80],
            "tier": payload.get("tier") if payload.get("tier") in ("moyen", "leger") else "moyen",
            "delegue": False,
            "outils": outils,
            "role": (payload.get("role") or "Tu es un agent specialise de NEOGEN.")[:2000],
            "version": "1",
            "custom": True,
        }
        action = "cree v1"
    _sauver_user(user, "agents_custom.json", profils)
    # rafraichir_profils = seulement pour les agents systeme (owner) ; les agents per-user
    # sont chargés dynamiquement dans dialoguer() depuis le sac de l'utilisateur.
    if not _ns.a_un_sac(user):
        try:
            import agent_core
            agent_core.rafraichir_profils()
        except Exception:
            pass
    return {"ok": True, "detail": f"bebe-agent '{cle}' {action} (tier {profils[cle]['tier']}, {len(profils[cle]['outils'])} outils surs)"}


def _appliquer_modele(payload: dict, _titre: str, user=None) -> dict:
    modeles = _charger_user(user, "modeles_custom.json", {})
    provider = (payload.get("provider") or "").strip().lower()
    if not provider:
        return {"ok": False, "raison": "provider manquant"}
    existant = modeles.get(provider)
    v = _bump_version(existant.get("version") or "1") if existant else "1"
    modeles[provider] = {
        "fort": payload.get("fort") or payload.get("modele") or "",
        "moyen": payload.get("moyen") or payload.get("modele") or "",
        "leger": payload.get("leger") or payload.get("modele") or "",
        "version": v,
    }
    if payload.get("base_url"):
        modeles[provider]["base_url"] = payload["base_url"]
    _sauver_user(user, "modeles_custom.json", modeles)
    action = f"mis a jour v{v}" if existant else f"cree v{v}"
    return {"ok": True, "detail": f"modele '{provider}' {action} (tiers configures)"}


def _appliquer_savoir(payload: dict, titre: str) -> dict:
    try:
        import memoire_agent
        contenu = payload.get("contenu") or payload.get("texte") or titre
        # Verifier si un souvenir similaire existe (rappel par mots-cles du titre)
        existants = memoire_agent.rappeler(titre[:40], limite=3) if titre else []
        m = memoire_agent.memoriser(f"[Savoir evolution] {contenu}", "fait")
        if existants:
            return {"ok": True, "detail": f"savoir mis a jour v1.1 (souvenir {m.get('id', '?')}, {len(existants)} grain(s) similaire(s) existant) -> nourrit le Hub"}
        return {"ok": True, "detail": f"savoir cree v1 (souvenir {m.get('id', '?')}) -> nourrit le Hub"}
    except Exception as e:
        return {"ok": False, "raison": f"memorisation echouee : {e}"}


def _appliquer_store(type_: str, payload: dict, titre: str, user=None) -> dict:
    """esthetique / section / integration / capacite : enregistre le descripteur data-driven.
    Si la cle existe -> mise a jour + bump version."""
    fichier = _STORES.get(type_)
    if not fichier:
        return {"ok": False, "raison": f"type '{type_}' sans store"}
    store = _charger_user(user, fichier, {})
    cle = payload.get("cle") or _slug(payload.get("nom") or titre)
    existant = store.get(cle)
    v = _bump_version(existant.get("version") if isinstance(existant, dict) else None) if existant is not None else "1"
    store[cle] = {**payload, "version": v}
    action = f"mis a jour v{v}" if existant is not None else f"cree v{v}"
    _sauver_user(user, fichier, store)
    return {"ok": True, "detail": f"{type_} '{cle}' {action} (data-driven)"}


# ── Etat / journal ──────────────────────────────────────────────────────────────

def etat() -> dict:
    gen = generation_courante()
    return {
        "noyau": noyau.resume(),
        "generation": {"numero": gen.get("numero"), "ouverte_le": gen.get("ouverte_le"),
                       "changements_cette_annee": len(gen.get("changelog", []))},
        "stores": {
            "regles": regles_actives(),
            "agents_custom": {k: {"titre": v.get("titre", k), "version": v.get("version", "1"),
                                   "tier": v.get("tier", "moyen"), "outils": v.get("outils", []),
                                   "role": (v.get("role") or "")[:120]}
                              for k, v in profils_custom().items()},
            "modeles_custom": list(modeles_custom().keys()),
            "esthetique": list(store_custom("esthetique").keys()),
            "sections": list(store_custom("section").keys()),
            "integrations": list(store_custom("integration").keys()),
        },
    }


def supprimer_agent(cle: str) -> dict:
    """Supprime un bébé-agent custom par sa clé. Les agents noyau sont intouchables."""
    import agent_core
    if cle in agent_core._PROFILS_NOYAU:
        return {"ok": False, "raison": f"'{cle}' est un agent noyau, il ne peut pas etre supprime"}
    profils = profils_custom()
    if cle not in profils:
        return {"ok": False, "raison": f"agent '{cle}' introuvable"}
    del profils[cle]
    _sauver("agents_custom.json", profils)
    agent_core.rafraichir_profils()
    if cle in agent_core.PROFILS:
        del agent_core.PROFILS[cle]
    # Retire l'entree du changelog (deduplication : 1 entree par artefact, suppression = effacement)
    gens = _charger("generations_neogen.json", None)
    if gens and "courante" in gens:
        gens["courante"]["changelog"] = [
            e for e in gens["courante"].get("changelog", [])
            if not (e.get("type") == "agent" and e.get("cle") == cle)
        ]
        _sauver("generations_neogen.json", gens)
    return {"ok": True, "detail": f"agent '{cle}' supprime"}


def changelog_generation() -> list[dict]:
    gen = generation_courante()
    return sorted(gen.get("changelog", []), key=lambda c: c.get("ts", 0), reverse=True)


def _statut_entree(e: dict) -> str:
    """Vérifie le statut réel d'une entrée du changelog selon son type.
    Retourne : 'actif' | 'erreur' | 'inactif' | 'inconnu'."""
    type_ = e.get("type", "")
    cle = e.get("cle", "").strip()
    titre = e.get("titre", "").strip()
    nom = cle or titre  # identifiant préféré
    try:
        if type_ == "cellule":
            import capacites_forgees as _cf
            import re
            # Extraction du vrai nom depuis detail : "cellule 'auto_fix_line_continuation' forgee..."
            detail = e.get("detail", "")
            m_det = re.search(r"cellule '([^']+)'", detail)
            nom_reel = m_det.group(1) if m_det else nom
            caps = {c["nom"]: c for c in _cf.lister()}
            # Cherche d'abord par nom réel (extrait de detail), puis par slug du titre
            slug = re.sub(r"[^a-z0-9_]+", "_", nom.lower()).strip("_")[:40]
            cap = caps.get(nom_reel) or caps.get(slug) or caps.get(nom)
            if cap:
                return "actif"  # présence dans CAPACITES = chargée en processus = intégrée
            # Cherche aussi dans registre conscience par nom réel puis par slug
            import conscience as _c
            item = _c.obtenir(nom_reel) or _c.obtenir(slug) or _c.obtenir(nom)
            if item:
                s = item.get("statut", "")
                return "actif" if s == "integree" else ("erreur" if s in ("a_reparer", "echouee") else "inactif")
            return "inactif"
        elif type_ in ("interface", "section", "esthetique"):
            return "actif"  # appliqué = actif par définition
        elif type_ == "regle":
            import re as _re
            ra = regles_actives()
            regles = ra.get("regles", {})
            versions = ra.get("versions_regles", {})
            # Extraction du vrai nom depuis detail : "regle 'cristallisation_du_savoir_canon' cree v1"
            detail = e.get("detail", "")
            m_det = _re.search(r"regle '([^']+)'", detail)
            nom_reel = m_det.group(1) if m_det else nom
            # Slugifier le nom pour matcher les clés de règles (ex: "Interdire input()" -> "interdire_input_")
            slug = _re.sub(r"[^a-z0-9]+", "_", nom.lower()).strip("_")[:60]
            if (nom_reel in regles or nom in regles or slug in regles or
                    nom_reel in versions or slug in versions or
                    any(slug in k or k in slug for k in regles)):
                return "actif"
            return "inactif"
        elif type_ == "agent":
            customs = profils_custom()
            return "actif" if nom in customs else "inactif"
        elif type_ == "skill":
            import savoir as _s
            try:
                skills = _s.HUB.chercher(nom, k=10) or []
                return "actif" if skills else "inactif"
            except Exception:
                return "inconnu"
        elif type_ == "modele":
            import gateway
            return "actif" if nom in gateway.TIERS else "inactif"
        elif type_ in ("savoir", "idee", "loi"):
            return "actif"  # appliqué dans le store
    except Exception:
        pass
    return "inconnu"


def statuts_changelog() -> list[dict]:
    """Enrichit le changelog avec le statut réel de chaque entrée.
    Retourne la liste avec champ 'statut_reel' + 'statut_ts'. Ne leve jamais."""
    try:
        cl = changelog_generation()
        now = time.time()
        result = []
        for e in cl:
            enrichi = dict(e)
            try:
                enrichi["statut_reel"] = _statut_entree(e)
            except Exception:
                enrichi["statut_reel"] = "inconnu"
            enrichi["statut_ts"] = now
            result.append(enrichi)
        return result
    except Exception:
        return changelog_generation()


def _ledger(entree: dict) -> None:
    os.makedirs(_DATA, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def _ledger_user(user, entree: dict) -> None:
    """Ledger dans le sac de l'utilisateur, ou ledger global pour le propriétaire."""
    if _ns.a_un_sac(user):
        p = _ns.data_path(user, "evolutions.jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    else:
        _ledger(entree)


def _slug(txt: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "_", (txt or "").lower()).strip("_")
    return s[:40] or "item"


def _bump_version(v: str | None) -> str:
    """'1' -> '1.1' -> '1.2' -> ... (bump mineur) ; None -> '1'."""
    if not v:
        return "1"
    s = str(v).lstrip("v")
    if "." not in s:
        return s + ".1"
    parts = s.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except (ValueError, IndexError):
        return s + ".1"


# ── Auto-verification offline ───────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - EVOLUTION GOUVERNEE : auto-verification (offline)")
    print("=" * 64)
    _DATA = tempfile.mkdtemp()
    _LEDGER = os.path.join(_DATA, "evolutions.jsonl")
    # Redirige conscience vers le temp (le hook _enregistrer_conscience ne doit pas polluer le reel).
    import conscience as _co
    _co._DATA = _DATA
    _co._REGISTRE = os.path.join(_DATA, "registre_capacites.json")

    # 1. Generation 1 creee, 0 changement.
    g = generation_courante()
    assert g["numero"] == 1 and g["changelog"] == [], g
    print("  generation 1 ouverte (1 an) -> OK")

    # 2. Appliquer une regle (data-driven) en admin.
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"
    r = appliquer({"type": "regle", "titre": "Reponse directe",
                   "payload": {"cle": "style_reponse", "valeur": "direct"}})
    assert r["ok"], r
    assert regles_actives()["regles"]["style_reponse"] == "direct"
    print(f"  regle appliquee -> {r['detail']}")

    # 3. Bebe-agent : delegue force a False, outils filtres aux surs.
    r = appliquer({"type": "agent", "titre": "Analyste",
                   "payload": {"nom": "analyste", "tier": "moyen", "delegue": True,
                               "outils": ["conseiller", "controler_ecran", "creer_application"]}})
    assert r["ok"], r
    prof = profils_custom()["analyste"]
    assert prof["delegue"] is False, "anti-escalade : delegue doit etre False"
    assert "controler_ecran" not in prof["outils"] and "conseiller" in prof["outils"], prof
    print(f"  bebe-agent cree, anti-escalade applique -> {r['detail']}")

    # 4. Modele custom ajoute.
    r = appliquer({"type": "modele", "titre": "Groq",
                   "payload": {"provider": "groq", "modele": "llama-3.3-70b"}})
    assert r["ok"] and "groq" in modeles_custom(), r
    print(f"  modele custom ajoute -> {r['detail']}")

    # 5. Changement refuse par le noyau : ne s'applique JAMAIS.
    r = appliquer({"type": "regle", "payload": {"non_root": False}})
    assert not r["ok"], r
    print(f"  changement touchant un mur -> refuse : {r['raison'][:50]}")

    # 6. Bridage public : un type systeme ne s'applique pas pour un non-admin.
    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""
    r = appliquer({"type": "agent", "titre": "x", "payload": {"nom": "x"}}, user=None)
    assert not r["ok"] and "admin" in r["raison"], r
    print("  bridage public : type systeme refuse pour non-admin -> OK")
    # mais un type perso (regle) passe en local bride
    r = appliquer({"type": "regle", "titre": "perso", "payload": {"cle": "theme", "valeur": "clair"}}, user=None)
    assert r["ok"], r
    print("  bridage public : type perso applique en local -> OK")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"

    # 7. Generation : les changements sont notifies au changelog (pas de nouvelle gen).
    cl = changelog_generation()
    assert len(cl) >= 4, f"changelog={len(cl)}"
    assert generation_courante()["numero"] == 1, "toujours gen 1 (annuel)"
    print(f"  changelog generation 1 : {len(cl)} changements notifies (regle annuelle) -> OK")

    # 8. proposer() : garde-fou payload_sain applique UNIQUEMENT pour un user avec sac
    #    (public). Le flux owner (user=None ou sans sac) reste inchange.
    import sys, types as _types
    faux_prop = _types.ModuleType("proposeur_hub")
    faux_prop.proposer_depuis_evolution = lambda chg: {"ok": True, "id": "test", "deja": False}
    sys.modules["proposeur_hub"] = faux_prop

    user_web = {"id": "u_test_evo_public", "email": "public@test.local"}
    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""

    r = proposer("regle", {"valeur": "<script>alert(1)</script>"}, titre="x", user=user_web)
    assert not r["ok"] and r.get("refuse"), r
    print("  proposer() : payload malveillant REFUSE pour un user web -> OK")

    r = proposer("regle", {"valeur": "<script>alert(1)</script>"}, titre="x", user=None)
    assert r["ok"], r
    print("  proposer() : meme payload ACCEPTE pour l'owner (user=None) -> flux inchange, OK")

    r = proposer("regle", {"valeur": "prioriser par urgence"}, titre="x", user=user_web)
    assert r["ok"], r
    print("  proposer() : payload legitime ACCEPTE pour un user web -> OK")

    del os.environ["NEOGEN_OWNER_UNLIMITED"]
    print("=" * 64)
    print("  TOUT VERT : auto-evolution gouvernee, data-driven, noyau intact.")
    print("=" * 64)
