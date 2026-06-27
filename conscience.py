"""
NEOGEN - Conscience du systeme : ce que l'organisme SAIT de lui-meme.

Demande de Jordan : « il faut que le systeme soit au courant des fonctions qu'il installe
en son sein, pour comprendre ce qui fonctionne, ce qui est relie, ce qui est en echec,
ce qui est reparable, ce qui peut etre mis a jour. »

Avant, chaque « donner vie » ecrivait dans son coin (regle dans un JSON, cellule sur disque,
agent dans un store...) sans qu'aucune vue ne dise SI c'est reellement branche. Ce module est
le REGISTRE UNIQUE d'auto-connaissance : une entree par capacite, avec son statut REEL.

  statut :  proposee   -> soumise, en attente
            stockee    -> ecrite dans un store data-driven (lue par un consommateur connu)
            forgee     -> code genere + persiste sur disque, mais pas encore branche en processus
            integree   -> VERIFIEE : chargeable + appelable (vraie porte d'acces ouverte)
            a_reparer  -> devrait fonctionner mais la verification echoue -> candidate a la forge
            echouee    -> la forge/integration a echoue (raison tracee)
            obsolete   -> l'artefact reel a disparu

  diagnostiquer() RECONCILIE le registre avec la REALITE : il regarde les cellules, les regles,
  les outils, les tensions de coherence, et met a jour chaque statut. C'est l'acte par lequel
  le systeme « se regarde lui-meme ». reparer(id) relance la forge sur une capacite cassee.

Robustesse : ne leve jamais ; ecrit uniquement dans data/. Conception : Jordan VINCENT + Claude. 2026-06-27.
"""
from __future__ import annotations

import json
import os
import time

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_REGISTRE = os.path.join(_DATA, "registre_capacites.json")

STATUTS = ("proposee", "stockee", "forgee", "integree", "a_reparer", "echouee", "obsolete")
# Statuts consideres « sains » (la capacite fait reellement quelque chose).
_SAINS = ("stockee", "integree")


# ── I/O ───────────────────────────────────────────────────────────────────────────

def _charger() -> dict:
    try:
        if os.path.exists(_REGISTRE):
            with open(_REGISTRE, encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict) and isinstance(d.get("capacites"), dict):
                    return d
    except Exception:
        pass
    return {"capacites": {}}


def _sauver(data: dict) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(_REGISTRE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Enregistrement / mise a jour ───────────────────────────────────────────────────

def enregistrer(id_: str, *, type: str, titre: str = "", statut: str = "proposee",
                note: str = "", **champs) -> dict:
    """Cree ou met a jour une capacite. Append a l'historique. Ne leve jamais."""
    with rob.garde("conscience.enregistrer", source="conscience"):
        if not id_:
            return {"ok": False, "raison": "id manquant"}
        data = _charger()
        caps = data["capacites"]
        existante = caps.get(id_, {})
        entree = {**existante}
        entree.update({
            "id": id_,
            "type": type or existante.get("type", "?"),
            "titre": titre or existante.get("titre", id_),
            "statut": statut if statut in STATUTS else existante.get("statut", "proposee"),
            "derniere_maj": time.time(),
        })
        if "cree_le" not in entree:
            entree["cree_le"] = time.time()
        for k, v in champs.items():
            entree[k] = v
        hist = existante.get("historique", [])
        if not hist or hist[-1].get("statut") != entree["statut"] or note:
            hist.append({"ts": time.time(), "statut": entree["statut"], "note": note[:200]})
        entree["historique"] = hist[-20:]   # borne
        caps[id_] = entree
        _sauver(data)
        return {"ok": True, "id": id_, "statut": entree["statut"]}
    return {"ok": False, "raison": "erreur capturee"}


def maj_statut(id_: str, statut: str, note: str = "", **champs) -> dict:
    """Raccourci : change le statut d'une capacite existante (ou la cree minimalement)."""
    data = _charger()
    existante = data["capacites"].get(id_, {})
    return enregistrer(id_, type=existante.get("type", "?"),
                       titre=existante.get("titre", id_), statut=statut, note=note, **champs)


def obtenir(id_: str) -> dict | None:
    return _charger()["capacites"].get(id_)


def lister(type: str | None = None, statut: str | None = None) -> list[dict]:
    caps = list(_charger()["capacites"].values())
    if type:
        caps = [c for c in caps if c.get("type") == type]
    if statut:
        caps = [c for c in caps if c.get("statut") == statut]
    return sorted(caps, key=lambda c: c.get("derniere_maj", 0), reverse=True)


def etat_systeme() -> dict:
    """Vue d'ensemble pour l'UI : total, repartition par statut/type, sante (% sain)."""
    caps = list(_charger()["capacites"].values())
    par_statut, par_type = {}, {}
    for c in caps:
        par_statut[c.get("statut", "?")] = par_statut.get(c.get("statut", "?"), 0) + 1
        par_type[c.get("type", "?")] = par_type.get(c.get("type", "?"), 0) + 1
    total = len(caps)
    sains = sum(1 for c in caps if c.get("statut") in _SAINS)
    return {
        "total": total,
        "sains": sains,
        "sante_pct": round(100 * sains / total) if total else 100,
        "par_statut": par_statut,
        "par_type": par_type,
        "a_reparer": [c["id"] for c in caps if c.get("statut") in ("a_reparer", "echouee")],
    }


# ── Diagnostic : reconcilier le registre avec la REALITE ───────────────────────────

def diagnostiquer() -> dict:
    """Le systeme se regarde lui-meme. Pour chaque artefact reel, met a jour son statut :
      - cellules forgees -> verifiees via capacites_forgees (integree / forgee / a_reparer)
      - regles requiert_code sans ancrage -> a_reparer
      - tensions de coherence (outils orphelins, parcours KO) -> signalees
    Renvoie {ok, total, par_statut, changements, a_reparer, tensions}. Ne leve jamais."""
    with rob.garde("conscience.diagnostiquer", source="conscience"):
        changements: list[dict] = []

        # 1. Cellules forgees : verite = le loader capacites_forgees.
        try:
            import capacites_forgees as _cf
            reg_cellules = _cf._charger_registre()
            for nom, meta in reg_cellules.items():
                v = _cf.verifier_integration(nom)
                if v.get("ok"):
                    statut = "integree"
                    note = v.get("signature", "")
                else:
                    integrable, _m = _cf._integrable(meta)
                    # Persistee mais volontairement non chargee (mur) -> 'forgee' (sain sur disque).
                    statut = "forgee" if not integrable else "a_reparer"
                    note = v.get("resume", "")
                avant = (obtenir(nom) or {}).get("statut")
                enregistrer(nom, type="cellule", titre=meta.get("description", nom)[:80],
                            statut=statut, note=note,
                            cellule=nom, fonction=v.get("fonction"),
                            hook_point="capacites_forgees.CAPACITES",
                            consomme_par=["outils.capacite_forgee"],
                            pensee_id=meta.get("pensee_id"))
                if avant != statut:
                    changements.append({"id": nom, "de": avant, "vers": statut})
        except Exception as e:
            rob.journaliser(f"diagnostic cellules : {e}", "erreur", source="conscience")

        # 1b. Fragments d'interface appliques -> capacites 'interface' integrees (vivantes a l'ecran).
        try:
            import json as _json
            frags_path = os.path.join(_DATA, "fragments_ui.json")
            if os.path.exists(frags_path):
                with open(frags_path, encoding="utf-8") as f:
                    frags = _json.load(f)
                for zone, liste in (frags or {}).items():
                    for frag in (liste or []):
                        fid = f"frag:{zone}:{frag.get('id')}"
                        statut = "integree" if frag.get("actif", True) else "obsolete"
                        avant = (obtenir(fid) or {}).get("statut")
                        enregistrer(fid, type="interface", titre=frag.get("titre", fid)[:80],
                                    statut=statut, note=f"fragment zone {zone}",
                                    store="fragments_ui.json", hook_point=f"UI/zone:{zone}",
                                    consomme_par=["ui (injection HTML)"])
                        if avant != statut:
                            changements.append({"id": fid, "de": avant, "vers": statut})
        except Exception as e:
            rob.journaliser(f"diagnostic fragments : {e}", "erreur", source="conscience")

        # 2. Regles requiert_code sans ancrage dans le code -> a_reparer.
        try:
            import coherence_auto as _coh
            for t in _coh._check_regles_code_requis():
                cle = t.get("cle", "")
                if not cle:
                    continue
                avant = (obtenir(cle) or {}).get("statut")
                # Si une cellule d'implementation existe deja et est integree -> ne pas degrader.
                cap = obtenir(cle)
                if cap and cap.get("statut") == "integree":
                    continue
                enregistrer(cle, type="regle", titre=t.get("meta", {}).get("titre", cle)[:80],
                            statut="a_reparer", note="requiert code, aucun ancrage detecte",
                            store="regles_actives.json")
                if avant != "a_reparer":
                    changements.append({"id": cle, "de": avant, "vers": "a_reparer"})
        except Exception as e:
            rob.journaliser(f"diagnostic regles : {e}", "erreur", source="conscience")

        # 3. Tensions de coherence globales (outils orphelins, parcours KO) -> pour info.
        tensions = []
        try:
            import coherence_auto as _coh
            audit = _coh.audit_journeys()
            tensions = audit.get("tensions", [])
        except Exception:
            pass

        etat = etat_systeme()
        rob.journaliser(
            f"diagnostic : {etat['total']} capacites, {len(changements)} changement(s), "
            f"{len(etat['a_reparer'])} a reparer", "info", source="conscience")
        return {"ok": True, "total": etat["total"], "par_statut": etat["par_statut"],
                "sante_pct": etat["sante_pct"], "changements": changements,
                "a_reparer": etat["a_reparer"], "tensions": tensions}
    return {"ok": False, "raison": "erreur capturee"}


# ── Reparation : relancer la forge sur une capacite cassee ─────────────────────────

def reparer(id_: str) -> dict:
    """Relance la forge sur une capacite a_reparer/echouee, en injectant le contexte d'echec.
    Renvoie {ok, job_id?} ou {ok:False, raison}. Ne leve jamais."""
    with rob.garde("conscience.reparer", source="conscience"):
        cap = obtenir(id_)
        if not cap:
            return {"ok": False, "raison": f"capacite '{id_}' inconnue"}
        if cap.get("statut") not in ("a_reparer", "echouee", "forgee"):
            return {"ok": False, "raison": f"statut '{cap.get('statut')}' non reparable"}
        derniere_note = ""
        for h in reversed(cap.get("historique", [])):
            if h.get("note"):
                derniere_note = h["note"]
                break
        besoin = (f"Re-generer l'implementation de la capacite NEOGEN '{cap.get('titre', id_)}' "
                  f"(cle '{id_}', type {cap.get('type')}). "
                  f"La tentative precedente a echoue : {derniere_note or 'integration impossible'}. "
                  f"Generer une fonction Python autonome, testable, sans input()/reseau/suppression, "
                  f"qui retourne un dict. Ne modifier aucun fichier hors de data/.")
        try:
            import forge_evolution
            job_id = forge_evolution.lancer_forge_async(
                besoin, titre=cap.get("titre", id_), pensee_id=cap.get("pensee_id") or "")
            maj_statut(id_, "proposee", note=f"reparation relancee (job {job_id})", job_id=job_id)
            return {"ok": True, "job_id": job_id}
        except Exception as e:
            maj_statut(id_, "echouee", note=f"reparation impossible : {e}")
            return {"ok": False, "raison": str(e)}
    return {"ok": False, "raison": "erreur capturee"}


# ── Auto-reparation : le systeme se soigne seul (garde anti-boucle) ────────────────

_MAX_REPARS = 3   # au-dela, on n'auto-reforge plus (evite la boucle infinie de forge)


def auto_reparer(max_par_passe: int = 3) -> dict:
    """Relance la forge sur les capacites a_reparer/echouee, en bornant : on saute celles
    qui ont deja ete tentees _MAX_REPARS fois (anti-boucle) ou recemment (rob.deja_fait).
    Appele au boot et exposable a la main. Ne leve jamais. Renvoie {relancees, ignorees}."""
    with rob.garde("conscience.auto_reparer", source="conscience"):
        relancees, ignorees = [], []
        for cap in lister():
            if cap.get("statut") not in ("a_reparer", "echouee"):
                continue
            if len(relancees) >= max_par_passe:
                break
            cid = cap.get("id")
            if int(cap.get("tentatives", 0)) >= _MAX_REPARS:
                ignorees.append({"id": cid, "raison": f"{_MAX_REPARS} tentatives atteintes"})
                continue
            sig = f"autorepar:{cid}"
            if rob.deja_fait(sig, ttl_s=3600):   # pas plus d'une auto-reparation/heure/capacite
                ignorees.append({"id": cid, "raison": "deja tentee recemment"})
                continue
            rob.marquer_fait(sig)
            r = reparer(cid)
            (relancees if r.get("ok") else ignorees).append(
                {"id": cid, "job_id": r.get("job_id"), "raison": r.get("raison")})
        if relancees:
            rob.journaliser(f"auto-reparation : {len(relancees)} capacite(s) relancee(s)",
                            "info", source="conscience")
        return {"ok": True, "relancees": relancees, "ignorees": ignorees}
    return {"ok": False, "raison": "erreur capturee"}


# ── Controle de sante : test de non-regression de chaque capacite integree ─────────

def controle_sante() -> dict:
    """Re-verifie chaque capacite 'integree' : se charge-t-elle encore + reste-t-elle
    appelable ? Une capacite qui ne passe plus -> repassee en 'a_reparer'. C'est le test
    de non-regression continu (a lancer en cron). Ne leve jamais. Renvoie {verifiees, regressions}."""
    with rob.garde("conscience.controle_sante", source="conscience"):
        import capacites_forgees as _cf
        regressions = []
        verifiees = 0
        for cap in lister(type="cellule"):
            if cap.get("statut") != "integree":
                continue
            verifiees += 1
            v = _cf.verifier_integration(cap["id"])
            if not v.get("ok"):
                maj_statut(cap["id"], "a_reparer",
                           note=f"regression detectee : {v.get('resume', 'verification echouee')}")
                regressions.append({"id": cap["id"], "raison": v.get("resume")})
        if regressions:
            rob.journaliser(f"controle sante : {len(regressions)} regression(s) detectee(s)",
                            "alerte", source="conscience")
        return {"ok": True, "verifiees": verifiees, "regressions": regressions}
    return {"ok": False, "raison": "erreur capturee"}


# ── Maintenance autonome : cycle periodique diagnostic -> auto-reparation -> sante ─

_MAINTENANCE_LANCEE = False


def cycle_maintenance() -> dict:
    """Un cycle complet de maintenance autonome : le systeme se regarde, se soigne, se teste,
    puis REVE. diagnostiquer() -> controle_sante() -> auto_reparer() -> subconscient.cycle_reve()
    (le sommeil de NEOGEN : consolide la memoire-graphe + fait emerger des idees nouvelles)."""
    diag = diagnostiquer()
    sante = controle_sante()
    repar = auto_reparer()
    reve = {"ok": False, "raison": "subconscient indisponible"}
    try:
        import subconscient
        reve = subconscient.cycle_reve(n=3)
    except Exception as e:
        rob.journaliser(f"cycle maintenance : reve avorte ({e})", "info", source="conscience")
    return {"diagnostic": diag, "sante": sante, "reparation": repar, "reve": reve}


def demarrer_maintenance(intervalle_h: float = 6.0) -> None:
    """Lance un thread daemon qui execute cycle_maintenance() toutes les intervalle_h heures.
    Idempotent (une seule fois). Ne bloque jamais le demarrage. Doctrine planificateur/telegram."""
    global _MAINTENANCE_LANCEE
    if _MAINTENANCE_LANCEE:
        return
    _MAINTENANCE_LANCEE = True
    import threading
    import time as _t

    def _boucle():
        while True:
            _t.sleep(max(600, int(intervalle_h * 3600)))
            with rob.garde("cycle maintenance conscience", source="conscience"):
                cycle_maintenance()

    threading.Thread(target=_boucle, daemon=True).start()
    rob.journaliser(f"maintenance conscience demarree (toutes les {intervalle_h}h)",
                    "info", source="conscience")


# ── Auto-verification offline ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - CONSCIENCE : auto-verification (offline)")
    print("=" * 64)
    _DATA = tempfile.mkdtemp()
    _REGISTRE = os.path.join(_DATA, "registre_capacites.json")

    # 1. Enregistrement + historique.
    r = enregistrer("ma_regle", type="regle", titre="Ma regle", statut="stockee", note="creee")
    assert r["ok"], r
    r = enregistrer("ma_regle", type="regle", titre="Ma regle", statut="integree", note="branchee")
    assert obtenir("ma_regle")["statut"] == "integree"
    assert len(obtenir("ma_regle")["historique"]) == 2
    print("  enregistrer + transitions de statut + historique OK")

    # 2. Capacite cassee -> apparait dans a_reparer.
    enregistrer("cassee", type="cellule", titre="Cassee", statut="a_reparer", note="import KO")
    etat = etat_systeme()
    assert "cassee" in etat["a_reparer"], etat
    assert etat["total"] == 2
    print(f"  etat_systeme : {etat['total']} capacites, sante {etat['sante_pct']}%, "
          f"a_reparer={etat['a_reparer']} OK")

    # 3. Filtres.
    assert len(lister(type="regle")) == 1
    assert len(lister(statut="integree")) == 1
    print("  lister(type/statut) OK")

    # 4. reparer sur statut non reparable -> refus propre.
    rr = reparer("ma_regle")  # integree -> non reparable
    assert not rr["ok"], rr
    print(f"  reparer(integree) -> refus propre ({rr['raison'][:40]}) OK")

    # 5. auto_reparer : relance les a_reparer/echouee (forge mockee), borne anti-boucle.
    # id unique par run : rob.deja_fait persiste hors du dossier temp, on evite la collision.
    import sys as _sys, types as _types, uuid as _uuid
    faux_forge = _types.ModuleType("forge_evolution")
    faux_forge.lancer_forge_async = lambda besoin, titre="", pensee_id="": "job_test_123"
    _sys.modules["forge_evolution"] = faux_forge
    _cid = "cassee_" + _uuid.uuid4().hex[:8]
    enregistrer(_cid, type="cellule", titre="Cassee unique", statut="a_reparer", note="import KO")
    ar = auto_reparer()
    assert ar["ok"] and any(x["id"] == _cid for x in ar["relancees"]), ar
    print(f"  auto_reparer : {len(ar['relancees'])} relancee(s) (forge mockee) OK")
    # La capacite echoue a nouveau (revenue a_reparer) -> 2e passe doit l'IGNORER (garde anti-boucle).
    maj_statut(_cid, "a_reparer", note="echec a nouveau")
    ar2 = auto_reparer()
    assert any(x["id"] == _cid and "recemment" in (x.get("raison") or "")
               for x in ar2["ignorees"]), ar2
    print(f"  auto_reparer : capacite re-cassee ignoree (garde anti-boucle 1/h) OK")

    # 6. controle_sante : une 'integree' dont la verif echoue repasse en a_reparer.
    enregistrer("cell_x", type="cellule", titre="Cell X", statut="integree")
    faux_cf = _types.ModuleType("capacites_forgees")
    faux_cf.verifier_integration = lambda nom: {"ok": False, "resume": "import casse (dep manquante)"}
    _sys.modules["capacites_forgees"] = faux_cf
    cs = controle_sante()
    assert cs["ok"] and any(r["id"] == "cell_x" for r in cs["regressions"]), cs
    assert obtenir("cell_x")["statut"] == "a_reparer"
    print(f"  controle_sante : regression detectee -> 'cell_x' repasse a_reparer OK")

    print("=" * 64)
    print("  TOUT VERT : conscience + auto-reparation bornee + controle de sante (non-regression).")
    print("=" * 64)
