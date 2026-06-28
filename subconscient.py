"""
NEOGEN - Subconscient : le moteur de REVE (non dirige, generatif).

La ou le conscient (resolveur, pensee) poursuit un BUT, le subconscient DIVAGUE sur la
memoire-graphe de NEOGEN pendant le sommeil (cycle de maintenance) et fait emerger des idees
sans-objectif, recompensees pour leur NOUVEAUTE et non leur utilite immediate. C'est ce qui
produit du jamais-vu, ensuite forgeable en vrai code.

Techniques (validees par recherche NotebookLM 2026-06-28, cf. Documentation-Projets/NEOGEN/
recherche-subconscient.md) :
  - CONSOLIDATION (Sleep Replay Consolidation, Tadros 2022) : graphe_associatif.consolider().
  - BISOCIATION + CONCEPTUAL BLENDING (Koestler ; Fauconnier-Turner) : on fusionne deux concepts
    ELOIGNES (deux_noeuds_distants) via le LLM (composition -> completion -> elaboration).
  - CREATIVITE TRANSFORMATIONNELLE / « self-soothing » (Crowder) : de temps en temps, on relache
    une contrainte / on exagere pour forcer un saut conceptuel.
  - NOVELTY SEARCH (Lehman & Stanley) : score = distance moyenne aux k plus proches reves d'une
    ARCHIVE permanente, PAS une fitness d'objectif. Le neuf est recompense en tant que tel.

Gouvernance : un reve emergent (nouveaute >= seuil) devient une PENSEE de type « reve » qui
remonte dans la bulle existante ; l'humain decide de lui donner vie. Ne touche jamais au noyau.
Ne leve jamais. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-28.
"""
from __future__ import annotations

import json
import os
import random
import time

from pydantic import BaseModel, Field

import robustesse as rob
import graphe_associatif as G

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_ARCHIVE = os.path.join(_DATA, "reves_archive.json")

SEUIL_REVE = 0.62          # nouveaute minimale pour qu'un reve emerge (sinon : oublie)
SEUIL_REVE_INGENIEUR = 0.85  # MAILLON B : au-dela, un reve EXCEPTIONNEL peut declencher l'Ingenieur
                             # (seulement si la config reve_auto_ingenieur est activee par Jordan)
K_VOISINS = 3              # k plus proches voisins pour la metrique de nouveaute


class Reve(BaseModel):
    titre: str = Field(description="titre court et evocateur de l'idee qui emerge")
    idee: str = Field(description="l'idee originale nee de la fusion des deux concepts, 2-4 phrases, "
                                  "concrete et actionnable, pas philosophique")


# ── Archive des reves (Novelty Search) ─────────────────────────────────────────────

def _archive() -> list:
    try:
        if os.path.exists(_ARCHIVE):
            with open(_ARCHIVE, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, list) else []
    except Exception:
        pass
    return []


def _sauver_archive(arch: list) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(_ARCHIVE, "w", encoding="utf-8") as f:
            json.dump(arch[-500:], f, ensure_ascii=False, indent=2)   # borne
    except Exception:
        pass


def _mots(texte: str) -> set:
    return set(G._mots_cles(texte, n=12))


def scorer_nouveaute(titre: str, idee: str) -> float:
    """Novelty Search : nouveaute = distance moyenne (1 - Jaccard) aux K reves les plus proches
    de l'archive. Archive vide -> 1.0 (tout est nouveau au debut). Renvoie 0..1."""
    mots = _mots(f"{titre} {idee}")
    if not mots:
        return 0.0
    arch = _archive()
    if not arch:
        return 1.0
    dists = []
    for r in arch:
        ma = set(r.get("mots", []))
        if not ma:
            continue
        inter = len(mots & ma)
        union = len(mots | ma) or 1
        dists.append(1.0 - inter / union)        # distance de Jaccard
    if not dists:
        return 1.0
    dists.sort()
    k = dists[:K_VOISINS]
    return round(sum(k) / len(k), 3)


# ── Le reve : bisociation de deux concepts distants via le LLM ─────────────────────

def _client_reve():
    """Client LLM du reve : suit le MODE configure pour la pensee (eco/fort/mixte). En eco c'est
    Ollama local (gratuit) ; en fort/mixte un provider systeme si une cle existe (sinon repli eco).
    Repli silencieux si indisponible -> rever() renvoie None proprement (jamais de cout impose)."""
    import pensee
    mode = pensee._config().get("mode", "eco")
    cl, _tier, _mode = pensee._resoudre_client(mode)
    return cl


def rever(client=None) -> dict | None:
    """Un cycle de reve : choisit deux concepts ELOIGNES du graphe et les fusionne (blend) via
    le LLM. De temps en temps, exagere/relache une contrainte (saut conceptuel). Renvoie un dict
    {titre, idee, paire, nouveaute} ou None si le graphe est trop pauvre / LLM indispo. Ne leve jamais."""
    with rob.garde("subconscient.rever", source="subconscient"):
        g = G.charger()
        if len(g.get("noeuds", {})) < 4:
            return None
        a, b = G.deux_noeuds_distants(g)
        if not a or not b:
            return None
        la, lb = G.label(g, a), G.label(g, b)

        exagere = random.random() < 0.33
        consigne_saut = (
            "\nMODE ONIRIQUE : relache une contrainte de bon sens, ose l'association absurde ou "
            "interdite, pousse l'idee la ou personne n'irait (creativite transformationnelle)."
            if exagere else
            "\nReste surprenant mais coherent : l'idee doit pouvoir devenir une vraie fonctionnalite."
        )
        systeme = (
            "Tu es le SUBCONSCIENT de NEOGEN qui reve. Tu ne resous pas un probleme : tu FAIS EMERGER "
            "une idee neuve en FUSIONNANT deux concepts eloignes (bisociation / conceptual blending).\n"
            "Methode : 1) compose (croise les attributs des deux concepts), 2) complete (importe le "
            "contexte qui rend le melange coherent), 3) elabore (deroule la logique propre du melange).\n"
            f"{consigne_saut}\n"
            "Donne un titre court et une idee concrete (2-4 phrases), actionnable pour une appli qui "
            "se forge elle-meme en Python. Pas de blabla philosophique."
        )
        message = (f"Concept A : « {la} ». Concept B : « {lb} ». "
                   f"Fais emerger l'idee neuve qui naît de leur fusion.")
        try:
            import gateway
            from generator import parse_resilient
            cl = client or _client_reve()
            resp = parse_resilient(
                cl, model=getattr(cl, "model", None) or gateway.TIERS["anthropic"]["moyen"],
                max_tokens=1200, system=systeme,
                messages=[{"role": "user", "content": message}],
                output_format=Reve,
            )
            if resp.parsed_output is None:
                return None
            r = resp.parsed_output
        except Exception as e:
            rob.journaliser(f"subconscient : reve avorte ({e})", "info", source="subconscient")
            return None

        nouveaute = scorer_nouveaute(r.titre, r.idee)
        return {"titre": r.titre[:80], "idee": r.idee[:600], "paire": [la, lb],
                "exagere": exagere, "nouveaute": nouveaute}
    return None


# ── Le cycle complet : consolider -> rever -> faire emerger les reves nouveaux ─────

def cycle_reve(n: int = 3, client=None) -> dict:
    """Sommeil de NEOGEN : (1) reconstruit + consolide le graphe, (2) genere n reves,
    (3) les reves assez NOUVEAUX deviennent des pensees type « reve » (remontee en bulle) et
    entrent dans l'archive. Ne leve jamais. Renvoie un resume."""
    with rob.garde("subconscient.cycle_reve", source="subconscient"):
        G.construire()
        G.consolider()
        arch = _archive()
        reves, emergents = [], []
        for _ in range(max(1, n)):
            r = rever(client=client)
            if not r:
                continue
            reves.append(r)
            if r["nouveaute"] >= SEUIL_REVE:
                # Emergence : devient une pensee « reve » (score = nouveaute -> bulle si >= 0.70).
                try:
                    import pensee
                    syn = (f"{r['idee']}  (rêve né de la fusion : {r['paire'][0]} × {r['paire'][1]})")
                    pensee._enregistrer({"titre": r["titre"], "synthese": syn, "type": "reve",
                                         "origine": "subconscient"}, r["nouveaute"])
                except Exception:
                    pass
                arch.append({"titre": r["titre"], "mots": list(_mots(f"{r['titre']} {r['idee']}")),
                             "nouveaute": r["nouveaute"], "ts": time.time()})
                emergents.append(r)
                # MAILLON B : un reve EXCEPTIONNEL peut prendre vie tout seul via l'Ingenieur,
                # mais SEULEMENT si Jordan a active reve_auto_ingenieur (humain dernier mot).
                if r["nouveaute"] >= SEUIL_REVE_INGENIEUR:
                    _peut_ingenieur = False
                    try:
                        import pensee as _p
                        _peut_ingenieur = bool(_p._config().get("reve_auto_ingenieur"))
                    except Exception:
                        _peut_ingenieur = False
                    if _peut_ingenieur:
                        try:
                            import ingenieur as _ing
                            besoin = (f"Rêve exceptionnel de NEOGEN (nouveauté {r['nouveaute']:.2f}) : "
                                      f"{r['idee']}. Si cette idée est techniquement réalisable et utile, "
                                      f"forge la capacité correspondante et ancre-la ; sinon explique "
                                      f"pourquoi en une ligne.")
                            _ing.lancer_async(besoin, titre=r["titre"])
                            rob.journaliser(f"subconscient : reve exceptionnel '{r['titre']}' "
                                            f"({r['nouveaute']:.2f}) confie a l'Ingenieur (auto)",
                                            "succes", source="subconscient")
                        except Exception as e:
                            rob.journaliser(f"subconscient : echec declenchement Ingenieur ({e})",
                                            "info", source="subconscient")
        _sauver_archive(arch)
        if emergents:
            rob.journaliser(f"subconscient : {len(emergents)}/{len(reves)} reve(s) emergent(s) "
                            f"(remontes en bulle)", "succes", source="subconscient")
        return {"ok": True, "reves": len(reves), "emergents": len(emergents),
                "details": emergents}
    return {"ok": False}


def lister_reves(limit: int = 30) -> list:
    """Reves archives (les plus recents/nouveaux d'abord) pour l'UI/diagnostic."""
    return sorted(_archive(), key=lambda r: r.get("ts", 0), reverse=True)[:limit]


def etat() -> dict:
    return {"reves_archives": len(_archive()), "graphe": G.etat()}


# ── Auto-verification offline (LLM mocke, graphe temporaire, pensee mockee) ─────────

if __name__ == "__main__":
    import sys
    import tempfile
    import types

    print("=" * 64)
    print("NEOGEN - SUBCONSCIENT : auto-verification (offline)")
    print("=" * 64)
    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _ARCHIVE = os.path.join(_tmp, "reves_archive.json")
    G._DATA = _tmp
    G._GRAPHE = os.path.join(_tmp, "graphe_associatif.json")
    random.seed(7)

    # Graphe minimal de deux mondes distants.
    g = G._vide()
    for lab, t in [("migraine", "savoir"), ("calcium", "savoir"), ("magnesium", "cellule"),
                   ("interface", "pensee"), ("musique", "pensee"), ("fiscalite", "savoir")]:
        G.ajouter_noeud(g, lab, t)
    G.lier(g, "migraine", "calcium", 2)
    G.sauver(g)

    # LLM mocke : renvoie un Reve deterministe.
    class _Resp:
        def __init__(self, p): self.parsed_output = p
    _compteur = {"n": 0}
    def _faux_parse(client, **kw):
        _compteur["n"] += 1
        return _Resp(Reve(titre=f"Idee onirique {_compteur['n']}",
                          idee=f"Fusion inattendue numero {_compteur['n']} entre des mondes distants "
                               f"produisant un mecanisme concret et original applicable a l'appli."))
    sys.modules["generator"] = types.ModuleType("generator")
    sys.modules["generator"].parse_resilient = _faux_parse
    # client reve mocke (evite Ollama).
    globals()["_client_reve"] = lambda: types.SimpleNamespace(model="mock")

    # pensee mockee : capture les emergences (evite d'ecrire dans le vrai pensees.jsonl).
    captures = []
    faux_pensee = types.ModuleType("pensee")
    faux_pensee._enregistrer = lambda d, s: captures.append((d, s))
    faux_pensee._resoudre_client = lambda mode: (types.SimpleNamespace(model="mock"), "moyen", "eco")
    sys.modules["pensee"] = faux_pensee

    # 1. scorer_nouveaute : archive vide -> 1.0, puis baisse avec un quasi-doublon.
    assert scorer_nouveaute("titre alpha", "idee beta gamma delta") == 1.0
    _sauver_archive([{"titre": "x", "mots": list(_mots("idee beta gamma delta epsilon"))}])
    n2 = scorer_nouveaute("titre alpha", "idee beta gamma delta")
    assert n2 < 1.0, n2
    print(f"  novelty search : archive vide=1.0, quasi-doublon={n2} (< 1.0) OK")
    _sauver_archive([])   # reset

    # 2. rever : fusionne deux concepts distants, renvoie une idee scoree.
    r = rever()
    assert r and r["titre"] and r["paire"][0] != r["paire"][1], r
    print(f"  rever : « {r['titre']} » <- fusion {r['paire']} (nouveaute {r['nouveaute']}) OK")

    # 3. cycle_reve : des reves nouveaux emergent en pensees + entrent dans l'archive.
    res = cycle_reve(n=4)
    assert res["ok"] and res["emergents"] >= 1, res
    assert captures, "au moins un reve doit remonter en pensee"
    assert len(_archive()) >= 1, "l'archive doit grandir"
    print(f"  cycle_reve : {res['emergents']}/{res['reves']} emergent(s) -> bulle + archive OK")

    print("=" * 64)
    print("  TOUT VERT : NEOGEN reve (bisociation + novelty search) et fait emerger du neuf.")
    print("=" * 64)
