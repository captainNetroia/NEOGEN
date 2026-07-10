"""
NEOGEN - Resolveur d'objectif : les 3 etats de connaissance, rendus EXECUTABLES.

Demande de Jordan : que l'appli (agents + fonctions + systeme) sache, face a N'IMPORTE QUEL
objectif, identifier ses INCONNUS et ANGLES MORTS, coder les manques pour les resoudre, et
demander les donnees quand elles sont sensibles — pour s'adapter a toute demande.

C'est la doctrine des 3 etats (CERTAIN / INCONNU / ANGLE MORT) transformee en moteur :

  1. analyser(objectif)  -> decompose l'objectif en ELEMENTS requis, chacun classe :
       - CERTAIN       : une capacite existante le couvre (outil agent ou cellule forgee)
       - INCONNU       : manquant mais FORGEABLE -> on sait quoi generer (besoin_forge)
       - ANGLE_MORT    : ambigu / risque non anticipe -> il faut clarifier (question)
       + drapeau DONNEE_SENSIBLE : une donnee privee est requise -> on la DEMANDE, on n'invente pas.
     L'analyse est ANCREE sur la realite : on injecte la liste des capacites reellement
     disponibles (outils + cellules integrees) pour que « CERTAIN » ne soit jamais une illusion.

  2. resoudre(objectif) -> pour chaque INCONNU forgeable, LANCE la forge (forge_evolution,
     avec sa boucle generate->test->repare->integre) ; collecte les questions (ANGLE_MORT)
     et les demandes de donnees sensibles a renvoyer a l'utilisateur ; trace l'objectif.

Honnetete (doctrine) : ce qui est hors de portee de la forge (action monde reel, integration
tierce) n'est pas hallucine en CERTAIN ; il est route vers l'outil idoine ou declare a clarifier.
Robustesse : ne leve jamais. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-28.
"""
from __future__ import annotations

import json
import os
import time

from pydantic import BaseModel, Field

import gateway
import robustesse as rob
from generator import parse_resilient

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_OBJECTIFS = os.path.join(_DATA, "objectifs.json")

ETATS = ("CERTAIN", "INCONNU", "ANGLE_MORT")


# ── Schema structure de l'analyse (sortie LLM contrainte) ─────────────────────────

class Element(BaseModel):
    description: str = Field(description="l'element/sous-tache requis pour l'objectif, une phrase")
    etat: str = Field(description="CERTAIN (une capacite existante le couvre), INCONNU (manquant "
                                  "mais codable), ou ANGLE_MORT (ambigu/risque a clarifier)")
    capacite_existante: str = Field(default="", description="si CERTAIN : nom EXACT de l'outil ou "
                                                            "de la cellule existante qui le couvre")
    besoin_forge: str = Field(default="", description="si INCONNU et codable : description precise "
                                                      "de la fonction Python autonome a generer")
    question: str = Field(default="", description="si ANGLE_MORT : la question a poser pour lever l'ambiguite")
    donnee_sensible: bool = Field(default=False, description="true si une donnee privee/sensible "
                                                            "(cle, mot de passe, info perso) est requise")
    donnee_demandee: str = Field(default="", description="si donnee_sensible : quelle donnee demander a l'utilisateur")


class AnalyseObjectif(BaseModel):
    faisable: bool = Field(description="l'objectif est-il atteignable avec NEOGEN (forge + outils) ?")
    resume: str = Field(description="synthese honnete : ce qui est faisable, ce qui bloque")
    elements: list[Element] = Field(description="3 a 8 elements requis, chacun classe en CERTAIN/INCONNU/ANGLE_MORT")
    plan: list[str] = Field(description="les etapes ordonnees pour atteindre l'objectif")


# ── I/O suivi des objectifs ───────────────────────────────────────────────────────

def _charger() -> dict:
    try:
        if os.path.exists(_OBJECTIFS):
            with open(_OBJECTIFS, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _sauver(d: dict) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(_OBJECTIFS, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Ancrage : ce que NEOGEN sait DEJA faire (pour que CERTAIN soit reel) ───────────

def _capacites_disponibles() -> str:
    """Liste des capacites reelles (outils agents + cellules forgees integrees) injectee dans
    le prompt : le LLM ne peut classer 'CERTAIN' que ce qui existe vraiment. Ne leve jamais."""
    lignes = []
    try:
        from outils import OUTILS
        for nom, (_fn, desc) in OUTILS.items():
            lignes.append(f"  - [outil] {nom} : {desc[:110]}")
    except Exception:
        pass
    try:
        import capacites_forgees as _cf
        for c in _cf.lister():
            lignes.append(f"  - [cellule] {c['nom']} : {c.get('resume', '')[:110]}")
    except Exception:
        pass
    return "\n".join(lignes) or "  (aucune capacite recensee)"


# ── 1. Analyser : appliquer les 3 etats a l'objectif ──────────────────────────────

def analyser(objectif: str, *, client=None, ctx=None) -> dict:
    """Decompose l'objectif et classe chaque element en CERTAIN/INCONNU/ANGLE_MORT, ancre sur
    les capacites reelles. Renvoie un dict (AnalyseObjectif) + compteurs. Ne leve jamais.
    ctx (gateway.LLMContext) : provider/cle choisis par l'utilisateur (BYOK). Ignore si
    'client' est deja fourni explicitement. None => gateway.client() retombe sur Anthropic
    systeme, comme avant ce fix."""
    with rob.garde("resolveur.analyser", source="resolveur"):
        objectif = (objectif or "").strip()
        if not objectif:
            return {"ok": False, "raison": "objectif vide"}
        capacites = _capacites_disponibles()
        systeme = (
            "Tu es le RESOLVEUR de NEOGEN. Face a un objectif, tu appliques la doctrine des 3 etats "
            "de connaissance, SANS rien inventer.\n\n"
            f"CAPACITES REELLEMENT DISPONIBLES (tu ne peux classer 'CERTAIN' que ce qui figure ici) :\n"
            f"{capacites}\n\n"
            "Pour l'objectif donne :\n"
            "1) Decompose-le en 3 a 8 ELEMENTS requis (sous-taches/briques).\n"
            "2) Classe CHAQUE element :\n"
            "   - CERTAIN : une capacite ci-dessus le couvre -> donne son nom EXACT dans capacite_existante.\n"
            "   - INCONNU : manquant mais codable en Python autonome -> decris la fonction dans besoin_forge.\n"
            "   - ANGLE_MORT : ambigu, risque, ou hors de portee (action monde reel sans outil) -> "
            "pose la question dans 'question'.\n"
            "3) Si un element exige une DONNEE SENSIBLE (cle API, mot de passe, info perso, secret), "
            "mets donnee_sensible=true et precise donnee_demandee : on la DEMANDERA, jamais on n'inventera.\n"
            "4) Donne un PLAN d'etapes ordonnees, et dis honnetement si l'objectif est faisable.\n\n"
            "Sois lucide : ne classe pas 'CERTAIN' par optimisme. Un doute = ANGLE_MORT. "
            "Une brique de code manquante mais ecrivable = INCONNU (elle sera forgee)."
        )
        try:
            cl = client or gateway.client(ctx, tier="fort")
            resp = parse_resilient(
                cl, max_tokens=4000,
                thinking={"type": "adaptive"}, system=systeme,
                messages=[{"role": "user", "content": f"Objectif : {objectif}"}],
                output_format=AnalyseObjectif,
            )
            if resp.parsed_output is None:
                return {"ok": False, "raison": "analyse non produite par le modele"}
            a = resp.parsed_output
        except Exception as e:
            rob.journaliser(f"resolveur : analyse echouee : {e}", "erreur", source="resolveur")
            return {"ok": False, "raison": f"analyse echouee : {e}"}

        elements = [_norm_element(e) for e in a.elements]
        compteurs = {et: sum(1 for e in elements if e["etat"] == et) for et in ETATS}
        return {"ok": True, "objectif": objectif, "faisable": bool(a.faisable),
                "resume": a.resume, "elements": elements, "plan": list(a.plan),
                "compteurs": compteurs,
                "donnees_sensibles": [e["donnee_demandee"] for e in elements if e["donnee_sensible"]]}
    return {"ok": False, "raison": "erreur capturee"}


def _norm_element(e) -> dict:
    etat = (e.etat or "").strip().upper().replace(" ", "_")
    if etat not in ETATS:
        etat = "ANGLE_MORT"   # tout doute -> angle mort (jamais CERTAIN par defaut)
    return {"description": e.description, "etat": etat,
            "capacite_existante": e.capacite_existante or "", "besoin_forge": e.besoin_forge or "",
            "question": e.question or "", "donnee_sensible": bool(e.donnee_sensible),
            "donnee_demandee": e.donnee_demandee or ""}


# ── 2. Resoudre : forger les INCONNUS, demander les donnees, tracer l'objectif ─────

def resoudre(objectif: str, *, auto_forge: bool = True, client=None, ctx=None) -> dict:
    """Analyse l'objectif puis AGIT : forge chaque INCONNU codable (forge_evolution async),
    collecte les ANGLES MORTS (questions) et les DONNEES SENSIBLES a demander. Trace l'objectif.
    Ne leve jamais. Renvoie {analyse, forges, questions, donnees_a_demander, objectif_id}."""
    with rob.garde("resolveur.resoudre", source="resolveur"):
        an = analyser(objectif, client=client, ctx=ctx)
        if not an.get("ok"):
            return an

        forges, questions, donnees = [], [], []
        for e in an["elements"]:
            if e["donnee_sensible"] and e["donnee_demandee"]:
                donnees.append(e["donnee_demandee"])
            if e["etat"] == "ANGLE_MORT" and e["question"]:
                questions.append(e["question"])
            if e["etat"] == "INCONNU" and e["besoin_forge"] and auto_forge:
                try:
                    import forge_evolution
                    job_id = forge_evolution.lancer_forge_async(
                        e["besoin_forge"], titre=e["description"][:80])
                    forges.append({"element": e["description"], "besoin": e["besoin_forge"],
                                   "job_id": job_id})
                except Exception as ex:
                    forges.append({"element": e["description"], "erreur": str(ex)})

        oid = _slug(objectif) + "_" + format(int(time.time()) % 100000, "x")
        store = _charger()
        store[oid] = {
            "id": oid, "objectif": objectif, "ts": time.time(),
            "faisable": an["faisable"], "resume": an["resume"], "plan": an["plan"],
            "compteurs": an["compteurs"], "elements": an["elements"],
            "forges": forges, "questions": questions, "donnees_a_demander": donnees,
            "statut": ("attente_donnees" if donnees else
                       "attente_clarification" if questions else
                       "forge_en_cours" if forges else "pret"),
        }
        _sauver(store)
        rob.journaliser(
            f"resolveur : objectif '{objectif[:50]}' -> {an['compteurs']} ; "
            f"{len(forges)} forge(s), {len(questions)} question(s), {len(donnees)} donnee(s)",
            "info", source="resolveur")
        return {"ok": True, "objectif_id": oid, "analyse": an, "forges": forges,
                "questions": questions, "donnees_a_demander": donnees,
                "statut": store[oid]["statut"]}
    return {"ok": False, "raison": "erreur capturee"}


def lister_objectifs() -> list[dict]:
    return sorted(_charger().values(), key=lambda o: o.get("ts", 0), reverse=True)


def objectif(oid: str) -> dict | None:
    return _charger().get(oid)


def _slug(txt: str) -> str:
    import re
    return (re.sub(r"[^a-z0-9]+", "_", (txt or "").lower()).strip("_")[:40]) or "objectif"


# ── Auto-verification offline (LLM mocke, aucun reseau, forge mockee) ──────────────

if __name__ == "__main__":
    import sys
    import tempfile
    import types

    print("=" * 64)
    print("NEOGEN - RESOLVEUR D'OBJECTIF : auto-verification (offline)")
    print("=" * 64)
    _DATA = tempfile.mkdtemp()
    _OBJECTIFS = os.path.join(_DATA, "objectifs.json")

    # LLM mocke : renvoie une analyse couvrant les 3 etats + une donnee sensible.
    class _Resp:
        def __init__(self, parsed): self.parsed_output = parsed
    def _faux_parse(client, **kw):
        return _Resp(AnalyseObjectif(
            faisable=True,
            resume="Faisable : 1 brique existe, 1 a forger, 1 a clarifier, 1 donnee a demander.",
            elements=[
                Element(description="Convertir des montants", etat="CERTAIN",
                        capacite_existante="creer_application"),
                Element(description="Calculer un score de risque maison", etat="INCONNU",
                        besoin_forge="fonction score_risque(donnees: dict) -> float, pure, sans I/O"),
                Element(description="Choisir le barème fiscal applicable", etat="ANGLE_MORT",
                        question="Quel pays/regime fiscal vise-t-on ?"),
                Element(description="Se connecter a la banque", etat="INCONNU",
                        besoin_forge="appel API bancaire", donnee_sensible=True,
                        donnee_demandee="cle API bancaire (a stocker dans credentials/)"),
            ],
            plan=["clarifier le regime", "forger le score", "demander la cle", "assembler"],
        ))
    # Remplace le LLM + la forge par des mocks (zero reseau).
    sys.modules["resolveur"] = sys.modules[__name__]
    globals()["parse_resilient"] = _faux_parse
    globals()["_client"] = lambda: object()
    faux_forge = types.ModuleType("forge_evolution")
    faux_forge.lancer_forge_async = lambda besoin, titre="", pensee_id="": "job_" + format(abs(hash(besoin)) % 9999, "x")
    sys.modules["forge_evolution"] = faux_forge

    # 1. analyser : 3 etats correctement comptes.
    a = analyser("Construire un outil d'analyse financiere")
    assert a["ok"], a
    assert a["compteurs"] == {"CERTAIN": 1, "INCONNU": 2, "ANGLE_MORT": 1}, a["compteurs"]
    assert a["donnees_sensibles"], a
    print(f"  analyser : 3 etats classes {a['compteurs']} + donnee sensible reperee OK")

    # 2. resoudre : forge les INCONNUS, collecte questions + donnees, trace l'objectif.
    r = resoudre("Construire un outil d'analyse financiere")
    assert r["ok"], r
    assert len(r["forges"]) == 2, r["forges"]            # 2 INCONNU codables -> 2 forges lancees
    assert r["questions"], r                              # 1 ANGLE_MORT -> question
    assert r["donnees_a_demander"], r                     # 1 donnee sensible -> demande
    assert r["statut"] == "attente_donnees", r            # priorite : on demande les donnees d'abord
    print(f"  resoudre : {len(r['forges'])} forge(s) lancee(s), {len(r['questions'])} question(s), "
          f"{len(r['donnees_a_demander'])} donnee(s) -> statut '{r['statut']}' OK")

    # 3. tracage persistant.
    assert objectif(r["objectif_id"]), "objectif non trace"
    assert len(lister_objectifs()) == 1
    print("  objectif trace + listable OK")

    print("=" * 64)
    print("  TOUT VERT : NEOGEN applique les 3 etats a tout objectif et agit (forge + demandes).")
    print("=" * 64)
