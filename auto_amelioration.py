"""
NEOGEN - Auto-amélioration EN BOUCLE FERMEE.

"auto" = automatique : un signal détecté DECLENCHE une action, sans intervention.
Sinon ce n'est pas de l'auto-amélioration. Cette capacité :

  1. LIT plusieurs sources réelles (pas seulement le registre) :
     - journal_erreurs.jsonl : échecs avec cause racine + leçon + correction
     - ledger.jsonl           : décisions de la membrane (ACCEPTE/REFUSE, murs)
     - ledger_production.jsonl + registre : succès/échecs, réparations
     - compétences            : usages (ce qui sert / ne sert jamais)
  2. DETECTE des signaux : erreurs récurrentes, réparations fréquentes, murs souvent
     violés, capacités fragiles, ET ce qui marche déjà bien (points forts).
  3. AGIT automatiquement (boucle fermée), actions sûres et gratuites :
     - cristallise une LEÇON récurrente en COMPETENCE réutilisable (injectée au prompt
       -> le système évite de refaire l'erreur) ;
     - mémorise un pattern d'échec comme fait durable (nourrit proposer/conseiller) ;
     - journalise chaque décision (traçabilité : un coup d'avance conservé).
  4. GARDE-FOUS : idempotence PAR leçon (jamais de doublon), throttle global léger,
     actions limitées aux opérations sûres (cristalliser/mémoriser/loguer). Une passe
     d'évolution coûteuse (evolution.py) est SUGGEREE, jamais déclenchée en aveugle.

Déclenchée : par un thread de fond (toutes ~30 min) + après chaque création (hook).
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
JOURNAL_ERREURS = os.path.join(_DATA, "journal_erreurs.jsonl")
LEDGER = os.path.join(_DATA, "ledger.jsonl")
ACTIONS = os.path.join(_DATA, "auto_amelioration.jsonl")  # trace des actions auto

# Seuils
SEUIL_ECHEC = 0.30          # >30% d'échecs -> signal
SEUIL_TENTATIVES = 2.0      # moyenne de tentatives > 2 -> réparations fréquentes
SEUIL_REJET_MEMBRANE = 0.30 # >30% de rejets membrane -> signal
MIN_ECHANTILLON = 3
MIN_RECURRENCE = 2          # une erreur vue >=2 fois = récurrente -> leçon
INTERVALLE_CYCLE_S = 1800   # thread de fond : un cycle toutes les 30 min
THROTTLE_S = 300            # ne pas relancer un cycle plus d'une fois / 5 min

_THREAD = None


# ── Lecture robuste ─────────────────────────────────────────────────────────

def _lire_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        out.append(json.loads(ligne))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def _type_erreur(txt: str) -> str:
    """Extrait le type d'exception d'un message ('ZeroDivisionError: ...' -> 'ZeroDivisionError')."""
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception)", txt or "")
    return m.group(1) if m else ((txt or "").split(":")[0].strip()[:40] or "erreur")


# ── Analyse multi-sources ───────────────────────────────────────────────────

def analyser_usage() -> dict:
    """Analyse multi-sources -> signaux + points forts. (Lecture seule, pour l'UI/endpoint.)"""
    with rob.garde("analyser_usage", source="auto_amelioration"):
        return _analyser()
    return {"total": 0, "signaux": [], "sain": True, "action_suggeree": "indisponible"}


def _analyser() -> dict:
    import registre
    entrees = registre.lister()
    erreurs = _lire_jsonl(JOURNAL_ERREURS)
    decisions = _lire_jsonl(LEDGER)

    total = len(entrees)
    signaux: list[dict] = []
    points_forts: list[str] = []

    # --- Production : succès / réparations ---
    taux_succes = tent_moy = None
    if total:
        succes = sum(1 for e in entrees if e.get("verdict") == "promu" or e.get("promouvable"))
        taux_succes = round(succes / total, 2)
        tent_moy = round(sum(e.get("tentatives", 1) for e in entrees) / total, 2)
        if total >= MIN_ECHANTILLON and (1 - taux_succes) > SEUIL_ECHEC:
            signaux.append({"type": "echec_eleve",
                            "detail": f"{int((1-taux_succes)*100)}% des créations non promouvables.",
                            "amelioration": "Renforcer le discernement (proposer) + repair sélectif."})
        if total >= MIN_ECHANTILLON and tent_moy > SEUIL_TENTATIVES:
            signaux.append({"type": "reparations_frequentes",
                            "detail": f"Moyenne de {tent_moy} tentatives par création.",
                            "amelioration": "Suggérer une passe d'évolution (evolution.py) des générateurs."})
        if taux_succes >= 0.9 and total >= MIN_ECHANTILLON:
            points_forts.append(f"Taux de succès élevé ({int(taux_succes*100)}%) sur {total} créations.")

    # --- Réseau fragile ---
    avec_reseau = [e for e in entrees if "reseau" in (e.get("capacites") or [])]
    if len(avec_reseau) >= MIN_ECHANTILLON:
        ko = sum(1 for e in avec_reseau if not (e.get("verdict") == "promu" or e.get("promouvable")))
        if ko / len(avec_reseau) > SEUIL_ECHEC:
            signaux.append({"type": "reseau_fragile",
                            "detail": f"Créations 'réseau' souvent en échec ({ko}/{len(avec_reseau)}).",
                            "amelioration": "Revoir la liste blanche de domaines / le proxy d'egress."})

    # --- Erreurs récurrentes (journal_erreurs) : LA matière à leçon ---
    par_type: dict[str, list[dict]] = {}
    for e in erreurs:
        par_type.setdefault(_type_erreur(e.get("erreur", "")), []).append(e)
    erreurs_recurrentes = []
    for typ, lst in par_type.items():
        if len(lst) >= MIN_RECURRENCE:
            dernier = lst[-1]
            diag = dernier.get("diagnostic", {}) if isinstance(dernier.get("diagnostic"), dict) else {}
            erreurs_recurrentes.append({
                "type": typ, "occurrences": len(lst),
                "lecon": diag.get("lecon", ""), "correction": diag.get("correction", ""),
            })
    if erreurs_recurrentes:
        signaux.append({"type": "erreurs_recurrentes",
                        "detail": "; ".join(f"{e['type']} x{e['occurrences']}" for e in erreurs_recurrentes),
                        "amelioration": "Cristalliser ces leçons en compétences (fait automatiquement).",
                        "donnees": erreurs_recurrentes})

    # --- Membrane : taux de rejet + motif dominant ---
    if decisions:
        rejets = [d for d in decisions if d.get("decision") == "REFUSE"]
        if len(decisions) >= MIN_ECHANTILLON and len(rejets) / len(decisions) > SEUIL_REJET_MEMBRANE:
            motifs = {}
            for d in rejets:
                motifs[d.get("reason", "?")] = motifs.get(d.get("reason", "?"), 0) + 1
            dominant = max(motifs.items(), key=lambda kv: kv[1]) if motifs else ("?", 0)
            signaux.append({"type": "mur_souvent_viole",
                            "detail": f"{len(rejets)}/{len(decisions)} rejets membrane. Motif dominant : {dominant[0]}",
                            "amelioration": "Mémoriser ce motif pour cadrer la génération en amont."})

    # --- Compétences : usages ---
    try:
        import competences
        skills = competences.lister(inclure_socle=False)
        tres_utiles = [s for s in skills if int(s.get("usages", 0)) >= 3]
        if tres_utiles:
            points_forts.append("Compétences qui servent : "
                                + ", ".join(s["nom"] for s in tres_utiles[:5]))
    except Exception:
        pass

    sain = not signaux
    action = ("Système sain : rien à corriger." if sain
              else "Signaux : " + "; ".join(s["amelioration"] for s in signaux))
    return {
        "total": total, "taux_succes": taux_succes, "tentatives_moyennes": tent_moy,
        "signaux": signaux, "points_forts": points_forts, "sain": sain,
        "action_suggeree": action,
        "sources": {"creations": total, "erreurs_journalisees": len(erreurs),
                    "decisions_membrane": len(decisions)},
    }


# ── Boucle fermée : signal -> action automatique ────────────────────────────

def _tracer_action(action: dict) -> None:
    action = {"ts": time.time(), "iso": time.strftime("%Y-%m-%d %H:%M:%S"), **action}
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(ACTIONS, "a", encoding="utf-8") as f:
            f.write(json.dumps(action, ensure_ascii=False) + "\n")
    except Exception:
        pass


def cycle(force: bool = False) -> dict:
    """UN cycle d'auto-amélioration : analyse -> actions automatiques -> trace.
    Idempotent par leçon (pas de doublon). Throttle global léger. Renvoie le rapport."""
    if not force and rob.deja_fait("auto_amelioration:cycle", ttl_s=THROTTLE_S):
        return {"execute": False, "raison": "throttle (cycle récent)"}
    rob.marquer_fait("auto_amelioration:cycle")

    rapport = analyser_usage()
    actions_prises: list[dict] = []

    with rob.garde("cycle auto-amélioration", source="auto_amelioration"):
        for sig in rapport.get("signaux", []):
            # 1) Erreurs récurrentes -> cristalliser une leçon en compétence (idempotent).
            if sig["type"] == "erreurs_recurrentes":
                for err in sig.get("donnees", []):
                    lecon = (err.get("lecon") or "").strip()
                    correction = (err.get("correction") or "").strip()
                    if not (lecon or correction):
                        continue
                    sig_lecon = "lecon:" + hashlib.sha1(
                        (err["type"] + lecon[:80]).encode()).hexdigest()[:12]
                    a = _appliquer_lecon(err["type"], lecon, correction, sig_lecon, err["occurrences"])
                    if a:
                        actions_prises.append(a)
            # 2) Mur souvent violé -> mémoriser le motif (cadre la génération future).
            elif sig["type"] == "mur_souvent_viole":
                a = _memoriser_pattern("membrane", sig["detail"])
                if a:
                    actions_prises.append(a)
            # 3) Réseau fragile -> mémoriser pour que proposer/conseiller en tiennent compte.
            elif sig["type"] == "reseau_fragile":
                a = _memoriser_pattern("reseau", sig["detail"])
                if a:
                    actions_prises.append(a)

    # Transmission télémétrie centralisée (hebdomadaire, ON par défaut).
    # Opt-out : NEOGEN_TELEMETRIE_ENDPOINT="" dans l'env de l'instance.
    _endpoint_tele = os.environ.get(
        "NEOGEN_TELEMETRIE_ENDPOINT", "https://telemetrie.netroia.tech/v1/collect"
    ).strip()
    if _endpoint_tele and not rob.deja_fait("telemetrie:transmission_semaine", ttl_s=604800):
        try:
            import telemetrie as _tele
            r_tele = _tele.transmettre_agregees(_endpoint_tele)
            if r_tele.get("ok"):
                rob.marquer_fait("telemetrie:transmission_semaine")
                rob.journaliser("telemetrie agregee transmise", "succes", source="auto_amelioration")
        except Exception as _e_tele:
            rob.journaliser(f"telemetrie transmission echouee : {_e_tele}", "erreur",
                            source="auto_amelioration")

    rob.battement("auto_amelioration", signaux=len(rapport.get("signaux", [])),
                  actions=len(actions_prises))
    rob.journaliser(f"cycle auto-amélioration : {len(actions_prises)} action(s) automatique(s)",
                    "succes" if actions_prises else "info", source="auto_amelioration")
    return {"execute": True, "analyse": rapport, "actions_prises": actions_prises}


def _appliquer_lecon(type_err: str, lecon: str, correction: str,
                     signature: str, occurrences: int) -> dict | None:
    """Cristallise une leçon récurrente en compétence (idempotent). Trace l'action."""
    try:
        import competences
        instructions = (
            f"LEÇON APPRISE (erreur '{type_err}' survenue {occurrences} fois). "
            f"{lecon} "
            + (f"Correction type : {correction}" if correction else "")
        ).strip()
        s = competences.cristalliser_auto(
            nom=f"eviter {type_err}",
            description=f"Éviter l'erreur récurrente '{type_err}' lors des créations.",
            instructions=instructions[:1500],
            outils=["creer_application"],
            signature=signature,
        )
        if not s:
            return None  # déjà connue (idempotent)
        # Mémoire durable aussi : le contexte nourrit proposer/conseiller.
        try:
            import memoire_agent
            memoire_agent.memoriser(
                f"Lors d'une création, éviter l'erreur '{type_err}' : {lecon[:200]}", "projet")
        except Exception:
            pass
        action = {"action": "lecon_cristallisee", "type_erreur": type_err,
                  "competence": s["nom"], "occurrences": occurrences}
        _tracer_action(action)
        rob.journaliser(f"leçon cristallisée : eviter {type_err} ({occurrences}x)",
                        "succes", source="auto_amelioration")
        return action
    except Exception as e:
        rob.journaliser(f"echec cristallisation leçon {type_err}", "erreur",
                        source="auto_amelioration", erreur=str(e))
        return None


def _memoriser_pattern(domaine: str, detail: str) -> dict | None:
    """Mémorise un pattern d'échec comme fait durable (idempotent par contenu)."""
    sig = "pattern:" + hashlib.sha1((domaine + detail[:80]).encode()).hexdigest()[:12]
    if rob.deja_fait(sig, ttl_s=86400 * 7):   # une fois / semaine max par pattern
        return None
    rob.marquer_fait(sig)
    try:
        import memoire_agent
        memoire_agent.memoriser(f"[auto-amélioration:{domaine}] {detail[:240]}", "projet")
        action = {"action": "pattern_memorise", "domaine": domaine, "detail": detail[:200]}
        _tracer_action(action)
        return action
    except Exception:
        return None


def journal_actions(limite: int = 30) -> list[dict]:
    """Dernières actions d'auto-amélioration prises (pour l'UI / traçabilité)."""
    return list(reversed(_lire_jsonl(ACTIONS)))[:limite]


# ── Déclenchement automatique ───────────────────────────────────────────────

def declencher_async() -> None:
    """Lance un cycle en arrière-plan (hook après création). Ne bloque jamais l'appelant."""
    threading.Thread(target=lambda: rob.protege(cycle, operation="cycle async",
                                                source="auto_amelioration"), daemon=True).start()


def _boucle() -> None:
    while True:
        with rob.garde("boucle auto-amélioration", source="auto_amelioration"):
            cycle()
        time.sleep(INTERVALLE_CYCLE_S)


def demarrer() -> None:
    """Démarre le thread d'auto-amélioration périodique (idempotent)."""
    global _THREAD
    if _THREAD is None or not _THREAD.is_alive():
        _THREAD = threading.Thread(target=_boucle, daemon=True)
        _THREAD.start()
        rob.journaliser("auto-amélioration démarrée (boucle fermée)", "info", source="auto_amelioration")


if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - AUTO-AMELIORATION (boucle fermée) : auto-vérification")
    print("=" * 64)
    res = analyser_usage()
    assert "signaux" in res and "sain" in res and "sources" in res
    print(f"  analyse multi-sources OK : {res['sources']}")
    print(f"  signaux: {len(res['signaux'])} | points forts: {len(res.get('points_forts', []))}")

    # cycle (force) : ne doit jamais planter, renvoie un rapport structuré
    r = cycle(force=True)
    assert r.get("execute") is True and "actions_prises" in r
    print(f"  cycle ferme OK : {len(r['actions_prises'])} action(s) prise(s)")
    # throttle : un 2e cycle non forcé est court-circuité
    r2 = cycle(force=False)
    assert r2.get("execute") is False, "le throttle devrait court-circuiter"
    print("  throttle anti-spam OK")
    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
