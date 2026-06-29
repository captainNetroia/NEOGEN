"""
NEOGEN - Le Vrai Pont : une idee technique devient du VRAI code, genere, valide, teste.

Probleme resolu : le bouton « Donner vie » routait tout vers le moteur data-driven
(evolution_gouvernee), qui ecrit des descripteurs JSON que presque aucun code ne lit.
Une idee technique (« auto-reparation des continuations de ligne ») finissait donc en
regle morte, sans effet. Ici, une idee technique passe par le VRAI moteur deja present :

  1. generator.generate_cell(besoin, genome)  -> Claude produit une Cell (code Python reel)
  2. executeur_conteneur.executer_en_conteneur -> smoke-test en Docker durci (isolation reelle)
     + analyse statique des effets reels (reseau/suppression) pour une quarantaine honnete
  3. vivarium.Membrane.evaluate              -> quarantaine adversariale + controle des murs
     (fail-closed : toute cellule qui frole un mur est REFUSEE + « necessite revue manuelle »)
  4. si ACCEPTE + test OK -> persiste data/cellules_forgees/{nom}.py + registre ; sinon REFUSE

La forge n'est PAS instantanee (Opus + Docker). Elle tourne donc en TACHE DE FOND, et publie
sa progression dans data/forge_jobs.json (etapes : generation -> test -> validation -> verdict)
pour que l'UI affiche une bulle vivante. L'utilisateur n'est jamais dans le flou.

GARDE-FOUS : noyau.autoriser() fail-closed a l'entree (cible data/ uniquement, jamais le noyau) ;
le code genere est une fonction autonome executee SANS reseau, non-root, read-only, ephemere ;
JAMAIS sur le VPS prod. forger() ne leve jamais.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

import robustesse as rob
import user_namespace as _ns

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_CELLULES_DIR = os.path.join(_DATA, "cellules_forgees")
_REGISTRE = os.path.join(_DATA, "cellules_forgees.json")
_JOBS = os.path.join(_DATA, "forge_jobs.json")


# ── Routage per-utilisateur : owner -> data/ (système) ; user web -> son sac ──────
#   Les cellules de l'OWNER deviennent les capacités réelles de NEOGEN (intégrées,
#   invocables par les agents primordiaux). Celles d'un USER WEB vivent dans son sac,
#   affichées et exécutables dans SON espace, JAMAIS intégrées au registre système
#   (sinon un user prendrait le dessus sur les agents primordiaux — interdit).

def _registre_path(user: dict | None = None) -> str:
    if _ns.a_un_sac(user):
        return _ns.data_path(user, "cellules_forgees.json")
    return _REGISTRE


def _cellules_dir(user: dict | None = None) -> str:
    if _ns.a_un_sac(user):
        return _ns.data_path(user, "cellules_forgees")
    return _CELLULES_DIR
_GENOME = os.path.join(BASE, "genome.json")

# Marqueur imprime par le smoke-test si le module se charge proprement en conteneur.
_MARQUEUR_CHARGE = "___FORGE_CHARGE_OK___"

# Nombre maximal de tentatives generate->test->repare (boucle « jusqu'a ce que ça marche »).
MAX_TENTATIVES = 3

# Etapes lisibles (pour la bulle de progression cote UI).
_ETAPES = {
    "demarre":    "Initialisation…",
    "generation": "Génération du code…",
    "test":       "Test en sandbox isolée…",
    "validation": "Contrôle des murs…",
    "integration": "Intégration au système…",
    "termine":    "Code généré, testé & intégré",
    "refuse":     "Refusé",
}


# ── Suivi de job (data-driven, lu par le polling UI) ─────────────────────────────

def _charger_jobs() -> dict:
    try:
        if os.path.exists(_JOBS):
            with open(_JOBS, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _set_job(job_id: str, **champs) -> None:
    """Met a jour l'etat d'un job. Ne leve jamais. Ajoute l'etape lisible + l'horodatage."""
    try:
        jobs = _charger_jobs()
        job = jobs.get(job_id, {"job_id": job_id})
        job.update(champs)
        if "etape" in champs:
            job["etape_label"] = _ETAPES.get(champs["etape"], champs["etape"])
        job["ts"] = time.time()
        jobs[job_id] = job
        # Purge : ne garder que les 50 jobs les plus recents (anti-gonflement).
        if len(jobs) > 50:
            recents = sorted(jobs.values(), key=lambda j: j.get("ts", 0), reverse=True)[:50]
            jobs = {j["job_id"]: j for j in recents}
        os.makedirs(_DATA, exist_ok=True)
        with open(_JOBS, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def statut_job(job_id: str) -> dict:
    """Etat courant d'un job pour le polling UI. {trouve:false} si inconnu."""
    job = _charger_jobs().get(job_id)
    return job if job else {"trouve": False, "job_id": job_id}


# ── Analyse statique des effets reels (quarantaine honnete) ──────────────────────

_MARQUEURS_RESEAU = ("import socket", "import urllib", "import requests", "import http",
                     "import httpx", "import aiohttp", "urlopen", "import ftplib",
                     "socket.", "requests.", "httpx.", "urllib.")
_MARQUEURS_SUPPRESSION = ("os.remove", "os.unlink", "shutil.rmtree", "os.rmdir",
                          ".unlink(", "shutil.rmdir")
_MARQUEURS_CONFIRM = ("confirm", "input(", "are you sure", "etes-vous sur", "êtes-vous sûr",
                      "confirmation")


def _effets_reels(code: str) -> dict:
    """Detecte par analyse statique ce que le code FAIT vraiment (pas ce qu'il pretend).
    Sert a remplir Cell.actual_effects -> la quarantaine de la Membrane devient reelle :
    si la cellule declare network_access=False mais touche au reseau, divergence detectee."""
    bas = (code or "").lower()
    reseau = any(m in bas for m in _MARQUEURS_RESEAU)
    suppression = any(m in bas for m in ("os.remove", "os.unlink", "shutil.rmtree",
                                         "os.rmdir", ".unlink(", "shutil.rmdir"))
    demande_confirm = any(m in bas for m in _MARQUEURS_CONFIRM)
    return {
        "network_access": reseau,
        "authorized_network": False,          # jamais auto-autorise (fail-closed)
        "deletes_data": suppression,
        "asks_confirmation": demande_confirm,
    }


# ── Smoke-test en conteneur durci ────────────────────────────────────────────────

def _smoke_test(code: str) -> dict:
    """Charge le code en conteneur Docker durci (reseau coupe, non-root, read-only, ephemere).
    Verifie qu'il se charge sans erreur (syntaxe, imports, pas de crash au chargement).
    Docker absent -> repli compile() (validation syntaxique), jamais d'execution non isolee."""
    # Validation syntaxique d'abord (rapide, locale, sans execution).
    try:
        compile(code, "<cellule_forgee>", "exec")
    except SyntaxError as e:
        return {"ok": False, "isole": False, "resume": f"syntaxe invalide : {e}"}

    try:
        import executeur_conteneur as exe
        dispo, info = exe.docker_disponible()
        if not dispo:
            return {"ok": True, "isole": False,
                    "resume": f"syntaxe OK ; sandbox indisponible ({info}) -> compile() seul"}
        harnais = code + f"\nprint('{_MARQUEUR_CHARGE}')\n"
        rc, out, err, _ = exe.executer_en_conteneur(harnais, timeout=20)
        if rc == 0 and _MARQUEUR_CHARGE in (out or ""):
            return {"ok": True, "isole": True, "resume": "charge proprement en conteneur isole"}
        motif = (err or out or f"code retour {rc}").strip().splitlines()
        return {"ok": False, "isole": True,
                "resume": "echec au chargement : " + (motif[-1] if motif else f"rc={rc}")}
    except Exception as e:
        return {"ok": True, "isole": False, "resume": f"syntaxe OK ; sandbox non lancee ({e})"}


# ── Persistance des cellules forgees ─────────────────────────────────────────────

def _charger_registre(user: dict | None = None) -> dict:
    try:
        chemin = _registre_path(user)
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _persister_cellule(cell, score, verdict_raison, test,
                        pensee_id: str = "", pensee_titre: str = "",
                        user: dict | None = None) -> str:
    """Ecrit le code reel + une entree de registre dans le sac de l'utilisateur (ou le
    système pour l'owner). Idempotent (re-forge ecrase proprement)."""
    nom = re.sub(r"[^a-z0-9_]+", "_", (cell.name or "cellule").lower()).strip("_") or "cellule"
    cellules_dir = _cellules_dir(user)
    os.makedirs(cellules_dir, exist_ok=True)
    chemin = os.path.join(cellules_dir, f"{nom}.py")
    entete = (f"# Cellule forgee par NEOGEN — {cell.description}\n"
              f"# Verdict Membrane : {verdict_raison}\n"
              f"# Genere le {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(entete + (cell.code or ""))

    reg = _charger_registre(user)
    reg[nom] = {
        "nom": nom,
        "description": cell.description,
        "score": score,
        "effets_declares": cell.declared_effects,
        "effets_reels": cell.actual_effects,
        "verdict": verdict_raison,
        "test": test,
        "fichier": f"cellules_forgees/{nom}.py",
        "ts": time.time(),
        "pensee_id": pensee_id or None,
        "pensee_titre": pensee_titre or None,
        "scope": _ns.sac_id(user) and f"user:{_ns.sac_id(user)}" or "maitre",
    }
    with open(_registre_path(user), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    return nom


def lister_cellules(user: dict | None = None) -> list[dict]:
    """Cellules forgees (sans le code) de l'utilisateur, plus recentes d'abord, pour l'UI."""
    reg = _charger_registre(user)
    cells = sorted(reg.values(), key=lambda c: c.get("ts", 0), reverse=True)
    return cells


def cellule(nom: str, user: dict | None = None) -> dict | None:
    """Une cellule forgee AVEC son code reel (pour l'affichage deplie), dans le sac du user."""
    reg = _charger_registre(user)
    meta = reg.get(nom)
    if not meta:
        return None
    out = dict(meta)
    chemin = os.path.join(_cellules_dir(user), f"{nom}.py")
    try:
        with open(chemin, encoding="utf-8") as f:
            out["code"] = f.read()
    except Exception:
        out["code"] = ""
    return out


# ── La forge : besoin -> cellule generee, testee, validee ────────────────────────

def _refus_si_mur(cell):
    """Decision d'escalade de la Membrane = fail-closed (decision Jordan 2026-06-26).
    Toute cellule qui frole un mur (reseau / suppression) est refusee + revue manuelle."""
    return (False, "necessite revue manuelle (cellule au contact d'un mur)")


def _integrer(nom: str) -> dict:
    """Branche reellement la cellule persistee dans le systeme (la rend appelable) et
    VERIFIE que ça marche. C'est ce qui transforme 'forgee' (code sur disque) en
    'integree' (vraie porte d'acces ouverte). Ne leve jamais."""
    try:
        import capacites_forgees as cf
        cf.recharger()
        return cf.verifier_integration(nom)
    except Exception as e:
        return {"ok": False, "resume": f"integration impossible : {e}"}


def _besoin_repare(besoin: str, tentative: int, erreur: str, conseil: str = "") -> str:
    """Reinjecte l'erreur de la tentative precedente dans le besoin pour la generation suivante."""
    return (f"{besoin}\n\n[TENTATIVE {tentative} ÉCHOUÉE] {erreur}. "
            f"{conseil or 'Corrige précisément ce problème.'} "
            f"Le code doit être une fonction Python autonome, sans input()/stdin, "
            f"sans accès réseau ni suppression de fichiers, et retourner un dict.")


def forger(besoin: str, *, titre: str = "", pensee_id: str = "", job_id: str = "",
           user: dict | None = None, byok_key: str | None = None) -> dict:
    """Genere une cellule de code reel a partir d'un besoin, la teste, la valide contre les murs.
    Publie sa progression dans le job. NE LEVE JAMAIS. Renvoie un dict de verdict."""
    with rob.garde("forge evolution", source="forge_evolution"):
        # 1. Gardien du noyau (fail-closed) : on ne forge que vers data/, jamais le noyau.
        import noyau
        nom_probable = re.sub(r"[^a-z0-9_]+", "_", (titre or "cellule").lower()).strip("_")[:40]
        _sac = _ns.sac_id(user)
        _cible_rel = (f"data/users/{_sac}/cellules_forgees/{nom_probable or 'cellule'}.py"
                      if _sac else f"data/cellules_forgees/{nom_probable or 'cellule'}.py")
        changement = {"type": "fonction",
                      "cible": _cible_rel,
                      "payload": {"besoin": (besoin or "")[:200]},
                      "titre": titre, "raison": "forge depuis une pensee"}
        ok, motif = noyau.autoriser(changement)
        if not ok:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100, raison=motif)
            rob.journaliser(f"forge refusee par le noyau : {motif}", "alerte", source="forge_evolution")
            return {"ok": False, "etat": "refusee", "raison": motif}

        # Prepare les briques de generation/validation (une seule fois).
        try:
            import generator
            from vivarium import Genome, Ledger, Membrane
            genome = Genome(_GENOME)
        except Exception as e:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison=f"préparation échouée : {e}")
            return {"ok": False, "etat": "refusee", "raison": f"préparation échouée : {e}"}

        # BOUCLE generate -> test -> valide -> repare (jusqu'a ce que ça marche, borne MAX_TENTATIVES).
        # Memoire des forges : injecte les lecons des echecs passes pour eviter de les refaire.
        besoin_courant = besoin
        try:
            import forge_memoire
            besoin_courant = besoin + forge_memoire.conseils_pour(besoin)
        except Exception:
            pass
        derniere_erreur = ""
        cell = decision = raison = score = test = None
        succes = False
        for tentative in range(1, MAX_TENTATIVES + 1):
            pct_base = 10 + (tentative - 1) * 25

            # 2. Generation du vrai code par Claude (besoin enrichi des echecs precedents).
            _set_job(job_id, etat="en_cours", etape="generation", pct=min(pct_base, 90),
                     tentative=tentative, tentatives_max=MAX_TENTATIVES)
            try:
                cell = generator.generate_cell(besoin_courant, genome, origin="forge",
                                               api_key=byok_key)
            except Exception as e:
                derniere_erreur = f"génération échouée : {e}"
                besoin_courant = _besoin_repare(besoin, tentative, derniere_erreur)
                continue

            # 2b. Règle interdire_input : pas de stdin -> on reforge avec consigne explicite.
            if re.search(r'\binput\s*\(|\bsys\.stdin\b|\braw_input\s*\(', cell.code or ""):
                derniere_erreur = "code contient input()/sys.stdin (interdit)"
                besoin_courant = _besoin_repare(
                    besoin, tentative, derniere_erreur,
                    "N'utilise JAMAIS input() ; reçois les données par paramètres de fonction.")
                continue

            # 2c. AUTO-CABLAGE : les cellules ancrees 'avant_validation_code' transforment le
            # code genere AVANT son test (ex: auto-reparation des continuations de ligne).
            # C'est la preuve qu'une capacite forgee AGIT dans le flux, pas seulement sur demande.
            try:
                import capacites_forgees as _cf
                _anc = _cf.executer_ancrage("avant_validation_code", code=cell.code or "")
                _code_repare = _anc.get("contexte", {}).get("code")
                if _code_repare and _code_repare != cell.code:
                    cell.code = _code_repare
            except Exception:
                pass

            # 3. Smoke-test sandbox + effets reels (quarantaine honnete).
            _set_job(job_id, etat="en_cours", etape="test", pct=min(pct_base + 12, 92),
                     tentative=tentative, tentatives_max=MAX_TENTATIVES)
            test = _smoke_test(cell.code or "")
            cell.actual_effects = _effets_reels(cell.code or "")
            if not test.get("ok"):
                derniere_erreur = f"test échoué : {test.get('resume')}"
                besoin_courant = _besoin_repare(besoin, tentative, derniere_erreur)
                continue

            # 4. Membrane : quarantaine adversariale + murs + escalade fail-closed.
            _set_job(job_id, etat="en_cours", etape="validation", pct=min(pct_base + 18, 95),
                     tentative=tentative, tentatives_max=MAX_TENTATIVES)
            try:
                membrane = Membrane(genome, Ledger(), human_decision=_refus_si_mur)
                decision, raison, score = membrane.evaluate(cell)
            except Exception as e:
                derniere_erreur = f"validation échouée : {e}"
                besoin_courant = _besoin_repare(besoin, tentative, derniere_erreur)
                continue
            if decision != "ACCEPTE":
                derniere_erreur = f"murs : {raison}"
                besoin_courant = _besoin_repare(
                    besoin, tentative, derniere_erreur,
                    "Reste loin des murs : aucun accès réseau, aucune suppression de données.")
                continue

            succes = True
            break

        if not succes:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison=derniere_erreur, tentative=MAX_TENTATIVES, tentatives_max=MAX_TENTATIVES)
            rob.journaliser(f"forge : echec apres {MAX_TENTATIVES} tentatives : {derniere_erreur}",
                            "alerte", source="forge_evolution")
            # Capitalise l'echec : la prochaine forge similaire evitera ce piege.
            try:
                import forge_memoire
                forge_memoire.memoriser_echec(besoin, derniere_erreur)
            except Exception:
                pass
            try:
                import conscience
                cid = re.sub(r"[^a-z0-9_]+", "_", (titre or "cellule").lower()).strip("_") or "cellule"
                conscience.enregistrer(cid, type="cellule", titre=titre or cid, statut="echouee",
                                       note=derniere_erreur, pensee_id=pensee_id, tentatives=MAX_TENTATIVES)
            except Exception:
                pass
            return {"ok": False, "etat": "refusee", "raison": derniere_erreur,
                    "tentatives": MAX_TENTATIVES, "test": test}

        # 5. Acceptee + testee -> persiste le code reel dans le sac du user (ou systeme owner).
        nom = _persister_cellule(cell, score, raison, test,
                                 pensee_id=pensee_id, pensee_titre=titre, user=user)

        # 6. INTEGRATION : SEULES les cellules du MAITRE (owner) sont integrees au registre
        #    systeme (capacites reelles de NEOGEN, invocables par les agents primordiaux).
        #    Une cellule d'un USER WEB reste dans SON sac : forgee + affichee, JAMAIS integree
        #    au systeme (garde-fou : un user ne prend jamais le dessus sur les agents primordiaux).
        if _ns.a_un_sac(user):
            statut_final = "forgee"
            integ = {"ok": False, "resume": "cellule du sac utilisateur : reste dans son espace, non integree au systeme"}
            _set_job(job_id, etat=statut_final, etape="termine", pct=100,
                     nom=nom, score=score, verdict=decision, integ=False,
                     tentative=tentative, tentatives_max=MAX_TENTATIVES)
            rob.journaliser(
                f"forge : cellule '{nom}' forgee dans le sac user {_ns.sac_id(user)} (score {score}, "
                f"{tentative} tentative(s), non integree au systeme)", "succes", source="forge_evolution")
            return {"ok": True, "etat": statut_final, "nom": nom, "score": score,
                    "verdict": decision, "raison": raison, "test": test,
                    "integration": integ, "tentatives": tentative}

        # --- OWNER uniquement : integration reelle au systeme ---
        # 6b. INTEGRATION REELLE : branche la cellule + verifie qu'elle est appelable.
        _set_job(job_id, etat="en_cours", etape="integration", pct=97,
                 nom=nom, tentative=tentative, tentatives_max=MAX_TENTATIVES)
        integ = _integrer(nom)
        statut_final = "integree" if integ.get("ok") else "forgee"

        try:
            import evolution_gouvernee
            evolution_gouvernee._notifier_generation(
                "cellule", titre or nom, f"cellule '{nom}' forgee (score {score}) : {cell.description}")
        except Exception:
            pass

        # 7. CONSCIENCE : le systeme sait desormais que cette capacite existe et son statut reel.
        try:
            import conscience
            conscience.enregistrer(
                nom, type="cellule", titre=titre or nom, statut=statut_final,
                note=integ.get("resume", ""), cellule=nom, fonction=integ.get("fonction"),
                signature=integ.get("signature"), score=score, verdict=decision,
                hook_point="capacites_forgees.CAPACITES", consomme_par=["outils.capacite_forgee"],
                pensee_id=pensee_id, tentatives=tentative)
        except Exception:
            pass

        _set_job(job_id, etat=statut_final, etape="termine", pct=100,
                 nom=nom, score=score, verdict=decision, integ=integ.get("ok"),
                 signature=integ.get("signature"), tentative=tentative, tentatives_max=MAX_TENTATIVES)
        rob.journaliser(
            f"forge : cellule '{nom}' {statut_final} (score {score}, {tentative} tentative(s), "
            f"integration={'ok' if integ.get('ok') else 'differee'})", "succes", source="forge_evolution")
        return {"ok": True, "etat": statut_final, "nom": nom, "score": score,
                "verdict": decision, "raison": raison, "test": test,
                "integration": integ, "tentatives": tentative}

    # rob.garde a absorbe une exception -> job en echec propre, jamais de zombie.
    _set_job(job_id, etat="refusee", etape="refuse", pct=100, raison="erreur capturée (voir journal)")
    return {"ok": False, "etat": "refusee", "raison": "erreur capturée (voir journal)"}


def lancer_forge_async(besoin: str, titre: str = "", pensee_id: str = "",
                       user: dict | None = None, byok_key: str | None = None) -> str:
    """Demarre la forge en tache de fond et renvoie un job_id immediatement (pas de blocage HTTP).
    L'UI poll statut_job(job_id) pour afficher la progression. La cellule est forgee dans le
    sac de l'utilisateur (user web) ou le systeme (owner)."""
    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, etat="en_cours", etape="demarre", pct=5,
             pensee_id=pensee_id, titre=titre or besoin[:80])

    def _run():
        try:
            r = forger(besoin, titre=titre, pensee_id=pensee_id, job_id=job_id, user=user,
                       byok_key=byok_key)
            # Marque la pensee source selon le verdict (statut honnete).
            # Note : la pensee est partagee (cerveau primordial) ; seul l'owner marque le statut
            # global. Pour un user web, sa forge n'altere pas l'etat de la pensee commune.
            if pensee_id and not _ns.a_un_sac(user):
                try:
                    import pensee
                    pensee.marquer_forge(pensee_id, "generee" if r.get("ok") else "refusee")
                except Exception:
                    pass
        except Exception:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison="erreur inattendue (voir journal)")

    threading.Thread(target=_run, daemon=True).start()
    return job_id


# ── Auto-verification offline (aucun appel reseau, generator + executeur mockes) ──

if __name__ == "__main__":
    import sys
    import tempfile
    import types

    print("=" * 64)
    print("NEOGEN - FORGE EVOLUTION : auto-verification (offline, sans reseau)")
    print("=" * 64)

    # Rediriger toutes les ecritures vers un dossier temporaire isole.
    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _CELLULES_DIR = os.path.join(_tmp, "cellules_forgees")
    _REGISTRE = os.path.join(_tmp, "cellules_forgees.json")
    _JOBS = os.path.join(_tmp, "forge_jobs.json")

    # Rediriger AUSSI capacites_forgees + conscience vers le temp (integration reelle isolee).
    import capacites_forgees as _cf
    import conscience as _co
    _cf._DATA = _tmp
    _cf._CELLULES_DIR = _CELLULES_DIR
    _cf._REGISTRE = _REGISTRE
    _co._DATA = _tmp
    _co._REGISTRE = os.path.join(_tmp, "registre_capacites.json")

    def _attendre(job, n=80):
        for _ in range(n):
            st = statut_job(job)
            if st.get("etat") in ("integree", "forgee", "generee", "refusee"):
                return st
            time.sleep(0.05)
        return statut_job(job)

    from vivarium import Cell

    # generator factice : renvoie une Cell propre (code sain, aucun effet).
    def _faux_generate(code_propre=True):
        code = ("def executer(donnees=None):\n"
                "    \"\"\"Repare les continuations de ligne.\"\"\"\n"
                "    return {'ok': True}\n") if code_propre else (
                "import socket\n"
                "def executer(donnees=None):\n"
                "    return socket.gethostname()\n")
        def _gen(need, genome, origin="forge"):
            c = Cell(name="reparer_continuations", description="Repare les backslash de continuation",
                     origin=origin,
                     declared_effects={"deletes_data": False, "asks_confirmation": False,
                                       "network_access": False, "authorized_network": False},
                     cursor_scores={"simplicite": 90, "vitesse": 80, "lisibilite": 85})
            c.code = code
            return c
        return _gen

    faux_gen = types.ModuleType("generator")
    faux_gen.generate_cell = _faux_generate(True)
    sys.modules["generator"] = faux_gen

    # executeur_conteneur factice : Docker « absent » -> repli compile() (pas d'exec reseau).
    faux_exe = types.ModuleType("executeur_conteneur")
    faux_exe.docker_disponible = lambda: (False, "docker non lance (test)")
    faux_exe.executer_en_conteneur = lambda code, timeout=20: (0, _MARQUEUR_CHARGE, "", "<test>")
    sys.modules["executeur_conteneur"] = faux_exe

    # 1. Cas propre : ACCEPTE -> code persiste + INTEGRE + connu de la conscience.
    job = lancer_forge_async("Repare les continuations de ligne", titre="Auto-reparation")
    st = _attendre(job)
    assert st["etat"] == "integree", st
    assert lister_cellules(), "la cellule doit etre persistee"
    nom_cell = st["nom"]
    c = cellule(nom_cell)
    assert c and "def executer" in c["code"], c
    # Integration reelle : la cellule est devenue une fonction appelable.
    r_inv = _cf.invoquer(nom_cell)
    assert r_inv["ok"] and r_inv["resultat"] == {"ok": True}, r_inv
    # Conscience : le systeme SAIT que cette capacite est integree.
    cap = _co.obtenir(nom_cell)
    assert cap and cap["statut"] == "integree", cap
    print(f"  cas propre : '{nom_cell}' integree + invocable + connue de la conscience OK")

    # 2. Cas mur : code reseau -> rejete apres {MAX} tentatives, aucune persistance.
    faux_gen.generate_cell = _faux_generate(False)
    n_avant = len(lister_cellules())
    job2 = lancer_forge_async("Recupere le nom d'hote via le reseau", titre="Acces reseau")
    st2 = _attendre(job2)
    assert st2["etat"] == "refusee", st2
    assert len(lister_cellules()) == n_avant, "une cellule au contact d'un mur ne doit pas etre persistee"
    print(f"  cas mur : REJET fail-closed apres {st2.get('tentative')} tentative(s) -> 0 persistance OK")

    # 3. Boucle de reparation : echec a la tentative 1 (syntaxe), succes a la 2.
    _cpt = {"n": 0}
    def _gen_repare(need, genome, origin="forge"):
        _cpt["n"] += 1
        c = Cell(name="repare_au_second_essai", description="Repare au 2e essai", origin=origin,
                 declared_effects={"deletes_data": False, "asks_confirmation": False,
                                   "network_access": False, "authorized_network": False},
                 cursor_scores={"simplicite": 80, "vitesse": 80, "lisibilite": 80})
        c.code = ("def executer(:\n  return" if _cpt["n"] == 1
                  else "def executer(donnees=None):\n    return {'ok': True}\n")
        return c
    faux_gen.generate_cell = _gen_repare
    job4 = lancer_forge_async("Capacite qui se repare", titre="Repare au second essai")
    st4 = _attendre(job4)
    assert st4["etat"] == "integree", st4
    assert st4.get("tentative") == 2, f"doit reussir a la 2e tentative : {st4}"
    print(f"  boucle de reparation : echec t1 -> succes t2 -> integree (tentative {st4['tentative']}) OK")

    # 4. Syntaxe toujours invalide -> refuse apres MAX tentatives + conscience = echouee.
    def _gen_casse(need, genome, origin="forge"):
        c = Cell(name="casse_total", description="x", origin=origin,
                 declared_effects={"deletes_data": False, "asks_confirmation": False,
                                   "network_access": False, "authorized_network": False},
                 cursor_scores={"simplicite": 50, "vitesse": 50, "lisibilite": 50})
        c.code = "def executer(:\n  return"  # toujours invalide
        return c
    faux_gen.generate_cell = _gen_casse
    job3 = lancer_forge_async("Code casse", titre="Casse total")
    st3 = _attendre(job3)
    assert st3["etat"] == "refusee", st3
    assert st3.get("tentative") == MAX_TENTATIVES, st3
    cap_echec = _co.obtenir("casse_total")
    assert cap_echec and cap_echec["statut"] == "echouee", cap_echec
    print(f"  echec persistant : refuse apres {MAX_TENTATIVES} tentatives + conscience='echouee' OK")

    # 5. ISOLATION PAR SAC : un user web forge dans SON sac -> forgee (PAS integree),
    #    invisible du systeme et des autres users (garde-fou agents primordiaux).
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "0"
    os.environ["NEOGEN_OWNER_EMAIL"] = "captain@netroia.com"
    _ns._DATA = _tmp
    _ns._USERS_ROOT = os.path.join(_tmp, "users")
    # Cellule au nom UNIQUE (evite la collision avec la cellule systeme du test 1).
    def _gen_alice(need, genome, origin="forge"):
        c = Cell(name="skill_alice_only", description="Skill propre a Alice", origin=origin,
                 declared_effects={"deletes_data": False, "asks_confirmation": False,
                                   "network_access": False, "authorized_network": False},
                 cursor_scores={"simplicite": 90, "vitesse": 80, "lisibilite": 85})
        c.code = "def executer(donnees=None):\n    return {'ok': True, 'qui': 'alice'}\n"
        return c
    faux_gen.generate_cell = _gen_alice
    alice = {"id": "alice", "email": "alice@x.com"}
    n_sys_avant = len(lister_cellules())  # cellules systeme (owner), inchangees
    job5 = lancer_forge_async("Repare les continuations", titre="Skill Alice", user=alice)
    st5 = _attendre(job5)
    assert st5["etat"] == "forgee", st5            # sac user -> forgee, JAMAIS integree
    assert not st5.get("integ"), st5
    cells_alice = lister_cellules(alice)
    assert cells_alice and any(c["nom"] == st5["nom"] for c in cells_alice), cells_alice
    assert len(lister_cellules()) == n_sys_avant, "la cellule user ne doit PAS polluer le systeme"
    r_inv_alice = _cf.invoquer(st5["nom"])
    assert not r_inv_alice.get("ok"), "une cellule de sac user ne doit PAS etre invocable par le systeme"
    bob = {"id": "bob", "email": "bob@x.com"}
    assert lister_cellules(bob) == [], "bob ne voit pas les cellules d'alice (isolation)"
    print(f"  isolation sac user : '{st5['nom']}' dans le sac alice, invisible systeme/bob OK")

    print("=" * 64)
    print("  TOUT VERT : forge + boucle reparation + integration owner + ISOLATION sac user.")
    print("=" * 64)
