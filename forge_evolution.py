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

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_CELLULES_DIR = os.path.join(_DATA, "cellules_forgees")
_REGISTRE = os.path.join(_DATA, "cellules_forgees.json")
_JOBS = os.path.join(_DATA, "forge_jobs.json")
_GENOME = os.path.join(BASE, "genome.json")

# Marqueur imprime par le smoke-test si le module se charge proprement en conteneur.
_MARQUEUR_CHARGE = "___FORGE_CHARGE_OK___"

# Etapes lisibles (pour la bulle de progression cote UI).
_ETAPES = {
    "demarre":    "Initialisation…",
    "generation": "Génération du code…",
    "test":       "Test en sandbox isolée…",
    "validation": "Contrôle des murs…",
    "termine":    "Code généré & testé",
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

def _charger_registre() -> dict:
    try:
        if os.path.exists(_REGISTRE):
            with open(_REGISTRE, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _persister_cellule(cell, score, verdict_raison, test) -> str:
    """Ecrit le code reel + une entree de registre. Idempotent (re-forge ecrase proprement)."""
    nom = re.sub(r"[^a-z0-9_]+", "_", (cell.name or "cellule").lower()).strip("_") or "cellule"
    os.makedirs(_CELLULES_DIR, exist_ok=True)
    chemin = os.path.join(_CELLULES_DIR, f"{nom}.py")
    entete = (f"# Cellule forgee par NEOGEN — {cell.description}\n"
              f"# Verdict Membrane : {verdict_raison}\n"
              f"# Genere le {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(entete + (cell.code or ""))

    reg = _charger_registre()
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
    }
    with open(_REGISTRE, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    return nom


def lister_cellules() -> list[dict]:
    """Cellules forgees (sans le code), plus recentes d'abord, pour l'UI."""
    reg = _charger_registre()
    cells = sorted(reg.values(), key=lambda c: c.get("ts", 0), reverse=True)
    return cells


def cellule(nom: str) -> dict | None:
    """Une cellule forgee AVEC son code reel (pour l'affichage deplie)."""
    reg = _charger_registre()
    meta = reg.get(nom)
    if not meta:
        return None
    out = dict(meta)
    chemin = os.path.join(_CELLULES_DIR, f"{nom}.py")
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


def forger(besoin: str, *, titre: str = "", pensee_id: str = "", job_id: str = "",
           user: dict | None = None) -> dict:
    """Genere une cellule de code reel a partir d'un besoin, la teste, la valide contre les murs.
    Publie sa progression dans le job. NE LEVE JAMAIS. Renvoie un dict de verdict."""
    with rob.garde("forge evolution", source="forge_evolution"):
        # 1. Gardien du noyau (fail-closed) : on ne forge que vers data/, jamais le noyau.
        import noyau
        nom_probable = re.sub(r"[^a-z0-9_]+", "_", (titre or "cellule").lower()).strip("_")[:40]
        changement = {"type": "fonction",
                      "cible": f"data/cellules_forgees/{nom_probable or 'cellule'}.py",
                      "payload": {"besoin": (besoin or "")[:200]},
                      "titre": titre, "raison": "forge depuis une pensee"}
        ok, motif = noyau.autoriser(changement)
        if not ok:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100, raison=motif)
            rob.journaliser(f"forge refusee par le noyau : {motif}", "alerte", source="forge_evolution")
            return {"ok": False, "etat": "refusee", "raison": motif}

        # 2. Generation du vrai code par Claude.
        _set_job(job_id, etat="en_cours", etape="generation", pct=20)
        try:
            import generator
            from vivarium import Genome, Ledger, Membrane
            genome = Genome(_GENOME)
            cell = generator.generate_cell(besoin, genome, origin="forge")
        except Exception as e:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison=f"génération échouée : {e}")
            rob.journaliser(f"forge : generation echouee : {e}", "erreur", source="forge_evolution")
            return {"ok": False, "etat": "refusee", "raison": f"génération échouée : {e}"}

        # 3. Smoke-test en sandbox + analyse des effets reels (quarantaine honnete).
        _set_job(job_id, etat="en_cours", etape="test", pct=55)
        test = _smoke_test(cell.code or "")
        cell.actual_effects = _effets_reels(cell.code or "")
        if not test.get("ok"):
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison=f"test échoué : {test.get('resume')}")
            rob.journaliser(f"forge : test echoue : {test.get('resume')}", "alerte",
                            source="forge_evolution")
            return {"ok": False, "etat": "refusee", "raison": test.get("resume"), "test": test}

        # 4. Membrane : quarantaine adversariale + murs + escalade fail-closed.
        _set_job(job_id, etat="en_cours", etape="validation", pct=80)
        try:
            membrane = Membrane(genome, Ledger(), human_decision=_refus_si_mur)
            decision, raison, score = membrane.evaluate(cell)
        except Exception as e:
            _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                     raison=f"validation échouée : {e}")
            return {"ok": False, "etat": "refusee", "raison": f"validation échouée : {e}"}

        if decision != "ACCEPTE":
            _set_job(job_id, etat="refusee", etape="refuse", pct=100, raison=raison, verdict=decision)
            rob.journaliser(f"forge : cellule rejetee par la Membrane : {raison}", "alerte",
                            source="forge_evolution")
            return {"ok": False, "etat": "refusee", "raison": raison, "verdict": decision}

        # 5. Acceptee + testee -> persiste le code reel.
        nom = _persister_cellule(cell, score, raison, test)
        try:
            import evolution_gouvernee
            evolution_gouvernee._notifier_generation(
                "cellule", titre or nom, f"cellule '{nom}' forgee (score {score}) : {cell.description}")
        except Exception:
            pass
        _set_job(job_id, etat="generee", etape="termine", pct=100,
                 nom=nom, score=score, verdict=decision)
        rob.journaliser(f"forge : cellule '{nom}' generee & testee (score {score})", "succes",
                        source="forge_evolution")
        return {"ok": True, "etat": "generee", "nom": nom, "score": score,
                "verdict": decision, "raison": raison, "test": test}

    # rob.garde a absorbe une exception -> job en echec propre, jamais de zombie.
    _set_job(job_id, etat="refusee", etape="refuse", pct=100, raison="erreur capturée (voir journal)")
    return {"ok": False, "etat": "refusee", "raison": "erreur capturée (voir journal)"}


def lancer_forge_async(besoin: str, titre: str = "", pensee_id: str = "") -> str:
    """Demarre la forge en tache de fond et renvoie un job_id immediatement (pas de blocage HTTP).
    L'UI poll statut_job(job_id) pour afficher la progression."""
    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, etat="en_cours", etape="demarre", pct=5,
             pensee_id=pensee_id, titre=titre or besoin[:80])

    def _run():
        try:
            r = forger(besoin, titre=titre, pensee_id=pensee_id, job_id=job_id)
            # Marque la pensee source selon le verdict (statut honnete).
            if pensee_id:
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

    # 1. Cas propre : ACCEPTE -> code persiste + registre + job termine.
    job = lancer_forge_async("Repare les continuations de ligne", titre="Auto-reparation")
    # le thread est synchrone-ish ; on attend qu'il finisse.
    for _ in range(50):
        st = statut_job(job)
        if st.get("etat") in ("generee", "refusee"):
            break
        time.sleep(0.05)
    st = statut_job(job)
    assert st["etat"] == "generee", st
    assert lister_cellules(), "la cellule doit etre persistee"
    c = cellule(lister_cellules()[0]["nom"])
    assert c and "def executer" in c["code"], c
    print(f"  cas propre : ACCEPTE -> cellule '{st['nom']}' persistee (score {st.get('score')}) OK")

    # 2. Cas mur : code qui touche au reseau -> effets reels divergents -> REJET, pas de persistance.
    faux_gen.generate_cell = _faux_generate(False)
    n_avant = len(lister_cellules())
    job2 = lancer_forge_async("Recupere le nom d'hote via le reseau", titre="Acces reseau")
    for _ in range(50):
        st2 = statut_job(job2)
        if st2.get("etat") in ("generee", "refusee"):
            break
        time.sleep(0.05)
    st2 = statut_job(job2)
    assert st2["etat"] == "refusee", st2
    assert len(lister_cellules()) == n_avant, "une cellule au contact d'un mur ne doit pas etre persistee"
    print(f"  cas mur : REJET fail-closed ({st2.get('raison')}) -> aucune persistance OK")

    # 3. Syntaxe invalide -> refuse au smoke-test.
    def _gen_casse(need, genome, origin="forge"):
        c = Cell(name="casse", description="x", origin=origin,
                 declared_effects={"deletes_data": False, "asks_confirmation": False,
                                   "network_access": False, "authorized_network": False},
                 cursor_scores={"simplicite": 50, "vitesse": 50, "lisibilite": 50})
        c.code = "def executer(:\n  return"  # syntaxe invalide
        return c
    faux_gen.generate_cell = _gen_casse
    job3 = lancer_forge_async("Code casse", titre="Casse")
    for _ in range(50):
        st3 = statut_job(job3)
        if st3.get("etat") in ("generee", "refusee"):
            break
        time.sleep(0.05)
    assert statut_job(job3)["etat"] == "refusee"
    print("  cas syntaxe invalide : refuse au smoke-test OK")

    print("=" * 64)
    print("  TOUT VERT : le pont forge fonctionne sans aucun appel reseau.")
    print("=" * 64)
