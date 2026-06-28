"""
NEOGEN - L'Ingenieur en action : orchestre « donner vie » a une idee technique.

Quand Jordan donne vie a une idee technique (ou qu'un agent a besoin de code), ce module
fait tourner l'agent INGENIEUR (agent_core.dialoguer + profil 'ingenieur') EN TACHE DE FOND
et publie sa progression dans le meme store de jobs que la forge (data/forge_jobs.json), pour
que l'UI affiche la bulle vivante. L'Ingenieur diagnostique, code (forge a chaud), ancre,
teste, et rapporte — exactement ce que ferait le developpeur humain.

Pourquoi un agent et pas juste la forge : la forge genere UNE cellule. L'Ingenieur, lui,
RAISONNE : il lit le code concerne, decide s'il faut une cellule (a chaud) ou un patch de
module (rebuild), ancre la capacite au bon endroit du flux, teste le resultat, appelle
d'autres agents si besoin, et signale ce qui reste (dettes, rebuild, autorisation noyau).

Robustesse : ne leve jamais ; pas de cle LLM ou erreur -> repli sur la forge directe (le
code prend vie quand meme). Asynchrone borne par MAX_ETAPES de la boucle ReAct.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-28.
"""
from __future__ import annotations

import threading
import uuid

import robustesse as rob


def _set_job(job_id: str, **champs) -> None:
    try:
        import forge_evolution as _fe
        _fe._set_job(job_id, **champs)
    except Exception:
        pass


def statut_job(job_id: str) -> dict:
    import forge_evolution as _fe
    return _fe.statut_job(job_id)


def _mission(besoin: str, titre: str) -> str:
    return (
        f"Donne vie a cette idee technique et rends-la REELLEMENT fonctionnelle : "
        f"« {titre or besoin[:60]} ». Detail : {besoin}\n\n"
        "Suis ta methode DevSecOps : VISION -> DIAGNOSTIC (diagnostic_ingenieur + lis le code "
        "concerne) -> PLAN -> CODE (forge_capacite la fonction manquante PUIS ancre-la dans le "
        "flux pour qu'elle agisse seule ; ou propose_patch si un module existant doit changer) "
        "-> TEST (verifie que ca marche) -> LIVRAISON (rapport clair : ce qui a ete fait, le "
        "verdict du test, les dettes, et si un rebuild/une autorisation est requis). "
        "Agis avec tes outils, ne te contente pas de decrire."
    )


def _run(besoin: str, titre: str, pensee_id: str, job_id: str) -> None:
    """Fait tourner l'Ingenieur et mappe ses etapes vers le job (bulle de progression)."""
    etat = {"pct": 8, "forgee": None, "score": None, "actions": 0}

    def emit(evt):
        try:
            t = evt.get("type")
            if t == "pensee":
                _set_job(job_id, etape="ingenieur", pct=min(etat["pct"], 92),
                         etape_label=("🔧 " + (evt.get("texte", "")[:70] or "réflexion…")))
            elif t == "action":
                etat["actions"] += 1
                etat["pct"] = min(90, etat["pct"] + 12)
                outil = evt.get("outil", "")
                _set_job(job_id, etape="ingenieur", pct=etat["pct"],
                         etape_label=f"🔧 {outil}…")
            elif t == "observation":
                obs = evt.get("texte", "") or ""
                # Capte le nom/score d'une capacite forgee avec succes (pour le verdict final).
                if "forger_capacite" == evt.get("outil") and "'" in obs and "ECHEC" not in obs:
                    try:
                        etat["forgee"] = obs.split("'")[1]
                    except Exception:
                        pass
        except Exception:
            pass

    with rob.garde("ingenieur run", source="ingenieur"):
        try:
            import agent_core as _ac
            _ac.rafraichir_profils()
            rapport = _ac.dialoguer("ingenieur", _mission(besoin, titre),
                                    emit=emit, user={"premium": True, "owner": True})
        except Exception as e:
            rapport = f"(repli) l'Ingenieur n'a pas pu orchestrer : {e}"
            _repli_forge(besoin, titre, pensee_id, job_id)
            return

        # Verdict final : on a forge/integre quelque chose -> 'termine' ; sinon rapport quand meme.
        _set_job(job_id, etat="termine", etape="termine", pct=100,
                 nom=etat["forgee"] or "", score=etat["score"],
                 rapport=(rapport or "")[:1200], mode="ingenieur")
        if pensee_id:
            try:
                import pensee
                pensee.marquer_forge(pensee_id, "generee" if etat["forgee"] else "notee")
            except Exception:
                pass
        rob.journaliser(f"ingenieur : '{titre or besoin[:50]}' traite "
                        f"(forge={etat['forgee'] or 'aucune'}, {etat['actions']} actions)",
                        "succes", source="ingenieur")
        return

    # rob.garde a absorbe une exception -> repli forge pour ne pas laisser le job zombie.
    _repli_forge(besoin, titre, pensee_id, job_id)


def _repli_forge(besoin: str, titre: str, pensee_id: str, job_id: str) -> None:
    """Si l'Ingenieur ne peut pas orchestrer (pas de LLM, erreur), on forge directement :
    l'idee prend vie quand meme (degrade mais fonctionnel)."""
    try:
        import forge_evolution as _fe
        r = _fe.forger(besoin, titre=titre, pensee_id=pensee_id, job_id=job_id)
        if pensee_id:
            try:
                import pensee
                pensee.marquer_forge(pensee_id, "generee" if r.get("ok") else "refusee")
            except Exception:
                pass
    except Exception as e:
        _set_job(job_id, etat="refusee", etape="refuse", pct=100,
                 raison=f"ingenieur + repli indisponibles : {e}")


def lancer_async(besoin: str, titre: str = "", pensee_id: str = "") -> str:
    """Lance l'Ingenieur en tache de fond, renvoie un job_id immediatement (polling UI)."""
    job_id = uuid.uuid4().hex[:12]
    _set_job(job_id, etat="en_cours", etape="demarre", pct=6,
             pensee_id=pensee_id, titre=titre or besoin[:80], mode="ingenieur")
    threading.Thread(target=_run, args=(besoin, titre, pensee_id, job_id), daemon=True).start()
    return job_id


# ── Auto-verification offline (dialoguer mocke, aucun reseau) ─────────────────────

if __name__ == "__main__":
    import sys
    import time
    import types

    print("=" * 64)
    print("NEOGEN - INGENIEUR : auto-verification (offline)")
    print("=" * 64)

    # Mock forge_evolution._set_job / statut_job avec un store memoire.
    _store = {}
    faux_fe = types.ModuleType("forge_evolution")

    def _sj(job_id, **champs):
        j = _store.get(job_id, {"job_id": job_id})
        j.update(champs)
        _store[job_id] = j
    faux_fe._set_job = _sj
    faux_fe.statut_job = lambda jid: _store.get(jid, {"trouve": False})
    faux_fe.forger = lambda besoin, titre="", pensee_id="", job_id="": (
        _sj(job_id, etat="generee", nom="repli_cell", pct=100) or {"ok": True, "nom": "repli_cell"})
    sys.modules["forge_evolution"] = faux_fe

    # Mock agent_core.dialoguer : simule un Ingenieur qui forge puis rapporte.
    faux_ac = types.ModuleType("agent_core")
    faux_ac.rafraichir_profils = lambda: 0

    def _dial(role, message, emit=None, user=None):
        assert role == "ingenieur", role
        if emit:
            emit({"type": "pensee", "texte": "Je diagnostique puis je code."})
            emit({"type": "action", "outil": "diagnostic_ingenieur"})
            emit({"type": "action", "outil": "forger_capacite"})
            emit({"type": "observation", "outil": "forger_capacite",
                  "texte": "[forger_capacite] 'auto_fix' integree (score 88) — ANCREE."})
        return "Fait : capacite auto_fix forgee, testee, ancree a avant_validation_code. RAS."
    faux_ac.dialoguer = _dial
    sys.modules["agent_core"] = faux_ac

    job = lancer_async("Repare les continuations de ligne", titre="Auto-reparation")
    for _ in range(60):
        st = statut_job(job)
        if st.get("etat") in ("termine", "refusee", "generee"):
            break
        time.sleep(0.05)
    st = statut_job(job)
    assert st["etat"] == "termine", st
    assert st["nom"] == "auto_fix", st
    assert "auto_fix" in st["rapport"], st
    print(f"  orchestration : Ingenieur forge+ancre+rapporte -> termine (nom={st['nom']}) OK")

    # Repli : dialoguer casse -> forge directe prend le relais.
    def _dial_casse(role, message, emit=None, user=None):
        raise RuntimeError("pas de cle LLM")
    faux_ac.dialoguer = _dial_casse
    job2 = lancer_async("Autre besoin", titre="Repli")
    for _ in range(60):
        if statut_job(job2).get("etat") in ("termine", "refusee", "generee"):
            break
        time.sleep(0.05)
    st2 = statut_job(job2)
    assert st2["etat"] == "generee" and st2["nom"] == "repli_cell", st2
    print("  repli : LLM indisponible -> forge directe, l'idee prend vie quand meme OK")

    print("=" * 64)
    print("  TOUT VERT : l'Ingenieur orchestre, avec repli forge fail-safe.")
    print("=" * 64)
